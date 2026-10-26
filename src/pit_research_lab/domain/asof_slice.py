"""A03 composition; pure traversal separate from explicit read-only code observation."""

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

from pit_research_lab.domain.contracts import (
    CodePin,
    NotEvaluated,
    Record,
    SemanticContext,
    SubjectFacts,
)
from pit_research_lab.domain.pit_slice import CodeObservation, observe_code
from pit_research_lab.domain.selection import (
    S3_CODE_PATHS,
    AsOfSelectionResult,
    BoundedCoverage,
    CandidateSource,
    CompletedRelation,
    DiscoveryEvidence,
    RelationSource,
    SelectionBundle,
    SelectionPolicy,
    canonical_bundle,
    complete_candidate,
    reconstruction_ref,
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
    discovery: DiscoveryEvidence | NotEvaluated = NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT")


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

    candidates = tuple(
        sorted(
            (
                complete_candidate(request.context, s, request.subject, code)
                for s in request.candidates
            ),
            key=lambda c: c.ref,
        )
    )
    relations = []
    for source in request.relations:
        notice = source.notice
        if isinstance(notice, NotEvaluated):
            relations.append(CompletedRelation(source.relation, notice))
        else:
            anchor = notice.subject if isinstance(notice.subject, SubjectFacts) else request.subject
            relations.append(
                CompletedRelation(
                    source.relation, complete_candidate(request.context, notice, anchor, code)
                )
            )
    bundle = canonical_bundle(
        SelectionBundle(
            request.context,
            request.subject,
            request.policy,
            request.coverage,
            candidates,
            tuple(sorted(relations, key=lambda r: r.relation.relation_ref)),
            code,
            request.discovery,
        )
    )
    return AsOfSelectionResult(
        bundle, select_asof(bundle), request.policy.evaluator_ref, reconstruction_ref(bundle)
    )
