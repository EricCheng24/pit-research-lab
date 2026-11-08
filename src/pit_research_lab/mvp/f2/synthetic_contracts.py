"""WU-01 local input validation, not Native qualification or App DTOs.

Diagnostics deliberately retain PROPOSED_FND_ names from the reviewed packet.
Only source structure, exact numbers, time representation and explicit coverage
are checked. Unknown facts are valid input facts, never invented numeric values.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

SCHEMA = "mvp-f2-synthetic-input-v0.1"
ENCODING = "wu01-local-input-json-v0.1:ascii-sorted-compact"
MODE = "SYNTHETIC_GOLDEN"
ZONE = "Asia/Taipei"
OFFSET = "+08:00"
UNKNOWN_CAUSES = frozenset(
    {"ABSENT_SOURCE_FIELD", "EXPLICIT_SOURCE_UNKNOWN", "AMBIGUOUS_SOURCE", "UNMAPPED"}
)
PRICE_STATES = frozenset({"KNOWN", "UNKNOWN", "MISSING", "HALT", "WITHHELD"})
REVENUE_STATES = frozenset({"KNOWN", "UNKNOWN", "MISSING", "WITHHELD"})
INSTANT_KEYS = frozenset({"source_text", "timezone_name", "offset", "precision", "origin_ref"})
REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "tick_id",
        "tick_order",
        "cutoff",
        "calendar_ref",
        "manifest_ref",
        "config_ref",
        "context_ref",
        "issuer_refs",
        "requested_feature_refs",
        "data_mode",
        "decision_frequency",
    }
)


class InputError(ValueError):
    """Finite local structural diagnostic; never a Native BlockingFailure."""

    def __init__(self, suffix: str, path: str = "") -> None:
        self.code = "PROPOSED_FND_" + suffix
        self.path = path
        super().__init__(self.code + (":" + path if path else ""))


def require(condition: bool, code: str, path: str = "") -> None:
    if not condition:
        raise InputError(code, path)


def mapping(value: object, path: str = "") -> dict[str, Any]:
    require(type(value) is dict, "OBJECT_REQUIRED", path)
    result = cast(dict[str, Any], value)
    require(all(type(k) is str for k in result), "SCHEMA_KEYS", path)
    return result


def keys(value: dict[str, Any], expected: set[str] | frozenset[str], path: str = "") -> None:
    require(set(value) == expected, "SCHEMA_KEYS", path)


def text(value: object, path: str = "") -> str:
    require(type(value) is str and bool(value), "TEXT_REQUIRED", path)
    return cast(str, value)


def integer(value: object, path: str = "") -> int:
    require(type(value) is int, "EXACT_INTEGER_REQUIRED", path)
    return cast(int, value)


def records(value: object, path: str = "") -> list[Any]:
    require(type(value) is list, "ARRAY_REQUIRED", path)
    return cast(list[Any], value)


def unique_texts(value: object, path: str = "") -> list[str]:
    result = [text(v, path) for v in records(value, path)]
    require(bool(result) and len(result) == len(set(result)), "DUPLICATE_OR_EMPTY_REFS", path)
    return result


def local_date(value: object, path: str = "") -> date:
    raw = text(value, path)
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is not None, "INVALID_DATE", path)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise InputError("INVALID_DATE", path) from exc


def parse_instant(value: object) -> datetime:
    """Validate original SECOND/zone/offset and return its UTC comparison value."""
    obj = mapping(value, "instant")
    raw = text(obj.get("source_text"), "source_text")
    require(
        obj.get("offset") is not None and re.search(r"[+-]\d{2}:?\d{2}$|Z$", raw) is not None,
        "AWARE_INSTANT_REQUIRED",
    )
    offset = obj.get("offset")
    require(
        type(offset) is str
        and re.fullmatch(r"[+-]\d{2}:\d{2}", offset) is not None
        and re.search(r"[+-]\d{2}:\d{2}$", raw) is not None,
        "OFFSET_FORMAT",
    )
    require(
        obj.get("precision") == "SECOND"
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", raw) is not None,
        "SECOND_PRECISION_REQUIRED",
    )
    keys(obj, INSTANT_KEYS, "instant")
    text(obj["origin_ref"], "origin_ref")
    require(
        obj["timezone_name"] == ZONE and offset == OFFSET and raw.endswith(OFFSET),
        "ZONE_OFFSET_MISMATCH",
    )
    try:
        stamp = datetime.fromisoformat(raw)
        local = stamp.astimezone(ZoneInfo(ZONE))
    except ValueError as exc:
        raise InputError("INVALID_INSTANT") from exc
    require(
        local.utcoffset() == stamp.utcoffset()
        and local.replace(tzinfo=None) == stamp.replace(tzinfo=None),
        "ZONE_OFFSET_MISMATCH",
    )
    return stamp.astimezone(UTC)


def validate_time_fact(value: object) -> datetime | None:
    obj = mapping(value, "publication")
    state = obj.get("state")
    if state == "KNOWN":
        require(bool(obj.get("proof_ref")), "TIME_PROOF_MISSING")
        require(obj.get("proof_kind") == "EXACT", "UNSUPPORTED_PROOF_KIND")
        keys(obj, {"state", "instant", "proof_kind", "proof_ref", "origin_ref"}, "publication")
        text(obj["proof_ref"])
        text(obj["origin_ref"])
        return parse_instant(obj["instant"])
    require(state == "UNKNOWN", "INVALID_TIME_FACT_STATE")
    keys(obj, {"state", "unknown_cause", "source_text", "origin_ref"}, "publication")
    require(
        type(obj["unknown_cause"]) is str and obj["unknown_cause"] in UNKNOWN_CAUSES,
        "UNKNOWN_CAUSE_REQUIRED",
    )
    require(obj["source_text"] is None or type(obj["source_text"]) is str, "TEXT_REQUIRED")
    text(obj["origin_ref"])
    return None


@dataclass(frozen=True)
class TimeRelation:
    relation: Literal["BEFORE", "AT", "AFTER", "UNKNOWN"]
    reason: str | None = None
    unknown_causes: tuple[str, ...] = ()


def compare_input_instants(left: object, right: object) -> TimeRelation:
    """Relational input helper only: no admissibility, version choice or labels."""

    def operand(value: object) -> tuple[datetime | None, tuple[str, ...]]:
        obj = mapping(value)
        if "state" in obj:
            moment = validate_time_fact(obj)
            return moment, (obj["unknown_cause"],) if moment is None else ()
        return parse_instant(obj), ()

    a, ac = operand(left)
    b, bc = operand(right)
    if a is None or b is None:
        return TimeRelation("UNKNOWN", "PROPOSED_FND_INSTANT_UNRESOLVED", ac + bc)
    return TimeRelation("BEFORE" if a < b else "AFTER" if a > b else "AT")


def _no_fraction(_: str) -> object:
    raise InputError("EXACT_INTEGER_REQUIRED")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def decode_input_bytes(body: bytes) -> Any:
    require(type(body) is bytes, "BYTES_REQUIRED")
    try:
        return json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_no_fraction,
            parse_constant=_no_fraction,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InputError("INVALID_INPUT_JSON") from exc


def input_bytes(value: object) -> bytes:
    """Local authored input encoding only, NOT an App/result canonical oracle."""

    def check(item: object) -> None:
        if item is None or type(item) in (str, int, bool):
            return
        if type(item) is list:
            for child in cast(list[Any], item):
                check(child)
            return
        if type(item) is dict:
            for k, v in mapping(item).items():
                text(k)
                check(v)
            return
        raise InputError(
            "EXACT_INTEGER_REQUIRED" if isinstance(item, float) else "JSON_VALUE_REQUIRED"
        )

    check(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def payload_pin(body: bytes) -> str:
    require(type(body) is bytes, "BYTES_REQUIRED")
    return sha256(body).hexdigest()


def validate_calendar(spec: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    coverage = mapping(spec["coverage"])
    keys(coverage, {"start", "end"})
    start, end = (local_date(coverage[k]) for k in ("start", "end"))
    require(start <= end, "INVALID_COVERAGE")
    rows = [mapping(v) for v in records(spec["calendar"])]
    ids = [v.get("session_id") for v in rows if v.get("status") == "SESSION"]
    require(len(ids) == len(set(text(v) for v in ids)), "DUPLICATE_SESSION_ID")
    days: list[date] = []
    for row in rows:
        day = local_date(row.get("date"))
        require(start <= day <= end, "SESSION_OUT_OF_COVERAGE")
        days.append(day)
        if row.get("status") == "CLOSED":
            require(not ({"session_id", "open", "close"} & row.keys()), "CONTRADICTORY_SESSION")
            keys(row, {"date", "status", "reason", "origin_ref"})
            text(row["reason"])
        else:
            require(row.get("status") == "SESSION", "INVALID_SESSION_STATE")
            keys(row, {"date", "status", "session_id", "open", "close", "origin_ref"})
            opened, closed = parse_instant(row["open"]), parse_instant(row["close"])
            require(opened < closed, "CONTRADICTORY_SESSION")
            require(
                all(
                    datetime.fromisoformat(row[k]["source_text"]).date() == day
                    for k in ("open", "close")
                ),
                "SESSION_DATE_MISMATCH",
            )
        text(row["origin_ref"])
    require(len(days) == len(set(days)), "CONTRADICTORY_SESSION")
    require(days == sorted(days), "CALENDAR_ORDER")
    require(
        days == [start + timedelta(days=i) for i in range((end - start).days + 1)],
        "CALENDAR_COVERAGE_GAP",
    )
    window = mapping(spec["decision_window"])
    keys(window, {"start", "end"})
    a, b = (local_date(window[k]) for k in ("start", "end"))
    require(start <= a <= b <= end, "DECISION_WINDOW_OUT_OF_COVERAGE")
    require(a.weekday() == 0 and b.weekday() == 6, "INCOMPLETE_DECISION_WEEK")
    return tuple(row for row in rows if row["status"] == "SESSION")


def _source_value(obj: dict[str, Any], value_key: str, price: bool = False) -> set[str]:
    state = obj.get("state")
    allowed_states = PRICE_STATES if price else REVENUE_STATES
    state_error = "INVALID_SOURCE_STATE" if price else "INVALID_REVENUE_STATE"
    require(type(state) is str and state in allowed_states, state_error)
    if state == "KNOWN":
        require(value_key in obj, "KNOWN_VALUE_MISSING")
        value = integer(obj[value_key], value_key)
        if price:
            require(value > 0, "NONPOSITIVE_PRICE")
        else:
            require(-(2**63) <= value < 2**63, "REVENUE_INT64_RANGE")
        return {value_key}
    require(value_key not in obj, "NONKNOWN_NUMERIC_VALUE_FORBIDDEN")
    text(obj.get("reason"), "reason")
    if state == "UNKNOWN":
        require(
            type(obj.get("unknown_cause")) is str and obj["unknown_cause"] in UNKNOWN_CAUSES,
            "UNKNOWN_CAUSE_REQUIRED",
        )
        return {"reason", "unknown_cause"}
    return {"reason"}


def validate_price_record(value: object) -> None:
    obj = mapping(value, "price")
    extra = _source_value(obj, "coefficient", price=True)
    require(obj.get("unit") == "NTD_price", "PRICE_UNIT_MISMATCH")
    require(obj.get("currency") == "NTD", "CURRENCY_MISMATCH")
    require(type(obj.get("scale")) is int and obj["scale"] == 6, "PRICE_SCALE_MISMATCH")
    keys(
        obj,
        {
            "price_ref",
            "issuer_ref",
            "session_ref",
            "kind",
            "state",
            "unit",
            "currency",
            "scale",
            "event_time",
            "available_at",
            "source_ref",
            "version_ref",
            "origin_ref",
        }
        | extra,
    )
    require(type(obj["kind"]) is str and obj["kind"] in {"OPEN", "CLOSE"}, "UNSUPPORTED_PRICE_KIND")
    for key in (
        "price_ref",
        "issuer_ref",
        "session_ref",
        "source_ref",
        "version_ref",
        "origin_ref",
    ):
        text(obj[key], key)
    require(
        parse_instant(obj["event_time"]) <= parse_instant(obj["available_at"]),
        "AVAILABILITY_PRECEDES_EVENT",
    )


def validate_roster(value: object) -> list[str]:
    ids: list[str] = []
    for raw in records(value):
        obj = mapping(raw)
        keys(
            obj,
            {
                "issuer_ref",
                "membership",
                "valid_from",
                "valid_through",
                "publication",
                "currency",
                "reporting_scope",
                "source_ref",
                "version_ref",
                "origin_ref",
            },
        )
        ids.append(text(obj["issuer_ref"]))
        member = mapping(obj["membership"])
        state = member.get("state")
        if state == "KNOWN":
            keys(member, {"state", "value", "origin_ref"})
            require(integer(member["value"]) in (0, 1), "INVALID_MEMBERSHIP_FLAG")
        else:
            require(state == "UNKNOWN", "INVALID_MEMBERSHIP_STATE")
            keys(member, {"state", "unknown_cause", "source_text", "origin_ref"})
            require(
                type(member["unknown_cause"]) is str and member["unknown_cause"] in UNKNOWN_CAUSES,
                "UNKNOWN_CAUSE_REQUIRED",
            )
            require(
                member["source_text"] is None or type(member["source_text"]) is str, "TEXT_REQUIRED"
            )
        text(member["origin_ref"])
        require(
            local_date(obj["valid_from"]) <= local_date(obj["valid_through"]),
            "INVALID_MEMBERSHIP_PERIOD",
        )
        validate_time_fact(obj["publication"])
        for key in ("currency", "reporting_scope", "source_ref", "version_ref", "origin_ref"):
            text(obj[key])
    require(bool(ids) and len(ids) == len(set(ids)), "DUPLICATE_OR_EMPTY_ISSUERS")
    return ids


def validate_revenue(value: object, issuers: list[str]) -> dict[str, dict[str, Any]]:
    versions: dict[str, dict[str, Any]] = {}
    event_ids: set[str] = set()
    for raw in records(value):
        obj = mapping(raw)
        require("publication" in obj, "MISSING_PUBLICATION_FACT")
        extra = _source_value(obj, "amount")
        require(obj.get("unit") == "NTD_thousands", "REVENUE_UNIT_MISMATCH")
        require(obj.get("currency") == "NTD", "CURRENCY_MISMATCH")
        keys(
            obj,
            {
                "event_ref",
                "issuer_ref",
                "reference_month",
                "state",
                "unit",
                "currency",
                "basis_ref",
                "reporting_scope",
                "source_ref",
                "content_ref",
                "representation_ref",
                "version_ref",
                "publication",
                "effective_time",
                "observed_at",
                "supersedes_ref",
                "origin_ref",
            }
            | extra,
        )
        require(obj["issuer_ref"] in issuers, "UNKNOWN_ISSUER_REF")
        month = text(obj["reference_month"])
        require(re.fullmatch(r"\d{4}-\d{2}", month) is not None, "INVALID_REFERENCE_MONTH")
        local_date(month + "-01")
        validate_time_fact(obj["publication"])
        for key in ("effective_time", "observed_at"):
            if obj[key] is not None:
                parse_instant(obj[key])
        for key in (
            "event_ref",
            "basis_ref",
            "reporting_scope",
            "source_ref",
            "content_ref",
            "representation_ref",
            "version_ref",
            "origin_ref",
        ):
            text(obj[key], key)
        require(
            obj["version_ref"] not in versions and obj["event_ref"] not in event_ids,
            "DUPLICATE_SOURCE_IDENTITY",
        )
        versions[obj["version_ref"]] = obj
        event_ids.add(obj["event_ref"])
    for version, obj in versions.items():
        parent = obj["supersedes_ref"]
        if parent is not None:
            require(
                type(parent) is str and parent in versions and parent != version,
                "BROKEN_REVISION_LINK",
            )
            prev = versions[parent]
            require(
                all(
                    obj[k] == prev[k]
                    for k in (
                        "issuer_ref",
                        "reference_month",
                        "unit",
                        "currency",
                        "basis_ref",
                        "reporting_scope",
                    )
                ),
                "BROKEN_REVISION_LINK",
            )
    for version, obj in versions.items():
        parent = obj["supersedes_ref"]
        seen = {version}
        while parent is not None:
            require(parent not in seen, "REVISION_CYCLE")
            seen.add(parent)
            parent = versions[parent]["supersedes_ref"]
    return versions


SPEC_KEYS = frozenset(
    {
        "schema_version",
        "pack_id",
        "pack_version",
        "generator",
        "data_mode",
        "source_spec_ref",
        "provenance",
        "limitations",
        "calendar_ref",
        "config_ref",
        "manifest_ref",
        "coverage",
        "decision_window",
        "calendar",
        "roster",
        "revenue_events",
        "source_coverage",
        "price_template",
        "endpoint_facts",
        "requested_feature_refs",
        "decision_frequency",
    }
)


def validate_source_spec(value: object) -> dict[str, Any]:
    """Validate source/header/calendar facts; build_pack also checks prices/endpoints."""
    obj = mapping(value, "input_spec")
    require("source_coverage" in obj, "SOURCE_COVERAGE_MISSING")
    keys(obj, SPEC_KEYS, "input_spec")
    require(obj["schema_version"] == SCHEMA, "UNSUPPORTED_SCHEMA")
    require(obj["data_mode"] == MODE, "UNSUPPORTED_DATA_MODE")
    require(obj["decision_frequency"] == "WEEKLY", "UNSUPPORTED_FREQUENCY")
    for key in (
        "pack_id",
        "pack_version",
        "source_spec_ref",
        "calendar_ref",
        "config_ref",
        "manifest_ref",
    ):
        text(obj[key], key)
    generator = mapping(obj["generator"])
    keys(generator, {"generator_id", "version"})
    text(generator["generator_id"])
    text(generator["version"])
    provenance = mapping(obj["provenance"])
    keys(provenance, {"kind", "origin_ref"})
    require(provenance["kind"] == "SYNTHETIC_AUTHORED", "UNSUPPORTED_PROVENANCE")
    text(provenance["origin_ref"])
    unique_texts(obj["limitations"])
    unique_texts(obj["requested_feature_refs"])
    validate_calendar(obj)
    issuers = validate_roster(obj["roster"])
    events = validate_revenue(obj["revenue_events"], issuers)
    coverage = mapping(obj["source_coverage"])
    keys(coverage, {"scope_ref", "issuer_refs", "event_refs", "status", "origin_ref"})
    text(coverage["scope_ref"])
    text(coverage["origin_ref"])
    require(
        type(coverage["status"]) is str
        and coverage["status"] in {"AUTHOR_DECLARED_COMPLETE_WITHIN_PACK", "UNKNOWN"},
        "INVALID_SOURCE_COVERAGE",
    )
    require(set(unique_texts(coverage["issuer_refs"])) == set(issuers), "SOURCE_COVERAGE_MISMATCH")
    declared = records(coverage["event_refs"])
    require(
        all(type(x) is str for x in declared)
        and len(declared) == len(set(declared))
        and set(declared) == {e["event_ref"] for e in events.values()},
        "SOURCE_COVERAGE_MISMATCH",
    )
    return obj


def serialize_tick_request(value: object) -> bytes:
    """Strict request-only surface, NOT an admitted snapshot or policy observation."""
    obj = mapping(value, "tick_request")
    extra = sorted(set(obj) - REQUEST_KEYS)
    require(not extra, "FORBIDDEN_DECISION_FIELD", extra[0] if extra else "")
    keys(obj, REQUEST_KEYS, "tick_request")
    require(obj["schema_version"] == SCHEMA, "UNSUPPORTED_SCHEMA")
    require(obj["data_mode"] == MODE, "UNSUPPORTED_DATA_MODE")
    require(obj["decision_frequency"] == "WEEKLY", "UNSUPPORTED_FREQUENCY")
    require(integer(obj["tick_order"]) >= 0, "INVALID_TICK_ORDER")
    for key in ("tick_id", "calendar_ref", "manifest_ref", "config_ref", "context_ref"):
        text(obj[key], key)
    cutoff = mapping(obj["cutoff"])
    nested_extra = sorted(set(cutoff) - INSTANT_KEYS)
    require(
        not nested_extra,
        "FORBIDDEN_DECISION_FIELD",
        "cutoff." + nested_extra[0] if nested_extra else "",
    )
    parse_instant(cutoff)
    unique_texts(obj["issuer_refs"])
    unique_texts(obj["requested_feature_refs"])
    return input_bytes(obj)
