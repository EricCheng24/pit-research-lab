"""Hand-authored rule oracles, never genuine F3 predictions or performance evidence."""

from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as Q

import pytest

from pit_research_lab.mvp.f5.contracts import (
    CALENDAR_SHA,
    POLICIES,
    DecisionFact,
    DecisionForecast,
    DecisionObservation,
    F5Error,
    IssuerInput,
)
from pit_research_lab.mvp.f5.policies import choose


def manual_observation(
    states=("KNOWN", "KNOWN"), growth=(Q(1, 10), Q(-1, 20)), forecasts=(Q(-1, 50), Q(3, 100))
):
    cells = []
    for name, state, g, prediction in zip(("A", "B"), states, growth, forecasts, strict=True):
        previous = DecisionFact(
            "2024-12",
            "KNOWN",
            100,
            "NTD_thousands",
            "consolidated-v1",
            name + "-P",
            name + "-P-VERSION",
            "2025-01-10T12:00:00+08:00",
            "2025-01-10T12:01:00+08:00",
            "SELECTED",
            "NONE",
            "1" * 64,
        )
        known = state == "KNOWN"
        current = DecisionFact(
            "2025-01",
            state,
            int(100 * (1 + g)) if known else None,
            "NTD_thousands",
            "consolidated-v1",
            name + "-C",
            name + "-C-VERSION",
            "2025-02-10T12:00:00+08:00",
            "2025-02-10T12:01:00+08:00",
            "SELECTED",
            "NONE" if known else state,
            "2" * 64,
        )
        reason = "NONE" if known else "INFORMATION_" + state
        forecast = DecisionForecast(
            name + ":t48",
            name,
            48,
            "2025-02-14T18:00:00+08:00",
            "3" * 64,
            CALENDAR_SHA,
            "4" * 64,
            "F1",
            "2025-02-14T17:00:00+08:00",
            "5" * 64,
            "6" * 64,
            "OLS_INTERCEPT_ONE_REGRESSOR_V1",
            20,
            "PREDICTED" if known else "UNAVAILABLE",
            prediction if known else None,
            reason,
        )
        cells.append(
            IssuerInput(
                name,
                name + ":t48",
                "4" * 64,
                current,
                previous,
                g if known else None,
                "KNOWN" if known else "UNAVAILABLE",
                reason,
                forecast,
                known,
                reason,
            )
        )
    return DecisionObservation(
        48, "2025-02-14T18:00:00+08:00", CALENDAR_SHA, "3" * 64, tuple(cells)
    )


def targets(action):
    return tuple(w for _, w in action.weights) + (action.cash_weight,)


def test_shared_projection_distinct_policy_targets():
    obs = manual_observation()
    decisions = [choose(obs, p) for p in POLICIES]
    assert [targets(a) for a in decisions] == [
        (Q(1, 2), Q(1, 2), Q()),
        (Q(1, 2), Q(), Q(1, 2)),
        (Q(), Q(1, 2), Q(1, 2)),
    ]
    assert {a.information_digest for a in decisions} == {obs.information_digest}
    assert decisions[1].issuer_reasons == (
        ("A", "POSITIVE_GROWTH_SELECTED"),
        ("B", "NONPOSITIVE_GROWTH"),
    )
    assert decisions[2].issuer_reasons == (
        ("A", "NONPOSITIVE_FORECAST"),
        ("B", "POSITIVE_FORECAST_SELECTED"),
    )
    with pytest.raises(F5Error, match="ISSUER_GRID"):
        obs.validate(production=True)  # 2-name oracle cannot weaken 5-name production.


@pytest.mark.parametrize("state", ["WITHHELD", "UNKNOWN", "ABSENT", "NOT_EVALUATED", "REJECTED"])
def test_withheld_partial_universe_and_cash_vs_abstain(state):
    obs = manual_observation((state, "KNOWN"))
    actions = [choose(obs, p) for p in POLICIES]
    assert [targets(a) for a in actions] == [
        (Q(), Q(1, 2), Q(1, 2)),
        (Q(), Q(), Q(1)),
        (Q(), Q(1, 2), Q(1, 2)),
    ]
    assert actions[1].disposition == "CASH"
    assert all(a.reason == "PARTIAL_INFORMATION" for a in actions)
    assert obs.issuers[0].current.amount is None and obs.issuers[0].forecast.value is None
    absent = manual_observation((state, state))
    for p in POLICIES:
        a = choose(absent, p)
        assert a.disposition == "ABSTAIN" and targets(a) == (Q(), Q(), Q(1))


def test_ties_zero_negative_signals_and_weight_validation():
    obs = manual_observation(growth=(Q(1, 10), Q(1, 10)), forecasts=(Q(), Q()))
    assert targets(choose(obs, POLICIES[1])) == (Q(1, 2), Q(1, 2), Q())
    assert choose(obs, POLICIES[2]).disposition == "CASH"
    action = choose(obs, POLICIES[0])
    for bad in (
        replace(action, weights=(("A", Q(-1)), ("B", Q(2)))),
        replace(action, weights=(("FOREIGN", Q(1, 2)), ("B", Q(1, 2)))),
        replace(action, cash_weight=Q(1)),
        replace(action, weights=(("A", 0.5), ("B", Q(1, 2)))),
    ):
        with pytest.raises(F5Error):
            bad.validate(obs, POLICIES[0])


def test_future_revision_does_not_change_prior_targets():
    obs = manual_observation()
    before = tuple(targets(choose(obs, p)) for p in POLICIES)
    future_revision = {"amount": 999999999, "available_at": "2025-02-14T18:00:01+08:00"}
    future_revision["amount"] = -999999999
    assert tuple(targets(choose(obs, p)) for p in POLICIES) == before
    contaminated = replace(
        obs,
        issuers=(
            replace(
                obs.issuers[0], current=replace(obs.issuers[0].current, available_at=obs.cutoff)
            ),
            obs.issuers[1],
        ),
    )
    with pytest.raises(F5Error, match="FUTURE_FEATURE"):
        choose(contaminated, POLICIES[0])
    with pytest.raises(TypeError):
        choose(obs, POLICIES[0], future_prices=future_revision)


def test_immature_forecast_not_a_successful_abstention():
    obs = manual_observation()
    bad = replace(obs.issuers[0].forecast, fit_cutoff="2025-02-14T18:00:01+08:00")
    with pytest.raises(F5Error, match="FORECAST_FOLD_FIT"):
        choose(
            replace(obs, issuers=(replace(obs.issuers[0], forecast=bad), obs.issuers[1])),
            POLICIES[2],
        )
    bad = replace(obs.issuers[0].forecast, state="UNAVAILABLE", value=None, reason="IMMATURE_LABEL")
    with pytest.raises(F5Error, match="FORECAST_UNAVAILABLE"):
        choose(
            replace(obs, issuers=(replace(obs.issuers[0], forecast=bad), obs.issuers[1])),
            POLICIES[2],
        )


def test_frozen_detached_values_have_no_reachable_evaluator():
    obs = manual_observation()

    def walk(v):
        if is_dataclass(v):
            assert not hasattr(v, "__dict__")
            for f in fields(v):
                assert f.name not in {"panel", "result", "target", "callback", "resolver", "path"}
                walk(getattr(v, f.name))
        elif type(v) is tuple:
            for child in v:
                walk(child)
        else:
            assert v is None or type(v) in (str, int, bool, Q)

    walk(obs)
    with pytest.raises(FrozenInstanceError):
        obs.tick = 49


def test_callback_or_extra_forecast_object_cannot_enter_policy():
    obs = manual_observation()
    called = []

    def resolver():
        called.append(True)
        return "FUTURE"

    bad = replace(obs.issuers[0].current, source_id=resolver)
    with pytest.raises(F5Error, match="UNSAFE_DECISION_FACT"):
        choose(
            replace(obs, issuers=(replace(obs.issuers[0], current=bad), obs.issuers[1])),
            POLICIES[0],
        )
    assert called == []


def test_unavailable_fact_cannot_reveal_future_provenance():
    obs = manual_observation(("WITHHELD", "KNOWN"))
    future = replace(obs.issuers[0].current, publication="2026-01-01T12:00:00+08:00")
    with pytest.raises(F5Error, match="FUTURE_FEATURE_REFUSED"):
        choose(
            replace(obs, issuers=(replace(obs.issuers[0], current=future), obs.issuers[1])),
            POLICIES[0],
        )
