"""One closed diagnostic content serializer; no trusted observation/admission route.

Application interface separation is not a hostile-process security sandbox.
"""

import json
from dataclasses import dataclass, field

from pit_research_lab.domain.causal_derivation import (
    B03CodeObservation,
    B03FeatureSpec,
    B03Refusal,
    B03Result,
    FixedScalar6,
    QualifiedSyntheticUniverse,
    semantic_bytes,
)
from pit_research_lab.domain.causal_slice import evaluate_causal
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    NotApplicable,
    Record,
    SemanticContext,
)
from pit_research_lab.domain.ratio import FixedRatio

SCHEMA = "b03-diagnostic-candidate-v0.1"


@dataclass(frozen=True)
class ProjectionPolicy(Record):
    feature_keys: tuple[str, ...]
    missing_keys: tuple[str, ...]
    schema_ref: str = SCHEMA
    policy_ref: str = "B03-DIAGNOSTIC-PROJECTION-v0.1"


@dataclass(frozen=True)
class ResearchAudit(Record):
    result: B03Result


@dataclass(frozen=True)
class DiagnosticProjectionCandidate(Record):
    candidate_bytes: bytes
    audit: ResearchAudit
    admission_state: str = field(default="WITHHELD", init=False)
    admission_eligible: bool = field(default=False, init=False)
    diagnostic_only: bool = field(default=True, init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)


@dataclass(frozen=True)
class ProjectionWithheld(Record):
    code: str
    audit: ResearchAudit | NotApplicable


@dataclass(frozen=True)
class ProjectionBlocked(Record):
    code: str
    audit: ResearchAudit | NotApplicable


def _serialize_candidate(result: B03Result) -> bytes:
    rows = []
    for row in result.rows:
        features: dict[str, int | str | None] = {}
        for key, outcome in row.features:
            if outcome.state == "NOT_COMPUTABLE":
                features[key] = None
            elif type(outcome.value) is int:
                features[key] = outcome.value
            elif isinstance(outcome.value, (FixedScalar6, FixedRatio)):
                features[key] = outcome.value.decimal_text
            else:
                raise ValueError("INVALID_PROJECTED_VALUE")
        rows.append({"entity_id": row.entity_id, "features": features})
    content = {
        "candidate_schema_version": SCHEMA,
        "decision_cutoff": result.request.context.information_cutoff.source_text,
        "rows": rows,
    }
    return json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def project_candidate(
    fixed_context: SemanticContext,
    fixed_feature_specs: tuple[B03FeatureSpec, ...],
    completed: B03Result | B03Refusal | BlockingFailure,
    universe: QualifiedSyntheticUniverse | B03Refusal | BlockingFailure,
    policy: ProjectionPolicy,
    code: B03CodeObservation,
    /,
) -> DiagnosticProjectionCandidate | ProjectionWithheld | ProjectionBlocked:
    none = NotApplicable("B03", "NO_COMPLETED_AUDIT")
    if isinstance(completed, BlockingFailure):
        return ProjectionBlocked(completed.code, none)
    if isinstance(completed, B03Refusal):
        return ProjectionWithheld(completed.code, none)
    audit = ResearchAudit(completed)
    expected = ProjectionPolicy(
        tuple(sorted(s.key for s in completed.request.specifications)),
        completed.request.allowed_missing,
    )
    if (
        policy != expected
        or semantic_bytes(fixed_context) != semantic_bytes(completed.request.context)
        or semantic_bytes(tuple(sorted(fixed_feature_specs, key=lambda s: s.key)))
        != semantic_bytes(tuple(sorted(completed.request.specifications, key=lambda s: s.key)))
        or semantic_bytes(universe) != semantic_bytes(completed.universe)
        or completed.code != code
    ):
        return ProjectionBlocked("PROJECTION_CONTEXT_OR_POLICY_MISMATCH", audit)
    replay = evaluate_causal(completed.request, code)
    if isinstance(replay, BlockingFailure):
        return ProjectionBlocked(replay.code, audit)
    if isinstance(replay, B03Refusal):
        return ProjectionWithheld(replay.code, audit)
    if not isinstance(replay, B03Result) or semantic_bytes(completed) != semantic_bytes(replay):
        return ProjectionBlocked("FORGED_OR_MISMAPPED_B03_RESULT", audit)
    # Apply typed failure priority before any missing or fallback representation.
    if completed.failures:
        failure = next(
            (f for f in completed.failures if f.category == "CONTRACT_VIOLATION"),
            completed.failures[0],
        )
        return ProjectionBlocked(failure.code, audit)
    if isinstance(completed.universe, BlockingFailure):
        return ProjectionBlocked(completed.universe.code, audit)
    if isinstance(completed.universe, B03Refusal):
        return ProjectionWithheld(completed.universe.code, audit)
    if completed.universe.members != ("SYN-A", "SYN-B"):
        return ProjectionWithheld("UNSUPPORTED_UNIVERSE_CARDINALITY", audit)
    for row in completed.rows:
        for _key, outcome in row.features:
            if outcome.state in {"CONTRACT_VIOLATION", "OPERATIONAL_ERROR"}:
                return ProjectionBlocked(outcome.reason, audit)
    for row in completed.rows:
        for key, outcome in row.features:
            if outcome.state == "UNRESOLVED":
                return ProjectionWithheld("REQUIRED_FEATURE_UNRESOLVED", audit)
            if outcome.state == "NOT_COMPUTABLE" and key not in policy.missing_keys:
                return ProjectionWithheld("MISSING_NOT_PERMITTED", audit)
    try:
        content = _serialize_candidate(completed)
    except ValueError:
        return ProjectionBlocked("INVALID_PROJECTED_VALUE", audit)
    return DiagnosticProjectionCandidate(content, audit)
