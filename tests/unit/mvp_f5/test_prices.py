"""Real bounded synthetic S1/S2 price qualification, never a real-market claim."""

from dataclasses import replace
from datetime import timedelta

import pytest

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f5 import prices
from pit_research_lab.mvp.f5.contracts import (
    POLICIES,
    DecisionSlot,
    EngineFailureDisposition,
    F5Error,
    digest,
    seal_slots,
)


def unit_barrier():
    """Typed failed slots at a trusted unit seam, NOT producer/policy execution."""
    cutoffs = prices.pinned_body()["cutoffs"]
    slots = []
    for tick in range(48, 96):
        for p in POLICIES:
            failure = digest(
                {
                    "tick": tick,
                    "cutoff": cutoffs[tick],
                    "policy_id": p,
                    "information_digest": "0" * 64,
                    "failure_cause": "UNIT_SEAM",
                }
            )
            slots.append(
                DecisionSlot(
                    tick,
                    cutoffs[tick],
                    p,
                    "0" * 64,
                    "FAILED_POLICY",
                    True,
                    failure,
                    None,
                    "UNIT_SEAM",
                    EngineFailureDisposition(failure),
                )
            )
    return seal_slots(tuple(slots), None)


@pytest.fixture(scope="module")
def barrier():
    return unit_barrier()


def test_exact_13_compatibility_pins_and_real_price_receipt(barrier):
    assert len(prices.COMPATIBILITY) == 13
    prices.check_compatibility()
    feed = prices.EvaluationPrices(barrier)
    mark = feed.read_mark("SYN-L1-1", "2025-02-17", "2025-02-17T13:30:01+08:00")
    assert mark.native_s1_state == "BOUND" and mark.native_s2_state == "SUPPORTED"
    assert mark.value_ticks > 0 and mark.unit == "NTD_price_ticks_1e4"
    assert mark.witness_kind == "PINNED_AUTHORED_DELIVERY"
    assert mark.original_publication_state == "NOT_PROVIDED_IN_PRICE_ROW"
    assert mark.diagnostic_only and not mark.admission_eligible
    assert (
        mark.trust == "NOT_TRUSTED_PIT_EVIDENCE" and mark.source_authentication == "NOT_ESTABLISHED"
    )
    assert mark.version_id == mark.source_id + "-VERSION"
    assert mark.witness_time == mark.available_at
    assert feed.native_invocations == feed.qualified_reads == 1


def test_compatibility_drift_and_signature_refuse_without_source_write(monkeypatch):
    original = prices.regular_bytes
    monkeypatch.setattr(
        prices,
        "regular_bytes",
        lambda p: b"drift" if p.name == "research_panel.py" else original(p),
    )
    with pytest.raises(F5Error, match="F2_COMPATIBILITY_PIN"):
        prices.check_compatibility()
    monkeypatch.setattr(prices, "regular_bytes", original)
    monkeypatch.setattr(f2, "_notice", lambda wrong: None)
    with pytest.raises(F5Error, match="F2_COMPATIBILITY_SIGNATURE"):
        prices.check_compatibility()


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing", "MISSING_MARK"),
        ("zero", "PRICE_VALUE"),
        ("foreign", "PRICE_VERSION_IDENTITY"),
        ("stale", "PRICE_VERSION_IDENTITY"),
        ("late", "PRICE_AVAILABILITY"),
        ("basis", "PRICE_VALUE"),
        ("version", "PRICE_VERSION_IDENTITY"),
    ],
)
def test_missing_stale_foreign_late_zero_mark(barrier, change, reason):
    feed = prices.EvaluationPrices(barrier)
    rows = feed._EvaluationPrices__rows  # trusted kernel fault seam, no policy capability
    key = ("SYN-L1-1", "2025-02-17")
    row = dict(rows[key])
    if change == "missing":
        del rows[key]
    else:
        if change == "zero":
            row["value"] = 0
        if change == "foreign":
            row["issuer"] = "FOREIGN"
        if change == "stale":
            row["session"] = "2025-02-14"
        if change == "late":
            row["available_at"] = "2025-02-17T13:30:02+08:00"
        if change == "basis":
            row["basis"] = "OTHER"
        if change == "version":
            row["id"] += "-REVISION"
        rows[key] = row
    with pytest.raises(F5Error, match=reason):
        feed.read_mark(*key, "2025-02-17T13:30:01+08:00")


def test_off_calendar_early_close_and_qualification_not_hash_only(barrier, monkeypatch):
    feed = prices.EvaluationPrices(barrier)
    with pytest.raises(F5Error, match="PRICE_IDENTITY"):
        feed.read_mark("SYN-L1-1", "2025-02-16", "2025-02-16T13:30:01+08:00")
    early = feed.read_mark("SYN-L1-1", "2024-12-31", "2024-12-31T11:30:01+08:00")
    assert early.close_time.endswith("11:30:00+08:00")
    original = prices.evaluate_slice

    def reject(*args):
        actual = original(*args)
        return replace(actual, s2=replace(actual.s2, state="NOT_ADMISSIBLE"))

    monkeypatch.setattr(prices, "evaluate_slice", reject)
    with pytest.raises(F5Error, match="PRICE_UNAVAILABLE"):
        feed.read_mark("SYN-L1-1", "2025-02-17", "2025-02-17T13:30:01+08:00")


def test_no_price_provider_without_sealed_barrier():
    with pytest.raises(F5Error, match="BARRIER_NOT_OPEN"):
        prices.EvaluationPrices(None)


def test_price_availability_not_future_asof(barrier):
    feed = prices.EvaluationPrices(barrier)
    at = f2.instant("2025-02-17T13:30:01+08:00")
    with pytest.raises(F5Error, match="PRICE_AVAILABILITY"):
        feed.read_mark("SYN-L1-1", "2025-02-17", (at - timedelta(seconds=1)).isoformat())
    with pytest.raises(F5Error, match="PRICE_ASOF"):
        feed.read_mark("SYN-L1-1", "2025-02-17", (at + timedelta(seconds=1)).isoformat())
