"""SYNTHETIC_TEST_ONLY full-market fixtures, unrelated to original source rows."""

import csv
import io
import json
from dataclasses import asdict, replace
from hashlib import sha256

from pit_research_lab.domain.contracts import (
    SCHEMA,
    AwareInstant,
    CandidateProfile,
    FieldOrigin,
    NotEvaluated,
    OriginKnownValue,
    SemanticContext,
    Unknown,
    UnknownCause,
    Visibility,
)
from pit_research_lab.domain.market_row_selection import HEADERS, FullMarketSelectionSpec
from pit_research_lab.domain.market_source_slice import IC1SourceInput
from pit_research_lab.domain.source_adapter import CSV_PROFILE
from pit_research_lab.domain.source_intake import (
    FilePin,
    OfflineSourceManifest,
    RightsRecord,
    snapshot_ref_for,
    validate_source_manifest,
)


def row(company="0007", amount="321", month="11509", note="SYNTHETIC_TEST_ONLY"):
    return (
        "SYNTHETIC_TABLE_DATE",
        month,
        company,
        "SYNTHETIC_TEST_ONLY",
        "SYNTHETIC_TEST_ONLY",
        amount,
        "PRIOR_MONTH_CONTEXT_ONLY",
        "PRIOR_YEAR_CONTEXT_ONLY",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        note,
    )


def csv_bytes(rows=None, headers=HEADERS, bom=True):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows([row("0010", "not-an-integer"), row(), row("0090")] if rows is None else rows)
    return (b"\xef\xbb\xbf" if bom else b"") + stream.getvalue().encode()


def pin(name, body):
    return FilePin(name, len(body), sha256(body).hexdigest())


def fixture(raw=None, mapping_updates=None, **changes):
    raw = csv_bytes() if raw is None else raw
    rp = pin("market.csv", raw)
    mapping = None
    mp = None
    if mapping_updates is not None:
        body = {
            "mapping_schema": "a06-field-mapping-v0.1",
            "applies_to_raw_sha256": rp.sha256,
            "source_columns": {
                "company_code": "公司代號",
                "reference_period": "資料年月",
                "source_amount": "營業收入-當月營收",
            },
            "support_class": "SYNTHETIC_TEST_ONLY",
            "evidence_origin": "SYNTHETIC_TEST_ONLY",
            "evidence_text": "SYNTHETIC_TEST_ONLY metadata",
            "issuer_ref": "SYNTHETIC_ONLY",
            "issuer_code": "0007",
            "metric": "net_operating_revenue",
            "period_kind": "DURATION",
            "reporting_scope": "consolidated",
            "basis_ref": "BASIS-CONSOLIDATED-V1",
            "currency": "NTD",
            "canonical_unit": "NTD_thousands",
        }
        body.update(mapping_updates)
        mapping = json.dumps(body, ensure_ascii=False).encode()
        mp = pin("mapping.json", mapping)
    rights = RightsRecord(
        "PERMITTED",
        ("OFFLINE_RESEARCH",),
        (rp.relative_path,) + ((mp.relative_path,) if mp else ()),
        "SYNTHETIC_TEST_ONLY terms",
        "SYNTHETIC_TEST_ONLY attribution",
        "SYNTHETIC_TEST_ONLY generated fixture permission",
        "SYNTHETIC_TEST_ONLY origin",
    )
    m = OfflineSourceManifest(
        "IC1-SYNTHETIC-ONLY",
        snapshot_ref_for(rp.sha256, mp.sha256 if mp else None),
        "SYNTHETIC_TEST_ONLY",
        "GOVERNMENT_AGGREGATE",
        "SYNTHETIC_TEST_ONLY market",
        None,
        None,
        None,
        None,
        rp,
        mp,
        rights,
        "SYNTHETIC_TEST_ONLY custody",
        "SYNTHETIC_ACQUISITION_TIME",
        "SYNTHETIC_TEST_ONLY",
        "OWNER_DECLARED",
        CSV_PROFILE,
        "UTF8_BOM",
        HEADERS,
        "ROC_YYYMM_PLUS_1911-v0.1",
        "SIGNED_DECIMAL_INT64-v0.1",
        "0007",
        2026,
        3,
        (),
    )
    return replace(m, **changes), raw, mapping


def source(**kwargs):
    m, raw, mapping = fixture(**kwargs)
    notes = b"SYNTHETIC_TEST_ONLY audit notes"
    return IC1SourceInput(validate_source_manifest(m, raw, mapping), pin("notes.txt", notes), notes)


def spec(**kwargs):
    return FullMarketSelectionSpec(company_code="0007", **kwargs)


def manifest_bytes(m):
    body = asdict(m)
    body.pop("schema_version")
    for name in ("raw", "mapping_file", "rights"):
        if body[name] is not None:
            body[name].pop("schema_version")
    body["source_metadata_claims"] = dict(m.source_metadata_claims)
    return json.dumps(body, ensure_ascii=False).encode()


def write_source(root, m, raw, mapping):
    root.mkdir()
    (root / "manifest.json").write_bytes(manifest_bytes(m))
    (root / m.raw.relative_path).write_bytes(raw)
    if mapping is not None:
        (root / m.mapping_file.relative_path).write_bytes(mapping)
    notes = b"SYNTHETIC_TEST_ONLY audit notes"
    (root / "notes.txt").write_bytes(notes)
    return pin("notes.txt", notes)


def context(code, intake, mode="public", cutoff="2025-07-07T00:00:00+08:00"):
    # Both sample historical cutoffs are synthetic, never real-source availability claims.
    o = FieldOrigin(
        Visibility.CALLER,
        "/ic1_synthetic",
        OriginKnownValue("SYNTHETIC_ONLY"),
        OriginKnownValue("SYNTHETIC_TEST_ONLY"),
        OriginKnownValue("0" * 64),
    )
    profile = CandidateProfile(
        SCHEMA,
        "wu01-unit-v0.1-CANDIDATE",
        "wu01-reasons-v0.1-CANDIDATE",
        "s1-information-v0.1-CANDIDATE",
        code.upstream_a06.upstream_a05.upstream_a04.observed_working_files,
        o,
    )
    return SemanticContext(
        "IC1-SYNTHETIC-CONTEXT",
        AwareInstant(cutoff, "Asia/Taipei", "+08:00", "SECOND", o),
        mode,
        "SYNTHETIC_ONLY",
        intake.manifest.snapshot_ref,
        "SYNTHETIC-CALENDAR",
        (),
        "NUM-1",
        profile,
        (),
        Unknown(UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, o),
        "SYNTHETIC-SPEC",
        (),
        NotEvaluated("S2", "SYNTHETIC_ONLY"),
        o,
    )
