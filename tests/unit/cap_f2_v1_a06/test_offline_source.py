"""A06 engineering negatives. Every local CSV/permission is SYNTHETIC_TEST_ONLY."""

import ast
import builtins
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest
from a05_inputs import inputs as ratio_inputs
from a06_inputs import HEADERS, context, csv_bytes, fixture, intake, manifest_bytes, write_fixture

from pit_research_lab.domain.contracts import ContractError, NotEvaluated
from pit_research_lab.domain.offline_replay import (
    A06_CODE_PATHS,
    evaluate_offline_replay,
    observe_offline_code,
)
from pit_research_lab.domain.ratio_slice import evaluate_ratio
from pit_research_lab.domain.source_adapter import assess_mapping, extract_monthly_rows
from pit_research_lab.domain.source_intake import (
    MAX_RAW_BYTES,
    FilePin,
    decode_manifest,
    inspect_offline_source,
    validate_source_manifest,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_offline_code(ROOT)


def stopped(result):
    assert (
        result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
        and result.source_authentication == "NOT_ESTABLISHED"
    )
    assert result.admission_eligible is False and result.diagnostic_only is True
    assert all(isinstance(value, NotEvaluated) for _, value in result.owner_results)
    assert all(
        s.state == "NOT_EVALUATED"
        for s in result.stages
        if s.stage in {"S1", "S2", "S3", "A04", "A05"}
    )
    assert isinstance(result.agent_observation, NotEvaluated)
    assert not hasattr(result, "to_agent_observation")


@pytest.mark.parametrize("missing", ["root", "manifest", "raw", "mapping"])
def test_t01_pending_never_creates_sample(tmp_path, missing):
    root = tmp_path / "source"
    m, raw, mapping = fixture(mapped=missing == "mapping")
    if missing != "root":
        root.mkdir()
    if missing not in {"root", "manifest"}:
        (root / "manifest.json").write_bytes(manifest_bytes(m))
    if missing == "mapping":
        (root / m.raw.relative_path).write_bytes(raw)
    before = set(tmp_path.rglob("*"))
    result = inspect_offline_source(root)
    assert result.disposition == "SOURCE_INPUT_PENDING"
    assert set(tmp_path.rglob("*")) == before


def test_t02_pure_and_reader_integrity_match(tmp_path):
    m, raw, metadata = fixture(mapped=True)
    root = tmp_path / "source"
    write_fixture(root, m, raw, metadata)
    expected = validate_source_manifest(m, raw, metadata)
    assert inspect_offline_source(root) == expected
    assert expected.observed_raw.sha256 == sha256(raw).hexdigest() and expected.raw_bytes == raw
    assert expected.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE"


@pytest.mark.parametrize("fault", ["raw", "length", "sha", "mapping", "snapshot", "custody"])
def test_t02_mutated_bytes_or_manifest_fail_closed(fault):
    m, raw, metadata = fixture(mapped=True)
    if fault == "raw":
        raw = raw[:-1] + bytes([raw[-1] ^ 1])
    elif fault == "length":
        m = replace(m, raw=replace(m.raw, byte_length=m.raw.byte_length + 1))
    elif fault == "sha":
        m = replace(m, raw=replace(m.raw, sha256="0" * 64))
    elif fault == "mapping":
        metadata += b" "
    elif fault == "snapshot":
        m = replace(m, snapshot_ref="OLD-SNAPSHOT")
    else:
        m = replace(m, custody_ref=None)
    assert validate_source_manifest(m, raw, metadata).disposition == "SOURCE_INTEGRITY_FAILURE"


@pytest.mark.parametrize(
    "name",
    [
        "../manifest.json",
        "/tmp/manifest.json",
        "a/../manifest.json",
        "a//manifest.json",
        "a\\manifest.json",
        "report.md",
        "result.zip",
    ],
)
def test_t03_unsafe_manifest_paths_rejected_before_read(tmp_path, name):
    result = inspect_offline_source(tmp_path / "source", name)
    assert result.disposition == "SOURCE_INTEGRITY_FAILURE"


@pytest.mark.parametrize(
    "name",
    [
        "../source.csv",
        "/tmp/source.csv",
        "a/../../source.csv",
        "a\\source.csv",
        ".env",
        "C:/source.csv",
    ],
)
def test_t03_unsafe_raw_pins_rejected(name):
    with pytest.raises(ContractError):
        FilePin(name, 0, sha256(b"").hexdigest())


@pytest.mark.parametrize(
    "kind",
    ["root_symlink", "ancestor_symlink", "manifest_symlink", "raw_symlink", "directory", "fifo"],
)
def test_t03_symlink_special_file_and_escape_blocked(tmp_path, kind):
    m, raw, metadata = fixture()
    root = tmp_path / "source"
    if kind in {"root_symlink", "ancestor_symlink"}:
        write_fixture(root, m, raw, metadata)
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        if kind == "root_symlink":
            root = alias
        else:
            child = root / "child"
            child.mkdir()
            root = alias / "child"
    else:
        root.mkdir()
        if kind == "manifest_symlink":
            (root / m.raw.relative_path).write_bytes(raw)
        else:
            (root / "manifest.json").write_bytes(manifest_bytes(m))
        target = root / ("manifest.json" if kind == "manifest_symlink" else m.raw.relative_path)
        if kind.endswith("symlink"):
            outside = tmp_path / "synthetic-outside"
            outside.write_bytes(manifest_bytes(m) if kind == "manifest_symlink" else raw)
            target.symlink_to(outside)
        elif kind == "directory":
            target.mkdir()
        else:
            os.mkfifo(target)
    result = inspect_offline_source(root)
    assert result.disposition == "SOURCE_INTEGRITY_FAILURE"


def test_t03_size_bound_and_report_zip_role_rejection():
    with pytest.raises(ContractError):
        FilePin("source.csv", MAX_RAW_BYTES + 1, "0" * 64)
    m, raw, metadata = fixture()
    result = validate_source_manifest(
        replace(m, raw=replace(m.raw, relative_path="result.zip")), raw, metadata
    )
    assert result.disposition == "SOURCE_INTEGRITY_FAILURE"


@pytest.mark.parametrize(
    "fault",
    ["UNKNOWN", "RESTRICTED", "COMMERCIAL", "NO_TERMS", "URL_ONLY", "WRONG_COVERAGE", "NO_ORIGIN"],
)
def test_t04_rights_not_inferred_from_dataset_link(fault):
    m, raw, metadata = fixture()
    rights = m.rights
    if fault in {"UNKNOWN", "RESTRICTED"}:
        rights = replace(rights, status=fault)
    elif fault == "COMMERCIAL":
        rights = replace(rights, allowed_uses=("COMMERCIAL_REUSE",))
    elif fault == "NO_TERMS":
        rights = replace(rights, terms_ref=None)
    elif fault == "URL_ONLY":
        rights = replace(rights, evidence_text="https://data.gov.tw/dataset/18420")
    elif fault == "WRONG_COVERAGE":
        rights = replace(rights, covered_paths=("unrelated.csv",))
    else:
        rights = replace(rights, origin_ref=None)
    result = validate_source_manifest(replace(m, rights=rights), raw, metadata)
    assert result.disposition == "SOURCE_RESTRICTED_OR_RIGHTS_UNRESOLVED"
    assert extract_monthly_rows(result).state == "NOT_EVALUATED"


@pytest.mark.parametrize(
    "body", [b'{"a":1,"a":2}', b'{"a":1.5}', b'{"a":NaN}', b"[]", b"{", b"\xff"]
)
def test_t04_manifest_duplicate_keys_invalid_types_fail_closed(body):
    with pytest.raises(ContractError):
        decode_manifest(body)


def test_t05_t07_bom_crlf_multiline_quote_tokens_original_identity():
    rows = [
        ("2099/12/31", f"2025{m:02d}", "0007", str(m), 'SYNTHETIC "quoted", name', "line1\r\nline2")
        for m in (4, 5, 6)
    ]
    raw = csv_bytes(rows, bom=True)
    value = intake(raw=raw, encoding="UTF8_BOM")
    parsed = extract_monthly_rows(value)
    assert parsed.state == "EXTRACTED" and value.raw_bytes == raw
    assert parsed.rows[0].headers == HEADERS
    assert parsed.rows[0].source_fields[4] == 'SYNTHETIC "quoted", name'
    assert parsed.rows[0].source_tokens[4] == '"SYNTHETIC ""quoted"", name"'
    assert parsed.rows[0].source_fields[5] == "line1\r\nline2"
    assert tuple(row.row_ordinal for row in parsed.rows) == (1, 2, 3)
    assert all(
        row.raw_sha256 == sha256(raw).hexdigest() and isinstance(row.exact_byte_span, NotEvaluated)
        for row in parsed.rows
    )


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_header",
        "missing_header",
        "missing_field",
        "extra_field",
        "bare_quote",
        "unclosed_quote",
        "after_quote",
        "bare_cr",
        "empty",
        "invalid_utf8",
        "bom_mismatch",
    ],
)
def test_t06_malformed_csv_no_favorable_partial_parse(fault):
    raw = csv_bytes()
    headers = HEADERS
    if fault == "duplicate_header":
        headers = (*HEADERS, HEADERS[0])
        raw = csv_bytes(headers=headers)
    elif fault == "missing_header":
        headers = HEADERS[1:]
        raw = csv_bytes(headers=headers)
    elif fault == "missing_field":
        raw = csv_bytes(rows=[("20250701", "202504", "0007")])
    elif fault == "extra_field":
        raw = csv_bytes(rows=[("20250701", "202504", "0007", "1", "SYNTHETIC", "NOTE", "EXTRA")])
    elif fault == "bare_quote":
        raw += b'bad"quote\n'
    elif fault == "unclosed_quote":
        raw += b'"unfinished'
    elif fault == "after_quote":
        raw += b'"closed"garbage\n'
    elif fault == "bare_cr":
        raw = raw.replace(b"\r\n", b"\r")
    elif fault == "empty":
        raw = b""
    elif fault == "invalid_utf8":
        raw += b"\xff"
    else:
        raw = b"\xef\xbb\xbf" + raw
    assert extract_monthly_rows(intake(raw=raw, headers=headers)).state == "REJECTED"


@pytest.mark.parametrize(
    "year,quarter,periods,policy",
    [
        (2024, 1, ("202401", "202402", "202403"), "CE_YYYYMM-v0.1"),
        (2024, 4, ("202410", "202411", "202412"), "CE_YYYYMM-v0.1"),
        (2025, 2, ("11404", "11405", "11406"), "ROC_YYYMM_PLUS_1911-v0.1"),
    ],
)
def test_t08_string_company_calendar_and_explicit_roc(year, quarter, periods, policy):
    raw = csv_bytes(rows=[("label", p, "0007", "-1", "SYNTHETIC", "NOTE") for p in periods])
    result = extract_monthly_rows(intake(raw=raw, year=year, quarter=quarter, period_policy=policy))
    assert result.state == "EXTRACTED" and result.rows[0].company_code == "0007"
    if year == 2024 and quarter == 1:
        assert result.rows[1].reference_period[1] == date(2024, 2, 29)
    assert result.rows[-1].reference_period[1].year == year


@pytest.mark.parametrize(
    "period", ["11404", "202500", "202513", "000004", "20250401", " 202504", "2025-04"]
)
def test_t08_unrecognized_period_not_guessed(period):
    raw = csv_bytes(rows=[("label", period, "0007", "1", "SYNTHETIC", "NOTE")])
    assert extract_monthly_rows(intake(raw=raw)).state == "REJECTED"


@pytest.mark.parametrize(
    "token,policy,expected",
    [
        (str(-(2**63)), "SIGNED_DECIMAL_INT64-v0.1", -(2**63)),
        (str(2**63 - 1), "SIGNED_DECIMAL_INT64-v0.1", 2**63 - 1),
        ("-1,234", "SIGNED_GROUPED_INT64-v0.1", -1234),
        ("0", "SIGNED_DECIMAL_INT64-v0.1", 0),
    ],
)
def test_t09_integer_policy_preserves_source_text(token, policy, expected):
    rows = [("label", f"2025{m:02d}", "0007", token, "SYNTHETIC", "NOTE") for m in (4, 5, 6)]
    result = extract_monthly_rows(intake(raw=csv_bytes(rows), integer_policy=policy))
    assert result.state == "EXTRACTED"
    assert result.rows[0].amount == expected and result.rows[0].source_amount_text == token


@pytest.mark.parametrize(
    "token",
    ["1.0", "1e3", "1,234", "1 234", "+1", " 1", "1 ", "01", "True", str(2**63), str(-(2**63) - 1)],
)
def test_t09_no_numeric_coercion(token):
    raw = csv_bytes(
        rows=[("label", f"2025{m:02d}", "0007", token, "SYNTHETIC", "NOTE") for m in (4, 5, 6)]
    )
    assert extract_monthly_rows(intake(raw=raw)).state == "REJECTED"


@pytest.mark.parametrize("token", ["", "NA", "N/A", "null", "-"])
def test_t09_unknown_is_not_zero(token):
    raw = csv_bytes(
        rows=[("label", f"2025{m:02d}", "0007", token, "SYNTHETIC", "NOTE") for m in (4, 5, 6)]
    )
    result = extract_monthly_rows(intake(raw=raw))
    assert result.state == "UNRESOLVED" and all(
        isinstance(row.amount, NotEvaluated) for row in result.rows
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"canonical_unit": "UNKNOWN"},
        {"basis_ref": "UNKNOWN"},
        {"reporting_scope": "UNKNOWN"},
        {"metric": "Revenue"},
        {"issuer_code": "7"},
        {"support_class": "HEADER_GUESS"},
        {"applies_to_raw_sha256": "0" * 64},
        {
            "source_columns": {
                "company_code": "公司代號",
                "reference_period": "資料年月",
                "source_amount": "備註",
            }
        },
    ],
)
def test_t09_semantic_mapping_needs_separate_pinned_applicable_support(updates):
    value = intake(mapped=True, support_updates=updates)
    assessment = assess_mapping(value, extract_monthly_rows(value))
    assert assessment.state == "REJECTED"


def test_t09_no_header_defaults_and_conditional_mapping():
    value = intake()
    assert assess_mapping(value, extract_monthly_rows(value)).state == "UNRESOLVED"
    supported = intake(mapped=True)
    mapped = assess_mapping(supported, extract_monthly_rows(supported))
    assert mapped.state == "MAPPED" and "NOT_ISSUER_AUTHENTICATION" in mapped.scope


@pytest.mark.parametrize(
    "kind",
    ["same_duplicate", "contradictory_duplicate", "other_company", "cross_quarter", "gapped"],
)
def test_t10_no_last_or_latest_row_winner(kind):
    rows = [("label", f"2025{m:02d}", "0007", "1", "SYNTHETIC", "NOTE") for m in (4, 5, 6)]
    if kind == "same_duplicate":
        rows.append(rows[0])
    elif kind == "contradictory_duplicate":
        rows.append(("later label", "202504", "0007", "999", "SYNTHETIC", "NOTE"))
    elif kind == "other_company":
        rows[1] = ("label", "202505", "7", "1", "SYNTHETIC", "NOTE")
    elif kind == "cross_quarter":
        rows[1] = ("label", "202507", "0007", "1", "SYNTHETIC", "NOTE")
    else:
        rows.pop(1)
    parsed = extract_monthly_rows(intake(raw=csv_bytes(rows)))
    assert parsed.state == ("UNRESOLVED" if kind == "gapped" else "REJECTED")


@pytest.mark.parametrize("mode", ["public", "prospective_observed"])
@pytest.mark.parametrize("cutoff", ["2025-07-07T00:00:00+08:00", "2025-07-14T00:00:00+08:00"])
def test_t11_t14_dates_and_capture_claims_never_supply_owner_time(code, mode, cutoff):
    value = intake(
        mapped=True,
        acquisition_text="2020-01-01T00:00:00+08:00",
        source_metadata_claims=(("capture", "2020-01-01"), ("publication", "2020-01-01")),
    )
    result = evaluate_offline_replay(value, context(code, value, mode=mode, cutoff=cutoff), code)
    assert result.disposition == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"
    assert all(s.state != "SUPPORTED" for s in result.stages)
    stopped(result)


def test_t12_original_and_generated_hashes_and_schemas_are_distinct(code):
    value = intake(mapped=True)
    result = evaluate_offline_replay(value, context(code, value), code)
    assert len(result.projections) == 3
    for projection in result.projections:
        assert projection.original.sha256 == sha256(value.raw_bytes).hexdigest()
        assert projection.projection_sha256 == sha256(projection.projection_bytes).hexdigest()
        assert projection.projection_sha256 != projection.original.sha256
        assert projection.representation_kind == "ADAPTER_GENERATED_PROJECTION"
        body = json.loads(projection.projection_bytes)
        assert body["projection_schema"] == "a06-extracted-row-v0.1"
        assert "issuer_publication" not in projection.projection_bytes.decode()
    stopped(result)


@pytest.mark.parametrize(
    "source_class",
    ["GOVERNMENT_AGGREGATE", "EXCHANGE_AGGREGATE", "THIRD_PARTY", "UNKNOWN", "ISSUER_ORIGINAL"],
)
def test_t13_no_source_class_or_issuer_label_magic(code, source_class):
    value = intake(mapped=True, source_class=source_class)
    result = evaluate_offline_replay(value, context(code, value), code)
    assert result.disposition == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"
    stopped(result)


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"third": "conflict"}, "UNRESOLVED"),
        ({"check_status": "FAILED"}, "OPERATIONAL_ERROR"),
        ({"third": "absent"}, "NOT_COMPUTABLE"),
    ],
)
def test_t15_actual_prior_owner_failures_stay_distinct_from_adapter_nonexecution(
    code, kwargs, expected
):
    spec, sum_spec, slots = ratio_inputs(code.upstream_a05, **kwargs)
    prior = evaluate_ratio(spec, sum_spec, slots, code.upstream_a05)
    value = intake()
    result = evaluate_offline_replay(value, context(code, value), code)
    assert prior.outcome.state == expected
    assert result.disposition == "MAPPING_UNRESOLVED"
    assert prior.outcome.state == expected
    stopped(result)  # No owner outcome invented from absence of external proof.


@pytest.mark.parametrize(
    "claim", ["publication_proof", "fragment", "content_version", "revision", "coverage_COMPLETED"]
)
def test_t16_impostor_metadata_cannot_force_transport_or_selection(code, claim):
    value = intake(mapped=True, source_metadata_claims=((claim, "SYNTHETIC_IMPOSTOR_CLAIM"),))
    result = evaluate_offline_replay(value, context(code, value), code)
    assert result.disposition == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"
    stopped(result)


def test_t16_forged_gate_and_extraction_results_rechecked(code):
    value = intake()
    forged = replace(value, raw_bytes=value.raw_bytes + b"tamper")
    result = evaluate_offline_replay(forged, context(code, forged), code)
    assert (
        result.disposition == "CONTRACT_VIOLATION"
        and result.reason == "INTAKE_RESULT_TRANSPORT_MISMATCH"
    )
    parsed = extract_monthly_rows(value)
    assert assess_mapping(value, replace(parsed, rows=())).state == "UNRESOLVED"


def test_t17_deterministic_replay_new_source_and_context_binding(code):
    first = intake(mapped=True)
    old_context = context(code, first)
    old = evaluate_offline_replay(first, old_context, code)
    assert old == evaluate_offline_replay(first, old_context, code)
    new = intake(
        mapped=True,
        raw=csv_bytes(
            rows=[("label", f"2025{m:02d}", "0007", "999", "SYNTHETIC", "NOTE") for m in (4, 5, 6)]
        ),
    )
    wrong = evaluate_offline_replay(new, old_context, code)
    assert wrong.reason == "CONTEXT_SOURCE_SNAPSHOT_MISMATCH"
    corrected = evaluate_offline_replay(new, context(code, new), code)
    assert corrected.research_ref != old.research_ref
    assert old == evaluate_offline_replay(first, old_context, code)
    stopped(corrected)


def test_t18_strict_preview_never_serializes_rights_custody_future_or_values(code):
    original = intake(mapped=True)
    m = replace(
        original.manifest,
        source_metadata_claims=(("future_revision", "PRIVATE-TRUTH"),),
        acquisition_text="PRIVATE-CUSTODY",
        rights=replace(original.manifest.rights, evidence_text="PRIVATE-RIGHTS-NOTE"),
    )
    changed = validate_source_manifest(m, original.raw_bytes, original.mapping_bytes)
    one = evaluate_offline_replay(original, context(code, original), code)
    two = evaluate_offline_replay(changed, context(code, changed), code)
    assert one.diagnostic_preview_bytes == two.diagnostic_preview_bytes
    preview = json.loads(one.diagnostic_preview_bytes)
    assert set(preview) == {
        "preview_kind",
        "cutoff",
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
        "0007",
        "SYNTHETIC_TEST_ONLY",
        "source_metadata",
        "right",
        "custody",
        "publication",
        "proof",
        "raw_sha256",
        "future_revision",
    ):
        assert marker not in two.diagnostic_preview_bytes.decode()
    with pytest.raises(ValueError):
        replace(one, admission_eligible=True)
    with pytest.raises(FrozenInstanceError):
        one.trust = "TRUSTED"


def test_t19_pure_manifest_parse_mapping_replay_resource_denial(code, monkeypatch):
    value = intake(mapped=True)
    ctx = context(code, value)

    def denied(*args, **kwargs):
        raise AssertionError("unexpected resource call in pure adapter")

    for obj, attr in (
        (builtins, "open"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (os, "open"),
        (os, "stat"),
        (subprocess, "check_output"),
        (socket, "socket"),
    ):
        monkeypatch.setattr(obj, attr, denied)
    result = evaluate_offline_replay(value, ctx, code)
    assert result.disposition == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"


def test_t19_ast_and_explicit_fifteen_hash_observation(code):
    assert len(code.upstream_a05.upstream_a04.observed_working_files) == 10
    assert len(code.upstream_a05.extension_pins) == 2 and len(code.extension_pins) == 3
    for pin, n in zip(code.extension_pins, code.extension_byte_lengths, strict=True):
        body = (ROOT / pin.path).read_bytes()
        assert sha256(body).hexdigest() == pin.sha256 and len(body) == n
    for path in A06_CODE_PATHS:
        tree = ast.parse((ROOT / path).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(
            any(
                word in name
                for word in (
                    "tests",
                    "oracle",
                    "acceptance",
                    "requests",
                    "urllib",
                    "psycopg",
                    "sqlalchemy",
                )
            )
            for name in imports
        )
        assert not any(
            isinstance(n, ast.Attribute) and n.attr in {"now", "today", "utcnow"}
            for n in ast.walk(tree)
        )


def test_t19_code_shape_failure_no_owner_admission(code):
    value = intake(mapped=True)
    broken = replace(code, extension_pins=code.extension_pins[:-1])
    result = evaluate_offline_replay(value, context(code, value), broken)
    assert result.disposition == "CONTRACT_VIOLATION"
    stopped(result)
