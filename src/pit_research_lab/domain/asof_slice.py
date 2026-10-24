"""A03 composition; pure traversal separate from explicit read-only code observation."""

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

from pit_research_lab.domain.contracts import (
    BlockingFailure,
    CodePin,
    IssuerBindingRequest,
    NotApplicable,
    NotEvaluated,
    NumericContract,
    Record,
    SemanticContext,
    SubjectComparisonRequest,
    SubjectFacts,
    SubjectOperand,
)
from pit_research_lab.domain.information import compare_subjects
from pit_research_lab.domain.pit_slice import CodeObservation, evaluate_slice, observe_code
from pit_research_lab.domain.selection import (
    S3_CODE_PATHS,
    AsOfSelectionResult,
    BoundedCoverage,
    CandidateSource,
    CompletedCandidate,
    CompletedRelation,
    RelationSource,
    SelectionBundle,
    SelectionPolicy,
    select_asof,
)


@dataclass(frozen=True)
class AsOfRequest(Record):
    context: SemanticContext
    subject: SubjectFacts
    policy: SelectionPolicy
    coverage: BoundedCoverage
    candidates: tuple[CandidateSource, ...]
    relations: tuple[RelationSource, ...]


def observe_asof_code(repository: Path) -> CodeObservation:
    """Observe actual disk bytes, including S3; not source or runtime attestation."""
    base = observe_code(repository)
    data = tuple((repository / path).read_bytes() for path in S3_CODE_PATHS)
    return replace(
        base,
        observed_working_files=base.observed_working_files
        + tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(S3_CODE_PATHS, data, strict=True)
        ),
        byte_lengths=base.byte_lengths + tuple(len(body) for body in data),
    )


def evaluate_asof(request: AsOfRequest, code: CodeObservation, /) -> AsOfSelectionResult:
    """Compute every claim/notice with the existing S1/S2 owner, then select."""

    def complete(source: CandidateSource, anchor: SubjectFacts) -> CompletedCandidate:
        evidence = source.request
        actual = evaluate_slice(request.context, evidence, code)
        identity = NotApplicable("S1", "PROVIDER_REFERENCE_ONLY")
        if isinstance(evidence, IssuerBindingRequest):
            if not isinstance(source.subject, SubjectFacts):
                return CompletedCandidate(
                    source,
                    actual,
                    BlockingFailure(
                        "CONTRACT_VIOLATION",
                        "MISSING_CANDIDATE_SUBJECT",
                        (),
                        "MISSING_CANDIDATE_SUBJECT",
                        request.context.origin,
                        "COMPARE_SUBJECTS",
                    ),
                )
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
            return CompletedCandidate(source, actual, compare_subjects(request.context, comparison))
        return CompletedCandidate(source, actual, identity)

    candidates = tuple(
        sorted((complete(s, request.subject) for s in request.candidates), key=lambda c: c.ref)
    )
    relations = []
    for source in request.relations:
        notice = source.notice
        if isinstance(notice, NotEvaluated):
            relations.append(CompletedRelation(source.relation, notice))
        else:
            anchor = notice.subject if isinstance(notice.subject, SubjectFacts) else request.subject
            relations.append(CompletedRelation(source.relation, complete(notice, anchor)))
    bundle = SelectionBundle(
        request.context,
        request.subject,
        request.policy,
        request.coverage,
        candidates,
        tuple(sorted(relations, key=lambda r: r.relation.relation_ref)),
        code,
    )
    return AsOfSelectionResult(bundle, select_asof(bundle))
