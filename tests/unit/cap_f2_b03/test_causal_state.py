"""Independently calculated fitted-state and label eligibility expectations."""

from dataclasses import replace
from pathlib import Path

import pytest
from b03_inputs import asof, causal_request, fitted, statement

from pit_research_lab.domain.causal_derivation import (
    B03Outcome,
    B03Refusal,
    B03Result,
    FitReference,
    FrozenStandardizer,
    label_eligibility,
)
from pit_research_lab.domain.causal_slice import (
    evaluate_causal,
    fit_standardizer,
    observe_causal_code,
)
from pit_research_lab.domain.contracts import BlockingFailure

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_causal_code(ROOT)


@pytest.mark.parametrize(
    "view,mean,variance,text",
    [
        ("HISTORICAL_OBSERVATION_VIEW", (12, 1), (4, 1), "2.000000"),
        ("FIT_TIME_AVAILABLE_HISTORICAL_DATA_VIEW", (13, 1), (1, 1), "3.000000"),
    ],
)
def test_training_views_and_exact_population_oracle(code, view, mean, variance, text):
    request = causal_request(code, view=view)
    result = evaluate_causal(request, code)
    assert isinstance(result, B03Result)
    state = result.fit.outcome
    assert isinstance(state, FrozenStandardizer)
    assert state.mean == mean and state.variance == variance
    assert dict(result.rows[0].features)["quarter_revenue_zscore"].value.decimal_text == text
    assert result.fit.inputs[0].outcome.value == (10 if mean == (12, 1) else 12)
    # The unchanged original historical source request continues to select 10.
    from pit_research_lab.domain.derived_slice import evaluate_derived

    old = request.fit.rows[0].historical
    assert (
        evaluate_derived(
            old.specification, old.slots, code.upstream_ratio.upstream_a04
        ).outcome.value
        == 10
    )


def test_future_training_row_cannot_enter_an_earlier_fit(code):
    from b03_inputs import quarter, view_at

    from pit_research_lab.domain.causal_derivation import SumRequest, TrainingRow
    from pit_research_lab.domain.derived_slice import evaluate_derived

    fit = fitted(code, corrected=False)
    core = code.upstream_ratio.upstream_a04
    spec, slots = quarter(
        core,
        "FIT-FUTURE",
        year=2024,
        quarter=4,
        values=(111, 222, 666),
        published="2025-01-20T10:00:00+08:00",
        cutoff="2025-01-27T00:00:00+08:00",
    )
    historical = SumRequest(spec, slots)
    assert evaluate_derived(spec, slots, core).outcome.value == 999
    future = TrainingRow(
        "FUTURE", historical, view_at(core, historical, fit.context.information_cutoff.source_text)
    )
    rows = (*fit.rows, future)
    challenged = replace(fit, rows=rows, retained=FitReference(rows, fit.view, fit.context, code))
    decision = causal_request(code, fit_request=fit).context
    result = fit_standardizer(challenged, code, decision)
    assert result.outcome == B03Refusal("FUTURE_DEPENDENCY")


def test_completed_fit_inputs_are_replayed_not_self_certified(code):
    from pit_research_lab.domain.causal_derivation import _fit_completed

    fit = fitted(code, corrected=False)
    decision = causal_request(code, fit_request=fit).context
    original = fit_standardizer(fit, code, decision)
    good = _fit_completed(fit, code, decision, original.inputs)
    assert isinstance(good, FrozenStandardizer)
    assert good.mean == (12, 1) and good.variance == (4, 1)
    first = original.inputs[0]
    forged = replace(first, outcome=replace(first.outcome, value=11))
    bad = _fit_completed(fit, code, decision, (forged, *original.inputs[1:]))
    print("LEGITIMATE_MEAN=12 VARIANCE=4; FORGED_RESULT_TYPE=" + type(bad).__name__)
    assert isinstance(bad, BlockingFailure)
    assert bad.code == "COMPLETED_FIT_OWNER_MISMATCH"


def test_single_training_row_is_insufficient_not_zero_variance(code):
    fit = fitted(code)
    one = fit.rows[:1]
    request = causal_request(code, fit_request=fit)
    limited = replace(fit, rows=one, retained=FitReference(one, fit.view, fit.context, code))
    assert fit_standardizer(limited, code, request.context).outcome == B03Refusal(
        "INSUFFICIENT_FIT_ROWS"
    )


@pytest.mark.parametrize("value", [True, 1.0, 2**63, -(2**63) - 1])
def test_scalar_rejects_boolean_float_and_signed_overflow(value):
    from pit_research_lab.domain.causal_derivation import FixedScalar6
    from pit_research_lab.domain.contracts import ContractError

    with pytest.raises(ContractError):
        FixedScalar6(value, "0.000001")


@pytest.mark.parametrize("mutation", ["future_fit", "view", "member", "numeric", "labels"])
def test_fitted_state_refusals_retain_original_reference(code, mutation):
    request = causal_request(code, view="HISTORICAL_OBSERVATION_VIEW")
    fit = request.fit
    if mutation == "future_fit":
        fit = fitted(code, fit_cutoff="2025-01-20T00:00:00+08:00")
    elif mutation == "view":
        fit = replace(fit, view="FIT_TIME_AVAILABLE_HISTORICAL_DATA_VIEW")
    elif mutation == "member":
        fit = replace(fit, rows=fit.rows[:1])
    elif mutation == "numeric":
        fit = replace(fit, numerical_policy="SAMPLE_VARIANCE")
    else:
        fit = replace(fit, labels=("OWN_ROW_TARGET",))
    result = fit_standardizer(fit, code, request.context)
    if mutation in {"future_fit", "labels"}:
        assert isinstance(result.outcome, B03Refusal)
        assert result.outcome.code == (
            "FUTURE_DEPENDENCY" if mutation == "future_fit" else "UNSUPPORTED_FIT_FAMILY"
        )
    else:
        assert isinstance(result.outcome, BlockingFailure)


def test_non_square_variance_is_independent_sqrt_six_oracle(code):
    # [0, 4]: mean2, variance4. Use [0, 2] gives mean1,var1, no irrational.
    # [0, 2, 4] has mean2,var8/3; x6 gives sqrt(6) -> 2.449490.

    from b03_inputs import view_at

    from pit_research_lab.domain.causal_derivation import TrainingRow

    fit = fitted(code, row_values=((0, 0, 0), (0, 0, 2)), corrected=False)
    third = fit.rows[1]
    h = view_at(code.upstream_ratio.upstream_a04, third.historical, "2024-11-04T00:00:00+08:00")
    # New independent same-quarter row with separately built amount4.
    from b03_inputs import quarter

    from pit_research_lab.domain.causal_derivation import SumRequest

    spec, slots = quarter(
        code.upstream_ratio.upstream_a04,
        "FIT-R3",
        year=2024,
        quarter=3,
        values=(0, 0, 4),
        published="2024-10-04T10:00:00+08:00",
        cutoff="2024-11-04T00:00:00+08:00",
    )
    h = SumRequest(spec, slots)
    r3 = TrainingRow(
        "R3",
        h,
        view_at(code.upstream_ratio.upstream_a04, h, fit.context.information_cutoff.source_text),
    )
    fit = replace(
        fit,
        rows=(*fit.rows, r3),
        retained=FitReference((*fit.rows, r3), fit.view, fit.context, code),
    )
    request = causal_request(code, fit_request=fit, values=(0, 0, 6))
    result = evaluate_causal(request, code)
    assert isinstance(result, B03Result)
    assert result.fit.outcome.variance == (8, 3)
    assert dict(result.rows[0].features)["quarter_revenue_zscore"].value.decimal_text == "2.449490"


def test_zero_variance_is_domain_missing_not_standardized_zero(code):
    fit = fitted(code, row_values=((2, 3, 5), (2, 3, 5)), corrected=False)
    request = causal_request(code, fit_request=fit)
    result = evaluate_causal(request, code)
    assert isinstance(result, B03Result)
    assert result.fit.outcome == B03Outcome("NOT_COMPUTABLE", reason="ZERO_TRAINING_VARIANCE")


@pytest.mark.parametrize("own_row", [False, True])
def test_mature_label_guard_is_not_training_isolation(code, own_row):
    from datetime import date

    fit = fitted(code)
    row_context = fit.rows[0].historical.slots[0].request.context
    c = statement(
        code.upstream_ratio.upstream_a04,
        "LABEL",
        1,
        (date(2024, 7, 29), date(2024, 8, 26)),
        "2024-08-27T10:00:00+08:00",
        metric="FORWARD_FOUR_WEEK_LABEL",
        unit="LABEL_UNITS",
        currency="NOT_APPLICABLE",
        scope="synthetic_label_guard",
        basis="FOUR_WEEK_BINARY_OUTCOME-v0.1",
    )
    req = asof(code.upstream_ratio.upstream_a04, c, (c,), cutoff="2025-01-06T00:00:00+08:00")
    result = label_eligibility(
        row_context,
        req,
        req.context,
        code.upstream_ratio.upstream_a04,
        own_row_encoding=own_row,
    )
    if own_row:
        assert result == B03Refusal("WITHIN_SAMPLE_TARGET_LEAKAGE")
    else:
        assert result.selection.state == "SELECTED" and result.selection.selected_value == 1
    early = replace(
        req.context,
        information_cutoff=replace(
            req.context.information_cutoff, source_text="2024-08-12T00:00:00+08:00"
        ),
    )
    assert label_eligibility(
        row_context, req, early, code.upstream_ratio.upstream_a04
    ) == B03Refusal("IMMATURE_LABEL")


def test_prior_frozen_state_reuse_and_eight_row_ceiling(code):
    from datetime import timedelta

    from b03_inputs import view_at

    fit = fitted(code, corrected=False)
    first = fit.rows[0]
    start = first.historical.slots[0].request.context.information_cutoff.source_text
    from datetime import datetime

    rows = []
    for i in range(8):
        cutoff = (datetime.fromisoformat(start) + timedelta(weeks=i)).isoformat()
        historical = view_at(code.upstream_ratio.upstream_a04, first.historical, cutoff)
        rows.append(replace(first, row_ref="W" + str(i), historical=historical))
    fit8 = replace(
        fit, rows=tuple(rows), retained=FitReference(tuple(rows), fit.view, fit.context, code)
    )
    # Duplicate values on distinct weekly rows are legitimate; variance zero is a domain outcome.
    current = causal_request(code, fit_request=fit8)
    evaluated = fit_standardizer(fit8, code, current.context)
    assert evaluated.outcome == B03Outcome("NOT_COMPUTABLE", reason="ZERO_TRAINING_VARIANCE")
    fit9 = replace(fit8, rows=(*fit8.rows, replace(first, row_ref="NINTH")))
    assert fit_standardizer(fit9, code, current.context).outcome.code == "FIT_ROW_LIMIT"
    ordinary = causal_request(code, fit_request=fit)
    later = causal_request(code, fit_request=fit, cutoff="2025-01-20T00:00:00+08:00")
    a, b = evaluate_causal(ordinary, code), evaluate_causal(later, code)
    assert isinstance(a, B03Result) and isinstance(b, B03Result)
    assert a.fit.outcome.state_ref == b.fit.outcome.state_ref


@pytest.mark.parametrize("current,expected", [(1, "0.000000"), (3, "0.000002"), (-1, "0.000000")])
def test_scalar_half_even_ties_and_no_negative_zero(code, current, expected):
    from decimal import ROUND_DOWN, localcontext

    fit = fitted(code, row_values=((-2_000_000, 0, 0), (2_000_000, 0, 0)), corrected=False)
    request = causal_request(
        code,
        fit_request=fit,
        values=(current, 0, 0),
        keys=("derived_quarter_revenue", "quarter_revenue_zscore"),
    )
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.rounding = ROUND_DOWN
        result = evaluate_causal(request, code)
    assert isinstance(result, B03Result)
    assert dict(result.rows[0].features)["quarter_revenue_zscore"].value.decimal_text == expected


def test_observed_fitting_is_explicitly_unsupported(code):
    request = causal_request(code, view="HISTORICAL_OBSERVATION_VIEW")
    context = replace(request.fit.context, mode="prospective_observed")
    fit = replace(
        request.fit,
        context=context,
        retained=FitReference(request.fit.rows, request.fit.view, context, code),
    )
    assert fit_standardizer(fit, code, request.context).outcome == B03Refusal(
        "UNSUPPORTED_B03_OBSERVED_PROFILE"
    )


def _r1_project(request, result, code):
    from pit_research_lab.domain.diagnostic_projection import ProjectionPolicy, project_candidate

    return project_candidate(
        request.context,
        request.specifications,
        result,
        result.universe if isinstance(result, B03Result) else result,
        ProjectionPolicy(
            tuple(sorted(s.key for s in request.specifications)), request.allowed_missing
        ),
        code,
    )


def _r1_clock_block(fit, code, reason, *, decision_cutoff=None):
    from pit_research_lab.domain.causal_derivation import _fit_completed
    from pit_research_lab.domain.derived_slice import evaluate_derived
    from pit_research_lab.domain.diagnostic_projection import ProjectionBlocked

    request = causal_request(code, fit_request=fit, cutoff=decision_cutoff)
    direct = fit_standardizer(fit, code, request.context)
    inputs = tuple(
        evaluate_derived(s.specification, s.slots, code.upstream_ratio.upstream_a04)
        for r in fit.rows
        for s in (r.historical if fit.view == "HISTORICAL_OBSERVATION_VIEW" else r.fit_time,)
    )
    internal = _fit_completed(fit, code, request.context, inputs)
    full = evaluate_causal(request, code)
    projected = _r1_project(request, full, code)
    print(
        "R1_CLOCK",
        reason,
        "DIRECT",
        type(direct.outcome).__name__,
        "INTERNAL",
        type(internal).__name__,
        "FULL",
        type(full).__name__,
        "PROJECTED",
        type(projected).__name__,
    )
    for result in (direct.outcome, internal, full):
        assert isinstance(result, BlockingFailure)
        assert result.category == "CONTRACT_VIOLATION" and result.code == reason
    assert isinstance(projected, ProjectionBlocked) and projected.code == reason
    assert not hasattr(projected, "candidate_bytes")


def test_r1_p1a_same_day_source_is_valid_at_0700_but_not_weekly_observation(code):
    from pit_research_lab.domain.derived_slice import evaluate_derived
    from pit_research_lab.domain.diagnostic_projection import DiagnosticProjectionCandidate

    core = code.upstream_ratio.upstream_a04
    lawful = fitted(code, correction_time="2024-07-29T06:00:00+08:00")
    late = fitted(
        code,
        correction_time="2024-07-29T06:00:00+08:00",
        historical_cutoffs=("2024-07-29T07:00:00+08:00", "2024-10-28T00:00:00+08:00"),
    )
    old, new = (
        evaluate_derived(f.rows[0].historical.specification, f.rows[0].historical.slots, core)
        for f in (lawful, late)
    )
    assert old.outcome.value == 10 and new.outcome.value == 12
    selected = new.dependencies[2].actual.selection.selected_assertion_refs[0]
    for summed, state in ((old, "NOT_ADMISSIBLE"), (new, "SUPPORTED")):
        leaf = next(c for c in summed.dependencies[2].actual.inputs.candidates if c.ref == selected)
        assert leaf.actual.s1.state == "BOUND" and leaf.actual.s2.state == state
    assert new.dependencies[2].actual.selection.state == "SELECTED"
    print("P1A_OWNER_PROOF midnight=10 0700=12; corrected source S1=BOUND S2=SUPPORTED S3=SELECTED")
    good_request = causal_request(code, fit_request=lawful)
    good = evaluate_causal(good_request, code)
    assert isinstance(good, B03Result) and good.fit.outcome.mean == (12, 1)
    assert good.fit.outcome.variance == (4, 1)
    assert dict(good.rows[0].features)["quarter_revenue_zscore"].value.decimal_text == "2.000000"
    assert isinstance(_r1_project(good_request, good, code), DiagnosticProjectionCandidate)
    _r1_clock_block(late, code, "INVALID_HISTORICAL_OBSERVATION_CUTOFF")


def test_r1_p1b_fit_day_0600_source_cannot_expand_midnight_fit_view(code):
    from pit_research_lab.domain.derived_slice import evaluate_derived

    view = "FIT_TIME_AVAILABLE_HISTORICAL_DATA_VIEW"
    lawful = fitted(code, view=view, correction_time="2025-01-06T06:00:00+08:00")
    late = fitted(
        code,
        view=view,
        correction_time="2025-01-06T06:00:00+08:00",
        fit_cutoff="2025-01-06T07:00:00+08:00",
    )
    values = []
    for f in (lawful, late):
        s = f.rows[0].fit_time
        actual = evaluate_derived(s.specification, s.slots, code.upstream_ratio.upstream_a04)
        values.append(actual.outcome.value)
    assert values == [10, 12]
    decision = causal_request(code, fit_request=lawful).context
    good = fit_standardizer(lawful, code, decision).outcome
    assert isinstance(good, FrozenStandardizer) and good.mean == (12, 1)
    print("P1B_OWNER_PROOF fit0000=10 fit0700=12; own Jan06T06 correction")
    _r1_clock_block(late, code, "INVALID_FIT_CUTOFF")


@pytest.mark.parametrize(
    "view", ["HISTORICAL_OBSERVATION_VIEW", "FIT_TIME_AVAILABLE_HISTORICAL_DATA_VIEW"]
)
@pytest.mark.parametrize("role", ["historical", "fit_time"])
@pytest.mark.parametrize("slot_index", [0, 1, 2])
def test_r1_p1c_later_row_every_slot_has_its_own_clock_guard(code, view, role, slot_index):
    from b03_inputs import view_at

    from pit_research_lab.domain.asof_slice import evaluate_asof

    fit = fitted(code, view=view)
    row = fit.rows[1]
    original = getattr(row, role)
    cutoff = "2024-10-28T07:00:00+08:00" if role == "historical" else "2025-01-06T07:00:00+08:00"
    rebuilt = view_at(code.upstream_ratio.upstream_a04, original, cutoff)
    slot = rebuilt.slots[slot_index]
    actual = evaluate_asof(slot.request, code.upstream_ratio.upstream_a04)
    assert actual.selection.state == "SELECTED"
    assert actual.inputs.candidates[0].actual.s1.state == "BOUND"
    assert actual.inputs.candidates[0].actual.s2.state == "SUPPORTED"
    slots = tuple(slot if i == slot_index else s for i, s in enumerate(original.slots))
    rows = (fit.rows[0], replace(row, **{role: replace(original, slots=slots)}))
    challenged = replace(fit, rows=rows, retained=FitReference(rows, fit.view, fit.context, code))
    _r1_clock_block(
        challenged,
        code,
        "INVALID_HISTORICAL_OBSERVATION_CUTOFF" if role == "historical" else "INVALID_FIT_CUTOFF",
    )


@pytest.mark.parametrize(
    "cutoff,zone,reason,source_supported",
    [
        (
            "2024-10-28T00:00:00+08:00",
            "Asia/Shanghai",
            "INVALID_HISTORICAL_OBSERVATION_CUTOFF",
            True,
        ),
        ("2024-10-28T00:00:00+00:00", "UTC", "INVALID_HISTORICAL_OBSERVATION_CUTOFF", True),
        ("2024-10-28T00:00:00+00:00", "Asia/Taipei", "ZONE_OFFSET_CONFLICT", False),
    ],
)
def test_r1_p1c_noncanonical_zone_offset_preserves_s2_validation(
    code, cutoff, zone, reason, source_supported
):
    from b03_inputs import view_at

    from pit_research_lab.domain.asof_slice import evaluate_asof

    fit = fitted(code)
    historical = view_at(
        code.upstream_ratio.upstream_a04, fit.rows[1].historical, cutoff, cutoff_timezone=zone
    )
    actual = evaluate_asof(historical.slots[0].request, code.upstream_ratio.upstream_a04)
    if source_supported:
        assert actual.selection.state == "SELECTED"
    else:
        assert isinstance(actual.selection, BlockingFailure)
    rows = (fit.rows[0], replace(fit.rows[1], historical=historical))
    fit = replace(fit, rows=rows, retained=FitReference(rows, fit.view, fit.context, code))
    if not source_supported:
        # S2 rejects the contradictory descriptor already. It cannot be sorted
        # into a valid plan; test the direct owner boundary, not a fake plan.
        decision = fitted(code).context
        result = fit_standardizer(fit, code, decision).outcome
        assert isinstance(result, BlockingFailure) and result.code == reason
        return
    _r1_clock_block(fit, code, reason)


def test_r1_direct_fit_and_completed_fit_also_check_decision_midnight(code):
    _r1_clock_block(
        fitted(code), code, "INVALID_DECISION_CUTOFF", decision_cutoff="2025-01-13T07:00:00+08:00"
    )


@pytest.mark.parametrize("role", ["row", "fit"])
def test_r1_p1e_mature_label_guard_does_not_relax_weekly_role_clock(code, role):
    from datetime import date

    from b03_inputs import view_at

    from pit_research_lab.domain.asof_slice import evaluate_asof

    core = code.upstream_ratio.upstream_a04
    f = fitted(code)
    row = view_at(
        core,
        f.rows[0].historical,
        "2024-07-29T07:00:00+08:00" if role == "row" else "2024-07-29T00:00:00+08:00",
    )
    c = statement(
        core,
        "R1-LABEL-" + role,
        1,
        (date(2024, 7, 29), date(2024, 8, 26)),
        "2024-08-27T10:00:00+08:00",
        metric="FORWARD_FOUR_WEEK_LABEL",
        unit="LABEL_UNITS",
        currency="NOT_APPLICABLE",
        scope="synthetic_label_guard",
        basis="FOUR_WEEK_BINARY_OUTCOME-v0.1",
    )
    req = asof(
        core,
        c,
        (c,),
        cutoff="2025-01-06T07:00:00+08:00" if role == "fit" else "2025-01-06T00:00:00+08:00",
    )
    assert evaluate_asof(req, core).selection.selected_value == 1
    result = label_eligibility(row.slots[0].request.context, req, req.context, core)
    assert isinstance(result, BlockingFailure)
    assert result.code == (
        "INVALID_HISTORICAL_OBSERVATION_CUTOFF" if role == "row" else "INVALID_FIT_CUTOFF"
    )
