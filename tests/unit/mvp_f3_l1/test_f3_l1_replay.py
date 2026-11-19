import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f3_l1 import experiment as e
from pit_research_lab.mvp.f3_l1 import replay as r
from pit_research_lab.mvp.f3_l1.contracts import fraction_read, wire_bytes


@pytest.fixture(scope="module")
def replays(tmp_path_factory):
    root = tmp_path_factory.mktemp("independent-replays")
    processes = []
    for name in ("a", "b"):
        out = root / name
        command = [
            sys.executable,
            "-B",
            "-m",
            "pit_research_lab.mvp.f3_l1.cli",
            "--output-dir",
            str(out),
        ]
        process = subprocess.Popen(
            command,
            cwd=f2.ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": str(f2.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        processes.append((out, command, process))
    for out, command, process in processes:
        stdout, stderr = process.communicate(timeout=600)
        (root / (out.name + "-process.json")).write_text(
            json.dumps(
                {
                    "argv": command,
                    "exit": process.returncode,
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                },
                indent=2,
            )
        )
        assert process.returncode == 0, stderr.decode()
    return root / "a", root / "b"


def read(out, name):
    return json.loads((out / (name + ".json")).read_bytes())["payload"]


@pytest.fixture(scope="module")
def prepared_before_scoring(tmp_path_factory):
    """Actual experiment; distinguish scoring access from legal historical training reads."""
    from pit_research_lab.mvp.f3_l1.contracts import Protocol

    panel = f2.load_panel()
    stages, score_entries, historical_oos_ids = [], [], set()
    scoring = False
    scoring_reads = 0
    original_score, original_outcome = e.score, panel.outcome
    required_seals = {"F1_PREDICTIONS_SEALED", "F2_PREDICTIONS_SEALED"}

    def score_spy(batch, *args):
        nonlocal scoring
        assert required_seals <= set(stages), "score entered before all folds were sealed"
        score_entries.append({"fold": batch.state.training.fold.name, "stages_seen": list(stages)})
        scoring = True
        try:
            return original_score(batch, *args)
        finally:
            scoring = False

    def outcome_spy(observation, asof):
        nonlocal scoring_reads
        if scoring:
            assert required_seals <= set(stages), "OOS outcome read before all folds were sealed"
            scoring_reads += 1
        actual = original_outcome(observation, asof)
        if not scoring and asof == panel.cutoffs[72].replace("18:00:00", "17:00:00"):
            if 48 <= observation.tick < 72:
                assert actual["available_at"] <= asof
                historical_oos_ids.add(observation.sample_id)
        return actual

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(e, "score", score_spy)
        patch.setattr(panel, "outcome", outcome_spy)
        actual = e.execute_experiment(panel, Protocol(), stages.append)
    details = {
        "stages": stages,
        "score_entries": score_entries,
        "scoring_outcome_reads": scoring_reads,
        "legitimate_later_fold_training_ids_from_earlier_oos": sorted(historical_oos_ids),
    }
    evidence = tmp_path_factory.mktemp("rem01-order-evidence") / "order.json"
    evidence.write_text(json.dumps(details, indent=2) + "\n")
    return actual, details


def test_REM01_T01_all_folds_sealed_before_actual_score_entry(prepared_before_scoring):
    actual, details = prepared_before_scoring
    assert [entry["fold"] for entry in details["score_entries"]] == ["F1", "F2"]
    assert [fold["fold"] for fold in actual["folds"]] == ["F1", "F2"]
    first_entry_stages = details["score_entries"][0]["stages_seen"]
    assert "F1_PREDICTIONS_SEALED" in first_entry_stages
    assert "F2_PREDICTIONS_SEALED" in first_entry_stages
    assert not any(stage.endswith("_SCORED") for stage in first_entry_stages)


def test_REM01_T03_oos_access_order_allows_mature_historical_training(prepared_before_scoring):
    _, details = prepared_before_scoring
    assert details["scoring_outcome_reads"] == 240
    # F2 legitimately trains on F1 test ticks 48..67, now mature at F2's own fit cutoff.
    assert set(details["legitimate_later_fold_training_ids_from_earlier_oos"]) == {
        f"SYN-L1-{issuer}:t{tick:02}" for tick in range(48, 68) for issuer in range(1, 6)
    }


def test_REM01_T04_exact_prior_research_payloads_unchanged(prepared_before_scoring):
    actual, _ = prepared_before_scoring
    # Captured before remediation from the independently reviewed L1 run, whose
    # result artifact SHA-256 is d38fa71856b9cdf078587111de1595da894fd26519319b8686cac2923d8a780e.
    # Each digest covers sorted compact UTF-8 JSON, including complete reduced
    # fraction strings and ordered sample IDs; no rounded displays stand in for numbers.
    expected = {
        "states": "ee7f4d03bdd8aea08590aadb71894dbbbd67d62e247846f67971c22517f5cded",
        "predictions": "f135e7ed789030c6ed95c5c6f9d8836fc0cfa12f9c74f618008a8f41d7a6eeb9",
        "training": "00c9a7ddb268e092eaae60ac8188ed612d91ea65cbda8651e2d80779dd233d4d",
        "targets": "bc1f342630e9e7354dffdccb1bcb4c62dafe30af526542ee77e9c47bf6868e7c",
        "folds": "eeffbc1f7999970f68a63bac380793c5d82a576a6cc25c6ee435573c4ec0bc73",
        "aggregate": "3fe1e757fe0f3a9a75fa23ad20039926a50ee6b056f9cd9803d1cc732e52757a",
        "dependence": "d2769da9f434e1ad3584834505c226b4fc59d59268ebe517348f5a446d13a777",
    }
    assert {name: f2.digest(actual[name]) for name in expected} == expected


def test_REM01_T02_second_fold_preparation_failure_never_scores(tmp_path, monkeypatch):
    fits, scores = [], []
    original_fit, original_score = e.fit, e.score

    def fail_second_fit(training, protocol):
        fits.append(training.fold.name)
        if training.fold.name == "F2":
            raise f2.PanelError("REM01_F2_PREPARATION_FAILURE")
        return original_fit(training, protocol)

    def score_spy(batch, *args):
        scores.append(batch.state.training.fold.name)
        return original_score(batch, *args)

    monkeypatch.setattr(e, "fit", fail_second_fit)
    monkeypatch.setattr(e, "score", score_spy)
    out = tmp_path / "second-fold-preparation-failure"
    with pytest.raises(f2.PanelError, match="REM01_F2_PREPARATION_FAILURE"):
        r.run_to_directory(out)
    assert fits == ["F1", "F2"]
    assert scores == []
    attempt = read(out, "attempt")
    assert attempt["execution_status"] == "FAILED"
    assert attempt["first_failure"] == "REM01_F2_PREPARATION_FAILURE"
    stages = [entry["stage"] for entry in attempt["completed_stages"]]
    assert "F1_PREDICTIONS_SEALED" in stages and "F2_TRAINING_SELECTED" in stages
    assert "F2_FITTED" not in stages and "F2_PREDICTIONS_SEALED" not in stages
    assert not any(stage.endswith("_SCORED") for stage in stages)
    assert attempt["result_ref"] is None and attempt["evidence_ref"] is None
    assert {p.name for p in out.iterdir()} == {"attempt.json"}


def test_P07_fresh_process_replay_all_content_path_invariance(replays):
    a, b = replays
    for name in (*r.ARTIFACTS, "evidence"):
        assert (a / (name + ".json")).read_bytes() == (b / (name + ".json")).read_bytes()
    first, second = read(a, "attempt"), read(b, "attempt")
    assert first["attempt_id"] != second["attempt_id"]
    assert first["started_at"] != second["started_at"]
    assert first["execution_status"] == second["execution_status"] == "SUCCEEDED"
    for attempt in (first, second):
        stages = [entry["stage"] for entry in attempt["completed_stages"]]
        seal_positions = [stages.index(fold + "_PREDICTIONS_SEALED") for fold in ("F1", "F2")]
        score_positions = [stages.index(fold + "_SCORED") for fold in ("F1", "F2")]
        assert max(seal_positions) < min(score_positions)
        assert score_positions == sorted(score_positions)
    r.verify_directory(a)
    r.verify_directory(b)


def test_P08_N10_actual_folds_unfavorable_result_and_refs(replays):
    a, _ = replays
    folds = read(a, "folds")["folds"]
    assert [f["fold"] for f in folds] == ["F1", "F2"]
    all_scored = []
    for fold in folds:
        assert fold["training_count"] >= 180 and fold["training_cutoffs"] >= 40
        assert fold["training_issuers"] == 5
        assert len(fold["scored_ids"]) >= 80
        assert len({s.split(":t")[1] for s in fold["scored_ids"]}) >= 20
        all_scored += fold["scored_ids"]
    assert len(all_scored) == len(set(all_scored)) == 240
    result = read(a, "result")
    assert fraction_read(result["aggregate"]["exact"]["sse"]) == sum(
        fraction_read(f["metrics"]["exact"]["sse"]) for f in folds
    )
    # This frozen experiment really has an unfavorable block; success is execution only.
    assert any(fraction_read(f["metrics"]["oos_improvement"]) < 0 for f in folds)
    assert read(a, "attempt")["execution_status"] == "SUCCEEDED"
    assert result["interpretation"] == "EXECUTION_COMPLETE_NO_CLAIM_OF_PREDICTIVE_EDGE"
    assert len(read(a, "bindings")["observations"]) == 480
    assert read(a, "bindings")["source_summary"]["native_invocations"] > 0
    for batch in read(a, "predictions")["batches"]:
        assert batch["outcomes_in_payload"] is False
        for row in batch["rows"]:
            assert "marks" not in row and "target" not in row and "audit" not in row
    for row in read(a, "handoff")["rows"]:
        assert row["horizon"] == "20_SUBSEQUENT_SESSIONS"
        assert "NO_APP_ADMISSION" in row["eligibility"]
        assert not {"action", "cost", "portfolio", "actual_return"}.intersection(row)


def test_N08_disk_drift_attempt_schema_and_provenance(replays, tmp_path, monkeypatch):
    a, _ = replays
    # Copy only compact run artifacts; no repository mutation.
    for path in a.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    result = tmp_path / "result.json"
    result.write_bytes(result.read_bytes() + b" ")
    with pytest.raises(f2.PanelError, match="ARTIFACT_PIN_MISMATCH"):
        r.verify_directory(tmp_path)
    result.write_bytes((a / "result.json").read_bytes())
    attempt = read(tmp_path, "attempt")
    attempt["experiment_ref"] = "0" * 64
    (tmp_path / "attempt.json").write_bytes(wire_bytes("ATTEMPT", attempt))
    with pytest.raises(f2.PanelError, match="ATTEMPT_REFERENCE_MISMATCH"):
        r.verify_directory(tmp_path)
    observed = r.provenance()
    original = r._pin

    def drift(path):
        pin = original(path)
        return {**pin, "sha256": "0" * 64} if path.endswith("experiment.py") else pin

    monkeypatch.setattr(r, "_pin", drift)
    assert f2.digest(observed) != f2.digest(r.provenance())
    envelope = json.loads((a / "result.json").read_bytes())
    envelope["schema"] = "F3_L1_UNREVIEWED_V999"
    (tmp_path / "result.json").write_bytes(f2.research_bytes(envelope))
    with pytest.raises(f2.PanelError, match="UNSUPPORTED_ARTIFACT_SCHEMA"):
        r._read(tmp_path, "result", "RESULT")


def test_failure_attempt_has_no_fabricated_outputs(tmp_path, monkeypatch):
    def refuse():
        raise f2.PanelError("SOURCE_PIN_MISMATCH")

    monkeypatch.setattr(r, "load_panel", refuse)
    out = tmp_path / "failure"
    with pytest.raises(f2.PanelError, match="SOURCE_PIN_MISMATCH"):
        r.run_to_directory(out)
    attempt = read(out, "attempt")
    assert (
        attempt["execution_status"] == "FAILED"
        and attempt["first_failure"] == "SOURCE_PIN_MISMATCH"
    )
    assert attempt["completed_stages"] == []
    assert attempt["result_ref"] is None and attempt["evidence_ref"] is None
    assert not (out / "result.json").exists()


def test_P05_N05_poisoned_test_y_changes_scores_only(panel, state, protocol, monkeypatch):
    observations = tuple(panel.observation(i, t) for t in range(48, 72) for i in panel.issuers)
    batch = e.predict(state, observations, protocol)
    sealed = f2.research_bytes(batch.payload())
    original = e.target
    count = []

    def forbidden(*_):
        count.append(True)
        raise AssertionError("outcome read before prediction time")

    with monkeypatch.context() as m:
        m.setattr(e, "target", forbidden)
        with pytest.raises(f2.PanelError, match="SCORE_BEFORE_PREDICTION"):
            e.score(batch, panel, batch.rows[0].decision_time, protocol)
    assert count == []
    from dataclasses import replace

    forged = replace(batch, prediction_id="0" * 64)
    with monkeypatch.context() as m:
        m.setattr(e, "target", forbidden)
        with pytest.raises(f2.PanelError, match="PREDICTION_NOT_SEALED"):
            e.score(forged, panel, "2026-02-28T23:59:59+08:00", protocol)
    assert count == []
    first, records, _ = e.score(batch, panel, "2026-02-28T23:59:59+08:00", protocol)
    targets = {
        obs.sample_id: original(panel, obs, "2026-02-28T23:59:59+08:00") for obs in observations
    }

    def poison(_panel, obs, _asof):
        actual = targets[obs.sample_id]
        changed = replace(actual, value=actual.value + 1)
        return replace(changed, _seal=e._seal(changed.payload()))

    monkeypatch.setattr(e, "target", poison)
    second, _, _ = e.score(batch, panel, "2026-02-28T23:59:59+08:00", protocol)
    assert first["metrics"] != second["metrics"]
    assert f2.research_bytes(batch.payload()) == sealed
    assert len(records) == 120


def test_N10_fixed_generator_and_source_pin_no_outcome_dependency():
    spec = importlib.util.spec_from_file_location(
        "l1_input_generator", f2.ROOT / "tests/fixtures/mvp_f3_l1/generate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = f2.research_bytes(module.generate())
    assert raw == (f2.ROOT / f2.FIXTURE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == f2.SOURCE_SHA256
    source = Path(module.__file__).read_text()
    assert "from pit_research_lab" not in source and "import pit_research_lab" not in source
    assert not {"metrics", "beta", "predictions", "expected_result"}.intersection(json.loads(raw))


def test_cli_rejects_repository_and_existing_output_without_writes(tmp_path):
    for out, reason in (
        (f2.ROOT / "must-not-write-f3", "OUTPUT_MUST_BE_OUTSIDE_CHECKOUT"),
        (tmp_path, "OUTPUT_ALREADY_EXISTS"),
    ):
        with pytest.raises(f2.PanelError, match=reason):
            r.run_to_directory(out)
    assert not (f2.ROOT / "must-not-write-f3").exists()
