"""SYNTHETIC_TEST_ONLY invented issuer and financial evidence, never UMC content."""

import csv
import io
import json
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

from pit_research_lab.domain.financial_semantics import (
    SupportInput,
    binding_for,
    binding_json,
)
from pit_research_lab.domain.market_row_selection import (
    HEADERS,
    FullMarketSelectionSpec,
    select_market_row,
)
from pit_research_lab.domain.source_intake import (
    FilePin,
    OfflineSourceManifest,
    RightsRecord,
    snapshot_ref_for,
    validate_source_manifest,
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode()


def pin(name, body):
    return {"relative_path": name, "byte_length": len(body), "sha256": sha256(body).hexdigest()}


def source(amount="321", foreign="FOREIGN_CONTEXT", reverse=False):
    def row(code, value):
        return [
            "SYNTHETIC_TABLE_DATE",
            "11509",
            code,
            "SYNTHETIC_TEST_ONLY",
            "SYNTHETIC",
            value,
        ] + ["CONTEXT_ONLY"] * 8

    rows = [row("9999", foreign), row("0007", amount)]
    if reverse:
        rows.reverse()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(HEADERS)
    writer.writerows(rows)
    raw = b"\xef\xbb\xbf" + stream.getvalue().encode()
    raw_pin = FilePin(**pin("market.csv", raw))
    manifest = OfflineSourceManifest(
        "IC3-SYNTHETIC-ONLY",
        snapshot_ref_for(raw_pin.sha256, None),
        "SYNTHETIC_TEST_ONLY",
        "GOVERNMENT_AGGREGATE",
        "SYNTHETIC_TEST_ONLY",
        None,
        None,
        None,
        None,
        raw_pin,
        None,
        RightsRecord(
            "PERMITTED",
            ("OFFLINE_RESEARCH",),
            ("market.csv",),
            "SYNTHETIC_TEST_ONLY terms",
            "SYNTHETIC_TEST_ONLY attribution",
            "SYNTHETIC_TEST_ONLY invented source permission",
            "SYNTHETIC_TEST_ONLY",
        ),
        "SYNTHETIC_CUSTODY",
        "SYNTHETIC_NON_PIT_ACQUISITION",
        "SYNTHETIC_TEST_ONLY",
        "OWNER_DECLARED",
        "A06_MONTHLY_REVENUE_CSV-v0.1",
        "UTF8_BOM",
        HEADERS,
        "ROC_YYYMM_PLUS_1911-v0.1",
        "SIGNED_DECIMAL_INT64-v0.1",
        "0007",
        2026,
        3,
        (),
    )
    intake = validate_source_manifest(manifest, raw, None)
    spec = FullMarketSelectionSpec(company_code="0007", expected_record_count=2)
    selected = select_market_row(intake, spec).selected
    return intake, spec, selected


def excerpt(**changes):
    values = {
        "issuer": "SYNTHETIC_TEST_ONLY Corporation",
        "company": "0007",
        "month": "2026-09",
        "assurance": "unaudited",
        "measurement": "monthly",
        "metric": "net sales",
        "amount": "321",
        "unit": "thousands",
        "currency": "New Taiwan Dollars",
        "scope": "consolidated",
    }
    values.update(changes)
    quotes = {
        "identity": "{issuer} (TWSE: {company})".format(**values),
        "sales": "{month} {assurance} {measurement} {metric}: {amount}".format(**values),
        "unit": "All figures are in {unit} of {currency}.".format(**values),
        "scope": "All figures are {scope}.".format(**values),
    }
    body = ("SYNTHETIC_TEST_ONLY\n" + "\n".join(quotes.values())).encode()
    return body, quotes


def evidence(
    name, body, quotes=None, role="ISSUER_AUTHORED_DISTRIBUTOR", statement="SYNTHETIC_RELEASE_1"
):
    origin = "SYNTHETIC_TEST_ONLY:" + name
    return {
        "file": pin(name, body),
        "role": role,
        "issuer_origin_ref": "SYNTHETIC_ISSUER_0007",
        "statement_ref": statement,
        "acquisition_origin": origin,
        "acquisition_text": "2099-10-23 SYNTHETIC_NON_PIT",
        "rights": {
            "status": "PERMITTED",
            "allowed_uses": ["OFFLINE_RESEARCH"],
            "covered_sha256": sha256(body).hexdigest(),
            "source_ref": origin,
            "terms_ref": "SYNTHETIC_TEST_ONLY self-created permission",
            "attribution": "SYNTHETIC_TEST_ONLY author",
            "evidence_text": "SYNTHETIC_TEST_ONLY generated fixture with scoped permission",
            "approval_ref": "SYNTHETIC_TEST_ONLY_APPROVAL",
        },
        "profile": "IC3-OWNER-SEMANTIC-CROSSWALK-v0.1"
        if role == "LOCAL_SEMANTIC_POLICY"
        else "IC3-LOCATED-MONTHLY-EXCERPT-v0.1",
        "locators": quotes or {},
    }


def bundle(selected=None, with_policy=True, statements=None):
    if selected is None:
        selected = source()[2]
    statements = [excerpt()] if statements is None else statements
    entries, bodies = [], []
    for number, (body, quotes) in enumerate(statements):
        name = f"issuer{number}.txt"
        entries.append(evidence(name, body, quotes))
        bodies.append((name, body))
    binding = binding_json(binding_for(selected))
    data = {
        "support_schema": "IC3-SUPPORT-BUNDLE-v0.1",
        "classification": "SYNTHETIC_TEST_ONLY",
        "source_binding": binding,
        "issuer_name": "SYNTHETIC_TEST_ONLY Corporation",
        "evidence": entries,
        "crosswalk": None,
    }
    policy = {
        "policy_schema": "IC3-OWNER-SEMANTIC-CROSSWALK-v0.1",
        "policy_ref": "SYNTHETIC_POLICY-v0.1",
        "owner_approval_ref": "SYNTHETIC_TEST_ONLY_APPROVAL",
        "classification": "SYNTHETIC_TEST_ONLY",
        "rationale": "SYNTHETIC_TEST_ONLY owner chooses monthly unaudited consolidated net sales as research revenue; this is not audit evidence.",
        "source_binding": deepcopy(binding),
        "issuer_name": data["issuer_name"],
        "issuer_ref": "SYNTHETIC_RESEARCH_ONLY_0007",
        "support_sha256s": sorted({entry["file"]["sha256"] for entry in entries}),
        "source_metric": "unaudited monthly net sales",
        "source_assurance": "unaudited",
        "target": {
            "metric": "net_operating_revenue",
            "period_kind": "DURATION",
            "reporting_scope": "consolidated",
            "basis_ref": "BASIS-CONSOLIDATED-V1",
            "currency": "NTD",
            "canonical_unit": "NTD_thousands",
        },
        "basis_interpretation": "OWNER_GOVERNED_RESEARCH_EQUIVALENCE_NOT_AUDIT_OR_GAAP_PROOF",
    }
    if with_policy:
        body = encoded(policy)
        data["crosswalk"] = evidence("policy.json", body, role="LOCAL_SEMANTIC_POLICY")
        bodies.append(("policy.json", body))
    return data, tuple(bodies)


def supplied(data, bodies):
    return SupportInput(encoded(data), bodies)


def change_body(data, bodies, name, new_body):
    data = deepcopy(data)
    entry = (
        data["crosswalk"]
        if name == "policy.json"
        else next(e for e in data["evidence"] if e["file"]["relative_path"] == name)
    )
    entry["file"] = pin(name, new_body)
    entry["rights"]["covered_sha256"] = sha256(new_body).hexdigest()
    return data, tuple((p, new_body if p == name else b) for p, b in bodies)


def write_bundle(root, data, bodies):
    root.mkdir()
    (root / "support.json").write_bytes(encoded(data))
    for name, body in bodies:
        (root / name).write_bytes(body)
    return root


def source_changed(intake, **changes):
    return replace(intake, **changes)
