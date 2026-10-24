"""SYNTHETIC_TEST_ONLY CSV/permission/metadata; no real issuer or source proof."""

import csv
import io
import json
from dataclasses import asdict, replace
from hashlib import sha256

from a03_inputs import seed

from pit_research_lab.domain.source_adapter import CSV_PROFILE, REQUIRED_HEADERS
from pit_research_lab.domain.source_intake import (
    FilePin,
    OfflineSourceManifest,
    RightsRecord,
    snapshot_ref_for,
    validate_source_manifest,
)

HEADERS = (*REQUIRED_HEADERS, "公司名稱", "備註")


def csv_bytes(rows=None, *, headers=HEADERS, bom=False, newline="\r\n"):
    if rows is None:
        rows = [
            (
                "2099/12/31",
                f"2025{m:02d}",
                "0007",
                str(m * 100),
                "SYNTHETIC_TEST_ONLY",
                "SYNTHETIC_TEST_ONLY",
            )
            for m in (4, 5, 6)
        ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator=newline)
    writer.writerow(headers)
    writer.writerows(rows)
    return (b"\xef\xbb\xbf" if bom else b"") + stream.getvalue().encode("utf-8")


def fixture(raw=None, *, mapped=False, support_updates=None, **changes):
    raw = csv_bytes() if raw is None else raw
    raw_pin = FilePin("revenue.csv", len(raw), sha256(raw).hexdigest())
    mapping = None
    mapping_pin = None
    if mapped:
        body = {
            "mapping_schema": "a06-field-mapping-v0.1",
            "source_columns": {
                "company_code": "公司代號",
                "reference_period": "資料年月",
                "source_amount": "營業收入-當月營收",
            },
            "applies_to_raw_sha256": raw_pin.sha256,
            "evidence_origin": "SYNTHETIC_TEST_ONLY independent metadata fixture",
            "evidence_text": "SYNTHETIC_TEST_ONLY definition of fixture fields, not real issuer evidence",
            "support_class": "SYNTHETIC_TEST_ONLY",
            "issuer_code": "0007",
            "issuer_ref": "SYNTHETIC_TEST_ONLY_ISSUER",
            "metric": "net_operating_revenue",
            "period_kind": "DURATION",
            "reporting_scope": "consolidated",
            "basis_ref": "BASIS-CONSOLIDATED-V1",
            "currency": "NTD",
            "canonical_unit": "NTD_thousands",
        }
        body.update(support_updates or {})
        mapping = json.dumps(body, ensure_ascii=False, sort_keys=True).encode()
        mapping_pin = FilePin("mapping.json", len(mapping), sha256(mapping).hexdigest())
    paths = (raw_pin.relative_path,) + ((mapping_pin.relative_path,) if mapping_pin else ())
    rights = RightsRecord(
        "PERMITTED",
        ("OFFLINE_RESEARCH",),
        paths,
        "SYNTHETIC_TEST_ONLY generated data",
        "SYNTHETIC_TEST_ONLY author",
        "SYNTHETIC_TEST_ONLY generated test fixture permission",
        "SYNTHETIC_TEST_ONLY owner declaration",
    )
    manifest = OfflineSourceManifest(
        bundle_ref="SYNTHETIC-TEST-A06",
        snapshot_ref=snapshot_ref_for(raw_pin.sha256, mapping_pin.sha256 if mapping_pin else None),
        data_classification="SYNTHETIC_TEST_ONLY",
        source_class="GOVERNMENT_AGGREGATE",
        source_title="SYNTHETIC_TEST_ONLY CSV",
        publisher="SYNTHETIC_TEST_ONLY publisher",
        retriever="SYNTHETIC_TEST_ONLY retriever",
        dataset_page_url=None,
        resource_url=None,
        raw=raw_pin,
        mapping_file=mapping_pin,
        rights=rights,
        custody_ref="SYNTHETIC_TEST_ONLY custody",
        acquisition_text=None,
        acquisition_origin="SYNTHETIC_TEST_ONLY metadata",
        acquisition_reliability="OWNER_DECLARED",
        csv_profile=CSV_PROFILE,
        encoding="UTF8",
        headers=HEADERS,
        period_policy="CE_YYYYMM-v0.1",
        integer_policy="SIGNED_DECIMAL_INT64-v0.1",
        company_code="0007",
        year=2025,
        quarter=2,
        source_metadata_claims=(),
    )
    manifest = replace(manifest, **changes)
    return manifest, raw, mapping


def intake(**kwargs):
    manifest, raw, mapping = fixture(**kwargs)
    return validate_source_manifest(manifest, raw, mapping)


def manifest_bytes(manifest):
    body = asdict(manifest)
    body.pop("schema_version")
    for name in ("raw", "mapping_file", "rights"):
        if body[name] is not None:
            body[name].pop("schema_version")
    body["source_metadata_claims"] = dict(manifest.source_metadata_claims)
    return json.dumps(body, sort_keys=True, ensure_ascii=False).encode()


def write_fixture(root, manifest, raw, mapping):
    root.mkdir()
    (root / "manifest.json").write_bytes(manifest_bytes(manifest))
    (root / manifest.raw.relative_path).write_bytes(raw)
    if mapping is not None:
        (root / manifest.mapping_file.relative_path).write_bytes(mapping)


def context(code, source, *, cutoff="2025-07-07T00:00:00+08:00", mode="public"):
    bundle, _ = seed(code.upstream_a05.upstream_a04)
    snapshot = (
        source.manifest.snapshot_ref
        if isinstance(source.manifest, OfflineSourceManifest)
        else "NO-SUPPLIED-SOURCE"
    )
    return replace(
        bundle.context,
        context_ref="A06-SYNTHETIC-" + cutoff + "-" + mode,
        evidence_set_ref=snapshot,
        mode=mode,
        information_cutoff=replace(bundle.context.information_cutoff, source_text=cutoff),
    )
