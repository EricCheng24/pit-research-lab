import copy
import json
from dataclasses import replace
from datetime import timedelta

import pytest

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f3_l1 import experiment as e


def variant():
    return json.loads((f2.ROOT / f2.FIXTURE).read_bytes())


def row_for(body, issuer="SYN-L1-2", month="2024-04"):
    return [r for r in body["revenues"] if r["issuer"] == issuer and r["month"] == month]


def test_P01_N01_before_at_after_and_revision_isolation():
    body = variant()
    rows = row_for(body)
    code = f2.observe_asof_code(f2.ROOT)
    # Independent fixture facts: correction arrives exactly at May 17 cutoff.
    old_amount = rows[0]["amount"]
    before = f2._select(rows, "2024-05-17T18:00:00+08:00", f2.SOURCE_SHA256, code)
    after = f2._select(rows, "2024-05-17T18:00:01+08:00", f2.SOURCE_SHA256, code)
    assert before.amount == old_amount and before.source_ref == "SYN-L1-2-REV-2024-04"
    assert after.amount == 1023 and after.source_ref.endswith("-R1")
    poisoned = copy.deepcopy(rows)
    poisoned[1]["amount"] = 999999999
    assert f2._select(poisoned, "2024-05-17T18:00:00+08:00", f2.SOURCE_SHA256, code) == before
    original = rows[:1]
    stamp = original[0]["available_at"]
    assert f2._select(original, stamp, f2.SOURCE_SHA256, code).state == "ABSENT"
    assert (
        f2._select(
            original, (f2.instant(stamp) - timedelta(seconds=1)).isoformat(), f2.SOURCE_SHA256, code
        ).state
        == "ABSENT"
    )
    assert (
        f2._select(
            original, (f2.instant(stamp) + timedelta(seconds=1)).isoformat(), f2.SOURCE_SHA256, code
        ).amount
        == old_amount
    )


@pytest.mark.parametrize("status", ["UNKNOWN", "WITHHELD", "ABSENT", "NOT_EVALUATED", "REJECTED"])
def test_N07_distinct_status_no_fallback_or_zero(status):
    body = variant()
    for row in row_for(body, issuer="SYN-L1-1", month="2024-04"):
        row["state"], row["amount"] = status, None
    panel = f2.ResearchPanel(body, _key=f2._LOADER)  # trusted adversarial test seam only
    tick = next(i for i, t in enumerate(panel.cutoffs) if t.startswith("2024-05-17"))
    obs = panel.observation(panel.issuers[0], tick)
    assert obs.current.month == "2024-04" and obs.current.state == status
    assert obs.current.amount is None
    with pytest.raises(f2.PanelError, match="INFORMATION_" + status):
        e.growth(obs)


def test_N06_raw_panel_forged_observation_and_identity(panel):
    with pytest.raises(f2.PanelError, match="DETACHED_OBSERVATION_REQUIRED"):
        e.growth(variant())
    obs = panel.observation(panel.issuers[1], 20)
    for changed in [
        replace(obs, dataset_digest="0" * 64),
        replace(obs, issuer=panel.issuers[0]),
        replace(obs, cutoff=panel.cutoffs[21]),
        replace(obs, binding_id="0" * 64),
        replace(obs, current=replace(obs.current, amount=10000000)),
    ]:
        with pytest.raises(f2.PanelError, match="OBSERVATION_BINDING_MISMATCH"):
            f2.verify_observation(changed)
    with pytest.raises(f2.PanelError, match="PINNED_LOADER_REQUIRED"):
        f2.ResearchPanel(variant())


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("duplicate_tick", "FIXED_DECISION_SCHEDULE"),
        ("reverse_tick", "FIXED_DECISION_SCHEDULE"),
        ("calendar", "SESSION_CLOCK"),
        ("price", "PRICE_VALUE"),
        ("grid", "PRICE_GRID"),
        ("unit", "SOURCE_UNIT_BASIS"),
        ("basis", "SOURCE_UNIT_BASIS"),
        ("duplicate", "DUPLICATE_SOURCE"),
        ("delivery", "DELIVERY_BEFORE_PUBLICATION"),
    ],
)
def test_N04_N06_N09_structural_rejection_before_native(monkeypatch, mutation, reason):
    body = variant()
    if mutation == "duplicate_tick":
        body["cutoffs"][1] = body["cutoffs"][0]
    if mutation == "reverse_tick":
        body["cutoffs"].reverse()
    if mutation == "calendar":
        body["calendar"][0]["close"] = "2024-01-02T13:30:00+08:00"
    if mutation == "price":
        body["prices"][0]["value"] = 0
    if mutation == "grid":
        body["prices"].pop()
    if mutation == "unit":
        body["revenues"][0]["unit"] = "USD"
    if mutation == "basis":
        body["revenues"][0]["basis"] = "foreign"
    if mutation == "duplicate":
        body["revenues"].append(body["revenues"][0])
    if mutation == "delivery":
        body["revenues"][0]["available_at"] = "2024-01-01T00:00:00+08:00"
    entered = []
    monkeypatch.setattr(f2, "evaluate_asof", lambda *_: entered.append(True))
    with pytest.raises(f2.PanelError, match=reason):
        f2.ResearchPanel(body, _key=f2._LOADER)
    assert entered == []


def test_P02_N02_maturity_end_is_not_availability(panel):
    obs = panel.observation(panel.issuers[1], 20)
    timing = panel.target_timing(obs)
    before = (f2.instant(timing["available_at"]) - timedelta(seconds=1)).isoformat()
    count = panel.native_invocations
    with pytest.raises(f2.PanelError, match="IMMATURE_LABEL"):
        e.target(panel, obs, before)
    assert panel.native_invocations == count  # even price qualification is not entered
    actual = e.target(panel, obs, timing["available_at"])
    e.validate_target(actual, obs, actual.available_at)  # equality at semantic fit is legal
    values = replace(
        actual, available_at=(f2.instant(actual.available_at) + timedelta(seconds=1)).isoformat()
    )
    values = replace(values, _seal=e._seal(values.payload()))  # trusted delayed-label challenge
    with pytest.raises(f2.PanelError, match="IMMATURE_LABEL"):
        e.validate_target(values, obs, actual.available_at)
    assert timing["end"] < timing["available_at"][:10]


def test_N02_delayed_price_delivery_changes_maturity_before_any_read(panel, training):
    sample = training.samples[-1]
    body = variant()
    delayed = (f2.instant(training.fit_cutoff) + timedelta(seconds=1)).isoformat()
    price = next(
        r
        for r in body["prices"]
        if r["issuer"] == sample.observation.issuer and r["session"] == sample.outcome.end
    )
    price["available_at"] = training.fit_cutoff
    exact = f2.ResearchPanel(body, _key=f2._LOADER)
    exact_obs = exact.observation(sample.observation.issuer, sample.observation.tick)
    accepted = e.target(exact, exact_obs, training.fit_cutoff)
    assert accepted.available_at == training.fit_cutoff
    e.validate_target(accepted, exact_obs, training.fit_cutoff)
    price["available_at"] = delayed
    challenged = f2.ResearchPanel(body, _key=f2._LOADER)
    obs = challenged.observation(sample.observation.issuer, sample.observation.tick)
    assert challenged.target_timing(obs)["available_at"] == delayed
    before = challenged.native_invocations
    with pytest.raises(f2.PanelError, match="IMMATURE_LABEL"):
        e.target(challenged, obs, training.fit_cutoff)
    assert challenged.native_invocations == before


def test_N07_unavailable_population_blocks_fit_before_ols(monkeypatch, protocol):
    body = variant()
    for row in body["revenues"]:
        row["state"], row["amount"] = "WITHHELD", None
    challenged = f2.ResearchPanel(body, _key=f2._LOADER)
    selected = e.training_set(challenged, e.FOLDS[0], protocol)
    assert not selected.samples
    assert len(selected.excluded) == 240
    entered = []
    monkeypatch.setattr(e, "ols", lambda *_: entered.append(True))
    with pytest.raises(f2.PanelError, match="INSUFFICIENT_TRAINING_SAMPLE"):
        e.fit(selected, protocol)
    assert entered == []


def test_N06_source_pins_and_closed_time_numeric(monkeypatch):
    original = f2.Path.read_bytes

    def changed(path):
        if str(path).endswith(f2.FIXTURE):
            return original(path) + b" "
        return original(path)

    monkeypatch.setattr(f2.Path, "read_bytes", changed)
    entered = []
    monkeypatch.setattr(f2, "ResearchPanel", lambda *_a, **_k: entered.append(True))
    with pytest.raises(f2.PanelError, match="SOURCE_PIN_MISMATCH"):
        f2.load_panel()
    assert not entered
    for bad in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":0.5}'):
        with pytest.raises(f2.PanelError):
            f2.decode(bad)
    for time in ("2024-01-01", "2024-01-01T00:00:00", "2024-01-01T00:00:00.1+08:00"):
        with pytest.raises(f2.PanelError):
            f2.instant(time)


def test_P05_N01_actual_future_source_and_price_poison_preserves_estimation(state, protocol):
    # A new in-memory source edition must have new identities, but must not change
    # parameters learned before the poisoned source/price interval was available.
    body = variant()
    for row in body["revenues"]:
        if row["publication"] > "2025-06-01" and row["state"] == "KNOWN":
            row["amount"] = 1000000000
    for mark in body["prices"]:
        if mark["session"] > "2025-06-01":
            mark["value"] += 1000000000
    changed = f2.ResearchPanel(body, _key=f2._LOADER)
    trained = e.fit(e.training_set(changed, e.FOLDS[0], protocol), protocol)
    assert (trained.gbar, trained.rbar, trained.alpha, trained.beta) == (
        state.gbar,
        state.rbar,
        state.alpha,
        state.beta,
    )
    assert trained.payload()["training_ids"] == state.payload()["training_ids"]
    assert trained.training.dataset_digest != state.training.dataset_digest
    assert trained.state_id != state.state_id  # never reuse provenance for changed bytes
