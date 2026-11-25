"""Closed, detached U1 presentation data and local snapshot identity."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime
from typing import Any, NoReturn, cast
from uuid import UUID

type Record = dict[str, Any]
SCHEMA = "F6_HISTORICAL_SYNTHETIC_F5_VIEW_V1"
EDITION = "WEEKLY_MODE_S_F5_ACCEPTED_01"
HISTORICAL_WU = "MVP-F5-WEEKLY-SYNTHETIC-COMPARE-01"
COMPLETE = "COMPLETE_COMPARABLE_SYNTHETIC"
QUESTION = "Does PIT monthly revenue growth predict subsequent synthetic returns?"
METHOD = "OLS_INTERCEPT_ONE_REGRESSOR_V1"
FIT_WORDING = "17:00_FIRST_TEST_SESSION"
FITS = ("2025-02-14T17:00:00+08:00", "2025-08-01T17:00:00+08:00")
ISSUERS = tuple(f"SYN-L1-{i}" for i in range(1, 6))
POLICIES = ("BENCHMARK", "A", "B")
FIRST_TICK = 48
AFTER_LAST_TICK = 96
MAX_VIEW = 2 * 1024 * 1024
MAX_HTML = 4 * 1024 * 1024
SNAPSHOT_DOMAIN = "F6-HISTORICAL-SYNTHETIC-F5-VIEW-V1"
BUILD_DOMAIN = SNAPSHOT_DOMAIN + "-BUILD"
RELEASE_DOMAIN = SNAPSHOT_DOMAIN + "-RELEASE"
UNAVAILABLE = frozenset(
    (
        "UNKNOWN_EDITION",
        "ARCHIVE_MISSING",
        "PEER_MISSING",
        "PAIR_INCOMPLETE",
        "PAIR_DEGRADED",
        "PAIR_FAILED",
    )
)
FAILED = frozenset(
    (
        "UNSAFE_INPUT",
        "INPUT_CHANGED",
        "ARCHIVE_PIN",
        "ARCHIVE_STRUCTURE",
        "MANIFEST_PIN",
        "MEMBER_MISMATCH",
        "PROVENANCE_MISMATCH",
        "RECEIPT_MISMATCH",
        "BOUNDS_EXCEEDED",
        "INPUT_IO",
        "UNSUPPORTED_SCHEMA",
        "MALFORMED_JSON",
    )
)
OUTPUT_FAILURES = frozenset(("UNSAFE_OUTPUT", "OUTPUT_IO"))
REASONS = UNAVAILABLE | FAILED | OUTPUT_FAILURES | {"EDITION_WITHHELD", "INVALID_INVOCATION"}
MISSING = ("UNKNOWN", "WITHHELD", "ABSENT", "NOT_EVALUATED", "REJECTED")
INFORMATION_REASONS = tuple("INFORMATION_" + state for state in MISSING)
ISSUER_REASONS = (
    "QUALIFIED_UNIVERSE_MEMBER",
    "POSITIVE_GROWTH_SELECTED",
    "NONPOSITIVE_GROWTH",
    "POSITIVE_FORECAST_SELECTED",
    "NONPOSITIVE_FORECAST",
    "NOT_RECORDED",
    *INFORMATION_REASONS,
)
LIMITATIONS = (
    "DESCRIPTIVE_SYNTHETIC_ONLY",
    "RUN_A_REALTIME_DISCONTINUITY",
    "NO_INDEPENDENT_HISTORICAL_TIMING_AUTHORITY",
)
HEX64 = r"[0-9a-f]{64}"
SHELL_SAFE_REF = r"[A-Za-z0-9:._-]{1,80}"
COMMON = "schema status build_sha256 attempt_id observed_at snapshot_id"
COVERAGE = {
    "ticks": 48,
    "valid_slots": 144,
    "oos_cells": 240,
    "historical_bindings": 480,
    "qualified_marks": 1205,
    "mark_sessions": 241,
    "rebalance_records": 288,
    "valuation_records": 1446,
}
DIGEST_FIELDS = (
    "f3_experiment_ref f3_protocol_ref dataset_digest source_fixture_sha256 "
    "f3_evidence_sha256 f5_evidence_sha256 archive_sha256 archive_manifest_sha256 "
    "effective_report_sha256"
)


class Refusal(Exception):
    """An outward-facing refusal containing only a closed code."""

    def __init__(self, code: str) -> None:
        if code not in REASONS:
            raise ValueError("unrecognized refusal")
        self.code = code
        super().__init__(code)


def fail(code: str) -> NoReturn:
    raise Refusal(code)


def require(condition: object, code: str = "UNSUPPORTED_SCHEMA") -> None:
    if not condition:
        fail(code)


def record(value: object, fields: str, code: str = "UNSUPPORTED_SCHEMA") -> Record:
    require(type(value) is dict, code)
    row = cast(Record, value)
    require(row.keys() == set(fields.split()), code)
    return row


def array(value: object, count: int, code: str = "UNSUPPORTED_SCHEMA") -> list[Any]:
    require(type(value) is list, code)
    items = cast(list[Any], value)
    require(len(items) == count, code)
    return items


def integer(value: object, lo: int, hi: int, code: str = "UNSUPPORTED_SCHEMA") -> int:
    require(type(value) is int, code)
    number = cast(int, value)
    require(lo <= number <= hi, code)
    return number


def text(value: object, pattern: str, code: str = "UNSUPPORTED_SCHEMA") -> str:
    require(type(value) is str, code)
    result = cast(str, value)
    require(re.fullmatch(pattern, result, flags=re.ASCII) is not None, code)
    return result


def choice(value: object, options: tuple[str, ...], code: str = "UNSUPPORTED_SCHEMA") -> str:
    require(type(value) is str and value in options, code)
    return cast(str, value)


def uuid4_text(value: object, code: str = "UNSUPPORTED_SCHEMA") -> str:
    result = text(
        value, r"[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}", code
    )
    require(UUID(result).version == 4, code)
    return result


def timestamp(value: object, *, utc: bool = False, code: str = "UNSUPPORTED_SCHEMA") -> datetime:
    prefix = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    ending = r"\.[0-9]{6}Z" if utc else r"\+08:00"
    result = text(value, prefix + ending, code)
    try:
        return datetime.fromisoformat(result)
    except ValueError:
        fail(code)


def fraction(value: object, *, unit: str | None = None) -> tuple[int, int]:
    fields = "numerator denominator" if unit is None else "kind unit numerator denominator"
    obj = record(value, fields)
    if unit is not None:
        require(obj["unit"] == unit and obj["kind"] == "EXACT_FRACTION")
    n = int(text(obj["numerator"], r"0|-?[1-9][0-9]{0,4095}"))
    d = int(text(obj["denominator"], r"[1-9][0-9]{0,4095}"))
    require(math.gcd(n, d) == 1)
    return n, d


def exact(value: object, unit: str = "RATIO") -> Record:
    fraction(value)
    raw = cast(Record, value)
    return {
        "kind": "EXACT_FRACTION",
        "unit": unit,
        "numerator": raw["numerator"],
        "denominator": raw["denominator"],
    }


def decimal12(value: object) -> str:
    return text(value, r"(?:0|[1-9][0-9]{0,23})\.[0-9]{12}")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def identify(domain: str, value: object) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def _wire_tree(value: object) -> None:
    if type(value) is str:
        require(all(unicodedata.category(c) not in ("Cc", "Cf", "Cs") for c in value))
    elif type(value) is list:
        for item in cast(list[object], value):
            _wire_tree(item)
    elif type(value) is dict:
        for key, item in cast(dict[object, object], value).items():
            require(type(key) is str)
            _wire_tree(key)
            _wire_tree(item)
    else:
        require(type(value) in (int, bool, type(None)))


def _missing_reason(value: object, state: str) -> None:
    reason = choice(value, (*INFORMATION_REASONS, "NOT_RECORDED"))
    if state in MISSING:
        require(reason in ("INFORMATION_" + state, "NOT_RECORDED"))


def _fact(value: object, cutoff: datetime) -> None:
    require(type(value) is dict)
    fact = cast(Record, value)
    state = choice(fact.get("state"), ("KNOWN", *MISSING))
    if state == "KNOWN":
        record(fact, "state month publication available_at qualification")
        month = text(fact["month"], r"[0-9]{4}-(?:0[1-9]|1[0-2])")
        require(month[:4] != "0000")
        require(timestamp(fact["publication"]) <= timestamp(fact["available_at"]) < cutoff)
        require(fact["qualification"] == "QUALIFIED_SYNTHETIC")
    else:
        record(fact, "state reason")
        _missing_reason(fact["reason"], state)


def _signal(value: object) -> None:
    require(type(value) is dict)
    signal = cast(Record, value)
    state = choice(signal.get("state"), ("VALUE", "UNAVAILABLE", *MISSING))
    if state == "VALUE":
        fraction(record(signal, "state metric")["metric"], unit="RATIO")
    else:
        _missing_reason(record(signal, "state reason")["reason"], state)


def _weight(value: object) -> None:
    n, d = fraction(value, unit="RATIO")
    require(0 <= n <= d)


def _trace(value: object, cutoff: datetime, policy: str) -> None:
    row = record(value, "policy slot disposition cash_weight weights event reference_at posted_at")
    require(row["policy"] == policy and row["slot"] == "VALID")
    choice(row["disposition"], ("ALLOCATE", "CASH", "ABSTAIN"))
    choice(row["event"], ("TRADE", "NO_TRADE"))
    require(cutoff < timestamp(row["reference_at"]) < timestamp(row["posted_at"]))
    _weight(row["cash_weight"])
    for alias, raw in zip(ISSUERS, array(row["weights"], len(ISSUERS)), strict=True):
        weight = record(raw, "issuer weight recorded_reason")
        require(weight["issuer"] == alias)
        _weight(weight["weight"])
        choice(weight["recorded_reason"], ISSUER_REASONS)


def _tick(value: object, expected: int) -> Record:
    tick = record(value, "tick cutoff fold information_ref issuers policies")
    require(integer(tick["tick"], FIRST_TICK, AFTER_LAST_TICK - 1) == expected)
    require(tick["fold"] == ("F1" if expected < 72 else "F2"))
    cutoff = timestamp(tick["cutoff"])
    text(tick["information_ref"], HEX64)
    for alias, row in zip(ISSUERS, array(tick["issuers"], len(ISSUERS)), strict=True):
        issuer = record(row, "issuer scope current_revenue preceding_revenue growth forecast")
        require(issuer["issuer"] == alias and type(issuer["scope"]) is dict)
        scope = issuer["scope"]
        if scope.get("state") == "QUALIFIED_SYNTHETIC":
            record(scope, "state")
        else:
            require(record(scope, "state reason")["state"] == "UNAVAILABLE")
            _missing_reason(scope["reason"], "UNAVAILABLE")
        _fact(issuer["current_revenue"], cutoff)
        _fact(issuer["preceding_revenue"], cutoff)
        _signal(issuer["growth"])
        _signal(issuer["forecast"])
    for policy, row in zip(POLICIES, array(tick["policies"], len(POLICIES)), strict=True):
        _trace(row, cutoff, policy)
    return tick


def _overview(value: object) -> Record:
    overview = record(
        value,
        "question method frequency seed forecast_sessions first_cutoff last_cutoff "
        "terminal_at fit_clock_wording actual_fits issuers coverage fee_rate slippage_rate initial_cash",
    )
    require(
        overview["question"] == QUESTION
        and overview["method"] == METHOD
        and overview["frequency"] == "WEEKLY"
        and integer(overview["seed"], 17, 17) == 17
        and integer(overview["forecast_sessions"], 20, 20) == 20
        and overview["fit_clock_wording"] == FIT_WORDING
        and overview["issuers"] == list(ISSUERS)
    )
    require(
        timestamp(overview["first_cutoff"])
        < timestamp(overview["last_cutoff"])
        < timestamp(overview["terminal_at"])
    )
    for ix, raw in enumerate(array(overview["actual_fits"], 2)):
        fit = record(raw, "fold fit_at")
        require(fit["fold"] == ("F1", "F2")[ix] and fit["fit_at"] == FITS[ix])
    coverage = record(overview["coverage"], " ".join(COVERAGE))
    for field, expected in COVERAGE.items():
        integer(coverage[field], expected, expected)
    require(fraction(overview["fee_rate"], unit="RATIO") == (3, 5000))
    require(fraction(overview["slippage_rate"], unit="RATIO") == (1, 2500))
    require(fraction(overview["initial_cash"], unit="SYNTHETIC_NTD") == (1000, 1))
    return overview


def _comparison(values: object, ticks: list[Record]) -> None:
    for ix, raw in enumerate(array(values, len(POLICIES))):
        book = record(
            raw,
            "policy valid_slots allocate_count cash_count abstain_count opportunities "
            "return_count net_return linked_gross_return max_drawdown weekly_sample_volatility "
            "fees slippage",
        )
        require(book["policy"] == POLICIES[ix])
        for count in ("valid_slots", "opportunities", "return_count"):
            integer(book[count], 48, 48)
        for state, count in (
            ("ALLOCATE", "allocate_count"),
            ("CASH", "cash_count"),
            ("ABSTAIN", "abstain_count"),
        ):
            require(
                integer(book[count], 0, 48)
                == sum(tick["policies"][ix]["disposition"] == state for tick in ticks)
            )
        for name in ("net_return", "linked_gross_return", "max_drawdown"):
            fraction(book[name], unit="RATIO")
        for name in ("fees", "slippage"):
            require(fraction(book[name], unit="SYNTHETIC_NTD")[0] >= 0)
        volatility = record(book["weekly_sample_volatility"], "kind unit text")
        require(volatility["kind"] == "NATIVE_DECIMAL_12" and volatility["unit"] == "RATIO")
        decimal12(volatility["text"])


def _evidence(value: object, observed_at: datetime) -> None:
    ev = record(
        value,
        "acceptance_ref historical_wu original_revision archive_validation validated_at "
        "historical_execution historical_pair_replay historical_class current_native_replay "
        "native_replay_reason current_research source_scope app_admission non_if03 limitations "
        + DIGEST_FIELDS,
    )
    text(ev["acceptance_ref"], SHELL_SAFE_REF)
    text(ev["original_revision"], r"[a-f0-9]{40}")
    require(timestamp(ev["validated_at"], utc=True) <= observed_at)
    for field in DIGEST_FIELDS.split():
        text(ev[field], HEX64)
    require(
        ev["historical_wu"] == HISTORICAL_WU
        and ev["historical_class"] == COMPLETE
        and ev["archive_validation"] == "PASSED"
        and ev["historical_execution"] == "SUCCEEDED"
        and ev["historical_pair_replay"] == "VERIFIED"
        and ev["source_scope"] == "AUTHORED_MODE_S"
        and ev["app_admission"] == "NONE"
        and ev["non_if03"] is True
        and ev["current_native_replay"] == ev["current_research"] == "NOT_RUN"
        and ev["native_replay_reason"] == "ORIGINAL_PROVENANCE_DIFFERS"
        and ev["limitations"] == list(LIMITATIONS)
    )


def refusal_status(reason: str) -> str:
    if reason == "EDITION_WITHHELD":
        return "WITHHELD"
    if reason in UNAVAILABLE:
        return "UNAVAILABLE"
    require(reason in FAILED)
    return "FAILED"


def validate(value: object) -> Record:
    """Validate wire shape independently of the archive authority decision."""
    require(type(value) is dict)
    view = cast(Record, value)
    status = choice(
        view.get("status"), ("AVAILABLE_HISTORICAL", "WITHHELD", "UNAVAILABLE", "FAILED")
    )
    if status == "AVAILABLE_HISTORICAL":
        record(view, COMMON + " edition_id release_id overview comparison ticks evidence")
        require(view["edition_id"] == EDITION)
        text(view["release_id"], HEX64)
        overview = _overview(view["overview"])
        ticks = [
            _tick(tick, ix) for ix, tick in enumerate(array(view["ticks"], 48), start=FIRST_TICK)
        ]
        require([tick["cutoff"] for tick in ticks] == sorted({tick["cutoff"] for tick in ticks}))
        require(ticks[0]["cutoff"] == overview["first_cutoff"])
        require(ticks[-1]["cutoff"] == overview["last_cutoff"])
        _comparison(view["comparison"], ticks)
        _evidence(view["evidence"], timestamp(view["observed_at"], utc=True))
    else:
        record(view, COMMON + " reason archive_validation current_native_replay current_research")
        reason = choice(view["reason"], tuple(sorted(UNAVAILABLE | FAILED | {"EDITION_WITHHELD"})))
        require(refusal_status(reason) == status)
        choice(view["archive_validation"], ("NOT_RUN", "FAILED", "PASSED_NO_DISCLOSURE"))
        require(view["current_native_replay"] == view["current_research"] == "NOT_RUN")
    _wire_tree(view)
    timestamp(view["observed_at"], utc=True)
    text(view["build_sha256"], HEX64)
    uuid4_text(view["attempt_id"])
    body = {key: val for key, val in view.items() if key != "snapshot_id"}
    require(view["schema"] == SCHEMA and view["snapshot_id"] == identify(SNAPSHOT_DOMAIN, body))
    require(len(canonical(view)) <= MAX_VIEW, "BOUNDS_EXCEEDED")
    return view


def snapshot(fields: Record, build: str, attempt: str, observed_at: str) -> Record:
    view = fields | {
        "schema": SCHEMA,
        "build_sha256": build,
        "attempt_id": attempt,
        "observed_at": observed_at,
    }
    _wire_tree(view)
    return validate(view | {"snapshot_id": identify(SNAPSHOT_DOMAIN, view)})
