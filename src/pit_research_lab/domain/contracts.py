"""Candidate S1 engineering contracts; no acceptance authority or temporal evaluator."""

from dataclasses import dataclass, fields
from dataclasses import field as data_field
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal

type Id = str
SCHEMA = "wu01-contract-v0.1-CANDIDATE"


class ContractError(ValueError):
    """Safe, finite structural diagnostic, separate from research reasons."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def identifier(value: str) -> None:
    require(type(value) is str and bool(value), "INVALID_IDENTIFIER")
    require(all(32 <= ord(c) <= 126 for c in value), "INVALID_IDENTIFIER")


def int64(value: int) -> None:
    require(type(value) is int, "INVALID_NUMERIC_TYPE")
    require(-(2**63) <= value < 2**63, "NUMERIC_RANGE")


def digest(value: str) -> None:
    require(type(value) is str and len(value) == 64, "INVALID_DIGEST")
    require(all(c in "0123456789abcdef" for c in value), "INVALID_DIGEST")


def _immutable(value: object) -> None:
    if value is None or type(value) in (str, int, bool, bytes, date, datetime):
        return
    if isinstance(value, StrEnum):
        return
    if isinstance(value, tuple):
        for child in value:
            _immutable(child)
        return
    if isinstance(value, Record):
        for field in fields(value):
            _immutable(getattr(value, field.name))
        return
    raise ContractError("MUTABLE_OR_UNSUPPORTED_VALUE")


@dataclass(frozen=True, kw_only=True)
class Record:
    schema_version: str = SCHEMA

    def __post_init__(self) -> None:
        require(self.schema_version == SCHEMA, "UNSUPPORTED_CONTRACT")
        for field in fields(self):
            if field.name == "origin":
                require(isinstance(getattr(self, field.name), FieldOrigin), "MISSING_ORIGIN")
            _immutable(getattr(self, field.name))


class Visibility(StrEnum):
    ACTIVE = "ACTIVE"
    AUXILIARY = "AUXILIARY"
    DEPENDENCY = "DEPENDENCY"
    AUDIT = "AUDIT"
    CALLER = "CALLER"


class UnknownCause(StrEnum):
    ABSENT_SOURCE_FIELD = "ABSENT_SOURCE_FIELD"
    EXPLICIT_SOURCE_UNKNOWN = "EXPLICIT_SOURCE_UNKNOWN"
    AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"
    UNMAPPED = "UNMAPPED"


@dataclass(frozen=True)
class OriginKnownValue[T](Record):
    value: T


@dataclass(frozen=True)
class OriginUnknownValue(Record):
    cause: UnknownCause


type OriginLeaf = OriginKnownValue[str] | OriginUnknownValue


@dataclass(frozen=True)
class FieldOrigin(Record):
    visibility: Visibility
    envelope_pointer: str
    object_id: OriginLeaf
    source_schema: OriginLeaf
    input_digest: OriginLeaf

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.visibility, Visibility), "INVALID_VISIBILITY")
        require(self.envelope_pointer.startswith("/"), "INVALID_ORIGIN_POINTER")
        for leaf in (self.object_id, self.source_schema, self.input_digest):
            require(isinstance(leaf, (OriginKnownValue, OriginUnknownValue)), "INVALID_ORIGIN")
        if isinstance(self.input_digest, OriginKnownValue):
            digest(self.input_digest.value)


@dataclass(frozen=True)
class Known[T](Record):
    value: T
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.value is not None, "INVALID_KNOWN_VALUE")
        require(isinstance(self.origin, FieldOrigin), "MISSING_ORIGIN")


@dataclass(frozen=True)
class Unknown(Record):
    cause: UnknownCause
    source_text: str | None
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.cause, UnknownCause), "INVALID_UNKNOWN_TAG")
        require(isinstance(self.origin, FieldOrigin), "MISSING_ORIGIN")


type Fact[T] = Known[T] | Unknown


@dataclass(frozen=True)
class NotApplicable(Record):
    owner: str
    reason: str


@dataclass(frozen=True)
class NotEvaluated(Record):
    owner: str
    reason: str


@dataclass(frozen=True)
class CodePin(Record):
    path: str
    sha256: str

    def __post_init__(self) -> None:
        super().__post_init__()
        identifier(self.path)
        digest(self.sha256)


@dataclass(frozen=True)
class CandidateProfile(Record):
    contract_ref: str
    mapping_ref: str
    reason_ref: str
    evaluator_ref: str
    code_pins: tuple[CodePin, ...]
    origin: FieldOrigin
    status: str = "CANDIDATE_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.status == "CANDIDATE_ENGINEERING_ONLY", "UNSUPPORTED_PROFILE")
        for value in (self.contract_ref, self.mapping_ref, self.reason_ref, self.evaluator_ref):
            identifier(value)
        require(self.contract_ref == SCHEMA, "UNSUPPORTED_PROFILE")
        require(
            (self.mapping_ref, self.reason_ref, self.evaluator_ref)
            == (
                "wu01-unit-v0.1-CANDIDATE",
                "wu01-reasons-v0.1-CANDIDATE",
                "s1-information-v0.1-CANDIDATE",
            ),
            "UNSUPPORTED_PROFILE",
        )
        require(bool(self.code_pins), "MISSING_CODE_PINS")
        require(len({p.path for p in self.code_pins}) == len(self.code_pins), "DUPLICATE_CODE_PIN")


@dataclass(frozen=True)
class AwareInstant(Record):
    source_text: str
    timezone_name: str
    offset: str
    precision: str
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            parsed = datetime.fromisoformat(self.source_text)
        except (TypeError, ValueError) as exc:
            raise ContractError("INVALID_INSTANT") from exc
        require(parsed.utcoffset() is not None, "INVALID_INSTANT")
        require(bool(self.timezone_name) and self.precision == "SECOND", "UNSUPPORTED_INSTANT")
        require(self.source_text.endswith(self.offset), "OFFSET_MISMATCH")


@dataclass(frozen=True)
class NumericContract(Record):
    numeric_ref: str = "NUM-1"
    minimum: int = -(2**63)
    maximum: int = 2**63 - 1
    unit: str = "NTD_thousands"
    allow_float: bool = False
    allow_bool: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        require(
            self.numeric_ref == "NUM-1"
            and type(self.minimum) is int
            and type(self.maximum) is int
            and self.minimum == -(2**63)
            and self.maximum == 2**63 - 1
            and self.unit == "NTD_thousands"
            and self.allow_float is False
            and self.allow_bool is False,
            "UNSUPPORTED_NUMERIC_CONTRACT",
        )


@dataclass(frozen=True)
class TemporalPolicy(Record):
    """Only the bounded public/observed evidence bases; no proxy policy."""

    policy_ref: str = "P-OBS-1"
    public_basis: str = "EVIDENCE_BOUND"
    observed_basis: str = "OBSERVED_ONLY"
    evaluator_ref: str = "s2-b01-bound-input-v0.1-CANDIDATE"


@dataclass(frozen=True)
class SemanticContext(Record):
    context_ref: Id
    information_cutoff: AwareInstant
    mode: str
    target_ref: Id
    evidence_set_ref: Id
    calendar_ref: Id
    policy_refs: tuple[Id, ...]
    numeric_ref: Id
    profile: CandidateProfile
    decision_wall_times: tuple[str, ...]
    computation_attempt_time: Fact[str]
    opaque_spec_ref: Id
    opaque_fit_refs: tuple[Id, ...]
    temporal_rule: TemporalPolicy | NotEvaluated
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.profile, CandidateProfile), "UNSUPPORTED_PROFILE")
        require(isinstance(self.information_cutoff, AwareInstant), "INVALID_INSTANT")
        require(self.mode in {"public", "prospective_observed"}, "UNSUPPORTED_CONTEXT_MODE")
        for ref in (
            self.context_ref,
            self.target_ref,
            self.evidence_set_ref,
            self.calendar_ref,
            self.numeric_ref,
            self.opaque_spec_ref,
        ):
            identifier(ref)


@dataclass(frozen=True)
class RoleRef(Record):
    visibility: Visibility
    role: str
    object_ref: Id
    envelope_pointer: str

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.visibility, Visibility), "INVALID_VISIBILITY")
        identifier(self.role)
        identifier(self.object_ref)
        require(self.envelope_pointer.startswith("/"), "INVALID_ORIGIN_POINTER")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.visibility.value, self.role, self.object_ref)


@dataclass(frozen=True)
class ContentPin(Record):
    content_version_ref: Id
    representation_ref: Id
    raw_length: int
    raw_sha256: str


@dataclass(frozen=True)
class S1Scope(Record):
    input_members: tuple[RoleRef, ...]
    raw_pins: tuple[ContentPin, ...]
    source_records: "SourceRecords | NotEvaluated" = NotEvaluated("S1", "SOURCE_RECORDS_ABSENT")

    def __post_init__(self) -> None:
        super().__post_init__()
        keys = [r.key for r in self.input_members]
        require(len(keys) == len(set(keys)), "DUPLICATE_MEMBER_IDENTITY")
        require(keys == sorted(keys), "UNORDERED_MEMBERSHIP")
        pins = [p.representation_ref for p in self.raw_pins]
        require(len(pins) == len(set(pins)), "DUPLICATE_RAW_PIN")


@dataclass(frozen=True)
class SubjectFacts(Record):
    subject_ref: Id
    economic_entity_ref: Fact[str]
    metric: Fact[str]
    period_kind: Fact[str]
    period_start: Fact[date]
    period_end: Fact[date]
    reporting_scope: Fact[str]
    basis_ref: Fact[str]
    mapping_state: str
    currency: Fact[str]
    canonical_unit: Fact[str]
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        identifier(self.subject_ref)
        for name in (
            "economic_entity_ref",
            "metric",
            "period_kind",
            "period_start",
            "period_end",
            "reporting_scope",
            "basis_ref",
            "currency",
            "canonical_unit",
        ):
            require(isinstance(getattr(self, name), (Known, Unknown)), "INVALID_FACT_TAG")
            fact = getattr(self, name)
            if isinstance(fact, Known):
                expected_type = date if name in {"period_start", "period_end"} else str
                require(type(fact.value) is expected_type, "INVALID_FACT_TYPE")
        if isinstance(self.period_start, Known) and isinstance(self.period_end, Known):
            require(self.period_start.value <= self.period_end.value, "INVALID_PERIOD")
        require(self.mapping_state in {"KNOWN", "UNMAPPED"}, "INVALID_MAPPING_STATE")


@dataclass(frozen=True)
class AssertionFacts(Record):
    assertion_ref: Id
    subject_ref: Id
    source_amount: Known[int]
    source_unit: Known[str]
    reference_period: tuple[date, date]
    content_version_ref: Id
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.source_amount, Known), "INVALID_SOURCE_AMOUNT")
        require(isinstance(self.source_unit, Known), "INVALID_SOURCE_UNIT")
        int64(self.source_amount.value)
        identifier(self.source_unit.value)
        identifier(self.assertion_ref)
        identifier(self.subject_ref)
        identifier(self.content_version_ref)
        require(
            len(self.reference_period) == 2
            and all(type(endpoint) is date for endpoint in self.reference_period),
            "INVALID_PERIOD",
        )
        require(self.reference_period[0] <= self.reference_period[1], "INVALID_PERIOD")


@dataclass(frozen=True)
class ContentFacts(Record):
    content_version_ref: Id
    representation_ref: Id
    raw_bytes: bytes
    raw_length: int
    raw_sha256: str
    source_schema: str
    source_ref: Fact[str]
    issuer_ref: Fact[str]
    provider_ref: Fact[str]
    source_locator: Fact[str]
    statement_members: tuple[Id, ...]
    report_members: tuple[Id, ...]
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(type(self.raw_bytes) is bytes and type(self.raw_length) is int, "INVALID_RAW_TYPE")
        digest(self.raw_sha256)
        require(
            len(self.raw_bytes) == self.raw_length
            and sha256(self.raw_bytes).hexdigest() == self.raw_sha256,
            "PINNED_INPUT_INVALID",
        )
        require(len(set(self.statement_members)) == len(self.statement_members), "DUPLICATE_ID")


@dataclass(frozen=True)
class RequestedTuple(Record):
    target_kind: str
    target_ref: Id
    subject_scope_refs: tuple[Id, ...]
    content_version_ref: Id
    representation_ref: Id
    fragment_selector: str | NotApplicable
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.target_kind in {"ASSERTION", "REPORT", "PROVIDER_CAPTURE"}, "INVALID_TARGET")
        require(
            len(set(self.subject_scope_refs)) == len(self.subject_scope_refs), "DUPLICATE_SCOPE"
        )


@dataclass(frozen=True)
class PublicationEventFacts(Record):
    event_ref: Id
    event_kind: str
    source_ref: Id
    issuer_ref: Id
    content_version_ref: Id
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        for value in (
            self.event_ref,
            self.event_kind,
            self.source_ref,
            self.issuer_ref,
            self.content_version_ref,
        ):
            identifier(value)


@dataclass(frozen=True)
class TimeProof(Record):
    """Exact-publication data shape only; no temporal eligibility computation."""

    proof_ref: Id
    target_kind: str
    target_ref: Id
    content_version_ref: Id
    fragment_selector: str
    timestamp: AwareInstant
    raw_descriptor: tuple[tuple[str, str | None], ...]
    origin: FieldOrigin
    proof_kind: str = "exact"


@dataclass(frozen=True)
class TemporalProofIdentity(Record):
    """Source-linked identity shared by additive A02 proof variants, not authentication."""

    proof_ref: Id
    target_kind: str
    target_ref: Id
    content_version_ref: Id
    fragment_selector: str
    raw_descriptor: tuple[tuple[str, str | None], ...]
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        for value in (self.proof_ref, self.target_ref, self.content_version_ref):
            identifier(value)
        require(self.target_kind in {"ASSERTION", "REPORT"}, "INVALID_PROOF_TARGET")


@dataclass(frozen=True)
class PublicationUpperBound(TemporalProofIdentity):
    upper_bound: AwareInstant
    closure: Literal["OPEN", "CLOSED"]
    proof_kind: Literal["upper_bound"] = data_field(default="upper_bound", init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.upper_bound, AwareInstant), "INVALID_UPPER_BOUND")
        require(self.closure in {"OPEN", "CLOSED"}, "INVALID_BOUND_CLOSURE")


@dataclass(frozen=True)
class AuthenticatedDate(TemporalProofIdentity):
    """Supplied date attestation; its name grants no source trust in this slice."""

    source_date: Fact[date]
    timezone: Fact[str]
    declared_upper_bound: AwareInstant | NotEvaluated
    closure: Literal["OPEN"] = data_field(default="OPEN", init=False)
    source_precision: Literal["DAY"] = data_field(default="DAY", init=False)
    derivation: Literal["NEXT_LOCAL_MIDNIGHT"] = data_field(
        default="NEXT_LOCAL_MIDNIGHT", init=False
    )
    proof_kind: Literal["date_with_upper_bound"] = data_field(
        default="date_with_upper_bound", init=False
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        require(isinstance(self.source_date, (Known, Unknown)), "INVALID_SOURCE_DATE")
        if isinstance(self.source_date, Known):
            require(type(self.source_date.value) is date, "INVALID_SOURCE_DATE")
        require(isinstance(self.timezone, (Known, Unknown)), "INVALID_SOURCE_ZONE")
        if isinstance(self.timezone, Known):
            identifier(self.timezone.value)
        require(
            isinstance(self.declared_upper_bound, (AwareInstant, NotEvaluated)),
            "INVALID_DECLARED_BOUND",
        )


@dataclass(frozen=True)
class UnresolvedSourceTime(TemporalProofIdentity):
    source_text: str
    timezone: Fact[str]
    offset: Fact[str]
    precision: Fact[str]
    proof_kind: Literal["unparsed_source_time"] = data_field(
        default="unparsed_source_time", init=False
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        require(type(self.source_text) is str, "INVALID_SOURCE_TIME_TEXT")
        for fact in (self.timezone, self.offset, self.precision):
            require(isinstance(fact, (Known, Unknown)), "INVALID_SOURCE_TIME_FACT")
            if isinstance(fact, Known):
                identifier(fact.value)


type TemporalProof = TimeProof | PublicationUpperBound | AuthenticatedDate | UnresolvedSourceTime
TEMPORAL_PROOF_TYPES = (TimeProof, PublicationUpperBound, AuthenticatedDate, UnresolvedSourceTime)


@dataclass(frozen=True)
class CaptureFacts(Record):
    observation_ref: Id
    representation_ref: Id
    captured_sha256: str
    completion: Fact[AwareInstant]
    precision: Fact[str]
    observation_kind: str
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        identifier(self.observation_ref)
        identifier(self.representation_ref)
        digest(self.captured_sha256)
        require(isinstance(self.completion, (Known, Unknown)), "INVALID_CAPTURE_COMPLETION")
        if isinstance(self.completion, Known):
            require(isinstance(self.completion.value, AwareInstant), "INVALID_CAPTURE_COMPLETION")


@dataclass(frozen=True)
class CaptureEdge(Record):
    edge_ref: Id
    from_observation: Id
    to_representation: Id
    edge_role: str
    origin: FieldOrigin


@dataclass(frozen=True)
class SupportBinding(Record):
    support_ref: Id
    evidence_ref: Id
    target: RequestedTuple
    attestation_scope: str
    event: PublicationEventFacts | NotApplicable
    proof_candidate: TemporalProof | NotApplicable
    origin: FieldOrigin

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.target.target_kind in {"ASSERTION", "REPORT"}, "INVALID_SUPPORT_KIND")


@dataclass(frozen=True)
class RequestBindingAttempt(Record):
    requested: RequestedTuple
    supplied: SupportBinding


@dataclass(frozen=True)
class BindingAssessment(Record):
    disposition: str
    requested: RequestedTuple
    supplied: SupportBinding
    mismatches: tuple[str, ...]


@dataclass(frozen=True)
class ExactUnitMapping(Record):
    mapping_ref: Id
    mapping_version: str
    from_unit: Id
    to_unit: Id
    numerator: int
    denominator: int
    subject_ref: Id
    applicability: tuple[tuple[str, str], ...]
    origin: FieldOrigin


@dataclass(frozen=True)
class Derivation(Record):
    rule_ref: str
    input_refs: tuple[Id, ...]
    exact_operands: tuple[int, ...]
    result: int
    origin: FieldOrigin


@dataclass(frozen=True)
class ExactAmount(Record):
    source_amount: int
    source_unit: Id
    canonical_amount: int
    canonical_unit: Id
    mapping_ref: Id
    derivation: Derivation


@dataclass(frozen=True)
class SubjectOperand(Record):
    subject: SubjectFacts
    assertion: AssertionFacts | NotApplicable
    contents: tuple[ContentFacts, ...]
    supports: tuple[SupportBinding, ...]
    events: tuple[PublicationEventFacts, ...]
    captures: tuple[CaptureFacts, ...]


@dataclass(frozen=True)
class SubjectComparisonRequest(Record):
    left: SubjectOperand
    right: SubjectOperand
    unit_mapping: ExactUnitMapping | NotApplicable
    numeric: NumericContract
    scope: S1Scope


@dataclass(frozen=True)
class IssuerBindingRequest(Record):
    requested: RequestedTuple
    content: ContentFacts
    assertion: AssertionFacts
    attempts: tuple[RequestBindingAttempt, ...]
    captures: tuple[CaptureFacts, ...]
    events: tuple[PublicationEventFacts, ...]
    scope: S1Scope


@dataclass(frozen=True)
class ProviderCaptureRequest(Record):
    requested: RequestedTuple
    content: ContentFacts
    capture: CaptureFacts
    capture_edges: tuple[CaptureEdge, ...]
    subject_reference: Fact[str]
    displayed_value: Known[int]
    source_unit: Known[str]
    scope: S1Scope


@dataclass(frozen=True)
class ContentInventoryRequest(Record):
    requested: RequestedTuple
    content: ContentFacts
    captures: tuple[CaptureFacts, ...]
    events: tuple[PublicationEventFacts, ...]
    supports: tuple[SupportBinding, ...]
    scope: S1Scope


@dataclass(frozen=True)
class SourceRecords(Record):
    """Immutable input-side projection, built before challenged request DTOs.

    The bounded adapter resolves actual evidence records into support tuples.
    These retained tuples and content pins are integrity references, not external
    authentication or protection against replacement of the entire input corpus.
    """

    input_members: tuple[RoleRef, ...]
    raw_pins: tuple[ContentPin, ...]
    supports: tuple[SupportBinding, ...]
    captures: tuple[CaptureFacts, ...]
    events: tuple[PublicationEventFacts, ...]
    capture_edges: tuple[CaptureEdge, ...]
    descriptor_ref: str = data_field(default="b01-source-records-v1", init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        for values, role in (
            (self.supports, "support_ref"),
            (self.captures, "observation_ref"),
            (self.events, "event_ref"),
            (self.capture_edges, "edge_ref"),
        ):
            keys = [(v.origin.visibility, getattr(v, role)) for v in values]
            require(len(keys) == len(set(keys)), "DUPLICATE_SOURCE_RECORD")


@dataclass(frozen=True)
class ScopedPath(Record):
    target: RequestedTuple
    evidence_ref: str | NotApplicable
    support_ref: str | NotApplicable
    event_ref: str | NotApplicable
    time_proof_ref: str | NotApplicable
    visibility: Visibility
    path_role: str
    origin: FieldOrigin


@dataclass(frozen=True)
class CompleteScopedProvenance(Record):
    input_members: tuple[RoleRef, ...]
    accepted_paths: tuple[ScopedPath, ...]
    rejected_attempts: tuple[BindingAssessment, ...]
    excluded_uses: tuple[RoleRef, ...]
    not_evaluated: tuple[NotEvaluated, ...]
    derived_facts: tuple[Derivation, ...]


@dataclass(frozen=True)
class DimensionComparison(Record):
    dimension: str
    left: Fact[str] | Fact[date]
    right: Fact[str] | Fact[date]
    relation: str


@dataclass(frozen=True)
class IdentityOutcome(Record):
    state: str
    reason: str
    context_ref: Id
    left_subject_ref: Id
    right_subject_ref: Id
    assertion_refs: tuple[Id, ...]
    content_version_refs: tuple[Id, ...]
    compared_dimensions: tuple[DimensionComparison, ...]
    source_assertions: tuple[AssertionFacts, ...]
    publication_event_facts: tuple[PublicationEventFacts, ...]
    canonical_amount: Known[int] | NotEvaluated
    mapping_ref: Known[str] | NotApplicable
    provenance: CompleteScopedProvenance

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.state in {"SAME", "DIFFERENT", "UNRESOLVED"}, "INVALID_IDENTITY_STATE")
        if isinstance(self.canonical_amount, Known):
            int64(self.canonical_amount.value)


@dataclass(frozen=True)
class SourceAttribution(Record):
    issuer: Fact[str]
    provider: Fact[str]
    source: Fact[str]


@dataclass(frozen=True)
class EvidenceOutcome(Record):
    state: str
    reason: str
    context_ref: Id
    requested_tuple: RequestedTuple
    source_attribution: SourceAttribution
    source_amount: Known[int] | NotEvaluated
    content_refs: tuple[Id, ...]
    supplied_bindings: tuple[SupportBinding, ...]
    assessments: tuple[BindingAssessment, ...]
    capture_facts: tuple[CaptureFacts, ...]
    publication_event_facts: tuple[PublicationEventFacts, ...]
    capture_edges: tuple[CaptureEdge, ...]
    provenance: CompleteScopedProvenance
    qualification_context: SemanticContext = data_field(kw_only=True)

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.state in {"BOUND", "UNRESOLVED"}, "INVALID_EVIDENCE_STATE")
        if isinstance(self.source_amount, Known):
            int64(self.source_amount.value)


@dataclass(frozen=True)
class BlockingFailure(Record):
    category: str
    code: str
    affected_scope: tuple[RoleRef, ...]
    safe_diagnostic: str
    origin: FieldOrigin
    attempted_operation: str


type S1Request = (
    SubjectComparisonRequest
    | IssuerBindingRequest
    | ProviderCaptureRequest
    | ContentInventoryRequest
)
type S1Outcome = IdentityOutcome | EvidenceOutcome | BlockingFailure
