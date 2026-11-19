"""Actual worktree provenance, outside-checkout artifacts and non-IF03 replay."""

import platform
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from pit_research_lab.mvp.f2.research_panel import (
    FIXTURE,
    MANIFEST,
    ROOT,
    PanelError,
    closed,
    decode,
    digest,
    load_panel,
    require,
)

from .contracts import LIMITATIONS, Protocol, fraction_read, wire_bytes
from .experiment import execute_experiment

ARTIFACTS = ("spec", "bindings", "folds", "states", "predictions", "targets", "result", "handoff")
KINDS = {
    "spec": "SPEC",
    "bindings": "BINDINGS",
    "folds": "FOLDS",
    "states": "STATES",
    "predictions": "PREDICTIONS",
    "targets": "TARGETS",
    "result": "RESULT",
    "handoff": "HANDOFF",
}
DOC = "docs/mvp/v1.0/f3-l1-research-runtime-v0.1.md"


def _pin(path: str) -> dict[str, Any]:
    file = ROOT / path
    require(
        file.is_file() and not any(p.is_symlink() for p in (file, *file.parents)), "PROVENANCE_FILE"
    )
    raw = file.read_bytes()
    return {"path": path, "byte_length": len(raw), "sha256": sha256(raw).hexdigest()}


def provenance() -> dict[str, Any]:
    require(sys.version_info[:2] == (3, 12), "PYTHON_312_REQUIRED")
    paths = {
        "src/pit_research_lab/__init__.py",
        "src/pit_research_lab/mvp/__init__.py",
        "src/pit_research_lab/mvp/f2/__init__.py",
        "src/pit_research_lab/mvp/f2/research_panel.py",
        "src/pit_research_lab/mvp/research_vslice/__init__.py",
        "src/pit_research_lab/mvp/research_vslice/contracts.py",
        "pyproject.toml",
        "uv.lock",
        DOC,
        FIXTURE,
        MANIFEST,
        "tests/fixtures/mvp_f3_l1/generate.py",
    }
    for folder in (
        "src/pit_research_lab/domain",
        "src/pit_research_lab/mvp/f3_l1",
        "tests/unit/mvp_f3_l1",
    ):
        paths.update(str(p.relative_to(ROOT)) for p in (ROOT / folder).glob("*.py"))
    base = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    return {
        "base_head": base,
        "code_claim": "ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT",
        "files": [_pin(p) for p in sorted(paths)],
        "runtime": {"python": sys.version, "implementation": platform.python_implementation()},
    }


def _safe_output(out: Path) -> None:
    require(
        out.is_absolute() and ".." not in out.parts and not out.is_relative_to(ROOT),
        "OUTPUT_MUST_BE_OUTSIDE_CHECKOUT",
    )
    require(not any(p.is_symlink() for p in (out, *out.parents)), "OUTPUT_SYMLINK")
    require(not out.exists(), "OUTPUT_ALREADY_EXISTS")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def run_to_directory(out: Path) -> dict[str, Any]:
    _safe_output(out)
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter_ns()
    attempt: dict[str, Any] = {
        "attempt_id": str(uuid.uuid4()),
        "execution_status": "RUNNING",
        "started_at": _now(),
        "finished_at": None,
        "elapsed_ns": None,
        "completed_stages": [],
        "first_failure": None,
        "experiment_ref": None,
        "result_ref": None,
        "evidence_ref": None,
    }

    def save_attempt() -> None:
        (out / "attempt.json").write_bytes(wire_bytes("ATTEMPT", attempt))

    def progress(stage: str) -> None:
        attempt["completed_stages"].append(
            {"stage": stage, "finished_at": _now(), "elapsed_ns": time.perf_counter_ns() - started}
        )
        save_attempt()

    save_attempt()
    try:
        observed = provenance()
        protocol = Protocol()
        panel = load_panel()
        spec = {
            "protocol": protocol.payload(),
            "protocol_ref": protocol.identity,
            "dataset_digest": panel.dataset_digest,
            "provenance": observed,
        }
        spec_bytes = wire_bytes("SPEC", spec)
        experiment_ref = sha256(spec_bytes).hexdigest()
        attempt["experiment_ref"] = experiment_ref
        progress("SPEC_PINNED")
        execution = execute_experiment(panel, protocol, progress)
        payloads = {
            "spec": spec,
            "bindings": {
                "observations": execution["bindings"],
                "qualification_receipts": execution["qualification_receipts"],
                "source_summary": execution["source_summary"],
            },
            "folds": {"folds": execution["folds"], "training": execution["training"]},
            "states": {"states": execution["states"]},
            "predictions": {"batches": execution["predictions"]},
            "targets": {"scored_targets": execution["targets"]},
        }
        bodies = {name: wire_bytes(KINDS[name], payload) for name, payload in payloads.items()}
        refs = {name: sha256(raw).hexdigest() for name, raw in bodies.items()}
        result = {
            "experiment_ref": experiment_ref,
            "dataset_digest": panel.dataset_digest,
            "protocol_ref": protocol.identity,
            "states_ref": refs["states"],
            "predictions_ref": refs["predictions"],
            "targets_ref": refs["targets"],
            "folds_ref": refs["folds"],
            "aggregate": execution["aggregate"],
            "dependence": execution["dependence"],
            "limitations": list(LIMITATIONS),
            "interpretation": "EXECUTION_COMPLETE_NO_CLAIM_OF_PREDICTIVE_EDGE",
        }
        bodies["result"] = wire_bytes("RESULT", result)
        result_ref = sha256(bodies["result"]).hexdigest()
        handoff = []
        for state, batch in zip(execution["states"], execution["predictions"], strict=True):
            for row in batch["rows"]:
                handoff.append(
                    {
                        **row,
                        "horizon": "20_SUBSEQUENT_SESSIONS",
                        "meaning": "UNADJUSTED_SIMPLE_RETURN_FORECAST_NOT_ACTION",
                        "method": "OLS_INTERCEPT_ONE_REGRESSOR_V1",
                        "fold": state["fold"],
                        "fit_cutoff": state["fit_cutoff"],
                        "state_id": state["state_id"],
                        "dataset_digest": panel.dataset_digest,
                        "protocol_ref": protocol.identity,
                        "research_result_ref": result_ref,
                        "limitations": list(LIMITATIONS),
                        "eligibility": "AUTHORED_SYNTHETIC_LOCAL_RELEASE_NO_APP_ADMISSION",
                    }
                )
        bodies["handoff"] = wire_bytes("HANDOFF", {"rows": handoff})
        evidence = {
            "experiment_ref": experiment_ref,
            "result_ref": result_ref,
            "protocol_ref": protocol.identity,
            "dataset_digest": panel.dataset_digest,
            "evidence_scope": "EXECUTED_AUTHORED_SYNTHETIC_RESEARCH_ONLY",
            "test_execution_attestation": "NOT_ATTESTED_BY_EXPERIMENT_RUNTIME",
            "artifacts": [
                {"file": name + ".json", "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}
                for name, raw in sorted(bodies.items())
            ],
            "limitations": list(LIMITATIONS),
        }
        require(observed == provenance(), "WORKTREE_CHANGED_DURING_EXECUTION")
        for name, raw in bodies.items():
            (out / (name + ".json")).write_bytes(raw)
        evidence_bytes = wire_bytes("EVIDENCE", evidence)
        (out / "evidence.json").write_bytes(evidence_bytes)
        attempt.update(result_ref=result_ref, evidence_ref=sha256(evidence_bytes).hexdigest())
        progress("EVIDENCE_WRITTEN")
        # Reconcile all on-disk links before declaring actual success.
        attempt["execution_status"] = "SUCCEEDED"
        attempt["finished_at"] = _now()
        attempt["elapsed_ns"] = time.perf_counter_ns() - started
        save_attempt()
        verify_directory(out)
    except Exception as error:
        code = str(error) if isinstance(error, PanelError) else "INTERNAL_ERROR"
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", code) is None:
            code = "INTERNAL_ERROR"
        attempt.update(
            execution_status="FAILED",
            first_failure=code,
            finished_at=_now(),
            elapsed_ns=time.perf_counter_ns() - started,
        )
        save_attempt()
        raise PanelError(code) from error
    return attempt


def _read(out: Path, name: str, kind: str) -> dict[str, Any]:
    value = decode((out / (name + ".json")).read_bytes())
    closed(value, "schema non_if03 payload")
    require(
        value["schema"] == "F3_L1_RESEARCH_" + kind + "_V0.1"
        and value["non_if03"] is True
        and type(value["payload"]) is dict,
        "UNSUPPORTED_ARTIFACT_SCHEMA",
    )
    payload: dict[str, Any] = value["payload"]
    fields = {
        "SPEC": "protocol protocol_ref dataset_digest provenance",
        "BINDINGS": "observations qualification_receipts source_summary",
        "FOLDS": "folds training",
        "STATES": "states",
        "PREDICTIONS": "batches",
        "TARGETS": "scored_targets",
        "HANDOFF": "rows",
        "RESULT": "experiment_ref dataset_digest protocol_ref states_ref predictions_ref targets_ref "
        "folds_ref aggregate dependence limitations interpretation",
        "EVIDENCE": "experiment_ref result_ref protocol_ref dataset_digest evidence_scope "
        "test_execution_attestation artifacts limitations",
        "ATTEMPT": "attempt_id execution_status started_at finished_at elapsed_ns completed_stages "
        "first_failure experiment_ref result_ref evidence_ref",
    }
    require(kind in fields, "UNSUPPORTED_ARTIFACT_SCHEMA")
    closed(payload, fields[kind])
    require(
        wire_bytes(kind, payload) == (out / (name + ".json")).read_bytes(), "NONCANONICAL_ARTIFACT"
    )
    return payload


def verify_directory(out: Path) -> None:
    evidence = _read(out, "evidence", "EVIDENCE")
    closed(
        evidence,
        "experiment_ref result_ref protocol_ref dataset_digest evidence_scope "
        "test_execution_attestation artifacts limitations",
    )
    require(
        [p["file"] for p in evidence["artifacts"]] == sorted(n + ".json" for n in ARTIFACTS),
        "ARTIFACT_INVENTORY",
    )
    refs = {}
    for pin in evidence["artifacts"]:
        closed(pin, "file sha256 byte_length")
        raw = (out / pin["file"]).read_bytes()
        require(
            sha256(raw).hexdigest() == pin["sha256"] and len(raw) == pin["byte_length"],
            "ARTIFACT_PIN_MISMATCH",
        )
        refs[pin["file"][:-5]] = pin["sha256"]
    values = {name: _read(out, name, KINDS[name]) for name in ARTIFACTS}
    spec, result = values["spec"], values["result"]
    closed(spec, "protocol protocol_ref dataset_digest provenance")
    require(
        spec["protocol"] == Protocol().payload() and spec["protocol_ref"] == Protocol().identity,
        "PROTOCOL_MISMATCH",
    )
    require(
        evidence["experiment_ref"] == refs["spec"] == result["experiment_ref"]
        and evidence["result_ref"] == refs["result"],
        "RESULT_REFERENCE_MISMATCH",
    )
    for key in ("dataset_digest", "protocol_ref"):
        require(spec[key] == evidence[key] == result[key], "EVIDENCE_IDENTITY_MISMATCH")
    for name in ("states", "predictions", "targets", "folds"):
        require(result[name + "_ref"] == refs[name], "RESULT_REFERENCE_MISMATCH")
    receipts = values["bindings"]["qualification_receipts"]
    require(
        all(digest(body) == ref for ref, body in receipts.items()), "QUALIFICATION_RECEIPT_MISMATCH"
    )
    observations = {}
    for obs in values["bindings"]["observations"]:
        body = {k: v for k, v in obs.items() if k != "binding_id"}
        require(
            obs["binding_id"] == digest(body) and obs["dataset_digest"] == spec["dataset_digest"],
            "BINDING_MISMATCH",
        )
        for fact in (obs["current"], obs["previous"]):
            ref = fact["qualification_ref"]
            require(ref is None or ref in receipts, "DANGLING_QUALIFICATION_REF")
        observations[obs["binding_id"]] = obs
    training = values["folds"]["training"]
    training_refs = {t["training_ref"] for t in training}
    for item in training:
        closed(
            item,
            "training_ref fold fit_cutoff test_start_mark dataset_digest protocol_ref schedule "
            "issuers members excluded",
        )
        require(
            item["training_ref"] == digest({k: v for k, v in item.items() if k != "training_ref"}),
            "TRAINING_REF_MISMATCH",
        )
        for member in item["members"]:
            require(member["binding_id"] in observations, "DANGLING_BINDING_REF")
    states = {}
    for state in values["states"]["states"]:
        closed(
            state,
            "state_id training_ref fold fit_cutoff dataset_digest protocol_ref training_ids "
            "gbar rbar alpha beta",
        )
        require(
            state["state_id"] == digest({k: v for k, v in state.items() if k != "state_id"})
            and state["training_ref"] in training_refs,
            "STATE_REFERENCE_MISMATCH",
        )
        for key in ("alpha", "beta", "gbar", "rbar"):
            fraction_read(state[key])
        states[state["state_id"]] = state
    batches = values["predictions"]["batches"]
    require(len(batches) == 2 and len(states) == 2 and len(training) == 2, "INCOMPLETE_FOLDS")
    for batch in batches:
        closed(
            batch,
            "prediction_id fold state_id dataset_digest protocol_ref rows outcomes_in_payload",
        )
        require(
            batch["prediction_id"]
            == digest({k: v for k, v in batch.items() if k != "prediction_id"})
            and batch["state_id"] in states
            and batch["outcomes_in_payload"] is False,
            "PREDICTION_REFERENCE_MISMATCH",
        )
        for row in batch["rows"]:
            closed(row, "sample_id issuer tick decision_time binding_id state value reason")
            require(row["binding_id"] in observations, "DANGLING_BINDING_REF")
            if row["value"] is not None:
                fraction_read(row["value"])
    for row in values["handoff"]["rows"]:
        require(
            row["research_result_ref"] == refs["result"] and row["state_id"] in states,
            "HANDOFF_REFERENCE_MISMATCH",
        )
    attempt = _read(out, "attempt", "ATTEMPT")
    closed(
        attempt,
        "attempt_id execution_status started_at finished_at elapsed_ns completed_stages "
        "first_failure experiment_ref result_ref evidence_ref",
    )
    require(
        uuid.UUID(attempt["attempt_id"]).version == 4
        and attempt["execution_status"] == "SUCCEEDED"
        and attempt["first_failure"] is None
        and attempt["experiment_ref"] == refs["spec"]
        and attempt["result_ref"] == refs["result"]
        and attempt["evidence_ref"] == sha256((out / "evidence.json").read_bytes()).hexdigest(),
        "ATTEMPT_REFERENCE_MISMATCH",
    )
