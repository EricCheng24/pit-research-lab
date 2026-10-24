"""Acceptance-side ENGINEERING_TEST and synthetic calibration; no admission grant."""

import copy
import hashlib
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest
from wu01_acceptance import ExternalAuthority, RuntimeGrant, calibrate, certify
from wu01_bindings import (
    candidate_bindings,
    candidate_content_bytes,
    candidate_content_sha256,
    documentary_accounting,
    runtime_accounting,
    source_records,
    validate_candidates,
    validate_registry,
)


def test_accounting_original_110_narratives_stay_blocked_and_154_unexecuted():
    records, _ = source_records()
    path = Path(__file__).parent.parent / "cap_f2_wu00" / "wu00_compare.py"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "b5e0a335b59354a2e2cedb2ea03bc2b7db125428c3b933bd027a8775d2331701"
    )
    module = ModuleType("_wu01_legacy_comparator")
    exec(compile(raw, str(path), "exec"), module.__dict__)
    assert len(records) == 110
    for record in records:
        assert module.compare({"value": 600}, record)["verdict"] == "BLOCKED"
        assert "semantic_comparison" in record
    runtime = runtime_accounting()
    assert len(runtime) == len({(cid, tier) for cid, tier, _ in runtime}) == 154
    assert {status for _, _, status in runtime} == {"NOT_EXECUTED"}
    assert ("A02-C01", "X", "NOT_EXECUTED") in runtime


def test_accounting_eight_candidates_nineteen_documentary_rows_and_separate_hashes():
    candidates = candidate_bindings()
    validate_candidates(candidates)
    assert len(candidates) == 8
    assert {c.status for c in candidates} == {"PROPOSED / NOT_APPROVED"}
    assert next(c for c in candidates if c.case_id == "A02-C01").full_required_tiers == ("S", "X")
    assert len(documentary_accounting()) == 19
    assert sum(state == "UNIMPLEMENTED" for _, state in documentary_accounting()) == 11
    raw = candidate_content_bytes(candidates)
    assert not raw.endswith(b"\n") and raw.isascii()
    assert candidate_content_sha256(candidates) == hashlib.sha256(raw).hexdigest()
    source_hash = hashlib.sha256(
        (Path(__file__).parent / "wu01_bindings.py").read_bytes()
    ).hexdigest()
    assert candidate_content_sha256(candidates) != source_hash


@pytest.mark.parametrize("fault", ["missing", "duplicate", "tier", "reason", "marker", "delta"])
def test_sensitivity_original_registry_integrity(fault):
    records, (golden, ledger) = source_records()
    altered = copy.deepcopy(records)
    if fault == "missing":
        altered.pop()
    elif fault == "duplicate":
        altered.append(copy.deepcopy(altered[0]))
    elif fault == "tier":
        altered[0]["required_tiers"] = ["S", "X"]
    elif fault == "reason":
        altered[0]["normative_fields"]["reason"] = "NONE"
    elif fault == "marker":
        altered[0]["semantic_comparison"] = "REVIEWED"
    else:
        altered[0]["delta_ref"] = "D-OTHER"
    with pytest.raises(ValueError):
        validate_registry(altered, golden, ledger)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "APPROVED"},
        {"case_id": "A03-C01"},
        {"full_required_tiers": ("S", "P")},
        {"source_row": "edited"},
        {"predicate_fields": ()},
        {"candidate_reason": "OTHER"},
    ],
)
def test_denial_candidate_scope_and_self_approval(changes):
    candidates = candidate_bindings()
    altered = (replace(candidates[0], **changes), *candidates[1:])
    with pytest.raises(ValueError):
        validate_candidates(altered)


@pytest.mark.parametrize(
    "authority,grant",
    [
        (None, None),
        ({"reviewer": "user", "decision": "APPROVED"}, None),
        (ExternalAuthority("", "", "", "forged-user", "APPROVED", False), None),
        (ExternalAuthority("a" * 64, "b" * 64, "c" * 64, "user", "APPROVED", False), None),
        (
            ExternalAuthority("a" * 64, "b" * 64, "c" * 64, "user", "APPROVED", True),
            RuntimeGrant("claimed-grant", "A02-C01", "S"),
        ),
        (
            ExternalAuthority("a" * 64, "b" * 64, "c" * 64, "user", "APPROVED", False),
            RuntimeGrant("claimed-grant", "A02-C01", "X"),
        ),
        (
            ExternalAuthority("a" * 64, "b" * 64, "c" * 64, "user", "APPROVED", False),
            RuntimeGrant("claimed-grant", "A02-C01", "S"),
        ),
    ],
)
def test_denial_external_claims_or_hashes_cannot_create_runtime_admission(authority, grant):
    before = runtime_accounting()
    result = certify({"state": "BOUND"}, candidate_bindings()[4], authority, grant)
    assert result.verdict == "BLOCKED" and result.runtime_evidence == ()
    assert runtime_accounting() == before
    if grant is None:
        assert "MISSING_SEPARATE_RUNTIME_GRANT" in result.issues
    if isinstance(authority, ExternalAuthority):
        assert "EXTERNAL_AUTHENTICATION_NOT_IMPLEMENTED_DEFERRED_WU01D" in result.issues


def test_calibration_exact_structural_equality_is_not_runtime_evidence():
    synthetic = {
        "state": "ARTIFICIAL_OK",
        "reason": "CALIBRATION",
        "value": 7,
        "target": ("T-CAL", "CV-CAL", "/x"),
        "lineage": ("SUP-CAL",),
    }
    result = calibrate(synthetic, copy.deepcopy(synthetic), stimulus_id="CAL-equal")
    assert (
        result.result == "PASS" and result.classification == "SYNTHETIC_COMPARATOR_CALIBRATION_ONLY"
    )
    assert not hasattr(result, "runtime_evidence")
    with pytest.raises(ValueError):
        calibrate(synthetic, synthetic, stimulus_id="A02-C01")


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "ARTIFICIAL_BAD"),
        ("reason", "OTHER"),
        ("value", True),
        ("value", 7.0),
        ("target", ("T-CAL", "OTHER-CV", "/x")),
        ("target", ("T-CAL", "CV-CAL", "/wrong")),
        ("lineage", ()),
        ("lineage", ("FORBIDDEN-CAL",)),
    ],
)
def test_calibration_detects_status_type_target_fragment_and_lineage(field, value):
    expected = {
        "state": "ARTIFICIAL_OK",
        "reason": "CALIBRATION",
        "value": 7,
        "target": ("T-CAL", "CV-CAL", "/x"),
        "lineage": ("SUP-CAL",),
    }
    actual = {**expected, field: value}
    assert calibrate(actual, expected, stimulus_id="CAL-actual-mutation").result == "FAIL"
    assert calibrate(expected, actual, stimulus_id="CAL-expected-mutation").result == "FAIL"
