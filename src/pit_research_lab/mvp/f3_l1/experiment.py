"""One fixed research flow: legal training -> OLS -> sealed forecasts -> later scores."""

import hmac
import secrets
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from pit_research_lab.mvp.f2.research_panel import (
    PanelObservation,
    ResearchPanel,
    digest,
    instant,
    require,
    verify_observation,
)
from pit_research_lab.mvp.research_vslice.contracts import research_bytes

from .contracts import FOLDS, Fold, Protocol, decimal_text, fraction_wire

_KEY = secrets.token_bytes(32)


def _seal(payload: dict[str, Any]) -> bytes:
    return hmac.digest(_KEY, research_bytes(payload), "sha256")


def growth(observation: PanelObservation) -> Fraction:
    obs = verify_observation(observation)
    for fact in (obs.current, obs.previous):
        require(fact.state == "KNOWN", "INFORMATION_" + fact.state)
        require(type(fact.amount) is int and fact.amount > 0, "NONPOSITIVE_REVENUE")
    require(
        obs.current.unit == obs.previous.unit == "NTD_thousands"
        and obs.current.basis == obs.previous.basis == "consolidated-v1",
        "FEATURE_UNIT_BASIS",
    )
    assert obs.current.amount is not None and obs.previous.amount is not None
    return Fraction(obs.current.amount, obs.previous.amount) - 1


@dataclass(frozen=True, slots=True)
class Target:
    sample_id: str
    dataset_digest: str
    start: str
    end: str
    available_at: str
    value: Fraction
    marks: tuple[tuple[str, str, str, str], ...]
    _seal: bytes = field(repr=False, compare=False)

    def payload(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "dataset_digest": self.dataset_digest,
            "start": self.start,
            "end": self.end,
            "available_at": self.available_at,
            "value": fraction_wire(self.value),
            "marks": [list(m) for m in self.marks],
        }


def target(panel: ResearchPanel, observation: PanelObservation, asof: str) -> Target:
    require(type(panel) is ResearchPanel, "F2_OUTCOME_PROVIDER_REQUIRED")
    actual = panel.outcome(observation, asof)
    start, end = actual["marks"]
    require(start["value"] > 0 and end["value"] > 0, "NONPOSITIVE_PRICE")
    values: dict[str, Any] = dict(
        sample_id=observation.sample_id,
        dataset_digest=panel.dataset_digest,
        start=actual["start"],
        end=actual["end"],
        available_at=actual["available_at"],
        value=Fraction(end["value"], start["value"]) - 1,
        marks=tuple(
            (m["ref"], m["version_ref"], m["source_digest"], m["available_at"])
            for m in actual["marks"]
        ),
    )
    unsigned = Target(**values, _seal=b"")
    return Target(**values, _seal=_seal(unsigned.payload()))


def validate_target(value: Target, observation: PanelObservation, cutoff: str) -> None:
    require(
        type(value) is Target and hmac.compare_digest(value._seal, _seal(value.payload())),
        "TARGET_NOT_ISSUED",
    )
    require(
        value.sample_id == observation.sample_id
        and value.dataset_digest == observation.dataset_digest,
        "TARGET_IDENTITY",
    )
    require(instant(value.available_at) <= instant(cutoff), "IMMATURE_LABEL")


@dataclass(frozen=True, slots=True)
class TrainingSample:
    observation: PanelObservation
    outcome: Target


@dataclass(frozen=True, slots=True)
class TrainingSet:
    fold: Fold
    fit_cutoff: str
    test_start_mark: str
    dataset_digest: str
    protocol_ref: str
    schedule: tuple[str, ...]
    issuers: tuple[str, ...]
    samples: tuple[TrainingSample, ...]
    excluded: tuple[tuple[str, str], ...]
    _seal: bytes = field(repr=False, compare=False)

    def payload(self) -> dict[str, Any]:
        return {
            "fold": self.fold.name,
            "fit_cutoff": self.fit_cutoff,
            "test_start_mark": self.test_start_mark,
            "dataset_digest": self.dataset_digest,
            "protocol_ref": self.protocol_ref,
            "schedule": list(self.schedule),
            "issuers": list(self.issuers),
            "members": [
                {"binding_id": s.observation.binding_id, "target": s.outcome.payload()}
                for s in self.samples
            ],
            "excluded": [list(e) for e in self.excluded],
        }


def training_set(
    panel: ResearchPanel,
    fold: Fold,
    protocol: Protocol,
    *,
    declared_members: tuple[str, ...] | None = None,
) -> TrainingSet:
    protocol.validate()
    require(fold in FOLDS and type(fold) is Fold, "INVALID_FOLD")
    require(
        len(panel.cutoffs) == 96 and tuple(sorted(set(panel.cutoffs))) == panel.cutoffs,
        "INVALID_FOLD_CHRONOLOGY",
    )
    cutoff = panel.cutoffs[fold.test_start].replace("18:00:00", "17:00:00")
    test_start = panel.target_timing(panel.observation(panel.issuers[0], fold.test_start))["start"]
    samples, excluded = [], []
    for tick in range(fold.history_end):
        for issuer in panel.issuers:
            obs = panel.observation(issuer, tick)
            reason = next(
                (
                    "INFORMATION_" + f.state
                    for f in (obs.current, obs.previous)
                    if f.state != "KNOWN"
                ),
                None,
            )
            if reason is None:
                growth(obs)
                timing = panel.target_timing(obs)
                if instant(timing["available_at"]) > instant(cutoff):
                    reason = "IMMATURE_LABEL"
                elif timing["end"] >= test_start:
                    reason = "OUTCOME_OVERLAPS_TEST"
            if reason is not None:
                require(declared_members is None or obs.sample_id not in declared_members, reason)
                excluded.append((obs.sample_id, reason))
            else:
                samples.append(TrainingSample(obs, target(panel, obs, cutoff)))
    if declared_members is not None:
        require(
            declared_members == tuple(s.observation.sample_id for s in samples),
            "TRAINING_MEMBERSHIP_MISMATCH",
        )
    values: dict[str, Any] = dict(
        fold=fold,
        fit_cutoff=cutoff,
        test_start_mark=test_start,
        dataset_digest=panel.dataset_digest,
        protocol_ref=protocol.identity,
        schedule=panel.cutoffs,
        issuers=panel.issuers,
        samples=tuple(samples),
        excluded=tuple(excluded),
    )
    unsigned = TrainingSet(**values, _seal=b"")
    return TrainingSet(**values, _seal=_seal(unsigned.payload()))


def ols(
    values: tuple[tuple[Fraction, Fraction], ...],
) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    """Numerical kernel with no source, label accessor or test-data capability."""
    require(
        len(values) >= 2 and all(type(x) is Fraction and type(y) is Fraction for x, y in values),
        "INVALID_OLS_INPUT",
    )
    gbar = sum((x for x, _ in values), Fraction()) / len(values)
    rbar = sum((y for _, y in values), Fraction()) / len(values)
    sxx = sum(((x - gbar) ** 2 for x, _ in values), Fraction())
    require(sxx > 0, "ZERO_GROWTH_VARIANCE")
    beta = sum(((x - gbar) * (y - rbar) for x, y in values), Fraction()) / sxx
    alpha = rbar - beta * gbar
    for number in (gbar, rbar, alpha, beta):
        fraction_wire(number)
    return gbar, rbar, alpha, beta


@dataclass(frozen=True, slots=True)
class FittedState:
    training: TrainingSet
    gbar: Fraction
    rbar: Fraction
    alpha: Fraction
    beta: Fraction
    state_id: str
    _seal: bytes = field(repr=False, compare=False)

    def payload(self) -> dict[str, Any]:
        return {
            "training_ref": digest(self.training.payload()),
            "fold": self.training.fold.name,
            "fit_cutoff": self.training.fit_cutoff,
            "dataset_digest": self.training.dataset_digest,
            "protocol_ref": self.training.protocol_ref,
            "training_ids": [s.observation.sample_id for s in self.training.samples],
            **{
                name: fraction_wire(getattr(self, name))
                for name in ("gbar", "rbar", "alpha", "beta")
            },
        }


def validate_training(training: TrainingSet, protocol: Protocol) -> None:
    protocol.validate()
    require(
        type(training) is TrainingSet
        and hmac.compare_digest(training._seal, _seal(training.payload())),
        "TRAINING_MEMBERSHIP_MISMATCH",
    )
    require(
        training.fold in FOLDS and training.protocol_ref == protocol.identity, "PROTOCOL_MISMATCH"
    )
    require(
        training.fit_cutoff
        == training.schedule[training.fold.test_start].replace("18:00:00", "17:00:00"),
        "FIT_CUTOFF_MISMATCH",
    )
    ids, ticks, issuers = [], set(), set()
    for sample in training.samples:
        obs = verify_observation(sample.observation)
        growth(obs)
        require(
            obs.dataset_digest == training.dataset_digest
            and obs.issuer in training.issuers
            and obs.cutoff == training.schedule[obs.tick],
            "TRAINING_IDENTITY",
        )
        require(
            obs.tick < training.fold.history_end
            and instant(obs.cutoff) < instant(training.fit_cutoff),
            "FUTURE_TRAINING_FEATURE",
        )
        validate_target(sample.outcome, obs, training.fit_cutoff)
        require(sample.outcome.end < training.test_start_mark, "OUTCOME_OVERLAPS_TEST")
        ids.append(obs.sample_id)
        ticks.add(obs.tick)
        issuers.add(obs.issuer)
    require(
        len(ids) == len(set(ids))
        and ids
        == [
            s.observation.sample_id
            for s in sorted(
                training.samples, key=lambda s: (s.observation.tick, s.observation.issuer)
            )
        ],
        "DUPLICATE_OR_UNORDERED_SAMPLE",
    )
    require(
        len(ids) >= protocol.min_train_rows
        and len(ticks) >= protocol.min_train_cutoffs
        and len(issuers) >= protocol.min_issuers,
        "INSUFFICIENT_TRAINING_SAMPLE",
    )


def fit(training: TrainingSet, protocol: Protocol) -> FittedState:
    validate_training(training, protocol)  # complete guards before numerical kernel entry
    gbar, rbar, alpha, beta = ols(
        tuple((growth(s.observation), s.outcome.value) for s in training.samples)
    )
    values: dict[str, Any] = dict(training=training, gbar=gbar, rbar=rbar, alpha=alpha, beta=beta)
    unsigned = FittedState(**values, state_id="", _seal=b"")
    body = unsigned.payload()
    return FittedState(**values, state_id=digest(body), _seal=_seal(body))


def validate_state(state: FittedState, protocol: Protocol) -> None:
    require(type(state) is FittedState, "FITTED_STATE_REQUIRED")
    validate_training(state.training, protocol)
    require(
        state.state_id == digest(state.payload())
        and hmac.compare_digest(state._seal, _seal(state.payload())),
        "FITTED_STATE_MISMATCH",
    )


@dataclass(frozen=True, slots=True)
class Prediction:
    sample_id: str
    issuer: str
    tick: int
    decision_time: str
    binding_id: str
    value: Fraction | None
    reason: str

    def payload(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "issuer": self.issuer,
            "tick": self.tick,
            "decision_time": self.decision_time,
            "binding_id": self.binding_id,
            "state": "PREDICTED" if self.value is not None else "UNAVAILABLE",
            "value": fraction_wire(self.value) if self.value is not None else None,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PredictionBatch:
    state: FittedState
    rows: tuple[Prediction, ...]
    prediction_id: str
    _seal: bytes = field(repr=False, compare=False)

    def payload(self) -> dict[str, Any]:
        return {
            "fold": self.state.training.fold.name,
            "state_id": self.state.state_id,
            "dataset_digest": self.state.training.dataset_digest,
            "protocol_ref": self.state.training.protocol_ref,
            "rows": [r.payload() for r in self.rows],
            "outcomes_in_payload": False,
        }


def predict(
    state: FittedState, observations: tuple[PanelObservation, ...], protocol: Protocol
) -> PredictionBatch:
    """Has no panel/outcome-provider argument: test y cannot be requested."""
    validate_state(state, protocol)
    training, rows = state.training, []
    expected = [
        (i, t)
        for t in range(training.fold.test_start, training.fold.test_end)
        for i in training.issuers
    ]
    actual = []
    for obs in observations:
        obs = verify_observation(obs)
        require(
            obs.dataset_digest == training.dataset_digest
            and obs.cutoff == training.schedule[obs.tick],
            "PREDICTION_INPUT_MISMATCH",
        )
        actual.append((obs.issuer, obs.tick))
        reason = next(
            ("INFORMATION_" + f.state for f in (obs.current, obs.previous) if f.state != "KNOWN"),
            "NONE",
        )
        value = state.rbar + state.beta * (growth(obs) - state.gbar) if reason == "NONE" else None
        rows.append(
            Prediction(
                obs.sample_id, obs.issuer, obs.tick, obs.cutoff, obs.binding_id, value, reason
            )
        )
    require(actual == expected, "TEST_GRID_MISMATCH")
    values: dict[str, Any] = dict(state=state, rows=tuple(rows))
    unsigned = PredictionBatch(**values, prediction_id="", _seal=b"")
    body = unsigned.payload()
    return PredictionBatch(**values, prediction_id=digest(body), _seal=_seal(body))


def metrics(records: tuple[tuple[str, Fraction, Fraction, Fraction], ...]) -> dict[str, Any]:
    require(
        bool(records) and len({r[0] for r in records}) == len(records), "DUPLICATE_OR_EMPTY_SCORE"
    )
    require(all(type(v) is Fraction for r in records for v in r[1:]), "EXACT_SCORE_REQUIRED")
    residual = [pred - actual for _, pred, actual, _ in records]
    absolute = sum((abs(r) for r in residual), Fraction())
    sse = sum((r * r for r in residual), Fraction())
    signed = sum(residual, Fraction())
    baseline_sse = sum(((base - y) ** 2 for _, _, y, base in records), Fraction())
    n = len(records)
    values = {
        "absolute_error_sum": absolute,
        "sse": sse,
        "signed_error_sum": signed,
        "baseline_sse": baseline_sse,
        "mae": absolute / n,
        "mse": sse / n,
        "mean_prediction_error": signed / n,
        "residual_variance_population": sse / n - (signed / n) ** 2,
        "minimum_residual": min(residual),
        "maximum_residual": max(residual),
    }
    grouped: dict[str, list[tuple[int, Fraction]]] = {}
    for (sample_id, _, _, _), error in zip(records, residual, strict=True):
        if ":t" in sample_id:
            issuer, tick = sample_id.rsplit(":t", 1)
            grouped.setdefault(issuer, []).append((int(tick), error))
    lag_products: list[Fraction] = []
    for group in grouped.values():
        ordered = sorted(group)
        lag_products.extend(
            a[1] * b[1] for a, b in zip(ordered, ordered[1:], strict=False) if b[0] == a[0] + 1
        )
    if lag_products:
        values["adjacent_within_issuer_residual_product_mean"] = sum(
            lag_products, Fraction()
        ) / len(lag_products)
    improvement = 1 - sse / baseline_sse if baseline_sse else None
    return {
        "n": n,
        "exact": {k: fraction_wire(v) for k, v in values.items()},
        "display": {
            **{k: decimal_text(v) for k, v in values.items()},
            "rmse": decimal_text(sse / n, sqrt=True),
            "oos_improvement": decimal_text(improvement) if improvement is not None else None,
        },
        "oos_improvement": fraction_wire(improvement)
        if improvement is not None
        else {"state": "NOT_COMPUTABLE", "reason": "ZERO_BASELINE_SSE"},
        "units": "dimensionless_simple_return; MSE/SSE are squared-return units",
        "iid_inference": "NOT_PERFORMED",
        "adjacent_residual_pairs": len(lag_products),
        "diagnostic_interpretation": "DESCRIPTIVE_MOMENTS_NOT_DEPENDENCE_ROBUST_INFERENCE",
    }


def score(
    batch: PredictionBatch, panel: ResearchPanel, scoring_cutoff: str, protocol: Protocol
) -> tuple[
    dict[str, Any], tuple[tuple[str, Fraction, Fraction, Fraction], ...], list[dict[str, Any]]
]:
    validate_state(batch.state, protocol)
    require(
        batch.prediction_id == digest(batch.payload())
        and hmac.compare_digest(batch._seal, _seal(batch.payload())),
        "PREDICTION_NOT_SEALED",
    )
    require(panel.dataset_digest == batch.state.training.dataset_digest, "SCORING_DATASET_MISMATCH")
    records, labels, excluded = [], [], []
    for row in batch.rows:
        require(instant(row.decision_time) < instant(scoring_cutoff), "SCORE_BEFORE_PREDICTION")
        if row.value is None:
            excluded.append([row.sample_id, row.reason])
            continue
        obs = panel.observation(row.issuer, row.tick)
        require(row.binding_id == obs.binding_id, "SCORING_BINDING_MISMATCH")
        actual = target(panel, obs, scoring_cutoff)  # only now is an OOS outcome read
        records.append((row.sample_id, row.value, actual.value, batch.state.rbar))
        labels.append(actual.payload())
    scored_ticks = {r[0].split(":t")[1] for r in records}
    require(
        len(records) >= protocol.min_test_rows and len(scored_ticks) >= protocol.min_test_cutoffs,
        "INSUFFICIENT_TEST_SAMPLE",
    )
    ordered = tuple(records)
    return (
        {
            "scoring_cutoff": scoring_cutoff,
            "prediction_id": batch.prediction_id,
            "scored_ids": [r[0] for r in records],
            "excluded": excluded,
            "metrics": metrics(ordered),
        },
        ordered,
        labels,
    )


def execute_experiment(
    panel: ResearchPanel, protocol: Protocol, progress: Callable[[str], None]
) -> dict[str, Any]:
    protocol.validate()
    bindings = [
        panel.observation(issuer, tick).public() for tick in range(96) for issuer in panel.issuers
    ]
    progress("F2_INPUTS_QUALIFIED")
    states: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    records: list[tuple[str, Fraction, Fraction, Fraction]] = []
    training_artifacts: list[dict[str, Any]] = []
    scoring_cutoff = "2026-02-28T23:59:59+08:00"
    prepared: list[PredictionBatch] = []
    # Finish every historical fit and seal every forecast before exposing the
    # orchestrator to OOS scoring. Later-fold mature training labels remain legal.
    for fold in FOLDS:
        training = training_set(panel, fold, protocol)
        progress(fold.name + "_TRAINING_SELECTED")
        state = fit(training, protocol)
        progress(fold.name + "_FITTED")
        observations = tuple(
            panel.observation(issuer, tick)
            for tick in range(fold.test_start, fold.test_end)
            for issuer in panel.issuers
        )
        batch = predict(state, observations, protocol)
        require(
            type(batch) is PredictionBatch
            and batch.state is state
            and batch.state.training.fold == fold,
            "PREPARED_FOLD_MISMATCH",
        )
        require(
            batch.prediction_id == digest(batch.payload())
            and hmac.compare_digest(batch._seal, _seal(batch.payload())),
            "PREDICTION_NOT_SEALED",
        )
        prepared.append(batch)
        progress(fold.name + "_PREDICTIONS_SEALED")
    require(
        len(prepared) == len(FOLDS) == 2
        and tuple(batch.state.training.fold for batch in prepared) == protocol.folds,
        "INCOMPLETE_FOLDS",
    )
    for batch in prepared:
        state = batch.state
        training = state.training
        fold = training.fold
        scored, fold_records, fold_labels = score(batch, panel, scoring_cutoff, protocol)
        progress(fold.name + "_SCORED")
        states.append({"state_id": state.state_id, **state.payload()})
        batches.append({"prediction_id": batch.prediction_id, **batch.payload()})
        training_artifacts.append(
            {"training_ref": digest(training.payload()), **training.payload()}
        )
        labels.extend(fold_labels)
        records.extend(fold_records)
        periods = {(s.observation.issuer, s.observation.current.month) for s in training.samples}
        folds.append(
            {
                "fold": fold.name,
                "history_candidates": [0, fold.history_end - 1],
                "test_ticks": [fold.test_start, fold.test_end - 1],
                "fit_cutoff": training.fit_cutoff,
                "training_ids": [s.observation.sample_id for s in training.samples],
                "training_count": len(training.samples),
                "training_cutoffs": len({s.observation.tick for s in training.samples}),
                "training_issuers": len({s.observation.issuer for s in training.samples}),
                "distinct_issuer_month_releases": len(periods),
                "distinct_source_versions": len(
                    {
                        f.version_ref
                        for s in training.samples
                        for f in (s.observation.current, s.observation.previous)
                    }
                ),
                "latest_training_label_availability": max(
                    s.outcome.available_at for s in training.samples
                ),
                "scored_cutoffs": len({sample.split(":t")[1] for sample in scored["scored_ids"]}),
                "excluded_training": [list(e) for e in training.excluded],
                "exclusion_counts": dict(Counter(reason for _, reason in training.excluded)),
                "state_id": state.state_id,
                **scored,
            }
        )
    require(len(folds) == 2, "INCOMPLETE_FOLDS")
    overlapping_pairs = sum(
        a["sample_id"].split(":t")[0] == b["sample_id"].split(":t")[0]
        and max(a["start"], b["start"]) < min(a["end"], b["end"])
        for index, a in enumerate(labels)
        for b in labels[index + 1 :]
    )
    return {
        "bindings": bindings,
        "qualification_receipts": panel.qualification_receipts(),
        "source_summary": panel.source_summary(),
        "states": states,
        "predictions": batches,
        "training": training_artifacts,
        "targets": labels,
        "folds": folds,
        "aggregate": metrics(tuple(records)),
        "dependence": {
            "weekly_rows_are_independent": False,
            "target_overlap": True,
            "overlapping_within_issuer_scored_window_pairs": overlapping_pairs,
            "common_price_shocks": True,
            "effective_sample_size": "NOT_ESTIMATED",
            "interpretation": "NO_H0_REJECTION_OR_POPULATION_INFERENCE",
        },
    }
