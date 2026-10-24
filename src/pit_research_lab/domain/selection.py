"""Pure, bounded S3 engineering selection; no source trust or agent projection.

The A03 declaration profile encodes a directed relation proposition as a synthetic
notice assertion's metric, with unit relation_declaration and value 1. Existing S1
checks that supplied SubjectFacts describe those exact raw statement bytes; the
notice has its own S1/S2 traversal. This profile is not a real-source schema.
"""

import json
from dataclasses import dataclass, field
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
    OriginKnownValue,
    ProviderCaptureRequest,
    Record,
    RoleRef,
    SemanticContext,
    SubjectFacts,
    TemporalProof,
    Visibility,
    require,
)
from pit_research_lab.domain.pit_slice import CodeObservation, SliceResult

EVALUATOR_REF = "s3-a03-direct-field-v0.1-CANDIDATE"
REQUIRED_CHECKS = ("CANDIDATE_DISCOVERY", "RELATION_REVIEW", "MATERIALITY_REVIEW")
S3_CODE_PATHS = (
    "src/pit_research_lab/domain/selection.py",
    "src/pit_research_lab/domain/asof_slice.py",
)
type Qualification = Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED", "AUDIT_ONLY"]
type Applicability = Literal["APPLICABLE", "SUPERSEDED", "NOT_QUALIFIED"]


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
class DirectRelation(Record):
    relation_ref: str
    kind: str
    subject_ref: str
    old_assertion_ref: str
    old_version_ref: str
    new_assertion_ref: str | NotApplicable
    new_version_ref: str | NotApplicable
    notice_assertion_ref: str
    origin: FieldOrigin


def relation_proposition(relation: DirectRelation) -> str:
    """Exact source proposition for this bounded synthetic declaration profile."""
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
class SelectionBundle(Record):
    context: SemanticContext
    subject: SubjectFacts
    policy: SelectionPolicy
    coverage: BoundedCoverage
    candidates: tuple[CompletedCandidate, ...]
    relations: tuple[CompletedRelation, ...]
    code: CodeObservation


@dataclass(frozen=True)
class CandidateAssessment(Record):
    candidate_ref: str
    qualification: Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED", "AUDIT_ONLY"]
    applicability: Literal["APPLICABLE", "SUPERSEDED", "NOT_QUALIFIED"]
    reason: str
    material_unknown: bool


@dataclass(frozen=True)
class RelationAssessment(Record):
    relation_ref: str
    state: Literal["QUALIFIED", "EXCLUDED", "UNRESOLVED"]
    reason: str


@dataclass(frozen=True)
class CoverageAssessment(Record):
    state: Literal["SUFFICIENT", "INSUFFICIENT"]
    completed_checks: tuple[str, ...]
    missing_checks: tuple[str, ...]


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


@dataclass(frozen=True)
class AsOfSelectionResult(Record):
    inputs: SelectionBundle
    selection: SelectionOutcome | BlockingFailure
    declared_s3_evaluator_ref: str = EVALUATOR_REF
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)


def _validate_actual(candidate: CompletedCandidate, bundle: SelectionBundle) -> None:
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


def select_asof(bundle: SelectionBundle) -> SelectionOutcome | BlockingFailure:
    """Consume completed S1/S2 operations; never parse time or source JSON here."""
    try:
        policy, context, coverage = bundle.policy, bundle.context, bundle.coverage
        require(
            policy.version == "a03-policy-v0.1"
            and policy.evaluator_ref == EVALUATOR_REF
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
        proof_inventory: dict[str, TemporalProof] = {}
        for c in (*bundle.candidates, *notices):
            _validate_actual(c, bundle)
            for outcome in (c.actual.s1, c.actual.s2, c.subject_identity):
                if isinstance(outcome, BlockingFailure):
                    return outcome
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
        relation_assessments = _relations(bundle)
        accepted = [a for a in relation_assessments if a.state == "QUALIFIED"]
        unsupported_graph = len(accepted) > 1
        superseded = (
            {
                r.relation.old_assertion_ref
                for r in bundle.relations
                if any(
                    a.relation_ref == r.relation.relation_ref and a.state == "QUALIFIED"
                    for a in relation_assessments
                )
            }
            if not unsupported_graph
            else set()
        )
        assessments = []
        applicable = []
        qualifications = {c.ref: _qualification(c, policy) for c in bundle.candidates}
        qualified_values = {
            c.source.request.assertion.source_amount.value
            for c in bundle.candidates
            if qualifications[c.ref][0] == "QUALIFIED"
            and c.ref not in superseded
            and isinstance(c.source.request, IssuerBindingRequest)
        }
        for c in sorted(bundle.candidates, key=lambda c: c.ref):
            qualification, reason = qualifications[c.ref]
            material = (
                _material(c, bundle)
                and qualification in {"UNRESOLVED", "AUDIT_ONLY"}
                and c.ref not in superseded
            )
            amount = (
                c.source.request.assertion.source_amount.value
                if isinstance(c.source.request, IssuerBindingRequest)
                else c.source.request.displayed_value.value
            )
            if policy.target == "CONTENT_VALUE" and qualified_values == {amount}:
                material = False  # This lead cannot change this bounded content-value target.
            applicability: Applicability = (
                "SUPERSEDED"
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
                ],
                key=lambda a: (a.category, a.ref, a.reason),
            )
        )
        reason = "NONE"
        if unsupported_graph:
            reason = "UNSUPPORTED_RELATION_GRAPH"
        elif any(a.state == "UNRESOLVED" for a in relation_assessments):
            reason = "RELATION_UNQUALIFIED"
        elif any(a.material_unknown for a in assessments):
            reason = "MATERIAL_CANDIDATE_UNRESOLVED"
        elif any(
            isinstance(r.relation.new_assertion_ref, str)
            and qualifications[r.relation.new_assertion_ref][0] != "QUALIFIED"
            for r in bundle.relations
            if any(
                a.relation_ref == r.relation.relation_ref and a.state == "QUALIFIED"
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
        )
    except ContractError as error:
        return BlockingFailure(
            "CONTRACT_VIOLATION", str(error), (), str(error), bundle.context.origin, "SELECT_ASOF"
        )
