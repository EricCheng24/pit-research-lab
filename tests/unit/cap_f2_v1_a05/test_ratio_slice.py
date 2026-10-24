"""A05 engineering scenarios, distinct from Frozen Golden obligations."""

import ast
import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from decimal import ROUND_DOWN, localcontext
from hashlib import sha256
from pathlib import Path

import pytest
from a03_inputs import revision
from a04_inputs import month_source, request, rewrite
from a05_inputs import inputs

from pit_research_lab.domain.contracts import ContractError, NotEvaluated, OriginKnownValue
from pit_research_lab.domain.derived_slice import evaluate_derived, observe_derived_code
from pit_research_lab.domain.ratio import (
    RATIO_CODE_PATHS,
    FixedRatio,
    _evaluate_completed,
    _fixed_ratio,
)
from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code
from pit_research_lab.domain.selection import ResearchAuditEntry

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_ratio_code(ROOT)


def run(code, **kwargs):
    spec, sum_spec, slots = inputs(code, **kwargs)
    return evaluate_ratio(spec, sum_spec, slots, code)


def isolated(result):
    assert result.origin_kind == "DERIVED"
    assert result.disposition == "INTEGRATED_PROVISIONAL"
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.admission_eligible is False and result.diagnostic_only is True
    for name in ("to_agent_observation", "agent_observation", "publish", "export"):
        assert not hasattr(result, name)


def swapped(slots, index, new_request, expected_subject=None):
    return tuple(
        replace(s, request=new_request, expected_subject=expected_subject or s.expected_subject)
        if i == index
        else s
        for i, s in enumerate(slots)
    )


def test_t01_actual_two_transforms_full_lineage_and_no_trust(code):
    spec, sum_spec, slots = inputs(code)
    result = evaluate_ratio(spec, sum_spec, slots, code)
    upstream = result.upstream_a04
    assert upstream == evaluate_derived(sum_spec, slots, code.upstream_a04)
    assert upstream.outcome.value == 56_799_290
    assert result.outcome.state == "VALUE_AVAILABLE"
    value = result.outcome.value
    assert isinstance(value, FixedRatio)
    assert (value.scaled_units, value.decimal_text, value.unit, value.scale) == (
        308955,
        "0.308955",
        "FRACTION",
        6,
    )
    assert result.research_only_audit.exact_fraction == (17_548_413, 56_799_290)
    for dep, line in zip(upstream.dependencies, upstream.outcome.lineage, strict=True):
        assert dep.actual.selection.state == "SELECTED"
        actual = dep.actual.inputs.candidates[0].actual
        assert actual.s1.state == "BOUND" and actual.s2.state == "SUPPORTED"
        assert line.raw_sha256s == (sha256(actual.request.content.raw_bytes).hexdigest(),)
        assert line.content_version_refs == (actual.request.content.content_version_ref,)
        assert (
            actual.request.attempts[0].supplied.proof_candidate.content_version_ref
            == line.content_version_refs[0]
        )
    assert result.specification.feature_ref != upstream.specification.feature_ref
    assert result.realization_ref != upstream.realization_ref
    isolated(result)


@pytest.mark.parametrize("delta,rounded", [(10, "0.308955"), (100, "0.308956")])
def test_t02_revision_exact_fraction_changes_and_rounding_collision(code, delta, rounded):
    early = run(code, revision_delta=delta)
    later = run(code, revision_delta=delta, cutoff="2025-07-14T00:00:00+08:00")
    assert early.outcome.value.decimal_text == "0.308955"
    assert later.outcome.value.decimal_text == rounded
    assert early.research_only_audit.exact_fraction == (17_548_413, 56_799_290)
    assert later.research_only_audit.exact_fraction == (17_548_413 + delta, 56_799_290 + delta)
    assert early.upstream_a04.outcome.lineage[2].assertion_refs == ("A-2025-06",)
    assert later.upstream_a04.outcome.lineage[2].assertion_refs == ("A-A05-REVISION",)
    notice = later.upstream_a04.dependencies[2].actual.inputs.relations[0].notice.actual
    assert notice.s1.state == "BOUND" and notice.s2.state == "SUPPORTED"
    assert early.upstream_a04.dependencies[2].actual.selection.relations[0].state == "EXCLUDED"
    assert later.upstream_a04.dependencies[2].actual.selection.relations[0].state == "QUALIFIED"
    assert early.realization_ref != later.realization_ref
    if delta == 10:
        assert early.outcome.value == later.outcome.value
    assert early == run(code, revision_delta=delta)


@pytest.mark.parametrize(
    "values,text",
    [
        ((1, 2, 0), "0.000000"),
        ((0, 0, 17), "1.000000"),
        ((1, 126, 1), "0.007812"),
        ((1, 124, 3), "0.023438"),
        ((1, 6, 1), "0.125000"),
        ((1, 1, 1), "0.333333"),
        ((0, 1, 2), "0.666667"),
        ((0, 2_000_000, 1), "0.000000"),
        ((0, 2_000_000 - 1, 1), "0.000000"),
        ((0, 2_000_000 - 2, 1), "0.000001"),
        ((1, 0, 2**63 - 2), "1.000000"),
    ],
)
def test_t03_t06_integration_exact_rounding_domain_boundaries(code, values, text):
    result = run(code, values=values)
    assert result.upstream_a04.outcome.state == "VALUE_AVAILABLE"
    assert result.upstream_a04.outcome.value == sum(values)
    assert result.outcome.state == "VALUE_AVAILABLE" and result.outcome.value.decimal_text == text
    assert result.research_only_audit.exact_fraction == (values[2], sum(values))
    assert json.loads(result.diagnostic_preview_bytes)["value"] == text
    assert not text.startswith("-") and len(text.split(".")[1]) == 6


def test_t04_zero_denominator_is_normal_domain_missing_not_zero_value(code):
    result = run(code, values=(0, 0, 0))
    assert result.upstream_a04.outcome.state == "VALUE_AVAILABLE"
    assert result.upstream_a04.outcome.value == 0
    assert result.outcome.state == "NOT_COMPUTABLE"
    assert result.outcome.reason == "ZERO_QUARTER_REVENUE_DENOMINATOR"
    assert isinstance(result.outcome.value, NotEvaluated)
    assert result.research_only_audit.numerator == result.research_only_audit.denominator == 0
    assert isinstance(result.research_only_audit.exact_fraction, NotEvaluated)
    preview = json.loads(result.diagnostic_preview_bytes)
    assert preview["value"] is None and preview["absence"] == result.outcome.reason
    isolated(result)


@pytest.mark.parametrize("values", [(-1, 3, 4), (1, 3, -2), (-1, 0, 1), (-3, -2, -1)])
def test_t05_selected_negative_is_preserved_but_outside_share_domain(code, values):
    result = run(code, values=values)
    assert result.upstream_a04.outcome.state == "VALUE_AVAILABLE"
    assert result.upstream_a04.outcome.value == sum(values)
    assert tuple(item.value for item in result.upstream_a04.outcome.lineage) == values
    assert result.outcome.state == "NOT_COMPUTABLE"
    assert result.outcome.reason == "NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN"
    assert isinstance(result.outcome.value, NotEvaluated)


@pytest.mark.parametrize(
    "n,d,text", [(1, 128, "0.007812"), (3, 128, "0.023438"), (0, 7, "0.000000"), (7, 7, "1.000000")]
)
def test_t06_integer_helper_ignores_decimal_ambient_context(n, d, text):
    with localcontext() as ctx:
        ctx.prec = 1
        ctx.rounding = ROUND_DOWN
        assert _fixed_ratio(n, d).decimal_text == text


@pytest.mark.parametrize(
    "n,d", [(True, 2), (1, True), (1.0, 2), (1, 2.0), (-1, 2), (3, 2), (0, 0), (1, 2**63)]
)
def test_t06_t12_math_helper_rejects_invalid_exact_operands(n, d):
    with pytest.raises(ContractError):
        _fixed_ratio(n, d)


@pytest.mark.parametrize(
    "changes",
    [
        {"scaled_units": True},
        {"scaled_units": 1.0},
        {"scaled_units": -1},
        {"scaled_units": 1_000_001},
        {"decimal_text": "0.1"},
        {"decimal_text": "-0.000000"},
        {"scale": True},
        {"unit": "PERCENT"},
        {"numerical_policy": "HALF_UP"},
    ],
)
def test_t06_fixed_representation_contradictions_rejected(changes):
    with pytest.raises(ContractError):
        replace(FixedRatio(0, "0.000000"), **changes)


@pytest.mark.parametrize(
    "kind,state,reason",
    [
        ("conflict", "UNRESOLVED", "DEPENDENCY_UNRESOLVED"),
        ("absent", "NOT_COMPUTABLE", "UPSTREAM_REQUIRED_INPUT_ABSENT"),
    ],
)
def test_t07_t08_upstream_uncertainty_and_bounded_absence(code, kind, state, reason):
    result = run(code, third=kind)
    assert result.outcome.state == state and result.outcome.reason == reason
    assert isinstance(result.outcome.value, NotEvaluated)
    assert isinstance(result.research_only_audit.denominator, NotEvaluated)
    assert result.research_only_audit.upstream_reason == result.upstream_a04.outcome.reason
    if state == "UNRESOLVED":
        assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)
    else:
        assert (
            json.loads(result.diagnostic_preview_bytes)["absence"]
            == "UPSTREAM_REQUIRED_INPUT_ABSENT"
        )


@pytest.mark.parametrize(
    "kwargs,state",
    [({"complete": False}, "UNRESOLVED"), ({"check_status": "FAILED"}, "OPERATIONAL_ERROR")],
)
def test_t09_coverage_failures_preserve_original_owner_reason(code, kwargs, state):
    result = run(code, **kwargs)
    assert result.outcome.state == state
    assert result.outcome.reason == result.upstream_a04.outcome.reason
    assert result.outcome.upstream_failures == result.upstream_a04.outcome.upstream_failures
    assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)


@pytest.mark.parametrize(
    "field,value",
    [
        ("unit", "NTD_thousands"),
        ("scale", 2),
        ("scale", True),
        ("transformation_ref", "PERCENT_GROWTH"),
        ("output_meaning", "ISSUER_PUBLISHED_SHARE"),
        ("numerator_role", "M1"),
        ("denominator_relation", "CALLER_SUPPLIED_NUMBER"),
        ("numerical_policy", "HALF_UP"),
        ("domain_policy", "ABSOLUTE_VALUES"),
        ("preview_policy", "FULL_AUDIT"),
        ("evaluator_ref", "FOREIGN"),
        ("prior_derived_sum_ref", "FOREIGN-SUM"),
        ("issuer_ref", "SYN-B"),
        ("year", 2024),
        ("quarter", 1),
        ("year", True),
        ("extra_dependencies", ("FITTED_STATE",)),
        ("extra_dependencies", ("LABEL",)),
        ("extra_dependencies", ("WINDOW",)),
        ("extra_dependencies", ("DYNAMIC_UNIVERSE",)),
        ("extra_dependencies", ("FALLBACK",)),
        ("extra_dependencies", ()),
    ],
)
def test_t10_invalid_static_spec_never_runs_another_formula(code, field, value):
    spec, sum_spec, slots = inputs(code)
    result = evaluate_ratio(replace(spec, **{field: value}), sum_spec, slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert isinstance(result.upstream_a04, NotEvaluated)
    assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)


@pytest.mark.parametrize("identity", ["sum", "assertion", "content", "representation"])
def test_t10_identity_is_not_sum_or_source(code, identity):
    spec, sum_spec, slots = inputs(code)
    r = slots[0].request.candidates[0].request
    collision = {
        "sum": sum_spec.feature_ref,
        "assertion": r.assertion.assertion_ref,
        "content": r.content.content_version_ref,
        "representation": r.content.representation_ref,
    }[identity]
    result = evaluate_ratio(replace(spec, feature_ref=collision), sum_spec, slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"


@pytest.mark.parametrize(
    "field,value",
    [
        ("basis_ref", "FOREIGN-BASIS"),
        ("reporting_scope", "individual"),
        ("canonical_unit", "NTD"),
        ("currency", "USD"),
        ("metric", "orders"),
        ("period_kind", "INSTANT"),
    ],
)
def test_t11_incompatible_source_contract_remains_a04_fault(code, field, value):
    spec, sum_spec, slots = inputs(code)
    source = rewrite(slots[1].request.candidates[0], subject_changes={field: value})
    new_request = request(code.upstream_a04, source, (source,))
    slots = swapped(slots, 1, new_request, source.subject)
    actual = evaluate_derived(sum_spec, slots, code.upstream_a04)
    result = evaluate_ratio(spec, sum_spec, slots, code)
    assert result.upstream_a04 == actual
    assert (
        result.outcome.state == "CONTRACT_VIOLATION"
        and result.outcome.reason == actual.outcome.reason
    )
    assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)


@pytest.mark.parametrize(
    "fault", ["period", "cutoff", "mode", "snapshot", "calendar", "numeric", "policy", "fragment"]
)
def test_t11_mixed_context_or_malformed_owner_input_cannot_be_domain_missing(code, fault):
    spec, sum_spec, slots = inputs(code)
    req = slots[1].request
    if fault == "period":
        source = month_source(code.upstream_a04, "WRONG-MONTH", 4, 19)
        req = request(code.upstream_a04, source, (source,))
        slots = swapped(slots, 1, req, source.subject)
    elif fault == "fragment":
        source = req.candidates[0]
        source = replace(
            source,
            request=replace(
                source.request,
                requested=replace(source.request.requested, fragment_selector="/statements/999"),
            ),
        )
        slots = swapped(slots, 1, request(code.upstream_a04, source, (source,)))
    else:
        context = req.context
        if fault == "cutoff":
            context = replace(
                context,
                information_cutoff=replace(
                    context.information_cutoff, source_text="2025-07-14T00:00:00+08:00"
                ),
            )
        else:
            field, value = {
                "mode": ("mode", "prospective_observed"),
                "snapshot": ("evidence_set_ref", "FOREIGN"),
                "calendar": ("calendar_ref", "FOREIGN"),
                "numeric": ("numeric_ref", "FOREIGN"),
                "policy": ("policy_refs", ("FOREIGN",)),
            }[fault]
            context = replace(context, **{field: value})
        slots = swapped(slots, 1, replace(req, context=context))
    result = evaluate_ratio(spec, sum_spec, slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert result.outcome.reason == result.upstream_a04.outcome.reason


def test_t12_sum_overflow_precedes_ratio_domain(code):
    result = run(code, values=(2**63 - 1, 1, 0))
    assert (
        result.outcome.state == "CONTRACT_VIOLATION"
        and result.outcome.reason == "INTEGER_SUM_OVERFLOW"
    )
    assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)


@pytest.mark.parametrize("value", [True, 1.0])
def test_t12_source_exact_integer_constructor_rejects_coercion(code, value):
    with pytest.raises(ContractError):
        inputs(code, values=(1, value, 3))


def test_t13_exact_ten_plus_two_observed_bytes_and_twelve_path_rejection(code):
    assert code.upstream_a04 == observe_derived_code(ROOT)
    assert len(code.upstream_a04.observed_working_files) == 10
    assert tuple(p.path for p in code.extension_pins) == RATIO_CODE_PATHS
    pins = (*code.upstream_a04.observed_working_files, *code.extension_pins)
    lengths = (*code.upstream_a04.byte_lengths, *code.extension_byte_lengths)
    for pin, length in zip(pins, lengths, strict=True):
        body = (ROOT / pin.path).read_bytes()
        assert sha256(body).hexdigest() == pin.sha256 and len(body) == length
    _, sum_spec, slots = inputs(code)
    twelve = replace(code.upstream_a04, observed_working_files=pins, byte_lengths=lengths)
    assert evaluate_derived(sum_spec, slots, twelve).outcome.reason == "INCOMPLETE_CODE_OBSERVATION"


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_order",
        "missing_pin",
        "missing_length",
        "bool_length",
        "negative_length",
        "zero_length",
        "upstream_twelve",
        "interpretation",
    ],
)
def test_t13_malformed_observation_structure_blocks(code, fault):
    spec, sum_spec, slots = inputs(code)
    if fault == "wrong_order":
        code = replace(code, extension_pins=tuple(reversed(code.extension_pins)))
    elif fault == "missing_pin":
        code = replace(code, extension_pins=code.extension_pins[:1])
    elif fault == "missing_length":
        code = replace(code, extension_byte_lengths=code.extension_byte_lengths[:1])
    elif fault in {"bool_length", "negative_length", "zero_length"}:
        n = {"bool_length": True, "negative_length": -1, "zero_length": 0}[fault]
        code = replace(code, extension_byte_lengths=(n, code.extension_byte_lengths[1]))
    elif fault == "upstream_twelve":
        code = replace(
            code,
            upstream_a04=replace(
                code.upstream_a04,
                observed_working_files=(
                    *code.upstream_a04.observed_working_files,
                    *code.extension_pins,
                ),
                byte_lengths=(*code.upstream_a04.byte_lengths, *code.extension_byte_lengths),
            ),
        )
    else:
        code = replace(
            code, upstream_a04=replace(code.upstream_a04, interpretation="COMMITTED_AND_TRUSTED")
        )
    result = evaluate_ratio(spec, sum_spec, slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"


def test_t13_well_shaped_self_asserted_pins_are_explicitly_unattested(code):
    spec, sum_spec, slots = inputs(code)
    fake = replace(
        code,
        extension_pins=(replace(code.extension_pins[0], sha256="0" * 64), code.extension_pins[1]),
        extension_byte_lengths=(1, code.extension_byte_lengths[1]),
    )
    result = evaluate_ratio(spec, sum_spec, slots, fake)
    assert result.code != observe_ratio_code(ROOT)
    assert "SUPPLIED_OBSERVATIONS_NOT_RUNTIME_ATTESTED" in result.code.verification_scope
    isolated(result)  # Shape consistency is never authenticity/admission.


@pytest.mark.parametrize("kind", ["assertion", "content", "representation"])
def test_t14_original_local_notice_nonendpoint_identity_guard_retained(code, kind):
    spec, sum_spec, slots = inputs(code)
    old = slots[2].request.candidates[0]
    new = month_source(
        code.upstream_a04, "A05-NEW", 6, 17_548_423, published="2025-07-04T14:00:00+08:00"
    )
    rel = revision(
        code.upstream_a04,
        old,
        new,
        subject_ref=old.subject.subject_ref,
        published="2025-07-04T14:00:00+08:00",
    )
    foreign, notice = slots[0].request.candidates[0].request, rel.notice.request
    origin_id, collision = {
        "assertion": (notice.assertion.assertion_ref, foreign.assertion.assertion_ref),
        "content": (notice.content.content_version_ref, foreign.content.content_version_ref),
        "representation": (notice.content.representation_ref, foreign.content.representation_ref),
    }[kind]
    rel = replace(rel, notice=rewrite(rel.notice, ids={origin_id: collision}))
    rel = replace(
        rel,
        relation=replace(
            rel.relation,
            origin=rel.notice.subject.metric.origin,
            notice_assertion_ref=collision
            if kind == "assertion"
            else rel.relation.notice_assertion_ref,
        ),
    )
    req = request(code.upstream_a04, old, (old, new), (rel,))
    result = evaluate_ratio(spec, sum_spec, swapped(slots, 2, req), code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert result.outcome.reason == "CONTRADICTORY_IMMUTABLE_IDENTITY"


def test_t15_sc01_apparent_success_never_grants_ratio_trust(code):
    spec, sum_spec, slots = inputs(code)
    source = slots[2].request.candidates[0]
    r = source.request
    binding = r.attempts[0].supplied
    origin = replace(binding.target.origin, object_id=OriginKnownValue("EVID-ORD1-TIME"))
    binding = replace(
        binding, evidence_ref="EVID-ORD1-TIME", target=replace(binding.target, origin=origin)
    )
    foreign = replace(
        next(m for m in r.scope.input_members if m.role == "evidence"), object_ref="EVID-ORD1-TIME"
    )
    r = replace(
        r,
        attempts=(replace(r.attempts[0], supplied=binding),),
        scope=replace(
            r.scope,
            input_members=tuple(sorted((*r.scope.input_members, foreign), key=lambda m: m.key)),
        ),
    )
    source = replace(source, request=r)
    result = evaluate_ratio(
        spec, sum_spec, swapped(slots, 2, request(code.upstream_a04, source, (source,))), code
    )
    actual = result.upstream_a04.dependencies[2].actual
    assert actual.inputs.candidates[0].actual.s1.state == "BOUND"
    assert actual.inputs.candidates[0].actual.s2.state == "SUPPORTED"
    assert actual.selection.state == "SELECTED" and result.outcome.state == "VALUE_AVAILABLE"
    isolated(result)


def test_t15_frozen_fields_no_agent_route(code):
    result = run(code)
    for field, value in (
        ("trust", "TRUSTED"),
        ("admission_eligible", True),
        ("source_authentication", "AUTHENTICATED"),
    ):
        with pytest.raises(ValueError):
            replace(result, **{field: value})
    with pytest.raises(FrozenInstanceError):
        result.admission_eligible = True
    isolated(result)


@pytest.mark.parametrize(
    "kind", ["positive", "zero_denominator", "negative", "conflict", "absent", "failed"]
)
def test_t16_audit_only_mutation_does_not_drive_any_branch_or_bytes(code, kind):
    options = {
        "positive": {},
        "zero_denominator": {"values": (0, 0, 0)},
        "negative": {"values": (-1, 2, 3)},
        "conflict": {"third": "conflict"},
        "absent": {"third": "absent"},
        "failed": {"check_status": "FAILED"},
    }[kind]
    spec, sum_spec, slots = inputs(code, **options)
    original = evaluate_ratio(spec, sum_spec, slots, code)
    upstream = original.upstream_a04
    dependencies = []
    for dep in upstream.dependencies:
        selection = dep.actual.selection
        if hasattr(selection, "research_only_audit"):
            selection = replace(
                selection,
                research_only_audit=tuple(reversed(selection.research_only_audit))
                + (ResearchAuditEntry("FUTURE", "PRIVATE-NOTE", "FUTURE-REVISED-TRUTH"),),
            )
        dependencies.append(replace(dep, actual=replace(dep.actual, selection=selection)))
    altered = replace(
        upstream,
        dependencies=tuple(dependencies),
        research_only_audit=tuple(reversed(upstream.research_only_audit)),
    )
    changed = _evaluate_completed(
        spec,
        sum_spec,
        slots,
        code,
        altered,
        annotations=("FUTURE-REVISION", "PRIVATE-INVESTIGATOR-NOTE"),
    )
    assert changed.upstream_a04 is altered
    assert changed.outcome == original.outcome
    assert changed.realization_ref == original.realization_ref
    assert changed.diagnostic_preview_bytes == original.diagnostic_preview_bytes


@pytest.mark.parametrize("fault", ["value", "state", "lineage", "context", "code", "preview"])
def test_t16_forged_completed_result_cannot_bypass_actual_a04(code, fault):
    spec, sum_spec, slots = inputs(code, third="conflict" if fault == "state" else "selected")
    original = evaluate_ratio(spec, sum_spec, slots, code)
    upstream = original.upstream_a04
    if fault == "value":
        upstream = replace(upstream, outcome=replace(upstream.outcome, value=42))
    elif fault == "state":
        upstream = replace(
            upstream, outcome=replace(upstream.outcome, state="VALUE_AVAILABLE", value=42)
        )
    elif fault == "lineage":
        line = upstream.outcome.lineage[2]
        upstream = replace(
            upstream,
            outcome=replace(
                upstream.outcome, lineage=(*upstream.outcome.lineage[:2], replace(line, value=1))
            ),
        )
    elif fault == "context":
        dep = upstream.dependencies[2]
        dep = replace(dep, slot=replace(dep.slot, request=slots[0].request))
        upstream = replace(upstream, dependencies=(*upstream.dependencies[:2], dep))
    elif fault == "code":
        upstream = replace(upstream, code=replace(upstream.code, head="0" * 40))
    else:
        upstream = replace(upstream, diagnostic_preview_bytes=b"PRIVATE-NOTE")
    result = _evaluate_completed(spec, sum_spec, slots, code, upstream)
    assert result.outcome.reason == "FORGED_OR_MISMAPPED_A04_RESULT"
    assert result.outcome.state == "CONTRACT_VIOLATION"


def test_t16_t17_repeat_permutation_and_snapshot_identity(code):
    spec, sum_spec, slots = inputs(code, revision_delta=10)
    result = evaluate_ratio(spec, sum_spec, slots, code)
    assert result == evaluate_ratio(spec, sum_spec, tuple(reversed(slots)), code)
    assert result == evaluate_ratio(spec, sum_spec, slots, code)
    newer = run(code, revision_delta=10, snapshot="E-A05-NEW")
    assert newer.outcome == result.outcome and newer.realization_ref != result.realization_ref
    assert newer.diagnostic_preview_bytes == result.diagnostic_preview_bytes
    assert result == evaluate_ratio(spec, sum_spec, slots, code)


def test_t18_preview_allowlist_exact_strings_and_no_research_ids(code):
    result = run(code, revision_delta=10)
    preview = json.loads(result.diagnostic_preview_bytes)
    assert set(preview) == {
        "preview_kind",
        "feature_ref",
        "cutoff",
        "mode",
        "value",
        "unit",
        "scale",
        "absence",
        "disposition",
        "trust",
        "source_authentication",
        "admission_eligible",
        "diagnostic_only",
    }
    assert type(preview["value"]) is str and preview["value"] == "0.308955"
    for forbidden in (
        "CV-",
        "REP-",
        "SUP-",
        "TP-",
        "CORRECTION",
        "NOTICE",
        "SCOPE-",
        "COVERAGE-",
        "SRC-",
        "FUTURE",
        "PRIVATE",
        "computed_at",
        "research_only_audit",
    ):
        assert forbidden not in result.diagnostic_preview_bytes.decode()


def test_t19_pure_public_evaluation_no_io_clock_or_observer(code, monkeypatch):
    spec, sum_spec, slots = inputs(code)

    def denied(*args, **kwargs):
        raise AssertionError("pure evaluation attempted I/O")

    for owner, name in (
        (builtins, "open"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (subprocess, "check_output"),
        (socket, "socket"),
    ):
        monkeypatch.setattr(owner, name, denied)
    import pit_research_lab.domain.ratio_slice as composer

    monkeypatch.setattr(composer, "observe_ratio_code", denied)
    assert evaluate_ratio(spec, sum_spec, slots, code).outcome.value.decimal_text == "0.308955"


def test_t19_ast_no_test_oracle_db_float_decimal_clock_implementation():
    for path in RATIO_CODE_PATHS:
        tree = ast.parse((ROOT / path).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(
            any(
                s in name
                for s in (
                    "tests",
                    "wu00",
                    "oracle",
                    "acceptance",
                    "sqlalchemy",
                    "psycopg",
                    "requests",
                    "decimal",
                )
            )
            for name in imports
        )
        assert not any(
            isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree)
        )
        # Path / relative_path belongs only to the explicit read-only observer;
        # numerical and request-based evaluation must not use true division.
        for function in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            if function.name != "observe_ratio_code":
                assert not any(
                    isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                    for n in ast.walk(function)
                )
        assert not any(
            isinstance(n, ast.Attribute) and n.attr in {"now", "today", "utcnow"}
            for n in ast.walk(tree)
        )
