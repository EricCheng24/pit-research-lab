"""Pure W02 exact-publication assembly. Trusted input bytes are distinct from caller DTOs."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Callable
from dataclasses import MISSING, dataclass, field, fields
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any, Literal, cast

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain.pit_slice import CodeObservation
from pit_research_lab.mvp.f2.synthetic_contracts import (
    InputError,
    decode_input_bytes,
    input_bytes,
    serialize_tick_request,
)
from pit_research_lab.mvp.f2.synthetic_temporal import (
    SyntheticInputPack,
    build_weekly_requests,
    verify_input_pack,
)

SCHEMA_VERSION = "w02-evidence-assembly-v0.1"
CONTRACT_VERSION = "w02-native-mapping-v0.1"
REASON_VERSION = "w02-adapter-reasons-v0.1"
ADOPTED_FIXTURE_SHA256 = "a876570e6bcc92ffe6977aea3d2ca06b4d19f3262f33abe95ff7607db8d46fa8"


def _source_checkout_root(module_source: str) -> str | None:
    """Lexical source-checkout binding, not I/O or filesystem attestation.

    Only the loaded module's conventional absolute src layout supplies authority.
    The trusted caller must still verify Git toplevel, regular files, symlink
    exclusion and actual Native bytes before providing observation metadata.
    Wheels/relative/ambiguous module layouts fail closed rather than accepting a
    receipt-selected root. No receipt, evidence field or environment selects it.
    """
    source = PurePosixPath(module_source)
    if (
        source.anchor != "/"
        or source.as_posix() != module_source
        or ".." in source.parts
        or "\\" in module_source
        or "\x00" in module_source
        or source.parts[-5:] != ("src", "pit_research_lab", "mvp", "f2", "native_requests.py")
    ):
        return None
    root = source.parents[4]
    return root.as_posix() if root != PurePosixPath("/") else None


_MODULE_CHECKOUT_ROOT = _source_checkout_root(__file__)
_TASK = "MVP-F2-WU-02-S1S2-IMPL-01"
_FOUNDATION_SHA = "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373"
_PROFILES = (
    ("BASE", "e844d2d650268c7ecf6802211fe1111e658f6ec83821a773dc9d4e01151491d2"),
    ("N_NONKNOWN_AMOUNT", "a6eff26b8dca90e1c420c92d60389b2c912652d19987798949e846c4fc20fb98"),
    ("U1", "abec385afc525bfa70c0b1e4627bb451c9dc73522ba41e86327e8fadc4356288"),
)
NATIVE_CODE_PINS = (
    (
        "src/pit_research_lab/__init__.py",
        "8121e022e7de092b4c79651137a4ccd89cd450ba910d65bb507b15781a52a5ff",
        79,
    ),
    (
        "src/pit_research_lab/domain/__init__.py",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        0,
    ),
    (
        "src/pit_research_lab/domain/contracts.py",
        "d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac",
        24933,
    ),
    (
        "src/pit_research_lab/domain/information.py",
        "fc1ed60a5fb3066553a18322f69df195429f7e83bd6dba774cb201d0f5c216d7",
        42942,
    ),
    (
        "src/pit_research_lab/domain/temporal.py",
        "09dfd6108c5ba2e117fb61ab4b9ce9254d342d1bf26fcfbf16d221b1d3f25dc7",
        18274,
    ),
    (
        "src/pit_research_lab/domain/pit_slice.py",
        "ab7ba2843035811e35e66f1a22eca51bc6d1b20d07248bb4f6097a76e898cc53",
        4029,
    ),
)


class W02Stage(StrEnum):
    S01_PACK = "S01_PACK"
    S02_TICK = "S02_TICK"
    S03_IDENTITY = "S03_IDENTITY"
    S04_EVIDENCE = "S04_EVIDENCE"
    S05_TYPED_EVIDENCE = "S05_TYPED_EVIDENCE"
    S06_OBSERVATION = "S06_OBSERVATION"
    S07_NATIVE_CONSTRUCTORS = "S07_NATIVE_CONSTRUCTORS"
    S08_NATIVE_INVOCATION = "S08_NATIVE_INVOCATION"
    S09_POST_OBSERVATION = "S09_POST_OBSERVATION"


class W02AdapterReason(StrEnum):
    PACK_INVALID = "PROPOSED_W02_PACK_INVALID"
    TICK_INVALID = "PROPOSED_W02_TICK_INVALID"
    TICK_NOT_MEMBER = "PROPOSED_W02_TICK_NOT_MEMBER"
    CUTOFF_IDENTITY_MISMATCH = "PROPOSED_W02_CUTOFF_IDENTITY_MISMATCH"
    SOURCE_IDENTITY_MISMATCH = "PROPOSED_W02_SOURCE_IDENTITY_MISMATCH"
    EVIDENCE_IDENTITY_MISMATCH = "PROPOSED_W02_EVIDENCE_IDENTITY_MISMATCH"
    EVIDENCE_SCHEMA_UNSUPPORTED = "PROPOSED_W02_EVIDENCE_SCHEMA_UNSUPPORTED"
    AMOUNT_NOT_KNOWN = "PROPOSED_W02_AMOUNT_NOT_KNOWN"
    EVIDENCE_MISSING = "PROPOSED_W02_EVIDENCE_MISSING"
    EVIDENCE_NOT_ADOPTED = "PROPOSED_W02_EVIDENCE_NOT_ADOPTED"
    RAW_PIN_INVALID = "PROPOSED_W02_RAW_PIN_INVALID"
    MEMBERSHIP_INVALID = "PROPOSED_W02_MEMBERSHIP_INVALID"
    SOURCE_RECORDS_INVALID = "PROPOSED_W02_SOURCE_RECORDS_INVALID"
    PROOF_SCOPE_UNAPPROVED = "PROPOSED_W02_PROOF_SCOPE_UNAPPROVED"
    PROOF_INVALID = "PROPOSED_W02_PROOF_INVALID"
    CONTEXT_PROFILE_INVALID = "PROPOSED_W02_CONTEXT_PROFILE_INVALID"
    OBSERVATION_UNAVAILABLE = "PROPOSED_W02_OBSERVATION_UNAVAILABLE"
    OBSERVATION_SCOPE_INVALID = "PROPOSED_W02_OBSERVATION_SCOPE_INVALID"
    OBSERVATION_PIN_MISMATCH = "PROPOSED_W02_OBSERVATION_PIN_MISMATCH"
    NATIVE_CONSTRUCTOR_REJECTED = "PROPOSED_W02_NATIVE_CONSTRUCTOR_REJECTED"
    NATIVE_INVOCATION_REJECTED = "PROPOSED_W02_NATIVE_INVOCATION_REJECTED"
    OBSERVATION_CHANGED = "PROPOSED_W02_OBSERVATION_CHANGED"


# This ordered data is also the priority within a validation stage.
REASON_PRIORITY = (
    (W02Stage.S01_PACK, (W02AdapterReason.PACK_INVALID,)),
    (W02Stage.S02_TICK, (W02AdapterReason.TICK_INVALID, W02AdapterReason.TICK_NOT_MEMBER)),
    (
        W02Stage.S03_IDENTITY,
        (
            W02AdapterReason.CUTOFF_IDENTITY_MISMATCH,
            W02AdapterReason.SOURCE_IDENTITY_MISMATCH,
            W02AdapterReason.EVIDENCE_IDENTITY_MISMATCH,
        ),
    ),
    (
        W02Stage.S04_EVIDENCE,
        (
            W02AdapterReason.EVIDENCE_SCHEMA_UNSUPPORTED,
            W02AdapterReason.AMOUNT_NOT_KNOWN,
            W02AdapterReason.EVIDENCE_MISSING,
            W02AdapterReason.EVIDENCE_NOT_ADOPTED,
        ),
    ),
    (
        W02Stage.S05_TYPED_EVIDENCE,
        (
            W02AdapterReason.RAW_PIN_INVALID,
            W02AdapterReason.MEMBERSHIP_INVALID,
            W02AdapterReason.SOURCE_RECORDS_INVALID,
            W02AdapterReason.PROOF_SCOPE_UNAPPROVED,
            W02AdapterReason.PROOF_INVALID,
            W02AdapterReason.CONTEXT_PROFILE_INVALID,
        ),
    ),
    (
        W02Stage.S06_OBSERVATION,
        (
            W02AdapterReason.OBSERVATION_UNAVAILABLE,
            W02AdapterReason.OBSERVATION_SCOPE_INVALID,
            W02AdapterReason.OBSERVATION_PIN_MISMATCH,
        ),
    ),
    (W02Stage.S07_NATIVE_CONSTRUCTORS, (W02AdapterReason.NATIVE_CONSTRUCTOR_REJECTED,)),
    (W02Stage.S08_NATIVE_INVOCATION, (W02AdapterReason.NATIVE_INVOCATION_REJECTED,)),
    (W02Stage.S09_POST_OBSERVATION, (W02AdapterReason.OBSERVATION_CHANGED,)),
)

type WireValue = None | bool | int | str | tuple[WireValue, ...] | WireObject


@dataclass(frozen=True, slots=True)
class WireObject:
    """Closed JSON object represented by immutable sorted pairs, never a dict boundary."""

    items: tuple[tuple[str, WireValue], ...]

    def __post_init__(self) -> None:
        keys = tuple(k for k, _ in self.items)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("Wire keys must be unique and ordered")
        for key, value in self.items:
            if type(key) is not str:
                raise ValueError("Wire key must be text")
            _check_wire(value)

    @classmethod
    def from_value(cls, value: object) -> WireObject:
        result = _freeze(value)
        if not isinstance(result, cls):
            raise ValueError("WireObject requires an object")
        return result

    def to_value(self) -> dict[str, Any]:
        return {key: _thaw(value) for key, value in self.items}


def _check_wire(value: object) -> None:
    if value is None or type(value) in (str, bool, int) or isinstance(value, WireObject):
        return
    if type(value) is tuple:
        for child in value:
            _check_wire(child)
        return
    raise ValueError("Only immutable closed JSON values cross the wire boundary")


def _freeze(value: object) -> WireValue:
    if value is None or type(value) in (str, bool, int):
        return cast(WireValue, value)
    if type(value) is dict:
        if not all(type(k) is str for k in value):
            raise ValueError("Nontext wire key")
        return WireObject(tuple((key, _freeze(v)) for key, v in sorted(value.items())))
    if type(value) in (list, tuple):
        return tuple(_freeze(v) for v in cast(list[object] | tuple[object, ...], value))
    raise ValueError("Unsupported wire value")


def _thaw(value: WireValue) -> Any:
    if isinstance(value, WireObject):
        return value.to_value()
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class FrozenNativeInput:
    content: WireObject | None
    subject: WireObject | None
    assertion: WireObject | None
    requested: WireObject | None
    event: WireObject | None
    proof: WireObject | None
    support: WireObject | None
    scope: WireObject | None

    @classmethod
    def from_record(cls, record: WireObject) -> FrozenNativeInput:
        value = record.to_value()
        request = _get(value, "request", "fields")
        attempts = _get(request, "attempts")
        binding = _get(attempts, 0, "fields", "supplied")
        return cls(
            _optional_wire(_get(request, "content")),
            _optional_wire(_get(value, "subject")),
            _optional_wire(_get(request, "assertion")),
            _optional_wire(_get(request, "requested")),
            _optional_wire(_get(request, "events", 0)),
            _optional_wire(_get(binding, "fields", "proof_candidate")),
            _optional_wire(binding),
            _optional_wire(_get(request, "scope")),
        )


def _optional_wire(value: Any) -> WireObject | None:
    return None if value is _ABSENT or value is None else WireObject.from_value(value)


@dataclass(frozen=True, slots=True)
class SourceEvent:
    # Original JSON is lossless; typed Unknown facts are retained caller-supplied
    # facts, not request constructors or qualification computed before S07.
    wire: WireObject
    unknown_facts: tuple[c.Unknown, ...] = ()


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    path: str
    classification: str
    author_ref: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class EventReplacement:
    event_index: int
    event: WireObject


@dataclass(frozen=True, slots=True)
class SourceSpecBinding:
    profile_id: str
    source_spec_sha256: str
    required_seed: int
    base_fixture_sha256: str
    exact_event_replacements: tuple[EventReplacement, ...]


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    record_id: str
    source_profile_id: str
    wu01_event_ref: str
    version_ref: str
    issuer_ref: str
    raw_notice: bytes
    raw_length: int
    raw_sha256: str
    original_event: SourceEvent
    native_fields: WireObject
    field_provenance: tuple[FieldProvenance, ...]


@dataclass(frozen=True, slots=True)
class ContextRecord:
    record_id: str
    tick_id: str
    native_fields: WireObject


@dataclass(frozen=True, slots=True)
class EvidenceAuthoringProvenance:
    classification: str
    author_ref: str
    independent_reviewer_role: str
    review_status: str


@dataclass(frozen=True, slots=True)
class EvidenceApprovalBinding:
    status: str
    owner_adoption_ref: str | None
    independent_review_ref: str | None
    approved_fixture_sha256: str | None
    approved_contract_version: str | None
    permitted_source_profile_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceAssembly:
    schema_version: str
    reference_fixture_bytes: bytes
    selected_record_id: str
    candidate_input: FrozenNativeInput
    fixture_sha256: str
    source_spec_profiles: tuple[SourceSpecBinding, ...]
    records: tuple[EvidenceRecord, ...]
    contexts: tuple[ContextRecord, ...]
    provenance: EvidenceAuthoringProvenance
    approval: EvidenceApprovalBinding


@dataclass(frozen=True, slots=True)
class CallerObservationReceipt:
    root_authorization_ref: str
    actual_root: str
    fixed_path_set: tuple[str, ...]
    before_receipt_id: str
    actual_observation_origin: str
    no_symlink_check_result: bool


@dataclass(frozen=True, slots=True)
class ObservedCodeInput:
    code: CodeObservation
    scope_receipt: CallerObservationReceipt


@dataclass(frozen=True, slots=True)
class ObservationUnavailable:
    failure_kind: Literal["ABSENT", "CALLER_SCOPE_REFUSED", "OPERATIONAL_UNAVAILABLE"]
    caller_evidence_paths: tuple[str, ...]
    safe_reason: str


@dataclass(frozen=True, slots=True)
class FailureSite:
    reason: W02AdapterReason
    stage: W02Stage
    path: str


@dataclass(frozen=True, slots=True)
class NativeOrFoundationError:
    exception_type: str
    code: str
    path: str
    attempted_operation: str


@dataclass(frozen=True, slots=True)
class W02MappingRefusal:
    contract_version: str
    reason: W02AdapterReason
    stage: W02Stage
    first_failure: FailureSite
    evidence_paths: tuple[str, ...]
    safe_detail: str
    retained_unknown_facts: tuple[c.Unknown, ...]
    upstream_error: NativeOrFoundationError | None
    native_invocation: Literal["NOT_RUN"] = field(default="NOT_RUN", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)


@dataclass(frozen=True, slots=True)
class NativeRequestAssembly:
    context: c.SemanticContext
    request: c.IssuerBindingRequest
    declared_profile: c.CandidateProfile
    code_input: ObservedCodeInput
    record_id: str
    tick_id: str
    cutoff: c.AwareInstant
    pack_payload_sha256: str
    exact_tick_bytes_sha256: str
    evidence_fixture_sha256: str
    original_wu01_context_ref: str
    original_wu01_manifest_ref: str
    original_wu01_config_ref: str
    original_wu01_calendar_ref: str
    original_unknown_facts: tuple[c.Unknown, ...]
    provenance: EvidenceAuthoringProvenance


_ABSENT = object()
_CONSTRUCTORS: dict[str, type[c.Record]] = {
    name: cls
    for name, cls in (
        ("OriginKnownValue", c.OriginKnownValue),
        ("OriginUnknownValue", c.OriginUnknownValue),
        ("FieldOrigin", c.FieldOrigin),
        ("Known", c.Known),
        ("Unknown", c.Unknown),
        ("CodePin", c.CodePin),
        ("CandidateProfile", c.CandidateProfile),
        ("AwareInstant", c.AwareInstant),
        ("TemporalPolicy", c.TemporalPolicy),
        ("SubjectFacts", c.SubjectFacts),
        ("ContentFacts", c.ContentFacts),
        ("AssertionFacts", c.AssertionFacts),
        ("RequestedTuple", c.RequestedTuple),
        ("PublicationEventFacts", c.PublicationEventFacts),
        ("TimeProof", c.TimeProof),
        ("PublicationUpperBound", c.PublicationUpperBound),
        ("UnresolvedSourceTime", c.UnresolvedSourceTime),
        ("SupportBinding", c.SupportBinding),
        ("RequestBindingAttempt", c.RequestBindingAttempt),
        ("RoleRef", c.RoleRef),
        ("ContentPin", c.ContentPin),
        ("SourceRecords", c.SourceRecords),
        ("S1Scope", c.S1Scope),
        ("IssuerBindingRequest", c.IssuerBindingRequest),
        ("SemanticContext", c.SemanticContext),
        ("NotEvaluated", c.NotEvaluated),
        ("NotApplicable", c.NotApplicable),
    )
}
_CONSTRUCTOR_ORDER = tuple(_CONSTRUCTORS)


class _ConstructorError(c.ContractError):
    def __init__(self, operation: str, original: c.ContractError) -> None:
        self.operation = operation
        self.original = original
        super().__init__(str(original))


class _NativeBuilder:
    """Only the closed Native constructor whitelist; never dynamic imports/eval."""

    def __init__(self) -> None:
        self.cache: dict[WireObject, c.Record] = {}

    def build[T: c.Record](self, value: WireObject, expected: type[T]) -> T:
        nodes: dict[str, list[WireObject]] = {}

        def collect(v: WireValue) -> None:
            if isinstance(v, WireObject):
                obj = v.to_value()
                if "native_type" in obj:
                    nodes.setdefault(obj["native_type"], []).append(v)
                for _, child in v.items:
                    collect(child)
            elif isinstance(v, tuple):
                for child in v:
                    collect(child)

        collect(value)
        for name in _CONSTRUCTOR_ORDER:
            for node in nodes.get(name, ()):
                self._decode(node)
        result = self._decode(value)
        if not isinstance(result, expected):
            raise c.ContractError("W02_NATIVE_CONSTRUCTOR_TYPE_MISMATCH")
        return result

    def _decode(self, value: WireValue) -> object:
        if isinstance(value, tuple):
            return tuple(self._decode(child) for child in value)
        if not isinstance(value, WireObject):
            return value
        obj = value.to_value()
        if obj.get("wire_type") == "bytes":
            return _decode_bytes(obj)
        if obj.get("wire_type") == "date":
            return date.fromisoformat(obj["iso8601"])
        if value in self.cache:
            return self.cache[value]
        name = obj["native_type"]
        cls = _CONSTRUCTORS[name]
        nested = dict(value.items)["fields"]
        assert isinstance(nested, WireObject)
        kwargs = {key: self._decode(child) for key, child in nested.items}
        if name in ("FieldOrigin", "RoleRef"):
            kwargs["visibility"] = c.Visibility(cast(str, kwargs["visibility"]))
        if name in ("Unknown", "OriginUnknownValue"):
            kwargs["cause"] = c.UnknownCause(cast(str, kwargs["cause"]))
        try:
            result = cast(Callable[..., c.Record], cls)(**kwargs)
        except c.ContractError as error:
            raise _ConstructorError(name, error) from error
        self.cache[value] = result
        return result


def _get(value: Any, *keys: str | int) -> Any:
    for key in keys:
        if isinstance(key, str) and isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(key, int) and isinstance(value, (list, tuple)) and 0 <= key < len(value):
            value = value[key]
        else:
            return _ABSENT
    return value


def _value(value: WireObject | None) -> Any:
    return _ABSENT if value is None else value.to_value()


def _known(value: Any) -> Any:
    if _get(value, "native_type") == "Known":
        return _get(value, "fields", "value")
    return _ABSENT


def _unknowns(evidence: EvidenceAssembly) -> tuple[c.Unknown, ...]:
    if not isinstance(evidence, EvidenceAssembly):
        return ()
    return tuple(
        fact for record in evidence.records for fact in record.original_event.unknown_facts
    )


def _refusal(
    evidence: EvidenceAssembly,
    stage: W02Stage,
    reason: W02AdapterReason,
    paths: tuple[str, ...],
    detail: str = "",
    upstream: NativeOrFoundationError | None = None,
) -> W02MappingRefusal:
    ordered = tuple(sorted(set(paths)))
    assert ordered
    return W02MappingRefusal(
        CONTRACT_VERSION,
        reason,
        stage,
        FailureSite(reason, stage, ordered[0]),
        ordered,
        detail or reason.value,
        _unknowns(evidence),
        upstream,
    )


def _upstream(error: InputError) -> NativeOrFoundationError:
    return NativeOrFoundationError("InputError", error.code, error.path, "WU01_INPUT_VALIDATION")


def _strict_json(body: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_number(_: str) -> Any:
        raise ValueError("Noninteger JSON number")

    return json.loads(
        body, object_pairs_hook=pairs, parse_float=invalid_number, parse_constant=invalid_number
    )


def _decode_bytes(obj: dict[str, Any]) -> bytes:
    if set(obj) != {"wire_type", "encoding", "source_encoding", "base64", "byte_len", "sha256"}:
        raise ValueError("Byte wire keys")
    if (
        obj["wire_type"] != "bytes"
        or obj["encoding"] != "base64"
        or obj["source_encoding"] != "UTF-8"
    ):
        raise ValueError("Byte wire encoding")
    body = base64.b64decode(obj["base64"], validate=True)
    if (
        type(obj["byte_len"]) is not int
        or obj["byte_len"] != len(body)
        or obj["sha256"] != sha256(body).hexdigest()
        or base64.b64encode(body).decode("ascii") != obj["base64"]
    ):
        raise ValueError("Byte wire pin")
    body.decode("utf-8")
    return body


def _schema_errors(value: Any, pointer: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        if "native_type" in value:
            name = value.get("native_type")
            if set(value) != {"native_type", "fields"} or name not in _CONSTRUCTORS:
                return [pointer]
            values = value["fields"]
            if not isinstance(values, dict):
                return [pointer + "/fields"]
            fs = tuple(f for f in fields(_CONSTRUCTORS[name]) if f.init)
            permitted = {f.name for f in fs}
            if set(values) - permitted:
                errors.append(pointer + "/fields")
            # Missing fields are S04 EVIDENCE_MISSING, not an invented earlier error.
            for key, child in values.items():
                errors.extend(_schema_errors(child, pointer + "/fields/" + key))
            return errors
        if "wire_type" in value:
            expected = (
                {"wire_type", "encoding", "source_encoding", "base64", "byte_len", "sha256"}
                if value["wire_type"] == "bytes"
                else {"wire_type", "iso8601"}
            )
            if value["wire_type"] not in ("bytes", "date") or set(value) != expected:
                return [pointer]
            return []
        return [pointer]
    if isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_schema_errors(child, pointer + "/" + str(index)))
    elif value is not None and type(value) not in (str, int, bool):
        errors.append(pointer)
    return errors


def _missing(value: Any, pointer: str) -> list[str]:
    if not isinstance(value, dict):
        return [pointer] if value is _ABSENT or value is None else []
    if value.get("native_type") not in _CONSTRUCTORS:
        return []
    values = value.get("fields", {})
    if not isinstance(values, dict):
        return []
    result = []
    for f in fields(_CONSTRUCTORS[value["native_type"]]):
        if (
            f.init
            and f.default is MISSING
            and f.default_factory is MISSING
            and (
                f.name not in values
                or (
                    values[f.name] is None
                    # Native Unknown explicitly permits absent source text. Null is
                    # still not a substitute for any required Fact/identity field.
                    and (value["native_type"], f.name) != ("Unknown", "source_text")
                )
            )
        ):
            result.append(pointer + "/fields/" + f.name)
    for key, child in values.items():
        if isinstance(child, dict):
            result.extend(_missing(child, pointer + "/fields/" + key))
        elif isinstance(child, list):
            for index, item in enumerate(child):
                result.extend(_missing(item, pointer + "/fields/" + key + "/" + str(index)))
    return result


def _identity_errors(
    event: dict[str, Any],
    reference: dict[str, Any],
    selected: EvidenceRecord,
    candidate: FrozenNativeInput,
) -> list[str]:
    errors: list[str] = []
    anchor = reference["identity_crosswalk"]
    wanted: tuple[tuple[str, Any, Any], ...] = (
        ("/record/event_ref", selected.wu01_event_ref, event["event_ref"]),
        ("/record/version_ref", selected.version_ref, event["version_ref"]),
        ("/record/issuer_ref", selected.issuer_ref, event["issuer_ref"]),
        ("/record/original_event", selected.original_event.wire.to_value(), event),
        (
            "/content/version",
            _get(_value(candidate.content), "fields", "content_version_ref"),
            event["version_ref"],
        ),
        (
            "/content/representation",
            _get(_value(candidate.content), "fields", "representation_ref"),
            event["representation_ref"],
        ),
        (
            "/content/issuer",
            _known(_get(_value(candidate.content), "fields", "issuer_ref")),
            event["issuer_ref"],
        ),
        (
            "/content/source",
            _known(_get(_value(candidate.content), "fields", "source_ref")),
            event["source_ref"],
        ),
        (
            "/assertion/assertion_ref",
            _get(_value(candidate.assertion), "fields", "assertion_ref"),
            anchor["native_assertion_ref"],
        ),
        (
            "/assertion/subject_ref",
            _get(_value(candidate.assertion), "fields", "subject_ref"),
            anchor["native_subject_ref"],
        ),
        (
            "/assertion/content_version_ref",
            _get(_value(candidate.assertion), "fields", "content_version_ref"),
            event["version_ref"],
        ),
        (
            "/assertion/source_unit",
            _known(_get(_value(candidate.assertion), "fields", "source_unit")),
            event["unit"],
        ),
        (
            "/assertion/reference_period",
            _get(_value(candidate.assertion), "fields", "reference_period"),
            [
                {"wire_type": "date", "iso8601": "2026-12-01"},
                {"wire_type": "date", "iso8601": "2026-12-31"},
            ],
        ),
        (
            "/requested/target_kind",
            _get(_value(candidate.requested), "fields", "target_kind"),
            "ASSERTION",
        ),
        (
            "/requested/target_ref",
            _get(_value(candidate.requested), "fields", "target_ref"),
            anchor["native_assertion_ref"],
        ),
        (
            "/requested/subject_scope_refs",
            _get(_value(candidate.requested), "fields", "subject_scope_refs"),
            [anchor["native_subject_ref"]],
        ),
        (
            "/requested/content_version_ref",
            _get(_value(candidate.requested), "fields", "content_version_ref"),
            event["version_ref"],
        ),
        (
            "/requested/representation_ref",
            _get(_value(candidate.requested), "fields", "representation_ref"),
            event["representation_ref"],
        ),
        (
            "/requested/fragment_selector",
            _get(_value(candidate.requested), "fields", "fragment_selector"),
            "/statements/0",
        ),
        (
            "/event/event_ref",
            _get(_value(candidate.event), "fields", "event_ref"),
            event["event_ref"],
        ),
        (
            "/event/source_ref",
            _get(_value(candidate.event), "fields", "source_ref"),
            event["source_ref"],
        ),
        (
            "/event/issuer_ref",
            _get(_value(candidate.event), "fields", "issuer_ref"),
            event["issuer_ref"],
        ),
    )
    for path, actual, expected in wanted:
        if actual is not _ABSENT and actual is not None and actual != expected:
            errors.append(path)
    if event["state"] == "KNOWN":
        amount = _known(_get(_value(candidate.assertion), "fields", "source_amount"))
        if (
            amount is not _ABSENT
            and amount is not None
            and (type(amount) is not int or amount != event["amount"])
        ):
            errors.append("/assertion/source_amount")
    subject_values = (
        ("subject_ref", anchor["native_subject_ref"], False),
        ("economic_entity_ref", event["issuer_ref"], True),
        ("metric", "monthly_revenue", True),
        ("period_kind", "DURATION", True),
        ("period_start", {"wire_type": "date", "iso8601": "2026-12-01"}, True),
        ("period_end", {"wire_type": "date", "iso8601": "2026-12-31"}, True),
        ("canonical_unit", event["unit"], True),
        ("currency", event["currency"], True),
        ("basis_ref", event["basis_ref"], True),
        ("reporting_scope", event["reporting_scope"], True),
    )
    for key, expected, wrapped in subject_values:
        actual = _get(_value(candidate.subject), "fields", key)
        actual = _known(actual) if wrapped else actual
        if actual is not _ABSENT and actual is not None and actual != expected:
            errors.append("/subject/" + key)
    return errors


def _raw_errors(
    selected: EvidenceRecord,
    reference: dict[str, Any],
    item: FrozenNativeInput,
) -> list[str]:
    errors: list[str] = []
    expected = reference["raw_notice_bytes"]
    if (
        type(selected.raw_notice) is not bytes
        or len(selected.raw_notice) != expected["byte_len"]
        or sha256(selected.raw_notice).hexdigest() != expected["sha256"]
        or selected.raw_length != expected["byte_len"]
        or selected.raw_sha256 != expected["sha256"]
    ):
        errors.append("/record/raw_notice")
    content = _get(_value(item.content), "fields")
    try:
        body = _decode_bytes(content["raw_bytes"])
    except (ValueError, binascii.Error, UnicodeError, KeyError, TypeError):
        errors.append("/content/raw_bytes")
    else:
        if (
            body != selected.raw_notice
            or type(content.get("raw_length")) is not int
            or content["raw_length"] != len(body)
            or content.get("raw_sha256") != expected["sha256"]
        ):
            errors.append("/content/raw_pin")
    actual_pins = _get(_value(item.scope), "fields", "raw_pins")
    expected_pins = _get(reference, "request", "fields", "scope", "fields", "raw_pins")
    if actual_pins != expected_pins:
        errors.append("/scope/raw_pins")
    return errors


def _membership_errors(
    selected: EvidenceRecord, reference: dict[str, Any], item: FrozenNativeInput
) -> list[str]:
    env = _get(selected.native_fields.to_value(), "source_envelope")
    members = _get(_value(item.scope), "fields", "input_members")
    if not isinstance(env, dict) or not isinstance(members, list):
        return ["/scope/input_members"]
    expected_roles = {
        "assertions",
        "subjects",
        "content_versions",
        "raw_assets",
        "supports",
        "evidence",
        "publication_events",
        "time_proofs",
    }
    if set(env) != expected_roles:
        return ["/source_envelope"]
    keys = []
    for member in members:
        values = _get(member, "fields")
        if not isinstance(values, dict) or values.get("visibility") != "ACTIVE":
            return ["/scope/input_members"]
        role, ref, pointer = (
            values.get("role"),
            values.get("object_ref"),
            values.get("envelope_pointer"),
        )
        if (
            role not in expected_roles
            or not isinstance(env[role], dict)
            or ref not in env[role]
            or not isinstance(pointer, str)
            or not pointer.startswith("/")
            or not pointer.endswith("/source_envelope/" + role)
        ):
            return ["/scope/input_members"]
        keys.append(("ACTIVE", role, ref))
    expected_keys = sorted(("ACTIVE", role, ref) for role, values in env.items() for ref in values)
    if keys != expected_keys or keys != sorted(set(keys)) or len(keys) != 8:
        return ["/scope/input_members"]
    # Roles/identities are fixed independently of challenged DTOs.
    base_keys = [
        (v["fields"]["visibility"], v["fields"]["role"], v["fields"]["object_ref"])
        for v in reference["request"]["fields"]["scope"]["fields"]["input_members"]
    ]
    if keys != base_keys:
        return ["/scope/input_members"]
    errors = []
    allowed_origins = {
        (
            v["fields"]["object_ref"],
            v["fields"]["envelope_pointer"] + "/" + v["fields"]["object_ref"],
        )
        for v in members
    }

    def check_origins(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if value.get("native_type") == "FieldOrigin":
                origin_fields = value["fields"]
                identity = (
                    _get(origin_fields, "object_id", "fields", "value"),
                    origin_fields.get("envelope_pointer"),
                )
                if (
                    identity not in allowed_origins
                    or origin_fields.get("visibility") != "ACTIVE"
                    or _get(origin_fields, "source_schema", "fields", "value")
                    != "synthetic-notice-v1"
                    or _get(origin_fields, "input_digest", "fields", "value") != selected.raw_sha256
                ):
                    errors.append(path)
            for key, child in value.items():
                check_origins(child, path + "/" + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check_origins(child, path + "/" + str(index))

    for item_field in fields(item):
        check_origins(_value(getattr(item, item_field.name)), "/" + item_field.name)
    if errors:
        return errors
    proof = _get(_value(item.proof), "fields")
    origin = _get(proof, "origin", "fields")
    pm = next(v["fields"] for v in members if v["fields"]["role"] == "time_proofs")
    if (
        _get(origin, "object_id", "fields", "value") != pm["object_ref"]
        or _get(origin, "envelope_pointer") != pm["envelope_pointer"] + "/" + pm["object_ref"]
    ):
        return ["/proof/origin"]
    return []


def _source_errors(selected: EvidenceRecord, item: FrozenNativeInput) -> list[str]:
    env = _get(selected.native_fields.to_value(), "source_envelope")
    scope = _get(_value(item.scope), "fields")
    retained = _get(scope, "source_records", "fields")
    if not isinstance(env, dict) or not isinstance(retained, dict):
        return ["/scope/source_records"]
    wanted = {
        "supports": list(env["supports"].values()),
        "events": list(env["publication_events"].values()),
        "captures": [],
        "capture_edges": [],
        "input_members": scope["input_members"],
        "raw_pins": scope["raw_pins"],
    }
    errors = ["/scope/source_records/" + key for key, v in wanted.items() if retained.get(key) != v]
    if _value(item.support) not in wanted["supports"]:
        errors.append("/support/source_reference")
    if _value(item.event) not in wanted["events"]:
        errors.append("/event/source_reference")
    if _get(_value(item.support), "fields", "proof_candidate") != _value(item.proof):
        errors.append("/proof/source_reference")
    return errors


def _proof_errors(event: dict[str, Any], item: FrozenNativeInput) -> list[str]:
    proof = _get(_value(item.proof), "fields")
    stamp = _get(proof, "timestamp", "fields")
    if not isinstance(stamp, dict):
        return ["/proof/timestamp"]
    source = event["publication"].get("instant")
    if not isinstance(source, dict):
        return ["/proof/source_publication"]
    errors = []
    for key in ("source_text", "timezone_name", "offset", "precision"):
        if stamp.get(key) != source[key]:
            errors.append("/proof/timestamp/" + key)
    raw = stamp.get("source_text")
    if (
        not isinstance(raw, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00", raw) is None
        or stamp.get("timezone_name") != "Asia/Taipei"
        or stamp.get("offset") != "+08:00"
        or stamp.get("precision") != "SECOND"
    ):
        errors.append("/proof/timestamp")
    else:
        try:
            datetime.fromisoformat(raw)
        except ValueError:
            errors.append("/proof/timestamp")
    expected: dict[str, Any] = {
        key: None
        for key in (
            "proof_id",
            "target_kind",
            "target_id",
            "content_version_id",
            "fragment_selector",
            "proof_kind",
            "timestamp",
            "timezone",
            "offset",
            "precision",
            "upper_bound",
            "bound",
            "source_date",
            "unparsed_source_text",
        )
    }
    expected.update(
        proof_id=proof["proof_ref"],
        target_kind="assertion",
        target_id=proof["target_ref"],
        content_version_id=proof["content_version_ref"],
        fragment_selector=proof["fragment_selector"],
        proof_kind="exact",
        timestamp=stamp.get("source_text"),
        timezone=stamp.get("timezone_name"),
        offset=stamp.get("offset"),
        precision=stamp.get("precision"),
    )
    descriptor = proof.get("raw_descriptor")
    if not isinstance(descriptor, list) or descriptor != [
        [k, expected[k]] for k in sorted(expected)
    ]:
        errors.append("/proof/raw_descriptor")
    if stamp.get("origin") != proof.get("origin"):
        errors.append("/proof/timestamp/origin")
    return errors


def _native_wire(value: object) -> Any:
    if isinstance(value, c.Record):
        return {
            "native_type": type(value).__name__,
            "fields": {
                f.name: _native_wire(getattr(value, f.name))
                for f in fields(value)
                if f.init and f.name != "schema_version"
            },
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_native_wire(v) for v in value]
    if type(value) is date:
        return {"wire_type": "date", "iso8601": value.isoformat()}
    return value


def _bindings_match(evidence: EvidenceAssembly, fixture: dict[str, Any]) -> bool:
    if tuple(p.profile_id for p in evidence.source_spec_profiles) != tuple(p[0] for p in _PROFILES):
        return False
    negatives = fixture["input_contract"]["authored_negative_source_spec_profiles"]
    for binding, (profile_id, digest) in zip(evidence.source_spec_profiles, _PROFILES, strict=True):
        expected_replacements = (
            ()
            if profile_id == "BASE"
            else (
                EventReplacement(
                    negatives[profile_id]["event_index"],
                    WireObject.from_value(negatives[profile_id]["exact_replacement_event"]),
                ),
            )
        )
        if (
            binding.source_spec_sha256 != digest
            or binding.required_seed != 17
            or binding.base_fixture_sha256 != _FOUNDATION_SHA
            or binding.exact_event_replacements != expected_replacements
        ):
            return False
    return True


def _context_errors(
    reference: dict[str, Any],
    context: ContextRecord,
    expected_context: dict[str, Any],
    item: FrozenNativeInput,
    declared: c.CandidateProfile,
    evidence: EvidenceAssembly,
    fixture: dict[str, Any],
    selected: EvidenceRecord,
) -> list[str]:
    errors = []
    if context.native_fields.to_value() != expected_context:
        errors.append("/context")
    if selected.native_fields.to_value() != reference:
        errors.append("/record/native_fields")
    # Positive exact-publication records have no unknown source amount/time. An
    # arbitrary caller-added Unknown cannot smuggle unrelated facts into output.
    if selected.original_event.unknown_facts:
        errors.append("/record/original_event/unknown_facts")
    if (
        not isinstance(declared, c.CandidateProfile)
        or _native_wire(declared) != fixture["declared_profile"]
    ):
        errors.append("/declared_profile")
    original = FrozenNativeInput.from_record(WireObject.from_value(reference))
    for f in fields(original):
        if getattr(original, f.name) != getattr(item, f.name):
            # Earlier stages own all substantive raw/source/proof/identity errors.
            # This final full byte-bound check denies any unreviewed positive DTO.
            errors.append("/candidate_input/" + f.name)
    provenance = evidence.provenance
    if (
        provenance.classification != "SYNTHETIC_AUTHORED_FOR_W02"
        or provenance.author_ref != fixture["authorship"]["author_ref"]
    ):
        errors.append("/provenance")
    return errors


def _observation_reason(
    observed: ObservedCodeInput | ObservationUnavailable,
) -> W02AdapterReason | None:
    if isinstance(observed, ObservationUnavailable):
        return (
            W02AdapterReason.OBSERVATION_SCOPE_INVALID
            if observed.failure_kind == "CALLER_SCOPE_REFUSED"
            else W02AdapterReason.OBSERVATION_UNAVAILABLE
        )
    if not isinstance(observed, ObservedCodeInput) or not isinstance(
        observed.code, CodeObservation
    ):
        return W02AdapterReason.OBSERVATION_SCOPE_INVALID
    receipt, code = observed.scope_receipt, observed.code
    if (
        receipt.root_authorization_ref != _TASK
        or _MODULE_CHECKOUT_ROOT is None
        or receipt.actual_root != _MODULE_CHECKOUT_ROOT
        or receipt.fixed_path_set != tuple(p[0] for p in NATIVE_CODE_PINS)
        or not receipt.before_receipt_id
        or receipt.actual_observation_origin != "pit_slice.observe_code"
        or receipt.no_symlink_check_result is not True
        or code.interpretation != "OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION"
        or re.fullmatch("[0-9a-f]{40}", code.head) is None
        or re.fullmatch("[0-9a-f]{40}", code.head_tree) is None
    ):
        return W02AdapterReason.OBSERVATION_SCOPE_INVALID
    permitted = {
        "src/pit_research_lab/mvp/f2/native_requests.py",
        "src/pit_research_lab/mvp/f2/temporal_qualification.py",
        "tests/unit/mvp_f2/test_temporal_asof.py",
        "tests/unit/mvp_f2/data/temporal_qualification_evidence_v0.1.json",
    }
    for line in code.worktree_status.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or parts[1] not in permitted or parts[0] not in ("??", "M", "A"):
            return W02AdapterReason.OBSERVATION_SCOPE_INVALID
    actual = tuple((p.path, p.sha256) for p in code.observed_working_files)
    if actual != tuple((p[0], p[1]) for p in NATIVE_CODE_PINS):
        return W02AdapterReason.OBSERVATION_PIN_MISMATCH
    if code.byte_lengths != tuple(p[2] for p in NATIVE_CODE_PINS):
        return W02AdapterReason.OBSERVATION_PIN_MISMATCH
    return None


def _collect_unknowns(value: object) -> tuple[c.Unknown, ...]:
    result: list[c.Unknown] = []

    def visit(v: object) -> None:
        if isinstance(v, c.Unknown):
            if v not in result:
                result.append(v)
        elif isinstance(v, c.Record):
            for f in fields(v):
                visit(getattr(v, f.name))
        elif isinstance(v, tuple):
            for child in v:
                visit(child)

    visit(value)
    return tuple(result)


def prepare_native_request(
    pinned_pack: SyntheticInputPack,
    exact_tick_request_bytes: bytes,
    evidence_assembly: EvidenceAssembly,
    declared_profile: c.CandidateProfile,
    actual_code_observation: ObservedCodeInput | ObservationUnavailable,
    /,
) -> NativeRequestAssembly | W02MappingRefusal:
    """Validate in the adopted S01..S07 order; never perform observation or qualification."""
    evidence = evidence_assembly
    try:
        verify_input_pack(pinned_pack)
    except InputError as error:
        return _refusal(
            evidence,
            W02Stage.S01_PACK,
            W02AdapterReason.PACK_INVALID,
            ("/pinned_pack" + ("/" + error.path if error.path else ""),),
            upstream=_upstream(error),
        )
    try:
        request_data = decode_input_bytes(exact_tick_request_bytes)
        canonical = serialize_tick_request(request_data)
    except InputError as error:
        return _refusal(
            evidence,
            W02Stage.S02_TICK,
            W02AdapterReason.TICK_INVALID,
            ("/tick_request" + ("/" + error.path if error.path else ""),),
            upstream=_upstream(error),
        )
    if canonical != exact_tick_request_bytes:
        return _refusal(
            evidence, W02Stage.S02_TICK, W02AdapterReason.TICK_INVALID, ("/tick_request/encoding",)
        )
    schedule = build_weekly_requests(pinned_pack)
    matches = [
        (i, raw)
        for i, raw in enumerate(schedule.requests)
        if decode_input_bytes(raw)["tick_id"] == request_data["tick_id"]
    ]
    if len(matches) != 1:
        return _refusal(
            evidence,
            W02Stage.S02_TICK,
            W02AdapterReason.TICK_NOT_MEMBER,
            ("/tick_request/tick_id",),
        )
    index, original_tick = matches[0]
    if original_tick != exact_tick_request_bytes:
        return _refusal(
            evidence,
            W02Stage.S03_IDENTITY,
            W02AdapterReason.CUTOFF_IDENTITY_MISMATCH,
            ("/tick_request",),
        )
    payload = pinned_pack.source_payload()
    spec = payload["input_spec"]
    source_digest = sha256(input_bytes(spec)).hexdigest()
    source_ids = [
        name for name, digest in _PROFILES if digest == source_digest and payload["seed"] == 17
    ]
    if not source_ids:
        return _refusal(
            evidence,
            W02Stage.S03_IDENTITY,
            W02AdapterReason.SOURCE_IDENTITY_MISMATCH,
            ("/pinned_pack/input_spec",),
        )
    profile_id = source_ids[0]
    if not isinstance(evidence, EvidenceAssembly):
        return _refusal(
            evidence,
            W02Stage.S04_EVIDENCE,
            W02AdapterReason.EVIDENCE_SCHEMA_UNSUPPORTED,
            ("/evidence_assembly",),
        )
    try:
        fixture = _strict_json(evidence.reference_fixture_bytes)
    except (ValueError, UnicodeError):
        return _refusal(
            evidence,
            W02Stage.S04_EVIDENCE,
            W02AdapterReason.EVIDENCE_SCHEMA_UNSUPPORTED,
            ("/reference_fixture_bytes",),
        )
    if not isinstance(fixture, dict):
        return _refusal(
            evidence,
            W02Stage.S04_EVIDENCE,
            W02AdapterReason.EVIDENCE_SCHEMA_UNSUPPORTED,
            ("/reference_fixture_bytes",),
        )
    rid = evidence.selected_record_id
    if rid not in ("R1", "R2", "R3", "R4"):
        return _refusal(
            evidence,
            W02Stage.S03_IDENTITY,
            W02AdapterReason.EVIDENCE_IDENTITY_MISMATCH,
            ("/selected_record_id",),
        )
    records = [r for r in evidence.records if r.record_id == rid]
    selected = records[0] if len(records) == 1 else None
    reference = _get(fixture, "records", rid)
    if selected is not None and isinstance(reference, dict):
        event_index = ("R1", "R2", "R3", "R4").index(rid)
        event = spec["revenue_events"][event_index]
        if selected.source_profile_id != profile_id:
            return _refusal(
                evidence,
                W02Stage.S03_IDENTITY,
                W02AdapterReason.SOURCE_IDENTITY_MISMATCH,
                ("/record/source_profile_id",),
            )
        identity_errors = _identity_errors(event, reference, selected, evidence.candidate_input)
        if identity_errors:
            return _refusal(
                evidence,
                W02Stage.S03_IDENTITY,
                W02AdapterReason.EVIDENCE_IDENTITY_MISMATCH,
                tuple(identity_errors),
            )
    else:
        event = spec["revenue_events"][("R1", "R2", "R3", "R4").index(rid)]
    item = evidence.candidate_input
    expected_kinds = {
        "content": ("ContentFacts",),
        "subject": ("SubjectFacts",),
        "assertion": ("AssertionFacts",),
        "requested": ("RequestedTuple",),
        "event": ("PublicationEventFacts",),
        "proof": ("TimeProof", "PublicationUpperBound", "UnresolvedSourceTime"),
        "support": ("SupportBinding",),
        "scope": ("S1Scope",),
    }
    schema_errors = []
    if evidence.schema_version != SCHEMA_VERSION:
        schema_errors.append("/evidence_assembly/schema_version")
    for f in fields(item):
        v = _value(getattr(item, f.name))
        if v is _ABSENT:
            continue
        if _get(v, "native_type") not in expected_kinds[f.name]:
            schema_errors.append("/" + f.name)
        schema_errors.extend(_schema_errors(v, "/" + f.name))
    if schema_errors:
        return _refusal(
            evidence,
            W02Stage.S04_EVIDENCE,
            W02AdapterReason.EVIDENCE_SCHEMA_UNSUPPORTED,
            tuple(schema_errors),
        )
    if event["state"] != "KNOWN":
        return _refusal(
            evidence,
            W02Stage.S04_EVIDENCE,
            W02AdapterReason.AMOUNT_NOT_KNOWN,
            ("/source_event/state",),
        )
    missing = []
    if selected is None:
        missing.append("/records/" + rid)
    if not isinstance(reference, dict):
        missing.append("/reference/records/" + rid)
    tick_name = "t" + str(index + 1)
    contexts = [
        ctx for ctx in evidence.contexts if ctx.record_id == rid and ctx.tick_id == tick_name
    ]
    if len(contexts) != 1:
        missing.append("/contexts/" + rid + "/" + tick_name)
    else:
        missing.extend(_missing(contexts[0].native_fields.to_value(), "/context"))
    for f in fields(item):
        missing.extend(_missing(_value(getattr(item, f.name)), "/" + f.name))
    if _get(_value(item.scope), "fields", "source_records", "native_type") != "SourceRecords":
        missing.append("/scope/source_records")
    if missing:
        return _refusal(
            evidence, W02Stage.S04_EVIDENCE, W02AdapterReason.EVIDENCE_MISSING, tuple(missing)
        )
    approval = evidence.approval
    actual_fixture = sha256(evidence.reference_fixture_bytes).hexdigest()
    binding = next((p for p in evidence.source_spec_profiles if p.profile_id == profile_id), None)
    if (
        actual_fixture != ADOPTED_FIXTURE_SHA256
        or evidence.fixture_sha256 != actual_fixture
        or approval.approved_fixture_sha256 != actual_fixture
        or approval.approved_contract_version != CONTRACT_VERSION
        or approval.status != "OWNER_ADOPTED_FOR_W02_S1S2"
        or approval.owner_adoption_ref != _TASK
        or not approval.independent_review_ref
        or approval.permitted_source_profile_ids != tuple(p[0] for p in _PROFILES)
        or binding is None
        or binding.source_spec_sha256 != source_digest
        or binding.required_seed != 17
        or binding.base_fixture_sha256 != _FOUNDATION_SHA
        or not _bindings_match(evidence, fixture)
    ):
        return _refusal(
            evidence,
            W02Stage.S04_EVIDENCE,
            W02AdapterReason.EVIDENCE_NOT_ADOPTED,
            ("/evidence_approval",),
        )
    # Native retained source data is explicit input, independent of candidate_input.
    # Its raw notice and final complete request must be the adopted fixed positive;
    # altered controls may reach only their prescribed earlier refusal stage.
    assert selected is not None and isinstance(reference, dict)
    checks: tuple[tuple[W02AdapterReason, Callable[[], list[str]]], ...] = (
        (W02AdapterReason.RAW_PIN_INVALID, lambda: _raw_errors(selected, reference, item)),
        (
            W02AdapterReason.MEMBERSHIP_INVALID,
            lambda: _membership_errors(selected, reference, item),
        ),
        (W02AdapterReason.SOURCE_RECORDS_INVALID, lambda: _source_errors(selected, item)),
    )
    for reason, check in checks:
        errors = check()
        if errors:
            return _refusal(evidence, W02Stage.S05_TYPED_EVIDENCE, reason, tuple(errors))
    if (
        _get(_value(item.proof), "native_type") != "TimeProof"
        or _get(_value(item.proof), "fields", "proof_kind") != "exact"
        or event["publication"]["state"] != "KNOWN"
    ):
        return _refusal(
            evidence,
            W02Stage.S05_TYPED_EVIDENCE,
            W02AdapterReason.PROOF_SCOPE_UNAPPROVED,
            ("/proof/proof_kind",),
        )
    proof_errors = _proof_errors(event, item)
    if proof_errors:
        return _refusal(
            evidence,
            W02Stage.S05_TYPED_EVIDENCE,
            W02AdapterReason.PROOF_INVALID,
            tuple(proof_errors),
        )
    context = contexts[0]
    expected_context = fixture["native_contexts"][rid][tick_name]
    context_errors = _context_errors(
        reference, context, expected_context, item, declared_profile, evidence, fixture, selected
    )
    if context_errors:
        return _refusal(
            evidence,
            W02Stage.S05_TYPED_EVIDENCE,
            W02AdapterReason.CONTEXT_PROFILE_INVALID,
            tuple(context_errors),
        )
    observation_failure = _observation_reason(actual_code_observation)
    if observation_failure is not None:
        return _refusal(
            evidence, W02Stage.S06_OBSERVATION, observation_failure, ("/actual_code_observation",)
        )
    assert isinstance(actual_code_observation, ObservedCodeInput)
    # S07 is the only request/context construction phase. There is no qualification
    # in this mapper; the Native owner executes later via invoke_s1s2.
    assert all(getattr(item, f.name) is not None for f in fields(item))
    try:
        builder = _NativeBuilder()
        builder.build(WireObject.from_value(fixture["declared_profile"]), c.CandidateProfile)
        builder.build(
            WireObject.from_value(expected_context["fields"]["information_cutoff"]), c.AwareInstant
        )
        builder.build(
            WireObject.from_value(expected_context["fields"]["temporal_rule"]), c.TemporalPolicy
        )
        builder.build(cast(WireObject, item.subject), c.SubjectFacts)
        builder.build(cast(WireObject, item.content), c.ContentFacts)
        builder.build(cast(WireObject, item.assertion), c.AssertionFacts)
        builder.build(cast(WireObject, item.requested), c.RequestedTuple)
        builder.build(cast(WireObject, item.event), c.PublicationEventFacts)
        builder.build(cast(WireObject, item.support), c.SupportBinding)
        builder.build(
            WireObject.from_value(reference["request"]["fields"]["attempts"][0]),
            c.RequestBindingAttempt,
        )
        builder.build(cast(WireObject, item.scope), c.S1Scope)
        request = builder.build(WireObject.from_value(reference["request"]), c.IssuerBindingRequest)
        native_context = builder.build(context.native_fields, c.SemanticContext)
    except c.ContractError as error:
        operation = (
            error.operation if isinstance(error, _ConstructorError) else "W02_REQUEST_ASSEMBLY"
        )
        original = error.original if isinstance(error, _ConstructorError) else error
        return _refusal(
            evidence,
            W02Stage.S07_NATIVE_CONSTRUCTORS,
            W02AdapterReason.NATIVE_CONSTRUCTOR_REJECTED,
            ("/native_constructors/" + operation,),
            upstream=NativeOrFoundationError(
                type(original).__name__,
                str(original),
                "/native_constructors/" + operation,
                operation,
            ),
        )
    unknowns = tuple(
        dict.fromkeys(
            (*_unknowns(evidence), *_collect_unknowns(request), *_collect_unknowns(native_context))
        )
    )
    return NativeRequestAssembly(
        native_context,
        request,
        declared_profile,
        actual_code_observation,
        rid,
        request_data["tick_id"],
        native_context.information_cutoff,
        pinned_pack.payload_sha256,
        sha256(exact_tick_request_bytes).hexdigest(),
        actual_fixture,
        request_data["context_ref"],
        request_data["manifest_ref"],
        request_data["config_ref"],
        request_data["calendar_ref"],
        unknowns,
        evidence.provenance,
    )
