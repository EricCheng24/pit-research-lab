"""Mechanical actual-only projection and observations of supplied immutable facts."""

from collections import Counter
from dataclasses import dataclass

from pit_research_lab.domain.contracts import (
    AssertionFacts,
    BlockingFailure,
    CaptureFacts,
    CompleteScopedProvenance,
    ContentFacts,
    ContentInventoryRequest,
    EvidenceOutcome,
    IdentityOutcome,
    IssuerBindingRequest,
    NotApplicable,
    OriginKnownValue,
    ProviderCaptureRequest,
    PublicationEventFacts,
    Record,
    RoleRef,
    S1Outcome,
    S1Request,
    ScopedPath,
    SubjectComparisonRequest,
    TimeProof,
    Visibility,
    require,
)


@dataclass(frozen=True)
class ActualInputAssociation(Record):
    operation: str
    context_ref: str
    requested_target_ref: str
    concrete_targets: tuple[str, ...]
    mode: str
    information_cutoff: str
    input_request: S1Request
    input_members: tuple[RoleRef, ...]
    source_captures: tuple[CaptureFacts, ...]
    source_events: tuple[PublicationEventFacts, ...]
    source_assertion_refs: tuple[str, ...]
    source_attempt_refs: tuple[str, ...]


@dataclass(frozen=True)
class ActualProbeRecord(Record):
    probe_ref: str
    operation: str
    input_members: tuple[RoleRef, ...]
    source_attempt_refs: tuple[str, ...]
    accepted_paths: tuple[ScopedPath, ...]
    rejected_support_refs: tuple[str, ...]
    supplied_capture_refs: tuple[str, ...]
    observed_capture_refs: tuple[str, ...]
    supplied_event_refs: tuple[str, ...]
    observed_event_refs: tuple[str, ...]
    supplied_assertion_refs: tuple[str, ...]
    observed_assertion_refs: tuple[str, ...]
    resource_attempts: tuple[str, ...]


@dataclass(frozen=True)
class ActualProjection(Record):
    projection_schema: str
    operation: str
    context_ref: str
    requested_target_ref: str
    concrete_targets: tuple[str, ...]
    mode: str
    information_cutoff: str
    system_outcome: S1Outcome
    provenance: CompleteScopedProvenance | NotApplicable
    probes: tuple[ActualProbeRecord, ...]


def observe_actual(actual, association, resource_attempts=()):
    """Record sets and paths, without constructing successful prohibition flags."""
    if isinstance(actual, BlockingFailure):
        paths, rejected, captures, events, assertions = (), (), (), (), ()
    else:
        paths = actual.provenance.accepted_paths
        rejected = tuple(a.supplied.support_ref for a in actual.provenance.rejected_attempts)
        events = tuple(e.event_ref for e in actual.publication_event_facts)
        captures = (
            tuple(c.observation_ref for c in actual.capture_facts)
            if isinstance(actual, EvidenceOutcome)
            else ()
        )
        assertions = actual.assertion_refs if isinstance(actual, IdentityOutcome) else ()
    return ActualProbeRecord(
        "SUPPLIED_SCOPE_AND_RESULT_SETS",
        association.operation,
        association.input_members,
        association.source_attempt_refs,
        paths,
        rejected,
        tuple(c.observation_ref for c in association.source_captures),
        captures,
        tuple(e.event_ref for e in association.source_events),
        events,
        association.source_assertion_refs,
        assertions,
        tuple(resource_attempts),
    )


def _contents(request):
    if isinstance(request, SubjectComparisonRequest):
        return request.left.contents + request.right.contents
    return (request.content,)


def _path_members(path):
    if path.path_role == "CAPTURE_ONLY" and path.target.target_kind == "PROVIDER_CAPTURE":
        require(isinstance(path.origin.object_id, OriginKnownValue), "UNOBSERVED_ACCEPTED_PATH")
        return (
            ("observations", path.target.target_ref),
            ("raw_assets", path.target.representation_ref),
            ("graph_edges", path.origin.object_id.value),
        )
    return (
        (
            "assertions" if path.target.target_kind == "ASSERTION" else "reports",
            path.target.target_ref,
        ),
        ("content_versions", path.target.content_version_ref),
        ("raw_assets", path.target.representation_ref),
        ("supports", path.support_ref),
        ("evidence", path.evidence_ref),
        ("publication_events", path.event_ref),
        ("time_proofs", path.time_proof_ref),
        *(("subjects", s) for s in path.target.subject_scope_refs),
    )


def _used_paths(paths):
    used = set()
    for path in paths:
        used.update(
            (path.visibility.value, role, ref)
            for role, ref in _path_members(path)
            if isinstance(ref, str)
        )
    return used


def project(actual, association, probes):
    """Closed projection; require actual observations and complete supplied-scope accounting."""
    require(type(probes) is tuple and len(probes) == 1, "MISSING_PROBE_COVERAGE")
    require(
        probes[0] == observe_actual(actual, association, probes[0].resource_attempts),
        "PROBE_OBSERVATION_MISMATCH",
    )
    if isinstance(actual, BlockingFailure):
        provenance = NotApplicable("S1", "BLOCKING_FAILURE")
    else:
        require(bool(association.input_members), "EMPTY_PROBE_COVERAGE")
        require(actual.context_ref == association.context_ref, "CONTEXT_ASSOCIATION_MISMATCH")
        provenance = actual.provenance
        require(
            provenance.input_members == association.input_members, "INCOMPLETE_SCOPE_ACCOUNTING"
        )
        used = _used_paths(provenance.accepted_paths)
        require(
            provenance.excluded_uses
            == tuple(m for m in association.input_members if m.key not in used),
            "INCOMPLETE_EXCLUDED_ACCOUNTING",
        )
        source_keys = {m.key for m in association.input_members}
        for path in provenance.accepted_paths:
            require(
                path.visibility in {Visibility.ACTIVE, Visibility.AUXILIARY},
                "FORBIDDEN_PATH_VISIBILITY",
            )
            for role, ref in _path_members(path):
                if isinstance(ref, str):
                    require(
                        (path.visibility.value, role, ref) in source_keys,
                        "UNOBSERVED_ACCEPTED_PATH",
                    )
            request = association.input_request
            source_bindings = (
                request.left.supports + request.right.supports
                if isinstance(request, SubjectComparisonRequest)
                else request.supports
                if isinstance(request, ContentInventoryRequest)
                else tuple(a.supplied for a in request.attempts)
                if isinstance(request, IssuerBindingRequest)
                else ()
            )
            if isinstance(path.support_ref, str):
                bindings = [
                    b
                    for b in source_bindings
                    if b.support_ref == path.support_ref and b.origin.visibility == path.visibility
                ]
                require(
                    len(bindings) == 1 and path.target == bindings[0].target,
                    "ACCEPTED_SOURCE_TUPLE_MISMATCH",
                )
                binding = bindings[0]
                for value, role in (
                    (binding.event, "publication_events"),
                    (binding.proof_candidate, "time_proofs"),
                ):
                    if isinstance(value, (PublicationEventFacts, TimeProof)):
                        ref = (
                            value.event_ref
                            if isinstance(value, PublicationEventFacts)
                            else value.proof_ref
                        )
                        require(
                            value.origin.visibility == path.visibility
                            and (value.origin.visibility.value, role, ref) in source_keys,
                            "UNOBSERVED_ACCEPTED_PATH",
                        )
                        require(
                            isinstance(value.origin.object_id, OriginKnownValue)
                            and value.origin.object_id.value == ref,
                            "UNOBSERVED_ACCEPTED_PATH",
                        )
                require(
                    (
                        path.evidence_ref,
                        path.event_ref,
                        path.time_proof_ref,
                    )
                    == (
                        binding.evidence_ref,
                        binding.event.event_ref
                        if isinstance(binding.event, PublicationEventFacts)
                        else binding.event,
                        binding.proof_candidate.proof_ref
                        if isinstance(binding.proof_candidate, TimeProof)
                        else binding.proof_candidate,
                    ),
                    "ACCEPTED_SOURCE_LINEAGE_MISMATCH",
                )
        contents: tuple[ContentFacts, ...] = _contents(association.input_request)
        cvs = {c.content_version_ref for c in contents}
        representations = {c.representation_ref for c in contents}
        source_events = tuple(
            sorted(
                (e for e in association.source_events if e.content_version_ref in cvs),
                key=lambda e: e.event_ref,
            )
        )
        require(actual.publication_event_facts == source_events, "EVENT_INVENTORY_MISMATCH")
        if isinstance(actual, IdentityOutcome):
            require(
                set(actual.assertion_refs) <= set(association.source_assertion_refs),
                "UNOBSERVED_ASSERTION",
            )
            require(
                isinstance(association.input_request, SubjectComparisonRequest),
                "OPERATION_ASSOCIATION_MISMATCH",
            )
            operands = association.input_request
            source_paths = Counter(
                ScopedPath(
                    binding.target,
                    binding.evidence_ref,
                    binding.support_ref,
                    binding.event.event_ref
                    if isinstance(binding.event, PublicationEventFacts)
                    else binding.event,
                    binding.proof_candidate.proof_ref
                    if isinstance(binding.proof_candidate, TimeProof)
                    else binding.proof_candidate,
                    binding.origin.visibility,
                    "IDENTITY_CONTENT",
                    binding.origin,
                )
                for operand in (operands.left, operands.right)
                if isinstance(operand.assertion, AssertionFacts)
                for binding in operand.supports
            )
            require(
                Counter(provenance.accepted_paths) == source_paths,
                "IDENTITY_PATH_COVERAGE_MISMATCH",
            )
            refs = tuple(
                o.assertion.assertion_ref
                for o in (operands.left, operands.right)
                if hasattr(o.assertion, "assertion_ref")
            )
            require(actual.assertion_refs == refs, "ASSERTION_IDENTITY_COLLAPSE")
            require(
                actual.source_assertions
                == tuple(
                    o.assertion
                    for o in (operands.left, operands.right)
                    if hasattr(o.assertion, "assertion_ref")
                ),
                "SOURCE_ASSERTION_CHANGED",
            )
            require(
                actual.content_version_refs
                == tuple(a.content_version_ref for a in actual.source_assertions),
                "SOURCE_CONTENT_IDENTITY_CHANGED",
            )
        else:
            require(
                isinstance(
                    association.input_request,
                    (IssuerBindingRequest, ProviderCaptureRequest, ContentInventoryRequest),
                ),
                "OPERATION_ASSOCIATION_MISMATCH",
            )
            require(
                actual.requested_tuple == association.input_request.requested,
                "TARGET_ASSOCIATION_MISMATCH",
            )
            require(
                actual.requested_tuple.target_ref in association.concrete_targets,
                "TARGET_ASSOCIATION_MISMATCH",
            )
            captures = tuple(
                sorted(
                    (
                        c
                        for c in association.source_captures
                        if c.representation_ref in representations
                    ),
                    key=lambda c: c.observation_ref,
                )
            )
            require(actual.capture_facts == captures, "CAPTURE_INVENTORY_MISMATCH")
            assessed = tuple(a.supplied.support_ref for a in actual.assessments)
            require(assessed == association.source_attempt_refs, "INCOMPLETE_ATTEMPT_ACCOUNTING")
            if isinstance(association.input_request, IssuerBindingRequest):
                require(
                    actual.supplied_bindings
                    == tuple(a.supplied for a in association.input_request.attempts),
                    "SUPPLIED_BINDING_CHANGED",
                )
                require(
                    tuple((a.requested, a.supplied) for a in actual.assessments)
                    == tuple((a.requested, a.supplied) for a in association.input_request.attempts),
                    "SUPPLIED_BINDING_CHANGED",
                )
            require(
                tuple(s.support_ref for s in actual.supplied_bindings) == assessed,
                "INCOMPLETE_ATTEMPT_ACCOUNTING",
            )
            require(
                tuple(a for a in actual.assessments if a.disposition == "REJECTED")
                == provenance.rejected_attempts,
                "INCOMPLETE_REJECTED_ACCOUNTING",
            )
            require(
                tuple(
                    a.supplied.support_ref
                    for a in actual.assessments
                    if a.disposition == "ACCEPTED"
                )
                == tuple(
                    p.support_ref
                    for p in provenance.accepted_paths
                    if p.path_role == "ISSUER_BINDING"
                ),
                "INCOMPLETE_ACCEPTED_ACCOUNTING",
            )
            content = association.input_request.content
            require(
                (
                    actual.source_attribution.issuer,
                    actual.source_attribution.provider,
                    actual.source_attribution.source,
                )
                == (content.issuer_ref, content.provider_ref, content.source_ref),
                "SOURCE_ATTRIBUTION_CHANGED",
            )
            if isinstance(association.input_request, ProviderCaptureRequest):
                request = association.input_request
                require(len(request.capture_edges) == 1, "PROVIDER_PATH_COVERAGE_MISMATCH")
                edge = request.capture_edges[0]
                na = NotApplicable("S1", "NO_SOURCE_REFERENCE")
                source_path = ScopedPath(
                    request.requested,
                    na,
                    na,
                    na,
                    na,
                    request.capture.origin.visibility,
                    "CAPTURE_ONLY",
                    edge.origin,
                )
                require(
                    request.requested.target_kind == "PROVIDER_CAPTURE"
                    and request.requested.target_ref == request.capture.observation_ref
                    and request.requested.representation_ref == request.capture.representation_ref
                    and edge.from_observation == request.capture.observation_ref
                    and edge.to_representation == request.capture.representation_ref
                    and edge.edge_role == "provider_lab_capture_only"
                    and edge.origin.visibility == request.capture.origin.visibility
                    and isinstance(edge.origin.object_id, OriginKnownValue)
                    and edge.origin.object_id.value == edge.edge_ref
                    and Counter(provenance.accepted_paths) == Counter((source_path,)),
                    "PROVIDER_PATH_COVERAGE_MISMATCH",
                )
    return ActualProjection(
        "wu01-actual-v0.1-CANDIDATE",
        association.operation,
        association.context_ref,
        association.requested_target_ref,
        association.concrete_targets,
        association.mode,
        association.information_cutoff,
        actual,
        provenance,
        probes,
    )
