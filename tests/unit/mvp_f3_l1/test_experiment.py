from dataclasses import replace
from fractions import Fraction as Q

import pytest

from pit_research_lab.mvp.f2.research_panel import PanelError
from pit_research_lab.mvp.f3_l1 import experiment as e
from pit_research_lab.mvp.f3_l1.contracts import (
    FOLDS,
    Protocol,
    decimal_text,
    fraction_read,
    fraction_wire,
)


def test_P04_independent_nonperfect_rational_ols():
    # x=(1,2,3), y=(1,2,2): Sxx=2, Sxy=1, SSE=1/6.
    gbar, rbar, alpha, beta = e.ols(((Q(1), Q(1)), (Q(2), Q(2)), (Q(3), Q(2))))
    assert (gbar, rbar, alpha, beta) == (Q(2), Q(5, 3), Q(2, 3), Q(1, 2))
    assert rbar + beta * (Q(4) - gbar) == Q(8, 3)
    assert sum(
        (alpha + beta * x - y) ** 2 for x, y in ((Q(1), Q(1)), (Q(2), Q(2)), (Q(3), Q(2)))
    ) == Q(1, 6)


def test_P06_independent_scores_aggregation_and_zero_baseline():
    a = (("a", Q(1), Q(2), Q(0)), ("b", Q(3), Q(1), Q(0)))
    b = (("c", Q(4), Q(0), Q(2)),)
    scores = e.metrics(a)
    assert fraction_read(scores["exact"]["mae"]) == Q(3, 2)
    assert fraction_read(scores["exact"]["mse"]) == Q(5, 2)
    assert fraction_read(scores["exact"]["mean_prediction_error"]) == Q(1, 2)
    aggregate = e.metrics(a + b)
    assert fraction_read(aggregate["exact"]["sse"]) == 21
    assert fraction_read(aggregate["oos_improvement"]) == Q(-4, 3)
    assert (
        fraction_read(aggregate["oos_improvement"])
        != (
            fraction_read(scores["oos_improvement"])
            + fraction_read(e.metrics(b)["oos_improvement"])
        )
        / 2
    )
    assert e.metrics((("zero", Q(1), Q(0), Q(0)),))["oos_improvement"] == {
        "state": "NOT_COMPUTABLE",
        "reason": "ZERO_BASELINE_SSE",
    }
    with pytest.raises(PanelError, match="DUPLICATE_OR_EMPTY_SCORE"):
        e.metrics(a + a)


def test_P03_fixed_folds_and_actual_maturity_purging(training, panel):
    assert FOLDS == (e.Fold("F1", 48, 48, 72), e.Fold("F2", 72, 72, 96))
    assert training.fit_cutoff == panel.cutoffs[48].replace("18:00:00", "17:00:00")
    assert len(training.samples) >= 180
    assert len({s.observation.tick for s in training.samples}) >= 40
    assert len({s.observation.issuer for s in training.samples}) >= 3
    assert all(
        s.outcome.available_at <= training.fit_cutoff and s.outcome.end < training.test_start_mark
        for s in training.samples
    )
    # Every candidate time contains all five issuers, included or explicitly excluded.
    considered = [s.observation.sample_id for s in training.samples] + [
        s for s, _ in training.excluded
    ]
    assert set(considered) == {f"{issuer}:t{t:02}" for t in range(48) for issuer in panel.issuers}
    assert any(reason == "IMMATURE_LABEL" for _, reason in training.excluded)


def test_N02_explicit_immature_member_cannot_silently_disappear(monkeypatch, panel, protocol):
    entered = []
    monkeypatch.setattr(e, "ols", lambda *_: entered.append(True))
    with pytest.raises(PanelError, match="IMMATURE_LABEL"):
        e.training_set(panel, FOLDS[0], protocol, declared_members=(f"{panel.issuers[0]}:t47",))
    assert entered == []


def test_N03_N04_N09_forged_training_floors_and_overlap_before_fit(monkeypatch, training, protocol):
    entered = []
    monkeypatch.setattr(e, "ols", lambda *_: entered.append(True))
    for challenged, reason in [
        (replace(training, samples=training.samples[:2]), "TRAINING_MEMBERSHIP_MISMATCH"),
        (replace(training, fit_cutoff=training.schedule[49]), "TRAINING_MEMBERSHIP_MISMATCH"),
    ]:
        with pytest.raises(PanelError, match=reason):
            e.fit(challenged, protocol)
    # Trusted kernel fault: a correctly sealed but insufficient set must still fail.
    limited = replace(training, samples=training.samples[:2])
    limited = replace(limited, _seal=e._seal(limited.payload()))
    with pytest.raises(PanelError, match="INSUFFICIENT_TRAINING_SAMPLE"):
        e.fit(limited, protocol)
    overlap = replace(training, test_start_mark=training.samples[0].outcome.end)
    overlap = replace(overlap, _seal=e._seal(overlap.payload()))
    with pytest.raises(PanelError, match="OUTCOME_OVERLAPS_TEST"):
        e.fit(overlap, protocol)
    duplicate = replace(training, samples=training.samples + (training.samples[0],))
    duplicate = replace(duplicate, _seal=e._seal(duplicate.payload()))
    with pytest.raises(PanelError, match="DUPLICATE_OR_UNORDERED_SAMPLE"):
        e.fit(duplicate, protocol)
    assert entered == []


def test_N04_protocol_and_fold_refusal_before_selection(monkeypatch, panel):
    entered = []
    monkeypatch.setattr(panel, "observation", lambda *_: entered.append(True))
    for fold in (replace(FOLDS[0], test_start=47), replace(FOLDS[0], history_end=60)):
        with pytest.raises(PanelError, match="INVALID_FOLD"):
            e.training_set(panel, fold, Protocol())
    for protocol in (
        replace(Protocol(), horizon_sessions=21),
        replace(Protocol(), seed=18),
        replace(Protocol(), folds=tuple(reversed(FOLDS))),
    ):
        with pytest.raises(PanelError, match="UNSUPPORTED_PROTOCOL"):
            e.training_set(panel, FOLDS[0], protocol)
    assert entered == []


def test_P05_N03_N05_no_test_label_capability_and_frozen_state(monkeypatch, state, panel, protocol):
    observations = tuple(panel.observation(i, t) for t in range(48, 72) for i in panel.issuers)
    entered = []

    def forbidden(*_):
        entered.append(True)
        raise AssertionError("test outcome accessor entered during predict")

    monkeypatch.setattr(panel, "outcome", forbidden)
    before = state.payload()
    batch = e.predict(state, observations, protocol)
    assert before == state.payload()
    assert e.fit(state.training, protocol).payload() == before
    assert entered == []
    assert all(
        set(r.payload())
        == {
            "sample_id",
            "issuer",
            "tick",
            "decision_time",
            "binding_id",
            "state",
            "value",
            "reason",
        }
        for r in batch.rows
    )
    # No public fit/predict argument can carry an outcome provider or test y.
    with pytest.raises(TypeError):
        e.predict(state, observations, protocol, test_y=forbidden)
    with pytest.raises(TypeError):
        e.fit(state.training, protocol, test_y=forbidden)
    wrong = replace(state, gbar=Q(100000000))
    with pytest.raises(PanelError, match="FITTED_STATE_MISMATCH"):
        e.predict(wrong, observations, protocol)
    with pytest.raises(PanelError, match="TEST_GRID_MISMATCH"):
        e.predict(state, observations[:-1], protocol)
    assert entered == []


def test_N09_numerical_and_canonical_refusals():
    with pytest.raises(PanelError, match="ZERO_GROWTH_VARIANCE"):
        e.ols(((Q(1), Q(1)), (Q(1), Q(2))))
    for pairs in (((True, Q(1)), (Q(2), Q(2))), ((0.5, Q(1)), (Q(2), Q(2)))):
        with pytest.raises(PanelError, match="INVALID_OLS_INPUT"):
            e.ols(pairs)
    for number in (
        {"numerator": "-0", "denominator": "1"},
        {"numerator": "2", "denominator": "4"},
        {"numerator": "01", "denominator": "1"},
        {"numerator": "1", "denominator": "0"},
        {"numerator": "+1", "denominator": "1"},
        {"numerator": "9" * 4097, "denominator": "1"},
    ):
        with pytest.raises(PanelError):
            fraction_read(number)
    assert fraction_wire(Q(-2, 3)) == {"numerator": "-2", "denominator": "3"}
    assert decimal_text(Q(-1, 10**15)) == "0.000000000000"
