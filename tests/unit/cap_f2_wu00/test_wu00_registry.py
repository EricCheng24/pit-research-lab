"""Independent documentary row reconciliation and initially unexecuted runtime accounting."""

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest
from wu00_compare import compare
from wu00_evidence import case_rollup, initialize, record_runtime, record_static
from wu00_oracle import cells, load_cases, source_texts, validate


def verify_authored_inventory(root, pins):
    """Ignore only regular Python bytecode inside __pycache__; retain strict authored equality."""
    assert len(pins) == len({pin["path"] for pin in pins}) == 15
    actual = set()
    for path in root.rglob("*"):
        assert not path.is_symlink(), f"symlink in candidate: {path}"
        if path.is_dir():
            continue
        assert path.is_file(), f"nonregular candidate entry: {path}"
        if path.parent.name == "__pycache__" and path.suffix == ".pyc":
            continue
        actual.add(str(path.relative_to(root)))
    assert actual == {pin["path"] for pin in pins} | {"data/provenance/artifact_bindings.json"}
    for pin in pins:
        relative = Path(pin["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        path = root / pin["path"]
        assert not path.is_symlink()
        data = path.read_bytes()
        assert (len(data), hashlib.sha256(data).hexdigest()) == (pin["byte_length"], pin["sha256"])


def test_produced_file_pins_and_ordinary_source_availability():
    root = Path(__file__).parent
    binding_path = root / "data/provenance/artifact_bindings.json"
    binding = json.loads(binding_path.read_text())
    verify_authored_inventory(root, binding["produced_files"])
    ordinary = {s["alias"] for s in binding["authoring_sources"] if s["required_in_ordinary_tests"]}
    assert ordinary == {"G", "L"}
    assert binding["governance"]["acceptance_granted"] is False
    assert len(binding["governance"]["decisions"]) == 10


@pytest.fixture
def authored_tree(tmp_path):
    assert not tmp_path.resolve().is_relative_to(Path(__file__).resolve().parents[3])
    pins = []
    for index in range(15):
        relative = f"data/inputs/asset{index}.json"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = b"{}\n"
        path.write_bytes(data)
        pins.append(
            {"path": relative, "byte_length": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    manifest = tmp_path / "data/provenance/artifact_bindings.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n")
    return tmp_path, pins


def test_authored_inventory_accepts_normal_tree_and_python_bytecode(authored_tree):
    root, pins = authored_tree
    verify_authored_inventory(root, pins)
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "test_wu00_registry.cpython-312.pyc").write_bytes(b"synthetic bytecode stimulus")
    verify_authored_inventory(root, pins)


@pytest.mark.parametrize(
    "extra", ["rogue.py", "data/inputs/rogue.json", "__pycache__/rogue.py", "rogue.pyc"]
)
def test_authored_inventory_rejects_unknown_files(authored_tree, extra):
    root, pins = authored_tree
    path = root / extra
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("rogue")
    with pytest.raises(AssertionError):
        verify_authored_inventory(root, pins)


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate_pin", "wrong_hash", "wrong_length", "symlink"]
)
def test_authored_inventory_rejects_missing_or_invalid_pins(authored_tree, fault):
    root, pins = authored_tree
    path = root / pins[0]["path"]
    if fault == "missing":
        path.unlink()
    elif fault == "duplicate_pin":
        pins[-1] = pins[0].copy()
    elif fault == "wrong_hash":
        pins[0]["sha256"] = "0" * 64
    elif fault == "wrong_length":
        pins[0]["byte_length"] += 1
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(root / pins[1]["path"])
    with pytest.raises(AssertionError):
        verify_authored_inventory(root, pins)


def test_every_normative_cell_and_ledger_row_is_preserved():
    records = load_cases()
    golden, ledger = source_texts()
    source = [row for row in golden if re.match(r"\| `(A\d{2}-C\d{2}|RP\d{2}-T\d{2})`", row)]
    assert len(source) == 110
    assert {row.split("`")[1] for row in source} == {r["case_id"] for r in records}
    assert sum(r["case_id"].startswith("A") for r in records) == 64
    assert sum(r["case_id"].startswith("RP") for r in records) == 46
    for record in records:
        row = golden[record["source"]["line"] - 1]
        assert row == record["source"]["row"]
        assert list(record["normative_fields"].values()) == cells(row)
        assert record["ledger"]["row"] == ledger[record["ledger"]["line"] - 1]
        # Untyped narrative and conditional assertions are visible, never silently certified.
        assert compare({"value": 600}, record)["verdict"] == "BLOCKED"


def test_per_row_tier_accounting_and_evidence_channels():
    records = load_cases()
    pairs = [(r["case_id"], t) for r in records for t in r["required_tiers"]]
    assert len(pairs) == len(set(pairs)) == 154
    assert Counter(t for _, t in pairs) == {"S": 56, "X": 29, "M": 16, "P": 53}
    envelope = initialize(records)
    record_static(envelope, "foundation-probe", "PASS", {"selected": 1})
    assert all(row["verdict"] == "NOT_EXECUTED" for row in envelope["golden_runtime"])
    assert all(case_rollup(envelope, record) == "NOT_EXECUTED" for record in records)
    with pytest.raises(ValueError, match="authorized runtime"):
        record_runtime(envelope, "A01-C01", "S", "PASS", {"comparison": "PASS"})
    receipt = {
        "separate_runtime_authorization": "comparator-unit-stimulus-only",
        "execution_id": "synthetic-probe",
        "actual": {"value": 600},
        "expected_source": "unit-probe",
        "comparison": "PASS",
        "negative_assertions_checked": True,
        "cleanup": "no resources",
        "persistence": {"backend": "mock"},
    }
    with pytest.raises(ValueError, match="real guarded"):
        record_runtime(envelope, "RP01-T01", "P", "PASS", receipt)
    # Even forged all-PASS rows cannot roll up an unbound narrative oracle as accepted.
    forged = copy.deepcopy(envelope)
    for row in forged["golden_runtime"]:
        row.update(verdict="PASS", runtime_evidence={"unit_probe": True})
    assert case_rollup(forged, records[0]) == "BLOCKED"
    shortened = copy.deepcopy(envelope)
    shortened["golden_runtime"].pop(0)
    assert case_rollup(shortened, records[0]) == "BLOCKED"


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing", "extra", "tier", "reason", "lineage", "forbidden"]
)
def test_registry_rejects_omission_generalization_and_oracle_edits(mutation):
    records = load_cases()
    if mutation == "duplicate":
        records.append(copy.deepcopy(records[0]))
    elif mutation == "missing":
        records.pop()
    elif mutation == "extra":
        records[-1]["case_id"] = "RP99-T99"
    elif mutation == "tier":
        records[0]["required_tiers"].append("P")
    else:
        field = "lineage_exclusions" if mutation == "lineage" else mutation
        records[0]["normative_fields"][field] = "OMITTED"
    with pytest.raises(ValueError):
        validate(records)
