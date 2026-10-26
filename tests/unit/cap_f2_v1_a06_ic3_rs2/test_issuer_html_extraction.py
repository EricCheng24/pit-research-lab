"""RS2-T01..T32: invented structure positives and explicit adverse proof."""

import ast
import json
import os
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path

import pytest
from rs2_inputs import (
    bw_html,
    bw_spec,
    material,
    pin,
    rights_description,
    row,
    sec_html,
    sec_spec,
    write_source,
)

import pit_research_lab.domain.issuer_html_slice as reader
from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated
from pit_research_lab.domain.issuer_html_extraction import (
    BW_SHA,
    CODE_PATHS,
    MAX_BODY,
    SEC_SHA,
    ExtractionRefusal,
    HtmlEvidenceObservation,
    extract_html,
)
from pit_research_lab.domain.issuer_html_slice import inspect_issuer_html
from pit_research_lab.domain.source_intake import FilePin


def parsed(text=None, spec=None, code=()):
    return extract_html(*material(text, spec), code)


def refused(result, reason=None):
    assert isinstance(result, ExtractionRefusal)
    assert isinstance(result.generated_view, NotEvaluated)
    assert isinstance(result.source_body, NotEvaluated)
    assert not result.admission_eligible
    if reason:
        assert result.reason == reason


def test_rs2_t01_accepted_candidate_bytes():
    from b01_preservation import verify_preserved
    from rs2_inputs import CANDIDATE_PINS

    root = Path(__file__).resolve().parents[3]
    assert len(CANDIDATE_PINS) == 46
    assert len({path for path, _, _ in CANDIDATE_PINS}) == 46
    ic1_path = "tests/unit/cap_f2_v1_a06_ic1/test_market_source_slice.py"
    # Keep the accepted RS2 record; only this reviewed CI test transition is current.
    assert tuple(pin for pin in CANDIDATE_PINS if pin[0] == ic1_path) == (
        (
            ic1_path,
            23778,
            "cedcd2ecd13edb87934fb5a99023eac2ffae01cbc52583b75aa8a22dd355b288",
        ),
    )
    for path, length, digest in CANDIDATE_PINS:
        if path == ic1_path:
            length, digest = (
                23817,
                "b8357c4323445363cab4cec1fb960ccc02cc883ffa774c9a096d54339cbce1cf",
            )
        verify_preserved(root, path, length, digest)


def test_rs2_t02_exact_new_file_budget():
    root = Path(__file__).resolve().parents[3]
    assert all((root / path).is_file() for path in CODE_PATHS)
    assert {p.name for p in Path(__file__).parent.glob("*.py")} == {
        "conftest.py",
        "rs2_inputs.py",
        "test_issuer_html_extraction.py",
        "b01_preservation.py",
    }


def test_b01_preservation_checks_current_and_historical_bytes(tmp_path, monkeypatch):
    import subprocess

    import b01_preservation as preservation

    live, historical = b"current fixture\n", b"historical fixture\n"
    path = tmp_path / "fixture.py"
    path.write_bytes(live)
    monkeypatch.setattr(
        preservation,
        "CURRENT_PINS",
        {
            "fixture.py": (len(live), sha256(live).hexdigest()),
        },
    )
    monkeypatch.setattr(
        preservation.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, historical),
    )
    expected = (len(historical), sha256(historical).hexdigest())
    preservation.verify_preserved(tmp_path, "fixture.py", *expected)
    path.write_bytes(b"tampered fixture\n")
    with pytest.raises(AssertionError, match="B01_CURRENT_PIN_MISMATCH"):
        preservation.verify_preserved(tmp_path, "fixture.py", *expected)
    path.write_bytes(live)
    with pytest.raises(AssertionError, match="PHASE_A_PIN_MISMATCH"):
        preservation.verify_preserved(tmp_path, "fixture.py", len(historical), "0" * 64)


def test_b01_absent_git_object_is_a_failure(monkeypatch):
    import b01_preservation as preservation
    from rs2_inputs import CANDIDATE_PINS

    monkeypatch.setattr(preservation, "FROZEN", "0" * 40)
    root = Path(__file__).resolve().parents[3]
    pin = next(p for p in CANDIDATE_PINS if p[0] == "src/pit_research_lab/domain/contracts.py")
    with pytest.raises(AssertionError, match="FROZEN_HISTORY_UNAVAILABLE"):
        preservation.verify_preserved(root, *pin)


def test_b01_both_ci_jobs_supply_historical_objects():
    root = Path(__file__).resolve().parents[3]
    workflow = (root / ".github/workflows/ci.yml").read_text()
    assert workflow.count("fetch-depth: 0") == 2
    assert workflow.count("persist-credentials: false") == 2
    assert "IC1_APPROVED_REAL" not in workflow and "RS3F_APPROVED_REAL" not in workflow


def test_b01_explicit_current_change_manifest():
    from b01_preservation import B01_PINS, CURRENT_PINS, NEW_FILE_PINS

    root = Path(__file__).resolve().parents[3]
    assert len(CURRENT_PINS) == 18
    assert set(B01_PINS) == {
        "tests/unit/cap_f2_v1_a03/a03_inputs.py",
        "tests/unit/cap_f2_v1_a06_ic3_rs2/test_issuer_html_extraction.py",
    }
    assert set(NEW_FILE_PINS) == {"tests/unit/cap_f2_v1_a03/test_b02_relations_asof.py"}
    assert set(CURRENT_PINS).isdisjoint(NEW_FILE_PINS)
    assert not any(path.startswith("tests/unit/cap_f2_wu00/") for path in CURRENT_PINS)
    for path, expected in (CURRENT_PINS | NEW_FILE_PINS).items():
        body = (root / path).read_bytes()
        assert (len(body), sha256(body).hexdigest()) == expected


def test_b02_merged_b01_history_is_not_moved_or_optional(monkeypatch):
    import b01_preservation as preservation
    from rs2_inputs import CANDIDATE_PINS

    root = Path(__file__).resolve().parents[3]
    pin = next(p for p in CANDIDATE_PINS if p[0] == "tests/unit/cap_f2_v1_a03/a03_inputs.py")
    assert preservation.FROZEN == "6edf54d4b81b7047c632937112aa4d764aa806b6"
    assert preservation.B01_FROZEN == "a945a33f92181498000a86cbaa66d8b89401d3cc"
    preservation.verify_preserved(root, *pin)
    monkeypatch.setattr(preservation, "B01_FROZEN", "0" * 40)
    with pytest.raises(AssertionError, match="B01_HISTORY_UNAVAILABLE"):
        preservation.verify_preserved(root, *pin)


def test_rs2_t03_sec_invented_happy_path(html_code):
    result = parsed(code=html_code)
    assert isinstance(result, HtmlEvidenceObservation)
    assert result.parsed_amount_text == "8,642"
    assert result.original_amount_lexeme == "8,642"
    assert result.specification.issuer_name.startswith("SYNTHETIC_TEST_ONLY")
    assert result.source_evidence_class == "DOCUMENT_CONTENT_OBSERVED_UNADMITTED"


@pytest.mark.parametrize(
    "kind",
    [
        "unknown",
        "utf8_declaration",
        "mixed_utf8",
        "undefined_cp1252",
        "bom_utf8",
        "bom_utf16",
        "charset_suffix",
        "duplicate_charset",
    ],
)
def test_rs2_t04_encoding_refusals(html_code, kind):
    body, p, spec = material()
    if kind == "unknown":
        spec = replace(spec, declared_encoding="latin1")
    elif kind == "utf8_declaration":
        body = body.replace(b"windows-1252", b"UTF-8")
    elif kind == "mixed_utf8":
        body = sec_html().encode("utf-8")
    elif kind == "undefined_cp1252":
        body += b"\x81"
    elif kind == "bom_utf8":
        body = b"\xef\xbb\xbf" + body
    elif kind == "bom_utf16":
        body = b"\xff\xfe" + body
    elif kind == "charset_suffix":
        body = body.replace(b"windows-1252", b"windows-1252evil")
    else:
        body = body.replace(b"</head>", b'<meta charset="windows-1252"></head>')
    refused(extract_html(body, pin("synthetic.html", body), spec, html_code))


def test_rs2_t04_declared_windows1252_roundtrip(html_code):
    body, p, s = material()
    assert b"\x92" in body and body.decode("cp1252").encode("cp1252") == body
    assert isinstance(extract_html(body, p, s, html_code), HtmlEvidenceObservation)


def test_rs2_t05_t06_t07_boundaries_and_two_tables(html_code):
    result = parsed(code=html_code)
    assert isinstance(result, HtmlEvidenceObservation)
    data = json.loads(result.view.canonical_view_bytes)
    assert data["selected_row_key"] == ["September", "Net sales"]
    assert data["year_column"] == "2026"
    assert "div[2]" in result.section_locator.element_path
    assert data["table_locator"]["element_path"].endswith("div[2]/table[1]")
    assert data["original_amount_lexeme"] == "8,642"
    assert any(
        dict(c.predicates).get("reason") == "ALL_EMPTY_SIX_CELL_LAYOUT_ONLY"
        for c in result.claim_locators
    )


def test_rs2_t08_exclusions_explicit_even_equal_target(html_code):
    result = parsed(sec_html(comparison="8,642", ytd="8,642"), code=html_code)
    assert isinstance(result, HtmlEvidenceObservation)
    assert len(result.exclusions) == 2
    assert {c.reason for c in result.exclusions} == {
        "EXCLUDED_YEAR_2025_OR_PRIOR_YEAR",
        "EXCLUDED_YEAR_TO_DATE",
    }
    assert all(c.parsed_text == "8,642" for c in result.exclusions)
    assert all(
        c.locator.element_path != result.claim_locators[-1].element_path for c in result.exclusions
    )


def test_rs2_t09_no_sec_borrowed_semantics(html_code):
    result = parsed(code=html_code)
    assert isinstance(result, HtmlEvidenceObservation)
    assert result.unobserved_claims == (
        "TWSE_CODE_NOT_OBSERVED_IN_SEC",
        "UNAUDITED_NOT_OBSERVED_IN_SEC",
        "CONSOLIDATED_NOT_OBSERVED_IN_SEC",
    )
    payload = json.loads(result.view.canonical_view_bytes)
    assert (
        payload["issuer_code"] == "NOT_EVALUATED" and payload["canonical_unit"] == "NOT_EVALUATED"
    )


def test_rs2_t10_t11_original_view_identity_and_replay(html_code):
    body, p, s = material()
    original = body
    first = extract_html(body, p, s, html_code)
    second = extract_html(body, p, s, html_code)
    assert first == second and isinstance(first, HtmlEvidenceObservation)
    assert body == original and p.sha256 == sha256(original).hexdigest()
    assert (
        first.view.generated_view_sha256
        == sha256(first.view.canonical_view_bytes).hexdigest()
        != p.sha256
    )
    data = json.loads(first.view.canonical_view_bytes)
    assert data["representation_kind"] == "ADAPTER_GENERATED_HTML_EXTRACTION_VIEW"
    assert (
        data["raw_filename"] == "synthetic.html"
        and data["raw_sha256"] == p.sha256
        and data["raw_byte_length"] == len(body)
    )
    assert data["capture_classification"] == "SYNTHETIC_TEST_ONLY"
    assert (
        b"/tmp/" not in first.view.canonical_view_bytes
        and b"timestamp" not in first.view.canonical_view_bytes
    )
    assert (
        b"<html" not in first.view.canonical_view_bytes
        and b"const decoy" not in first.view.canonical_view_bytes
    )
    with pytest.raises(FrozenInstanceError):
        first.parsed_amount_text = "0"


def test_rs2_t11_non_target_original_changes_keep_distinct_identity(html_code):
    first = parsed(code=html_code)
    second = parsed(sec_html().replace("machinery", "unrelated equipment"), code=html_code)
    assert isinstance(first, HtmlEvidenceObservation) and isinstance(
        second, HtmlEvidenceObservation
    )
    assert first.parsed_amount_text == second.parsed_amount_text
    assert first.source_pin.sha256 != second.source_pin.sha256
    assert first.view.generated_view_sha256 != second.view.generated_view_sha256


def test_rs2_t12_actual_start_offsets_only(html_code):
    body, p, s = material()
    result = extract_html(body, p, s, html_code)
    assert isinstance(result, HtmlEvidenceObservation)
    for locator in (result.section_locator, result.table_locator, *result.claim_locators):
        assert locator.exact_byte_span == "BYTE_SPAN_NOT_ESTABLISHED"
        assert body[locator.original_element_start_tag_byte_offset :][:1] == b"<"
    target = result.claim_locators[-1]
    offset = target.original_element_start_tag_byte_offset
    assert body[offset : offset + 40].startswith(b"<td>8,642</td>")
    assert (
        json.loads(result.view.canonical_view_bytes)["exact_byte_span"]
        == "BYTE_SPAN_NOT_ESTABLISHED"
    )


@pytest.mark.parametrize("kind", ["duplicate_marker", "hidden_marker", "wrong_exhibit"])
def test_rs2_t13_marker_failures(html_code, kind):
    text = sec_html()
    marker = "<p>Exhibit 99.2</p>"
    replacement = (
        marker * 2
        if kind == "duplicate_marker"
        else ("<p hidden>Exhibit 99.2</p>" if kind == "hidden_marker" else "<p>Exhibit 99.3</p>")
    )
    refused(parsed(text.replace(marker, replacement), code=html_code))


@pytest.mark.parametrize("kind", ["header", "row", "table", "layout", "unit"])
def test_rs2_t14_same_value_duplicates(html_code, kind):
    text = sec_html()
    header = row(["Period", "Items", "2026", "2025", "Changes", "%"])
    target = row(["September", "Net sales", "8,642", "5,103", "3,539", "69.35%"])
    if kind == "header":
        text = text.replace(header, header * 2)
    elif kind == "row":
        text = text.replace(target, target * 2)
    elif kind == "layout":
        text = text.replace(row([""] * 6), row([""] * 6) * 2)
    elif kind == "unit":
        text = text.replace(
            "<div>1) Sales volume (NT$ Thousand)</div>",
            "<div>1) Sales volume (NT$ Thousand)</div>" * 2,
        )
    else:
        start = text.index('<table id="sales">', text.index('<div id="revenue">'))
        end = text.index("</table>", start) + 8
        text = text[:start] + text[start:end] * 2 + text[end:]
    refused(parsed(text, code=html_code))


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "SYNTHETIC_TEST_ONLY Another Issuer"),
        ("date", "October 7, 2026"),
        ("period", "SYNTHETIC_TEST_ONLY for the period of August 2026."),
        ("unit", "1) Sales volume (US$ Million)"),
        ("amount", "8,643"),
        ("amount", "-"),
        ("amount", "8642.0"),
    ],
)
def test_rs2_t15_conflicting_expected_scope(html_code, field, value):
    refused(parsed(sec_html(**{field: value}), code=html_code))


def test_rs2_t15_wrong_year_and_added_claim_refused(html_code):
    refused(parsed(sec_html().replace(">2026<", ">2027<"), code=html_code))
    refused(
        parsed(sec_html().replace("Owner’s note", "unaudited consolidated 2303"), code=html_code),
        "UNEXPECTED_SEC_SEMANTIC_CLAIM",
    )


@pytest.mark.parametrize(
    "extra",
    [
        "<p>SYNTHETIC_TEST_ONLY Another Issuer</p>",
        "<p>October 7, 2026</p>",
        "<p>SYNTHETIC_TEST_ONLY for the period of August 2026.</p>",
    ],
)
def test_rs2_t15_conflicting_header_cannot_hide_behind_matching_header(html_code, extra):
    text = sec_html().replace("<div>1) Sales volume", extra + "<div>1) Sales volume")
    refused(parsed(text, code=html_code))


def test_rs2_t16_decoy_values_do_not_choose_winner(html_code):
    result = parsed(sec_html(comparison="99,999", ytd="88,888"), code=html_code)
    assert isinstance(result, HtmlEvidenceObservation) and result.parsed_amount_text == "8,642"
    refused(
        parsed(sec_html(amount="99,999", comparison="8,642", ytd="8,642"), code=html_code),
        "TARGET_AMOUNT_CONFLICT",
    )
    text = sec_html().replace("<td>September</td>", "<td>August</td>")
    refused(parsed(text, code=html_code))


@pytest.mark.parametrize(
    "attr", ['rowspan="2"', 'colspan="2"', 'colspan="0"', 'rowspan="true"', 'colspan="01"']
)
def test_rs2_t17_table_spans(html_code, attr):
    refused(
        parsed(sec_html().replace("<td>8,642</td>", f"<td {attr}>8,642</td>"), code=html_code),
        "UNSUPPORTED_TABLE_SPAN",
    )


@pytest.mark.parametrize(
    "tag", ["script", "style", "template", "noscript", "iframe", "object", "svg"]
)
def test_rs2_t18_excluded_critical_payloads(html_code, tag):
    text = sec_html().replace("<td>8,642</td>", f"<td><{tag}>8,642</{tag}></td>")
    refused(parsed(text, code=html_code), "EXECUTABLE_OR_EXCLUDED_CRITICAL_NODE")


@pytest.mark.parametrize(
    "attr",
    [
        "hidden",
        'aria-hidden="true"',
        'style="display:none"',
        'style="visibility: hidden"',
        'onclick="raiseBad()"',
        'onload="steal()"',
        'srcdoc="untrusted"',
    ],
)
def test_rs2_t18_hidden_and_active_attributes(html_code, attr):
    refused(parsed(sec_html().replace("<td>8,642</td>", f"<td {attr}>8,642</td>"), code=html_code))


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "java\tscript:bad()",
        "data:text/html,bad",
        "file:///private/path",
        "vbscript:bad()",
    ],
)
def test_rs2_t18_malicious_links_never_executed(html_code, url):
    text = sec_html().replace("<td>8,642</td>", f'<td><a href="{url}">8,642</a></td>')
    refused(parsed(text, code=html_code), "UNSAFE_CRITICAL_LINK")


@pytest.mark.parametrize(
    "kind",
    [
        "mismatched_close",
        "unclosed",
        "mixed_paragraph",
        "cell_outside_row",
        "nested_table",
        "duplicate_attribute",
        "xml_entity",
        "xml_pi",
        "unknown_entity",
        "missing_semicolon",
    ],
)
def test_rs2_t19_malformed_or_ambiguous_html(html_code, kind):
    text = sec_html()
    replacements = {
        "mismatched_close": ("<td>8,642</td>", "<td>8,642</th>"),
        "unclosed": ("</html>", ""),
        "mixed_paragraph": ("<p>SYNTHETIC_TEST_ONLY Owner’s note</p>", "<p><p>bad</p></p>"),
        "cell_outside_row": ("<tbody>", "<tbody><td>8,642</td>"),
        "nested_table": ("<td>8,642</td>", "<td><table><tr><td>8,642</td></tr></table></td>"),
        "duplicate_attribute": ("<td>8,642</td>", '<td id="a" id="b">8,642</td>'),
        "xml_entity": ("<!DOCTYPE html>", '<!DOCTYPE html [<!ENTITY x SYSTEM "file:///private">]>'),
        "xml_pi": ("<!DOCTYPE html>", '<?xml version="1.0"?>'),
        "unknown_entity": ("Owner’s", "Owner&unknown;"),
        "missing_semicolon": ("Owner’s", "Owner&nbsp note"),
    }
    old, new = replacements[kind]
    refused(parsed(text.replace(old, new), code=html_code))


def test_rs2_t20_entities_whitespace_no_source_rewrite(html_code):
    text = (
        sec_html()
        .replace("Sales volume (NT$ Thousand)", "Sales\nvolume (NT$&nbsp;Thousand)")
        .replace(">8,642<", ">8,&#54;42<")
    )
    body, p, s = material(text)
    result = extract_html(body, p, s, html_code)
    assert isinstance(result, HtmlEvidenceObservation)
    assert result.parsed_amount_text == "8,642" and result.original_amount_lexeme == "8,&#54;42"
    assert body == text.encode("cp1252") and p.sha256 == sha256(body).hexdigest()
    assert result == extract_html(body, p, s, html_code)


@pytest.mark.parametrize("kind", ["body", "nodes", "depth", "rows", "columns"])
def test_rs2_t21_all_resource_bounds(html_code, kind):
    text = sec_html()
    if kind == "body":
        body = b"x" * (MAX_BODY + 1)
        result = extract_html(
            body, FilePin("synthetic.html", MAX_BODY, "0" * 64), sec_spec(), html_code
        )
    else:
        if kind == "nodes":
            text = text.replace("</body>", "<i></i>" * 5001 + "</body>")
        elif kind == "depth":
            text = text.replace("</body>", "<i>" * 257 + "x" + "</i>" * 257 + "</body>")
        elif kind == "rows":
            text = text.replace("</tbody>", "<tr><td></td></tr>" * 257 + "</tbody>")
        else:
            text = text.replace("<tbody>", "<tbody>" + row(["x"] * 17))
        result = parsed(text, code=html_code)
    refused(result)
    assert result.reason in {
        "HTML_BODY_SIZE_LIMIT",
        "HTML_NODE_LIMIT",
        "HTML_DEPTH_LIMIT",
        "TABLE_ROW_LIMIT",
        "TABLE_COLUMN_LIMIT",
    }


def external_spec():
    return sec_spec(
        source_role="SEC_PUBLIC_FILING",
        classification="OWNER_SUPPLIED_EXTERNAL",
        issuer_name="United Microelectronics Corporation",
        expected_amount_text="25,350,431",
    )


def test_rs2_t22_real_formal_preflight_zero_body_reads(html_code, monkeypatch):
    calls = []

    def forbidden(*args):
        calls.append(args)
        raise AssertionError("Original open prohibited")

    monkeypatch.setattr(reader, "_open_root", forbidden)
    monkeypatch.setattr(reader, "_read_html_relative", forbidden)
    p = FilePin("umc-ex99.htm", 58214, SEC_SHA)
    result = inspect_issuer_html(
        Path("/mnt/c/Users/rooki/Downloads/CAP-F2-V1-A06-IC3_support_inputs"),
        p,
        external_spec(),
        html_code,
    )
    assert result.status == "RIGHTS_PENDING" and result.reason == "RIGHTS_DOCUMENTARY_GAP"
    assert calls == [] and result.body_read_attempts == ()
    assert isinstance(result.source_body, NotEvaluated) and isinstance(
        result.observation, NotEvaluated
    )


@pytest.mark.parametrize(
    "token", ["PERMITTED", "OWNER_APPROVED", "SIGNED", "https://example.invalid/approval"]
)
def test_rs2_t23_nonempty_approval_never_authenticates(html_code, monkeypatch, tmp_path, token):
    p = FilePin("umc-ex99.htm", 58214, SEC_SHA)
    s = external_spec()
    artifact = {
        "relative_path": "SYNTHETIC_TEST_ONLY_terms.txt",
        "byte_length": 17,
        "sha256": "0" * 64,
    }
    metadata = rights_description(
        p,
        s,
        html_code,
        terms_pin=artifact,
        decision_pin=artifact,
        approval_ref=token,
        declared_status="PERMITTED",
    )

    def forbidden(*args):
        raise AssertionError("No actual raw or terms access")

    monkeypatch.setattr(reader, "_open_root", forbidden)
    result = inspect_issuer_html(tmp_path, p, s, html_code, metadata)
    assert result.status == "RIGHTS_PENDING" and result.reason == "OWNER_APPROVAL_UNVERIFIED"
    assert result.body_read_attempts == () and isinstance(result.source_body, NotEvaluated)


@pytest.mark.parametrize("mutation", ["hash", "length", "issuer", "month"])
def test_rs2_t24_pure_identity_or_scope_mismatch(html_code, mutation):
    body, p, s = material()
    if mutation == "hash":
        p = replace(p, sha256="0" * 64)
    elif mutation == "length":
        p = replace(p, byte_length=p.byte_length - 1)
    elif mutation == "issuer":
        s = replace(s, issuer_name="SYNTHETIC_TEST_ONLY wrong")
    else:
        s = replace(s, reference_month="2026-08")
    refused(extract_html(body, p, s, html_code))


@pytest.mark.parametrize(
    "kind",
    [
        "symlink_leaf",
        "symlink_root",
        "fifo",
        "directory",
        "hash",
        "length",
        "oversize",
        "partial_read",
        "swap",
        "swap_same_bytes",
        "parent_swap",
    ],
)
def test_rs2_t24_safe_synthetic_reader(html_code, tmp_path, monkeypatch, kind):
    body, p, s = material()
    root = tmp_path / "SYNTHETIC_TEST_ONLY"
    p = write_source(root, body)
    leaf = root / p.relative_path
    if kind in ("symlink_leaf", "fifo", "directory"):
        leaf.unlink()
        if kind == "symlink_leaf":
            leaf.symlink_to(root / "other.html")
            (root / "other.html").write_bytes(body)
        elif kind == "fifo":
            os.mkfifo(leaf)
        else:
            leaf.mkdir()
    elif kind == "symlink_root":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    elif kind == "hash":
        leaf.write_bytes(body[:-1] + b"X")
    elif kind == "length":
        leaf.write_bytes(body + b"!")
    elif kind == "oversize":
        leaf.write_bytes(b"x" * (MAX_BODY + 1))
    elif kind in ("partial_read", "swap", "swap_same_bytes", "parent_swap"):
        original = reader.os.read
        triggered = False
        if kind == "parent_swap":
            leaf.unlink()
            (root / "nested").mkdir()
            leaf = root / "nested" / "synthetic.html"
            leaf.write_bytes(body)
            p = pin("nested/synthetic.html", body)

        def race(fd, n):
            nonlocal triggered
            if kind == "partial_read":
                return b""
            result = original(fd, n)
            if not triggered:
                triggered = True
                if kind == "parent_swap":
                    (root / "nested").rename(root / "retired")
                    (root / "nested").mkdir()
                    (root / "nested" / "synthetic.html").write_bytes(body)
                else:
                    replacement = root / "replacement.html"
                    replacement.write_bytes(
                        body if kind == "swap_same_bytes" else body + b"changed"
                    )
                    os.replace(replacement, leaf)
            return result

        monkeypatch.setattr(reader.os, "read", race)
    result = inspect_issuer_html(root, p, s, html_code)
    assert result.status == "STRUCTURAL_REFUSAL" and not isinstance(
        result.observation, HtmlEvidenceObservation
    )
    assert isinstance(result.source_body, NotEvaluated)


@pytest.mark.parametrize(
    "path", ["../escape.html", "/tmp/file.html", ".hidden", "a/../b", "a\\b", "a:b"]
)
def test_rs2_t24_unsafe_relative_pins(path):
    with pytest.raises(ContractError):
        FilePin(path, 1, "0" * 64)


def test_rs2_t24_no_synthetic_relabel_access_to_owner_root(html_code, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Owner root cannot be relabelled")

    monkeypatch.setattr(reader, "_open_root", forbidden)
    body, p, s = material()
    result = inspect_issuer_html(
        Path("/mnt/c/Users/rooki/Downloads/CAP-F2-V1-A06-IC3_support_inputs"), p, s, html_code
    )
    assert result.reason == "SYNTHETIC_INPUT_REQUIRES_ISOLATED_TMP_ROOT"
    result = inspect_issuer_html(
        Path("/tmp/SYNTHETIC_TEST_ONLY"), FilePin("umc-ex99.htm", 58214, SEC_SHA), s, html_code
    )
    assert result.reason == "REAL_SOURCE_CANNOT_BE_RELABELLED_SYNTHETIC"


@pytest.mark.parametrize(
    "field,value",
    [
        ("profile_id", "wrong"),
        ("profile_version", "v99"),
        ("source_role", "THIRD_PARTY"),
        ("reference_month", "2026-08"),
        ("issuer_name", "wrong"),
        ("source_pin", {"relative_path": "wrong.html", "byte_length": 1, "sha256": "0" * 64}),
        ("code_pins", []),
    ],
)
def test_rs2_t25_metadata_cross_links(html_code, tmp_path, monkeypatch, field, value):
    _, p, s = material()

    def forbidden(*args):
        raise AssertionError("Invalid cross-link must precede read")

    monkeypatch.setattr(reader, "_open_root", forbidden)
    result = inspect_issuer_html(
        tmp_path, p, s, html_code, rights_description(p, s, html_code, **{field: value})
    )
    assert result.status == "STRUCTURAL_REFUSAL" and result.body_read_attempts == ()


@pytest.mark.parametrize(
    "body", [b'{"x":1,"x":2}', b"[]", b"\xff", b'{"x":1.5}', b"{}", b"x" * 65537]
)
def test_rs2_t25_metadata_schema_refuses(html_code, tmp_path, body):
    _, p, s = material()
    result = inspect_issuer_html(tmp_path, p, s, html_code, body)
    assert result.status == "STRUCTURAL_REFUSAL" and result.body_read_attempts == ()


def test_rs2_t25_code_version_identity_and_diagnostics(html_code):
    body, p, s = material()
    first = extract_html(body, p, s, html_code)
    changed = (CodePin(CODE_PATHS[0], "0" * 64), html_code[1])
    second = extract_html(body, p, s, changed)
    assert isinstance(first, HtmlEvidenceObservation) and isinstance(
        second, HtmlEvidenceObservation
    )
    assert first.view.generated_view_sha256 != second.view.generated_view_sha256
    refused(
        extract_html(body, p, replace(s, profile_version="v99"), html_code),
        "UNSUPPORTED_HTML_PROFILE",
    )
    refusal = extract_html(body, p, s, ())
    assert refusal == extract_html(body, p, s, ())
    refused(refusal, "EXTRACTOR_CODE_LINK_MISMATCH")


def test_rs2_t26_bw_invented_synthetic_only(html_code):
    result = parsed(spec=bw_spec(), code=html_code)
    assert isinstance(result, HtmlEvidenceObservation) and result.parsed_amount_text == "7,319"
    assert result.specification.reference_month == "2031-05"
    assert "SYNTHETIC_TEST_ONLY" in result.specification.issuer_name


def test_rs2_t26_bw_synthetic_explicit_reader(html_code, tmp_path):
    body, p, s = material(spec=bw_spec())
    root = tmp_path / "SYNTHETIC_TEST_ONLY_bw"
    p = write_source(root, body)
    result = inspect_issuer_html(root, p, s, html_code)
    assert result.status == "DOCUMENT_CONTENT_OBSERVED_UNADMITTED"
    assert result.reason == "SYNTHETIC_ONLY_NO_REAL_RIGHTS_ADMISSION"
    assert result.body_read_attempts == (p.relative_path,)
    assert isinstance(result.source_body, NotEvaluated)


def test_rs2_t24_root_replaced_during_read_is_refused(html_code, tmp_path, monkeypatch):
    body, p, s = material()
    root = tmp_path / "SYNTHETIC_TEST_ONLY_root"
    p = write_source(root, body)
    original = reader.os.read
    changed = False

    def replace_root(fd, limit):
        nonlocal changed
        chunk = original(fd, limit)
        if not changed:
            changed = True
            root.rename(tmp_path / "retired_root")
            root.mkdir()
            (root / p.relative_path).write_bytes(body)
        return chunk

    monkeypatch.setattr(reader.os, "read", replace_root)
    result = inspect_issuer_html(root, p, s, html_code)
    assert result.reason == "SOURCE_ROOT_CHANGED_DURING_READ"
    assert isinstance(result.source_body, NotEvaluated)


def test_rs2_t24_special_file_refused_before_leaf_open(html_code, tmp_path, monkeypatch):
    body, p, s = material()
    root = tmp_path / "SYNTHETIC_TEST_ONLY_special"
    root.mkdir()
    os.mkfifo(root / p.relative_path)
    original = reader.os.open
    opened = []

    def observe(name, *args, **kwargs):
        opened.append(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(reader.os, "open", observe)
    result = inspect_issuer_html(root, p, s, html_code)
    assert result.reason == "UNSAFE_SOURCE_PATH"
    assert p.relative_path not in opened


@pytest.mark.parametrize(
    "kind", ["external", "real_role", "known_hash", "known_filename", "fake_approval"]
)
def test_rs2_t27_bw_real_unconditionally_disabled(html_code, tmp_path, monkeypatch, kind):
    body, p, s = material(spec=bw_spec())
    if kind in ("external", "fake_approval"):
        s = replace(s, classification="OWNER_SUPPLIED_EXTERNAL")
    elif kind == "real_role":
        s = replace(s, source_role="BUSINESS_WIRE")
    elif kind == "known_hash":
        p = replace(p, sha256=BW_SHA)
    else:
        p = replace(p, relative_path="UMC Reports Sales for September 2026.html")

    def forbidden(*args):
        raise AssertionError("No BW body I/O")

    monkeypatch.setattr(reader, "_open_root", forbidden)
    metadata = rights_description(p, s, html_code, approval_ref="PERMITTED")
    result = inspect_issuer_html(tmp_path, p, s, html_code, metadata)
    assert (
        result.status == result.reason == "BUSINESS_WIRE_REAL_BODY_DISABLED"
        and result.body_read_attempts == ()
    )
    refused(extract_html(body, p, s, html_code), "BUSINESS_WIRE_REAL_BODY_DISABLED")


def test_rs2_t28_related_story_and_script_never_target(html_code):
    text = bw_html().replace(
        "SYNTHETIC_TEST_ONLY April 2031 unrelated", "SYNTHETIC_TEST_ONLY evil unrelated 99,999"
    )
    result = parsed(text, bw_spec(), html_code)
    assert isinstance(result, HtmlEvidenceObservation) and result.parsed_amount_text == "7,319"
    assert "99,999" not in result.view.canonical_view_bytes.decode()
    assert "script" not in {loc.purpose for loc in result.claim_locators}


@pytest.mark.parametrize(
    "kind",
    [
        "root",
        "title",
        "row",
        "header",
        "unit",
        "scope",
        "span",
        "hidden",
        "duplicate_title",
        "duplicate_unit",
        "duplicate_scope",
    ],
)
def test_rs2_t29_bw_critical_duplicates_and_abuse(html_code, kind):
    text = bw_html()
    if kind == "root":
        text = text.replace("</main>", '<div id="bw-release-story"></div></main>')
    elif kind == "title":
        text = text.replace("Monthly revenue: May 2031", "Monthly revenue: April 2031", 1)
    elif kind == "row":
        target = row(["May", "7,319", "6,208", "1,111", "17.90%"])
        text = text.replace(target, target * 2, 1)
    elif kind == "header":
        header = row(["Period", "2031", "2030", "Y/Y Change", "Y/Y (%)"])
        text = text.replace(header, header * 2, 1)
    elif kind == "unit":
        text = text.replace("Synthetic scale: NTD thousands.", "Synthetic scale: USD units.", 1)
    elif kind == "scope":
        text = text.replace("Synthetic scope: consolidated.", "Synthetic scope: standalone.", 1)
    elif kind == "span":
        text = text.replace('colspan="5"', 'colspan="6"', 1)
    elif kind.startswith("duplicate_"):
        value = {
            "duplicate_title": "Monthly revenue: May 2031",
            "duplicate_unit": "Synthetic scale: NTD thousands.",
            "duplicate_scope": "Synthetic scope: consolidated.",
        }[kind]
        repeated = row([value], attrs=' colspan="5"')
        text = text.replace(repeated, repeated * 2, 1)
    else:
        text = text.replace("<td>7,319</td>", "<td hidden>7,319</td>", 1)
    refused(parsed(text, bw_spec(), html_code))


@pytest.mark.parametrize(
    "style",
    [
        "display: /*comment*/ none",
        "d\\69splay:none",
        "background:url(javascript:bad())",
        "width:expression(bad())",
    ],
)
def test_rs2_t18_ambiguous_or_active_css_refused(html_code, style):
    text = sec_html().replace("<td>8,642</td>", f'<td style="{style}">8,642</td>')
    refused(parsed(text, code=html_code))


def test_rs2_t18_comment_inside_critical_amount_refuses(html_code):
    refused(
        parsed(
            sec_html().replace("<td>8,642</td>", "<td>8,<!--instruction-->642</td>"), code=html_code
        )
    )


def test_rs2_t25_bool_pin_and_fake_rights_schema_refuse(html_code, tmp_path):
    _, p, s = material()
    data = json.loads(rights_description(p, s, html_code))
    data["source_pin"]["byte_length"] = True
    result = inspect_issuer_html(tmp_path, p, s, html_code, json.dumps(data).encode())
    assert result.reason == "INVALID_RIGHTS_PIN_LENGTH" and result.body_read_attempts == ()


def test_rs2_t30_synthetic_reader_no_writes_or_promotion(html_code, tmp_path):
    body, p, s = material()
    root = tmp_path / "SYNTHETIC_TEST_ONLY"
    p = write_source(root, body)
    before = {f.name: f.read_bytes() for f in root.iterdir()}
    result = inspect_issuer_html(root, p, s, html_code)
    assert result.status == "DOCUMENT_CONTENT_OBSERVED_UNADMITTED"
    observation = result.observation
    assert isinstance(observation, HtmlEvidenceObservation)
    assert not result.admission_eligible and not observation.admission_eligible
    assert (
        observation.mapping == "MAPPING_UNRESOLVED"
        and observation.native_transport == "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA"
    )
    assert observation.agent_observation == "NOT_PRODUCED"
    assert all(isinstance(value, NotEvaluated) for _, value in observation.owner_results)
    assert before == {f.name: f.read_bytes() for f in root.iterdir()}
    assert not (root / "support.json").exists() and not (root / "manifest.json").exists()


def test_rs2_t31_pure_syntax_and_outer_code_observation(html_code):
    root = Path(__file__).resolve().parents[3]
    assert tuple(p.path for p in html_code) == CODE_PATHS
    for p in html_code:
        body = (root / p.path).read_bytes()
        assert sha256(body).hexdigest() == p.sha256
        ast.parse(body)
    tree = ast.parse((root / CODE_PATHS[0]).read_text())
    identifiers = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not identifiers & {"open", "Path", "os", "subprocess", "requests", "socket", "pytest"}


def test_rs2_t32_all_protected_tracked_and_wu00_pins():
    from b01_preservation import verify_preserved
    from rs2_inputs import TRACKED_PINS, WU00_PINS

    root = Path(__file__).resolve().parents[3]
    assert len(TRACKED_PINS) == 63 and len(WU00_PINS) == 15
    for path, length, digest in (*TRACKED_PINS, *WU00_PINS):
        verify_preserved(root, path, length, digest)
