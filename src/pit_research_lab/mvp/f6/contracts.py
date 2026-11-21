"""Closed, immutable representations of UNAUTHENTICATED F6 wire claims.

Validation proves shape and local consistency only. In particular, decoding a
PASSED/AVAILABLE claim grants no verification or release capability. P1-03 must
establish those facts independently before serving any result. No I/O occurs here.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from math import gcd
from typing import ClassVar, NoReturn, Self, cast
from uuid import UUID

VERSION = "F6_FIXED_SYNTHETIC_F3_L1_RESEARCH_V0.1"
CAPABILITY_ID = "fixed-synthetic-f3-l1-v0.1"
CAPABILITY_DOMAIN = b"F6_FIXED_RESEARCH_CAPABILITY_V0.1\x00"
SUBMISSION_DOMAIN = b"F6_FIXED_RESEARCH_SUBMISSION_V0.1\x00"
NATIVE_VERSION = "F3_L1_RESEARCH_V0.1"
NUMERIC_POLICY = "FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1"
QUESTION = "Does PIT monthly revenue growth predict subsequent synthetic returns?"
METHOD = "OLS_INTERCEPT_ONE_REGRESSOR_V1"
INTERPRETATION = "EXECUTION_COMPLETE_NO_CLAIM_OF_PREDICTIVE_EDGE"
UNITS = "dimensionless_simple_return; MSE/SSE are squared-return units"
DIAGNOSTIC = "DESCRIPTIVE_MOMENTS_NOT_DEPENDENCE_ROBUST_INFERENCE"
SOURCE_SHA256 = "8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d"
MANIFEST_SHA256 = "7b0cb1bec7b4d42ea55670eeb9d8ee4b744e7c39368cadd7e0eb1298deeb3219"
# Current fixed input is itself the native sorted compact JSON preimage. Equal
# digest text does NOT equate the raw-source and native dataset reference domains.
DATASET_SHA256 = SOURCE_SHA256
NATIVE_LIMITATIONS = (
    "AUTHORED_SYNTHETIC_INFRASTRUCTURE_ONLY",
    "NOT_REAL_TWSE_OR_HISTORICAL_PIT_CERTIFICATION",
    "NO_IF03_ISSUANCE_OR_IF05_ADMISSION",
    "NO_IID_PVALUES_CI_OR_H0_REJECTION",
    "REPEATED_MONTHLY_SIGNALS_AND_DEPENDENT_ENTITIES",
    "OVERLAPPING_20_SESSION_OUTCOMES",
    "DESCRIPTIVE_ASSOCIATION_AND_OOS_ASSESSMENT_ONLY",
    "NO_CAUSAL_OR_PROFITABILITY_CLAIM",
)
APP_LIMITATIONS = (
    "NO_APP_PIT_ELIGIBILITY_PREDICATE",
    "EVIDENCE_CLASS_PROMOTION_NOT_AUTHORIZED",
    "NATIVE_INTEGRITY_NOT_IF03_CANONICAL_EQUIVALENCE",
    "LOCAL_TRUSTED_CODE_NOT_HOSTILE_CODE_SANDBOX",
)
FIXTURE_LIMITATION = "DISPLAY_SCENARIO_NOT_EXECUTED_RESEARCH"
ISSUERS = tuple(f"SYN-L1-{i}" for i in range(1, 6))
STAGES = (
    "SPEC_PINNED",
    "F2_INPUTS_QUALIFIED",
    "F1_TRAINING_SELECTED",
    "F1_FITTED",
    "F1_PREDICTIONS_SEALED",
    "F2_TRAINING_SELECTED",
    "F2_FITTED",
    "F2_PREDICTIONS_SEALED",
    "F1_SCORED",
    "F2_SCORED",
    "EVIDENCE_WRITTEN",
)
ARTIFACTS = tuple(
    sorted(
        f"{n}.json"
        for n in (
            "spec",
            "bindings",
            "folds",
            "states",
            "predictions",
            "targets",
            "result",
            "handoff",
            "evidence",
            "attempt",
        )
    )
)
DETERMINISTIC_ARTIFACTS = tuple(n for n in ARTIFACTS if n != "attempt.json")
METRIC_NAMES = (
    "absolute_error_sum",
    "sse",
    "signed_error_sum",
    "baseline_sse",
    "mae",
    "mse",
    "mean_prediction_error",
    "residual_variance_population",
    "minimum_residual",
    "maximum_residual",
)
ADJACENT_METRIC = "adjacent_within_issuer_residual_product_mean"
BASE_PATH = "/api/f6/fixed-research/v0.1/runs/"


class Reason(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    UNSUPPORTED_SELECTION = "UNSUPPORTED_SELECTION"
    CAPABILITY_CHANGED = "CAPABILITY_CHANGED"
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    JOB_BUSY = "JOB_BUSY"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
    STORAGE_BLOCKED = "STORAGE_BLOCKED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    RESULT_NOT_RELEASED = "RESULT_NOT_RELEASED"
    NATIVE_CONTRACT_INVALID = "NATIVE_CONTRACT_INVALID"
    ARTIFACT_INTEGRITY_FAILED = "ARTIFACT_INTEGRITY_FAILED"
    REPLAY_BASIS_CHANGED = "REPLAY_BASIS_CHANGED"
    NOT_A_REPLAY = "NOT_A_REPLAY"
    NOT_STARTED = "NOT_STARTED"
    NO_FAILURE = "NO_FAILURE"
    NOT_YET_AVAILABLE = "NOT_YET_AVAILABLE"
    NO_ADJACENT_PAIRS = "NO_ADJACENT_PAIRS"
    ZERO_BASELINE_SSE = "ZERO_BASELINE_SSE"
    NATIVE_WITHHELD = "NATIVE_WITHHELD"
    NATIVE_UNKNOWN_STATE = "NATIVE_UNKNOWN_STATE"
    SOURCE_REFERENCE_MISSING = "SOURCE_REFERENCE_MISSING"
    LAUNCH_INTERRUPTED = "LAUNCH_INTERRUPTED"
    CHILD_NONZERO_EXIT = "CHILD_NONZERO_EXIT"
    CHILD_TIMEOUT = "CHILD_TIMEOUT"
    SUPERVISOR_LOST = "SUPERVISOR_LOST"
    EXECUTION_OUTCOME_UNKNOWN = "EXECUTION_OUTCOME_UNKNOWN"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    HOST_REJECTED = "HOST_REJECTED"
    ORIGIN_REJECTED = "ORIGIN_REJECTED"
    CSRF_REJECTED = "CSRF_REJECTED"
    BODY_TOO_LARGE = "BODY_TOO_LARGE"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MISSING_PREDECESSOR = "MISSING_PREDECESSOR"


class Kind(StrEnum):
    CAPABILITY = "CAPABILITY"
    SUBMISSION_REQUEST = "SUBMISSION_REQUEST"
    RUN_RECEIPT = "RUN_RECEIPT"
    RUN_STATUS = "RUN_STATUS"
    VERIFIED_RESULT = "VERIFIED_RESULT"
    EVIDENCE_PROVENANCE = "EVIDENCE_PROVENANCE"
    BASIC_REPLAY_RESULT = "BASIC_REPLAY_RESULT"
    ERROR = "ERROR"


class ReferenceKind(StrEnum):
    EXPERIMENT = "F3_EXPERIMENT_SPEC_BYTES"
    PROTOCOL = "F3_PROTOCOL_PAYLOAD"
    RESULT = "F3_RESULT_BYTES"
    EVIDENCE = "F3_EVIDENCE_BYTES"
    DATASET = "F2_PANEL_RESEARCH_BYTES"
    BINDING = "F3_BINDING_PAYLOAD"
    STATE = "F3_STATE_PAYLOAD"
    PREDICTION = "F3_PREDICTION_PAYLOAD"
    TRAINING = "F3_TRAINING_PAYLOAD"
    SOURCE = "RAW_SOURCE_BYTES"
    MANIFEST = "MANIFEST_BYTES"


class Execution(StrEnum):
    NOT_RUN = "NOT_RUN"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class Pit(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    WITHHELD = "WITHHELD"


class Provenance(StrEnum):
    NOT_EXECUTED = "NOT_EXECUTED"
    ACTUAL_F3_CLI = "ACTUAL_F3_CLI"
    FIXTURE_ONLY = "FIXTURE_ONLY"


class VerificationState(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED_NATIVE_DIRECTORY_AND_APP_LINKS"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"


class ReleaseState(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    BLOCKED = "BLOCKED"


class FactState(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    WITHHELD = "WITHHELD"
    ABSENT = "ABSENT"
    NOT_EVALUATED = "NOT_EVALUATED"
    REJECTED = "REJECTED"


class ContractError(ValueError):
    """Closed safe failure; never echoes supplied data."""

    def __init__(self, code: Reason = Reason.INVALID_REQUEST) -> None:
        self.code = code
        super().__init__(code.value)


type JSONValue = str | int | bool | None | list[JSONValue] | dict[str, JSONValue]
type WireObject = dict[str, JSONValue]
type Validator = Callable[[JSONValue], object]


def require(condition: bool, code: Reason = Reason.INVALID_REQUEST) -> None:
    if not condition:
        raise ContractError(code)


def _json(value: object) -> JSONValue:
    if value is None or type(value) in (str, int, bool):
        return cast(JSONValue, value)
    if type(value) is list:
        return [_json(v) for v in cast(list[object], value)]
    if type(value) is dict:
        result: WireObject = {}
        for key, item in cast(dict[object, object], value).items():
            require(type(key) is str)
            result[cast(str, key)] = _json(item)
        return result
    raise ContractError()


def canonical_json(value: object) -> bytes:
    """Local control JSON, NOT IF-03: sorted keys, compact UTF-8, no floats."""
    try:
        return json.dumps(
            _json(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError() from None


def _pairs(pairs: list[tuple[str, JSONValue]]) -> WireObject:
    result: WireObject = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _bad_number(_: str) -> NoReturn:
    raise ContractError()


def decode_json(raw: bytes) -> JSONValue:
    require(type(raw) is bytes)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_bad_number,
            parse_constant=_bad_number,
        )
        return _json(value)
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError() from None


def record(value: object, fields: str) -> WireObject:
    """Exact object shape; leaf validation is always explicit at call sites."""
    require(type(value) is dict)
    obj = cast(WireObject, value)
    require(all(type(k) is str for k in obj) and set(obj) == set(fields.split()))
    return obj


def text(value: object) -> str:
    require(type(value) is str)
    result = cast(str, value)
    require(bool(result))
    try:
        result.encode("utf-8")
    except UnicodeError:
        raise ContractError() from None
    return result


def _enum(value: object, choices: tuple[str, ...]) -> str:
    result = text(value)
    require(result in choices)
    return result


def _literal(value: object, expected: object) -> None:
    require(type(value) is type(expected) and value == expected)


def uint(value: object) -> int:
    require(type(value) is int)
    result = cast(int, value)
    require(0 <= result <= 2**53 - 1)
    return result


def uint_text(value: object) -> str:
    result = text(value)
    require(re.fullmatch(r"0|[1-9][0-9]*", result) is not None)
    return result


def sha256_text(value: object) -> str:
    result = text(value)
    require(re.fullmatch(r"[0-9a-f]{64}", result) is not None)
    return result


def uuid4_text(value: object) -> str:
    result = text(value)
    try:
        identifier = UUID(result)
    except ValueError:
        raise ContractError() from None
    require(identifier.version == 4 and str(identifier) == result)
    return result


def timestamp(value: object, *, native: bool = False) -> str:
    result = text(value)
    pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    pattern += r"\+08:00" if native else r"(?:\.[0-9]{1,6})?\+00:00"
    require(re.fullmatch(pattern, result) is not None)
    try:
        datetime.fromisoformat(result)
    except ValueError:
        raise ContractError() from None
    return result


def _date(value: object) -> str:
    result = text(value)
    try:
        require(date.fromisoformat(result).isoformat() == result)
    except ValueError:
        raise ContractError() from None
    return result


def native_time(value: JSONValue) -> str:
    return timestamp(value, native=True)


def _array(value: object, item: Validator, size: int | None = None) -> list[JSONValue]:
    require(type(value) is list)
    result = cast(list[JSONValue], value)
    require(size is None or len(result) == size)
    for member in result:
        item(member)
    return result


def _reason(value: object) -> str:
    return _enum(value, tuple(Reason))


def unavailable(reason: Reason) -> WireObject:
    require(type(reason) is Reason)
    return {"state": "UNAVAILABLE", "reason": reason.value}


def present(value: JSONValue) -> WireObject:
    return {"state": "PRESENT", "value": _json(value)}


def _slot(value: object, item: Validator) -> WireObject:
    require(type(value) is dict)
    obj = cast(WireObject, value)
    if obj.get("state") == "PRESENT":
        record(obj, "state value")
        item(obj["value"])
    else:
        record(obj, "state reason")
        _literal(obj["state"], "UNAVAILABLE")
        _reason(obj["reason"])
    return obj


def _is_present(value: JSONValue) -> bool:
    return type(value) is dict and value.get("state") == "PRESENT"


@dataclass(frozen=True, slots=True)
class ExactFraction:
    numerator: str
    denominator: str

    def __post_init__(self) -> None:
        n, d = text(self.numerator), text(self.denominator)
        require(len(n.lstrip("-")) <= 4096 and len(d) <= 4096)
        require(re.fullmatch(r"0|-?[1-9][0-9]*", n) is not None)
        require(re.fullmatch(r"[1-9][0-9]*", d) is not None)
        try:
            require(gcd(int(n), int(d)) == 1)
        except ValueError:
            raise ContractError() from None

    def to_wire(self) -> WireObject:
        return {"numerator": self.numerator, "denominator": self.denominator}

    @classmethod
    def from_wire(cls, value: object) -> Self:
        obj = record(value, "numerator denominator")
        return cls(text(obj["numerator"]), text(obj["denominator"]))


@dataclass(frozen=True, slots=True)
class NativeDigestRef:
    kind: ReferenceKind
    sha256: str

    def __post_init__(self) -> None:
        require(type(self.kind) is ReferenceKind)
        sha256_text(self.sha256)

    def to_wire(self) -> WireObject:
        return {"kind": self.kind.value, "sha256": self.sha256}

    @classmethod
    def from_wire(cls, value: object, expected: ReferenceKind) -> Self:
        obj = record(value, "kind sha256")
        _literal(obj["kind"], expected.value)
        return cls(expected, sha256_text(obj["sha256"]))


def _ref(value: object, expected: ReferenceKind) -> NativeDigestRef:
    return NativeDigestRef.from_wire(value, expected)


def _reference_validator(kind: ReferenceKind) -> Validator:
    def validate(value: JSONValue) -> NativeDigestRef:
        return _ref(value, kind)

    return validate


REF_FIELDS = {
    "experiment_ref": ReferenceKind.EXPERIMENT,
    "protocol_ref": ReferenceKind.PROTOCOL,
    "result_ref": ReferenceKind.RESULT,
    "evidence_ref": ReferenceKind.EVIDENCE,
    "dataset_digest": ReferenceKind.DATASET,
}


def _native_refs(value: object, *, complete: bool = False) -> WireObject:
    obj = record(value, "native_attempt_id " + " ".join(REF_FIELDS))
    _slot(obj["native_attempt_id"], uuid4_text)
    for field, kind in REF_FIELDS.items():
        _slot(obj[field], _reference_validator(kind))
    if complete:
        require(all(_is_present(v) for v in obj.values()), Reason.SOURCE_REFERENCE_MISSING)
    if _is_present(obj["protocol_ref"]):
        require(
            cast(WireObject, cast(WireObject, obj["protocol_ref"])["value"])["sha256"]
            == PROTOCOL_SHA256
        )
    if _is_present(obj["dataset_digest"]):
        require(
            cast(WireObject, cast(WireObject, obj["dataset_digest"])["value"])["sha256"]
            == DATASET_SHA256
        )
    return obj


def _display(value: object) -> str:
    result = text(value)
    require(re.fullmatch(r"-?(?:0|[1-9][0-9]*)\.[0-9]{12}", result) is not None)
    require(result != "-0.000000000000")
    return result


def fixed_protocol() -> WireObject:
    """Detached transcription of S04 Protocol.payload; no native module import."""
    return {
        "schema": NATIVE_VERSION,
        "seed": 17,
        "horizon_sessions": 20,
        "numeric_policy": NUMERIC_POLICY,
        "folds": fixed_folds(),
        "min_train_cutoffs": 40,
        "min_train_rows": 180,
        "min_issuers": 3,
        "min_test_cutoffs": 20,
        "min_test_rows": 80,
        "non_if03": True,
        "question": QUESTION,
        "h0": "beta = 0",
        "h1": "beta != 0",
        "method": METHOD,
        "feature": "LATEST_AVAILABLE_MONTH_OVER_IMMEDIATE_PREDECESSOR_MINUS_ONE",
        "temporal_policy": {
            "feature": "public_delivery < decision",
            "training_label": "available_at <= fit",
            "fit": "17:00_FIRST_TEST_SESSION",
            "prediction": "18:00_LAST_SESSION_OF_WEEK",
            "target": "20_SUBSEQUENT_SESSION_CLOSES",
            "purge": "outcome_end < first_test_start_mark",
            "score": "sealed_prediction_then_mature_outcome",
            "validation": "NOT_APPLICABLE_NO_TUNING",
        },
        "exclusion_policy": "TYPED_UNAVAILABLE_NO_IMPUTATION_NO_OLDER_PAIR_FALLBACK",
        "limitations": list(NATIVE_LIMITATIONS),
    }


def fixed_folds() -> list[JSONValue]:
    return [
        {"name": "F1", "history_end": 48, "test_start": 48, "test_end": 72},
        {"name": "F2", "history_end": 72, "test_start": 72, "test_end": 96},
    ]


PROTOCOL_SHA256 = sha256(canonical_json(fixed_protocol())).hexdigest()


def _failure(value: JSONValue) -> None:
    obj = record(value, "code native_code first_observed_at stage")
    _reason(obj["code"])
    _slot(obj["native_code"], _native_code)
    timestamp(obj["first_observed_at"])
    _slot(obj["stage"], lambda v: _enum(v, STAGES))


def _native_code(value: object) -> str:
    result = text(value)
    require(re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", result) is not None)
    return result


def _verification(value: object) -> WireObject:
    obj = record(value, "state scope checked_at manifest_sha256 failure")
    state = _enum(obj["state"], tuple(VerificationState))
    _literal(obj["scope"], "NATIVE_F3_ARTIFACTS_AND_APP_LAUNCH_BINDING")
    _slot(obj["checked_at"], timestamp)
    _slot(obj["manifest_sha256"], sha256_text)
    _slot(obj["failure"], _failure)
    if state == VerificationState.PASSED:
        require(_is_present(obj["checked_at"]) and _is_present(obj["manifest_sha256"]))
        require(obj["failure"] == unavailable(Reason.NO_FAILURE))
    elif state in (VerificationState.FAILED, VerificationState.INVALIDATED):
        require(_is_present(obj["failure"]) and _is_present(obj["checked_at"]))
    else:
        require(not any(_is_present(obj[k]) for k in ("checked_at", "manifest_sha256", "failure")))
    return obj


def _release(value: object) -> WireObject:
    obj = record(value, "state reason verification")
    state = _enum(obj["state"], tuple(ReleaseState))
    _reason(obj["reason"])
    verified = _verification(obj["verification"])
    if state == ReleaseState.AVAILABLE:
        require(verified["state"] == VerificationState.PASSED)
        _literal(obj["reason"], Reason.NO_FAILURE.value)
    else:
        require(obj["reason"] != Reason.NO_FAILURE)
    return obj


def _source_ref(value: JSONValue) -> None:
    obj = record(value, "kind source_ref version_ref qualification_ref")
    _literal(obj["kind"], "AUTHORED_SYNTHETIC_DECLARATION")
    _slot(obj["source_ref"], text)
    _slot(obj["version_ref"], text)
    _slot(obj["qualification_ref"], sha256_text)


def _question(obj: WireObject) -> None:
    for field, expected in (
        ("question", QUESTION),
        ("h0", "beta = 0"),
        ("h1", "beta != 0"),
        ("method_id", METHOD),
    ):
        _literal(obj[field], expected)


CAPABILITY_FIELDS = (
    "capability_id capability_revision readiness unavailable_reasons submission_gate "
    "question h0 h1 method_id native_protocol_schema protocol_ref source_bytes_sha256 "
    "manifest_bytes_sha256 dataset_digest decision_frequency cutoff_count issuer_count "
    "horizon_sessions seed folds numeric_policy application_build_ref native_provenance_basis "
    "resource_policy_ref replay_modes"
)


def _capability_fields(value: object) -> WireObject:
    obj = record(value, CAPABILITY_FIELDS)
    _literal(obj["capability_id"], CAPABILITY_ID)
    sha256_text(obj["capability_revision"])
    readiness = _enum(obj["readiness"], ("EXECUTABLE", "UNAVAILABLE"))
    reasons = _array(obj["unavailable_reasons"], _reason)
    require((readiness == "EXECUTABLE") == (len(reasons) == 0))
    gate = _enum(
        obj["submission_gate"], ("OPEN", "JOB_BUSY", "RECOVERY_BLOCKED", "STORAGE_BLOCKED")
    )
    _question(obj)
    _literal(obj["native_protocol_schema"], NATIVE_VERSION)
    require(_ref(obj["protocol_ref"], ReferenceKind.PROTOCOL).sha256 == PROTOCOL_SHA256)
    require(_ref(obj["dataset_digest"], ReferenceKind.DATASET).sha256 == DATASET_SHA256)
    _literal(obj["source_bytes_sha256"], SOURCE_SHA256)
    _literal(obj["manifest_bytes_sha256"], MANIFEST_SHA256)
    _literal(obj["decision_frequency"], "WEEKLY")
    for field, expected in (
        ("cutoff_count", 96),
        ("issuer_count", 5),
        ("horizon_sessions", 20),
        ("seed", 17),
    ):
        uint(obj[field])
        _literal(obj[field], expected)
    folds = _array(obj["folds"], lambda v: record(v, "name history_end test_start test_end"), 2)
    require(canonical_json(folds) == canonical_json(fixed_folds()))
    _literal(obj["numeric_policy"], NUMERIC_POLICY)
    sha256_text(obj["application_build_ref"])
    sha256_text(obj["native_provenance_basis"])
    policy = _slot(obj["resource_policy_ref"], sha256_text)
    if policy["state"] == "UNAVAILABLE":
        require(readiness == "UNAVAILABLE" and gate != "OPEN")
    _literal(
        canonical_json(obj["replay_modes"]),
        canonical_json(
            [
                "NATIVE_DIRECTORY_VERIFICATION",
                "FRESH_PROCESS_NATIVE_RESEARCH_REPLAY",
            ]
        ),
    )
    return obj


def capability_control_bytes(payload: object) -> bytes:
    """Fingerprint a closed descriptor payload; never establishes readiness."""
    obj = _capability_fields(_json(payload))
    excluded = {"capability_revision", "readiness", "unavailable_reasons", "submission_gate"}
    basis: WireObject = {"schema_version": VERSION}
    basis.update({k: v for k, v in obj.items() if k not in excluded})
    return CAPABILITY_DOMAIN + canonical_json(basis)


def capability_revision(payload: object) -> str:
    return sha256(capability_control_bytes(payload)).hexdigest()


def _capability(value: object) -> None:
    obj = _capability_fields(value)
    require(obj["capability_revision"] == capability_revision(obj), Reason.CAPABILITY_CHANGED)


def _submission(value: object) -> None:
    obj = record(
        value, "schema_version kind capability_id capability_revision data_mode idempotency_key"
    )
    _literal(obj["schema_version"], VERSION)
    _literal(obj["kind"], Kind.SUBMISSION_REQUEST.value)
    _literal(obj["capability_id"], CAPABILITY_ID)
    _literal(obj["data_mode"], "SYNTHETIC_GOLDEN")
    sha256_text(obj["capability_revision"])
    uuid4_text(obj["idempotency_key"])


def submission_control_bytes(request: object) -> bytes:
    obj = _json(request)
    _submission(obj)
    assert isinstance(obj, dict)
    return SUBMISSION_DOMAIN + canonical_json(
        {k: v for k, v in obj.items() if k != "idempotency_key"}
    )


def submission_fingerprint(request: object) -> str:
    return sha256(submission_control_bytes(request)).hexdigest()


def _run_relation(obj: WireObject) -> str:
    app_id = uuid4_text(obj["app_run_id"])
    kind = _enum(obj["run_kind"], ("EXPERIMENT", "FRESH_REPLAY"))
    relation = _slot(obj["replay_of_app_run_id"], uuid4_text)
    if kind == "EXPERIMENT":
        require(relation == unavailable(Reason.NOT_A_REPLAY))
    else:
        require(relation["state"] == "PRESENT" and relation["value"] != app_id)
    return app_id


def _receipt(value: object) -> None:
    obj = record(
        value,
        "app_run_id run_kind replay_of_app_run_id accepted_at idempotency_key "
        "request_fingerprint capability_id capability_revision native_refs status_path",
    )
    app_id = _run_relation(obj)
    timestamp(obj["accepted_at"])
    uuid4_text(obj["idempotency_key"])
    sha256_text(obj["request_fingerprint"])
    _literal(obj["capability_id"], CAPABILITY_ID)
    sha256_text(obj["capability_revision"])
    _native_refs(obj["native_refs"])
    _literal(obj["status_path"], BASE_PATH + app_id)


def _progress(value: JSONValue) -> None:
    obj = record(value, "stage finished_at elapsed_ns")
    _enum(obj["stage"], STAGES)
    timestamp(obj["finished_at"])
    uint_text(obj["elapsed_ns"])


def _status(value: object) -> None:
    obj = record(
        value,
        "app_run_id run_kind replay_of_app_run_id catalog_revision phase "
        "accepted_at updated_at started_at finished_at native_refs native_execution_status "
        "completed_stages first_failure release result_path evidence_path",
    )
    app_id = _run_relation(obj)
    uint_text(obj["catalog_revision"])
    phase = _enum(
        obj["phase"],
        (
            "INTENT_RECORDED",
            "STARTING",
            "NATIVE_RUNNING",
            "VERIFYING",
            "RECONCILING",
            "COMPLETE",
            "FAILED",
            "BLOCKED",
        ),
    )
    timestamp(obj["accepted_at"])
    timestamp(obj["updated_at"])
    _slot(obj["started_at"], timestamp)
    _slot(obj["finished_at"], timestamp)
    _native_refs(obj["native_refs"], complete=phase == "COMPLETE")
    _slot(obj["native_execution_status"], lambda v: _enum(v, ("RUNNING", "SUCCEEDED", "FAILED")))
    stages = _array(obj["completed_stages"], _progress)
    names = [cast(WireObject, stage)["stage"] for stage in stages]
    require(names == list(STAGES[: len(names)]))
    _slot(obj["first_failure"], _failure)
    release = _release(obj["release"])
    for field, suffix in (("result_path", "/result"), ("evidence_path", "/evidence")):
        slot = _slot(obj[field], text)
        if release["state"] == "AVAILABLE":
            require(slot == present(BASE_PATH + app_id + suffix))
        else:
            require(slot["state"] == "UNAVAILABLE")
    if phase == "COMPLETE":
        require(obj["native_execution_status"] == present("SUCCEEDED"))
        require(obj["first_failure"] == unavailable(Reason.NO_FAILURE))
        require(
            _is_present(obj["started_at"])
            and _is_present(obj["finished_at"])
            and names == list(STAGES)
        )
        require(release["state"] in ("AVAILABLE", "BLOCKED"))
        if release["state"] == "BLOCKED":
            require(
                cast(WireObject, release["verification"])["state"] == VerificationState.INVALIDATED
            )
    else:
        require(release["state"] != "AVAILABLE")


# These existing reasons describe policy/input admission without an execution
# failure. Recovery/launch/verification problems are deliberately not in this set.
_STATUS_POLICY_BLOCKS = (
    Reason.NATIVE_WITHHELD,
    Reason.SERVICE_NOT_READY,
    Reason.STORAGE_BLOCKED,
    Reason.RESOURCE_LIMIT,
    Reason.SOURCE_REFERENCE_MISSING,
    Reason.NATIVE_UNKNOWN_STATE,
)
_STATUS_OPERATION_FAILURES = (
    Reason.LAUNCH_INTERRUPTED,
    Reason.CHILD_NONZERO_EXIT,
    Reason.CHILD_TIMEOUT,
    Reason.SUPERVISOR_LOST,
    Reason.EXECUTION_OUTCOME_UNKNOWN,
    Reason.VERIFICATION_FAILED,
    Reason.ARTIFACT_INTEGRITY_FAILED,
    Reason.NATIVE_CONTRACT_INVALID,
    Reason.RECOVERY_BLOCKED,
    Reason.INTERNAL_ERROR,
)


def _status_without_launch(obj: WireObject, *, input_pins: bool = False) -> None:
    """No issued native execution artifacts; reconciliation may know input pins."""
    require(not _is_present(obj["started_at"]))
    require(not _is_present(obj["native_execution_status"]) and not obj["completed_stages"])
    refs = cast(WireObject, obj["native_refs"])
    for field, value in refs.items():
        if not input_pins or field not in ("protocol_ref", "dataset_digest"):
            require(not _is_present(value))
    verification = cast(WireObject, cast(WireObject, obj["release"])["verification"])
    require(verification["state"] == VerificationState.NOT_CHECKED)


def _status_times(obj: WireObject) -> None:
    """Compare app wall timestamps only; never native decision/fit clocks."""
    accepted = datetime.fromisoformat(text(obj["accepted_at"]))
    updated = datetime.fromisoformat(text(obj["updated_at"]))
    require(accepted <= updated)
    lower = accepted
    for field in ("started_at", "finished_at"):
        slot = cast(WireObject, obj[field])
        if slot["state"] == "PRESENT":
            observed = datetime.fromisoformat(text(slot["value"]))
            require(lower <= observed <= updated)
            lower = observed
    failure = cast(WireObject, obj["first_failure"])
    if failure["state"] == "PRESENT":
        body = cast(WireObject, failure["value"])
        observed = datetime.fromisoformat(text(body["first_observed_at"]))
        require(accepted <= observed <= updated)
        require(body["code"] != Reason.NO_FAILURE)
    else:
        require(failure == unavailable(Reason.NO_FAILURE))


def _status_lifecycle(envelope: WireObject) -> None:
    """Mandatory envelope-context closure, not a process/verification authority."""
    obj = cast(WireObject, envelope["payload"])
    phase = text(obj["phase"])
    execution = text(envelope["execution_status"])
    provenance = text(envelope["execution_provenance"])
    release = cast(WireObject, obj["release"])
    verification = cast(WireObject, release["verification"])
    actual = provenance == Provenance.ACTUAL_F3_CLI
    first = _is_present(obj["first_failure"])
    _status_times(obj)
    if first:
        failure = cast(WireObject, cast(WireObject, obj["first_failure"])["value"])
        if failure["code"] in (Reason.CHILD_NONZERO_EXIT, Reason.CHILD_TIMEOUT):
            require(actual)
    if release["reason"] in (Reason.CHILD_NONZERO_EXIT, Reason.CHILD_TIMEOUT):
        require(actual)

    if provenance == Provenance.FIXTURE_ONLY:
        require(execution == Execution.NOT_RUN)
        require(phase in ("INTENT_RECORDED", "STARTING", "BLOCKED"))
        _status_without_launch(obj)
    else:
        expected = {
            "INTENT_RECORDED": Execution.PENDING,
            "STARTING": Execution.PENDING,
            "NATIVE_RUNNING": Execution.RUNNING,
            "VERIFYING": Execution.RUNNING,
            "COMPLETE": Execution.SUCCEEDED,
            "FAILED": Execution.FAILED,
            "BLOCKED": Execution.BLOCKED,
            "RECONCILING": Execution.RUNNING if actual else Execution.PENDING,
        }
        require(execution == expected[phase])
        if actual:
            require(_is_present(obj["started_at"]))
        else:
            _status_without_launch(obj, input_pins=phase == "RECONCILING")

    if phase in ("INTENT_RECORDED", "STARTING"):
        require(not actual and not _is_present(obj["finished_at"]))
    elif phase in ("NATIVE_RUNNING", "VERIFYING"):
        require(actual and not _is_present(obj["finished_at"]))
        if phase == "NATIVE_RUNNING":
            require(verification["state"] == VerificationState.NOT_CHECKED)
    elif phase == "RECONCILING":
        if not actual:
            require(not _is_present(obj["finished_at"]))
    elif phase == "COMPLETE":
        require(actual)
        # _status validates full native refs/stages, timestamps and NO_FAILURE.
    elif phase == "FAILED":
        require(actual and first and _is_present(obj["finished_at"]))
    else:
        require(phase == "BLOCKED" and release["state"] == ReleaseState.BLOCKED)
        if actual or release["reason"] not in _STATUS_POLICY_BLOCKS:
            require(first)

    if phase != "COMPLETE":
        require(release["state"] != ReleaseState.AVAILABLE)
        known_failure = (
            obj["native_execution_status"] == present("FAILED")
            or verification["state"] == VerificationState.FAILED
            or release["reason"] in _STATUS_OPERATION_FAILURES
        )
        require(not known_failure or first)
    if verification["state"] in (VerificationState.PASSED, VerificationState.INVALIDATED):
        _native_refs(obj["native_refs"], complete=True)
        require(obj["native_execution_status"] == present("SUCCEEDED"))
        require(len(cast(list[JSONValue], obj["completed_stages"])) == len(STAGES))
    if verification["state"] == VerificationState.INVALIDATED:
        require(phase == "COMPLETE")
    if release["state"] == ReleaseState.AVAILABLE:
        require(actual and envelope["pit_status"] != Pit.WITHHELD)


def _metrics(value: object) -> None:
    obj = record(
        value,
        "n exact display oos_improvement units iid_inference adjacent_residual_pairs "
        "diagnostic_interpretation",
    )
    require(uint(obj["n"]) > 0)
    exact = record(obj["exact"], " ".join((*METRIC_NAMES, ADJACENT_METRIC)))
    display = record(
        obj["display"], " ".join((*METRIC_NAMES, ADJACENT_METRIC, "rmse", "oos_improvement"))
    )
    for field in METRIC_NAMES:
        ExactFraction.from_wire(exact[field])
        _display(display[field])
    _display(display["rmse"])
    pairs = uint(obj["adjacent_residual_pairs"])
    for values, validator in ((exact, ExactFraction.from_wire), (display, _display)):
        slot = _slot(values[ADJACENT_METRIC], validator)
        require(_is_present(slot) == (pairs > 0))
        if pairs == 0:
            require(slot == unavailable(Reason.NO_ADJACENT_PAIRS))
    improvement = obj["oos_improvement"]
    if type(improvement) is dict and "state" in improvement:
        record(improvement, "state reason")
        require(improvement == {"state": "NOT_COMPUTABLE", "reason": "ZERO_BASELINE_SSE"})
        require(display["oos_improvement"] == unavailable(Reason.ZERO_BASELINE_SSE))
    else:
        ExactFraction.from_wire(improvement)
        require(_slot(display["oos_improvement"], _display)["state"] == "PRESENT")
    _literal(obj["units"], UNITS)
    _literal(obj["iid_inference"], "NOT_PERFORMED")
    _literal(obj["diagnostic_interpretation"], DIAGNOSTIC)


def _exclusion(value: JSONValue) -> None:
    obj = record(value, "native_reason count")
    _enum(obj["native_reason"], EXCLUSION_REASONS)
    uint(obj["count"])


EXCLUSION_REASONS = tuple(
    "INFORMATION_" + state for state in FactState if state != FactState.KNOWN
) + (
    "IMMATURE_LABEL",
    "OUTCOME_OVERLAPS_TEST",
)


def _fold_result(value: object) -> None:
    obj = record(
        value,
        "fold state_id fit_cutoff history_candidates test_ticks training_count "
        "training_cutoffs training_issuers scored_count scored_cutoffs excluded_training_count "
        "exclusion_counts latest_training_label_availability distinct_issuer_month_releases "
        "distinct_source_versions alpha beta gbar rbar metrics",
    )
    fold = _enum(obj["fold"], ("F1", "F2"))
    _ref(obj["state_id"], ReferenceKind.STATE)
    native_time(obj["fit_cutoff"])
    native_time(obj["latest_training_label_availability"])
    for field in ("history_candidates", "test_ticks"):
        _array(obj[field], uint, 2)
    require(obj["history_candidates"] == ([0, 47] if fold == "F1" else [0, 71]))
    require(obj["test_ticks"] == ([48, 71] if fold == "F1" else [72, 95]))
    for field in (
        "training_count",
        "training_cutoffs",
        "training_issuers",
        "scored_count",
        "scored_cutoffs",
        "excluded_training_count",
        "distinct_issuer_month_releases",
        "distinct_source_versions",
    ):
        uint(obj[field])
    for field in ("alpha", "beta", "gbar", "rbar"):
        ExactFraction.from_wire(obj[field])
    _array(obj["exclusion_counts"], _exclusion)
    _metrics(obj["metrics"])
    require(cast(WireObject, obj["metrics"])["n"] == obj["scored_count"])
    require(uint(obj["training_count"]) >= 180 and uint(obj["training_cutoffs"]) >= 40)
    require(3 <= uint(obj["training_issuers"]) <= 5)
    require(uint(obj["scored_count"]) >= 80 and 20 <= uint(obj["scored_cutoffs"]) <= 24)


def _dependence(value: object) -> None:
    obj = record(
        value,
        "weekly_rows_are_independent target_overlap "
        "overlapping_within_issuer_scored_window_pairs common_price_shocks "
        "effective_sample_size interpretation",
    )
    _literal(obj["weekly_rows_are_independent"], False)
    _literal(obj["target_overlap"], True)
    uint(obj["overlapping_within_issuer_scored_window_pairs"])
    _literal(obj["common_price_shocks"], True)
    _literal(obj["effective_sample_size"], "NOT_ESTIMATED")
    _literal(obj["interpretation"], "NO_H0_REJECTION_OR_POPULATION_INFERENCE")


def _result(value: object) -> None:
    obj = record(
        value,
        "app_run_id native_refs verification question h0 h1 method_id "
        "decision_frequency horizon_sessions seed interpretation aggregate folds dependence",
    )
    uuid4_text(obj["app_run_id"])
    _native_refs(obj["native_refs"], complete=True)
    require(_verification(obj["verification"])["state"] == VerificationState.PASSED)
    _question(obj)
    _literal(obj["decision_frequency"], "WEEKLY")
    _literal(obj["horizon_sessions"], 20)
    _literal(obj["seed"], 17)
    _literal(obj["interpretation"], INTERPRETATION)
    _metrics(obj["aggregate"])
    folds = _array(obj["folds"], _fold_result, 2)
    require([cast(WireObject, f)["fold"] for f in folds] == ["F1", "F2"])
    _dependence(obj["dependence"])
    require(
        cast(WireObject, obj["aggregate"])["n"]
        == sum(uint(cast(WireObject, f)["scored_count"]) for f in folds)
    )


def relative_source_path(value: object) -> str:
    result = text(value)
    require(not result.startswith("/") and "\\" not in result)
    require(all(part not in ("", ".", "..") for part in result.split("/")))
    fixed = {
        "src/pit_research_lab/__init__.py",
        "src/pit_research_lab/mvp/__init__.py",
        "src/pit_research_lab/mvp/f2/__init__.py",
        "src/pit_research_lab/mvp/f2/research_panel.py",
        "src/pit_research_lab/mvp/research_vslice/__init__.py",
        "src/pit_research_lab/mvp/research_vslice/contracts.py",
        "pyproject.toml",
        "uv.lock",
        "docs/mvp/v1.0/f3-l1-research-runtime-v0.1.md",
        "tests/fixtures/mvp_f3_l1/revenue_growth_panel_v0_1.json",
        "tests/fixtures/mvp_f3_l1/manifest_v0_1.json",
        "tests/fixtures/mvp_f3_l1/generate.py",
    }
    pattern = (
        r"(?:src/pit_research_lab/domain|src/pit_research_lab/mvp/f3_l1|"
        r"tests/unit/mvp_f3_l1)/[A-Za-z_][A-Za-z0-9_]*\.py"
    )
    require(result in fixed or re.fullmatch(pattern, result) is not None)
    return result


def _file_pin(value: JSONValue) -> None:
    obj = record(value, "path byte_length sha256")
    relative_source_path(obj["path"])
    uint_text(obj["byte_length"])
    sha256_text(obj["sha256"])


def _code_pin(value: JSONValue) -> None:
    obj = record(value, "path sha256")
    relative_source_path(obj["path"])
    sha256_text(obj["sha256"])


def _artifact_pin(value: JSONValue) -> None:
    obj = record(value, "name byte_length sha256 role")
    name = _enum(obj["name"], ARTIFACTS)
    uint_text(obj["byte_length"])
    sha256_text(obj["sha256"])
    _literal(obj["role"], "ATTEMPT_METADATA" if name == "attempt.json" else "DETERMINISTIC_CONTENT")


def _source_summary(value: object) -> WireObject:
    obj = record(
        value,
        "dataset_digest calendar_id issuer_roster cutoffs calendar_coverage "
        "revenue_declarations price_marks scope non_if03 admission_eligible "
        "source_authentication native_invocations invocation_count_scope",
    )
    require(_ref(obj["dataset_digest"], ReferenceKind.DATASET).sha256 == DATASET_SHA256)
    _literal(obj["calendar_id"], "SYN-L1-CALENDAR-V1")
    require(obj["issuer_roster"] == list(ISSUERS))
    cutoffs = _array(obj["cutoffs"], native_time, 96)
    require(cutoffs == sorted(set(cast(list[str], cutoffs))))
    _array(obj["calendar_coverage"], _date, 2)
    for field in ("revenue_declarations", "price_marks", "native_invocations"):
        uint(obj[field])
    _literal(obj["scope"], "AUTHORED_SYNTHETIC_PUBLIC_ONLY")
    _literal(obj["non_if03"], True)
    _literal(obj["admission_eligible"], False)
    _literal(obj["source_authentication"], "NOT_ESTABLISHED")
    _literal(
        obj["invocation_count_scope"],
        "TOP_LEVEL_ASOF_AND_EXPLICIT_S1_S2_CALLS_EXCLUDES_TRANSITIVE_REPLAY",
    )
    return obj


SELECTION_STATES = ("SELECTED", "UNRESOLVED", "NO_QUALIFIED_CLAIM")
SELECTION_REASONS = (
    "NONE",
    "NO_QUALIFIED_WITHIN_SCOPE",
    "INPUT_INVENTORY_LIMIT",
    "UNSUPPORTED_RELATION_GRAPH",
    "RELATION_UNQUALIFIED",
    "MATERIAL_CANDIDATE_UNRESOLVED",
    "COVERAGE_INSUFFICIENT",
    "ATTRIBUTION_UNRESOLVED",
)
FACT_REASONS = (*SELECTION_REASONS, *tuple(FactState), "MISSING_PREDECESSOR")


def _fact_trace(value: object) -> WireObject:
    obj = record(
        value,
        "month state native_state reason source_ref version_ref qualification_ref "
        "publication available_at unit basis",
    )
    month = text(obj["month"])
    _date(month + "-01")
    state = _enum(obj["state"], tuple(FactState))
    _enum(obj["native_state"], SELECTION_STATES)
    _enum(obj["reason"], FACT_REASONS)
    for field in ("source_ref", "version_ref"):
        _slot(obj[field], text)
    _slot(obj["qualification_ref"], sha256_text)
    for field in ("publication", "available_at"):
        _slot(obj[field], native_time)
    _literal(obj["unit"], "NTD_thousands")
    _literal(obj["basis"], "consolidated-v1")
    if state == FactState.KNOWN:
        require(
            all(
                _is_present(obj[k])
                for k in (
                    "source_ref",
                    "version_ref",
                    "qualification_ref",
                    "publication",
                    "available_at",
                )
            ),
            Reason.SOURCE_REFERENCE_MISSING,
        )
        _literal(obj["native_state"], "SELECTED")
        _literal(obj["reason"], "NONE")
        require(
            cast(WireObject, obj["version_ref"])["value"]
            == str(cast(WireObject, obj["source_ref"])["value"]) + "-VERSION"
        )
    return obj


def _observation_trace(value: object) -> None:
    obj = record(value, "sample_id issuer tick cutoff binding_id current previous")
    issuer = _enum(obj["issuer"], ISSUERS)
    tick = uint(obj["tick"])
    require(tick < 96)
    _literal(obj["sample_id"], f"{issuer}:t{tick:02}")
    native_time(obj["cutoff"])
    _ref(obj["binding_id"], ReferenceKind.BINDING)
    _fact_trace(obj["current"])
    _fact_trace(obj["previous"])


def _selected_source(value: JSONValue) -> None:
    obj = record(value, "assertion source_sha256 s1 s2")
    text(obj["assertion"])
    sha256_text(obj["source_sha256"])
    _literal(obj["s1"], "BOUND")
    _literal(obj["s2"], "SUPPORTED")


def _value_qualification(value: JSONValue) -> None:
    obj = record(value, "source_sha256 s1 s2 native_invocation")
    sha256_text(obj["source_sha256"])
    _literal(obj["s1"], "BOUND")
    _literal(obj["s2"], "SUPPORTED")
    _literal(obj["native_invocation"], "RUN")


def _safe_receipt(value: object) -> None:
    obj = record(
        value,
        "qualification_ref schema non_if03 dataset_digest cutoff subject state reason "
        "native_invocation selected_sources code_pins revenue_value_qualification",
    )
    sha256_text(obj["qualification_ref"])
    _literal(obj["schema"], "F2_L1_QUALIFICATION_RECEIPT_V1")
    _literal(obj["non_if03"], True)
    require(_ref(obj["dataset_digest"], ReferenceKind.DATASET).sha256 == DATASET_SHA256)
    native_time(obj["cutoff"])
    text(obj["subject"])
    _enum(obj["state"], SELECTION_STATES)
    _enum(obj["reason"], SELECTION_REASONS)
    _literal(obj["native_invocation"], "RUN")
    _array(obj["selected_sources"], _selected_source)
    _array(obj["code_pins"], _code_pin)
    _slot(obj["revenue_value_qualification"], _value_qualification)


def _evidence(value: object) -> None:
    obj = record(
        value,
        "app_run_id native_refs verification evidence_scope test_execution_attestation "
        "application_build_ref resource_policy_ref native_code_claim native_base_head runtime "
        "source_file_pins source_bytes_sha256 manifest_bytes_sha256 artifacts source_summary "
        "observation_trace native_receipts",
    )
    uuid4_text(obj["app_run_id"])
    _native_refs(obj["native_refs"], complete=True)
    require(_verification(obj["verification"])["state"] == VerificationState.PASSED)
    _literal(obj["evidence_scope"], "EXECUTED_AUTHORED_SYNTHETIC_RESEARCH_ONLY")
    _literal(obj["test_execution_attestation"], "NOT_ATTESTED_BY_EXPERIMENT_RUNTIME")
    sha256_text(obj["application_build_ref"])
    sha256_text(obj["resource_policy_ref"])
    _literal(obj["native_code_claim"], "ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT")
    require(re.fullmatch(r"[0-9a-f]{40}", text(obj["native_base_head"])) is not None)
    runtime = record(obj["runtime"], "python implementation")
    require(text(runtime["python"]).startswith("3.12."))
    text(runtime["implementation"])
    pins = _array(obj["source_file_pins"], _file_pin)
    paths = [text(cast(WireObject, p)["path"]) for p in pins]
    require(paths == sorted(set(paths)))
    _literal(obj["source_bytes_sha256"], SOURCE_SHA256)
    _literal(obj["manifest_bytes_sha256"], MANIFEST_SHA256)
    artifacts = _array(obj["artifacts"], _artifact_pin, 10)
    require([cast(WireObject, a)["name"] for a in artifacts] == list(ARTIFACTS))
    artifact_hashes = {
        text(cast(WireObject, a)["name"]): cast(WireObject, a)["sha256"] for a in artifacts
    }
    native = cast(WireObject, obj["native_refs"])
    for name, field in (
        ("spec.json", "experiment_ref"),
        ("result.json", "result_ref"),
        ("evidence.json", "evidence_ref"),
    ):
        require(
            cast(WireObject, cast(WireObject, native[field])["value"])["sha256"]
            == artifact_hashes[name]
        )
    summary = _source_summary(obj["source_summary"])
    observations = _array(obj["observation_trace"], _observation_trace, 480)
    receipts = _array(obj["native_receipts"], _safe_receipt)
    receipt_refs = [text(cast(WireObject, r)["qualification_ref"]) for r in receipts]
    require(len(receipt_refs) == len(set(receipt_refs)))
    cutoffs = cast(list[JSONValue], summary["cutoffs"])
    by_receipt = {
        text(cast(WireObject, r)["qualification_ref"]): cast(WireObject, r) for r in receipts
    }
    for index, member in enumerate(observations):
        obs = cast(WireObject, member)
        require(obs["tick"] == index // 5 and obs["issuer"] == ISSUERS[index % 5])
        require(obs["cutoff"] == cutoffs[index // 5])
        for field in ("current", "previous"):
            fact = cast(WireObject, obs[field])
            ref = cast(WireObject, fact["qualification_ref"])
            if ref["state"] == "PRESENT":
                require(ref["value"] in receipt_refs, Reason.SOURCE_REFERENCE_MISSING)
                require(by_receipt[text(ref["value"])]["cutoff"] == obs["cutoff"])
            if fact["state"] == "KNOWN":
                require(
                    text(cast(WireObject, fact["publication"])["value"])
                    <= text(cast(WireObject, fact["available_at"])["value"])
                    < text(obs["cutoff"])
                )


def _comparison(value: JSONValue) -> None:
    obj = record(value, "artifact original_sha256 replay_sha256 byte_equal")
    _enum(obj["artifact"], DETERMINISTIC_ARTIFACTS)
    sha256_text(obj["original_sha256"])
    sha256_text(obj["replay_sha256"])
    require(type(obj["byte_equal"]) is bool)
    require((obj["original_sha256"] == obj["replay_sha256"]) == obj["byte_equal"])


def _replay(value: object) -> None:
    obj = record(
        value,
        "original_app_run_id replay_app_run_id mode state original_native_refs "
        "replay_native_refs original_verification replay_verification basis_check "
        "comparisons compared_at first_failure scope attempt_metadata_policy",
    )
    require(uuid4_text(obj["original_app_run_id"]) != uuid4_text(obj["replay_app_run_id"]))
    _literal(obj["mode"], "FRESH_PROCESS_NATIVE_RESEARCH_REPLAY")
    state = _enum(
        obj["state"],
        (
            "NOT_RUN",
            "PENDING",
            "RUNNING",
            "MATCH",
            "MISMATCH",
            "NOT_COMPARABLE",
            "FAILED",
            "BLOCKED",
        ),
    )
    compared = state in ("MATCH", "MISMATCH")
    original = _native_refs(obj["original_native_refs"], complete=compared)
    replay = _native_refs(obj["replay_native_refs"], complete=compared)
    checks = [
        _verification(obj[field]) for field in ("original_verification", "replay_verification")
    ]
    basis = record(obj["basis_check"], "state reasons")
    _enum(basis["state"], ("SAME", "DIFFERENT", "UNAVAILABLE"))
    reasons = _array(basis["reasons"], _reason)
    require((basis["state"] == "SAME") == (not reasons))
    comparisons = _array(obj["comparisons"], _comparison)
    _slot(obj["compared_at"], timestamp)
    _slot(obj["first_failure"], _failure)
    if compared:
        require(all(check["state"] == VerificationState.PASSED for check in checks))
        require(basis["state"] == "SAME" and _is_present(obj["compared_at"]))
        require(original["native_attempt_id"] != replay["native_attempt_id"])
        require(
            [cast(WireObject, c)["artifact"] for c in comparisons] == list(DETERMINISTIC_ARTIFACTS)
        )
        for comparison in comparisons:
            row = cast(WireObject, comparison)
            field = {
                "spec.json": "experiment_ref",
                "result.json": "result_ref",
                "evidence.json": "evidence_ref",
            }.get(text(row["artifact"]))
            if field is not None:
                for side, references in (("original", original), ("replay", replay)):
                    require(
                        cast(WireObject, cast(WireObject, references[field])["value"])["sha256"]
                        == row[side + "_sha256"]
                    )
        equal = all(cast(WireObject, c)["byte_equal"] is True for c in comparisons)
        require((state == "MATCH") == equal)
        if state == "MATCH":
            require(all(original[k] == replay[k] for k in REF_FIELDS))
        require(obj["first_failure"] == unavailable(Reason.NO_FAILURE))
    else:
        require(not comparisons and not _is_present(obj["compared_at"]))
    if state == "NOT_COMPARABLE":
        require(basis["state"] != "SAME")
    _literal(obj["scope"], "NATIVE_DETERMINISTIC_RESEARCH_BYTES_ONLY")
    _literal(
        obj["attempt_metadata_policy"],
        "EXPECT_DISTINCT_ATTEMPT_UUID_EXCLUDE_WALL_TIME_AND_DURATION_FROM_CONTENT_EQUALITY",
    )


def _error(value: object) -> None:
    obj = record(value, "schema_version kind code request_id app_run_id")
    _literal(obj["schema_version"], VERSION)
    _literal(obj["kind"], Kind.ERROR.value)
    _reason(obj["code"])
    uuid4_text(obj["request_id"])
    _slot(obj["app_run_id"], uuid4_text)


PAYLOAD_VALIDATORS: dict[Kind, Callable[[object], None]] = {
    Kind.CAPABILITY: _capability,
    Kind.RUN_RECEIPT: _receipt,
    Kind.RUN_STATUS: _status,
    Kind.VERIFIED_RESULT: _result,
    Kind.EVIDENCE_PROVENANCE: _evidence,
    Kind.BASIC_REPLAY_RESULT: _replay,
}


def _validate_document(value: JSONValue, expected: Kind) -> None:
    require(type(value) is dict)
    obj = cast(WireObject, value)
    require(obj.get("schema_version") == VERSION, Reason.UNSUPPORTED_SCHEMA)
    _literal(obj.get("kind"), expected.value)
    if expected == Kind.SUBMISSION_REQUEST:
        _submission(obj)
        return
    if expected == Kind.ERROR:
        _error(obj)
        return
    record(
        obj,
        "schema_version kind non_if03 data_mode pit_status execution_status evidence_class "
        "execution_provenance source_refs limitations payload",
    )
    _literal(obj["non_if03"], True)
    _literal(obj["data_mode"], "SYNTHETIC_GOLDEN")
    pit = _enum(obj["pit_status"], tuple(Pit))
    execution = _enum(obj["execution_status"], tuple(Execution))
    provenance = _enum(obj["execution_provenance"], tuple(Provenance))
    _literal(obj["evidence_class"], "UNVERIFIED")
    _array(obj["source_refs"], _source_ref)
    limitations = [*NATIVE_LIMITATIONS, *APP_LIMITATIONS]
    if provenance == Provenance.FIXTURE_ONLY:
        limitations.append(FIXTURE_LIMITATION)
        require(execution == Execution.NOT_RUN)
    if provenance == Provenance.NOT_EXECUTED:
        require(execution in (Execution.NOT_RUN, Execution.PENDING, Execution.BLOCKED))
    require(obj["limitations"] == limitations)
    PAYLOAD_VALIDATORS[expected](obj["payload"])
    payload = cast(WireObject, obj["payload"])
    if expected == Kind.CAPABILITY:
        require(execution == Execution.NOT_RUN and provenance != Provenance.ACTUAL_F3_CLI)
    if expected == Kind.RUN_STATUS:
        _status_lifecycle(obj)
    if expected in (Kind.VERIFIED_RESULT, Kind.EVIDENCE_PROVENANCE):
        require(execution == Execution.SUCCEEDED and provenance == Provenance.ACTUAL_F3_CLI)
        require(pit == Pit.UNRESOLVED, Reason.NATIVE_WITHHELD)
    if expected == Kind.EVIDENCE_PROVENANCE:
        for row in cast(list[WireObject], payload["observation_trace"]):
            require(
                all(
                    cast(WireObject, row[f])["state"] != "WITHHELD" for f in ("current", "previous")
                ),
                Reason.NATIVE_WITHHELD,
            )
    if expected == Kind.BASIC_REPLAY_RESULT and payload["state"] in ("MATCH", "MISMATCH"):
        require(execution == Execution.SUCCEEDED and provenance == Provenance.ACTUAL_F3_CLI)
        require(pit == Pit.UNRESOLVED)


@dataclass(frozen=True, slots=True)
class WireDocument:
    """Immutable schema-checked CLAIM, never proof of verification or release.

    Only named concrete types are accepted. The stored canonical bytes detach
    all input containers; to_wire returns a fresh copy. There is no authority
    token, verifier stub, authenticated flag or convenience release constructor.
    """

    _encoded: bytes
    KIND: ClassVar[Kind]

    def __post_init__(self) -> None:
        require(type(self) in DOCUMENT_TYPES.values())
        value = decode_json(self._encoded)
        _validate_document(value, self.KIND)
        object.__setattr__(self, "_encoded", canonical_json(value))

    @classmethod
    def from_wire(cls, value: object) -> Self:
        return cls(canonical_json(value))

    @classmethod
    def parse(cls, raw: bytes) -> Self:
        return cls(raw)

    def serialize(self) -> bytes:
        return self._encoded

    def to_wire(self) -> WireObject:
        return cast(WireObject, decode_json(self._encoded))


class CapabilityDescriptor(WireDocument):
    __slots__ = ()
    KIND = Kind.CAPABILITY


class SubmissionRequest(WireDocument):
    __slots__ = ()
    KIND = Kind.SUBMISSION_REQUEST


class ApplicationRunReceipt(WireDocument):
    __slots__ = ()
    KIND = Kind.RUN_RECEIPT


class RunStatusResponse(WireDocument):
    __slots__ = ()
    KIND = Kind.RUN_STATUS


class VerifiedResultView(WireDocument):
    __slots__ = ()
    KIND = Kind.VERIFIED_RESULT


class EvidenceProvenanceView(WireDocument):
    __slots__ = ()
    KIND = Kind.EVIDENCE_PROVENANCE


class BasicReplayResult(WireDocument):
    __slots__ = ()
    KIND = Kind.BASIC_REPLAY_RESULT


class ErrorResponse(WireDocument):
    __slots__ = ()
    KIND = Kind.ERROR


DOCUMENT_TYPES: dict[Kind, type[WireDocument]] = {
    cls.KIND: cls
    for cls in (
        CapabilityDescriptor,
        SubmissionRequest,
        ApplicationRunReceipt,
        RunStatusResponse,
        VerifiedResultView,
        EvidenceProvenanceView,
        BasicReplayResult,
        ErrorResponse,
    )
}


def parse_document(raw: bytes) -> WireDocument:
    obj = decode_json(raw)
    require(type(obj) is dict)
    assert isinstance(obj, dict)
    kind = _enum(obj.get("kind"), tuple(Kind))
    return DOCUMENT_TYPES[Kind(kind)](raw)


def validate_submission_selection(
    request: SubmissionRequest, capability: CapabilityDescriptor
) -> None:
    """Pure current-selection check; does not accept/persist/execute a job."""
    submitted = request.to_wire()
    selected = cast(WireObject, capability.to_wire()["payload"])
    require(
        submitted["capability_revision"] == selected["capability_revision"],
        Reason.CAPABILITY_CHANGED,
    )
    require(selected["readiness"] == "EXECUTABLE", Reason.SERVICE_NOT_READY)
    require(selected["submission_gate"] == "OPEN", Reason.JOB_BUSY)


def validate_status_continuity(previous: RunStatusResponse, current: RunStatusResponse) -> None:
    """Pure comparison of already closed claims; no catalog or transition engine.

    One snapshot cannot detect erasure of a previously known first cause. A later
    catalog must retain the prior record and apply this check when updating it.
    """
    before = previous.to_wire()
    after = current.to_wire()
    old = cast(WireObject, before["payload"])
    new = cast(WireObject, after["payload"])
    require(old["app_run_id"] == new["app_run_id"])
    require(
        old["run_kind"] == new["run_kind"]
        and old["replay_of_app_run_id"] == new["replay_of_app_run_id"]
    )
    if _is_present(old["first_failure"]):
        require(old["first_failure"] == new["first_failure"])
    if before["execution_provenance"] == Provenance.ACTUAL_F3_CLI:
        require(after["execution_provenance"] == Provenance.ACTUAL_F3_CLI)
        require(old["started_at"] == new["started_at"])
    if old["phase"] == "COMPLETE":
        require(new["phase"] == "COMPLETE")
        for field in ("native_refs", "completed_stages", "native_execution_status", "finished_at"):
            require(old[field] == new[field])
    if new["phase"] == "RECONCILING":
        if _is_present(old["native_execution_status"]):
            require(_is_present(new["native_execution_status"]))
        old_refs = cast(WireObject, old["native_refs"])
        new_refs = cast(WireObject, new["native_refs"])
        for field, value in old_refs.items():
            if _is_present(value):
                require(value == new_refs[field])
        stages = cast(list[JSONValue], old["completed_stages"])
        require(cast(list[JSONValue], new["completed_stages"])[: len(stages)] == stages)
        if _is_present(old["finished_at"]):
            require(old["finished_at"] == new["finished_at"])


@dataclass(frozen=True, slots=True)
class ProjectedValue:
    """A detached closed nested value; carries no verification authority."""

    _encoded: bytes

    def __post_init__(self) -> None:
        require(type(self) in PROJECTED_VALIDATORS)
        value = decode_json(self._encoded)
        PROJECTED_VALIDATORS[type(self)](value)
        object.__setattr__(self, "_encoded", canonical_json(value))

    @classmethod
    def from_wire(cls, value: object) -> Self:
        return cls(canonical_json(value))

    def to_wire(self) -> WireObject:
        return cast(WireObject, decode_json(self._encoded))

    def serialize(self) -> bytes:
        return self._encoded


class MetricsValue(ProjectedValue):
    __slots__ = ()


class FactTraceValue(ProjectedValue):
    __slots__ = ()


class SourceSummaryValue(ProjectedValue):
    __slots__ = ()


class ObservationTraceValue(ProjectedValue):
    __slots__ = ()


class SafeReceiptValue(ProjectedValue):
    __slots__ = ()


class FoldResultValue(ProjectedValue):
    __slots__ = ()


PROJECTED_VALIDATORS: dict[type[ProjectedValue], Callable[[object], object]] = {
    MetricsValue: _metrics,
    FactTraceValue: _fact_trace,
    SourceSummaryValue: _source_summary,
    ObservationTraceValue: _observation_trace,
    SafeReceiptValue: _safe_receipt,
    FoldResultValue: _fold_result,
}
