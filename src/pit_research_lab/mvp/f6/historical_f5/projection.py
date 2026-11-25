"""Select a detached disclosure from privately link-checked historical records."""

from __future__ import annotations

from collections import Counter

from . import contract as c
from .archive import ORIGINAL_POLICIES, Historical
from .contract import Record, choice, exact


def _fact(source: Record) -> Record:
    state = choice(source["state"], ("KNOWN", *c.MISSING))
    if state == "KNOWN":
        return {
            "state": state,
            "month": source["month"],
            "publication": source["publication"],
            "available_at": source["available_at"],
            "qualification": "QUALIFIED_SYNTHETIC",
        }
    return {"state": state, "reason": "INFORMATION_" + state}


def _signal(value: object, state: object, reason: object, available: str) -> Record:
    status = choice(state, (available, "UNAVAILABLE"))
    if status == available:
        c.require(reason == "NONE")
        return {"state": "VALUE", "metric": exact(value)}
    c.require(value is None)
    missing = choice(reason, c.INFORMATION_REASONS)
    return {"state": missing.removeprefix("INFORMATION_"), "reason": missing}


def _issuer(source: Record) -> Record:
    forecast = source["forecast"]
    scope: Record = {"state": "QUALIFIED_SYNTHETIC"}
    if source["research_eligible"] is not True:
        c.require(source["research_eligible"] is False)
        scope = {
            "state": "UNAVAILABLE",
            "reason": choice(source["eligibility_reason"], c.INFORMATION_REASONS),
        }
    return {
        "issuer": source["issuer"],
        "scope": scope,
        "current_revenue": _fact(source["current"]),
        "preceding_revenue": _fact(source["previous"]),
        "growth": _signal(
            source["growth"], source["growth_state"], source["growth_reason"], "KNOWN"
        ),
        "forecast": _signal(forecast["value"], forecast["state"], forecast["reason"], "PREDICTED"),
    }


def _policy_trace(slot: Record, event: Record, name: str) -> Record:
    action = slot["policy_action"]
    weights = []
    for (alias, amount), (reason_alias, reason) in zip(
        action["weights"], action["issuer_reasons"], strict=True
    ):
        c.require(alias == reason_alias)
        weights.append({"issuer": alias, "weight": exact(amount), "recorded_reason": reason})
    return {
        "policy": name,
        "slot": slot["outcome"],
        "disposition": action["disposition"],
        "cash_weight": exact(action["cash_weight"]),
        "weights": weights,
        "event": event["event"],
        "reference_at": event["reference_at"],
        "posted_at": event["posted_at"],
    }


def _tick(history: Historical, tick: int, observation: Record) -> Record:
    return {
        "tick": tick,
        "cutoff": observation["cutoff"],
        "fold": observation["issuers"][0]["forecast"]["fold"],
        "information_ref": observation["information_digest"],
        "issuers": [_issuer(issuer) for issuer in observation["issuers"]],
        "policies": [
            _policy_trace(history.slots[tick, policy], history.events[tick, policy], alias)
            for policy, alias in zip(ORIGINAL_POLICIES, c.POLICIES, strict=True)
        ],
    }


def _overview(history: Historical) -> Record:
    native, comparison = history.f3_spec["protocol"], history.f5_spec["protocol"]
    return {
        "question": native["question"],
        "method": native["method"],
        "frequency": "WEEKLY",
        "seed": native["seed"],
        "forecast_sessions": native["horizon_sessions"],
        "first_cutoff": history.observations[c.FIRST_TICK]["cutoff"],
        "last_cutoff": history.observations[c.AFTER_LAST_TICK - 1]["cutoff"],
        "terminal_at": comparison["terminal"],
        "fit_clock_wording": native["temporal_policy"]["fit"],
        "actual_fits": [{"fold": fit["fold"], "fit_at": fit["fit_at"]} for fit in history.fits],
        "issuers": [entry["issuer"] for entry in history.observations[c.FIRST_TICK]["issuers"]],
        "coverage": {name: history.coverage[name] for name in c.COVERAGE},
        "fee_rate": exact(comparison["fee"]),
        "slippage_rate": exact(comparison["slippage"]),
        "initial_cash": exact(comparison["initial_cash"], "SYNTHETIC_NTD"),
    }


def _book(history: Historical, policy: str, label: str) -> Record:
    source = history.books[policy]
    full = source["full_period_candidate"]
    decisions = Counter(
        slot["policy_action"]["disposition"]
        for (_, key), slot in history.slots.items()
        if key == policy and slot["outcome"] == "VALID"
    )
    return {
        "policy": label,
        "valid_slots": sum(decisions.values()),
        "allocate_count": decisions["ALLOCATE"],
        "cash_count": decisions["CASH"],
        "abstain_count": decisions["ABSTAIN"],
        "opportunities": source["processed_opportunities"],
        "return_count": full["weekly_return_count"],
        "net_return": exact(full["net_return"]),
        "linked_gross_return": exact(full["linked_pre_friction_gross_return"]),
        "max_drawdown": exact(full["maximum_daily_event_drawdown"]),
        "weekly_sample_volatility": {
            "kind": "NATIVE_DECIMAL_12",
            "unit": "RATIO",
            "text": c.decimal12(full["weekly_volatility_display"]),
        },
        "fees": exact(source["total_fee"], "SYNTHETIC_NTD"),
        "slippage": exact(source["total_slippage"], "SYNTHETIC_NTD"),
    }


def _evidence(history: Historical, validated_at: str) -> Record:
    release = history.release
    return {
        "acceptance_ref": release.acceptance_ref,
        "historical_wu": release.historical_wu,
        "original_revision": release.original_revision,
        "f3_experiment_ref": history.experiment_ref,
        "f3_protocol_ref": history.f3_spec["protocol_ref"],
        "dataset_digest": history.f3_spec["dataset_digest"],
        "source_fixture_sha256": history.f5_spec["source_sha256"],
        "f3_evidence_sha256": release.f3_sha256,
        "f5_evidence_sha256": release.f5_sha256,
        "archive_sha256": release.archive_sha256,
        "archive_manifest_sha256": release.manifest_sha256,
        "effective_report_sha256": release.effective_sha256,
        "archive_validation": "PASSED",
        "validated_at": validated_at,
        "historical_execution": "SUCCEEDED",
        "historical_pair_replay": "VERIFIED",
        "historical_class": c.COMPLETE,
        "current_native_replay": "NOT_RUN",
        "native_replay_reason": "ORIGINAL_PROVENANCE_DIFFERS",
        "current_research": "NOT_RUN",
        "source_scope": "AUTHORED_MODE_S",
        "app_admission": "NONE",
        "non_if03": True,
        "limitations": list(c.LIMITATIONS),
    }


def historical(
    history: Historical, build: str, attempt: str, validated_at: str, observed_at: str
) -> Record:
    view = {
        "status": "AVAILABLE_HISTORICAL",
        "edition_id": history.release.edition,
        "release_id": history.release.identity,
        "overview": _overview(history),
        "comparison": [
            _book(history, policy, label)
            for policy, label in zip(ORIGINAL_POLICIES, c.POLICIES, strict=True)
        ],
        "ticks": [
            _tick(history, tick, observation) for tick, observation in history.observations.items()
        ],
        "evidence": _evidence(history, validated_at),
    }
    return c.snapshot(view, build, attempt, observed_at)


def refusal(reason: str, archive_validation: str, build: str, attempt: str, when: str) -> Record:
    return c.snapshot(
        {
            "status": c.refusal_status(reason),
            "reason": reason,
            "archive_validation": archive_validation,
            "current_native_replay": "NOT_RUN",
            "current_research": "NOT_RUN",
        },
        build,
        attempt,
        when,
    )
