"""Pure, bounded WU-01 source generation and Weekly request scheduling.

Full source payloads contain future facts and are NOT policy-safe observations.
Request serialization is a separate explicit surface, not a memory sandbox.
No Native evaluator, admitted snapshot, label calculation or fill is provided.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .synthetic_contracts import (
    ENCODING,
    MODE,
    OFFSET,
    SCHEMA,
    ZONE,
    decode_input_bytes,
    input_bytes,
    integer,
    keys,
    local_date,
    mapping,
    parse_instant,
    payload_pin,
    records,
    require,
    serialize_tick_request,
    text,
    validate_calendar,
    validate_price_record,
    validate_source_spec,
)


@dataclass(frozen=True)
class SyntheticInputPack:
    """Supplied source bytes/pin only; neither authentication nor PIT admission."""

    payload_bytes: bytes
    payload_sha256: str

    def source_payload(self) -> dict[str, Any]:
        """New detached source copy, including future facts; NOT a policy API."""
        return mapping(decode_input_bytes(self.payload_bytes))


@dataclass(frozen=True)
class WeekAnnotation:
    iso_week: str
    annotation: str = "NO_SESSION_WEEK"


@dataclass(frozen=True)
class WeeklyRequests:
    """Immutable request bytes, not qualified per-cutoff snapshots or a sidecar."""

    requests: tuple[bytes, ...]
    annotations: tuple[WeekAnnotation, ...]


def _instant_at(raw: dict[str, Any], seconds: int, origin: str) -> dict[str, str]:
    local = parse_instant(raw).astimezone(ZoneInfo(ZONE)) + timedelta(seconds=seconds)
    return {
        "source_text": local.isoformat(timespec="seconds"),
        "timezone_name": ZONE,
        "offset": OFFSET,
        "precision": "SECOND",
        "origin_ref": origin,
    }


def _price_ref(issuer: str, session: str, kind: str) -> str:
    return issuer + ":" + session + ":" + kind


def _generate_prices(
    spec: dict[str, Any], sessions: tuple[dict[str, Any], ...]
) -> list[dict[str, Any]]:
    template = mapping(spec["price_template"])
    keys(
        template,
        {
            "unit",
            "currency",
            "scale",
            "source_ref",
            "version_ref",
            "defaults",
            "overrides",
            "available_delay_seconds",
        },
    )
    delay = integer(template["available_delay_seconds"])
    require(0 <= delay <= 86400, "INVALID_AVAILABILITY_DELAY")
    text(template["source_ref"])
    text(template["version_ref"])
    issuers = [r["issuer_ref"] for r in spec["roster"]]
    defaults: dict[str, dict[str, Any]] = {}
    for raw in records(template["defaults"]):
        row = mapping(raw)
        keys(row, {"issuer_ref", "OPEN", "CLOSE"})
        issuer = text(row["issuer_ref"])
        require(issuer not in defaults, "DUPLICATE_PRICE_DEFAULT")
        defaults[issuer] = row
    require(set(defaults) == set(issuers), "PRICE_GRID_COVERAGE_GAP")
    session_ids = {s["session_id"] for s in sessions}
    overrides: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in records(template["overrides"]):
        row = mapping(raw)
        state = text(row.get("state"))
        fields = {"coefficient"} if state == "KNOWN" else {"reason"}
        if state == "UNKNOWN":
            fields.add("unknown_cause")
        keys(row, {"issuer_ref", "session_ref", "kind", "state", "origin_ref"} | fields)
        key = tuple(text(row[k]) for k in ("issuer_ref", "session_ref", "kind"))
        require(
            key[0] in issuers and key[1] in session_ids and key[2] in {"OPEN", "CLOSE"},
            "PRICE_GRID_REF_MISMATCH",
        )
        require(key not in overrides, "DUPLICATE_PRICE_OVERRIDE")
        overrides[key] = row
    prices = []
    for session in sessions:
        for issuer in issuers:  # Complete roster, including explicit zero/unknown membership.
            for kind in ("OPEN", "CLOSE"):
                event = session["open" if kind == "OPEN" else "close"]
                ref = _price_ref(issuer, session["session_id"], kind)
                row = {
                    "price_ref": ref,
                    "issuer_ref": issuer,
                    "session_ref": session["session_id"],
                    "kind": kind,
                    "state": "KNOWN",
                    "coefficient": defaults[issuer][kind],
                    "unit": template["unit"],
                    "currency": template["currency"],
                    "scale": template["scale"],
                    "event_time": event,
                    "available_at": _instant_at(event, delay, "SYN-AVAIL-" + ref),
                    "source_ref": template["source_ref"],
                    "version_ref": template["version_ref"],
                    "origin_ref": "SYN-PRICE-" + ref,
                }
                override = overrides.get((issuer, session["session_id"], kind))
                if override is not None:
                    del row["coefficient"]
                    for key in ("state", "coefficient", "reason", "unknown_cause", "origin_ref"):
                        if key in override:
                            row[key] = override[key]
                validate_price_record(row)
                prices.append(row)
    return prices


def validate_price_grid(
    prices: object,
    sessions: tuple[dict[str, Any], ...],
    issuers: list[str],
) -> dict[str, dict[str, Any]]:
    expected = {
        _price_ref(i, s["session_id"], k)
        for s in sessions
        for i in issuers
        for k in ("OPEN", "CLOSE")
    }
    by_session = {s["session_id"]: s for s in sessions}
    found: dict[str, dict[str, Any]] = {}
    for raw in records(prices):
        row = mapping(raw)
        validate_price_record(row)
        ref = row["price_ref"]
        require(
            row["issuer_ref"] in issuers and row["session_ref"] in by_session,
            "PRICE_GRID_REF_MISMATCH",
        )
        require(
            ref == _price_ref(row["issuer_ref"], row["session_ref"], row["kind"]),
            "PRICE_GRID_REF_MISMATCH",
        )
        require(ref not in found, "DUPLICATE_PRICE_RECORD")
        session = by_session[row["session_ref"]]
        require(
            parse_instant(row["event_time"])
            == parse_instant(session["open" if row["kind"] == "OPEN" else "close"]),
            "PRICE_EVENT_SESSION_MISMATCH",
        )
        found[ref] = row
    require(set(found) == expected, "PRICE_GRID_COVERAGE_GAP")
    return found


def _validate_endpoints(spec: dict[str, Any], prices: dict[str, dict[str, Any]]) -> None:
    seen: set[str] = set()
    first, last = (local_date(spec["coverage"][k]) for k in ("start", "end"))
    for raw in records(spec["endpoint_facts"]):
        row = mapping(raw)
        keys(
            row,
            {
                "endpoint_ref",
                "price_ref",
                "source_date",
                "state",
                "available_at",
                "maturity_at",
                "origin_ref",
            },
        )
        ref = text(row["endpoint_ref"])
        require(ref not in seen, "DUPLICATE_ENDPOINT_REF")
        seen.add(ref)
        day = local_date(row["source_date"])
        require(first <= day <= last, "ENDPOINT_OUT_OF_COVERAGE")
        price_ref = text(row["price_ref"])
        require(price_ref in prices, "ENDPOINT_SOURCE_MISSING")
        price = prices[price_ref]
        require(
            day == datetime.fromisoformat(price["event_time"]["source_text"]).date(),
            "ENDPOINT_SOURCE_DATE_MISMATCH",
        )
        require(row["state"] == price["state"], "ENDPOINT_SOURCE_STATE_MISMATCH")
        text(row["origin_ref"])
        if row["state"] == "KNOWN":
            available = parse_instant(row["available_at"])
            require(
                available == parse_instant(price["available_at"]), "ENDPOINT_AVAILABILITY_MISMATCH"
            )
            require(
                parse_instant(row["maturity_at"]) >= available, "ENDPOINT_MATURITY_CONTRADICTION"
            )
        else:
            require(
                row["available_at"] is None and row["maturity_at"] is None,
                "UNRESOLVED_ENDPOINT_TIME_REQUIRED",
            )


def build_pack(input_spec: object, seed: int = 17) -> SyntheticInputPack:
    """Detached deterministic source/input bytes; expected oracle data is not read.

    Seed is pinned metadata, not a stochastic market model. The reviewed grid
    deliberately stays fixed. Its changed seed changes input identity only.
    """
    require(0 <= integer(seed) < 2**63, "INVALID_SEED")
    spec = mapping(decode_input_bytes(input_bytes(input_spec)))
    validate_source_spec(spec)
    sessions = validate_calendar(spec)
    prices = _generate_prices(spec, sessions)
    grid = validate_price_grid(prices, sessions, [r["issuer_ref"] for r in spec["roster"]])
    _validate_endpoints(spec, grid)
    body = input_bytes(
        {
            "schema_version": SCHEMA,
            "encoding": ENCODING,
            "seed": seed,
            "input_spec": spec,
            "prices": prices,
        }
    )
    return SyntheticInputPack(body, payload_pin(body))


def verify_input_pack(pack: SyntheticInputPack) -> None:
    """Check local bytes/declared pins and structure, never authenticate source."""
    require(type(pack) is SyntheticInputPack, "INPUT_PACK_REQUIRED")
    require(
        type(pack.payload_bytes) is bytes
        and type(pack.payload_sha256) is str
        and payload_pin(pack.payload_bytes) == pack.payload_sha256,
        "PAYLOAD_PIN_MISMATCH",
    )
    payload = pack.source_payload()
    keys(payload, {"schema_version", "encoding", "seed", "input_spec", "prices"})
    require(
        payload["schema_version"] == SCHEMA and payload["encoding"] == ENCODING,
        "UNSUPPORTED_SCHEMA",
    )
    spec = validate_source_spec(payload["input_spec"])
    sessions = validate_calendar(spec)
    grid = validate_price_grid(
        payload["prices"], sessions, [r["issuer_ref"] for r in spec["roster"]]
    )
    _validate_endpoints(spec, grid)
    expected = build_pack(spec, payload["seed"])
    require(payload["prices"] == expected.source_payload()["prices"], "GENERATED_PRICE_MISMATCH")
    require(pack.payload_bytes == expected.payload_bytes, "INPUT_ENCODING_MISMATCH")


def build_weekly_requests(pack: SyntheticInputPack) -> WeeklyRequests:
    """Use actual pinned rows, not weekdays; no qualified snapshot is produced."""
    verify_input_pack(pack)
    spec = pack.source_payload()["input_spec"]
    start, end = (local_date(spec["decision_window"][k]) for k in ("start", "end"))
    sessions = validate_calendar(spec)
    requests: list[bytes] = []
    annotations = []
    monday = start
    while monday <= end:
        sunday = monday + timedelta(days=6)
        candidates = [s for s in sessions if monday <= local_date(s["date"]) <= sunday]
        year, week, _ = monday.isocalendar()
        if not candidates:
            annotations.append(WeekAnnotation(f"{year}-W{week:02}"))
        else:
            last = max(candidates, key=lambda s: s["date"])
            tick = "SYN-TICK-" + last["date"]
            cutoff = {
                "source_text": last["date"] + "T18:00:00+08:00",
                "timezone_name": ZONE,
                "offset": OFFSET,
                "precision": "SECOND",
                "origin_ref": tick,
            }
            require(
                parse_instant(last["close"]) < parse_instant(cutoff),
                "SESSION_CLOSE_NOT_BEFORE_CUTOFF",
                f"{last['session_id']}:{year}-W{week:02}",
            )
            requests.append(
                serialize_tick_request(
                    {
                        "schema_version": SCHEMA,
                        "tick_id": tick,
                        "tick_order": len(requests),
                        "cutoff": cutoff,
                        "calendar_ref": spec["calendar_ref"],
                        "manifest_ref": spec["manifest_ref"] + ":" + pack.payload_sha256,
                        "config_ref": spec["config_ref"],
                        "context_ref": "SYN-CONTEXT-" + pack.payload_sha256 + ":" + last["date"],
                        "issuer_refs": [r["issuer_ref"] for r in spec["roster"]],
                        "requested_feature_refs": spec["requested_feature_refs"],
                        "data_mode": MODE,
                        "decision_frequency": "WEEKLY",
                    }
                )
            )
        monday += timedelta(days=7)
    return WeeklyRequests(tuple(requests), tuple(annotations))
