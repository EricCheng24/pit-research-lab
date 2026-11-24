"""Trusted-kernel unit seams are NOT genuine producer artifacts or acceptance."""

import copy
import json
from dataclasses import replace
from fractions import Fraction

import pytest

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f3_l1 import experiment as f3
from pit_research_lab.mvp.f3_l1.contracts import Protocol
from pit_research_lab.mvp.f5 import inputs
from pit_research_lab.mvp.f5.contracts import CALENDAR_SHA, DecisionObservation, F5Error


@pytest.fixture(scope="module")
def kernel():
    panel = f2.load_panel()
    protocol = Protocol()
    bindings = [panel.observation(i, t).public() for t in range(96) for i in panel.issuers]
    training = f3.training_set(panel, f3.FOLDS[0], protocol)
    state = f3.fit(training, protocol)
    batch = f3.predict(
        state,
        tuple(panel.observation(i, t) for t in range(48, 72) for i in panel.issuers),
        protocol,
    )
    values = {
        "spec": {
            "protocol": protocol.payload(),
            "protocol_ref": protocol.identity,
            "dataset_digest": panel.dataset_digest,
        },
        "bindings": {
            "observations": bindings,
            "qualification_receipts": panel.qualification_receipts(),
        },
        "folds": {
            "training": [{"training_ref": f2.digest(training.payload()), **training.payload()}, {}]
        },
        "states": {"states": [{"state_id": state.state_id, **state.payload()}, {}]},
        "predictions": {"batches": [{"prediction_id": batch.prediction_id, **batch.payload()}, {}]},
        "handoff": {"rows": []},
        "result_ref": "0" * 64,
    }
    return panel, values, state


def test_absent_origin_refuses_before_verifier_or_policy(tmp_path, monkeypatch):
    def forbidden(*args):
        pytest.fail("producer verifier must not run without established origin")

    monkeypatch.setattr(inputs.f3_replay, "verify_directory", forbidden)
    for directory, pin in ((None, None), (tmp_path, "0" * 64)):
        with pytest.raises(F5Error, match="BLOCKED_INPUT"):
            inputs.import_f3(directory, pin, None)
    # Self-consistent bytes/hash are not an independently established origin.
    (tmp_path / "evidence.json").write_text('{"self_attested":true}')
    from hashlib import sha256

    pin = sha256((tmp_path / "evidence.json").read_bytes()).hexdigest()
    with pytest.raises(F5Error, match="BLOCKED_INPUT"):
        inputs.import_f3(tmp_path, pin, None)


@pytest.mark.parametrize("field", ["issuer", "tick", "binding_id", "decision_time", "sample_id"])
def test_forecast_identity_and_result_pollution(kernel, field):
    panel, values, _ = kernel
    row = copy.deepcopy(values["predictions"]["batches"][0]["rows"][0])
    row[field] = 49 if field == "tick" else "FOREIGN"
    with pytest.raises(F5Error, match="FORECAST_BINDING"):
        inputs.project(panel.observation(panel.issuers[0], 48), row, values["states"]["states"][0])
    row = copy.deepcopy(values["predictions"]["batches"][0]["rows"][0])
    row["research_result_ref"] = "0" * 64
    with pytest.raises(f2.PanelError, match="CLOSED_FIELDS"):
        inputs.project(panel.observation(panel.issuers[0], 48), row, values["states"]["states"][0])


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("membership", "TRAINING_MEMBERSHIP"),
        ("immature", "TRAINING_MEMBERSHIP"),
        ("state", "FITTED_STATE"),
        ("prediction", "PREDICTION_SEMANTICS"),
        ("grid", "HISTORICAL_BINDING_GRID"),
    ],
)
def test_source_semantic_forgery_not_just_hashes(kernel, mutation, reason):
    panel, original, _ = kernel
    values = copy.deepcopy(original)
    if mutation == "membership":
        values["folds"]["training"][0]["members"].pop()
    elif mutation == "immature":
        values["folds"]["training"][0]["members"][0]["target"]["available_at"] = (
            "2026-01-01T18:00:00+08:00"
        )
    elif mutation == "state":
        values["states"]["states"][0]["fit_cutoff"] = "2025-08-01T17:00:00+08:00"
    elif mutation == "prediction":
        values["predictions"]["batches"][0]["rows"][0]["value"] = {
            "numerator": "999",
            "denominator": "1",
        }
    else:
        values["bindings"]["observations"].pop()
    # Hash link integrity is deliberately not the oracle: source reconstruction is.
    with pytest.raises(F5Error, match=reason):
        inputs.verify_semantics(values, panel)


@pytest.mark.parametrize("state", ["UNKNOWN", "WITHHELD", "ABSENT", "NOT_EVALUATED", "REJECTED"])
def test_unavailable_source_state_remains_null_no_fallback(kernel, state):
    panel, values, _ = kernel
    original = panel.observation(panel.issuers[0], 48)
    body = json.loads((f2.ROOT / f2.FIXTURE).read_bytes())
    for row in body["revenues"]:
        if row["issuer"] == original.issuer and row["month"] == original.current.month:
            row["state"], row["amount"] = state, None
    # Explicit trusted in-memory F2 test seam; protected fixture stays unchanged.
    changed = f2.ResearchPanel(body, _key=f2._LOADER)
    obs = changed.observation(original.issuer, 48)
    row = {
        "sample_id": obs.sample_id,
        "issuer": obs.issuer,
        "tick": 48,
        "decision_time": obs.cutoff,
        "binding_id": obs.binding_id,
        "state": "UNAVAILABLE",
        "value": None,
        "reason": "INFORMATION_" + state,
    }
    unit_state = values["states"]["states"][0] | {"dataset_digest": changed.dataset_digest}
    item = inputs.project(obs, row, unit_state)
    assert item.current.month == original.current.month and item.current.amount is None
    assert item.growth is None and item.growth_reason == "INFORMATION_" + state
    assert not item.research_eligible


def test_current_tick_projection_no_nested_training_or_resolver(kernel):
    panel, values, _ = kernel
    cells = tuple(
        inputs.project(panel.observation(i, 48), row, values["states"]["states"][0])
        for i, row in zip(
            panel.issuers, values["predictions"]["batches"][0]["rows"][:5], strict=True
        )
    )
    obs = DecisionObservation(48, panel.cutoffs[48], CALENDAR_SHA, panel.dataset_digest, cells)
    obs.validate(production=True)
    text = repr(obs)
    assert all(
        k not in text
        for k in (
            "research_result_ref",
            "training_ref",
            "available_outcome",
            "ResearchPanel",
            "PredictionBatch",
        )
    )
    with pytest.raises(F5Error, match="FORECAST_FOLD_FIT"):
        replace(cells[0].forecast, fold="F2").validate()
    with pytest.raises(F5Error, match="FUTURE_FEATURE"):
        replace(cells[0].current, available_at=obs.cutoff).validate(obs.cutoff)
    with pytest.raises(F5Error, match="SOURCE_VERSION"):
        replace(cells[0].current, version_id="LATE_REVISION").validate(obs.cutoff)
    assert type(cells[0].forecast.value) is Fraction


def test_semantic_fit_maturity_equality_and_plus_second(kernel):
    panel, _, state = kernel
    sample = state.training.samples[-1]
    f3.validate_target(sample.outcome, sample.observation, sample.outcome.available_at)
    delayed = replace(sample.outcome, available_at="2026-02-28T18:00:00+08:00")
    delayed = replace(delayed, _seal=f3._seal(delayed.payload()))
    with pytest.raises(f2.PanelError, match="IMMATURE_LABEL"):
        f3.validate_target(delayed, sample.observation, state.training.fit_cutoff)
    assert all(s.outcome.available_at <= state.training.fit_cutoff for s in state.training.samples)


def test_regular_input_symlink_refused(tmp_path):
    p = tmp_path / "source"
    p.write_bytes(b"{}")
    link = tmp_path / "link"
    link.symlink_to(p)
    with pytest.raises(F5Error, match="INPUT_SYMLINK"):
        inputs.regular_bytes(link)


def test_mock_origin_record_is_not_producer_authority(tmp_path):
    origin = inputs.ProducerOrigin(
        tmp_path, "0" * 64, "1" * 40, "3.12.13", "CPython", (), "MOCK_SELF_ATTESTED"
    )
    with pytest.raises(F5Error, match="PRODUCER_ORIGIN_NOT_ESTABLISHED"):
        inputs.import_f3(tmp_path, "0" * 64, origin)


@pytest.mark.parametrize(
    "mutation", ["absent", "record", "directory", "evidence", "receipt", "grant"]
)
def test_trusted_witness_request_binding_cannot_be_self_issued(tmp_path, mutation):
    """Injected code is a UNIT-ONLY trust seam, never external execution proof."""
    record = inputs.ProducerOrigin(
        tmp_path, "0" * 64, "1" * 40, "3.12.13", "CPython", (), "UNIT_ONLY_NO_EXECUTION"
    )

    def witness(directory, expected):
        return record

    reason = "ORIGIN_WITNESS_BINDING"
    if mutation == "absent":
        witness, reason = None, "BLOCKED_INPUT"
    elif mutation == "record":
        witness, reason = lambda directory, expected: object(), "ORIGIN_WITNESS_RECORD"
    elif mutation == "directory":
        record = replace(record, directory=tmp_path / "foreign")
    elif mutation == "evidence":
        record = replace(record, evidence_sha256="2" * 64)
    elif mutation == "receipt":
        record = replace(record, receipt_id="")
    else:
        record = replace(record, _grant=b"SELF_ISSUED_OR_SERIALIZED")
        reason = "ORIGIN_WITNESS_REUSED_GRANT"
    with pytest.raises(F5Error, match=reason):
        inputs.establish_from_witness(tmp_path, "0" * 64, witness)


def test_unit_witness_grant_does_not_pass_original_artifact_gate(tmp_path):
    """Positive LOCAL wiring only; no F3 origin or artifact is asserted genuine."""
    tmp_path.chmod(0o700)
    calls = []

    def unit_witness(directory, expected):
        calls.append((directory, expected))
        return inputs.ProducerOrigin(
            directory, expected, "1" * 40, "3.12.13", "CPython", (), "UNIT_ONLY_NO_EXECUTION"
        )

    granted = inputs.establish_from_witness(tmp_path, "0" * 64, unit_witness)
    assert calls == [(tmp_path, "0" * 64)] and granted._grant
    assert "_grant" not in granted.semantic()  # local grants never enter stable provenance
    with pytest.raises(F5Error, match="ARTIFACT_INVENTORY"):
        inputs.require_origin(tmp_path, "0" * 64, granted)
    with pytest.raises(F5Error, match="PRODUCER_ORIGIN"):
        inputs.require_origin(tmp_path, "2" * 64, granted)


@pytest.mark.parametrize("mutation", ["closure", "runtime", "head"])
def test_original_producer_closure_and_runtime_are_separate_unit_gate(
    monkeypatch, tmp_path, mutation
):
    p = inputs.f3_replay.provenance()
    rows = copy.deepcopy(p["files"])
    origin = inputs.ProducerOrigin(
        tmp_path,
        "0" * 64,
        "1" * 40,
        "3.12.13",
        "CPython",
        tuple((x["path"], x["sha256"], x["byte_length"]) for x in rows),
        "UNIT_ONLY_GATE_B_NOT_ORIGIN_PROOF",
    )
    value = {
        "provenance": {
            "base_head": origin.producer_head,
            "code_claim": "ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT",
            "runtime": {"python": origin.python, "implementation": origin.implementation},
            "files": rows,
        }
    }
    inputs.validate_provenance(value, origin)  # gate B alone cannot establish gate A
    if mutation == "closure":
        rows[0]["sha256"] = "f" * 64
        origin = replace(
            origin, source_pins=tuple((x["path"], x["sha256"], x["byte_length"]) for x in rows)
        )  # self-consistent rehash still differs from locked original closure
        reason = "PRODUCER_CODE_CLOSURE"
    elif mutation == "runtime":
        origin = replace(origin, python="3.14.0")
        value["provenance"]["runtime"]["python"] = origin.python
        reason = "PRODUCER_RUNTIME"
    else:
        value["provenance"]["base_head"] = "2" * 40
        reason = "PRODUCER_PROVENANCE"
    with pytest.raises(F5Error, match=reason):
        inputs.validate_provenance(value, origin)


def test_wrong_historical_fit_clock_refused_before_prediction(kernel, monkeypatch):
    panel, values, state = kernel
    wrong = replace(state.training, fit_cutoff="2025-02-14T17:00:01+08:00")
    monkeypatch.setattr(f3, "training_set", lambda *args: wrong)
    with pytest.raises(F5Error, match="FIT_CUTOFF_MISMATCH"):
        inputs.verify_semantics(values, panel)
