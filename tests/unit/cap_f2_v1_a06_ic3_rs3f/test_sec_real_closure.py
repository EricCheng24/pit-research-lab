"""RS3F synthetic faults only. Real-source execution is separately opted in."""

import ast
import json
import os
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path

import pytest

import pit_research_lab.domain.sec_real_closure as controller
from pit_research_lab.domain.contracts import ContractError, NotEvaluated
from pit_research_lab.domain.issuer_html_extraction import HtmlEvidenceObservation, extract_html
from pit_research_lab.domain.sec_financial_diagnostic import (
    SEC_PIN,
    FieldEvidence,
    compare_amounts,
)
from pit_research_lab.domain.sec_real_closure import APPROVED_REQUEST, DOCUMENTS, PINNED_CODE
from pit_research_lab.domain.source_intake import FilePin

REPOSITORY = Path(__file__).absolute().parents[3]


def pin(name, body):
    return FilePin(name, len(body), sha256(body).hexdigest())


def refused(result, *, before_body=True):
    assert result.status == "REFUSED"
    assert isinstance(result.observation, NotEvaluated)
    assert isinstance(result.diagnostic, NotEvaluated)
    assert isinstance(result.source_body, NotEvaluated)
    assert not result.admission_eligible
    if before_body:
        assert result.body_read_attempts == ()
        assert not any(e.stage == "SEC_SOURCE_BODY_READ" for e in result.events)


def test_t01_t28_exact_accepted_baseline(rs2_fixture):
    extra = (
        (
            "src/pit_research_lab/domain/issuer_html_extraction.py",
            29798,
            "f6cdc70564b4836543f732dfaed630e1f0a563986e88145f748a7e8d7d0e9cd3",
        ),
        (
            "src/pit_research_lab/domain/issuer_html_slice.py",
            10438,
            "4930e8635729b5d7d92cf4202595575f1e2edd2b19d3512996beb3386411b425",
        ),
        (
            "tests/unit/cap_f2_v1_a06_ic3_rs2/conftest.py",
            318,
            "1bc869afe3823a0dd50aa5cd853af8b4d18d3e5e17a8a4a4bc8a2d7a855e0204",
        ),
        (
            "tests/unit/cap_f2_v1_a06_ic3_rs2/rs2_inputs.py",
            23831,
            "0967227c8884b27721db7168dfb945cc0992eb8678cbc5cca4af72d023d62d55",
        ),
        (
            "tests/unit/cap_f2_v1_a06_ic3_rs2/test_issuer_html_extraction.py",
            31873,
            "e82368ea37f4d2d577c1b1e9fb6168cc5d0b260f2c9f0f1cbe697dfbb093c5e6",
        ),
    )
    candidates = (*rs2_fixture.CANDIDATE_PINS, *extra)
    assert len(rs2_fixture.CANDIDATE_PINS) == 46
    assert len(candidates) == 51 and len(rs2_fixture.TRACKED_PINS) == 63
    assert len({name for name, _, _ in candidates}) == 51
    assert len(rs2_fixture.WU00_PINS) == 15
    ic1_path = "tests/unit/cap_f2_v1_a06_ic1/test_market_source_slice.py"
    rs2_path = "tests/unit/cap_f2_v1_a06_ic3_rs2/test_issuer_html_extraction.py"
    # Historical tuples stay frozen; current exceptions cover only these reviewed edits.
    historical_versions = {
        ic1_path: (
            23778,
            "cedcd2ecd13edb87934fb5a99023eac2ffae01cbc52583b75aa8a22dd355b288",
        ),
        rs2_path: (
            31873,
            "e82368ea37f4d2d577c1b1e9fb6168cc5d0b260f2c9f0f1cbe697dfbb093c5e6",
        ),
    }
    current_versions = {
        ic1_path: (
            23817,
            "b8357c4323445363cab4cec1fb960ccc02cc883ffa774c9a096d54339cbce1cf",
        ),
        rs2_path: (
            32611,
            "0305a5a53c33abdc15dee485edcf90f5ce9c76da6434e3a3aa5d72144e2923d8",
        ),
    }
    assert len(current_versions) == 2 and set(current_versions) == set(historical_versions)
    assert set(current_versions).isdisjoint(
        name for name, _, _ in (*rs2_fixture.TRACKED_PINS, *rs2_fixture.WU00_PINS)
    )
    for path, historical_pin in historical_versions.items():
        assert tuple(pin for pin in candidates if pin[0] == path) == ((path, *historical_pin),)
    for name, length, digest in (*candidates, *rs2_fixture.TRACKED_PINS, *rs2_fixture.WU00_PINS):
        if name in current_versions:
            length, digest = current_versions[name]
        source = REPOSITORY / name
        assert REPOSITORY in source.parents and source.resolve() == source and source.is_file()
        body = source.read_bytes()
        assert len(body) == length and sha256(body).hexdigest() == digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "Other"),
        ("cik", "0000000001"),
        ("accession", "OTHER"),
        ("exhibit", "Exhibit 99.1"),
        ("purpose", "REDISTRIBUTION"),
        ("reference_month", "2026-08"),
        ("profile_id", "OTHER"),
        ("classification", "SYNTHETIC_TEST_ONLY"),
        ("source_root", "/tmp/SYNTHETIC_TEST_ONLY_source"),
        ("source_root", controller.SOURCE_ROOT + "/../CAP-F2-V1-A06-IC3_support_inputs"),
        ("source_pin", replace(SEC_PIN, relative_path="synthetic_unapproved.html")),
        ("source_pin", replace(SEC_PIN, sha256="0" * 64)),
        ("source_pin", replace(SEC_PIN, byte_length=58213)),
    ],
)
def test_t02_t06_scope_denied_before_any_io(monkeypatch, field, value):
    def forbidden(*args):
        pytest.fail("Invalid scope reached file I/O")

    monkeypatch.setattr(controller, "_read_pinned", forbidden)
    monkeypatch.setattr(controller, "_disk_code", forbidden)
    refused(controller.run_sec_diagnostic(replace(APPROVED_REQUEST, **{field: value})))


@pytest.mark.parametrize(
    "fake",
    ["PERMITTED", "fake-approval-ref", True, {"is_approved": True}, {"signature": "self-signed"}],
)
def test_t05_caller_receipts_are_not_authority(monkeypatch, fake):
    monkeypatch.setattr(controller, "_disk_code", lambda: pytest.fail("No I/O"))
    refused(controller.run_sec_diagnostic(fake))
    with pytest.raises(TypeError):
        controller.run_sec_diagnostic(approval_ref="PERMITTED")


@pytest.mark.parametrize("index", range(9))
@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_t03_t04_t07_document_failure_zero_sec_opens(monkeypatch, index, failure):
    reads = []

    def fake_read(root, p):
        reads.append(str(root) + "/" + p.relative_path)
        assert str(root) != controller.SOURCE_ROOT
        if p == DOCUMENTS[index].pin:
            if failure == "missing":
                raise FileNotFoundError("SYNTHETIC_TEST_ONLY_missing")
            raise ContractError("SOURCE_PIN_MISMATCH")
        return b"SYNTHETIC_TEST_ONLY mocked earlier documentary read"

    monkeypatch.setattr(controller, "_read_pinned", fake_read)
    refused(controller.run_sec_diagnostic())
    assert len(reads) == index + 1


def decision_fixture():
    """Invented minimal schema fixture, never the approval transcription or its file."""
    return {
        "actual_approved_scope": {
            "accession": APPROVED_REQUEST.accession,
            "cik": APPROVED_REQUEST.cik,
            "conditional_permitted_operation": "AFTER_RIGHTS_EVIDENCE_AND_INDEPENDENT_VERIFICATION: offline read-only inert HTML locating and original-preserving extraction to a separately hashed view with SEC EDGAR attribution",
            "content": "Exhibit 99.2 text and financial table content only",
            "exclusions": list(controller.EXCLUSIONS),
            "exhibit": "Exhibit 99.2",
            "express_no_grants": list(controller.NO_GRANTS),
            "filing": "SEC EDGAR Form 6-K",
            "issuer": APPROVED_REQUEST.issuer,
            "purpose": "OFFLINE_RESEARCH",
            "source_capture": {
                "bytes": 58214,
                "capture_class": "BROWSER_SAVED_CAPTURE",
                "relative_path": "umc-ex99.htm",
                "sha256": SEC_PIN.sha256,
            },
            "system": "PIT Research Lab",
            "temporal_class": "NON_PIT",
        },
        "record_schema": "CAP-F2-V1-A06-IC3-RS3B1-OWNER-DECISION-PROPOSED-v0.1",
        "decision_status": "APPROVED_IN_CONVERSATION",
        "authorizer_identity": "NOT_INDEPENDENTLY_AUTHENTICATED",
        "decision_time_basis": "NON_PIT_NO_TRUSTED_MESSAGE_TIME_OBSERVED",
        "decision_message_native_id": None,
        "decision_message_server_timestamp": None,
        "decision_message_raw_transport_bytes_available": False,
        "chat_transcription": {
            "bom": False,
            "bytes": 1241,
            "filename": DOCUMENTS[3].pin.relative_path,
            "raw_chat_message_hash_is_this": False,
            "sha256": DOCUMENTS[3].pin.sha256,
            "source": "assistant_transcription_of_user_message",
            "trailing_newline": False,
            "unicode_normalization": "NONE",
        },
        "documentary_basis": {
            "policy_capture_pins": [
                {
                    "bytes": d.pin.byte_length,
                    "classification": "BROWSER_SAVED_POLICY_CAPTURES",
                    "relative_path": d.pin.relative_path,
                    "sha256": d.pin.sha256,
                }
                for d in DOCUMENTS[:2]
            ],
            "rights_source_notes_pin": {
                "bytes": DOCUMENTS[2].pin.byte_length,
                "relative_path": DOCUMENTS[2].pin.relative_path,
                "sha256": DOCUMENTS[2].pin.sha256,
            },
            "rs3a_report": {
                "bytes": DOCUMENTS[5].pin.byte_length,
                "filename": DOCUMENTS[5].pin.relative_path,
                "sha256": DOCUMENTS[5].pin.sha256,
            },
            "rs3a_inventory": {
                "bytes": DOCUMENTS[6].pin.byte_length,
                "filename": DOCUMENTS[6].pin.relative_path,
                "sha256": DOCUMENTS[6].pin.sha256,
            },
        },
        "engineering_baseline": {
            "ic2_manifest_sha256": controller.MANIFEST_PIN.sha256,
            "ic2_snapshot": controller.SNAPSHOT,
        },
        "synthetic_fixture_label": "SYNTHETIC_TEST_ONLY_not_an_authorization_record",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("issuer", "Other"),
        ("cik", "wrong"),
        ("accession", "wrong"),
        ("exhibit", "Exhibit 99.1"),
        ("purpose", "PERMITTED"),
        ("temporal_class", "PIT"),
        ("exclusions", []),
        ("express_no_grants", []),
        ("source_capture", {}),
    ],
)
def test_t04_t06_parsed_scope_rejected_before_source(monkeypatch, key, value):
    data = decision_fixture()
    data["actual_approved_scope"][key] = value
    reads = []

    def fake_read(root, p):
        assert str(root) != controller.SOURCE_ROOT
        reads.append(p.relative_path)
        return json.dumps(data).encode()

    monkeypatch.setattr(controller, "_read_pinned", fake_read)
    refused(controller.run_sec_diagnostic())
    assert len(reads) == 9


@pytest.mark.parametrize(
    "kind", ["policy_sha", "transcript_sha", "native_identity", "duplicate_json"]
)
def test_t04_t05_t06_exact_decision_links(kind):
    data = decision_fixture()
    if kind == "policy_sha":
        data["documentary_basis"]["policy_capture_pins"][0]["sha256"] = "0" * 64
    elif kind == "transcript_sha":
        data["chat_transcription"]["sha256"] = "0" * 64
    elif kind == "native_identity":
        data["decision_message_native_id"] = "fake-native-ref"
    body = json.dumps(data).encode()
    if kind == "duplicate_json":
        body = b'{"actual_approved_scope":{},"actual_approved_scope":{}}'
    with pytest.raises(ContractError):
        controller._validate_decision(body)


def test_t04_synthetic_scope_schema_only_never_runtime_authority():
    body = json.dumps(decision_fixture()).encode()
    controller._validate_decision(body)
    from pit_research_lab.domain.sec_financial_diagnostic import check_pin

    with pytest.raises(ContractError, match="SOURCE_PIN_MISMATCH"):
        check_pin(body, DOCUMENTS[4].pin)


def test_t06_changed_code_profile_zero_body(monkeypatch):
    monkeypatch.setattr(
        controller,
        "_disk_code",
        lambda: (_ for _ in ()).throw(ContractError("CODE_PROFILE_PIN_MISMATCH")),
    )
    monkeypatch.setattr(controller, "_read_pinned", lambda *a: pytest.fail("No source read"))
    refused(controller.run_sec_diagnostic())


def test_t08_fake_bw_name_zero_body(monkeypatch):
    # This named fake is in /tmp only; no real BW path, bytes or hash is used.
    request = replace(
        APPROVED_REQUEST,
        source_root="/tmp/SYNTHETIC_TEST_ONLY",
        source_pin=FilePin("fake_business_wire.html", 1, "0" * 64),
    )
    monkeypatch.setattr(controller, "_read_pinned", lambda *a: pytest.fail("BW read"))
    refused(controller.run_sec_diagnostic(request))


@pytest.mark.parametrize(
    "kind",
    [
        "leaf_symlink",
        "root_symlink",
        "fifo",
        "directory",
        "hash",
        "length",
        "partial",
        "leaf_swap",
        "root_swap",
    ],
)
def test_t09_t10_guarded_synthetic_files(tmp_path, monkeypatch, kind):
    root = tmp_path / "SYNTHETIC_TEST_ONLY"
    root.mkdir()
    body = b"SYNTHETIC_TEST_ONLY invented file"
    p = pin("invented.txt", body)
    leaf = root / p.relative_path
    leaf.write_bytes(body)
    if kind in ("leaf_symlink", "fifo", "directory"):
        leaf.unlink()
        if kind == "leaf_symlink":
            target = root / "target.txt"
            target.write_bytes(body)
            leaf.symlink_to(target)
        elif kind == "fifo":
            os.mkfifo(leaf)
        else:
            leaf.mkdir()
    elif kind == "root_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    elif kind == "hash":
        leaf.write_bytes(b"X" * len(body))
    elif kind == "length":
        leaf.write_bytes(body + b"!")
    else:
        original = controller.os.read
        changed = False

        def race(fd, limit):
            nonlocal changed
            if kind == "partial":
                return b""
            block = original(fd, limit)
            if not changed:
                changed = True
                if kind == "root_swap":
                    root.rename(tmp_path / "retired")
                    root.mkdir()
                    (root / p.relative_path).write_bytes(body)
                else:
                    replacement = root / "replacement"
                    replacement.write_bytes(body)
                    os.replace(replacement, leaf)
            return block

        monkeypatch.setattr(controller.os, "read", race)
    with pytest.raises((ContractError, OSError)):
        controller._read_pinned(root, p)


@pytest.mark.parametrize("path", ["../escape", "a/../b", "/tmp/file", "a\\b", ".hidden"])
def test_t09_traversal_rejected(path):
    with pytest.raises(ContractError):
        FilePin(path, 1, "0" * 64)


@pytest.mark.parametrize("reason", ["SOURCE_PIN_MISMATCH", "SOURCE_ROOT_CHANGED_DURING_READ"])
def test_t10_post_open_failure_emits_no_view(monkeypatch, reason):
    # All earlier I/O replaced with invented bytes; financial read itself fails.
    data = json.dumps(decision_fixture()).encode()
    from pit_research_lab.domain.source_intake import decode_manifest

    def fake_read(root, p):
        if str(root) == controller.SOURCE_ROOT:
            raise ContractError(reason)
        return data

    class FakeManifest:
        raw = controller.GOV_PIN
        mapping_file = None
        snapshot_ref = controller.SNAPSHOT

    import pit_research_lab.domain.market_row_selection as market
    import pit_research_lab.domain.source_intake as intake

    monkeypatch.setattr(controller, "_read_pinned", fake_read)
    monkeypatch.setattr(intake, "decode_manifest", lambda b: FakeManifest())
    monkeypatch.setattr(
        market,
        "preflight_manifest",
        lambda m: type("Preflight", (), {"reason": "RIGHTS_PREFLIGHT_PASSED"})(),
    )
    assert callable(decode_manifest)
    result = controller.run_sec_diagnostic()
    refused(result, before_body=False)
    assert result.body_read_attempts == (controller.SOURCE_ROOT + "/umc-ex99.htm",)
    assert result.reason == reason


@pytest.mark.parametrize(
    "kind",
    [
        "duplicate_marker",
        "duplicate_row",
        "wrong_year",
        "hidden",
        "script",
        "malformed",
        "charset",
        "encoding",
    ],
)
def test_t12_t15_t16_invented_structure_faults(rs2_fixture, kind):
    text = rs2_fixture.sec_html()
    if kind == "duplicate_marker":
        text = text.replace("<p>Exhibit 99.2</p>", "<p>Exhibit 99.2</p>" * 2)
    elif kind == "duplicate_row":
        target = rs2_fixture.row(["September", "Net sales", "8,642", "5,103", "3,539", "69.35%"])
        text = text.replace(target, target * 2)
    elif kind == "wrong_year":
        text = text.replace("<td>2026</td>", "<td>2025</td>")
    elif kind == "hidden":
        text = text.replace("<td>8,642</td>", "<td hidden>8,642</td>")
    elif kind == "script":
        text = text.replace("<td>8,642</td>", "<td><script>8,642</script></td>")
    elif kind == "malformed":
        text = text.replace("</html>", "")
    elif kind == "charset":
        text = text.replace("windows-1252", "UTF-8")
    body, p, spec = rs2_fixture.material(text)
    if kind == "encoding":
        body += b"\x81"
        p = pin(p.relative_path, body)
    result = extract_html(body, p, spec, PINNED_CODE[:2])
    assert not isinstance(result, HtmlEvidenceObservation)


def test_t19_numeric_only_no_conversion():
    assert compare_amounts(25350431, 25350431).state == "EQUAL"
    assert compare_amounts(25350431, 25350432).state == "CONTRADICTED"
    assert compare_amounts(1, 1000).unit_operation == "NO_UNIT_OR_CURRENCY_CONVERSION"
    for value in (True, "25350431", 25350431.0):
        with pytest.raises(ContractError):
            compare_amounts(value, 25350431)


def test_t20_matrix_immutable():
    row = FieldEvidence(
        "SYNTHETIC",
        "0" * 64,
        "consolidated",
        "NOT_ESTABLISHED_BY_SEC",
        None,
        (),
        "SYNTHETIC_TEST_ONLY",
    )
    with pytest.raises(FrozenInstanceError):
        row.value = "consolidated"


def test_t08_t23_no_discovery_or_native_dispatch():
    for name in controller.BRIDGE_PATHS:
        tree = ast.parse((REPOSITORY / name).read_text())
        identifiers = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not identifiers & {"socket", "requests", "subprocess", "urlopen", "httpx"}
        assert not attributes & {
            "rglob",
            "glob",
            "walk",
            "iterdir",
            "read_bytes",
            "write_bytes",
            "write_text",
            "evaluate_financial_semantics",
            "evaluate_market_source",
            "assess_financial_semantics",
        }
