"""Dependency/resource probes and comparator sensitivity; no hostile-code isolation claim."""

import ast
import copy
import subprocess
import sys
from pathlib import Path

import pytest
from wu00_compare import compare
from wu00_inputs import materialize

ROOT = Path(__file__).parent


def test_input_and_production_import_direction():
    paths = [ROOT / "wu00_inputs.py", *list((ROOT.parents[2] / "src").rglob("*.py"))]
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(
                "wu00_oracle" in n or "wu00_compare" in n or "wu00_evidence" in n for n in names
            )
        if path.name == "wu00_inputs.py":
            assert not any(
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and (
                    "data/oracle" in n.value
                    or "cases.json" in n.value
                    or "reference_vectors" in n.value
                )
                for n in ast.walk(tree)
            )


def test_input_resources_with_oracle_access_denied_in_subprocess():
    script = r"""
import runpy, sys
from pathlib import Path
root = Path(sys.argv[1])
opened = []
def audit(event, args):
    if event != "open" or not isinstance(args[0], (str, bytes)):
        return
    name = str(args[0])
    if "data/oracle" in name or "wu00_oracle" in name:
        raise PermissionError("oracle unavailable")
    if "data/inputs" in name:
        opened.append(Path(name).name)
sys.addaudithook(audit)
module = runpy.run_path(str(root / "wu00_inputs.py"))
for row in module["load_deltas"]():
    bundle = module["materialize"](row["case_id"])
    active = bundle["active_discovery_membership"]
    module["validate_receipt_pages"](active["receipts"], active["pages"])
    for pending in bundle["dependency_only_or_fault_schedule_inputs"]:
        if pending.get("kind") == "pending_receipt_append":
            module["validate_receipt_pages"]([pending["receipt"]], pending["pages"])
assert set(opened) == {"base.json", "contexts.json", "deltas.json"}
try:
    (root / "data/oracle/cases.json").read_bytes()
except PermissionError:
    print("64 cases materialized; oracle access denied; three input resources only")
else:
    raise AssertionError("oracle resource guard ineffective")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-S", "-c", script, str(ROOT.resolve())],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "64 cases materialized; oracle access denied" in result.stdout


def test_no_answers_or_catalogue_in_operation_envelope():
    def walk(value):
        if isinstance(value, dict):
            for key, member in value.items():
                assert not key.startswith("expected")
                assert key not in {
                    "selected_winner",
                    "verification_verdict",
                    "sealed_source_catalogue",
                }
                walk(member)
        elif isinstance(value, list):
            for member in value:
                walk(member)

    for cid in ["A03-C03", "A05-C04", "A05-C05", "A08-C01", "A12-C05"]:
        walk(materialize(cid))


def probe_contract():
    # An isolated comparator-unit stimulus, not a binding approved for a Golden case.
    expected = {
        "binding_status": "REVIEWED_PREDICATES",
        "system_state": "VALUE_AVAILABLE",
        "value": 600,
        "reason": "NONE",
        "required_lineage": ["APR", "MAY", "JUN1"],
        "excluded_lineage": ["JUN2"],
        "forbidden_checks": ["used_latest"],
        "required_tiers": ["S"],
    }
    actual = {
        "system_state": "VALUE_AVAILABLE",
        "value": 600,
        "reason": "NONE",
        "lineage": ["APR", "MAY", "JUN1"],
        "forbidden_checks": {"used_latest": False},
        "required_tiers": ["S"],
    }
    return actual, expected


@pytest.mark.parametrize(
    "fault",
    [
        "reason",
        "missing_reason",
        "lineage",
        "excluded",
        "forbidden",
        "missing_forbidden",
        "type",
        "state",
        "tier",
    ],
)
def test_correct_number_cannot_hide_wrong_metadata(fault):
    actual, expected = probe_contract()
    assert compare(actual, expected)["verdict"] == "PASS"
    if fault == "reason":
        actual["reason"] = "WRONG"
    elif fault == "missing_reason":
        del actual["reason"]
    elif fault == "lineage":
        actual["lineage"] = ["APR", "MAY"]
    elif fault == "excluded":
        actual["lineage"].append("JUN2")
    elif fault == "forbidden":
        actual["forbidden_checks"]["used_latest"] = True
    elif fault == "missing_forbidden":
        del actual["forbidden_checks"]
    elif fault == "type":
        actual["value"] = 600.0
    elif fault == "state":
        actual["system_state"] = "FAILED"
    elif fault == "tier":
        actual["required_tiers"] = []
    assert compare(actual, expected)["verdict"] == "FAIL"


def test_conditional_reason_has_no_default_or_target_conflation():
    actual, branch = probe_contract()
    contract = {
        "binding_status": "REVIEWED_PREDICATES",
        "branches": {"ATTRIBUTED_ASSERTION": branch},
    }
    assert compare(actual, contract)["verdict"] == "FAIL"
    actual["target"] = "ATTRIBUTED_ASSERTION"
    assert compare(actual, contract)["verdict"] == "PASS"
    changed = copy.deepcopy(contract)
    changed["branches"]["ATTRIBUTED_ASSERTION"]["reason"] = "ATTRIBUTION_UNRESOLVED"
    assert compare(actual, changed)["verdict"] == "FAIL"


@pytest.mark.parametrize(
    "state,value",
    [
        ("NOT_COMPUTABLE", None),
        ("UNRESOLVED", None),
        ("WITHHELD", None),
        ("UNCONFIRMED", None),
        ("FAILED", None),
        ("VALUE_AVAILABLE", 0),
    ],
)
def test_system_states_null_and_zero_are_distinct(state, value):
    actual, expected = probe_contract()
    actual.update(system_state=state, value=value)
    assert compare(actual, expected)["verdict"] == "FAIL"
