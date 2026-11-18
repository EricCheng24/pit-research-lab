"""Independent interpreter invocations each load original files and execute their own episode."""

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from pit_research_lab.mvp.research_vslice.contracts import ResearchError, research_bytes
from pit_research_lab.mvp.research_vslice.replay import STAGE_V_IDS, execute
from pit_research_lab.mvp.research_vslice.sources import SOURCE_PINS, checkout_root


def invoke(out, seed=17, threshold=105):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pit_research_lab.mvp.research_vslice.cli",
            "--seed",
            str(seed),
            "--rule-threshold",
            str(threshold),
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        env={**os.environ, "UV_OFFLINE": "1", "UV_NO_SYNC": "1"},
        check=False,
        timeout=30,
    )


def test_RC04_T01_two_fresh_processes(tmp_path):
    # Neither subprocess reads the other output, nor any generated expected trace.
    a, b = tmp_path / "a", tmp_path / "b"
    pa, pb = invoke(a), invoke(b)
    assert pa.returncode == pb.returncode == 0, (pa.stderr, pb.stderr)
    ta, tb = (p / "trace.json" for p in (a, b))
    assert ta.read_bytes() == tb.read_bytes()
    assert sha256(ta.read_bytes()).hexdigest() == pa.stdout.decode().strip()
    assert pa.stdout == pb.stdout
    assert (a / "manifest.json").read_bytes() == (b / "manifest.json").read_bytes()
    trace = json.loads(ta.read_bytes())
    assert trace["format"] == "RESEARCH_TRACE_V0.1" and trace["non_if03"]
    assert len(trace["episodes"]) == 2
    assert [len(e["ticks"]) for e in trace["episodes"]] == [4, 4]
    assert all(e["terminal"] for e in trace["episodes"])
    assert json.loads((a / "manifest.json").read_bytes())["config"]["annotations"] == [
        {"iso_week": "2027-W03", "kind": "NO_SESSION_WEEK"}
    ]


def test_RC04_T03_stable_complete_actual_manifest():
    trace, manifest = execute(17)
    other_trace, other = execute(17)
    assert trace == other_trace and manifest == other
    assert manifest["source_pins"] == [
        {"path": p, "sha256": h, "size": n} for p, h, n in SOURCE_PINS
    ]
    for group in ["source_pins", "code_pins", "test_pins"]:
        assert manifest[group]
        for pin in manifest[group]:
            data = (checkout_root() / pin["path"]).read_bytes()
            assert (sha256(data).hexdigest(), len(data)) == (pin["sha256"], pin["size"])
    assert len(manifest["code_pins"]) == 8 and len(manifest["test_pins"]) == 4
    assert manifest["runtime"]["python"] == sys.version
    assert manifest["agent_ids"] == ["no_data_baseline_v1", "eligible_rule_v1"]
    assert manifest["seed"] == 17
    assert manifest["config"]["native_invocation"] == "NOT_RUN"
    assert manifest["trace_sha256"] == sha256(trace).hexdigest()
    assert manifest["trace_size"] == len(trace)
    identity = manifest["execution_identity_sha256"]
    spec = {
        k: v
        for k, v in manifest.items()
        if k not in ["trace_sha256", "trace_size", "execution_identity_sha256"]
    }
    assert sha256(research_bytes(spec)).hexdigest() == identity
    assert json.loads(trace)["execution_identity_sha256"] == identity
    assert len(manifest["tests"]["deferred_stage_m"]) == 8
    assert all(
        x["execution"] == "NOT_RUN" and x["result"] == "NOT_VERIFIED"
        for x in manifest["tests"]["deferred_stage_m"]
    )
    for forbidden in ["pid", "wall_clock", "hostname", "tmp_path"]:
        assert forbidden not in manifest


def test_process_seed_config_sensitivity_and_original_recoverability(tmp_path):
    traces, manifests = [], []
    for name, seed, threshold in [
        ("a", 17, 105),
        ("seed", 18, 105),
        ("algorithm", 17, 95),
        ("recover", 17, 105),
    ]:
        out = tmp_path / name
        process = invoke(out, seed, threshold)
        assert process.returncode == 0, process.stderr
        traces.append((out / "trace.json").read_bytes())
        manifests.append(json.loads((out / "manifest.json").read_bytes()))
    assert traces[0] == traces[3]
    assert traces[0] != traces[1] and traces[0] != traces[2]

    def actions(trace):
        return [
            [t["transition"]["action"] for t in e["ticks"]] for e in json.loads(trace)["episodes"]
        ]

    assert actions(traces[0])[0] == ["HOLD"] * 4
    assert actions(traces[1])[0] == ["ABSTAIN"] * 4
    assert actions(traces[0])[1] == ["HOLD", "FLAG_REVIEW", "FLAG_REVIEW", "HOLD"]
    assert actions(traces[2])[1] == ["FLAG_REVIEW", "FLAG_REVIEW", "FLAG_REVIEW", "HOLD"]
    assert len({m["execution_identity_sha256"] for m in manifests}) == 3


def test_cli_refuses_unsafe_or_reused_output(tmp_path):
    assert invoke(tmp_path / "negative", -1).returncode == 2
    assert not (tmp_path / "negative").exists()
    assert invoke(tmp_path / "good").returncode == 0
    assert invoke(tmp_path / "good").returncode == 2
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "good", target_is_directory=True)
    assert invoke(link / "child").returncode == 2
    assert invoke(checkout_root() / "must-not-write").returncode == 2
    assert not (checkout_root() / "must-not-write").exists()
    assert invoke(tmp_path / ".." / "should-not-write").returncode == 2


def test_stage_v_inventory_exact_no_stage_m_promotion():
    matrix = json.loads(
        (
            checkout_root() / "docs/mvp/v1.0/wu05-rebaseline01-research-acceptance-matrix-v0.1.json"
        ).read_bytes()
    )
    assert set(STAGE_V_IDS) == {c["id"] for c in matrix["acceptance_tests"] if c["stage"] == "V"}
    paths = Path(__file__).parent.glob("test_*.py")
    text = "\n".join(p.read_text() for p in paths)
    for cid in STAGE_V_IDS:
        assert text.count("def test_" + cid.replace("-", "_") + "_") == 1
    assert matrix["research_functional_acceptance"] is False
    assert matrix["legacy_s1_ratified_count_out_of_five"] == 0
    with pytest.raises(ResearchError, match="INVALID_THRESHOLD"):
        execute(17, -1)
