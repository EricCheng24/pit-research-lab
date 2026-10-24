"""IC1-T01..T20 construction evidence; generated financial inputs are SYNTHETIC_TEST_ONLY."""

import ast
import builtins
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from ic1_inputs import (
    context,
    csv_bytes,
    fixture,
    pin,
    row,
    source,
    spec,
    write_source,
)

from pit_research_lab.domain import market_source_slice as reader
from pit_research_lab.domain import source_intake as legacy_io
from pit_research_lab.domain.contracts import ContractError, NotEvaluated
from pit_research_lab.domain.market_row_selection import (
    HEADERS,
    SelectedSourceRow,
    select_market_row,
    validate_ic1_intake,
)
from pit_research_lab.domain.market_source_slice import (
    IC1_CODE_PATHS,
    evaluate_market_source,
    inspect_market_source,
)
from pit_research_lab.domain.source_intake import (
    MAX_RAW_BYTES,
    FilePin,
    RawSourceIdentity,
    _open_root,
    _read_relative,
    validate_source_manifest,
)

ROOT = Path(__file__).resolve().parents[3]
INPUT = Path("/mnt/c/Users/rooki/Downloads/CAP-F2-V1-A06_source_inputs")
REAL_PINS = (
    FilePin(
        "t187ap05_L.csv", 205416, "754761b82a8a7ec9f6146cdaaaa415e1a8d609fec3222da0002ab93eea44ccfd"
    ),
    FilePin(
        "source_notes.txt", 271, "c13e2c33fd2585fc268a2af9896d65ec013b0c3b64e56ae270a9de61c69471d8"
    ),
)


def evaluated(code, value=None, **kwargs):
    value = source() if value is None else value
    return evaluate_market_source(value, spec(), context(code, value.intake, **kwargs), code)


def stopped(result):
    assert result.overall_disposition == "INTEGRATED_PROVISIONAL"
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.admission_eligible is False and result.diagnostic_only is True
    assert isinstance(result.agent_observation, NotEvaluated)
    assert all(isinstance(v, NotEvaluated) for _, v in result.owner_results)
    assert {
        s.stage: s.state for s in result.stages if s.stage in ("S1", "S2", "S3", "A04", "A05")
    } == {name: "NOT_EVALUATED" for name in ("S1", "S2", "S3", "A04", "A05")}
    assert (
        next(s.state for s in result.stages if s.stage == "TYPED_TRANSPORT")
        == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"
    )


@pytest.mark.skipif(
    os.environ.get("IC1_APPROVED_REAL") != "1",
    reason="Explicit IC1 owner-source identity check only",
)
@pytest.mark.parametrize("expected", REAL_PINS)
def test_ic1_t01_actual_owner_file_identification_only(expected):
    # Explicit forensic identity authorization; no CSV decode or admitted ingestion.
    fd = _open_root(INPUT)
    try:
        body = _read_relative(fd, expected.relative_path, MAX_RAW_BYTES)
        assert len(body) == expected.byte_length
        assert sha256(body).hexdigest() == expected.sha256
    finally:
        os.close(fd)


def test_ic1_t02_t04_missing_manifest_isolated_from_owner_root(monkeypatch, tmp_path):
    # Missing-manifest semantics must not depend on the approved live owner source root.
    test_root = tmp_path / "SYNTHETIC_TEST_ONLY_missing_manifest"
    test_root.mkdir()
    assert not (test_root / "manifest.json").exists()
    reads = []
    original = reader._read_relative

    def record(fd, name, limit):
        reads.append(name)
        return original(fd, name, limit)

    monkeypatch.setattr(reader, "_read_relative", record)
    result = inspect_market_source(test_root, pin("notes.txt", b"SYNTHETIC_TEST_ONLY"))
    assert result.intake.disposition == "SOURCE_INPUT_PENDING"
    assert result.intake.reason == "ROOT_MANIFEST_OR_PINNED_FILE_MISSING"
    assert reads == ["manifest.json"]  # No admitted raw, mapping, or notes reads.
    assert isinstance(result.intake.raw_bytes, NotEvaluated)
    assert select_market_row(result.intake, spec()).state == "NOT_EVALUATED"


def test_ic1_t02_t03_synthetic_full_market_1088_records(tmp_path):
    rows = [row(f"{i:04d}", str(i)) for i in range(1088)]
    m, raw, mapping = fixture(raw=csv_bytes(rows))
    notes = write_source(tmp_path / "SYNTHETIC_TEST_ONLY", m, raw, mapping)
    supplied = inspect_market_source(tmp_path / "SYNTHETIC_TEST_ONLY", notes)
    assert supplied.intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE"
    selected = select_market_row(supplied.intake, spec(expected_record_count=1088))
    assert selected.state == "ROW_SELECTED" and selected.record_count == 1088
    assert selected.selected.extracted.row_ordinal == 8
    assert selected.selected.extracted.source_amount_text == "7"
    assert (tmp_path / "SYNTHETIC_TEST_ONLY" / "market.csv").read_bytes() == raw


def test_ic1_t04_t05_t08_exact_source_locator_original_and_view(code):
    value = source(raw=csv_bytes([row("0090"), row(note='line1\r\nline2, "quoted"'), row("0010")]))
    before = value.intake.raw_bytes
    selected = evaluated(code, value).selection
    assert selected.state == "ROW_SELECTED" and selected.match_count == 1
    s = selected.selected
    assert isinstance(s, SelectedSourceRow) and s.extracted.row_ordinal == 2
    assert s.original == value.intake.observed_raw
    assert s.original.sha256 == sha256(before).hexdigest() and s.original.byte_length == len(before)
    assert s.amount_column_index == 5 and s.amount_column_name == HEADERS[5]
    assert s.extracted.source_amount_text == "321" and s.extracted.source_tokens[5] == "321"
    assert s.extracted.company_code == "0007" and s.extracted.headers == HEADERS
    assert s.extracted.source_fields[13] == 'line1\r\nline2, "quoted"'
    assert isinstance(s.extracted.exact_byte_span, NotEvaluated)
    assert s.view.representation_kind == "ADAPTER_GENERATED_SELECTION_VIEW"
    assert s.original.representation_kind == "ORIGINAL"
    assert (
        sha256(s.view.projection_bytes).hexdigest() == s.view.projection_sha256 != s.original.sha256
    )
    assert value.intake.raw_bytes == before


@pytest.mark.parametrize(
    "rows,state",
    [
        ([row("9999")], "TARGET_ROW_NOT_FOUND"),
        ([row(), row()], "DUPLICATE_TARGET_ROW"),
        ([row(), row(amount="999")], "DUPLICATE_TARGET_ROW"),
        ([row(amount="bogus"), row()], "DUPLICATE_TARGET_ROW"),
    ],
)
def test_ic1_t06_no_first_last_or_latest_winner(rows, state):
    result = select_market_row(source(raw=csv_bytes(rows)).intake, spec())
    assert result.state == state and isinstance(result.selected, NotEvaluated)


@pytest.mark.parametrize(
    "fault",
    [
        "width",
        "quote",
        "unicode",
        "header_duplicate",
        "header_order",
        "month",
        "bom",
        "field_limit",
        "column_limit",
        "bare_cr",
        "nul",
        "record_limit",
        "expected_count",
    ],
)
def test_ic1_t07_malformed_foreign_record_no_partial_value(fault):
    raw = csv_bytes([row(), row("9999")])
    selection_spec = spec()
    if fault == "width":
        raw = csv_bytes([row(), row("9999")[:-1]])
    elif fault == "quote":
        raw += b'"unclosed'
    elif fault == "unicode":
        raw += b"\xff"
    elif fault == "header_duplicate":
        raw = csv_bytes(headers=(*HEADERS[:-1], HEADERS[0]))
    elif fault == "header_order":
        raw = csv_bytes(headers=HEADERS[::-1])
    elif fault == "month":
        raw = csv_bytes([row(), row("9999", month="11508")])
    elif fault == "bom":
        raw = raw[3:]
    elif fault == "field_limit":
        raw = csv_bytes([row(), row("9999", note="x" * 4097)])
    elif fault == "column_limit":
        raw = csv_bytes([row(), ("x",) * 33])
    elif fault == "bare_cr":
        raw += b"x\ry"
    elif fault == "nul":
        raw += b"\x00"
    elif fault == "record_limit":
        raw = csv_bytes([row()]) + (b"x,11509,9999" + b"," * 11 + b"\r\n") * 10000
    elif fault == "expected_count":
        selection_spec = spec(expected_record_count=1088)
    result = select_market_row(source(raw=raw).intake, selection_spec)
    assert result.state == "EXTRACTION_REJECTED" and isinstance(result.selected, NotEvaluated)


@pytest.mark.parametrize("amount", ["NA", "", "-", "1.2", " 5", "+5", "01", "1,000", str(2**63)])
def test_ic1_t07_target_amount_unknown_or_invalid_fails_closed(amount):
    result = select_market_row(source(raw=csv_bytes([row(amount=amount)])).intake, spec())
    assert result.state == "EXTRACTION_REJECTED" and isinstance(result.selected, NotEvaluated)


@pytest.mark.parametrize("amount", [str(-(2**63)), str(2**63 - 1), "-5", "0"])
def test_ic1_t04_source_signed_integer_only(amount):
    result = select_market_row(source(raw=csv_bytes([row(amount=amount)])).intake, spec())
    assert result.state == "ROW_SELECTED" and result.selected.extracted.amount == int(amount)
    assert result.selected.amount_semantics == "SOURCE_REPORTED_INTEGER_ONLY"


@pytest.mark.parametrize(
    "fault",
    ["UNKNOWN", "RESTRICTED", "coverage", "uses", "terms", "origin", "attribution", "url_only"],
)
def test_ic1_t09_rights_refusal_zero_raw_reads_and_no_bytes(tmp_path, monkeypatch, fault):
    m, raw, mapping = fixture()
    rights = m.rights
    if fault in ("UNKNOWN", "RESTRICTED"):
        rights = replace(rights, status=fault)
    elif fault == "coverage":
        rights = replace(rights, covered_paths=("another.csv",))
    elif fault == "uses":
        rights = replace(rights, allowed_uses=("COMMERCIAL",))
    elif fault == "url_only":
        rights = replace(rights, evidence_text="https://example.invalid")
    else:
        rights = replace(
            rights,
            **{
                {"terms": "terms_ref", "origin": "origin_ref", "attribution": "attribution"}[
                    fault
                ]: None
            },
        )
    m = replace(m, rights=rights)
    notes = write_source(tmp_path / "source", m, raw, mapping)
    calls = []
    original = reader._read_relative

    def record(fd, name, limit):
        calls.append(name)
        return original(fd, name, limit)

    monkeypatch.setattr(reader, "_read_relative", record)
    result = inspect_market_source(tmp_path / "source", notes)
    assert calls == ["manifest.json"]  # includes zero raw-read attempts and zero raw bytes
    assert result.intake.disposition == "SOURCE_RESTRICTED_OR_RIGHTS_UNRESOLVED"
    assert isinstance(result.intake.raw_bytes, NotEvaluated)
    assert isinstance(result.intake.mapping_bytes, NotEvaluated)
    assert isinstance(result.intake.observed_raw, NotEvaluated)
    refused_legacy = validate_source_manifest(m, raw, mapping)
    guarded = validate_ic1_intake(refused_legacy)
    assert isinstance(guarded.raw_bytes, NotEvaluated)  # legacy finding remains OPEN


@pytest.mark.parametrize(
    "fault", ["none", "raw", "notes", "mapping", "rights", "custody", "snapshot"]
)
def test_ic1_t10_permitted_pinned_read_and_mutations(tmp_path, fault):
    m, raw, mapping = fixture(mapping_updates={})
    if fault == "rights":
        m = replace(m, rights=replace(m.rights, covered_paths=("market.csv",)))
    if fault == "custody":
        m = replace(m, custody_ref=None)
    if fault == "snapshot":
        m = replace(m, snapshot_ref="FORGED")
    notes = write_source(tmp_path / "source", m, raw, mapping)
    if fault in ("raw", "notes", "mapping"):
        name = {"raw": "market.csv", "notes": "notes.txt", "mapping": "mapping.json"}[fault]
        with (tmp_path / "source" / name).open("ab") as out:
            out.write(b" ")
    result = inspect_market_source(tmp_path / "source", notes)
    assert (result.intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE") == (
        fault == "none"
    )
    if fault != "none":
        assert isinstance(result.intake.raw_bytes, NotEvaluated)


@pytest.mark.parametrize(
    "fault",
    [
        "root_symlink",
        "ancestor_symlink",
        "raw_symlink",
        "manifest_symlink",
        "notes_symlink",
        "fifo",
        "directory",
        "oversize",
        "traversal",
        "relative_root",
        "missing",
        "collision",
    ],
)
def test_ic1_t11_unsafe_io_no_output_writes(tmp_path, fault):
    m, raw, mapping = fixture()
    root = tmp_path / "source"
    notes = write_source(root, m, raw, mapping)
    path = "manifest.json"
    if fault in ("root_symlink", "ancestor_symlink"):
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        if fault == "ancestor_symlink":
            (root / "child").mkdir()
            root = alias / "child"
        else:
            root = alias
    elif fault.endswith("_symlink"):
        name = {
            "raw_symlink": "market.csv",
            "manifest_symlink": "manifest.json",
            "notes_symlink": "notes.txt",
        }[fault]
        target = root / name
        outside = tmp_path / "outside"
        target.rename(outside)
        target.symlink_to(outside)
    elif fault in ("fifo", "directory", "oversize"):
        target = root / "market.csv"
        target.unlink()
        if fault == "fifo":
            os.mkfifo(target)
        elif fault == "directory":
            target.mkdir()
        else:
            target.write_bytes(b"x" * (MAX_RAW_BYTES + 1))
    elif fault == "traversal":
        path = "../manifest.json"
    elif fault == "relative_root":
        root = Path("relative/source")
    elif fault == "missing":
        root = tmp_path / "missing"
    elif fault == "collision":
        notes = replace(notes, relative_path="manifest.json")
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    result = inspect_market_source(root, notes, path)
    assert result.intake.disposition in ("SOURCE_INTEGRITY_FAILURE", "SOURCE_INPUT_PENDING")
    assert isinstance(result.intake.raw_bytes, NotEvaluated)
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


def test_ic1_t11_concurrent_change_guard(tmp_path, monkeypatch):
    (tmp_path / "synthetic.csv").write_bytes(b"SYNTHETIC_TEST_ONLY")
    fd = _open_root(tmp_path)
    original = os.fstat
    calls = []

    def changed(leaf):
        s = original(leaf)
        calls.append(leaf)
        return SimpleNamespace(
            st_mode=s.st_mode,
            st_size=s.st_size,
            st_dev=s.st_dev,
            st_ino=s.st_ino,
            st_mtime_ns=s.st_mtime_ns + len(calls),
        )

    monkeypatch.setattr(legacy_io.os, "fstat", changed)
    try:
        with pytest.raises(ContractError, match="INPUT_CHANGED_DURING_READ"):
            _read_relative(fd, "synthetic.csv", 100)
    finally:
        os.close(fd)


@pytest.mark.parametrize("mode", ["public", "prospective_observed"])
@pytest.mark.parametrize("cutoff", ["2025-07-07T00:00:00+08:00", "2025-07-14T00:00:00+08:00"])
def test_ic1_t12_t13_t15_t16_no_historical_owner_promotion(code, mode, cutoff):
    value = source(
        acquisition_text="1999-01-01T00:00:00+08:00",
        source_metadata_claims=(("publication", "1999"), ("coverage_COMPLETED", "forged")),
    )
    result = evaluated(code, value, mode=mode, cutoff=cutoff)
    assert result.selection.state == "ROW_SELECTED"
    assert isinstance(result.selection.selected, SelectedSourceRow)
    assert b"synthetic-notice-v1" not in result.selection.selected.view.projection_bytes
    assert result.selection.record_count == 3 and result.selection.match_count == 1
    assert next(s.state for s in result.stages if s.stage == "MAPPING") == "MAPPING_UNRESOLVED"
    stopped(result)


@pytest.mark.parametrize(
    "changes",
    [
        None,
        {},
        {"canonical_unit": "NTD"},
        {"basis_ref": "UNKNOWN"},
        {"issuer_code": "0099"},
        {"source_columns": {"source_amount": "營業收入-上月營收"}},
        {"reporting_scope": "unknown"},
        {"support_class": "OWNER_DECLARED"},
        {"issuer_ref": ""},
    ],
)
def test_ic1_t14_mapping_requires_independent_exact_support(code, changes):
    result = evaluated(code, source(mapping_updates=changes))
    state = next(s.state for s in result.stages if s.stage == "MAPPING")
    assert state == (
        "MAPPING_UNRESOLVED"
        if changes is None
        else "MAPPED_CONDITIONALLY"
        if changes == {}
        else "MAPPING_REJECTED"
    )
    stopped(result)


def test_ic1_t17_allowlist_invariant_under_private_audit_changes(code):
    a = source()
    m = replace(
        a.intake.manifest,
        custody_ref="PRIVATE_CUSTODY",
        rights=replace(a.intake.manifest.rights, evidence_text="PRIVATE_RIGHTS"),
        source_metadata_claims=(("future_revision", "PRIVATE_FUTURE"),),
    )
    b = replace(a, intake=validate_source_manifest(m, a.intake.raw_bytes))
    first, second = evaluated(code, a), evaluated(code, b)
    assert first.diagnostic_preview_bytes == second.diagnostic_preview_bytes
    assert first.selection == second.selection
    assert first.research_ref != second.research_ref
    assert set(json.loads(first.diagnostic_preview_bytes)) == {
        "preview_kind",
        "mode",
        "availability",
        "disposition",
        "trust",
        "source_authentication",
        "admission_eligible",
        "diagnostic_only",
    }
    for marker in (
        "PRIVATE",
        "321",
        "0007",
        "11509",
        "SYNTHETIC",
        "sha256",
        "reason",
        "proof",
        "rights",
        "custody",
    ):
        assert marker not in first.diagnostic_preview_bytes.decode()
    with pytest.raises(FrozenInstanceError):
        first.diagnostic_only = False


@pytest.mark.parametrize("change", ["foreign_amount", "order", "notes", "count_policy", "context"])
def test_ic1_t18_determinism_and_provenance_separation(code, change):
    a = source()
    first = evaluated(code, a)
    assert first == evaluated(code, a)
    b = a
    selection_spec = spec()
    ctx = context(code, b.intake)
    if change == "foreign_amount":
        b = source(raw=csv_bytes([row("0010", "changed"), row(), row("0090")]))
    elif change == "order":
        b = source(raw=csv_bytes([row(), row("0010", "not-an-integer"), row("0090")]))
    elif change == "notes":
        notes = b"SYNTHETIC_TEST_ONLY changed notes"
        b = replace(a, notes_bytes=notes, notes_pin=pin("notes.txt", notes))
    elif change == "count_policy":
        selection_spec = spec(expected_record_count=3)
    elif change == "context":
        ctx = context(code, b.intake, cutoff="2025-07-14T00:00:00+08:00")
    if change in ("foreign_amount", "order"):
        ctx = context(code, b.intake)
    second = evaluate_market_source(b, selection_spec, ctx, code)
    assert second.research_ref != first.research_ref
    assert second.selection.selected.extracted.amount == first.selection.selected.extracted.amount
    if change in ("foreign_amount", "order"):
        assert b.intake.manifest.snapshot_ref != a.intake.manifest.snapshot_ref
    assert first == evaluated(code, a)


@pytest.mark.parametrize(
    "fault", ["raw", "ready", "no_manifest", "identity", "notes", "notes_role", "code", "context"]
)
def test_ic1_t19_forged_transport_is_revalidated(code, fault):
    value = source()
    observation = code
    ctx = context(code, value.intake)
    if fault == "raw":
        value = replace(
            value, intake=replace(value.intake, raw_bytes=value.intake.raw_bytes + b"x")
        )
    elif fault == "ready":
        value = replace(
            value, intake=replace(value.intake, raw_bytes=NotEvaluated("IC1", "FORGED_READY"))
        )
    elif fault == "no_manifest":
        value = replace(
            value, intake=replace(value.intake, manifest=NotEvaluated("IC1", "FORGED_READY"))
        )
    elif fault == "notes_role":
        value = replace(value, notes_pin=replace(value.notes_pin, relative_path="market.csv"))
    elif fault == "identity":
        value = replace(
            value,
            intake=replace(value.intake, observed_raw=RawSourceIdentity("wrong.csv", 0, "0" * 64)),
        )
    elif fault == "notes":
        value = replace(value, notes_bytes=b"tamper")
    elif fault == "code":
        observation = replace(code, extension_pins=code.extension_pins[:-1])
    elif fault == "context":
        ctx = replace(ctx, evidence_set_ref="WRONG-SNAPSHOT")
    result = evaluate_market_source(value, spec(), ctx, observation)
    assert result.selection.state == "NOT_EVALUATED"
    assert isinstance(result.source.intake.raw_bytes, NotEvaluated)
    stopped(result)


def test_ic1_t19_pure_core_resource_denial_and_outer_pins(code, monkeypatch):
    value = source()
    ctx = context(code, value.intake)
    for p, n in zip(code.extension_pins, code.extension_byte_lengths, strict=True):
        body = (ROOT / p.path).read_bytes()
        assert len(body) == n and sha256(body).hexdigest() == p.sha256
    assert len(code.upstream_a06.extension_pins) == 3
    assert len(code.upstream_a06.upstream_a05.extension_pins) == 2
    assert len(code.upstream_a06.upstream_a05.upstream_a04.observed_working_files) == 10
    for path in IC1_CODE_PATHS:
        tree = ast.parse((ROOT / path).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(
            word in name
            for name in imports
            for word in ("tests", "oracle", "requests", "urllib", "sqlalchemy", "psycopg")
        )
        assert not any(
            isinstance(n, ast.Attribute) and n.attr in ("now", "today", "utcnow")
            for n in ast.walk(tree)
        )

    def denied(*args, **kwargs):
        raise AssertionError("unexpected pure-core I/O")

    for obj, name in (
        (builtins, "open"),
        (Path, "read_bytes"),
        (os, "open"),
        (os, "stat"),
        (socket, "socket"),
        (subprocess, "check_output"),
    ):
        monkeypatch.setattr(obj, name, denied)
    result = evaluate_market_source(value, spec(), ctx, code)
    assert result.selection.state == "ROW_SELECTED"
    stopped(result)


def test_ic1_t20_known_protected_content_pins():
    # Complete 63/36/15 preservation is also audited externally before delivery.
    pins = {
        "src/pit_research_lab/domain/source_intake.py": "c59235802a73f3285e98fbff72d5faa97e8797324bcbcf3f5e3b8cf60e48a240",
        "src/pit_research_lab/domain/source_adapter.py": "afaec82a33bded42b567f0d1bd2305d5a823f5b965e87ca6494747fb1108c4df",
        "src/pit_research_lab/domain/offline_replay.py": "d6c84c3a647bacd06e6dc06cc57f3139219b07742e766c67f6910be5fe273e7b",
        "tests/unit/cap_f2_v1_a06/test_offline_source.py": "1c58a1af8c6b100bbe523bfac1965d6be10572b29edf5794f3c63f1ffd56fe97",
    }
    for path, h in pins.items():
        assert sha256((ROOT / path).read_bytes()).hexdigest() == h


@pytest.mark.parametrize(
    "updates",
    [
        {"reference_month": "2026-13"},
        {"reference_month": "2026-9"},
        {"company_code": " 0007"},
        {"period_policy": "CE_YYYYMM-v0.1"},
        {"amount_column": "營業收入-上月營收"},
        {"policy": "latest"},
        {"expected_record_count": True},
    ],
)
def test_ic1_t19_invalid_policy_rejected(updates):
    from pit_research_lab.domain.market_row_selection import FullMarketSelectionSpec

    with pytest.raises(ContractError):
        FullMarketSelectionSpec(**updates)


@pytest.mark.parametrize(
    "fault", ["manifest_version", "csv_profile", "period_policy", "encoding", "company_code"]
)
def test_ic1_t19_profile_mismatch_cannot_select(fault):
    value = source(**{fault: "UNSUPPORTED"})
    result = select_market_row(value.intake, spec())
    assert result.state in {"NOT_EVALUATED", "EXTRACTION_REJECTED"}
    assert isinstance(result.selected, NotEvaluated)
