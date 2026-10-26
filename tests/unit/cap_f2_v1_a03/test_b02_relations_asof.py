"""Independent B02 counterexamples; synthetic construction, no Golden execution."""

import json
from dataclasses import replace
from hashlib import sha256
from itertools import permutations
from pathlib import Path

import pytest
from a03_inputs import (
    b02_invocation,
    b02_request,
    invocation,
    lead_notice,
    provider,
    revision,
    scoped_revision,
    source,
)

from pit_research_lab.domain.asof_slice import evaluate_asof, observe_asof_code
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    NotApplicable,
    NotEvaluated,
    Unknown,
    UnknownCause,
)
from pit_research_lab.domain.selection import (
    B02_EVALUATOR_REF,
    B02_POLICY_VERSION,
    EVALUATOR_REF,
    DiscoveryExclusion,
    RevisionScope,
    SelectionOutcome,
    select_asof,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_asof_code(ROOT)


@pytest.mark.parametrize("profile", ["legacy", "b02"])
@pytest.mark.parametrize("fault", ["s1", "s2", "identity", "both", "provenance"])
def test_direct_completed_results_are_not_authority(code, fault, profile):
    """A real owner result is the positive control; then mutate only its transport."""
    c = source(code, "FORGED", published="2025-07-10T14:00:00+08:00")
    if fault in {"s1", "both"}:
        c = source(code, "FORGED", unbound=True, historical=True)
    if fault == "identity":
        c = source(code, "FORGED", metric="other_metric")
    request = invocation(code, (c,))
    actual = evaluate_asof(b02_request(request) if profile == "b02" else request, code)
    assert select_asof(actual.inputs) == actual.selection
    completed = actual.inputs.candidates[0]
    evidence, identity = completed.actual, completed.subject_identity
    if fault in {"s1", "both"}:
        evidence = replace(evidence, s1=replace(evidence.s1, state="BOUND", reason="NONE"))
    if fault in {"s2", "both"}:
        evidence = replace(evidence, s2=replace(evidence.s2, state="SUPPORTED", reason="NONE"))
    if fault == "identity":
        identity = replace(identity, state="SAME", reason="NONE")
    if fault == "provenance":
        evidence = replace(
            evidence,
            s1=replace(evidence.s1, provenance=replace(evidence.s1.provenance, excluded_uses=())),
        )
    forged = replace(completed, actual=evidence, subject_identity=identity)
    result = select_asof(replace(actual.inputs, candidates=(forged,)))
    assert isinstance(result, BlockingFailure)
    assert result.code == "COMPLETED_OWNER_MISMATCH"


def test_unsupported_equal_amount_cannot_waive_historical_uncertainty(code):
    good = source(code, "GOOD")
    unsupported = source(code, "LEAD", unbound=True, historical=True)
    result = evaluate_asof(invocation(code, (good, unsupported), target="CONTENT_VALUE"), code)
    assert result.inputs.candidates[1].actual.s1.state == "UNRESOLVED"
    assert result.selection.state == "UNRESOLVED"
    # A supported equal-content lead, with time alone unresolved, is a valid neighbor.
    supported = source(code, "LEAD", unknown=True, historical=True)
    neighbor = evaluate_asof(invocation(code, (good, supported), target="CONTENT_VALUE"), code)
    assert neighbor.selection.state == "SELECTED"
    assert neighbor.selection.selected_value == 300


# The following expected states are independently specified by S3 §§3–5 and
# B02-AJ03…06. Builders supply source inputs, never expected evaluator answers.
EARLY = "2025-07-07T00:00:00+08:00"
LATE = "2025-07-14T00:00:00+08:00"


def evaluate(code, candidates=(), relations=(), **kwargs):
    return evaluate_asof(b02_invocation(code, candidates, relations, **kwargs), code)


def selected(result, value, refs):
    assert isinstance(result.selection, SelectionOutcome)
    assert result.selection.state == "SELECTED"
    assert result.selection.selected_value == value
    assert result.selection.selected_assertion_refs == refs
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert not result.admission_eligible and result.diagnostic_only
    assert result.declared_s3_evaluator_ref == B02_EVALUATOR_REF


def refusal(result, reason, category="CONTRACT_VIOLATION"):
    assert isinstance(result.selection, BlockingFailure)
    assert result.selection.category == category and result.selection.code == reason
    assert not result.admission_eligible


def unknown(origin):
    return Unknown(UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, origin)


def test_ir01_relation_independent_of_old_publication(code):
    old = source(code, "OLD", unbound=True, historical=True)
    new = source(code, "NEW", 310, "2025-07-10T14:00:00+08:00")
    notice = scoped_revision(code, old, new)
    lead = lead_notice(code, old)
    early = evaluate(code, (old, new), (notice,), leads=(lead,))
    late = evaluate(code, (old, new), (notice,), leads=(lead,), cutoff=LATE)
    assert early.selection.state == "UNRESOLVED"
    selected(late, 310, ("A-NEW",))
    relation = late.selection.relations[0]
    assert (relation.event_support, relation.notice_visibility, relation.relation_support) == (
        "SUPPORTED",
        "SUPPORTED",
        "SUPPORTED",
    )
    assert relation.effect == "SUPERSEDES"
    old_result = next(c for c in late.inputs.candidates if c.ref == "A-OLD")
    assert old_result.actual.s2.state == "UNRESOLVED"
    assert late.inputs.relations[0].notice.actual.s1.provenance.accepted_paths


@pytest.mark.parametrize(
    "cutoff,ref,value,state",
    [
        (EARLY, "A-OLD", 300, "EXCLUDED"),
        ("2025-07-10T14:00:00+08:00", "A-OLD", 300, "EXCLUDED"),
        (LATE, "A-NEW", 310, "QUALIFIED"),
    ],
)
def test_ir02_cutoff_and_publication_persistence(code, cutoff, ref, value, state):
    old = source(code, "OLD")
    new = source(code, "NEW", 310, "2025-07-10T14:00:00+08:00")
    result = evaluate(code, (old, new), (scoped_revision(code, old, new),), cutoff=cutoff)
    selected(result, value, (ref,))
    assert result.selection.relations[0].state == state
    assert (
        next(c for c in result.inputs.candidates if c.ref == "A-OLD").actual.s2.state == "SUPPORTED"
    )


@pytest.mark.parametrize("count", [1, 3])
def test_ir03_provider_copies_do_not_veto_or_vote(code, count):
    issuer = source(code, "ISSUER")
    result = evaluate(
        code,
        (issuer, *(provider(code, "P" + str(i)) for i in range(count))),
        target="CONTENT_VALUE",
    )
    selected(result, 300, ("A-ISSUER",))
    assert sum(a.reason == "PROVIDER_DISCREPANCY" for a in result.selection.candidates) == count
    assert all(
        a.qualification == "AUDIT_ONLY"
        for a in result.selection.candidates
        if a.candidate_ref != "A-ISSUER"
    )


@pytest.mark.parametrize(
    "unbound,amount,target,state",
    [
        (True, 300, "CONTENT_VALUE", "UNRESOLVED"),
        (False, 300, "CONTENT_VALUE", "SELECTED"),
        (False, 315, "CONTENT_VALUE", "UNRESOLVED"),
        (False, 300, "ATTRIBUTED_ASSERTION", "UNRESOLVED"),
    ],
)
def test_ir04_content_support_required_for_materiality_waiver(code, unbound, amount, target, state):
    good = source(code, "GOOD")
    lead = source(code, "LEAD", amount, unknown=not unbound, unbound=unbound, historical=True)
    result = evaluate(
        code, (good, lead), leads=(lead_notice(code, lead, unknown=True),), target=target
    )
    assert result.selection.state == state
    assert any(
        a.category == "HISTORICAL_LEAD" and a.ref == "LEAD-LEAD"
        for a in result.selection.research_only_audit
    )
    assert result.selection.coverage.state == "SUFFICIENT"


def test_ir04_historical_label_without_retained_notice_is_insufficient(code):
    good, lead = source(code, "GOOD"), source(code, "LEAD", 315, unknown=True, historical=True)
    result = evaluate(code, (good, lead), target="CONTENT_VALUE")
    assert result.selection.state == "UNRESOLVED"
    assert "MATERIALITY_EVIDENCE" in result.selection.coverage.missing_checks
    neighbor = evaluate(
        code, (good, lead), leads=(lead_notice(code, lead),), target="CONTENT_VALUE"
    )
    assert neighbor.selection.reason == "MATERIAL_CANDIDATE_UNRESOLVED"
    future = evaluate(
        code,
        (good, lead),
        leads=(lead_notice(code, lead, published="2025-07-10T14:00:00+08:00"),),
        target="CONTENT_VALUE",
    )
    selected(future, 300, ("A-GOOD",))
    assert any(a.reason == "FUTURE_ONLY_LEAD" for a in future.selection.research_only_audit)


def test_ir05_single_with_independent_completed_discovery(code):
    candidate = source(code, "ONE")
    result = evaluate(code, (candidate,))
    selected(result, 300, ("A-ONE",))
    assert result.selection.coverage.evidence_refs == ("DISCOVERY-B02",)
    assert result.inputs.discovery.pages == (("C:A-ONE",),)
    assert result.inputs.discovery.candidates == (candidate,)
    assert (
        result.inputs.candidates[0].actual.s1.provenance.accepted_paths[0].evidence_ref
        == "EVID-ONE"
    )


@pytest.mark.parametrize("gap", ["reference", "termination", "pages", "checks"])
def test_ir06_unsearched_empty_is_not_absence(code, gap):
    request = b02_invocation(
        code,
        (),
        terminated=gap != "termination",
        complete=gap != "checks",
        pages=() if gap == "pages" else None,
    )
    if gap == "reference":
        request = replace(request, discovery=NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT"))
    result = evaluate_asof(request, code)
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.reason == "COVERAGE_INSUFFICIENT"
    assert result.selection.coverage.state == "INSUFFICIENT"
    assert isinstance(result.selection.selected_value, NotEvaluated)
    assert evaluate(code).selection.state == "NO_QUALIFIED_CLAIM"


def test_ir07_sufficient_bounded_empty_not_global_absence(code):
    result = evaluate(code)
    assert result.selection.state == "NO_QUALIFIED_CLAIM"
    assert result.selection.reason == "NO_QUALIFIED_WITHIN_SCOPE"
    assert result.inputs.discovery.pages == ((),) and result.inputs.discovery.terminated
    assert result.selection.coverage.state == "SUFFICIENT"
    assert result.selection.selected_assertion_refs == ()
    assert isinstance(result.selection.selected_value, NotEvaluated)


def test_ir08_peer_issuer_conflict_is_not_latest_or_id_winner(code):
    old, new = source(code, "ZZZ"), source(code, "AAA", 315, "2025-07-05T12:00:00+08:00")
    for candidates in permutations((old, new)):
        result = evaluate(code, candidates)
        assert result.selection.state == "UNRESOLVED"
        assert result.selection.reason == "MATERIAL_CANDIDATE_UNRESOLVED"
        assert {a.candidate_ref for a in result.selection.candidates} == {"A-ZZZ", "A-AAA"}
    resolved = evaluate(
        code, (old, new), (scoped_revision(code, old, new, published="2025-07-05T13:00:00+08:00"),)
    )
    selected(resolved, 315, ("A-AAA",))


def test_ir09_different_subject_discovery_not_issuer_conflict(code):
    target = source(code, "ONE")
    foreign = source(code, "FOREIGN", 999, metric="other_financial_field")
    result = evaluate(
        code, (target, provider(code)), exclusions=(DiscoveryExclusion(foreign, "NOT_COMPARABLE"),)
    )
    selected(result, 300, ("A-ONE",))
    assert any(
        a.category == "DISCOVERY_EXCLUSION" and a.ref == "A-FOREIGN"
        for a in result.selection.research_only_audit
    )
    wrong = evaluate(code, (target, foreign))
    refusal(wrong, "SUBJECT_SCOPE_MISMATCH")
    forged_exclusion = evaluate(
        code, (target,), exclusions=(DiscoveryExclusion(source(code, "PEER"), "NOT_COMPARABLE"),)
    )
    refusal(forged_exclusion, "UNJUSTIFIED_DISCOVERY_EXCLUSION")


@pytest.mark.parametrize("scope_kind", ["FIELD", "DOCUMENT"])
def test_ir10_scope_maps_only_evidenced_fields(code, scope_kind):
    old, new = source(code, "OLD"), source(code, "NEW", 310)
    notice = scoped_revision(
        code, old, new, scope_kind=scope_kind, published="2025-07-05T12:00:00+08:00"
    )
    selected(evaluate(code, (old, new), (notice,)), 310, ("A-NEW",))
    # Same document event about another field is source-valid, not a target edge.
    other_old = source(code, "X0", metric="field_x")
    other_new = source(code, "X1", 310, metric="field_x")
    foreign_notice = scoped_revision(
        code,
        other_old,
        other_new,
        tag="X-NOTICE",
        scope_kind=scope_kind,
        published="2025-07-05T12:00:00+08:00",
    )
    unchanged = evaluate(code, (old,), (foreign_notice,))
    selected(unchanged, 300, ("A-OLD",))
    assert unchanged.selection.relations[0].effect == "OUT_OF_SCOPE"
    unmapped = scoped_revision(
        code,
        old,
        new,
        scope_kind="DOCUMENT",
        subjects=unknown(old.subject.origin),
        published="2025-07-05T12:00:00+08:00",
    )
    result = evaluate(code, (old, new), (unmapped,))
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.relations[0].reason == "RELATION_SCOPE_UNKNOWN"


def test_ir11_withdrawal_without_successor_does_not_restore(code):
    old, new = source(code, "OLD"), source(code, "NEW", 310)
    correction = scoped_revision(code, old, new, tag="R01", published="2025-07-04T12:00:00+08:00")
    withdrawal = scoped_revision(
        code, new, kind="WITHDRAWS", tag="WITHDRAW", published="2025-07-10T12:00:00+08:00"
    )
    selected(evaluate(code, (old, new), (correction, withdrawal)), 310, ("A-NEW",))
    result = evaluate(code, (old, new), (correction, withdrawal), cutoff=LATE)
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.reason == "RELATION_UNQUALIFIED"
    assert any(
        a.reason == "WITHDRAWAL_WITHOUT_RESTORATION" for a in result.selection.research_only_audit
    )
    assert {a.candidate_ref: a.applicability for a in result.selection.candidates} == {
        "A-OLD": "SUPERSEDED",
        "A-NEW": "WITHDRAWN",
    }
    assert result.selection.relations[1].effect == "WITHDRAWS"  # stable relation-ref order
    assert isinstance(withdrawal.relation.new_assertion_ref, NotApplicable)
    assert isinstance(result.selection.selected_value, NotEvaluated)


def test_ir11_event_supported_with_unknown_target_and_unknown_successor(code):
    old = source(code, "OLD")
    for endpoint in ("old", "new"):
        u = unknown(old.subject.origin)
        changes = {endpoint + "_assertion_ref": u, endpoint + "_version_ref": u}
        notice = scoped_revision(
            code, old, kind="WITHDRAWS", **changes, published="2025-07-05T12:00:00+08:00"
        )
        result = evaluate(code, (old,), (notice,))
        relation = result.selection.relations[0]
        assert relation.event_support == relation.notice_visibility == "SUPPORTED"
        assert relation.relation_support == relation.state == "UNRESOLVED"
        assert relation.reason == "RELATION_TARGET_UNKNOWN"
        assert result.selection.state == "UNRESOLVED"


def chain(code, *, values=(100, 110, 120), last_time="2025-07-05T12:00:00+08:00"):
    a, b, c = (source(code, "V" + str(i), value) for i, value in enumerate(values))
    return (a, b, c), (
        scoped_revision(code, a, b, tag="R01", published="2025-07-04T12:00:00+08:00"),
        scoped_revision(code, b, c, tag="R12", published=last_time),
    )


def test_ir12_two_step_direct_evidence_not_forged_shortcut(code):
    candidates, relations = chain(code)
    result = evaluate(code, candidates, relations)
    selected(result, 120, ("A-V2",))
    assert tuple(a.relation_ref for a in result.selection.relations) == ("REL-R01", "REL-R12")
    (path,) = result.selection.derived_reachability
    assert (path.old_assertion_ref, path.new_assertion_ref, path.direct_relation_path) == (
        "A-V0",
        "A-V2",
        ("REL-R01", "REL-R12"),
    )
    assert not any(r.relation_ref == "REL-R02" for r in result.selection.relations)
    # Forging a direct shortcut while retaining the actual r12 source bytes fails.
    forged = replace(
        relations[1],
        relation=replace(relations[1].relation, old_assertion_ref="A-V0", old_version_ref="CV-V0"),
    )
    refusal(evaluate(code, candidates, (relations[0], forged)), "RELATION_CONTENT_MISMATCH")


@pytest.mark.parametrize(
    "target,state", [("CONTENT_VALUE", "SELECTED"), ("ATTRIBUTED_ASSERTION", "UNRESOLVED")]
)
def test_ir13_equal_values_are_distinct_publications(code, target, state):
    a, b = source(code, "ONE"), source(code, "PEER")
    result = evaluate(code, (a, b), target=target)
    assert result.selection.state == state
    if state == "SELECTED":
        selected(result, 300, ("A-ONE", "A-PEER"))
    else:
        assert result.selection.reason == "ATTRIBUTION_UNRESOLVED"
    assert {c.source.request.content.content_version_ref for c in result.inputs.candidates} == {
        "CV-ONE",
        "CV-PEER",
    }


def test_ir14_equal_terminal_number_not_identity_cycle(code):
    candidates, relations = chain(code, values=(100, 110, 100))
    selected(evaluate(code, candidates, relations), 100, ("A-V2",))
    cycle = scoped_revision(
        code, candidates[1], candidates[0], tag="CYCLE", published="2025-07-05T12:00:00+08:00"
    )
    refusal(evaluate(code, candidates[:2], (relations[0], cycle)), "RELATION_IDENTITY_CYCLE")


def test_ir15_new_snapshot_new_reconstruction_old_replay_immutable(code):
    old = source(code, "OLD")
    request = b02_invocation(code, (old,))
    original = evaluate_asof(request, code)
    new = source(code, "EARLY", 305)
    notice = scoped_revision(code, old, new, published="2025-07-05T12:00:00+08:00")
    changed = evaluate(code, (old, new), (notice,), snapshot="NEW-EVIDENCE")
    selected(original, 300, ("A-OLD",))
    selected(changed, 305, ("A-EARLY",))
    assert original.reconstruction_ref != changed.reconstruction_ref
    assert original.inputs.context.evidence_set_ref != changed.inputs.context.evidence_set_ref
    assert evaluate_asof(request, code) == original


def test_ir16_fixed_trust_and_no_agent_export(code):
    result = evaluate(code, (source(code, "ONE"),))
    for key in ("trust", "diagnostic_only", "admission_eligible", "source_authentication"):
        with pytest.raises(ValueError, match="init=False"):
            replace(result, **{key: True})
    assert not hasattr(result, "to_agent_observation")
    assert result.selection.state == "SELECTED"


def test_ir17_relation_public_cannot_invent_observed_capture(code):
    old = source(code, "OLD")
    new = source(code, "NEW", 310)
    notice = scoped_revision(code, old, new, published="2025-07-05T12:00:00+08:00")
    selected(evaluate(code, (old, new), (notice,)), 310, ("A-NEW",))
    observed = evaluate(code, (old, new), (notice,), mode="prospective_observed")
    assert observed.selection.relations[0].notice_visibility == "NOT_ADMISSIBLE"
    assert observed.selection.state == "NO_QUALIFIED_CLAIM"
    # All three actual captures are complete by this later cutoff; observed positive.
    selected(
        evaluate(
            code,
            (old, new),
            (notice,),
            mode="prospective_observed",
            cutoff="2025-07-21T00:00:00+08:00",
        ),
        310,
        ("A-NEW",),
    )


def test_ir18_set_permutations_and_conflict_never_force_winner(code):
    candidates, relations = chain(code)
    request = b02_invocation(code, candidates, relations)
    expected = evaluate_asof(request, code)
    for cs in permutations(candidates):
        for rs in permutations(relations):
            changed = replace(
                request,
                candidates=cs,
                relations=rs,
                coverage=replace(request.coverage, checks=tuple(reversed(request.coverage.checks))),
            )
            assert evaluate_asof(changed, code) == expected
    conflicting = evaluate(code, (source(code, "ZZZ", 100), source(code, "AAA", 110)))
    assert conflicting.selection.state == "UNRESOLVED"


def rewritten_checks(coverage, **changes):
    """Attacker's internally consistent check JSON; retained evidence is not changed."""
    coverage = replace(coverage, **changes)
    checks = []
    for check in coverage.checks:
        raw = json.loads(check.evidence_bytes)
        raw.update(
            candidate_refs=list(coverage.evaluated_candidate_refs),
            relation_refs=list(coverage.evaluated_relation_refs),
        )
        data = json.dumps(raw, sort_keys=True).encode()
        checks.append(
            replace(
                check,
                evidence_bytes=data,
                origin=replace(
                    check.origin,
                    input_digest=replace(check.origin.input_digest, value=sha256(data).hexdigest()),
                ),
            )
        )
    return replace(coverage, checks=tuple(checks))


@pytest.mark.parametrize(
    "fault",
    [
        "candidate",
        "relation",
        "both_lists_and_json",
        "lead",
        "page",
        "termination",
        "digest",
        "check",
        "context",
    ],
)
def test_retained_discovery_cannot_be_rewritten_by_challenged_invocation(code, fault):
    old, new = source(code, "OLD"), source(code, "NEW", 310)
    relation = scoped_revision(code, old, new)
    request = b02_invocation(code, (old, new), (relation,), cutoff=LATE)
    selected(evaluate_asof(request, code), 310, ("A-NEW",))
    retained = request.discovery
    # Assertions below distinguish challenged transport vs pinned retained inputs.
    if fault == "candidate":
        request = replace(
            request,
            candidates=(old,),
            coverage=rewritten_checks(request.coverage, evaluated_candidate_refs=("A-OLD",)),
        )
        expected = "DISCOVERY_MEMBERSHIP_MISMATCH"
    elif fault == "relation":
        request = replace(
            request,
            relations=(),
            coverage=rewritten_checks(request.coverage, evaluated_relation_refs=()),
        )
        expected = "DISCOVERY_MEMBERSHIP_MISMATCH"
    elif fault == "both_lists_and_json":
        coverage = rewritten_checks(
            request.coverage, evaluated_candidate_refs=("A-OLD",), evaluated_relation_refs=()
        )
        # Even a coherently altered check reference is not the retained source descriptor.
        request = replace(
            request,
            candidates=(old,),
            relations=(),
            coverage=coverage,
            discovery=replace(
                retained,
                candidates=(old,),
                relations=(),
                checks=coverage.checks,
                pages=(("C:A-OLD",),),
            ),
        )
        expected = "DISCOVERY_SOURCE_MISMATCH"
    else:
        changes = {
            "lead": {"leads": (lead_notice(code, source(code, "LEAD", historical=True)),)},
            "page": {"pages": (("C:A-OLD",),)},
            "termination": {"terminated": False},
            "digest": {"raw_bytes": b"forged complete discovery"},
            "check": {"checks": ()},
            "context": {"context_ref": "OLD-CONTEXT"},
        }[fault]
        request = replace(request, discovery=replace(retained, **changes))
        expected = "DISCOVERY_SOURCE_MISMATCH"
    refusal(evaluate_asof(request, code), expected)


@pytest.mark.parametrize("status", ["NOT_PERFORMED", "FAILED"])
def test_independent_required_check_status(code, status):
    legacy = invocation(code, ())
    check = replace(legacy.coverage.checks[0], status=status)
    data = json.loads(check.evidence_bytes)
    data["status"] = status
    raw = json.dumps(data, sort_keys=True).encode()
    check = replace(
        check,
        evidence_bytes=raw,
        origin=replace(
            check.origin,
            input_digest=replace(check.origin.input_digest, value=sha256(raw).hexdigest()),
        ),
    )
    legacy = replace(
        legacy, coverage=replace(legacy.coverage, checks=(check, *legacy.coverage.checks[1:]))
    )
    result = evaluate_asof(b02_request(legacy), code)
    if status == "FAILED":
        refusal(result, "REQUIRED_OPERATION_FAILED", "OPERATIONAL_ERROR")
    else:
        assert result.selection.state == "UNRESOLVED"
        assert "CANDIDATE_DISCOVERY" in result.selection.coverage.missing_checks
    assert evaluate(code).selection.state == "NO_QUALIFIED_CLAIM"


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("branch", "UNSUPPORTED_RELATION_BRANCH"),
        ("merge", "UNSUPPORTED_RELATION_MERGE"),
        ("third", "EFFECTIVE_RELATION_LIMIT"),
        ("disconnected", "UNSUPPORTED_DISCONNECTED_LINEAGE"),
        ("duplicate_edge", "DUPLICATE_DIRECT_DECLARATION"),
    ],
)
def test_bounded_lineage_capability_refusals_have_two_edge_positive(code, fault, expected):
    candidates, relations = chain(code)
    selected(evaluate(code, candidates, relations), 120, ("A-V2",))
    a, b, c = candidates
    if fault == "branch":
        relations = (
            relations[0],
            scoped_revision(code, a, c, tag="BRANCH", published="2025-07-05T12:00:00+08:00"),
        )
    elif fault == "merge":
        relations = (
            scoped_revision(code, a, c, tag="MERGE", published="2025-07-04T12:00:00+08:00"),
            relations[1],
        )
    elif fault == "duplicate_edge":
        relations = (
            relations[0],
            scoped_revision(code, a, b, tag="COPY", published="2025-07-05T12:00:00+08:00"),
        )
    else:
        d = source(code, "V3", 130)
        candidates += (d,)
        if fault == "third":
            relations += (
                scoped_revision(code, c, d, tag="R23", published="2025-07-06T12:00:00+08:00"),
            )
        else:
            relations = (
                relations[0],
                scoped_revision(code, c, d, tag="R23", published="2025-07-05T12:00:00+08:00"),
            )
    result = evaluate(code, candidates, relations)
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.reason == expected
    assert not result.selection.selected_assertion_refs


def test_known_late_third_edge_does_not_enter_effective_budget(code):
    candidates, relations = chain(code)
    d = source(code, "V3", 130, published="2025-07-10T12:00:00+08:00")
    late = scoped_revision(
        code, candidates[-1], d, tag="R23", published="2025-07-10T12:00:00+08:00"
    )
    result = evaluate(code, (*candidates, d), (*relations, late))
    selected(result, 120, ("A-V2",))
    assert (
        next(r for r in result.selection.relations if r.relation_ref == "REL-R23").state
        == "EXCLUDED"
    )


@pytest.mark.parametrize(
    "fault", ["type", "scope", "endpoint", "version", "origin", "notice_result", "missing"]
)
def test_relation_declaration_and_completion_cannot_be_forged(code, fault):
    old, new = source(code, "OLD"), source(code, "NEW", 310)
    notice = scoped_revision(code, old, new, published="2025-07-05T12:00:00+08:00")
    good = evaluate(code, (old, new), (notice,))
    selected(good, 310, ("A-NEW",))
    if fault == "notice_result":
        completed = good.inputs.relations[0]
        actual = replace(
            completed.notice.actual, s1=replace(completed.notice.actual.s1, reason="FORGED")
        )
        completed = replace(completed, notice=replace(completed.notice, actual=actual))
        result = select_asof(replace(good.inputs, relations=(completed,)))
        assert isinstance(result, BlockingFailure) and result.code == "COMPLETED_OWNER_MISMATCH"
        return
    if fault == "missing":
        notice = replace(notice, notice=NotEvaluated("S3", "NO_NOTICE_SUPPLIED"))
        result = evaluate(code, (old, new), (notice,))
        assert result.selection.state == "UNRESOLVED"
        assert result.selection.relations[0].reason == "RELATION_EVIDENCE_ABSENT"
        return
    changes = {
        "type": {"kind": "REPLACES"},
        "scope": {"scope": replace(notice.relation.scope, subject_refs=("OTHER",))},
        "endpoint": {"new_assertion_ref": "A-OLD"},
        "version": {"new_version_ref": "WRONG"},
        "origin": {"origin": old.subject.metric.origin},
    }[fault]
    changed = replace(notice, relation=replace(notice.relation, **changes))
    refusal(evaluate(code, (old, new), (changed,)), "RELATION_CONTENT_MISMATCH")


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("version", "RELATION_VERSION_MISMATCH"),
        ("endpoint", "RELATION_ENDPOINT_MISMATCH"),
        ("field", "RELATION_FIELD_MISMATCH"),
        ("document", "RELATION_DOCUMENT_MISMATCH"),
    ],
)
def test_source_valid_but_contradictory_known_endpoint_even_if_late(code, fault, expected):
    old, new = source(code, "OLD"), source(code, "NEW", 310, published="2025-07-10T14:00:00+08:00")
    kwargs = {
        "version": {"new_version_ref": "WRONG"},
        "endpoint": {"new_assertion_ref": "MISSING"},
        "field": {
            "scope": RevisionScope(
                "FIELD", ("WRONG-FIELD",), "CV-OLD", "CV-NEW", old.subject.origin
            )
        },
        "document": {
            "scope": RevisionScope(
                "FIELD", (old.subject.subject_ref,), "CV-WRONG", "CV-NEW", old.subject.origin
            )
        },
    }[fault]
    notice = scoped_revision(code, old, new, **kwargs)
    refusal(evaluate(code, (old, new), (notice,)), expected)
    selected(evaluate(code, (old, new), (scoped_revision(code, old, new),)), 300, ("A-OLD",))


@pytest.mark.parametrize("kind", ["CORRECTS", "REPLACES", "REISSUES", "RESTATEMENT"])
def test_four_kind_interpretation_not_numeric_revision_inference(code, kind):
    old = source(code, "OLD")
    new = source(code, "NEW", 300 if kind == "REISSUES" else 310)
    relation = scoped_revision(code, old, new, kind=kind, published="2025-07-05T12:00:00+08:00")
    result = evaluate(code, (old, new), (relation,), target="CONTENT_VALUE")
    if kind in {"CORRECTS", "REPLACES"}:
        selected(result, 310, ("A-NEW",))
    elif kind == "REISSUES":
        selected(result, 300, ("A-NEW", "A-OLD"))
        assert result.selection.relations[0].effect == "REISSUES"
        attributed = evaluate(code, (old, new), (relation,))
        assert attributed.selection.reason == "ATTRIBUTION_UNRESOLVED"
    else:
        assert result.selection.state == "UNRESOLVED"
        assert result.selection.relations[0].reason == "UNSUPPORTED_RELATION_KIND_NO_ROLLBACK"


@pytest.mark.parametrize("profile", ["legacy", "b02"])
def test_explicit_version_dispatch_and_legacy_values(code, profile):
    old, new = source(code, "OLD"), source(code, "NEW", 310, "2025-07-10T14:00:00+08:00")
    relation = revision(code, old, new) if profile == "legacy" else scoped_revision(code, old, new)
    builder = invocation if profile == "legacy" else b02_invocation
    for cutoff, expected in [(EARLY, 300), (LATE, 310)]:
        request = builder(code, (old, new), (relation,), cutoff=cutoff)
        result = evaluate_asof(request, code)
        assert result.selection.selected_value == expected
        assert result.inputs.policy.version == (
            "a03-policy-v0.1" if profile == "legacy" else B02_POLICY_VERSION
        )
        assert result.declared_s3_evaluator_ref == (
            EVALUATOR_REF if profile == "legacy" else B02_EVALUATOR_REF
        )
    request = builder(code, (old, new), (relation,), cutoff=LATE)
    forged = replace(request, policy=replace(request.policy, evaluator_ref="UNVERSIONED"))
    refusal(evaluate_asof(forged, code), "UNSUPPORTED_SELECTION_POLICY")
    mismatch = scoped_revision(code, old, new) if profile == "legacy" else revision(code, old, new)
    wrong = builder(code, (old, new), (mismatch,), cutoff=LATE)
    refusal(
        evaluate_asof(wrong, code),
        "LEGACY_RELATION_PROFILE_MISMATCH"
        if profile == "legacy"
        else "B02_RELATION_PROFILE_MISMATCH",
    )


@pytest.mark.parametrize("inventory", ["candidates", "notices", "leads_exclusions"])
@pytest.mark.parametrize("count", [32, 33])
def test_declared_finite_inventory_boundary(code, inventory, count):
    if inventory == "candidates":
        candidates = tuple(source(code, "LIMIT-" + str(i)) for i in range(count))
        result = evaluate(code, candidates, target="CONTENT_VALUE")
    elif inventory == "notices":
        old = source(code, "OLD")
        new = source(code, "NEW", 310, published="2025-07-10T14:00:00+08:00")
        notices = tuple(scoped_revision(code, old, new, tag="LATE-" + str(i)) for i in range(count))
        result = evaluate(code, (old, new), notices)
    else:
        candidate = source(code, "ONE")
        excluded = tuple(
            DiscoveryExclusion(source(code, "X-" + str(i), metric="other_metric"), "NOT_COMPARABLE")
            for i in range(count)
        )
        result = evaluate(code, (candidate,), exclusions=excluded)
    if count == 33:
        assert result.selection.state == "UNRESOLVED"
        assert result.selection.reason == "INPUT_INVENTORY_LIMIT"
        assert not result.selection.selected_assertion_refs
    else:
        assert result.selection.state == "SELECTED"
        assert result.selection.selected_value == 300


@pytest.fixture
def derived_builders(monkeypatch):
    """Load input-only builders; no source replacement or downstream-owner mocks."""
    import importlib.util
    import sys

    modules = []
    for folder, name in [("cap_f2_v1_a04", "a04_inputs"), ("cap_f2_v1_a05", "a05_inputs")]:
        module = sys.modules.get(name)
        if module is None:
            spec = importlib.util.spec_from_file_location(
                name, ROOT / "tests/unit" / folder / (name + ".py")
            )
            module = importlib.util.module_from_spec(spec)
            monkeypatch.setitem(sys.modules, name, module)
            spec.loader.exec_module(module)
        modules.append(module)
    return tuple(modules)


def versioned_slots(code, slots):
    """New snapshots with newly built scoped notice bytes; legacy requests untouched."""
    changed = []
    for slot in slots:
        req = slot.request
        relations = tuple(
            scoped_revision(code, req.candidates[0], req.candidates[1], tag="B02-" + slot.slot_ref)
            for _ in req.relations
        )
        req = replace(req, relations=relations)
        changed.append(replace(slot, request=b02_request(req)))
    return tuple(changed)


@pytest.mark.parametrize(
    "delta,expected_sum,rounded",
    [
        (None, 56_799_290, "0.308955"),
        (10, 56_799_300, "0.308955"),
        (100, 56_799_390, "0.308956"),
    ],
)
def test_b02_actual_a03_a04_a05_values_and_lineage(derived_builders, delta, expected_sum, rounded):
    from pit_research_lab.domain.derived_slice import evaluate_derived
    from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code

    _, a05 = derived_builders
    observation = observe_ratio_code(ROOT)
    spec, sum_spec, legacy = a05.inputs(observation, revision_delta=delta, cutoff=LATE)
    slots = versioned_slots(observation.upstream_a04, legacy)
    result = evaluate_ratio(spec, sum_spec, slots, observation)
    assert result.upstream_a04 == evaluate_derived(sum_spec, slots, observation.upstream_a04)
    assert result.upstream_a04.outcome.value == expected_sum
    assert result.outcome.value.decimal_text == rounded
    assert result.research_only_audit.exact_fraction == (17_548_413 + (delta or 0), expected_sum)
    for dependency in result.upstream_a04.dependencies:
        assert dependency.actual == evaluate_asof(dependency.slot.request, observation.upstream_a04)
        assert dependency.actual.selection.state == "SELECTED"
        assert dependency.actual.declared_s3_evaluator_ref == B02_EVALUATOR_REF
    assert not result.admission_eligible and result.diagnostic_only
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"


@pytest.mark.parametrize(
    "kind,state,reason",
    [
        ("conflict", "UNRESOLVED", "DEPENDENCY_UNRESOLVED"),
        ("absence", "NOT_COMPUTABLE", "UPSTREAM_REQUIRED_INPUT_ABSENT"),
        ("unsearched", "UNRESOLVED", "DEPENDENCY_UNRESOLVED"),
        ("withdrawal", "UNRESOLVED", "DEPENDENCY_UNRESOLVED"),
        ("failed", "OPERATIONAL_ERROR", "REQUIRED_OPERATION_FAILED"),
        ("tampered", "CONTRACT_VIOLATION", "DISCOVERY_SOURCE_MISMATCH"),
    ],
)
def test_b02_actual_downstream_nonvalues(derived_builders, kind, state, reason):
    from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code

    _, a05 = derived_builders
    observation = observe_ratio_code(ROOT)
    kwargs = {"third": "conflict"} if kind == "conflict" else {}
    if kind in {"absence", "unsearched"}:
        kwargs = {"third": "absent", "complete": kind != "unsearched"}
    if kind == "failed":
        kwargs = {"check_status": "FAILED"}
    if kind == "withdrawal":
        kwargs = {"revision_delta": 10, "cutoff": LATE}
    spec, sum_spec, legacy = a05.inputs(observation, **kwargs)
    slots = versioned_slots(observation.upstream_a04, legacy)
    if kind == "withdrawal":
        req = slots[2].request
        notice = scoped_revision(
            observation.upstream_a04,
            req.candidates[1],
            kind="WITHDRAWS",
            tag="B02-WITHDRAW",
            published="2025-07-11T12:00:00+08:00",
        )
        req = b02_request(replace(req, relations=(*req.relations, notice)))
        slots = (*slots[:2], replace(slots[2], request=req))
    if kind == "tampered":
        req = slots[2].request
        req = replace(req, discovery=replace(req.discovery, raw_bytes=b"forged completion"))
        slots = (*slots[:2], replace(slots[2], request=req))
    result = evaluate_ratio(spec, sum_spec, slots, observation)
    assert result.outcome.state == state and result.outcome.reason == reason
    assert isinstance(result.outcome.value, NotEvaluated)
    assert isinstance(result.upstream_a04.outcome.value, NotEvaluated)
    assert not result.admission_eligible


def test_b02_downstream_audit_only_noninterference(derived_builders):
    from pit_research_lab.domain.ratio import _evaluate_completed
    from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code
    from pit_research_lab.domain.selection import ResearchAuditEntry

    _, a05 = derived_builders
    observation = observe_ratio_code(ROOT)
    spec, sum_spec, legacy = a05.inputs(observation)
    slots = versioned_slots(observation.upstream_a04, legacy)
    original = evaluate_ratio(spec, sum_spec, slots, observation)
    upstream = original.upstream_a04
    changed = []
    for dependency in upstream.dependencies:
        s3 = dependency.actual
        selection = replace(
            s3.selection,
            research_only_audit=s3.selection.research_only_audit
            + (ResearchAuditEntry("FUTURE_ONLY", "FUTURE-REVISION", "RESEARCH_AUDIT_ONLY"),),
        )
        changed.append(replace(dependency, actual=replace(s3, selection=selection)))
    annotated = replace(upstream, dependencies=tuple(changed))
    result = _evaluate_completed(
        spec, sum_spec, slots, observation, annotated, annotations=("future conflict audit only",)
    )
    assert result.outcome == original.outcome
    assert result.diagnostic_preview_bytes == original.diagnostic_preview_bytes
    assert result.realization_ref == original.realization_ref
    assert not hasattr(result, "to_agent_observation")


def test_legacy_and_b02_mixed_dependency_versions_refuse(derived_builders):
    from pit_research_lab.domain.derived_slice import evaluate_derived, observe_derived_code

    a04, _ = derived_builders
    observation = observe_derived_code(ROOT)
    spec, legacy = a04.family(observation)
    mixed = (*versioned_slots(observation, legacy)[:2], legacy[2])
    result = evaluate_derived(spec, mixed, observation)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert result.outcome.reason == "MIXED_RECONSTRUCTION_CONTEXT"
    assert evaluate_derived(spec, legacy, observation).outcome.value == 56_799_290


@pytest.mark.parametrize("late", [False, True])
def test_cycle_cannot_hide_behind_branch_or_late_notice(code, late):
    candidates, relations = chain(code)
    a, b, c = candidates
    cycle = scoped_revision(
        code,
        b,
        a,
        tag="R10",
        published="2025-07-10T12:00:00+08:00" if late else "2025-07-05T12:00:00+08:00",
    )
    branch = scoped_revision(code, a, c, tag="ZZ-BRANCH", published="2025-07-05T12:00:00+08:00")
    refusal(evaluate(code, candidates, (relations[0], cycle, branch)), "RELATION_IDENTITY_CYCLE")
    selected(evaluate(code, candidates, relations), 120, ("A-V2",))


def test_unidentified_intermediate_does_not_manufacture_path(code):
    old, new = source(code, "OLD", 100), source(code, "NEW", 120)
    u = unknown(old.subject.origin)
    first = scoped_revision(
        code,
        old,
        new,
        tag="PARTIAL01",
        new_assertion_ref=u,
        new_version_ref=u,
        published="2025-07-04T12:00:00+08:00",
    )
    second = scoped_revision(
        code,
        old,
        new,
        tag="PARTIAL12",
        old_assertion_ref=u,
        old_version_ref=u,
        published="2025-07-05T12:00:00+08:00",
    )
    result = evaluate(code, (old, new), (first, second))
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.derived_reachability == ()
    assert all(
        r.event_support == "SUPPORTED" and r.reason == "RELATION_TARGET_UNKNOWN"
        for r in result.selection.relations
    )
    candidates, relations = chain(code)
    selected(evaluate(code, candidates, relations), 120, ("A-V2",))


@pytest.mark.parametrize("count", [32, 33])
def test_standalone_discovered_lead_inventory_never_disappears(code, count):
    leads = tuple(
        lead_notice(
            code,
            source(code, "CLUE-" + str(i), unknown=True, historical=True),
            tag="LEAD-NOTICE-" + str(i),
        )
        for i in range(count)
    )
    result = evaluate(code, (source(code, "ONE"),), leads=leads)
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.reason == (
        "INPUT_INVENTORY_LIMIT" if count == 33 else "MATERIAL_CANDIDATE_UNRESOLVED"
    )
    assert (
        len([a for a in result.selection.research_only_audit if a.category == "HISTORICAL_LEAD"])
        == count
    )


def test_contradictory_support_identifier_across_source_valid_claims(code):
    from wu01_inputs import synthetic_scope

    old, peer = source(code, "ONE"), source(code, "TWO")
    attempt = peer.request.attempts[0]
    original = attempt.supplied
    ref = old.request.attempts[0].supplied.support_ref
    origin = replace(
        original.origin,
        object_id=replace(original.origin.object_id, value=ref),
        envelope_pointer=original.origin.envelope_pointer.replace(original.support_ref, ref),
    )
    binding = replace(original, support_ref=ref, origin=origin)
    members = tuple(
        replace(m, object_ref=ref) if m.role == "supports" else m
        for m in peer.request.scope.input_members
    )
    req = replace(peer.request, attempts=(replace(attempt, supplied=binding),))
    req = replace(
        req, scope=synthetic_scope(replace(req.scope, input_members=members), supports=(binding,))
    )
    peer = replace(peer, request=req)
    result = evaluate(code, (old, peer), target="CONTENT_VALUE")
    assert all(c.actual.s1.state == "BOUND" for c in result.inputs.candidates)
    refusal(result, "CONTRADICTORY_SUPPORT_IDENTITY")
    selected(
        evaluate(code, (old, source(code, "TWO")), target="CONTENT_VALUE"), 300, ("A-ONE", "A-TWO")
    )


def test_failed_lead_operation_preserves_s2_operational_failure(code, monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError

    from pit_research_lab.domain import temporal

    original = temporal._publication
    good = source(code, "GOOD")
    candidate = source(code, "CLUE", unknown=True, historical=True)
    lead = lead_notice(code, candidate, tag="OP-LEAD")
    request = b02_invocation(code, (good, candidate), leads=(lead,))

    def injected(proof, cutoff):
        if proof.proof_ref == "TP-OP-LEAD":
            raise ZoneInfoNotFoundError("synthetic missing zone infrastructure")
        return original(proof, cutoff)

    with monkeypatch.context() as m:
        m.setattr(temporal, "_publication", injected)
        refusal(evaluate_asof(request, code), "ZONE_DATA_UNAVAILABLE", "OPERATIONAL_ERROR")
    assert evaluate_asof(request, code).selection.state == "UNRESOLVED"


def test_ordered_discovery_pages_are_pinned_not_sorted(code):
    first, second = source(code, "ONE"), source(code, "TWO")
    pages = (("C:A-TWO",), ("C:A-ONE",))
    request = b02_invocation(code, (first, second), pages=pages, target="CONTENT_VALUE")
    original = evaluate_asof(request, code)
    selected(original, 300, ("A-ONE", "A-TWO"))
    assert original.inputs.discovery.pages == pages
    changed = replace(request, discovery=replace(request.discovery, pages=tuple(reversed(pages))))
    refusal(evaluate_asof(changed, code), "DISCOVERY_SOURCE_MISMATCH")
    # A genuinely new independently constructed receipt has a different identity.
    another = evaluate(
        code,
        (first, second),
        pages=tuple(reversed(pages)),
        target="CONTENT_VALUE",
        snapshot="DIFFERENT-PAGE-RECEIPT",
    )
    selected(another, 300, ("A-ONE", "A-TWO"))
    assert another.reconstruction_ref != original.reconstruction_ref


@pytest.mark.parametrize(
    "field", ["context_ref", "mode", "information_cutoff", "source_provenance"]
)
def test_direct_b02_full_context_and_provenance_guard(code, field):
    original = evaluate(code, (source(code, "ONE"),))
    selected(original, 300, ("A-ONE",))
    candidate = original.inputs.candidates[0]
    actual = candidate.actual
    if field == "source_provenance":
        actual = replace(actual, s2=replace(actual.s2, accepted_binding_refs=("FOREIGN-SUPPORT",)))
        reason = "COMPLETED_OWNER_MISMATCH"
    else:
        change = {
            "context_ref": "OTHER",
            "mode": "prospective_observed",
            "information_cutoff": replace(actual.context.information_cutoff, source_text=LATE),
        }[field]
        actual = replace(actual, context=replace(actual.context, **{field: change}))
        reason = "MIXED_CONTEXT_OR_INPUT"
    result = select_asof(replace(original.inputs, candidates=(replace(candidate, actual=actual),)))
    assert isinstance(result, BlockingFailure) and result.code == reason


def test_source_supported_notice_with_unknown_time_cannot_supersede(code):
    from pit_research_lab.domain.selection import relation_proposition

    old, new = source(code, "OLD"), source(code, "NEW", 310)
    relation = scoped_revision(code, old, new, published="2025-07-05T12:00:00+08:00")
    selected(evaluate(code, (old, new), (relation,)), 310, ("A-NEW",))
    notice = source(
        code,
        "B02-NOTICE",
        1,
        metric=relation_proposition(relation.relation),
        unit="relation_declaration",
        unknown=True,
    )
    result = evaluate(
        code, (old, new), (replace(relation, notice=notice),), snapshot="UNKNOWN-NOTICE-TIME"
    )
    assessed = result.selection.relations[0]
    assert assessed.event_support == assessed.relation_support == "SUPPORTED"
    assert assessed.notice_visibility == "UNRESOLVED"
    assert assessed.state == result.selection.state == "UNRESOLVED"
    assert all(a.applicability != "SUPERSEDED" for a in result.selection.candidates)


# Targeted Remediation-1: expectations precede source repairs. This matrix is
# grounded in S3 §§3.2/3.4/5.4, Golden A07-C04 and the owner's R1/R2 contract.
R1_WITHDRAWAL_TIME = "2025-07-10T12:00:00+08:00"
R1_BEFORE = "2025-07-10T11:59:59+08:00"
R1_AFTER = "2025-07-10T12:00:01+08:00"


def remediation_observation(result):
    """Print actual synthetic owner/selection metadata, never financial source bodies."""
    outcome = result.selection
    data = {
        "cutoff": result.inputs.context.information_cutoff.source_text,
        "selection": {
            "state": getattr(
                outcome, "state", outcome.category if isinstance(outcome, BlockingFailure) else ""
            ),
            "reason": outcome.code if isinstance(outcome, BlockingFailure) else outcome.reason,
            "value": str(getattr(outcome, "selected_value", "NOT_SELECTED")),
            "refs": getattr(outcome, "selected_assertion_refs", ()),
        },
        "claims": [
            {
                "ref": c.ref,
                "s1": c.actual.s1.state,
                "s2": c.actual.s2.state,
                "identity": c.subject_identity.state,
            }
            for c in result.inputs.candidates
        ],
        "notices": [
            {
                "relation": r.relation.relation_ref,
                "notice": r.notice.ref,
                "version": r.notice.source.request.content.content_version_ref,
                "s1": r.notice.actual.s1.state,
                "s2": r.notice.actual.s2.state,
                "identity": r.notice.subject_identity.state,
            }
            for r in result.inputs.relations
            if not isinstance(r.notice, NotEvaluated)
        ],
    }
    if isinstance(outcome, SelectionOutcome):
        data["applicability"] = {a.candidate_ref: a.applicability for a in outcome.candidates}
        data["relations"] = [
            {
                "ref": r.relation_ref,
                "state": r.state,
                "reason": r.reason,
                "event": r.event_support,
                "visibility": r.notice_visibility,
                "support": r.relation_support,
                "effect": r.effect,
            }
            for r in outcome.relations
        ]
        data["audit"] = [(a.category, a.ref, a.reason) for a in outcome.research_only_audit]
        data["coverage"] = outcome.coverage.state
    print("REMEDIATION_OWNER_OBSERVATION " + json.dumps(data, sort_keys=True))


def remediation_evidence(result, expected_visibility):
    """Establish source-valid public-owner preconditions independently of final state."""
    for candidate in result.inputs.candidates:
        assert candidate.actual.s1.state == "BOUND"
        assert candidate.actual.s2.state == "SUPPORTED"
        assert candidate.subject_identity.state == "SAME"
    for item in result.inputs.relations:
        notice = item.notice
        assert notice.actual.s1.state == "BOUND" and notice.subject_identity.state == "SAME"
        assert notice.actual.s2.state == expected_visibility.get(
            item.relation.relation_ref, "SUPPORTED"
        )
        assert item.relation.origin == notice.source.subject.metric.origin
        assert item.relation.origin.input_digest.value == notice.source.request.content.raw_sha256
        (path,) = notice.actual.s1.provenance.accepted_paths
        assert path.target.target_ref == notice.ref
        assert path.target.content_version_ref == notice.source.request.content.content_version_ref
        assert path.support_ref == notice.source.request.attempts[0].supplied.support_ref
        assert path.evidence_ref == notice.source.request.attempts[0].supplied.evidence_ref
        assert notice.actual.s2.accepted_binding_refs == (path.support_ref,)
    assert result.inputs.discovery.terminated
    assert len(result.inputs.coverage.checks) == 3
    assert all(check.status == "COMPLETED" for check in result.inputs.coverage.checks)
    assert select_asof(result.inputs) == result.selection


def remediation_family(code, *, target="old", kind="CORRECTS", cutoff=R1_AFTER):
    old = source(code, "R1-A0", 300, "2025-07-03T10:00:00+08:00")
    new = source(code, "R1-A1", 310, "2025-07-04T10:00:00+08:00")
    correction = scoped_revision(
        code, old, new, kind=kind, tag="R1-CORRECTION", published="2025-07-05T10:00:00+08:00"
    )
    withdrawal = scoped_revision(
        code,
        old if target == "old" else new,
        kind="WITHDRAWS",
        tag="R1-WITHDRAWAL",
        published=R1_WITHDRAWAL_TIME,
    )
    return b02_invocation(code, (old, new), (correction, withdrawal), cutoff=cutoff)


@pytest.mark.parametrize("kind", ["CORRECTS", "REPLACES"])
@pytest.mark.parametrize("target", ["old", "current"])
@pytest.mark.parametrize(
    "cutoff,visible",
    [
        (R1_BEFORE, False),
        (R1_WITHDRAWAL_TIME, False),
        (R1_AFTER, True),
    ],
)
def test_remediation_r1_withdrawal_applicability(code, kind, target, cutoff, visible):
    request = remediation_family(code, target=target, kind=kind, cutoff=cutoff)
    result = evaluate_asof(request, code)
    remediation_observation(result)
    visibility = "SUPPORTED" if visible else "NOT_ADMISSIBLE"
    remediation_evidence(result, {"REL-R1-WITHDRAWAL": visibility})
    assert result.selection.coverage.state == "SUFFICIENT"
    correction, withdrawal = result.selection.relations
    assert correction.relation_ref == "REL-R1-CORRECTION" and correction.effect == "SUPERSEDES"
    assert withdrawal.relation_ref == "REL-R1-WITHDRAWAL"
    assert withdrawal.event_support == withdrawal.relation_support == "SUPPORTED"
    assert withdrawal.notice_visibility == visibility
    assert withdrawal.state == ("QUALIFIED" if visible else "EXCLUDED")
    assert withdrawal.effect == ("WITHDRAWS" if visible else "NONE")
    applicability = {a.candidate_ref: a.applicability for a in result.selection.candidates}
    if visible and target == "current":
        assert result.selection.state == "UNRESOLVED"
        assert result.selection.reason == "RELATION_UNQUALIFIED"
        assert result.selection.selected_assertion_refs == ()
        assert isinstance(result.selection.selected_value, NotEvaluated)
        assert applicability == {"A-R1-A0": "SUPERSEDED", "A-R1-A1": "WITHDRAWN"}
        assert any(
            a.reason == "WITHDRAWAL_WITHOUT_RESTORATION"
            for a in result.selection.research_only_audit
        )
    else:
        selected(result, 310, ("A-R1-A1",))
        assert applicability["A-R1-A1"] == "APPLICABLE"
        assert applicability["A-R1-A0"] == ("WITHDRAWN" if visible else "SUPERSEDED")
        if visible:
            assert any(
                a.ref == "A-R1-A0" and a.reason == "SUPERSEDED_AND_WITHDRAWN"
                for a in result.selection.research_only_audit
            )
    assert {a.ref for a in result.selection.research_only_audit if a.category == "RELATION"} == {
        "REL-R1-CORRECTION",
        "REL-R1-WITHDRAWAL",
    }
    assert result.selection.derived_reachability == ()


@pytest.mark.parametrize("kind", ["CORRECTS", "REPLACES"])
def test_remediation_r1_old_withdrawal_permutations(code, kind):
    request = remediation_family(code, kind=kind)
    original = evaluate_asof(request, code)
    remediation_observation(original)
    selected(original, 310, ("A-R1-A1",))
    for candidates in permutations(request.candidates):
        for relations in permutations(request.relations):
            result = evaluate_asof(
                replace(request, candidates=candidates, relations=relations), code
            )
            assert result == original
    assert len(original.selection.relations) == 2


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("competitor", "MATERIAL_CANDIDATE_UNRESOLVED"),
        ("unqualified_successor", "MATERIAL_CANDIDATE_UNRESOLVED"),
        ("coverage", "COVERAGE_INSUFFICIENT"),
        ("unknown_target", "RELATION_UNQUALIFIED"),
        ("unsupported_kind", "RELATION_UNQUALIFIED"),
        ("missing_notice", "RELATION_UNQUALIFIED"),
    ],
)
def test_remediation_r1_other_gates_are_not_bypassed(code, fault, reason):
    old = source(code, "R1-A0", 300)
    new = source(
        code,
        "R1-A1",
        310,
        unknown=fault == "unqualified_successor",
        historical=fault == "unqualified_successor",
    )
    correction = scoped_revision(
        code, old, new, tag="R1-CORRECTION", published="2025-07-05T10:00:00+08:00"
    )
    changes = {}
    if fault == "unknown_target":
        u = unknown(old.subject.origin)
        changes = {"old_assertion_ref": u, "old_version_ref": u}
    withdrawal = scoped_revision(
        code,
        old,
        kind="RESTATEMENT" if fault == "unsupported_kind" else "WITHDRAWS",
        tag="R1-WITHDRAWAL",
        published=R1_WITHDRAWAL_TIME,
        **changes,
    )
    if fault == "missing_notice":
        withdrawal = replace(withdrawal, notice=NotEvaluated("S3", "NO_NOTICE_SUPPLIED"))
    candidates, leads = (old, new), ()
    if fault == "competitor":
        competitor = source(code, "R1-COMPETITOR", 315, unknown=True, historical=True)
        candidates += (competitor,)
        leads = (lead_notice(code, competitor, tag="R1-LEAD"),)
    if fault == "unqualified_successor":
        leads = (lead_notice(code, new, tag="R1-LEAD"),)
    result = evaluate(
        code,
        candidates,
        (correction, withdrawal),
        leads=leads,
        complete=fault != "coverage",
        cutoff=R1_AFTER,
    )
    remediation_observation(result)
    assert result.selection.state == "UNRESOLVED" and result.selection.reason == reason
    assert result.selection.selected_assertion_refs == ()
    assert isinstance(result.selection.selected_value, NotEvaluated)


@pytest.mark.parametrize("cutoff", [R1_BEFORE, R1_WITHDRAWAL_TIME, R1_AFTER])
def test_remediation_r2_known_successor_is_structural_before_visibility(code, cutoff):
    old, new = source(code, "R2-A0", 300), source(code, "R2-A1", 310)
    # Build fresh canonical source bytes, not a forged CompletedRelation or stale wrapper.
    contradictory = scoped_revision(
        code, old, new, kind="WITHDRAWS", tag="R2-NOTICE", published=R1_WITHDRAWAL_TIME
    )
    result = evaluate(code, (old, new), (contradictory,), cutoff=cutoff)
    remediation_observation(result)
    remediation_evidence(
        result, {"REL-R2-NOTICE": "SUPPORTED" if cutoff == R1_AFTER else "NOT_ADMISSIBLE"}
    )
    refusal(result, "WITHDRAWAL_SUCCESSOR_CONTRADICTION")


@pytest.mark.parametrize(
    "cutoff,visible",
    [
        (R1_BEFORE, False),
        (R1_WITHDRAWAL_TIME, False),
        (R1_AFTER, True),
    ],
)
def test_remediation_r2_no_successor_neighbor_and_solitary_withdrawal(code, cutoff, visible):
    old = source(code, "R2-A0", 300)
    withdrawal = scoped_revision(
        code, old, kind="WITHDRAWS", tag="R2-NOTICE", published=R1_WITHDRAWAL_TIME
    )
    result = evaluate(code, (old,), (withdrawal,), cutoff=cutoff)
    remediation_observation(result)
    remediation_evidence(result, {"REL-R2-NOTICE": "SUPPORTED" if visible else "NOT_ADMISSIBLE"})
    (assessed,) = result.selection.relations
    assert assessed.event_support == assessed.relation_support == "SUPPORTED"
    assert assessed.state == ("QUALIFIED" if visible else "EXCLUDED")
    assert assessed.reason == ("NO_AUTOMATIC_ROLLBACK" if visible else "RELATION_AFTER_CUTOFF")
    if visible:
        assert (
            result.selection.state == "UNRESOLVED"
            and result.selection.reason == "RELATION_UNQUALIFIED"
        )
        assert result.selection.candidates[0].applicability == "WITHDRAWN"
        assert isinstance(result.selection.selected_value, NotEvaluated)
    else:
        selected(result, 300, ("A-R2-A0",))
        assert assessed.effect == "NONE"


@pytest.mark.parametrize("endpoint", ["old", "new"])
@pytest.mark.parametrize("cutoff", [R1_BEFORE, R1_AFTER])
def test_remediation_r2_source_valid_unknown_is_not_contradiction(code, endpoint, cutoff):
    old = source(code, "R2-A0", 300)
    u = unknown(old.subject.origin)
    withdrawal = scoped_revision(
        code,
        old,
        kind="WITHDRAWS",
        tag="R2-NOTICE",
        published=R1_WITHDRAWAL_TIME,
        **{endpoint + "_assertion_ref": u, endpoint + "_version_ref": u},
    )
    result = evaluate(code, (old,), (withdrawal,), cutoff=cutoff)
    remediation_observation(result)
    remediation_evidence(
        result, {"REL-R2-NOTICE": "SUPPORTED" if cutoff == R1_AFTER else "NOT_ADMISSIBLE"}
    )
    (assessed,) = result.selection.relations
    assert assessed.event_support == "SUPPORTED" and assessed.relation_support == "UNRESOLVED"
    if cutoff == R1_AFTER:
        assert assessed.state == result.selection.state == "UNRESOLVED"
        assert assessed.reason == "RELATION_TARGET_UNKNOWN"
    else:
        selected(result, 300, ("A-R2-A0",))
        assert assessed.reason == "RELATION_AFTER_CUTOFF"


def test_remediation_r2_stale_declaration_keeps_integrity_refusal(code):
    old = source(code, "R2-A0", 300)
    legitimate = scoped_revision(
        code, old, kind="WITHDRAWS", tag="R2-NOTICE", published=R1_WITHDRAWAL_TIME
    )
    selected(evaluate(code, (old,), (legitimate,), cutoff=R1_BEFORE), 300, ("A-R2-A0",))
    stale = replace(
        legitimate,
        relation=replace(
            legitimate.relation,
            new_assertion_ref=old.request.assertion.assertion_ref,
            new_version_ref=old.request.content.content_version_ref,
        ),
    )
    result = evaluate(code, (old,), (stale,), cutoff=R1_BEFORE)
    remediation_observation(result)
    refusal(result, "RELATION_CONTENT_MISMATCH")


@pytest.mark.parametrize("same_content", [True, False])
@pytest.mark.parametrize("cutoff", [R1_BEFORE, R1_WITHDRAWAL_TIME, R1_AFTER])
def test_remediation_reissues_profile_adjudication(code, same_content, cutoff):
    old = source(code, "REISSUE-A0", 300)
    new = source(code, "REISSUE-A1", 300 if same_content else 310)
    reissue = scoped_revision(
        code, old, new, kind="REISSUES", tag="REISSUE-NOTICE", published=R1_WITHDRAWAL_TIME
    )
    result = evaluate(code, (old, new), (reissue,), target="CONTENT_VALUE", cutoff=cutoff)
    remediation_observation(result)
    remediation_evidence(
        result, {"REL-REISSUE-NOTICE": "SUPPORTED" if cutoff == R1_AFTER else "NOT_ADMISSIBLE"}
    )
    assert (
        len({c.source.request.content.content_version_ref for c in result.inputs.candidates}) == 2
    )
    if same_content:
        selected(result, 300, ("A-REISSUE-A0", "A-REISSUE-A1"))
        assert all(a.applicability == "APPLICABLE" for a in result.selection.candidates)
        assert result.selection.relations[0].effect == (
            "REISSUES" if cutoff == R1_AFTER else "NONE"
        )
        assert result.selection.relations[0].state == (
            "QUALIFIED" if cutoff == R1_AFTER else "EXCLUDED"
        )
    elif cutoff == R1_AFTER:
        refusal(result, "REISSUE_CONTENT_MISMATCH")
    else:
        assert result.selection.state == "UNRESOLVED"
        assert result.selection.reason == "MATERIAL_CANDIDATE_UNRESOLVED"
        assert result.selection.relations[0].reason == "RELATION_AFTER_CUTOFF"
        assert result.selection.selected_assertion_refs == ()


@pytest.mark.parametrize("target", ["old", "current"])
def test_remediation_r1_downstream_unaffected_successor(derived_builders, target):
    from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code

    _, a05 = derived_builders
    observation = observe_ratio_code(ROOT)
    spec, sum_spec, legacy = a05.inputs(observation, revision_delta=10, cutoff=LATE)
    slots = versioned_slots(observation.upstream_a04, legacy)
    june = slots[2].request
    withdrawal = scoped_revision(
        observation.upstream_a04,
        june.candidates[0 if target == "old" else 1],
        kind="WITHDRAWS",
        tag="REMEDIATION-WITHDRAW",
        published="2025-07-11T12:00:00+08:00",
    )
    june = b02_request(replace(june, relations=(*june.relations, withdrawal)))
    slots = (*slots[:2], replace(slots[2], request=june))
    result = evaluate_ratio(spec, sum_spec, slots, observation)
    actual_s3 = result.upstream_a04.dependencies[2].actual
    remediation_observation(actual_s3)
    assert not result.admission_eligible and result.diagnostic_only
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    if target == "old":
        assert actual_s3.selection.state == "SELECTED"
        assert actual_s3.selection.selected_assertion_refs == ("A-A05-REVISION",)
        assert result.upstream_a04.outcome.value == 56_799_300
        assert result.outcome.value.decimal_text == "0.308955"
        assert result.research_only_audit.exact_fraction == (17_548_423, 56_799_300)
    else:
        assert actual_s3.selection.state == "UNRESOLVED"
        assert actual_s3.selection.reason == "RELATION_UNQUALIFIED"
        assert actual_s3.selection.selected_assertion_refs == ()
        assert result.upstream_a04.outcome.state == result.outcome.state == "UNRESOLVED"
        assert result.outcome.reason == "DEPENDENCY_UNRESOLVED"
        assert isinstance(result.upstream_a04.outcome.value, NotEvaluated)
        assert isinstance(result.outcome.value, NotEvaluated)
