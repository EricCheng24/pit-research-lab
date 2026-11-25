"""Synthetic presentation controls. No retained research data is loaded."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import pytest

from pit_research_lab.mvp.f6.historical_f5 import archive, contract, projection

STAMP = "2026-11-24T12:01:04.000001Z"
OBSERVED = "2026-11-24T12:01:05.000001Z"
BUILD = "4" * 64
ATTEMPT = "12345678-1234-4123-8123-123456789abc"
OTHER_ATTEMPT = "22345678-1234-4123-8123-123456789abc"


def rat(n: int, d: int = 1) -> dict[str, str]:
    return {"numerator": str(n), "denominator": str(d)}


def synthetic_history() -> archive.Historical:
    """Hand-authored synthetic source values for projection tests, never archive admission."""
    values: dict[int, dict[str, Any]] = {}
    slots = {}
    events = {}
    beginning = datetime.fromisoformat("2025-02-18T18:00:00+08:00")
    original_policies = (
        "QUALIFIED_EW_CAP50_V1",
        "GROWTH_POSITIVE_EW_CAP50_V1",
        "F3_OOS_POSITIVE_EW_CAP50_V1",
    )
    for tick in range(48, 96):
        cutoff = beginning + timedelta(days=7 * (tick - 48))
        later = (cutoff + timedelta(days=1)).replace(hour=13, minute=30)
        facts = {
            "state": "KNOWN",
            "month": "2024-12",
            "publication": "2025-01-02T12:00:00+08:00",
            "available_at": "2025-01-04T12:00:00+08:00",
            "amount": 529083410,
            "source_id": "private-not-a-view-field",
            "reason": "NONE",
        }
        aliases = [f"SYN-L1-{j}" for j in range(1, 6)]
        values[tick] = {
            "cutoff": cutoff.isoformat(),
            "information_digest": hashlib.sha256(str(tick).encode()).hexdigest(),
            "issuers": [
                {
                    "issuer": alias,
                    "research_eligible": True,
                    "eligibility_reason": "NONE",
                    "current": facts.copy(),
                    "previous": facts.copy(),
                    "growth": rat(j - 1, 17) if j != 1 else rat(0),
                    "growth_state": "KNOWN",
                    "growth_reason": "NONE",
                    "forecast": {
                        "fold": "F1" if tick < 72 else "F2",
                        "value": rat(-9, 37),
                        "state": "PREDICTED",
                        "reason": "NONE",
                    },
                }
                for j, alias in enumerate(aliases, start=1)
            ],
        }
        for index, p in enumerate(original_policies):
            cash = index == 1 and tick in {64, 67, 68}
            slots[tick, p] = {
                "outcome": "VALID",
                "policy_action": {
                    "disposition": "CASH" if cash else "ALLOCATE",
                    "cash_weight": rat(int(cash)),
                    "weights": [[alias, rat(0) if cash else rat(1, 5)] for alias in aliases],
                    "issuer_reasons": [
                        [alias, "NONPOSITIVE_GROWTH" if cash else "NOT_RECORDED"]
                        for alias in aliases
                    ],
                },
            }
            events[tick, p] = {
                "event": "NO_TRADE" if cash else "TRADE",
                "reference_at": later.isoformat(),
                "posted_at": (later + timedelta(seconds=1)).isoformat(),
            }
    return archive.Historical(
        release=replace(
            archive._RELEASE, acceptance_ref="SYNTHETIC-TEST-ONLY", archive_sha256="8" * 64
        ),
        f3_spec={
            "protocol_ref": "6" * 64,
            "dataset_digest": "5" * 64,
            "protocol": {
                "question": "Does PIT monthly revenue growth predict subsequent synthetic returns?",
                "method": "OLS_INTERCEPT_ONE_REGRESSOR_V1",
                "seed": 17,
                "horizon_sessions": 20,
                "temporal_policy": {"fit": "17:00_FIRST_TEST_SESSION"},
            },
        },
        experiment_ref="9" * 64,
        f5_spec={
            "protocol": {
                "terminal": "2026-01-17T18:00:00+08:00",
                "fee": rat(3, 5000),
                "slippage": rat(1, 2500),
                "initial_cash": rat(1000),
            },
            "source_sha256": "1" * 64,
        },
        fits=[
            {"fold": "F1", "fit_at": "2025-02-14T17:00:00+08:00"},
            {"fold": "F2", "fit_at": "2025-08-01T17:00:00+08:00"},
        ],
        observations=values,
        slots=slots,
        events=events,
        coverage={
            "ticks": 48,
            "valid_slots": 144,
            "oos_cells": 240,
            "historical_bindings": 480,
            "qualified_marks": 1205,
            "mark_sessions": 241,
            "rebalance_records": 288,
            "valuation_records": 1446,
        },
        books={
            **{
                p: {
                    "full_period_candidate": {
                        "net_return": rat(-k, 37),
                        "linked_pre_friction_gross_return": rat(k, 29),
                        "maximum_daily_event_drawdown": rat(k, 13),
                        "weekly_volatility_display": f"0.00000000000{k}",
                        "weekly_return_count": 48,
                    },
                    "processed_opportunities": 48,
                    "total_fee": rat(k, 7),
                    "total_slippage": rat(k, 11),
                }
                for k, p in enumerate(original_policies, 1)
            },
            "excluded-mirror": {"synthetic_ignore": True},
        },
    )


def synthetic_view() -> dict[str, Any]:
    return projection.historical(synthetic_history(), BUILD, ATTEMPT, STAMP, OBSERVED)


def with_identifier(value: dict[str, Any]) -> dict[str, Any]:
    body = {key: val for key, val in value.items() if key != "snapshot_id"}
    wire = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return body | {
        "snapshot_id": hashlib.sha256(b"F6-HISTORICAL-SYNTHETIC-F5-VIEW-V1\0" + wire).hexdigest()
    }


def test_H02_recorded_exact_values_and_census() -> None:
    out = synthetic_view()
    assert out["overview"]["coverage"]["qualified_marks"] == 1205
    assert [book["net_return"]["numerator"] for book in out["comparison"]] == ["-1", "-2", "-3"]
    assert [book["linked_gross_return"]["denominator"] for book in out["comparison"]] == ["29"] * 3
    assert [book["cash_count"] for book in out["comparison"]] == [0, 3, 0]
    assert [book["allocate_count"] for book in out["comparison"]] == [48, 45, 48]
    assert [book["weekly_sample_volatility"]["text"] for book in out["comparison"]] == [
        "0.000000000001",
        "0.000000000002",
        "0.000000000003",
    ]
    assert [book["fees"]["unit"] for book in out["comparison"]] == ["SYNTHETIC_NTD"] * 3
    assert out["ticks"][16]["policies"][1]["cash_weight"]["numerator"] == "1"
    assert "excluded-mirror" not in json.dumps(out)
    assert "529083410" not in json.dumps(out)
    assert "private-not-a-view-field" not in json.dumps(out)


def test_H04_release_snapshot_and_original_identities() -> None:
    a = synthetic_view()
    b = projection.historical(synthetic_history(), BUILD, OTHER_ATTEMPT, STAMP, OBSERVED)
    assert a == with_identifier(a) and b == with_identifier(b)
    assert a["snapshot_id"] != b["snapshot_id"]
    assert a["release_id"] == b["release_id"] and a["release_id"] != a["build_sha256"]
    evidence = a["evidence"]
    assert evidence["acceptance_ref"] == "SYNTHETIC-TEST-ONLY"
    assert evidence["original_revision"] == "5ee19b68067e58f29742f67b2db3a2de6dd25152"
    assert evidence["historical_class"] == "COMPLETE_COMPARABLE_SYNTHETIC"
    assert evidence["native_replay_reason"] == "ORIGINAL_PROVENANCE_DIFFERS"
    assert evidence["archive_validation"] == "PASSED" and evidence["validated_at"] == STAMP
    assert [
        evidence[k]
        for k in (
            "historical_execution",
            "historical_pair_replay",
            "current_native_replay",
            "current_research",
        )
    ] == ["SUCCEEDED", "VERIFIED", "NOT_RUN", "NOT_RUN"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda x: x.update({"raw": "/private/original"}),
        lambda x: x["overview"].update({"seed": True}),
        lambda x: x["overview"].update(
            {
                "initial_cash": {
                    "kind": "EXACT_FRACTION",
                    "unit": "RATIO",
                    "numerator": "1000",
                    "denominator": "1",
                }
            }
        ),
        lambda x: x["evidence"].update({"current_research": "SUCCEEDED"}),
        lambda x: x["evidence"].update({"acceptance_ref": "Bad\ud800"}),
        lambda x: x["ticks"].reverse(),
        lambda x: x["ticks"][1].update({"cutoff": x["ticks"][0]["cutoff"]}),
        lambda x: x["ticks"][0]["issuers"][0]["growth"].update({"state": "WITHHELD"}),
        lambda x: x["ticks"][0]["policies"].reverse(),
        lambda x: x["comparison"][0].update({"return_count": 49}),
        lambda x: x["comparison"][0]["fees"].update({"denominator": "0"}),
        lambda x: x["comparison"][0]["fees"].update({"numerator": "01"}),
    ],
    ids=[
        "extra",
        "bool",
        "unit",
        "promotion",
        "unicode",
        "tick-order",
        "duplicate-time",
        "mixed-union",
        "policy-order",
        "counts",
        "zero-denominator",
        "noncanonical",
    ],
)
def test_H02_H04_strict_view_rejects_changes_even_with_self_hash(mutator: Any) -> None:
    view = synthetic_view()
    mutator(view)
    with pytest.raises((contract.Refusal, UnicodeEncodeError)):
        contract.validate(with_identifier(view))


def test_H02_unknown_and_true_zero_stay_distinct() -> None:
    source = synthetic_history()
    left, right = source.observations[48]["issuers"][:2]
    left["previous"].update({"state": "WITHHELD", "amount": None})
    left.update(
        {
            "research_eligible": False,
            "eligibility_reason": "INFORMATION_WITHHELD",
            "growth": None,
            "growth_state": "UNAVAILABLE",
            "growth_reason": "INFORMATION_WITHHELD",
        }
    )
    left["forecast"].update(
        {"value": None, "state": "UNAVAILABLE", "reason": "INFORMATION_WITHHELD"}
    )
    right["growth"] = rat(0)
    out = projection.historical(source, BUILD, ATTEMPT, STAMP, OBSERVED)
    hidden, zero = out["ticks"][0]["issuers"][:2]
    assert hidden["preceding_revenue"] == {"state": "WITHHELD", "reason": "INFORMATION_WITHHELD"}
    assert hidden["forecast"] == {"state": "WITHHELD", "reason": "INFORMATION_WITHHELD"}
    assert zero["growth"]["metric"]["numerator"] == "0"


@pytest.mark.parametrize(
    ("pair", "allowed"),
    [
        (rat(0), True),
        (rat(-29, 31), True),
        (rat(0, 2), False),
        (rat(2, 4), False),
        ({"numerator": "1" * 4096, "denominator": "2"}, True),
        ({"numerator": "1" * 4097, "denominator": "2"}, False),
    ],
)
def test_H02_fraction_boundary(pair: dict[str, str], allowed: bool) -> None:
    if allowed:
        assert contract.exact(pair)["numerator"] == pair["numerator"]
    else:
        with pytest.raises(contract.Refusal):
            contract.exact(pair)


def test_H04_refusal_forbids_historical_fields() -> None:
    result = projection.refusal("EDITION_WITHHELD", "NOT_RUN", BUILD, ATTEMPT, OBSERVED)
    assert result["status"] == "WITHHELD"
    assert result["current_native_replay"] == result["current_research"] == "NOT_RUN"
    forbidden = {"evidence", "books", "comparison", "ticks", "edition_id", "release_id"}
    assert not result.keys() & forbidden
    clone = copy.deepcopy(result) | {"historical_execution": "SUCCEEDED"}
    with pytest.raises(contract.Refusal):
        contract.validate(with_identifier(clone))
