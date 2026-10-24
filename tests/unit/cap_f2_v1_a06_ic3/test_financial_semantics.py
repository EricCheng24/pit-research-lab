"""IC3-T01..T20: synthetic positives, adverse gates and preserved owner boundaries."""

import ast
import json
import os
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path

import pytest
from ic3_inputs import (
    bundle,
    change_body,
    encoded,
    excerpt,
    source,
    supplied,
    write_bundle,
)

import pit_research_lab.domain.financial_semantics_slice as reader
from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated
from pit_research_lab.domain.financial_semantics import (
    CLAIMS,
    MappingCandidate,
    SupportInput,
    assess_financial_semantics,
    decode_support,
)
from pit_research_lab.domain.financial_semantics_slice import (
    IC3_CODE_PATHS,
    evaluate_financial_semantics,
    inspect_financial_support,
)
from pit_research_lab.domain.market_row_selection import select_market_row
from pit_research_lab.domain.source_intake import snapshot_ref_for


def assess(data=None, bodies=None, src=None):
    src = source() if src is None else src
    if data is None:
        data, bodies = bundle(src[2])
    return assess_financial_semantics(*src, supplied(data, bodies))


def claim(result, number):
    return result.claims[number - 1]


@pytest.mark.parametrize(
    "name,expected",
    [
        ("source_intake.py", "c59235802a73f3285e98fbff72d5faa97e8797324bcbcf3f5e3b8cf60e48a240"),
        ("source_adapter.py", "afaec82a33bded42b567f0d1bd2305d5a823f5b965e87ca6494747fb1108c4df"),
        (
            "market_source_slice.py",
            "75d5311c199f971feacf03bb4d7dca06cbc2203322a927ff5d397f807466b4e7",
        ),
        (
            "market_row_selection.py",
            "2167b7649fd5b6051c924af146839eecdaee6e31bf8948d7d28b1d82b57440af",
        ),
    ],
)
def test_ic3_t01_preserved_public_gate_pins(name, expected):
    root = Path(__file__).resolve().parents[3]
    assert (
        sha256((root / "src/pit_research_lab/domain" / name).read_bytes()).hexdigest() == expected
    )


def test_ic3_t02_absent_input_and_isolated_missing_manifest(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("No root must cause no filesystem I/O")

    with monkeypatch.context() as m:
        m.setattr(reader, "_open_root", forbidden)
        empty = inspect_financial_support(None)
    root = tmp_path / "SYNTHETIC_TEST_ONLY_no_support"
    root.mkdir()
    missing = inspect_financial_support(root)
    for supplied_input in (empty, missing):
        result = assess_financial_semantics(*source(), supplied_input)
        assert result.support_input == "SUPPORT_INPUT_PENDING"
        assert result.mapping == "MAPPING_UNRESOLVED"
        assert isinstance(result.candidate, NotEvaluated)
        assert all(c.state == "UNRESOLVED" for c in result.claims)
    assert missing.read_attempts == ("support.json",)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "version",
        "bool_size",
        "float_size",
        "duplicate",
        "bad_utf8",
        "null",
        "array",
        "bool_amount",
        "unknown_role",
        "extra_nested",
    ],
)
def test_ic3_t03_strict_schema(mutation):
    data, bodies = bundle()
    if mutation == "extra":
        data["extra"] = "no"
    elif mutation == "version":
        data["support_schema"] = "future-v999"
    elif mutation in ("bool_size", "float_size"):
        data["evidence"][0]["file"]["byte_length"] = True if mutation == "bool_size" else 1.2
    elif mutation == "bool_amount":
        data["source_binding"]["amount"] = True
    elif mutation == "unknown_role":
        data["evidence"][0]["role"] = "AUTHENTICATED_BY_URL"
    elif mutation == "extra_nested":
        data["evidence"][0]["rights"]["signature"] = "invented"
    body = encoded(data)
    body = {
        "duplicate": b'{"support_schema":"x","support_schema":"y"}',
        "bad_utf8": b"\xff",
        "null": b"null",
        "array": b"[]",
    }.get(mutation, body)
    with pytest.raises(ContractError):
        decode_support(body)
    result = assess_financial_semantics(*source(), SupportInput(body, bodies))
    assert result.support_input == "EVIDENCE_RESTRICTED_OR_UNVERIFIED"
    assert isinstance(result.candidate, NotEvaluated)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "UNKNOWN"),
        ("status", "RESTRICTED"),
        ("status", "EXPIRED"),
        ("allowed_uses", ["REDISTRIBUTION"]),
        ("covered_sha256", "0" * 64),
        ("source_ref", "ANOTHER_PUBLISHER"),
        ("terms_ref", "https://data.gov.tw/license"),
        ("evidence_text", "https://example.invalid/license"),
        ("attribution", ""),
        ("approval_ref", ""),
    ],
)
def test_ic3_t04_rights_preflight_zero_body_reads(tmp_path, monkeypatch, field, value):
    data, bodies = bundle()
    data["evidence"][0]["rights"][field] = value
    root = write_bundle(tmp_path / "SYNTHETIC_TEST_ONLY", data, bodies)
    reads = []
    original = reader._read_relative

    def record(fd, path, limit):
        reads.append(path)
        return original(fd, path, limit)

    monkeypatch.setattr(reader, "_read_relative", record)
    inspected = inspect_financial_support(root)
    assert reads == ["support.json"]
    assert inspected.bodies == () and isinstance(inspected.manifest_bytes, NotEvaluated)
    result = assess_financial_semantics(*source(), inspected)
    assert result.support_input == "EVIDENCE_RESTRICTED_OR_UNVERIFIED"


def test_ic3_t04_later_evidence_and_policy_rights_checked_before_any_body(tmp_path):
    data, bodies = bundle(statements=[excerpt(), excerpt(amount="999")])
    data["crosswalk"]["rights"]["status"] = "RESTRICTED"
    inspected = inspect_financial_support(
        write_bundle(tmp_path / "SYNTHETIC_TEST_ONLY", data, bodies)
    )
    assert inspected.read_attempts == ("support.json",)
    assert inspected.bodies == ()


@pytest.mark.parametrize(
    "path",
    [
        "../outside.txt",
        "/tmp/body.txt",
        ".hidden",
        "a/../b",
        "a\\b",
        "a:b",
        "support.json",
        "policy.json",
    ],
)
def test_ic3_t05_invalid_paths_and_collisions(path):
    data, _ = bundle()
    data["evidence"][0]["file"]["relative_path"] = path
    with pytest.raises(ContractError):
        decode_support(encoded(data))


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        "root_symlink",
        "fifo",
        "directory",
        "oversize",
        "digest",
        "missing",
        "traversal_root",
    ],
)
def test_ic3_t05_safe_descriptor_refusals(tmp_path, kind):
    data, bodies = bundle()
    root = write_bundle(tmp_path / "SYNTHETIC_TEST_ONLY", data, bodies)
    body_path = root / "issuer0.txt"
    if kind in ("symlink", "fifo", "directory", "missing"):
        body_path.unlink()
    if kind == "symlink":
        body_path.symlink_to(root / "policy.json")
    elif kind == "root_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    elif kind == "fifo":
        os.mkfifo(body_path)
    elif kind == "directory":
        body_path.mkdir()
    elif kind == "oversize":
        body_path.write_bytes(b"x" * 65537)
    elif kind == "digest":
        body_path.write_bytes(bodies[0][1] + b"changed")
    elif kind == "traversal_root":
        root = root / ".." / root.name
    result = inspect_financial_support(root)
    assert result.reason != "SUPPORT_BYTES_READ_NOT_ADJUDICATED"
    assert result.bodies == ()
    assert isinstance(result.manifest_bytes, NotEvaluated)


def test_ic3_t05_successful_guarded_read(tmp_path):
    data, bodies = bundle()
    inspected = inspect_financial_support(
        write_bundle(tmp_path / "SYNTHETIC_TEST_ONLY", data, bodies)
    )
    result = assess_financial_semantics(*source(), inspected)
    assert inspected.read_attempts == ("support.json", "issuer0.txt", "policy.json")
    assert result.mapping == "MAPPING_CANDIDATE_PREPARED"
    assert all(c.state == "SUPPORTED" for c in result.claims)


@pytest.mark.parametrize(
    "mutation", ["raw", "ordinal", "company", "month", "amount", "lexeme", "view", "column"]
)
def test_ic3_t06_forged_selection_is_recomputed(mutation):
    intake, spec, selected = source()
    data, bodies = bundle(selected)
    if mutation == "raw":
        intake = replace(intake, raw_bytes=intake.raw_bytes + b" ")
    elif mutation == "view":
        selected = replace(selected, view=replace(selected.view, projection_sha256="0" * 64))
    else:
        fields = {
            "ordinal": {"row_ordinal": 267},
            "company": {"company_code": "2303"},
            "month": {"reference_period": (selected.extracted.reference_period[1],) * 2},
            "amount": {"amount": 322},
            "lexeme": {
                "source_tokens": selected.extracted.source_tokens[:5]
                + ("321",)
                + selected.extracted.source_tokens[6:]
            },
            "column": {"headers": tuple(reversed(selected.extracted.headers))},
        }
        selected = replace(selected, extracted=replace(selected.extracted, **fields[mutation]))
    result = assess_financial_semantics(intake, spec, selected, supplied(data, bodies))
    assert result.reason == "SOURCE_SELECTION_BINDING_REJECTED"
    assert isinstance(result.selected, NotEvaluated)
    assert isinstance(result.candidate, NotEvaluated)


@pytest.mark.parametrize(
    "field,value",
    [
        ("row_ordinal", 267),
        ("column_index", 6),
        ("column_name", "營業收入-上月營收"),
        ("company_code", "2303"),
        ("reference_month", "2026-08"),
        ("amount_lexeme", "000321"),
        ("amount", 322),
        ("view_sha256", "0" * 64),
    ],
)
def test_ic3_t06_support_binding_cannot_retarget_selected_row(field, value):
    data, bodies = bundle()
    data["source_binding"][field] = value
    assert assess(data, bodies).reason == "SUPPORT_SOURCE_BINDING_MISMATCH"


@pytest.mark.parametrize(
    "changes,number,field",
    [
        ({"company": "9999"}, 1, "issuer_code"),
        ({"issuer": "SYNTHETIC_TEST_ONLY Other Issuer"}, 1, "issuer_name"),
        ({"month": "2026-08"}, 2, "month"),
        ({"amount": "322"}, 3, "amount"),
        ({"metric": "gross sales"}, 2, "metric"),
        ({"currency": "US Dollars"}, 4, "currency"),
        ({"unit": "units"}, 5, "magnitude"),
        ({"unit": "millions"}, 5, "magnitude"),
        ({"scope": "standalone"}, 6, "scope"),
        ({"scope": "separate"}, 6, "scope"),
        ({"assurance": "audited"}, 6, "assurance"),
        ({"measurement": "year-to-date"}, 7, "measurement"),
        ({"measurement": "point-in-time", "metric": "assets"}, 7, "measurement"),
    ],
)
def test_ic3_t07_t11_dimension_specific_contradictions(changes, number, field):
    data, bodies = bundle(statements=[excerpt(**changes)])
    result = assess(data, bodies)
    assert result.semantics == "SEMANTICS_CONTRADICTED"
    assert claim(result, number).state == "CONTRADICTED"
    assert field in claim(result, number).contradicted_fields
    assert result.mapping == "MAPPING_UNRESOLVED"
    assert isinstance(result.candidate, NotEvaluated)


def test_ic3_t07_source_company_label_cannot_supply_identity():
    result = assess_financial_semantics(*source(), SupportInput())
    assert claim(result, 1).state == "UNRESOLVED"
    assert not result.supports


def test_ic3_t07_all_claims_require_the_target_issuer_month():
    data, bodies = bundle(statements=[excerpt(company="9999")])
    result = assess(data, bodies)
    assert all(c.state == "CONTRADICTED" for c in result.claims[:7])
    assert all("issuer_code" in c.contradicted_fields for c in result.claims[:7])


def test_ic3_t08_ytd_net_sales_cannot_support_monthly_source_field():
    data, bodies = bundle(statements=[excerpt(measurement="year-to-date")])
    result = assess(data, bodies)
    assert claim(result, 2).state == "CONTRADICTED"
    assert "measurement" in claim(result, 2).contradicted_fields


def test_ic3_t12_separate_crosswalk_required_even_when_issuer_claims_match():
    data, bodies = bundle(with_policy=False)
    result = assess(data, bodies)
    assert all(c.state == "SUPPORTED" for c in result.claims[:7])
    assert result.semantics == "SEMANTICS_SUPPORTED_FOR_RESEARCH"
    assert claim(result, 8).state == "UNRESOLVED"
    assert result.mapping == "MAPPING_UNRESOLVED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("metric", "gross_revenue"),
        ("period_kind", "STOCK"),
        ("basis_ref", "AUDITED_TIFRS"),
        ("currency", "USD"),
        ("canonical_unit", "NTD"),
        ("reporting_scope", "standalone"),
    ],
)
def test_ic3_t12_incompatible_canonical_crosswalk(field, value):
    data, bodies = bundle()
    policy = json.loads(dict(bodies)["policy.json"])
    policy["target"][field] = value
    data, bodies = change_body(data, bodies, "policy.json", encoded(policy))
    result = assess(data, bodies)
    assert claim(result, 8).reason == "CROSSWALK_SEMANTICS_INCOMPATIBLE"
    assert isinstance(result.candidate, NotEvaluated)


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_approval_ref", ""),
        ("rationale", "https://example.invalid"),
        ("support_sha256s", []),
        ("source_assurance", "audited"),
        ("basis_interpretation", "AUDITED_GAAP_PROOF"),
        ("policy_schema", "future"),
    ],
)
def test_ic3_t12_crosswalk_not_a_well_shaped_shortcut(field, value):
    data, bodies = bundle()
    policy = json.loads(dict(bodies)["policy.json"])
    policy[field] = value
    data, bodies = change_body(data, bodies, "policy.json", encoded(policy))
    result = assess(data, bodies)
    assert claim(result, 8).state == "UNRESOLVED"
    assert isinstance(result.candidate, NotEvaluated)


@pytest.mark.parametrize(
    "amount", ["321", "-1", "0", "9223372036854775807", "-9223372036854775808"]
)
def test_ic3_t13_signed_int64_lexeme_and_no_unit_conversion(amount):
    src = source(amount=amount)
    data, bodies = bundle(src[2], statements=[excerpt(amount=str(int(amount)))])
    result = assess(data, bodies, src)
    assert result.mapping == "MAPPING_CANDIDATE_PREPARED"
    assert src[2].extracted.source_tokens[5] == '"' + amount + '"'
    assert result.supports[0].monthly_amount.value == int(amount)
    assert result.selected.extracted.amount == int(amount)
    assert result.selected.original.sha256 != result.selected.view.projection_sha256
    assert isinstance(result.selected.extracted.exact_byte_span, NotEvaluated)


@pytest.mark.parametrize(
    "amount", ["9223372036854775808", "-9223372036854775809", "1.5", "12,34", "UNKNOWN"]
)
def test_ic3_t13_support_invalid_amount_never_becomes_value(amount):
    data, bodies = bundle(statements=[excerpt(amount=amount)])
    result = assess(data, bodies)
    assert result.support_input == "EVIDENCE_RESTRICTED_OR_UNVERIFIED"
    assert isinstance(result.candidate, NotEvaluated)


@pytest.mark.parametrize("token", ["000321", "+17", "9223372036854775808"])
def test_ic3_t13_existing_source_integer_policy_remains_strict(token):
    intake, spec, selected = source(amount=token)
    outcome = select_market_row(intake, spec)
    assert outcome.state == "EXTRACTION_REJECTED"
    assert outcome.reason in ("INVALID_INTEGER_TOKEN", "NUMERIC_RANGE")
    assert isinstance(selected, NotEvaluated)
    result = assess_financial_semantics(intake, spec, selected, SupportInput())
    assert result.reason == "SOURCE_SELECTION_BINDING_REJECTED"


def test_ic3_t15_unselected_additional_contradictory_statement_fails_closed():
    data, bodies = bundle()
    data, bodies = change_body(
        data, bodies, "issuer0.txt", bodies[0][1] + b"\nAll figures are standalone."
    )
    result = assess(data, bodies)
    assert result.reason == "UNSUPPORTED_OR_ADDITIONAL_STATEMENT"
    assert isinstance(result.candidate, NotEvaluated)


def test_ic3_t14_same_release_syndications_one_origin_group():
    body, quotes = excerpt()
    data, bodies = bundle(statements=[(body, quotes), (body + b"\n", quotes)])
    data["evidence"][1]["role"] = "RETRANSMISSION"
    result = assess(data, bodies)
    assert len(result.supports) == 2
    assert len(claim(result, 1).evidence_groups) == 1
    assert result.mapping == "MAPPING_CANDIDATE_PREPARED"


def test_ic3_t14_identical_bytes_cannot_claim_distinct_upstream_origin():
    data, bodies = bundle(statements=[excerpt(), excerpt()])
    data["evidence"][1]["statement_ref"] = "INVENTED_INDEPENDENT_ORIGIN"
    assert assess(data, bodies).reason == "CONTRADICTORY_COMMON_ORIGIN_DECLARATIONS"


def test_ic3_t14_same_located_release_different_bytes_not_independent():
    body, quotes = excerpt()
    data, bodies = bundle(statements=[(body, quotes), (body + b"\n", quotes)])
    data["evidence"][1]["statement_ref"] = "FALSE_SECOND_STATEMENT"
    assert assess(data, bodies).reason == "CONTRADICTORY_COMMON_ORIGIN_DECLARATIONS"


def test_ic3_t06_bool_cannot_impersonate_integer_in_selection():
    intake, spec, selected = source(amount="1")
    forged = replace(selected, extracted=replace(selected.extracted, amount=True))
    result = assess_financial_semantics(intake, spec, forged, SupportInput())
    assert result.reason == "SOURCE_SELECTION_BINDING_REJECTED"


@pytest.mark.parametrize("level", ["ic3", "ic1", "a06", "a05", "a04"])
def test_ic3_t20_all_inherited_code_shapes_are_checked(ic3_code, level):
    ic1 = ic3_code.upstream_ic1
    a06 = ic1.upstream_a06
    a05 = a06.upstream_a05
    a04 = a05.upstream_a04
    if level == "a04":
        a04 = replace(a04, byte_lengths=())
    if level in ("a04", "a05"):
        a05 = replace(
            a05,
            upstream_a04=a04,
            extension_byte_lengths=() if level == "a05" else a05.extension_byte_lengths,
        )
    if level in ("a04", "a05", "a06"):
        a06 = replace(
            a06,
            upstream_a05=a05,
            extension_byte_lengths=() if level == "a06" else a06.extension_byte_lengths,
        )
    ic1 = replace(
        ic1,
        upstream_a06=a06,
        extension_byte_lengths=() if level == "ic1" else ic1.extension_byte_lengths,
    )
    malformed = replace(
        ic3_code,
        upstream_ic1=ic1,
        extension_byte_lengths=() if level == "ic3" else ic3_code.extension_byte_lengths,
    )
    with pytest.raises(ContractError, match="INVALID_OUTER_CODE_OBSERVATION"):
        evaluate_financial_semantics(*source(), SupportInput(), malformed)


@pytest.mark.parametrize("reverse", [False, True])
def test_ic3_t15_conflicts_no_majority_latest_or_order_winner(reverse):
    statements = [excerpt(), excerpt(), excerpt(amount="999")]
    if reverse:
        statements.reverse()
    data, bodies = bundle(statements=statements)
    data["evidence"][-1]["acquisition_text"] = "2999-01-01 NON_PIT"
    result = assess(data, bodies)
    assert result.semantics == "SEMANTICS_CONTRADICTED"
    assert claim(result, 3).state == "CONTRADICTED"
    assert isinstance(result.candidate, NotEvaluated)


@pytest.mark.parametrize(
    "kind",
    [
        "url",
        "summary",
        "unanchored",
        "duplicate_quote",
        "invalid_unicode",
        "html_profile",
        "third_party",
        "government",
        "no_synthetic_marker",
    ],
)
def test_ic3_t16_no_positive_from_leads_or_unverified_content(kind):
    data, bodies = bundle()
    body = bodies[0][1]
    if kind == "url":
        body = b"https://example.invalid/issuer"
    elif kind == "summary":
        body = b"SYNTHETIC_TEST_ONLY ChatGPT summary: probably thousands NTD"
    elif kind == "unanchored":
        data["evidence"][0]["locators"]["sales"] += "invented"
    elif kind == "duplicate_quote":
        body += b"\n" + data["evidence"][0]["locators"]["sales"].encode()
    elif kind == "invalid_unicode":
        body += b"\xff"
    elif kind == "html_profile":
        data["evidence"][0]["profile"] = "AUTO_HTML_SCRAPE"
    elif kind in ("third_party", "government"):
        data["evidence"][0]["role"] = (
            "THIRD_PARTY" if kind == "third_party" else "GOVERNMENT_REFERENCE"
        )
    elif kind == "no_synthetic_marker":
        body = body.replace(b"SYNTHETIC_TEST_ONLY", b"CLAIMED_REAL")
    data, bodies = change_body(data, bodies, "issuer0.txt", body)
    result = assess(data, bodies)
    assert result.support_input == "EVIDENCE_RESTRICTED_OR_UNVERIFIED"
    assert all(c.state != "SUPPORTED" for c in result.claims)


def test_ic3_t17_determinism_and_mutation_identity(ic3_code):
    src = source()
    data, bodies = bundle(src[2])
    support = supplied(data, bodies)
    result = evaluate_financial_semantics(*src, support, ic3_code)
    assert result == evaluate_financial_semantics(*src, support, ic3_code)
    mutated = replace(support, bodies=(bodies[0][0:1] + (bodies[0][1] + b"!",),) + bodies[1:])
    rejected = evaluate_financial_semantics(*src, mutated, ic3_code)
    assert rejected.assessment.reason == "EVIDENCE_PIN_MISMATCH"
    assert rejected.research_ref != result.research_ref
    data["evidence"][0]["rights"]["evidence_text"] += " Audit narrative only."
    audit_changed = evaluate_financial_semantics(*src, supplied(data, bodies), ic3_code)
    assert audit_changed.assessment.selected == result.assessment.selected
    assert audit_changed.research_ref != result.research_ref
    for changed_src in (source(foreign="CHANGED_NON_TARGET"), source(reverse=True)):
        changed_data, changed_bodies = bundle(changed_src[2])
        changed = evaluate_financial_semantics(
            *changed_src, supplied(changed_data, changed_bodies), ic3_code
        )
        assert changed.research_ref != result.research_ref
        assert (
            changed.assessment.selected.extracted.amount
            == result.assessment.selected.extracted.amount
        )


def test_ic3_t17_policy_and_code_identity(ic3_code):
    src = source()
    data, bodies = bundle(src[2])
    first = evaluate_financial_semantics(*src, supplied(data, bodies), ic3_code)
    policy = json.loads(dict(bodies)["policy.json"])
    policy["policy_ref"] = "SYNTHETIC_POLICY-v0.2"
    changed_data, changed_bodies = change_body(data, bodies, "policy.json", encoded(policy))
    second = evaluate_financial_semantics(*src, supplied(changed_data, changed_bodies), ic3_code)
    assert first.research_ref != second.research_ref
    changed_code = replace(
        ic3_code, extension_pins=(CodePin(IC3_CODE_PATHS[0], "0" * 64), ic3_code.extension_pins[1])
    )
    third = evaluate_financial_semantics(*src, supplied(data, bodies), changed_code)
    assert third.research_ref != first.research_ref
    assert "NOT_RUNTIME_ATTESTED" in third.code.interpretation


def test_ic3_t18_exact_candidate_schema_noninstalled_and_immutable():
    src = source()
    before = src[0].manifest
    result = assess(src=src)
    candidate = result.candidate
    assert isinstance(candidate, MappingCandidate)
    data = json.loads(candidate.body)
    assert set(data) == {
        "mapping_schema",
        "applies_to_raw_sha256",
        "source_columns",
        "issuer_code",
        "issuer_ref",
        "metric",
        "period_kind",
        "reporting_scope",
        "basis_ref",
        "currency",
        "canonical_unit",
        "support_class",
        "evidence_origin",
        "evidence_text",
    }
    assert data["source_columns"] == {
        "company_code": "公司代號",
        "reference_period": "資料年月",
        "source_amount": "營業收入-當月營收",
    }
    assert data["support_class"] == "SYNTHETIC_TEST_ONLY"
    assert candidate.sha256 == sha256(candidate.body).hexdigest()
    assert candidate.status == "PROPOSED_NOT_INSTALLED_RESEARCH_ONLY"
    assert src[0].manifest == before and before.mapping_file is None
    assert before.snapshot_ref == snapshot_ref_for(before.raw.sha256, None)
    assert before.snapshot_ref != snapshot_ref_for(before.raw.sha256, candidate.sha256)
    assert before.rights.covered_paths == ("market.csv",)
    with pytest.raises(FrozenInstanceError):
        candidate.status = "INSTALLED"


@pytest.mark.parametrize("context", ["public", "prospective_observed"])
def test_ic3_t19_preview_constant_and_no_native_owner_execution(ic3_code, context):
    src = source()
    data, bodies = bundle(src[2])
    results = [
        evaluate_financial_semantics(*src, s, ic3_code, context)
        for s in (SupportInput(), supplied(data, bodies))
    ]
    assert results[0].diagnostic_preview_bytes == results[1].diagnostic_preview_bytes
    for result in results:
        preview = json.loads(result.diagnostic_preview_bytes)
        assert set(preview) == {
            "availability",
            "disposition",
            "trust",
            "admission_eligible",
            "diagnostic_only",
            "agent_observation",
        }
        assert all(
            word not in result.diagnostic_preview_bytes
            for word in (
                b"321",
                b"0007",
                b"2099",
                b"NTD",
                b"SYNTHETIC",
                b"sha256",
                b"reason",
                b"rights",
            )
        )
        assert not result.admission_eligible and result.diagnostic_only
        assert result.agent_observation == "NOT_PRODUCED"
        assert result.typed_transport == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"
        assert tuple(owner for owner, _ in result.owner_results) == ("S1", "S2", "S3", "A04", "A05")
        assert all(isinstance(v, NotEvaluated) for _, v in result.owner_results)
        assert isinstance(result.historical_publication_proof, NotEvaluated)
        assert result.source_authentication == "NOT_ESTABLISHED"


def test_ic3_t20_outer_observation_and_core_purity(ic3_code):
    root = Path(__file__).resolve().parents[3]
    for pin, length in zip(ic3_code.extension_pins, ic3_code.extension_byte_lengths, strict=True):
        body = (root / pin.path).read_bytes()
        assert len(body) == length and sha256(body).hexdigest() == pin.sha256
    core = ast.parse((root / IC3_CODE_PATHS[0]).read_text())
    names = {node.id for node in ast.walk(core) if isinstance(node, ast.Name)}
    assert not names & {"open", "Path", "subprocess", "socket", "requests", "os", "pytest"}
    for path in IC3_CODE_PATHS:
        text = (root / path).read_text()
        assert "tests.unit" not in text and "golden" not in text.lower()
    assert len(ic3_code.upstream_ic1.extension_pins) == 2
    assert len(ic3_code.upstream_ic1.upstream_a06.extension_pins) == 3
    assert CLAIMS == tuple(f"IC3-C{i:02d}" for i in range(1, 9))
