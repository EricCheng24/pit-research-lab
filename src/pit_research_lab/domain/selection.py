"""Pure, bounded S3 engineering selection; no source trust or agent projection.

The A03 declaration profile encodes a directed relation proposition as a synthetic
notice assertion's metric, with unit relation_declaration and value 1. Existing S1
checks that supplied SubjectFacts describe those exact raw statement bytes; the
notice has its own S1/S2 traversal. This profile is not a real-source schema.
"""

import json
from dataclasses import dataclass, field, fields, replace
from datetime import date
from hashlib import sha256
from typing import Literal

from pit_research_lab.domain.contracts import (
    TEMPORAL_PROOF_TYPES,
    BlockingFailure,
    ContractError,
    FieldOrigin,
    IdentityOutcome,
    IssuerBindingRequest,
    Known,
    NotApplicable,
    NotEvaluated,
    NumericContract,
    OriginKnownValue,
    ProviderCaptureRequest,
    Record,
    RoleRef,
    SemanticContext,
    SubjectComparisonRequest,
    SubjectFacts,
    SubjectOperand,
    TemporalProof,
    Unknown,
    Visibility,
    require,
)
from pit_research_lab.domain.information import compare_subjects
from pit_research_lab.domain.pit_slice import CodeObservation, SliceResult, evaluate_slice

EVALUATOR_REF = "s3-a03-direct-field-v0.1-CANDIDATE"
B02_EVALUATOR_REF = "s3-b02-scoped-linear-v0.1-CANDIDATE"
B02_POLICY_VERSION = "b02-policy-v0.1"
MAX_CANDIDATES = 32
MAX_NOTICES = 32
MAX_LEADS_EXCLUSIONS = 32
MAX_EFFECTIVE_DECLARATIONS = 2
REQUIRED_CHECKS = ("CANDIDATE_DISCOVERY", "RELATION_REVIEW", "MATERIALITY_REVIEW")
S3_CODE_PATHS = (
    "src/pit_research_lab/domain/selection.py",
    "src/pit_research_lab/domain/asof_slice.py",
)
type Qualification = Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED", "AUDIT_ONLY"]
type Applicability = Literal["APPLICABLE", "SUPERSEDED", "WITHDRAWN", "NOT_QUALIFIED"]


@dataclass(frozen=True)
class HistoricalLead(Record):
    lead_ref: str
    candidate_ref: str
    scope_ref: str
    basis: Literal["CONTEMPORANEOUS_ISSUER_NOTICE", "CURRENT_PROVIDER_ONLY"]
    evidence_member: RoleRef
    origin: FieldOrigin


@dataclass(frozen=True)
class CandidateSource(Record):
    subject: SubjectFacts | NotApplicable
    request: IssuerBindingRequest | ProviderCaptureRequest
    historical_lead: HistoricalLead | NotApplicable


@dataclass(frozen=True)
class CompletedCandidate(Record):
    source: CandidateSource
    actual: SliceResult
    subject_identity: IdentityOutcome | BlockingFailure | NotApplicable

    @property
    def ref(self) -> str:
        return self.source.request.requested.target_ref


@dataclass(frozen=True)
class RevisionScope(Record):
    kind: Literal["FIELD", "DOCUMENT"]
    subject_refs: tuple[str, ...] | Unknown
    old_document_ref: str | Unknown
    new_document_ref: str | Unknown | NotApplicable
    origin: FieldOrigin


@dataclass(frozen=True)
class DirectRelation(Record):
    relation_ref: str
    kind: str
    subject_ref: str
    old_assertion_ref: str | Unknown
    old_version_ref: str | Unknown
    new_assertion_ref: str | Unknown | NotApplicable
    new_version_ref: str | Unknown | NotApplicable
    notice_assertion_ref: str
    origin: FieldOrigin
    declaration_version: str = "a03-v0.1"
    scope: RevisionScope | NotEvaluated = NotEvaluated("S3", "LEGACY_EXACT_FIELD_PROFILE")
    event_property: Literal["NONE", "RESTATEMENT"] = "NONE"


def relation_proposition(relation: DirectRelation) -> str:
    """Exact source proposition for this bounded synthetic declaration profile."""
    if relation.declaration_version == "b02-v0.1":
        scope = relation.scope
        return (
            "B02_DIRECT_RELATION:"
            + _canonical(
                (
                    relation.relation_ref,
                    relation.kind,
                    relation.subject_ref,
                    relation.old_assertion_ref,
                    relation.old_version_ref,
                    relation.new_assertion_ref,
                    relation.new_version_ref,
                    relation.notice_assertion_ref,
                    relation.event_property,
                    (scope.kind, scope.subject_refs, scope.old_document_ref, scope.new_document_ref)
                    if isinstance(scope, RevisionScope)
                    else scope,
                )
            ).decode()
        )
    return "A03_DIRECT_RELATION:" + json.dumps(
        {
            "relation_ref": relation.relation_ref,
            "kind": relation.kind,
            "subject_ref": relation.subject_ref,
            "old_assertion_ref": relation.old_assertion_ref,
            "old_version_ref": relation.old_version_ref,
            "new_assertion_ref": relation.new_assertion_ref
            if isinstance(relation.new_assertion_ref, str)
            else None,
            "new_version_ref": relation.new_version_ref
            if isinstance(relation.new_version_ref, str)
            else None,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


@dataclass(frozen=True)
class RelationSource(Record):
    relation: DirectRelation
    notice: CandidateSource | NotEvaluated


@dataclass(frozen=True)
class CompletedRelation(Record):
    relation: DirectRelation
    notice: CompletedCandidate | NotEvaluated


@dataclass(frozen=True)
class SelectionPolicy(Record):
    policy_ref: str
    version: str
    subject_ref: str
    mode: str
    target: Literal["CONTENT_VALUE", "ATTRIBUTED_ASSERTION"]
    issuer_ref: str
    source_refs: tuple[str, ...]
    provider_refs: tuple[str, ...]
    discovery_scope_ref: str
    required_checks: tuple[str, ...]
    materiality_rule: str = "GROUNDED_HISTORICAL_COMPETITOR"
    provider_rule: str = "AUDIT_CURRENT_ONLY"
    evaluator_ref: str = EVALUATOR_REF


@dataclass(frozen=True)
class CoverageCheck(Record):
    check_ref: str
    scope_ref: str
    status: Literal["COMPLETED", "NOT_PERFORMED", "FAILED"]
    evidence_refs: tuple[str, ...]
    evidence_bytes: bytes
    origin: FieldOrigin


@dataclass(frozen=True)
class BoundedCoverage(Record):
    coverage_ref: str
    context_ref: str
    evidence_set_ref: str
    policy_ref: str
    policy_version: str
    scope_ref: str
    source_refs: tuple[str, ...]
    evaluated_candidate_refs: tuple[str, ...]
    evaluated_relation_refs: tuple[str, ...]
    checks: tuple[CoverageCheck, ...]


@dataclass(frozen=True)
class LeadEvidence(Record):
    lead_ref: str
    candidate_ref: str
    subject_ref: str
    scope_ref: str
    notice: CandidateSource


def lead_proposition(lead: LeadEvidence) -> str:
    return (
        "B02_HISTORICAL_LEAD:"
        + _canonical((lead.lead_ref, lead.candidate_ref, lead.subject_ref, lead.scope_ref)).decode()
    )


@dataclass(frozen=True)
class DiscoveryExclusion(Record):
    source: CandidateSource
    reason: Literal["NOT_COMPARABLE"]


@dataclass(frozen=True)
class DiscoveryEvidence(Record):
    """Retained synthetic discovery input, independent of challenged coverage lists.

    Its pinned descriptor reconciles the supplied reference, not an authenticated
    external search or protection against wholesale replacement of the corpus.
    """

    discovery_ref: str
    context_ref: str
    evidence_set_ref: str
    policy: SelectionPolicy
    subject: SubjectFacts
    mode: str
    cutoff_text: str
    query_key: str
    window: tuple[str, str]
    candidates: tuple[CandidateSource, ...]
    relations: tuple[RelationSource, ...]
    leads: tuple[LeadEvidence, ...]
    exclusions: tuple[DiscoveryExclusion, ...]
    pages: tuple[tuple[str, ...], ...]
    terminated: bool
    checks: tuple[CoverageCheck, ...]
    raw_bytes: bytes
    origin: FieldOrigin


def _json_value(value: object) -> object:
    if isinstance(value, Record):
        return {
            "type": type(value).__name__,
            **{f.name: getattr(value, f.name) for f in fields(value)},
        }
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, date):
        return value.isoformat()
    raise ContractError("UNSUPPORTED_RECONSTRUCTION_VALUE")


def _canonical(value: object) -> bytes:
    return json.dumps(value, default=_json_value, sort_keys=True, separators=(",", ":")).encode()


def discovery_proposition(evidence: DiscoveryEvidence) -> bytes:
    """Versioned descriptor of retained inputs; excludes only its own byte/origin pin."""
    return _canonical(
        (
            "b02-synthetic-discovery-v1",
            evidence.discovery_ref,
            evidence.context_ref,
            evidence.evidence_set_ref,
            evidence.policy,
            evidence.subject,
            evidence.mode,
            evidence.cutoff_text,
            evidence.query_key,
            evidence.window,
            tuple(sorted(evidence.candidates, key=lambda c: c.request.requested.target_ref)),
            tuple(sorted(evidence.relations, key=lambda r: r.relation.relation_ref)),
            tuple(sorted(evidence.leads, key=lambda lead: lead.lead_ref)),
            tuple(sorted(evidence.exclusions, key=lambda x: x.source.request.requested.target_ref)),
            evidence.pages,
            evidence.terminated,
            tuple(sorted(evidence.checks, key=lambda c: c.check_ref)),
        )
    )


@dataclass(frozen=True)
class SelectionBundle(Record):
    context: SemanticContext
    subject: SubjectFacts
    policy: SelectionPolicy
    coverage: BoundedCoverage
    candidates: tuple[CompletedCandidate, ...]
    relations: tuple[CompletedRelation, ...]
    code: CodeObservation
    discovery: DiscoveryEvidence | NotEvaluated = NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT")


@dataclass(frozen=True)
class CandidateAssessment(Record):
    candidate_ref: str
    qualification: Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED", "AUDIT_ONLY"]
    applicability: Applicability
    reason: str
    material_unknown: bool


@dataclass(frozen=True)
class RelationAssessment(Record):
    relation_ref: str
    state: Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED"]
    reason: str
    event_support: Literal["SUPPORTED", "UNRESOLVED"] = "UNRESOLVED"
    notice_visibility: Literal["SUPPORTED", "UNRESOLVED", "NOT_ADMISSIBLE"] = "UNRESOLVED"
    relation_support: Literal["SUPPORTED", "UNRESOLVED"] = "UNRESOLVED"
    effect: Literal["SUPERSEDES", "WITHDRAWS", "REISSUES", "OUT_OF_SCOPE", "UNKNOWN", "NONE"] = (
        "NONE"
    )


@dataclass(frozen=True)
class CoverageAssessment(Record):
    state: Literal["SUFFICIENT", "INSUFFICIENT"]
    completed_checks: tuple[str, ...]
    missing_checks: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reachability(Record):
    old_assertion_ref: str
    new_assertion_ref: str
    direct_relation_path: tuple[str, ...]


@dataclass(frozen=True)
class ResearchAuditEntry(Record):
    category: str
    ref: str
    reason: str


@dataclass(frozen=True)
class SelectionOutcome(Record):
    state: Literal["SELECTED", "UNRESOLVED", "NO_QUALIFIED_CLAIM"]
    reason: str
    selected_assertion_refs: tuple[str, ...]
    selected_value: int | NotEvaluated
    candidates: tuple[CandidateAssessment, ...]
    relations: tuple[RelationAssessment, ...]
    coverage: CoverageAssessment
    research_only_audit: tuple[ResearchAuditEntry, ...]
    derived_reachability: tuple[Reachability, ...] = ()


@dataclass(frozen=True)
class AsOfSelectionResult(Record):
    inputs: SelectionBundle
    selection: SelectionOutcome | BlockingFailure
    declared_s3_evaluator_ref: str = EVALUATOR_REF
    reconstruction_ref: str | NotEvaluated = NotEvaluated("S3", "LEGACY_RECONSTRUCTION")
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)


def complete_candidate(
    context: SemanticContext, source: CandidateSource, anchor: SubjectFacts, code: CodeObservation
) -> CompletedCandidate:
    """One actual S1/S2/identity traversal for composer and untrusted direct consumers."""
    evidence = source.request
    actual = evaluate_slice(context, evidence, code)
    identity: IdentityOutcome | BlockingFailure | NotApplicable = NotApplicable(
        "S1", "PROVIDER_REFERENCE_ONLY"
    )
    if isinstance(evidence, IssuerBindingRequest):
        if not isinstance(source.subject, SubjectFacts):
            identity = BlockingFailure(
                "CONTRACT_VIOLATION",
                "MISSING_CANDIDATE_SUBJECT",
                (),
                "MISSING_CANDIDATE_SUBJECT",
                context.origin,
                "COMPARE_SUBJECTS",
            )
        else:
            na = NotApplicable("S1", "NO_UNIT_MAPPING")
            comparison = SubjectComparisonRequest(
                SubjectOperand(anchor, na, (), (), (), ()),
                SubjectOperand(
                    source.subject,
                    evidence.assertion,
                    (evidence.content,),
                    tuple(a.supplied for a in evidence.attempts),
                    evidence.events,
                    evidence.captures,
                ),
                na,
                NumericContract(),
                evidence.scope,
            )
            identity = compare_subjects(context, comparison)
    return CompletedCandidate(source, actual, identity)


def _validate_actual(
    candidate: CompletedCandidate, bundle: SelectionBundle, anchor: SubjectFacts
) -> None:
    actual, request = candidate.actual, candidate.source.request
    require(
        actual.context == bundle.context and actual.request == request, "MIXED_CONTEXT_OR_INPUT"
    )
    require(actual.code_observation == bundle.code, "MIXED_CODE_OBSERVATION")
    if isinstance(request, ProviderCaptureRequest):
        require(
            isinstance(request.subject_reference, Known)
            and request.subject_reference.value == bundle.subject.subject_ref,
            "PROVIDER_SUBJECT_SCOPE_MISMATCH",
        )
    if isinstance(candidate.subject_identity, IdentityOutcome):
        require(
            candidate.subject_identity.context_ref == bundle.context.context_ref,
            "OUTCOME_CONTEXT_MISMATCH",
        )
    if not isinstance(actual.s1, BlockingFailure):
        require(
            actual.s1.context_ref == bundle.context.context_ref
            and actual.s1.requested_tuple == request.requested
            and actual.s1.content_refs == (request.content.content_version_ref,),
            "OUTCOME_INPUT_MISMATCH",
        )
        amount = (
            request.assertion.source_amount
            if isinstance(request, IssuerBindingRequest)
            else request.displayed_value
        )
        require(actual.s1.source_amount == amount, "OUTCOME_AMOUNT_MISMATCH")
    if not isinstance(actual.s2, BlockingFailure):
        require(
            actual.s2.context == bundle.context and actual.s2.requested_tuple == request.requested,
            "TEMPORAL_CONTEXT_MISMATCH",
        )
    expected = complete_candidate(bundle.context, candidate.source, anchor, bundle.code)
    require(candidate == expected, "COMPLETED_OWNER_MISMATCH")


def _qualification(
    candidate: CompletedCandidate, policy: SelectionPolicy
) -> tuple[Qualification, str]:
    actual, request = candidate.actual, candidate.source.request
    if isinstance(request, ProviderCaptureRequest):
        require(
            isinstance(request.content.provider_ref, Known)
            and request.content.provider_ref.value in policy.provider_refs,
            "PROVIDER_OUTSIDE_SCOPE",
        )
        return "AUDIT_ONLY", "PROVIDER_DISCREPANCY"
    require(
        isinstance(request.content.source_ref, Known)
        and request.content.source_ref.value in policy.source_refs
        and isinstance(request.content.issuer_ref, Known)
        and request.content.issuer_ref.value == policy.issuer_ref,
        "ISSUER_OUTSIDE_SCOPE",
    )
    identity = candidate.subject_identity
    if not isinstance(identity, IdentityOutcome):
        raise ContractError("MISSING_S1_SUBJECT_ASSESSMENT")
    require(identity.state != "DIFFERENT", "SUBJECT_SCOPE_MISMATCH")
    if isinstance(actual.s1, BlockingFailure) or isinstance(actual.s2, BlockingFailure):
        raise ContractError("BLOCKED_CANDIDATE")
    if identity.state != "SAME":
        return "UNRESOLVED", identity.reason
    if actual.s1.state != "BOUND":
        return "UNRESOLVED", actual.s1.reason
    if actual.s2.state == "NOT_ADMISSIBLE":
        return "EXCLUDED", actual.s2.reason
    if actual.s2.state != "SUPPORTED":
        return "UNRESOLVED", actual.s2.reason
    return "QUALIFIED", "NONE"


def _material(candidate: CompletedCandidate, bundle: SelectionBundle) -> bool:
    lead = candidate.source.historical_lead
    if isinstance(lead, NotApplicable):
        require(
            lead.owner == "S3" and lead.reason == "NO_HISTORICAL_CLUE", "UNDECLARED_MATERIALITY"
        )
        return False
    request = candidate.source.request
    require(
        lead.candidate_ref == candidate.ref
        and lead.scope_ref == bundle.policy.discovery_scope_ref
        and lead.evidence_member in request.scope.input_members
        and isinstance(lead.origin.input_digest, OriginKnownValue)
        and lead.origin.input_digest.value == request.content.raw_sha256,
        "FOREIGN_MATERIALITY_LEAD",
    )
    if lead.basis == "CURRENT_PROVIDER_ONLY":
        require(isinstance(request, ProviderCaptureRequest), "INVALID_PROVIDER_LEAD")
        return False
    require(lead.basis == "CONTEMPORANEOUS_ISSUER_NOTICE", "UNSUPPORTED_MATERIALITY_RULE")
    return True  # A concrete unresolved historical lead may change the strict target.


def _relations(bundle: SelectionBundle) -> tuple[RelationAssessment, ...]:
    candidates = {c.ref: c for c in bundle.candidates}
    assessments = []
    for item in bundle.relations:
        relation, notice = item.relation, item.notice
        require(
            relation.declaration_version == "a03-v0.1"
            and isinstance(relation.scope, NotEvaluated)
            and relation.event_property == "NONE",
            "LEGACY_RELATION_PROFILE_MISMATCH",
        )
        if isinstance(notice, NotEvaluated):
            assessments.append(
                RelationAssessment(relation.relation_ref, "UNRESOLVED", "RELATION_EVIDENCE_ABSENT")
            )
            continue
        source, actual = notice.source, notice.actual
        if not isinstance(source.request, IssuerBindingRequest) or not isinstance(
            source.subject, SubjectFacts
        ):
            raise ContractError("RELATION_NOTICE_NOT_ISSUER_ASSERTION")
        require(
            isinstance(source.request.content.source_ref, Known)
            and source.request.content.source_ref.value in bundle.policy.source_refs
            and isinstance(source.request.content.issuer_ref, Known)
            and source.request.content.issuer_ref.value == bundle.policy.issuer_ref,
            "RELATION_NOTICE_OUTSIDE_SCOPE",
        )
        require(
            notice.ref == relation.notice_assertion_ref and notice.ref not in candidates,
            "RELATION_NOTICE_IDENTITY_MISMATCH",
        )
        require(
            isinstance(source.subject.metric, Known)
            and source.subject.metric.value == relation_proposition(relation)
            and source.subject.metric.origin == relation.origin
            and isinstance(relation.origin.input_digest, OriginKnownValue)
            and relation.origin.input_digest.value == source.request.content.raw_sha256
            and source.request.assertion.source_amount.value == 1
            and source.request.assertion.source_unit.value == "relation_declaration",
            "RELATION_CONTENT_MISMATCH",
        )
        require(
            isinstance(notice.subject_identity, IdentityOutcome)
            and notice.subject_identity.state == "SAME",
            "RELATION_SUBJECT_UNRESOLVED",
        )
        if isinstance(actual.s1, BlockingFailure) or isinstance(actual.s2, BlockingFailure):
            raise ContractError("BLOCKED_RELATION_NOTICE")
        # Contradictory supplied endpoints are structural faults even for future notices.
        if (
            relation.subject_ref == bundle.subject.subject_ref
            and relation.kind in {"CORRECTS", "REPLACES"}
            and isinstance(relation.new_assertion_ref, str)
            and isinstance(relation.new_version_ref, str)
        ):
            require(
                relation.old_assertion_ref in candidates
                and relation.new_assertion_ref in candidates
                and relation.old_assertion_ref != relation.new_assertion_ref,
                "RELATION_ENDPOINT_MISMATCH",
            )
            require(isinstance(relation.old_assertion_ref, str), "RELATION_ENDPOINT_MISMATCH")
            assert isinstance(relation.old_assertion_ref, str)
            old, new = (
                candidates[relation.old_assertion_ref],
                candidates[relation.new_assertion_ref],
            )
            require(
                old.source.request.content.content_version_ref == relation.old_version_ref
                and new.source.request.content.content_version_ref == relation.new_version_ref,
                "RELATION_VERSION_MISMATCH",
            )
            require(
                all(
                    source.request.content.content_version_ref
                    != c.source.request.content.content_version_ref
                    and source.request.content.representation_ref
                    != c.source.request.content.representation_ref
                    for c in (old, new)
                ),
                "BORROWED_RELATION_NOTICE",
            )
        if actual.s1.state != "BOUND" or actual.s2.state == "UNRESOLVED":
            assessments.append(
                RelationAssessment(relation.relation_ref, "UNRESOLVED", "RELATION_UNQUALIFIED")
            )
            continue
        if actual.s2.state == "NOT_ADMISSIBLE":
            assessments.append(
                RelationAssessment(relation.relation_ref, "EXCLUDED", "RELATION_AFTER_CUTOFF")
            )
            continue
        if relation.subject_ref != bundle.subject.subject_ref:
            assessments.append(
                RelationAssessment(relation.relation_ref, "EXCLUDED", "RELATION_SCOPE_MISMATCH")
            )
            continue
        if relation.kind not in {"CORRECTS", "REPLACES"}:
            assessments.append(
                RelationAssessment(
                    relation.relation_ref, "UNRESOLVED", "UNSUPPORTED_RELATION_KIND_NO_ROLLBACK"
                )
            )
            continue
        if not isinstance(relation.new_assertion_ref, str) or not isinstance(
            relation.new_version_ref, str
        ):
            assessments.append(
                RelationAssessment(relation.relation_ref, "UNRESOLVED", "RELATION_TARGET_UNKNOWN")
            )
            continue
        assessments.append(RelationAssessment(relation.relation_ref, "QUALIFIED", "NONE"))
    return tuple(sorted(assessments, key=lambda a: a.relation_ref))


def _relations_b02(bundle: SelectionBundle) -> tuple[RelationAssessment, ...]:
    """Separate source event, visibility, directed proposition and field effect."""
    candidates = {c.ref: c for c in bundle.candidates}
    assessments = []
    for item in sorted(bundle.relations, key=lambda r: r.relation.relation_ref):
        relation, notice = item.relation, item.notice
        if isinstance(notice, NotEvaluated):
            assessments.append(
                RelationAssessment(
                    relation.relation_ref,
                    "UNRESOLVED",
                    "RELATION_EVIDENCE_ABSENT",
                    effect="UNKNOWN",
                )
            )
            continue
        request = notice.source.request
        require(isinstance(request, IssuerBindingRequest), "RELATION_NOTICE_NOT_ISSUER_ASSERTION")
        assert isinstance(request, IssuerBindingRequest)
        require(relation.declaration_version == "b02-v0.1", "B02_RELATION_PROFILE_MISMATCH")
        require(relation.event_property in {"NONE", "RESTATEMENT"}, "UNSUPPORTED_EVENT_PROPERTY")
        require(
            notice.ref == relation.notice_assertion_ref and notice.ref not in candidates,
            "RELATION_NOTICE_IDENTITY_MISMATCH",
        )
        require(
            isinstance(notice.source.subject, SubjectFacts)
            and isinstance(notice.source.subject.metric, Known)
            and notice.source.subject.metric.value == relation_proposition(relation)
            and notice.source.subject.metric.origin == relation.origin
            and isinstance(relation.origin.input_digest, OriginKnownValue)
            and relation.origin.input_digest.value == request.content.raw_sha256
            and request.assertion.source_amount.value == 1
            and request.assertion.source_unit.value == "relation_declaration",
            "RELATION_CONTENT_MISMATCH",
        )
        scope = relation.scope
        in_scope = relation.subject_ref == bundle.subject.subject_ref
        if isinstance(scope, RevisionScope):
            require(scope.kind in {"FIELD", "DOCUMENT"}, "INVALID_REVISION_SCOPE")
            require(scope.origin == relation.origin, "RELATION_SCOPE_ORIGIN_MISMATCH")
            if isinstance(scope.subject_refs, tuple):
                require(
                    len(scope.subject_refs) == len(set(scope.subject_refs)), "DUPLICATE_SCOPE_FIELD"
                )
                if scope.kind == "FIELD":
                    require(
                        scope.subject_refs == (relation.subject_ref,), "RELATION_FIELD_MISMATCH"
                    )
                in_scope = in_scope and bundle.subject.subject_ref in scope.subject_refs
        # Structural contradictions are not hidden by an after-cutoff notice.
        for ref, version, document in (
            (
                relation.old_assertion_ref,
                relation.old_version_ref,
                scope.old_document_ref if isinstance(scope, RevisionScope) else None,
            ),
            (
                relation.new_assertion_ref,
                relation.new_version_ref,
                scope.new_document_ref if isinstance(scope, RevisionScope) else None,
            ),
        ):
            require(
                isinstance(ref, str) == isinstance(version, str), "RELATION_ENDPOINT_PAIR_MISMATCH"
            )
            if in_scope and isinstance(ref, str):
                require(ref in candidates, "RELATION_ENDPOINT_MISMATCH")
                candidate = candidates[ref]
                require(
                    candidate.source.request.content.content_version_ref == version,
                    "RELATION_VERSION_MISMATCH",
                )
                if isinstance(document, str):
                    require(document == version, "RELATION_DOCUMENT_MISMATCH")
                require(
                    candidate.subject_identity.state != "DIFFERENT"
                    if isinstance(candidate.subject_identity, IdentityOutcome)
                    else False,
                    "RELATION_FIELD_MISMATCH",
                )
                require(
                    request.content.content_version_ref
                    != candidate.source.request.content.content_version_ref
                    and request.content.representation_ref
                    != candidate.source.request.content.representation_ref,
                    "BORROWED_RELATION_NOTICE",
                )
        if relation.kind == "WITHDRAWS":
            unknown_successor = isinstance(relation.new_assertion_ref, Unknown) and isinstance(
                relation.new_version_ref, Unknown
            )
            absent_successor = (
                isinstance(relation.new_assertion_ref, NotApplicable)
                and isinstance(relation.new_version_ref, NotApplicable)
                and relation.new_assertion_ref.owner == relation.new_version_ref.owner == "S3"
                and relation.new_assertion_ref.reason
                == relation.new_version_ref.reason
                == "NO_SUCCESSOR"
            )
            # This is a source-declared type constraint, independent of visibility.
            # Unknown endpoints remain a valid incomplete event, not a known successor.
            require(unknown_successor or absent_successor, "WITHDRAWAL_SUCCESSOR_CONTRADICTION")
        qualification, _ = _qualification(notice, bundle.policy)
        event: Literal["SUPPORTED", "UNRESOLVED"] = (
            "SUPPORTED"
            if not isinstance(notice.actual.s1, BlockingFailure)
            and notice.actual.s1.state == "BOUND"
            else "UNRESOLVED"
        )
        visibility: Literal["SUPPORTED", "UNRESOLVED", "NOT_ADMISSIBLE"] = "UNRESOLVED"
        if not isinstance(notice.actual.s2, BlockingFailure):
            visibility = notice.actual.s2.state

        def assessed(
            state: Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED"],
            reason: str,
            supported: Literal["SUPPORTED", "UNRESOLVED"] = "UNRESOLVED",
            effect: Literal[
                "SUPERSEDES", "WITHDRAWS", "REISSUES", "OUT_OF_SCOPE", "UNKNOWN", "NONE"
            ] = "UNKNOWN",
            *,
            ref: str = relation.relation_ref,
            event_state: Literal["SUPPORTED", "UNRESOLVED"] = event,
            notice_state: Literal["SUPPORTED", "UNRESOLVED", "NOT_ADMISSIBLE"] = visibility,
        ) -> RelationAssessment:
            return RelationAssessment(
                ref, state, reason, event_state, notice_state, supported, effect
            )

        known_old = isinstance(relation.old_assertion_ref, str)
        known_new = isinstance(relation.new_assertion_ref, str)
        mapped = (
            isinstance(scope, RevisionScope)
            and isinstance(scope.subject_refs, tuple)
            and bool(scope.subject_refs)
            and isinstance(scope.old_document_ref, str)
            and (not known_new or isinstance(scope.new_document_ref, str))
        )
        supported = (
            mapped
            and known_old
            and (
                known_new
                if relation.kind in {"CORRECTS", "REPLACES"}
                else isinstance(relation.new_assertion_ref, (str, NotApplicable))
            )
            and relation.kind in {"CORRECTS", "REPLACES", "WITHDRAWS", "REISSUES"}
        )
        support: Literal["SUPPORTED", "UNRESOLVED"] = (
            "SUPPORTED" if supported and event == "SUPPORTED" else "UNRESOLVED"
        )
        if not in_scope:
            assessments.append(
                assessed("EXCLUDED", "RELATION_SCOPE_MISMATCH", support, "OUT_OF_SCOPE")
            )
        elif visibility == "NOT_ADMISSIBLE":
            assessments.append(assessed("EXCLUDED", "RELATION_AFTER_CUTOFF", support, "NONE"))
        elif qualification != "QUALIFIED":
            assessments.append(assessed("UNRESOLVED", "RELATION_UNQUALIFIED", support))
        elif relation.kind not in {"CORRECTS", "REPLACES", "WITHDRAWS", "REISSUES"}:
            assessments.append(assessed("UNRESOLVED", "UNSUPPORTED_RELATION_KIND_NO_ROLLBACK"))
        elif not mapped:
            assessments.append(assessed("UNRESOLVED", "RELATION_SCOPE_UNKNOWN"))
        elif not supported:
            assessments.append(assessed("UNRESOLVED", "RELATION_TARGET_UNKNOWN"))
        else:
            if relation.kind == "WITHDRAWS":
                assessments.append(
                    assessed("QUALIFIED", "NO_AUTOMATIC_ROLLBACK", "SUPPORTED", "WITHDRAWS")
                )
            elif relation.kind == "REISSUES":
                if (
                    known_new
                    and isinstance(relation.old_assertion_ref, str)
                    and isinstance(relation.new_assertion_ref, str)
                ):
                    old, new = (
                        candidates[relation.old_assertion_ref],
                        candidates[relation.new_assertion_ref],
                    )
                    require(
                        isinstance(old.source.request, IssuerBindingRequest)
                        and isinstance(new.source.request, IssuerBindingRequest),
                        "REISSUE_NOT_ISSUER",
                    )
                    assert isinstance(old.source.request, IssuerBindingRequest)
                    assert isinstance(new.source.request, IssuerBindingRequest)
                    require(
                        old.source.request.assertion.source_amount.value
                        == new.source.request.assertion.source_amount.value,
                        "REISSUE_CONTENT_MISMATCH",
                    )
                assessments.append(
                    assessed("QUALIFIED", "REISSUE_IS_NOT_SUPERSESSION", "SUPPORTED", "REISSUES")
                )
            else:
                require(
                    relation.old_assertion_ref != relation.new_assertion_ref,
                    "RELATION_IDENTITY_CYCLE",
                )
                assessments.append(assessed("QUALIFIED", "NONE", "SUPPORTED", "SUPERSEDES"))
    return tuple(assessments)


def _lineage(
    bundle: SelectionBundle, assessments: tuple[RelationAssessment, ...]
) -> tuple[set[str], set[str], tuple[Reachability, ...], str]:
    # Check source-backed identity contradictions even if a notice is late.
    # Keep every edge: a branch must not overwrite an edge and conceal a cycle.
    supported = {
        a.relation_ref
        for a in assessments
        if a.relation_support == "SUPPORTED" and a.effect != "OUT_OF_SCOPE"
    }
    directions: dict[str, set[str]] = {}
    for item in bundle.relations:
        relation = item.relation
        if relation.relation_ref in supported and relation.kind in {"CORRECTS", "REPLACES"}:
            assert isinstance(relation.old_assertion_ref, str)
            assert isinstance(relation.new_assertion_ref, str)
            directions.setdefault(relation.old_assertion_ref, set()).add(relation.new_assertion_ref)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ref: str) -> None:
        require(ref not in visiting, "RELATION_IDENTITY_CYCLE")
        if ref in visited:
            return
        visiting.add(ref)
        for target in sorted(directions.get(ref, ())):
            visit(target)
        visiting.remove(ref)
        visited.add(ref)

    for ref in sorted(directions):
        visit(ref)
    effective = {a.relation_ref: a for a in assessments if a.state != "EXCLUDED"}
    accepted = [
        r.relation
        for r in bundle.relations
        if r.relation.relation_ref in effective
        and effective[r.relation.relation_ref].state == "QUALIFIED"
    ]
    transitions = [r for r in accepted if effective[r.relation_ref].effect == "SUPERSEDES"]
    edges: dict[str, tuple[str, str]] = {}
    incoming: dict[str, str] = {}
    reason = "NONE"
    for relation in sorted(transitions, key=lambda r: r.relation_ref):
        old, new = relation.old_assertion_ref, relation.new_assertion_ref
        assert isinstance(old, str) and isinstance(new, str)
        if old in edges:
            reason = (
                "DUPLICATE_DIRECT_DECLARATION"
                if edges[old][0] == new
                else "UNSUPPORTED_RELATION_BRANCH"
            )
        if new in incoming and incoming[new] != old:
            reason = "UNSUPPORTED_RELATION_MERGE"
        edges[old] = (new, relation.relation_ref)
        incoming[new] = old
    nodes = {
        ref
        for r in accepted
        for ref in (r.old_assertion_ref, r.new_assertion_ref)
        if isinstance(ref, str)
    }
    if len(nodes) > 3:
        reason = "UNSUPPORTED_DISCONNECTED_LINEAGE"
    elif len(accepted) == 2:
        first, second = accepted
        endpoints = (
            {ref for ref in (r.old_assertion_ref, r.new_assertion_ref) if isinstance(ref, str)}
            for r in (first, second)
        )
        if not set.intersection(*endpoints):
            reason = "UNSUPPORTED_DISCONNECTED_LINEAGE"
    if len(effective) > MAX_EFFECTIVE_DECLARATIONS:
        reason = "EFFECTIVE_RELATION_LIMIT"
    superseded = {r.old_assertion_ref for r in transitions if isinstance(r.old_assertion_ref, str)}
    withdrawn = {
        r.old_assertion_ref
        for r in accepted
        if effective[r.relation_ref].effect == "WITHDRAWS" and isinstance(r.old_assertion_ref, str)
    }
    paths = []
    for start in sorted(edges) if reason == "NONE" else ():
        middle, first_ref = edges[start]
        if middle in edges:
            end, second_ref = edges[middle]
            paths.append(Reachability(start, end, (first_ref, second_ref)))
    if withdrawn - superseded and reason == "NONE":
        reason = "WITHDRAWAL_WITHOUT_RESTORATION"
    return superseded, withdrawn, tuple(paths), reason


def _discovery(
    bundle: SelectionBundle, coverage: CoverageAssessment
) -> tuple[CoverageAssessment | BlockingFailure, dict[str, bool], tuple[ResearchAuditEntry, ...]]:
    evidence = bundle.discovery
    grounded: dict[str, bool] = {}
    audit: list[ResearchAuditEntry] = []
    missing = set(coverage.missing_checks)
    if not isinstance(evidence, DiscoveryEvidence):
        missing.add("DISCOVERY_EVIDENCE")
        return (
            CoverageAssessment("INSUFFICIENT", coverage.completed_checks, tuple(sorted(missing))),
            grounded,
            (),
        )
    require(
        isinstance(evidence.origin.input_digest, OriginKnownValue)
        and sha256(evidence.raw_bytes).hexdigest() == evidence.origin.input_digest.value
        and evidence.raw_bytes == discovery_proposition(evidence)
        and isinstance(evidence.origin.object_id, OriginKnownValue)
        and evidence.origin.object_id.value == evidence.discovery_ref
        and evidence.origin.visibility in {Visibility.ACTIVE, Visibility.AUXILIARY},
        "DISCOVERY_SOURCE_MISMATCH",
    )
    require(
        evidence.context_ref == bundle.context.context_ref
        and evidence.evidence_set_ref == bundle.context.evidence_set_ref
        and evidence.policy == bundle.policy
        and evidence.subject == bundle.subject
        and evidence.mode == bundle.context.mode
        and evidence.cutoff_text == bundle.context.information_cutoff.source_text
        and evidence.query_key == bundle.subject.subject_ref
        and bool(evidence.window[0])
        and evidence.window[1] == evidence.cutoff_text,
        "DISCOVERY_CONTEXT_MISMATCH",
    )
    require(
        sorted(evidence.candidates, key=lambda c: c.request.requested.target_ref)
        == sorted(
            (c.source for c in bundle.candidates), key=lambda c: c.request.requested.target_ref
        )
        and sorted(evidence.relations, key=lambda r: r.relation.relation_ref)
        == sorted(
            (
                RelationSource(
                    r.relation,
                    r.notice.source if isinstance(r.notice, CompletedCandidate) else r.notice,
                )
                for r in bundle.relations
            ),
            key=lambda r: r.relation.relation_ref,
        ),
        "DISCOVERY_MEMBERSHIP_MISMATCH",
    )
    require(
        sorted(evidence.checks, key=lambda c: c.check_ref)
        == sorted(bundle.coverage.checks, key=lambda c: c.check_ref),
        "DISCOVERY_CHECK_MISMATCH",
    )
    members = ["C:" + c.request.requested.target_ref for c in evidence.candidates]
    members += ["R:" + r.relation.relation_ref for r in evidence.relations]
    members += ["L:" + lead.lead_ref for lead in evidence.leads]
    members += ["X:" + x.source.request.requested.target_ref for x in evidence.exclusions]
    flattened = [ref for page in evidence.pages for ref in page]
    require(
        len(members) == len(set(members))
        and len(flattened) == len(set(flattened))
        and set(flattened) == set(members),
        "DISCOVERY_PAGE_MEMBERSHIP_MISMATCH",
    )
    if not evidence.terminated or not evidence.pages:
        missing.add("DISCOVERY_TERMINATION")
    occupied = {c.ref for c in bundle.candidates}
    occupied.update(
        r.notice.ref for r in bundle.relations if isinstance(r.notice, CompletedCandidate)
    )
    for lead in sorted(evidence.leads, key=lambda lead: lead.lead_ref):
        require(
            lead.subject_ref == bundle.subject.subject_ref
            and lead.scope_ref == bundle.policy.discovery_scope_ref,
            "FOREIGN_MATERIALITY_LEAD",
        )
        require(isinstance(lead.notice.subject, SubjectFacts), "LEAD_NOTICE_SUBJECT_ABSENT")
        assert isinstance(lead.notice.subject, SubjectFacts)
        notice = complete_candidate(bundle.context, lead.notice, lead.notice.subject, bundle.code)
        require(notice.ref not in occupied, "DUPLICATE_NOTICE_IDENTITY")
        occupied.add(notice.ref)
        require(isinstance(lead.notice.request, IssuerBindingRequest), "LEAD_NOTICE_NOT_ISSUER")
        assert isinstance(lead.notice.request, IssuerBindingRequest)
        require(
            isinstance(lead.notice.subject.metric, Known)
            and lead.notice.subject.metric.value == lead_proposition(lead)
            and lead.notice.request.assertion.source_amount.value == 1
            and lead.notice.request.assertion.source_unit.value == "historical_lead_declaration",
            "LEAD_CONTENT_MISMATCH",
        )
        # Owner failures remain failures; valid missing time remains uncertainty.
        for outcome in (notice.actual.s1, notice.actual.s2, notice.subject_identity):
            if isinstance(outcome, BlockingFailure):
                return outcome, grounded, tuple(audit)
        qualification, _ = _qualification(notice, bundle.policy)
        backed = (
            not isinstance(notice.actual.s1, BlockingFailure) and notice.actual.s1.state == "BOUND"
        )
        if not backed:
            missing.add("MATERIALITY_EVIDENCE")
        relevant = qualification != "EXCLUDED"
        grounded[lead.candidate_ref] = grounded.get(lead.candidate_ref, False) or relevant
        audit.append(
            ResearchAuditEntry(
                "HISTORICAL_LEAD",
                lead.lead_ref,
                "POTENTIAL_PRE_CUTOFF_COMPETITOR" if relevant else "FUTURE_ONLY_LEAD",
            )
        )
    for candidate in bundle.candidates:
        clue = candidate.source.historical_lead
        # The legacy label alone cannot certify a completed B02 materiality review.
        if isinstance(clue, HistoricalLead):
            _material(candidate, bundle)
            if clue.basis == "CONTEMPORANEOUS_ISSUER_NOTICE":
                matching = [
                    r
                    for r in evidence.leads
                    if r.lead_ref == clue.lead_ref and r.candidate_ref == candidate.ref
                ]
                if not matching:
                    missing.add("MATERIALITY_EVIDENCE")
                    grounded[candidate.ref] = True
    for exclusion in evidence.exclusions:
        actual = complete_candidate(bundle.context, exclusion.source, bundle.subject, bundle.code)
        require(actual.ref not in occupied, "DUPLICATE_DISCOVERY_IDENTITY")
        occupied.add(actual.ref)
        require(
            exclusion.reason == "NOT_COMPARABLE"
            and isinstance(actual.subject_identity, IdentityOutcome)
            and actual.subject_identity.state == "DIFFERENT"
            and not isinstance(actual.actual.s1, BlockingFailure),
            "UNJUSTIFIED_DISCOVERY_EXCLUSION",
        )
        audit.append(ResearchAuditEntry("DISCOVERY_EXCLUSION", actual.ref, exclusion.reason))
    audit.append(
        ResearchAuditEntry(
            "DISCOVERY",
            evidence.discovery_ref,
            "BOUNDED_COMPLETE" if not missing else "BOUNDED_INCOMPLETE",
        )
    )
    return (
        CoverageAssessment(
            "INSUFFICIENT" if missing else "SUFFICIENT",
            coverage.completed_checks,
            tuple(sorted(missing)),
            (evidence.discovery_ref,),
        ),
        grounded,
        tuple(audit),
    )


def reconstruction_ref(bundle: SelectionBundle) -> str | NotEvaluated:
    if bundle.policy.version != B02_POLICY_VERSION:
        return NotEvaluated("S3", "LEGACY_RECONSTRUCTION")
    context = {
        f.name: getattr(bundle.context, f.name)
        for f in fields(bundle.context)
        if f.name not in {"decision_wall_times", "computation_attempt_time"}
    }
    identity = (
        context,
        bundle.subject,
        bundle.policy,
        tuple(
            sorted(
                (c.source for c in bundle.candidates), key=lambda c: c.request.requested.target_ref
            )
        ),
        tuple(sorted((r.relation for r in bundle.relations), key=lambda r: r.relation_ref)),
        bundle.discovery,
        tuple(sorted(bundle.coverage.checks, key=lambda c: c.check_ref)),
        tuple(sorted(bundle.coverage.evaluated_candidate_refs)),
        tuple(sorted(bundle.coverage.evaluated_relation_refs)),
        bundle.code.observed_working_files,
    )
    return "B02-RECONSTRUCTION-" + sha256(_canonical(identity)).hexdigest()


def canonical_bundle(bundle: SelectionBundle) -> SelectionBundle:
    """Canonicalize declared sets only; discovery pages keep their exact order."""
    if bundle.policy.version != B02_POLICY_VERSION:
        return bundle
    policy = replace(
        bundle.policy,
        source_refs=tuple(sorted(bundle.policy.source_refs)),
        provider_refs=tuple(sorted(bundle.policy.provider_refs)),
    )
    evidence = bundle.discovery
    if isinstance(evidence, DiscoveryEvidence):
        evidence = replace(
            evidence,
            policy=replace(
                evidence.policy,
                source_refs=tuple(sorted(evidence.policy.source_refs)),
                provider_refs=tuple(sorted(evidence.policy.provider_refs)),
            ),
            candidates=tuple(
                sorted(evidence.candidates, key=lambda c: c.request.requested.target_ref)
            ),
            relations=tuple(sorted(evidence.relations, key=lambda r: r.relation.relation_ref)),
            checks=tuple(sorted(evidence.checks, key=lambda c: c.check_ref)),
            leads=tuple(sorted(evidence.leads, key=lambda lead: lead.lead_ref)),
            exclusions=tuple(
                sorted(evidence.exclusions, key=lambda x: x.source.request.requested.target_ref)
            ),
        )
    return replace(
        bundle,
        policy=policy,
        discovery=evidence,
        candidates=tuple(sorted(bundle.candidates, key=lambda c: c.ref)),
        relations=tuple(sorted(bundle.relations, key=lambda r: r.relation.relation_ref)),
        coverage=replace(
            bundle.coverage,
            source_refs=tuple(sorted(bundle.coverage.source_refs)),
            evaluated_candidate_refs=tuple(sorted(bundle.coverage.evaluated_candidate_refs)),
            evaluated_relation_refs=tuple(sorted(bundle.coverage.evaluated_relation_refs)),
            checks=tuple(sorted(bundle.coverage.checks, key=lambda c: c.check_ref)),
        ),
    )


def select_asof(bundle: SelectionBundle) -> SelectionOutcome | BlockingFailure:
    """Consume completed S1/S2 operations; never parse time or source JSON here."""
    try:
        bundle = canonical_bundle(bundle)
        policy, context, coverage = bundle.policy, bundle.context, bundle.coverage
        b02 = policy.version == B02_POLICY_VERSION
        require(
            (policy.version, policy.evaluator_ref)
            in {("a03-policy-v0.1", EVALUATOR_REF), (B02_POLICY_VERSION, B02_EVALUATOR_REF)}
            and bool(policy.source_refs)
            and policy.target in {"CONTENT_VALUE", "ATTRIBUTED_ASSERTION"}
            and policy.required_checks == REQUIRED_CHECKS
            and policy.materiality_rule == "GROUNDED_HISTORICAL_COMPETITOR"
            and policy.provider_rule == "AUDIT_CURRENT_ONLY",
            "UNSUPPORTED_SELECTION_POLICY",
        )
        require(
            policy.mode == context.mode
            and policy.subject_ref == bundle.subject.subject_ref
            and policy.target == context.target_ref
            and policy.policy_ref in context.policy_refs,
            "POLICY_CONTEXT_MISMATCH",
        )
        require(
            set(S3_CODE_PATHS) <= {p.path for p in bundle.code.observed_working_files},
            "S3_CODE_IDENTITY_ABSENT",
        )
        refs = [c.ref for c in bundle.candidates]
        versions = [c.source.request.content.content_version_ref for c in bundle.candidates]
        reps = [c.source.request.content.representation_ref for c in bundle.candidates]
        relation_refs = [r.relation.relation_ref for r in bundle.relations]
        require(
            all(len(v) == len(set(v)) for v in (refs, versions, reps, relation_refs)),
            "DUPLICATE_CANDIDATE_OR_RELATION",
        )
        notices = tuple(
            r.notice for r in bundle.relations if isinstance(r.notice, CompletedCandidate)
        )
        all_candidates = (*bundle.candidates, *notices)
        require(
            len({c.ref for c in all_candidates}) == len(all_candidates), "DUPLICATE_NOTICE_IDENTITY"
        )
        if b02:
            require(
                all(
                    len(values) == len(set(values))
                    for values in (
                        [c.source.request.content.content_version_ref for c in all_candidates],
                        [c.source.request.content.representation_ref for c in all_candidates],
                    )
                ),
                "DUPLICATE_NOTICE_CONTENT_IDENTITY",
            )
            require(
                len(policy.source_refs) == len(set(policy.source_refs))
                and len(policy.provider_refs) == len(set(policy.provider_refs)),
                "DUPLICATE_SOURCE_SCOPE",
            )
        proof_inventory: dict[str, TemporalProof] = {}
        support_inventory: dict[str, object] = {}
        for c in (*bundle.candidates, *notices):
            anchor = bundle.subject
            if c in notices and isinstance(c.source.subject, SubjectFacts):
                anchor = c.source.subject
            _validate_actual(c, bundle, anchor)
            for outcome in (c.actual.s1, c.actual.s2, c.subject_identity):
                if isinstance(outcome, BlockingFailure):
                    return outcome
            if isinstance(c.source.request, IssuerBindingRequest):
                for attempt in c.source.request.attempts:
                    binding = attempt.supplied
                    require(
                        binding.support_ref not in support_inventory
                        or support_inventory[binding.support_ref] == binding,
                        "CONTRADICTORY_SUPPORT_IDENTITY",
                    )
                    support_inventory[binding.support_ref] = binding
            if not isinstance(c.actual.s1, BlockingFailure):
                for assessment in c.actual.s1.assessments:
                    proof = assessment.supplied.proof_candidate
                    if assessment.disposition == "ACCEPTED" and isinstance(
                        proof, TEMPORAL_PROOF_TYPES
                    ):
                        require(
                            proof.proof_ref not in proof_inventory
                            or proof_inventory[proof.proof_ref] == proof,
                            "CONTRADICTORY_PROOF_IDENTITY",
                        )
                        proof_inventory[proof.proof_ref] = proof
        require(
            coverage.context_ref == context.context_ref
            and coverage.evidence_set_ref == context.evidence_set_ref
            and coverage.policy_ref == policy.policy_ref
            and coverage.policy_version == policy.version
            and coverage.scope_ref == policy.discovery_scope_ref
            and set(coverage.source_refs) == set(policy.source_refs),
            "COVERAGE_CONTEXT_MISMATCH",
        )
        require(
            len(coverage.evaluated_candidate_refs) == len(set(coverage.evaluated_candidate_refs))
            and set(coverage.evaluated_candidate_refs) == set(refs)
            and len(coverage.evaluated_relation_refs) == len(set(coverage.evaluated_relation_refs))
            and set(coverage.evaluated_relation_refs) == set(relation_refs),
            "COVERAGE_UNIVERSE_MISMATCH",
        )
        check_refs = [c.check_ref for c in coverage.checks]
        require(len(check_refs) == len(set(check_refs)), "DUPLICATE_COVERAGE_CHECK")
        grounded: dict[str, bool] = {}
        discovery_audit: tuple[ResearchAuditEntry, ...] = ()
        discovery_coverage = CoverageAssessment("SUFFICIENT", (), ())
        if b02:
            discovery_result, grounded, discovery_audit = _discovery(bundle, discovery_coverage)
            if isinstance(discovery_result, BlockingFailure):
                return discovery_result
            discovery_coverage = discovery_result
        completed = []
        for check in coverage.checks:
            require(
                check.check_ref in REQUIRED_CHECKS and check.scope_ref == coverage.scope_ref,
                "FOREIGN_COVERAGE_CHECK",
            )
            if check.status == "FAILED":
                return BlockingFailure(
                    "OPERATIONAL_ERROR",
                    "REQUIRED_OPERATION_FAILED",
                    (),
                    "REQUIRED_OPERATION_FAILED",
                    check.origin,
                    "SELECT_ASOF",
                )
            require(check.status in {"COMPLETED", "NOT_PERFORMED"}, "INVALID_COVERAGE_STATE")
            if check.status == "COMPLETED":
                expected_evidence = json.dumps(
                    {
                        "check": check.check_ref,
                        "scope": coverage.scope_ref,
                        "source_refs": sorted(coverage.source_refs),
                        "candidate_refs": sorted(coverage.evaluated_candidate_refs),
                        "relation_refs": sorted(coverage.evaluated_relation_refs),
                        "context_ref": coverage.context_ref,
                        "evidence_set_ref": coverage.evidence_set_ref,
                        "policy_ref": policy.policy_ref,
                        "policy_version": policy.version,
                        "status": check.status,
                    },
                    sort_keys=True,
                ).encode()
                require(
                    bool(check.evidence_refs)
                    and bool(check.evidence_bytes)
                    and isinstance(check.origin.input_digest, OriginKnownValue)
                    and sha256(check.evidence_bytes).hexdigest() == check.origin.input_digest.value,
                    "UNEXPLAINED_COVERAGE_COMPLETION",
                )
                require(
                    check.evidence_bytes == expected_evidence
                    and isinstance(check.origin.object_id, OriginKnownValue)
                    and check.origin.object_id.value in check.evidence_refs
                    and check.origin.visibility in {Visibility.ACTIVE, Visibility.AUXILIARY},
                    "COVERAGE_EVIDENCE_SCOPE_MISMATCH",
                )
                completed.append(check.check_ref)
        missing = tuple(sorted(set(REQUIRED_CHECKS) - set(completed)))
        coverage_result = CoverageAssessment(
            "INSUFFICIENT" if missing else "SUFFICIENT", tuple(sorted(completed)), missing
        )
        inventory_exceeded = False
        if b02:
            missing = tuple(sorted(set(missing) | set(discovery_coverage.missing_checks)))
            coverage_result = CoverageAssessment(
                "INSUFFICIENT" if missing else "SUFFICIENT",
                coverage_result.completed_checks,
                missing,
                discovery_coverage.evidence_refs,
            )
            missing = coverage_result.missing_checks
            evidence = bundle.discovery
            inventory_exceeded = (
                len(bundle.candidates) > MAX_CANDIDATES
                or len(bundle.relations) > MAX_NOTICES
                or (
                    isinstance(evidence, DiscoveryEvidence)
                    and len(evidence.leads) + len(evidence.exclusions) > MAX_LEADS_EXCLUSIONS
                )
            )
        relation_assessments = _relations_b02(bundle) if b02 else _relations(bundle)
        accepted = [a for a in relation_assessments if a.state == "QUALIFIED"]
        graph_reason = "NONE"
        withdrawn: set[str] = set()
        reachability: tuple[Reachability, ...] = ()
        if b02:
            superseded, withdrawn, reachability, graph_reason = _lineage(
                bundle, relation_assessments
            )
        else:
            graph_reason = "UNSUPPORTED_RELATION_GRAPH" if len(accepted) > 1 else "NONE"
            superseded = {
                r.relation.old_assertion_ref
                for r in bundle.relations
                if graph_reason == "NONE"
                and isinstance(r.relation.old_assertion_ref, str)
                and any(
                    a.relation_ref == r.relation.relation_ref and a.state == "QUALIFIED"
                    for a in relation_assessments
                )
            }
        assessments = []
        applicable = []
        qualifications = {c.ref: _qualification(c, policy) for c in bundle.candidates}
        qualified_values = {
            c.source.request.assertion.source_amount.value
            for c in bundle.candidates
            if qualifications[c.ref][0] == "QUALIFIED"
            and c.ref not in superseded
            and c.ref not in withdrawn
            and isinstance(c.source.request, IssuerBindingRequest)
        }
        for c in sorted(bundle.candidates, key=lambda c: c.ref):
            qualification, reason = qualifications[c.ref]
            material = (
                (grounded.get(c.ref, False) if b02 else _material(c, bundle))
                and qualification in {"UNRESOLVED", "AUDIT_ONLY"}
                and c.ref not in superseded
                and c.ref not in withdrawn
            )
            amount = (
                c.source.request.assertion.source_amount.value
                if isinstance(c.source.request, IssuerBindingRequest)
                else c.source.request.displayed_value.value
            )
            if (
                policy.target == "CONTENT_VALUE"
                and qualified_values == {amount}
                and not isinstance(c.actual.s1, BlockingFailure)
                and c.actual.s1.state == "BOUND"
            ):
                material = False  # This lead cannot change this bounded content-value target.
            applicability: Applicability = (
                "WITHDRAWN"
                if c.ref in withdrawn
                else "SUPERSEDED"
                if c.ref in superseded
                else ("APPLICABLE" if qualification == "QUALIFIED" else "NOT_QUALIFIED")
            )
            assessments.append(
                CandidateAssessment(c.ref, qualification, applicability, reason, material)
            )
            if applicability == "APPLICABLE":
                applicable.append(c)
        audit = tuple(
            sorted(
                [
                    ResearchAuditEntry(
                        "CANDIDATE",
                        a.candidate_ref,
                        a.reason if a.applicability != "SUPERSEDED" else "SUPERSEDED",
                    )
                    for a in assessments
                ]
                + [
                    ResearchAuditEntry("RELATION", a.relation_ref, a.reason)
                    for a in relation_assessments
                ]
                + list(discovery_audit)
                + [
                    ResearchAuditEntry("APPLICABILITY", ref, "SUPERSEDED_AND_WITHDRAWN")
                    for ref in sorted(superseded & withdrawn)
                ]
                + (
                    [ResearchAuditEntry("APPLICABILITY", policy.subject_ref, graph_reason)]
                    if graph_reason != "NONE"
                    else []
                ),
                key=lambda a: (a.category, a.ref, a.reason),
            )
        )
        reason = "NONE"
        if inventory_exceeded:
            reason = "INPUT_INVENTORY_LIMIT"
        elif graph_reason != "NONE":
            reason = (
                "RELATION_UNQUALIFIED"
                if graph_reason == "WITHDRAWAL_WITHOUT_RESTORATION"
                else graph_reason
            )
        elif any(a.state == "UNRESOLVED" for a in relation_assessments):
            reason = "RELATION_UNQUALIFIED"
        elif any(a.material_unknown for a in assessments) or any(
            material and ref not in qualifications for ref, material in grounded.items()
        ):
            reason = "MATERIAL_CANDIDATE_UNRESOLVED"
        elif any(
            isinstance(r.relation.new_assertion_ref, str)
            and qualifications[r.relation.new_assertion_ref][0] != "QUALIFIED"
            for r in bundle.relations
            if any(
                a.relation_ref == r.relation.relation_ref
                and a.state == "QUALIFIED"
                and (not b02 or a.effect == "SUPERSEDES")
                for a in relation_assessments
            )
        ):
            reason = "MATERIAL_CANDIDATE_UNRESOLVED"
        elif missing:
            reason = "COVERAGE_INSUFFICIENT"
        values = {
            c.source.request.assertion.source_amount.value
            for c in applicable
            if isinstance(c.source.request, IssuerBindingRequest)
        }
        if reason == "NONE" and (
            len(values) > 1 or (policy.target == "ATTRIBUTED_ASSERTION" and len(applicable) > 1)
        ):
            reason = (
                "MATERIAL_CANDIDATE_UNRESOLVED" if len(values) > 1 else "ATTRIBUTION_UNRESOLVED"
            )
        state: Literal["SELECTED", "UNRESOLVED", "NO_QUALIFIED_CLAIM"] = "UNRESOLVED"
        selected: tuple[str, ...] = ()
        value: int | NotEvaluated = NotEvaluated("S3", "NO_SELECTION")
        if reason == "NONE":
            if applicable:
                state, selected, value = (
                    "SELECTED",
                    tuple(c.ref for c in applicable),
                    next(iter(values)),
                )
            else:
                state, reason = "NO_QUALIFIED_CLAIM", "NO_QUALIFIED_WITHIN_SCOPE"
        return SelectionOutcome(
            state,
            reason,
            selected,
            value,
            tuple(assessments),
            relation_assessments,
            coverage_result,
            audit,
            reachability,
        )
    except ContractError as error:
        return BlockingFailure(
            "CONTRACT_VIOLATION", str(error), (), str(error), bundle.context.origin, "SELECT_ASOF"
        )
