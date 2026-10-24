"""Explicit approved fixed-source run; no real data fixture or source copying.

Opt in with RS3F_APPROVED_REAL=1. This test-only switch requests execution; it
grants no permission and cannot bypass any controller preflight check.
"""

import builtins
import json
import os
import socket
from dataclasses import FrozenInstanceError, asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

import pit_research_lab.domain.sec_real_closure as controller
from pit_research_lab.domain.contracts import ContractError
from pit_research_lab.domain.issuer_html_extraction import HtmlEvidenceObservation
from pit_research_lab.domain.market_row_selection import SelectedSourceRow, select_market_row
from pit_research_lab.domain.sec_financial_diagnostic import (
    GOV_PIN,
    MANIFEST_PIN,
    SEC_PIN,
    VIEW_SHA,
    FinancialDiagnostic,
    build_diagnostic,
)
from pit_research_lab.domain.source_intake import decode_manifest, validate_source_manifest


@pytest.mark.skipif(
    os.environ.get("RS3F_APPROVED_REAL") != "1", reason="Explicit approved input run only"
)
def test_t02_t04_t11_t14_t17_t25_real_sec_replay_and_diagnostic(monkeypatch):
    actual_opens = []
    reads = []
    original_open = os.open
    original_builtin_open = builtins.open
    original_read = controller._read_pinned
    cached_government = {}

    def check_path(name):
        text = os.fspath(name) if isinstance(name, (str, bytes, os.PathLike)) else ""
        if isinstance(text, bytes):
            text = os.fsdecode(text)
        assert "_files" not in text and "UMC Reports Sales for September 2026.html" not in text
        return text

    def observe_open(name, *args, **kwargs):
        text = check_path(name)
        if text == "umc-ex99.htm":
            actual_opens.append(text)
        return original_open(name, *args, **kwargs)

    def observe_builtin(name, *args, **kwargs):
        check_path(name)
        return original_builtin_open(name, *args, **kwargs)

    def observe_read(root, pin):
        reads.append((str(root), pin))
        if str(root) == controller.SOURCE_ROOT:
            assert pin == SEC_PIN
        body = original_read(root, pin)
        if pin in (GOV_PIN, MANIFEST_PIN):
            cached_government[pin.relative_path] = body
        return body

    def no_network(*args, **kwargs):
        pytest.fail("No network is authorized")

    monkeypatch.setattr(os, "open", observe_open)
    monkeypatch.setattr(builtins, "open", observe_builtin)
    monkeypatch.setattr(controller, "_read_pinned", observe_read)
    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    cutoff = "2026-09-30T23:59:59+08:00"
    first = controller.run_sec_diagnostic(
        cutoff=cutoff, audit_label_non_pit="audit clock A NON_PIT"
    )
    assert first.status == "IMPLEMENTED_PROVISIONAL", first.reason
    second = controller.run_sec_diagnostic(
        cutoff=cutoff, audit_label_non_pit="audit clock B NON_PIT"
    )
    assert second.status == "IMPLEMENTED_PROVISIONAL", second.reason
    assert actual_opens == ["umc-ex99.htm", "umc-ex99.htm"]
    for run in (first, second):
        assert run.source_use == controller.APPROVAL_STATUS
        assert len(run.body_read_attempts) == 1
        first_body = next(e.sequence for e in run.events if e.stage == "SEC_SOURCE_BODY_READ")
        verified = [
            e
            for e in run.events
            if e.stage == "PRE_SOURCE_BODY_OPEN" and e.state == "READ_STABLE_PIN_MATCH"
        ]
        assert len(verified) == 9 and max(e.sequence for e in verified) < first_body
        approved = next(e for e in run.events if e.state == controller.APPROVAL_STATUS)
        assert approved.sequence < first_body
    assert reads == [(Path(d.root).as_posix(), d.pin) for d in controller.DOCUMENTS] + [
        (controller.GOVERNMENT_ROOT, MANIFEST_PIN),
        (controller.SOURCE_ROOT, SEC_PIN),
        (controller.GOVERNMENT_ROOT, GOV_PIN),
    ] + [(Path(d.root).as_posix(), d.pin) for d in controller.DOCUMENTS] + [
        (controller.GOVERNMENT_ROOT, MANIFEST_PIN),
        (controller.SOURCE_ROOT, SEC_PIN),
        (controller.GOVERNMENT_ROOT, GOV_PIN),
    ]
    obs = first.observation
    diagnostic = first.diagnostic
    assert isinstance(obs, HtmlEvidenceObservation) and isinstance(diagnostic, FinancialDiagnostic)
    assert isinstance(second.observation, HtmlEvidenceObservation)
    assert isinstance(second.diagnostic, FinancialDiagnostic)
    assert obs.source_pin == SEC_PIN and obs.parsed_amount_text == "25,350,431"
    assert obs.original_amount_lexeme == "25,350,431" and obs.unit_heading == "NT$ Thousand"
    assert obs.view.generated_view_sha256 == VIEW_SHA
    assert sha256(obs.view.canonical_view_bytes).hexdigest() == VIEW_SHA != SEC_PIN.sha256
    assert obs.view.canonical_view_bytes == second.observation.view.canonical_view_bytes
    assert {c.reason for c in obs.exclusions} == {
        "EXCLUDED_YEAR_2025_OR_PRIOR_YEAR",
        "EXCLUDED_YEAR_TO_DATE",
    }
    assert len(obs.claim_locators) == 7
    assert all(loc.exact_byte_span == "BYTE_SPAN_NOT_ESTABLISHED" for loc in obs.claim_locators)
    assert all(loc.original_element_start_tag_byte_offset >= 0 for loc in obs.claim_locators)
    assert diagnostic.serialize() == second.diagnostic.serialize()
    assert diagnostic.sha256 == second.diagnostic.sha256
    assert diagnostic.research_ref == second.diagnostic.research_ref
    assert first.audit_label_non_pit != second.audit_label_non_pit
    assert diagnostic.government.row_ordinal == 267
    assert diagnostic.government.company_code == "2303"
    assert diagnostic.government.reference_month == "2026-09"
    assert diagnostic.government.amount == 25350431
    assert diagnostic.government.amount_lexeme == '"25350431"'
    assert diagnostic.comparison.state == "EQUAL"
    sec_fields = {
        f.field_name: f for f in diagnostic.fields if f.source_role == "SEC_PUBLIC_FILING"
    }
    for name in (
        "TWSE_code",
        "unaudited",
        "consolidated",
        "canonical_basis_equivalence",
        "historical_publication_availability",
    ):
        assert (
            sec_fields[name].status == "NOT_ESTABLISHED_BY_SEC" and sec_fields[name].value is None
        )
    assert sec_fields["document_stated_date"].status == "OBSERVED_NON_PIT"
    assert all(c.state == "UNRESOLVED" and c.reason for c in diagnostic.claims)
    assert len(diagnostic.claims) == 8 and diagnostic.ic3_r01 == "P2_OPEN"
    assert diagnostic.mapping == "MAPPING_UNRESOLVED" and diagnostic.diagnostic_only
    assert not diagnostic.trusted_pit and not diagnostic.admission_eligible
    assert (
        diagnostic.cutoff_availability == "UNRESOLVED"
        and diagnostic.historic_PIT == "NOT_ESTABLISHED"
    )
    assert diagnostic.source_authentication == "NOT_ESTABLISHED"
    assert diagnostic.agent_observation == "NOT_PRODUCED" and diagnostic.golden == "NOT_GRANTED"
    assert all(state.startswith("NOT_EVALUATED") for _, state in diagnostic.owner_results)
    with pytest.raises(FrozenInstanceError):
        diagnostic.mapping = "MAPPED"
    # T18: recompute the genuine IC1 selection, then explicitly reject forged/stale DTOs.
    mb = cached_government[MANIFEST_PIN.relative_path]
    raw = cached_government[GOV_PIN.relative_path]
    manifest = decode_manifest(mb)
    intake = validate_source_manifest(manifest, raw, None)
    spec = controller.SEC_SPEC
    from pit_research_lab.domain.market_row_selection import FullMarketSelectionSpec

    selected = select_market_row(intake, FullMarketSelectionSpec()).selected
    assert isinstance(selected, SelectedSourceRow)
    assert (
        build_diagnostic(
            obs, mb, raw, first.code_context, claimed_selection=selected, cutoff=cutoff
        )
        == diagnostic
    )
    for fake in (
        replace(selected, extracted=replace(selected.extracted, amount=1)),
        replace(selected, extracted=replace(selected.extracted, row_ordinal=266)),
        replace(selected, extracted=replace(selected.extracted, amount=True)),
    ):
        with pytest.raises(ContractError, match="FORGED_OR_STALE_SELECTION"):
            build_diagnostic(obs, mb, raw, first.code_context, claimed_selection=fake)
    # Observation DTO alterations cannot reuse the genuine fixed view as a receipt.
    for fake in (
        replace(obs, parsed_amount_text="25,350,432"),
        replace(obs, unit_heading="USD units"),
        replace(obs, specification=replace(spec, reference_month="2026-08")),
        replace(obs, original_amount_lexeme="forged"),
        replace(obs, claim_locators=obs.claim_locators[:-1]),
    ):
        with pytest.raises(ContractError):
            build_diagnostic(fake, mb, raw, first.code_context)
    with pytest.raises(ContractError, match="SOURCE_PIN_MISMATCH"):
        build_diagnostic(obs, mb, raw[:-1] + b"X", first.code_context)
    # Optional evidence sink is constrained to /tmp, stores derived diagnostics only.
    sink = os.environ.get("RS3F_RUN_EVIDENCE")
    if sink:
        path = Path(sink)
        assert path.is_absolute() and path.parts[:2] == ("/", "tmp") and ".." not in path.parts
        payload = {
            "disposition": first.status,
            "rights_status": first.source_use,
            "runs": [
                {
                    "events": [asdict(e) for e in r.events],
                    "body_read_attempts": r.body_read_attempts,
                }
                for r in (first, second)
            ],
            "actual_sec_leaf_open_count": len(actual_opens),
            "bw_body_read_count": 0,
            "all_document_reads": [{"root": root, "pin": asdict(pin)} for root, pin in reads],
            "extraction_view": json.loads(obs.view.canonical_view_bytes),
            "extraction_view_sha256": VIEW_SHA,
            "extraction_view_byte_length": len(obs.view.canonical_view_bytes),
            "diagnostic": json.loads(diagnostic.serialize()),
            "diagnostic_sha256": diagnostic.sha256,
            "diagnostic_byte_length": len(diagnostic.serialize()),
            "research_ref": diagnostic.research_ref,
            "two_run_view_bytes_equal": True,
            "two_run_diagnostic_bytes_equal": True,
            "audit_only_label_changed": True,
            "selection_forgery_and_observation_tampering_checks": "PASS",
        }
        with path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
