"""B01 independent falsifiers from the original SC register; engineering tests only."""

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_wu01_information import actual_projection, execute, inputs
from wu01_actual import _used_paths

from pit_research_lab.domain.asof_slice import evaluate_asof, observe_asof_code
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    ContractError,
    IdentityOutcome,
    IssuerBindingRequest,
    Known,
    NotApplicable,
    NotEvaluated,
    OriginKnownValue,
    RequestBindingAttempt,
    TemporalPolicy,
)
from pit_research_lab.domain.derived_slice import evaluate_derived
from pit_research_lab.domain.pit_slice import evaluate_slice
from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code
from pit_research_lab.domain.selection import CandidateSource, HistoricalLead
from pit_research_lab.domain.temporal import qualify_temporal


def changed_binding(binding, fault):
    if fault == "evidence_identity":
        return replace(
            binding,
            evidence_ref="EVID-ORD1-TIME",
            target=replace(
                binding.target,
                origin=replace(binding.target.origin, object_id=OriginKnownValue("EVID-ORD1-TIME")),
            ),
        )
    if fault == "support_pointer":
        return replace(binding, origin=replace(binding.origin, envelope_pointer="/forged"))
    if fault == "evidence_pointer":
        return replace(
            binding,
            target=replace(
                binding.target, origin=replace(binding.target.origin, envelope_pointer="/forged")
            ),
        )
    return replace(
        binding,
        proof_candidate=replace(
            binding.proof_candidate,
            origin=replace(binding.proof_candidate.origin, envelope_pointer="/forged"),
        ),
    )


@pytest.mark.parametrize("case", ["A01-C03", "A02-C01", "A02-C03"])
@pytest.mark.parametrize(
    "fault", ["evidence_identity", "support_pointer", "evidence_pointer", "proof_pointer"]
)
def test_b01_sc01_source_relation_is_not_rebound(case, fault):
    b = inputs(case)
    r = b.request
    if case == "A01-C03":
        r = replace(r, left=replace(r.left, supports=(changed_binding(r.left.supports[0], fault),)))
    elif case == "A02-C01":
        r = replace(
            r,
            attempts=(
                replace(r.attempts[0], supplied=changed_binding(r.attempts[0].supplied, fault)),
            ),
        )
    else:
        r = replace(
            r,
            supports=tuple(
                changed_binding(s, fault) if s.target.target_ref == r.requested.target_ref else s
                for s in r.supports
            ),
        )
    result = execute(replace(b, request=r))
    assert isinstance(result, BlockingFailure), result


@pytest.mark.parametrize("erase_roles", [False, True])
def test_b01_sc02_empty_supports_do_not_erase_obligations(erase_roles):
    b = inputs("A01-C03")
    r = replace(
        b.request,
        left=replace(b.request.left, supports=()),
        right=replace(b.request.right, supports=()),
    )
    if erase_roles:
        roles = {
            "assertions",
            "subjects",
            "content_versions",
            "supports",
            "evidence",
            "publication_events",
            "time_proofs",
        }
        r = replace(
            r,
            scope=replace(
                r.scope,
                input_members=tuple(m for m in r.scope.input_members if m.role not in roles),
            ),
        )
    assert isinstance(execute(replace(b, request=r)), BlockingFailure)


def rebalanced(actual, paths):
    used = _used_paths(paths)
    return replace(
        actual,
        provenance=replace(
            actual.provenance,
            accepted_paths=paths,
            excluded_uses=tuple(m for m in actual.provenance.input_members if m.key not in used),
        ),
    )


@pytest.mark.parametrize("case", ["A02-C01", "A02-C03"])
@pytest.mark.parametrize("fault", ["origin", "surplus"])
def test_b01_sc03_exact_projection_paths(case, fault):
    b = inputs(case)
    actual = execute(b)
    path = actual.provenance.accepted_paths[0]
    paths = (
        (replace(path, origin=replace(path.origin, envelope_pointer="/forged")),)
        if fault == "origin"
        else (path, replace(path, path_role="IDENTITY_CONTENT"))
    )
    with pytest.raises(ContractError):
        actual_projection(b, rebalanced(actual, paths))


@pytest.mark.parametrize("case", ["A02-C01", "A02-C02", "A02-C03", "A02-C04"])
def test_b01_sc04_content_retention(case):
    b = inputs(case)
    with pytest.raises(ContractError):
        actual_projection(b, replace(execute(b), content_refs=("OTHER",)))


@pytest.mark.parametrize("case", ["A02-C01", "A02-C02", "A02-C04"])
def test_b01_sc04_amount_retention(case):
    b = inputs(case)
    actual = execute(b)
    with pytest.raises(ContractError):
        actual_projection(b, replace(actual, source_amount=Known(999, actual.source_amount.origin)))


@pytest.mark.parametrize("fault", ["empty", "duplicate", "target"])
def test_b01_sc04_provider_edge_retention(fault):
    b = inputs("A02-C04")
    actual = execute(b)
    edge = actual.capture_edges[0]
    edges = (
        ()
        if fault == "empty"
        else (edge, edge)
        if fault == "duplicate"
        else (replace(edge, to_representation="OTHER"),)
    )
    with pytest.raises(ContractError):
        actual_projection(b, replace(actual, capture_edges=edges))


def test_b01_sc05_provider_cannot_fabricate_source():
    b = inputs("A02-C04")
    r = b.request
    r = replace(
        r,
        content=replace(r.content, source_ref=Known("SRC-FABRICATED", r.content.source_ref.origin)),
    )
    assert isinstance(execute(replace(b, request=r)), BlockingFailure)


def test_b01_sc01_provider_edge_pointer():
    b = inputs("A02-C04")
    edge = b.request.capture_edges[0]
    r = replace(
        b.request,
        capture_edges=(replace(edge, origin=replace(edge.origin, envelope_pointer="/forged")),),
    )
    assert isinstance(execute(replace(b, request=r)), BlockingFailure)


@pytest.mark.parametrize(
    "case,state",
    [
        ("A01-C01", "SAME"),
        ("A01-C02", "DIFFERENT"),
        ("A01-C03", "SAME"),
        ("A01-C04", "UNRESOLVED"),
        ("A02-C01", "BOUND"),
        ("A02-C02", "UNRESOLVED"),
        ("A02-C03", "BOUND"),
        ("A02-C04", "UNRESOLVED"),
    ],
)
def test_b01_genuine_neighbors(case, state):
    b = inputs(case)
    actual = execute(b)
    assert actual.state == state
    actual_projection(b, actual)


@pytest.mark.parametrize("field", ["cutoff", "evidence", "mode", "policies", "profile", "target"])
def test_b01_direct_s2_rejects_stale_full_context(field):
    b = inputs("A02-C01")
    actual = execute(b)
    c = b.context
    updates = {
        "cutoff": {
            "information_cutoff": replace(
                c.information_cutoff, source_text="2025-07-14T00:00:00+08:00"
            )
        },
        "evidence": {"evidence_set_ref": "OTHER"},
        "mode": {"mode": "prospective_observed"},
        "policies": {"policy_refs": (*c.policy_refs, "OTHER")},
        "profile": {"profile": replace(c.profile, code_pins=c.profile.code_pins[:-1])},
        "target": {"target_ref": "CONTENT_VALUE"},
    }
    result = qualify_temporal(replace(c, **updates[field]), b.request, actual)
    assert result.state == "UNRESOLVED"
    assert result.diagnostics == ("QUALIFICATION_CONTEXT_MISMATCH",)


@pytest.mark.parametrize("fault", ["amount", "content", "paths", "assessment"])
def test_b01_direct_s2_replays_actual_s1(fault):
    b = inputs("A02-C01")
    actual = execute(b)
    if fault == "amount":
        actual = replace(actual, source_amount=Known(999, actual.source_amount.origin))
    elif fault == "content":
        actual = replace(actual, content_refs=("OTHER",))
    elif fault == "paths":
        actual = rebalanced(actual, ())
    else:
        actual = replace(actual, assessments=actual.assessments * 2)
    result = qualify_temporal(b.context, b.request, actual)
    assert result.state == "UNRESOLVED"
    assert result.diagnostics == ("S1_OUTCOME_MISMATCH",)


@pytest.mark.parametrize(
    "rule",
    [
        NotEvaluated("S2", "ABSENT"),
        replace(TemporalPolicy(), public_basis="CONSERVATIVE_PROXY"),
        replace(TemporalPolicy(), observed_basis="INTERVAL"),
        replace(TemporalPolicy(), evaluator_ref="OTHER"),
    ],
)
def test_b01_unsupported_temporal_contract_is_explicit(rule):
    b = inputs("A02-C01")
    c = replace(b.context, temporal_rule=rule)
    result = qualify_temporal(c, b.request, execute(replace(b, context=c)))
    assert result.state == "UNRESOLVED"
    assert result.diagnostics == ("UNSUPPORTED_TEMPORAL_POLICY",)


def test_b01_direct_valid_repeated_and_administrative_clock_noninterference():
    b = inputs("A02-C01")
    actual = execute(b)
    first = qualify_temporal(b.context, b.request, actual)
    assert first.state == "SUPPORTED"
    assert qualify_temporal(b.context, b.request, actual) == first
    c = replace(b.context, decision_wall_times=("2099-01-01T08:00:00+08:00",))
    assert qualify_temporal(c, b.request, actual).state == first.state


def test_b01_absent_reference_never_falls_back_to_bound():
    b = inputs("A02-C01")
    r = replace(
        b.request, scope=replace(b.request.scope, source_records=NotEvaluated("S1", "ABSENT"))
    )
    result = execute(replace(b, request=r))
    assert isinstance(result, BlockingFailure) and result.code == "SOURCE_RECORDS_ABSENT"


def test_b01_duplicate_source_identity_is_structurally_invalid():
    b = inputs("A02-C01")
    source = b.request.scope.source_records
    with pytest.raises(ContractError, match="DUPLICATE_SOURCE_RECORD"):
        replace(source, supports=(*source.supports, source.supports[0]))


def _sc02_empty_reference(request, *, remove_roles=()):
    """Declare limited synthetic reference facts; not the unchanged A01-C03 corpus."""
    members = tuple(m for m in request.scope.input_members if m.role not in remove_roles)
    source = replace(request.scope.source_records, supports=(), input_members=members)
    scope = replace(request.scope, source_records=source, input_members=members)
    return replace(request, scope=scope)


def _sc02_identity_receipt(label, bundle, result):
    """Diagnostic facts only: no production output is used as an expected oracle."""
    receipt = {
        "case": label,
        "source_support_refs": [
            s.support_ref for s in bundle.request.scope.source_records.supports
        ],
        "source_members": [m.key for m in bundle.request.scope.source_records.input_members],
    }
    if isinstance(result, BlockingFailure):
        receipt.update(category=result.category, code=result.code)
    else:
        receipt.update(
            state=result.state,
            reason=result.reason,
            assertion_refs=result.assertion_refs,
            accepted_paths=[
                (p.target.target_ref, p.evidence_ref, p.support_ref, p.path_role)
                for p in result.provenance.accepted_paths
            ],
            excluded_uses=[m.key for m in result.provenance.excluded_uses],
        )
    print(json.dumps(receipt, sort_keys=True))


@pytest.mark.parametrize(
    "case,state,paths,error",
    [
        ("genuine", "SAME", 2, None),
        ("challenged_empty", None, None, "IDENTITY_SOURCE_COVERAGE_MISMATCH"),
        ("both_empty", "SAME", 0, None),
        ("support_roles_removed", None, None, "UNDECLARED_PATH_MEMBER"),
        ("both_empty_optional_roles_removed", "SAME", 0, None),
        ("both_empty_identity_role_removed", None, None, "UNDECLARED_PATH_MEMBER"),
        ("content_only", "DIFFERENT", 2, None),
        ("canonical_assertionless", "SAME", 1, None),
    ],
)
def test_sc02_targeted_identity_matrix(case, state, paths, error):
    # Independent contract oracle: S1 baseline §3.2 defines SAME by dimensions,
    # not publication sufficiency. WU-01A §6 separates identity and binding.
    # Original SC-02 requires preserving the *supplied* own paths. Replacing the
    # reference corpus is a separate limited-input case, not original C03 proof.
    name = {"content_only": "A01-C02", "canonical_assertionless": "A01-C01"}.get(case, "A01-C03")
    b = inputs(name)
    r = b.request
    original = r
    if case in {
        "challenged_empty",
        "both_empty",
        "both_empty_optional_roles_removed",
        "both_empty_identity_role_removed",
    }:
        r = replace(r, left=replace(r.left, supports=()), right=replace(r.right, supports=()))
    if case.startswith("both_empty"):
        roles = (
            ("supports", "evidence")
            if "optional" in case
            else ("assertions",)
            if "identity_role" in case
            else ()
        )
        r = _sc02_empty_reference(r, remove_roles=roles)
    if case == "support_roles_removed":
        members = tuple(m for m in r.scope.input_members if m.role not in {"supports", "evidence"})
        r = replace(
            r,
            scope=replace(
                r.scope,
                input_members=members,
                source_records=replace(r.scope.source_records, input_members=members),
            ),
        )
    context = replace(b.context, context_ref="SC02-" + case, evidence_set_ref="E-SC02-" + case)
    b = replace(b, request=r, context=context, source_members=r.scope.input_members)
    result = execute(b)
    _sc02_identity_receipt(case, b, result)
    if error:
        assert isinstance(result, BlockingFailure)
        assert (result.category, result.code) == ("CONTRACT_VIOLATION", error)
        return
    assert isinstance(result, IdentityOutcome)
    assert (result.state, result.reason) == (
        state,
        "SUBJECT_MISMATCH" if state == "DIFFERENT" else "NONE",
    )
    assert len(result.provenance.accepted_paths) == paths
    assert result.assertion_refs == tuple(
        o.assertion.assertion_ref
        for o in (r.left, r.right)
        if not isinstance(o.assertion, NotApplicable)
    )
    used = _used_paths(result.provenance.accepted_paths)
    assert result.provenance.excluded_uses == tuple(
        m for m in r.scope.input_members if m.key not in used
    )
    assert actual_projection(b, result).system_outcome == result
    if case.startswith("both_empty"):
        assert result.assertion_refs == (
            original.left.assertion.assertion_ref,
            original.right.assertion.assertion_ref,
        )
        assert result.source_assertions == (original.left.assertion, original.right.assertion)
        assert result.provenance.excluded_uses == r.scope.input_members
        assert isinstance(result.canonical_amount, NotEvaluated)
    if case == "content_only":
        assert all(
            isinstance(s.event, NotApplicable) and isinstance(s.proof_candidate, NotApplicable)
            for s in r.left.supports + r.right.supports
        )
    if case == "canonical_assertionless":
        assert isinstance(r.right.assertion, NotApplicable) and r.right.supports == ()
        assert result.canonical_amount.value == 100


@pytest.mark.parametrize(
    "case,state",
    [("A01-C01", "SAME"), ("A01-C02", "DIFFERENT"), ("A01-C03", "SAME"), ("A01-C04", "UNRESOLVED")],
)
def test_sc02_targeted_original_a01_controls(case, state):
    b = inputs(case)
    result = execute(b)
    assert result.state == state
    assert all(
        o.supports
        for o in (b.request.left, b.request.right)
        if not isinstance(o.assertion, NotApplicable)
    )
    assert actual_projection(b, result).system_outcome == result


@pytest.fixture
def sc02_builders(monkeypatch):
    """Load only existing source-data builders, without modifying import paths."""
    root = Path(__file__).resolve().parents[1]
    modules = []
    for folder, name in [
        ("cap_f2_v1_a03", "a03_inputs"),
        ("cap_f2_v1_a04", "a04_inputs"),
        ("cap_f2_v1_a05", "a05_inputs"),
    ]:
        module = sys.modules.get(name)
        if module is None:
            spec = importlib.util.spec_from_file_location(name, root / folder / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            monkeypatch.setitem(sys.modules, name, module)
            spec.loader.exec_module(module)
        modules.append(module)
    return tuple(modules)


@pytest.mark.parametrize("prune_roles", [False, True])
def test_sc02_targeted_same_never_qualifies_evidence_alone(sc02_builders, prune_roles):
    a03, _, _ = sc02_builders
    root = Path(__file__).resolve().parents[3]
    code = observe_asof_code(root)
    b = inputs("A01-C03")
    operand = b.request.left
    binding = operand.supports[0]
    scope = _sc02_empty_reference(
        b.request, remove_roles=("supports", "evidence") if prune_roles else ()
    ).scope
    request = IssuerBindingRequest(
        binding.target,
        operand.contents[0],
        operand.assertion,
        (),
        operand.captures,
        operand.events,
        scope,
    )
    candidate = CandidateSource(operand.subject, request, _sc02_grounded_lead(request, "A03-SCOPE"))
    context = replace(
        b.context, context_ref="SC02-EMPTY-PUBLIC", evidence_set_ref="E-SC02-EMPTY-PUBLIC"
    )
    actual = evaluate_slice(context, request, code)
    assert (actual.s1.state, actual.s1.reason) == ("UNRESOLVED", "CONTENT_BINDING_INSUFFICIENT")
    assert (actual.s2.state, actual.s2.reason) == ("UNRESOLVED", "CONTENT_BINDING_INSUFFICIENT")
    assert actual.s1.provenance.accepted_paths == () and actual.s2.accepted_binding_refs == ()
    asof = evaluate_asof(a03.invocation(code, (candidate,), snapshot="E-SC02-EMPTY-PUBLIC"), code)
    assert asof.inputs.candidates[0].subject_identity.state == "SAME"
    assert asof.selection.state == "UNRESOLVED" and asof.selection.selected_assertion_refs == ()
    positive = replace(
        candidate,
        request=replace(
            request,
            attempts=(RequestBindingAttempt(binding.target, binding),),
            scope=b.request.scope,
        ),
    )
    control = evaluate_asof(a03.invocation(code, (positive,), snapshot="E-SC02-GENUINE"), code)
    assert control.selection.state == "SELECTED" and control.selection.selected_value == 300
    assert actual.diagnostic_only and not actual.admission_eligible
    print(
        json.dumps(
            {
                "case": "downstream",
                "prune_roles": prune_roles,
                "identity": "SAME",
                "s1": actual.s1.state,
                "s2": actual.s2.state,
                "s3": asof.selection.state,
                "control": control.selection.selected_value,
            }
        )
    )


@pytest.mark.parametrize("layer", ["A04", "A05"])
def test_sc02_targeted_empty_evidence_has_no_derived_value(sc02_builders, layer):
    _, _, a05 = sc02_builders
    code = observe_ratio_code(Path(__file__).resolve().parents[3])
    ratio_spec, sum_spec, slots = a05.inputs(code, snapshot="E-SC02-EMPTY-DERIVED")
    candidate = slots[2].request.candidates[0]
    r = candidate.request
    r = replace(r, attempts=(), scope=_sc02_empty_reference(r).scope)
    limited = replace(
        candidate,
        request=r,
        historical_lead=_sc02_grounded_lead(r, slots[2].request.policy.discovery_scope_ref),
    )
    slot = replace(slots[2], request=replace(slots[2].request, candidates=(limited,)))
    changed = (*slots[:2], slot)
    result = (
        evaluate_derived(sum_spec, changed, code.upstream_a04)
        if layer == "A04"
        else evaluate_ratio(ratio_spec, sum_spec, changed, code)
    )
    assert (result.outcome.state, result.outcome.reason) == ("UNRESOLVED", "DEPENDENCY_UNRESOLVED")
    assert isinstance(result.outcome.value, NotEvaluated)
    assert result.diagnostic_only and not result.admission_eligible
    print(
        json.dumps(
            {
                "case": layer,
                "state": result.outcome.state,
                "reason": result.outcome.reason,
                "value": "NotEvaluated",
            }
        )
    )


def _sc02_grounded_lead(request, scope_ref):
    # Golden A06-C03 and A03's declared materiality policy require uncertainty
    # for a grounded historical lead. NO_HISTORICAL_CLUE is a different policy
    # input and can yield bounded NO_QUALIFIED_CLAIM, also with no numeric claim.
    return HistoricalLead(
        "SC02-SYNTHETIC-LEAD",
        request.requested.target_ref,
        scope_ref,
        "CONTEMPORANEOUS_ISSUER_NOTICE",
        next(
            m
            for m in request.scope.input_members
            if m.role == "raw_assets" and m.object_ref == request.content.representation_ref
        ),
        request.content.origin,
    )
