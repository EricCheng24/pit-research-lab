"""WU05 synthetic draft contracts. No codec, issued reference, resolver or grant.

SC CAN-01..10 defines the reference/helper shapes; body labels below are local
draft schemas, not registered resource versions. Passing validation proves only
structure. In particular, supplied six-field cores are never authenticated here.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, cast

from pit_research_lab.domain.contracts import ContractError, int64
from pit_research_lab.domain.ratio import NUMERICAL_POLICY, FixedRatio

ROLES = tuple(
    (
        "CALENDAR TEMPORAL_CONFIGURATION DECISION_SCHEDULE MANIFEST SOURCE_VERSION_HISTORY "
        "SOURCE_VERSION COVERAGE SEMANTIC_TRACE NATIVE_RECEIPT SEMANTIC_EVIDENCE "
        "OBSERVATION_RELEASE_POLICY OBSERVATION_RELEASE_RECEIPT AUDIT_ACCESS_POLICY "
        "READER_CAPABILITY_POLICY ASSOCIATION_PROTOCOL EXPERIMENT_ASSOCIATION AUTHOR_RECORD "
        "OWNER_DECISION METHOD HYPOTHESIS PROTOCOL HORIZON_MATURITY EVALUATION_PLAN POLICY "
        "EXECUTION_RULES EVALUATION_PROTOCOL POLICY_EVALUATION_PROTOCOL OUTCOME PRICE NUMERIC_POLICY "
        "TIMEZONE_RULES PROJECTION_POLICY SOURCE_TEXT ORIGIN RESULT_METRIC LIMITATION ACTION "
        "SCHEDULE_INVARIANT_POLICY SOURCE_CADENCE STATE"
    ).split()
)
REQUIRED = frozenset(
    "CALENDAR TEMPORAL_CONFIGURATION DECISION_SCHEDULE MANIFEST SOURCE_VERSION_HISTORY "
    "SOURCE_VERSION COVERAGE SEMANTIC_TRACE NATIVE_RECEIPT OBSERVATION_RELEASE_POLICY "
    "AUDIT_ACCESS_POLICY PROTOCOL HORIZON_MATURITY EXECUTION_RULES EVALUATION_PROTOCOL "
    "NUMERIC_POLICY TIMEZONE_RULES PROJECTION_POLICY ORIGIN SCHEDULE_INVARIANT_POLICY "
    "SOURCE_CADENCE".split()
)
CONDITIONAL = frozenset("SEMANTIC_EVIDENCE SOURCE_TEXT OBSERVATION_RELEASE_RECEIPT".split())
INTERFACE = frozenset(("AUTHOR_RECORD", "OWNER_DECISION"))
DOMAINS = {
    "SOURCE-BYTES": "source-bytes-candidate-v0.1",
    "F2-QUALIFICATION": "f2-qualification-candidate-v0.1",
    "F2-OBSERVATION": "f2-observation-candidate-v0.1",
    "TEMPORAL-SEQUENCE": "temporal-sequence-candidate-v0.1",
}
PROFILE = "typed-json-candidate-v0.1"
FLAGS = {
    "diagnostic_only": True,
    "admission_eligible": False,
    "trust": "NOT_TRUSTED_PIT_EVIDENCE",
    "source_authentication": "NOT_ESTABLISHED",
    "disposition": "INTEGRATED_PROVISIONAL",
}
UNKNOWN_CAUSES = {"ABSENT_SOURCE_FIELD", "EXPLICIT_SOURCE_UNKNOWN", "AMBIGUOUS_SOURCE", "UNMAPPED"}


class State(StrEnum):
    INVALID = "INVALID"
    NOT_SUPPLIED = "NOT_SUPPLIED"
    NOT_EVALUATED = "NOT_EVALUATED"
    DENIED = "DENIED"
    WITHHELD = "WITHHELD"
    STRUCTURE_VALID = "STRUCTURE_VALID_NON_ISSUED"


class ResourceError(ContractError):
    """Finite local error; never a Native failure or eligibility predicate."""

    def __init__(self, code: str, state: State = State.INVALID) -> None:
        self.code = code
        self.state = state
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ResourceError(code)


@dataclass(frozen=True, slots=True)
class Check:
    state: State
    reasons: tuple[str, ...]
    # A structural success is explicitly not an issuance or admission result.
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)


def closed(value: object, fields: str) -> dict[str, Any]:
    require(type(value) is dict, "OBJECT_REQUIRED")
    data = cast(dict[str, Any], value)
    require(set(data) == set(fields.split()), "CLOSED_FIELDS")
    return data


def text(value: object, limit: int = 65536) -> str:
    require(type(value) is str, "TEXT_REQUIRED")
    result = cast(str, value)
    try:
        require(0 < len(result.encode("utf-8")) <= limit, "TEXT_BOUND")
    except UnicodeError as exc:
        raise ResourceError("INVALID_UNICODE") from exc
    return result


def literal(*allowed: object) -> Callable[[object], None]:
    def validate(value: object) -> None:
        require(any(type(value) is type(a) and value == a for a in allowed), "LITERAL")

    return validate


def array(value: object, minimum: int = 1, maximum: int = 4096) -> list[Any]:
    require(type(value) is list, "ARRAY_REQUIRED")
    result = cast(list[Any], value)
    require(minimum <= len(result) <= maximum, "ARRAY_BOUND")
    return result


def items(validator: Callable[[object], object], minimum: int = 1) -> Callable[[object], None]:
    def validate(value: object) -> None:
        for item in array(value, minimum):
            validator(item)

    return validate


def tagged_integer(value: object, signed: bool = False) -> int:
    d = closed(value, "type value")
    literal("int64" if signed else "uint64")(d["type"])
    spelling = text(d["value"], 21)
    require(
        re.fullmatch(r"0|-?[1-9][0-9]*" if signed else r"0|[1-9][0-9]*", spelling) is not None,
        "INTEGER_SPELLING",
    )
    number = int(spelling)
    require(-(2**63) <= number < 2**63 if signed else 0 <= number < 2**64, "INTEGER_RANGE")
    return number


def hex64(value: object) -> str:
    result = text(value, 64)
    require(re.fullmatch("[0-9a-f]{64}", result) is not None, "HEX64")
    return result


@dataclass(frozen=True, slots=True)
class ParentCore:
    domain: str
    schema: str
    profile: str
    algorithm: str
    payload_length: int
    digest: str


def parent(value: object, domain: str = "SOURCE-BYTES") -> ParentCore:
    d = closed(
        value,
        "domain_tag object_schema_version canonical_profile_version "
        "digest_algorithm canonical_payload_byte_length digest_hex",
    )
    require(domain in DOMAINS, "UNSUPPORTED_DOMAIN")
    literal("PITLAB/ACADEMIC/" + domain + "/candidate-v0.1")(d["domain_tag"])
    literal(DOMAINS[domain])(d["object_schema_version"])
    literal(PROFILE)(d["canonical_profile_version"])
    literal("SHA-256")(d["digest_algorithm"])
    length = tagged_integer(d["canonical_payload_byte_length"])
    require(1 <= length <= 16777216, "PAYLOAD_LENGTH")
    return ParentCore(domain, DOMAINS[domain], PROFILE, "SHA-256", length, hex64(d["digest_hex"]))


@dataclass(frozen=True, slots=True)
class ResourceKey:
    kind: str
    version: str
    schema: str
    content: ParentCore


def resource(value: object, *kinds: str) -> ResourceKey:
    d = closed(value, "resource_kind resource_version resource_schema content_ref")
    kind = text(d["resource_kind"], 128)
    require(kind in ROLES and (not kinds or kind in kinds), "RESOURCE_KIND")
    return ResourceKey(
        kind,
        text(d["resource_version"], 128),
        text(d["resource_schema"], 128),
        parent(d["content_ref"]),
    )


def ref(*kinds: str) -> Callable[[object], ResourceKey]:
    return lambda value: resource(value, *kinds)


def safe_reason(value: object) -> None:
    d = closed(value, "owner code")
    text(d["owner"], 128)
    text(d["code"], 128)


def code_pin(value: object) -> None:
    d = closed(value, "role path byte_length sha256 semantic_version")
    text(d["role"], 128)
    path = text(d["path"])
    require(
        not path.startswith("/")
        and "\\" not in path
        and all(p not in ("", ".", "..") for p in path.split("/")),
        "CODE_PATH",
    )
    tagged_integer(d["byte_length"])
    hex64(d["sha256"])
    text(d["semantic_version"], 128)


def flags(value: object) -> None:
    d = closed(value, " ".join(FLAGS))
    for key, expected in FLAGS.items():
        literal(expected)(d[key])


def scope(value: object) -> None:
    d = closed(value, "data_mode pit_status evidence_class scope_flags")
    for key, val in (
        ("data_mode", "SYNTHETIC_GOLDEN"),
        ("pit_status", "UNRESOLVED"),
        ("evidence_class", "UNVERIFIED"),
    ):
        literal(val)(d[key])
    flags(d["scope_flags"])


def absent(value: object, tag: str = "not_applicable") -> None:
    d = closed(value, "type owner reason")
    literal(tag)(d["type"])
    text(d["owner"])
    text(d["reason"])


def unknown(value: object) -> None:
    d = closed(value, "type cause origin_ref source_text_ref")
    literal("unknown")(d["type"])
    literal(*sorted(UNKNOWN_CAUSES))(d["cause"])
    resource(d["origin_ref"], "ORIGIN")
    if type(d["source_text_ref"]) is dict and d["source_text_ref"].get("type") == "not_applicable":
        absent(d["source_text_ref"])
    else:
        resource(d["source_text_ref"], "SOURCE_TEXT")


def fact(value: object, known: Callable[[object], object]) -> None:
    require(type(value) is dict, "FACT_REQUIRED")
    d = cast(dict[str, Any], value)
    if d.get("type") == "known":
        closed(d, "type value origin_ref")
        known(d["value"])
        resource(d["origin_ref"], "ORIGIN")
    elif d.get("type") == "unknown":
        unknown(d)
    elif d.get("type") == "not_evaluated":
        absent(d, "not_evaluated")
    elif d.get("type") == "withheld":
        closed(d, "type owner reason policy_ref")
        text(d["owner"])
        text(d["reason"])
        resource(d["policy_ref"], "OBSERVATION_RELEASE_POLICY")
    else:
        raise ResourceError("FACT_TAG")


def declared_taipei(value: object) -> datetime:
    """Explicit +08 declaration arithmetic; no named-zone/rule attestation."""
    raw = text(value, 25)
    require(
        re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+08:00", raw)
        is not None,
        "TIME_REPRESENTATION",
    )
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ResourceError("INVALID_TIME") from exc


def time_record(value: object) -> datetime:
    """Check declared offset arithmetic only. This does NOT validate named-zone rules."""
    d = closed(
        value,
        "source_text timezone_name offset precision origin_ref utc_comparison timezone_rules_ref",
    )
    literal("Asia/Taipei")(d["timezone_name"])
    literal("+08:00")(d["offset"])
    literal("SECOND")(d["precision"])
    instant = declared_taipei(d["source_text"])
    require(
        d["utc_comparison"] == instant.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "UTC_CONTRADICTION",
    )
    resource(d["origin_ref"], "ORIGIN")
    resource(d["timezone_rules_ref"], "TIMEZONE_RULES")
    return instant


def tick(value: object) -> None:
    d = closed(value, "tick_id tick_order decision_cutoff context_ref")
    text(d["tick_id"], 128)
    tagged_integer(d["tick_order"])
    time_record(d["decision_cutoff"])
    text(d["context_ref"], 128)


def source_version_ref(value: object) -> None:
    d = closed(value, "body_ref version_ref representation_ref revision_history_ref")
    parent(d["body_ref"])
    resource(d["version_ref"], "SOURCE_VERSION")
    text(d["representation_ref"])
    resource(d["revision_history_ref"], "SOURCE_VERSION_HISTORY")


def revenue(value: object, unit: object) -> int:
    literal("NTD_thousands")(unit)
    result = tagged_integer(value, signed=True)
    int64(result)
    return result


def fixed_ratio(value: object) -> FixedRatio:
    d = closed(value, "type scaled_units decimal_text scale unit numeric_policy_ref")
    literal("fixed_ratio6")(d["type"])
    resource(d["numeric_policy_ref"], "NUMERIC_POLICY")
    literal("FRACTION")(d["unit"])
    require(tagged_integer(d["scale"]) == 6, "RATIO_SCALE")
    try:
        return FixedRatio(
            tagged_integer(d["scaled_units"]),
            text(d["decimal_text"]),
            numerical_policy=NUMERICAL_POLICY,
        )
    except ContractError as exc:
        raise ResourceError("INVALID_FIXED_RATIO") from exc


def strict_json(raw: bytes) -> dict[str, Any]:
    """Bounded draft transport reader; not a canonical encoder/depth conformance claim."""
    require(type(raw) is bytes and 0 < len(raw) <= 16777216, "BODY_BOUND")

    def pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in entries:
            require(key not in result, "DUPLICATE_KEY")
            result[key] = value
        return result

    def bad_constant(_: str) -> None:
        raise ResourceError("NONFINITE_NUMBER")

    try:
        result = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad_constant
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ResourceError):
            raise
        raise ResourceError("INVALID_JSON") from exc
    require(type(result) is dict, "OBJECT_REQUIRED")
    return cast(dict[str, Any], result)


def closure_class(role: str) -> str:
    require(role in ROLES, "RESOURCE_KIND")
    if role in REQUIRED:
        return "REQUIRED_FOR_SLICE"
    if role in CONDITIONAL:
        return "CONDITIONAL"
    if role in INTERFACE:
        return "INTERFACE_ONLY"
    return "NOT_APPLICABLE_IN_SLICE" if role == "LIMITATION" else "DEFERRED_WITH_GATE"
