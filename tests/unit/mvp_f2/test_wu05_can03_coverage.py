"""110-row diagnostic overlay integrity and actual replay, never status promotion."""

import ast
import copy
import json
from collections import Counter

import pytest
from test_wu05_can03_conformance import (
    CASES,
    CORE_IDS,
    GRAPH_IDS,
    REF_IDS,
    RELATION_IDS,
    compare_golden,
    observe_negative,
    relation_observation,
)
from wu05_can03_expected import (
    FIX,
    FREEZE_HASH,
    LEDGER_HASH,
    ROOT,
    freeze,
    metadata_hash,
)

MATRIX_PATH = FIX / "wu05_can03_v0_1/coverage_matrix.json"
MATRIX = json.loads(MATRIX_PATH.read_bytes())
SCOPED = CORE_IDS | REF_IDS | GRAPH_IDS | {f"B{i:02}" for i in range(1, 9)}
GAP_OPERATIONS = Counter(
    {
        "before": 2,
        "time": 3,
        "ticks": 6,
        "contexts": 1,
        "native_summary": 2,
        "safe_fields": 5,
        "authorization": 2,
        "parent_match": 1,
        "maturity": 1,
        "schedule": 4,
    }
)


def historical_ids(filename, symbol):
    """Inspect constant assignments only; do not import historical test helpers."""
    tree = ast.parse((ROOT / "tests/unit/mvp_f2" / filename).read_text())
    value = next(
        n.value
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == symbol for t in n.targets)
    )
    if isinstance(value, ast.Set):
        return ast.literal_eval(value)
    # The historical CORE_IDS spelling is set(<literal>.split()).
    assert isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
    assert value.func.id == "set" and not value.keywords and len(value.args) == 1
    split = value.args[0]
    assert isinstance(split, ast.Call) and isinstance(split.func, ast.Attribute)
    assert split.func.attr == "split" and not split.args and not split.keywords
    return set(ast.literal_eval(split.func.value).split())


def validate_overlay(matrix):
    assert matrix["source_ledger_sha256"] == LEDGER_HASH
    assert matrix["source_freeze_sha256"] == FREEZE_HASH
    assert matrix["baseline"] == "d861b6f6c0447b2fbd25b7f58beba65163b00b25"
    rows = matrix["cases"]
    assert len(rows) == len(set(rows)) == 110 and set(rows) == set(CASES)
    frozen = freeze()
    source = {
        r["case_id"]: (group, r) for group, records in frozen["included"].items() for r in records
    }
    source.update({r["case_id"]: ("excluded", r) for r in frozen["excluded"]})
    for cid, row in rows.items():
        case = CASES[cid]
        assert row["case_id"] == cid
        for key in ("status", "execution", "operation", "domains", "expected"):
            assert row[key] == case[key], (cid, key)
        assert row["record_metadata_sha256"] == metadata_hash(case)
        assert row["record_metadata_sha256"] == source[cid][1]["record_metadata_sha256"]
        assert row["origin_partition"] == source[cid][0]
        assert row["source_pointer"] == (
            "tests/fixtures/mvp_if03/wu05_oracle01_v0_1/cases.json#/cases/"
            + str(list(CASES).index(cid))
        )
        assert row["implemented_scope"] and row["limitations"] and row["evidence_pointer"]
        executed = cid in SCOPED | RELATION_IDS
        assert (row["run_state"] == "EXECUTED") == executed
        assert row["prior_stage_provenance"] == (
            "PRIOR_STAGE_REPORTED" if cid in SCOPED else "NO_PRIOR_PRODUCTION_PASS_CLAIM"
        )
        assert row["evidence_provenance"] == (
            "EXECUTED_THIS_RUN" if executed else "NOT_RUN_THIS_RUN"
        )
        if not executed:
            assert all(
                row[k] is None for k in ("actual_category", "actual_code", "actual_relation")
            )
            assert row["api_under_test"] == "NONE" and row["dispatch_kind"] == "NOT_RUN"
            assert row["adjudication"] not in {"PASS_SCOPED", "PASS_BOUNDED_RELATION_DIAGNOSTIC"}
        elif cid.startswith("N-"):
            assert {"category": row["actual_category"], "code": row["actual_code"]} == case[
                "expected"
            ]
            assert row["actual_relation"] is None and row["adjudication"] == "PASS_SCOPED"
        else:
            assert row["actual_relation"] == case["expected"]
            assert row["actual_category"] is None and row["actual_code"] is None
    assert Counter(r["origin_partition"] for r in rows.values()) == {
        "complete_positives": 8,
        "narrow_refusals": 80,
        "executed_relations": 6,
        "excluded": 16,
    }
    assert sum(r["adjudication"] == "PASS_SCOPED" for r in rows.values()) == 61
    gaps = {cid for cid in CASES if cid.startswith("N-")} - SCOPED
    assert len(gaps) == 27 and Counter(CASES[c]["operation"] for c in gaps) == GAP_OPERATIONS
    assert sum(r["run_state"] == "EXECUTED" for r in rows.values()) == 67
    excluded = [CASES[c] for c in rows if rows[c]["origin_partition"] == "excluded"]
    assert Counter(c["status"] for c in excluded) == {
        "CONTRACT_RELATIONAL_ASSERTION": 5,
        "BLOCKED_NOT_CONSTRUCTIBLE": 10,
        "DEFERRED_SEPARATE_OWNER": 1,
    }
    for cid in ("P2-DEPTH-64", "P2-DEPTH-65"):
        assert rows[cid]["adjudication"] == "DEFERRED_DEPTH"
        assert "PENDING_OWNER_BOUNDARY_DECISION" in rows[cid]["limitations"]


def test_overlay_invariants_and_historical_scope_extraction():
    assert CORE_IDS == historical_ids("test_wu05_can01_codec.py", "CORE_IDS")
    assert REF_IDS == historical_ids("test_wu05_can02_references.py", "FROZEN_IDS")
    assert GRAPH_IDS == historical_ids("test_wu05_can02_graph.py", "FROZEN_IDS")
    assert (len(CORE_IDS), len(REF_IDS | GRAPH_IDS), len(SCOPED)) == (43, 10, 61)
    assert not CORE_IDS & (REF_IDS | GRAPH_IDS) and not REF_IDS & GRAPH_IDS
    validate_overlay(MATRIX)


@pytest.mark.parametrize("cid", sorted(SCOPED | RELATION_IDS))
def test_recorded_observations_reproduce(cid):
    row = MATRIX["cases"][cid]
    if cid.startswith("B"):
        actual = compare_golden(cid)
        assert actual.frame_digest == row["golden_expected_frame_sha256"]
    elif cid.startswith("N-"):
        assert observe_negative(CASES[cid]) == {
            "category": row["actual_category"],
            "code": row["actual_code"],
        }
    else:
        assert relation_observation(cid) == row["actual_relation"]
        assert row["adjudication"] == "PASS_BOUNDED_RELATION_DIAGNOSTIC"


def test_changed_expected_code_in_isolated_matrix_copy_is_detected():
    changed = copy.deepcopy(MATRIX)
    changed["cases"]["N-DIGEST"]["expected"]["code"] = "INJECTED_WRONG_EXPECTATION"
    with pytest.raises(AssertionError):
        validate_overlay(changed)
    actual = observe_negative(CASES["N-DIGEST"])
    assert actual != changed["cases"]["N-DIGEST"]["expected"]
    assert MATRIX["cases"]["N-DIGEST"]["expected"] == CASES["N-DIGEST"]["expected"]


def test_expected_helper_is_stdlib_only_and_has_no_production_or_author_dependency():
    tree = ast.parse((ROOT / "tests/unit/mvp_f2/wu05_can03_expected.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert imports <= {"json", "stat", "functools", "hashlib", "pathlib", "zipfile"}
    assert "wu05_oracle_reference" not in imports
