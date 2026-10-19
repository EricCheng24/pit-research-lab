"""Static fixture checks, not Golden case/tier execution."""

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
from wu00_inputs import (
    decode,
    integrity_stimulus,
    literal_bytes,
    load_catalogue,
    load_deltas,
    materialize,
    selected_receipt_pages,
    validate_catalogue,
    validate_receipt_pages,
)

DATA = Path(__file__).parent / "data"


def test_approved_literal_bytes_and_states():
    world = load_catalogue()
    bindings = json.loads((DATA / "provenance" / "artifact_bindings.json").read_text())
    assert world["inventory_sha256"] == next(
        a["sha256"] for a in bindings["authoring_sources"] if a["alias"] == "INV2"
    )
    for key, field in [
        ("raw", "raw_assets"),
        ("pages", "page_assets"),
        ("receipts", "receipt_assets"),
    ]:
        pins = {r["id"]: r for r in bindings["approved_literal_pins"][key]}
        assert set(pins) == {a["id"] for a in world[field]}
        for asset in world[field]:
            data = literal_bytes(asset)
            assert len(data) == pins[asset["id"]]["byte_length"]
            assert hashlib.sha256(data).hexdigest() == pins[asset["id"]]["sha256"]
    receipts = [decode(a["payload"]) for a in world["receipt_assets"]]
    assert Counter(r["search_state"] for r in receipts) == {
        "COMPLETED": 21,
        "NOT_PERFORMED": 1,
        "FAILED": 1,
    }
    empty = next(r for r in receipts if r.get("receipt_id") == "RCPT-B-APR-COMPLETE-EMPTY")
    assert empty["exact_member_ids"] == [] and empty["terminal"] == "END_OF_RESULTS"
    for receipt in receipts:
        assert receipt["source_publication_timezone"] is None
        assert receipt["source_publication_precision"] is None


def test_structural_integrity_negatives():
    world = load_catalogue()
    world["raw_assets"][2]["payload"] += " "
    with pytest.raises(ValueError, match="literal integrity"):
        validate_catalogue(world)
    world = load_catalogue()
    world["graph_edges"][0]["to"] = "MISSING"
    with pytest.raises(ValueError, match="dangling"):
        validate_catalogue(world)
    with pytest.raises(ValueError, match="duplicate"):
        decode('{"x":1,"x":2}')
    for invalid in ["-0", "1.0", "1e2", str(2**63)]:
        with pytest.raises(ValueError):
            decode(invalid)


def test_graph_nodes_closure_and_separate_witnesses():
    world = load_catalogue()
    assert len(world["chains"]) == 19
    assert len({e["id"] for e in world["graph_edges"]}) == 170
    for event in world["publication_events"].values():
        assert set(event) == {
            "event_id",
            "event_kind",
            "source_id",
            "issuer_id",
            "content_version_id",
        }
    assert world["supports"]["SUP-ORD1-PUB"]["target_id"] == "A-ORD-01"
    assert world["supports"]["SUP-JUN1-PUB"]["target_id"] == "A-JUN-01"
    for support in world["supports"].values():
        bindings = world["evidence"][support["evidence_id"]]["bindings"]
        assert any(
            all(
                binding[k] == support[k]
                for k in [
                    "target_kind",
                    "target_id",
                    "subject_scope_ids",
                    "content_version_id",
                    "fragment_selector",
                ]
            )
            for binding in bindings
        )
    raw_ids = {"REP-RAW-" + a["id"] for a in world["raw_assets"]}
    catalogue_sets = {
        "assertion_ids": set(world["assertions"]),
        "relation_ids": set(world["relations"]),
        "report_ids": set(world["reports"]),
        "content_version_ids": set(world["content_versions"]),
        "raw_representation_ids": raw_ids,
        "evidence_ids": set(world["evidence"]),
        "support_ids": set(world["supports"]),
        "publication_event_ids": set(world["publication_events"]),
        "time_proof_ids": set(world["time_proofs"]),
        "observation_ids": set(world["observations"]),
        "lead_ids": set(world["leads"]),
        "subject_ids": set(world["subjects"]),
    }
    for asset in world["receipt_assets"]:
        for field, values in decode(asset["payload"])["custody_closure"].items():
            assert values == sorted(values) and len(values) == len(set(values))
            if field in catalogue_sets:
                assert set(values) <= catalogue_sets[field], (asset["id"], field)


@pytest.mark.parametrize("case_id", [r["case_id"] for r in load_deltas()])
def test_each_delta_is_fresh_and_has_no_catalogue_capability(case_id):
    first = materialize(case_id)
    second = materialize(case_id)
    assert first == second and first is not second
    assert "sealed_source_catalogue" not in first
    first["grid"][0][1] = "CORRUPTED"
    first["active_discovery_membership"]["facts"]["assertions"].clear()
    assert second == materialize(case_id)


@pytest.mark.parametrize("case_id", [f"A03-C{i:02}" for i in range(1, 7)] + ["A05-C04"])
def test_active_temporal_paths_cannot_recover_old_revenue_proof(case_id):
    bundle = materialize(case_id)
    facts = bundle["active_discovery_membership"]["facts"]
    assert "EVID-JUN1-TIME" not in facts["evidence"]
    assert "SUP-JUN1-PUB" not in facts["supports"]
    assert "TP-JUN1" not in facts["time_proofs"]
    assert facts["supports"]["SUP-ORD1-PUB"]["target_id"] == "A-ORD-01"
    assert "REP-RAW-CV-JUN-01" in facts["raw_assets"]
    assert "PUB-JUN-01" in facts["publication_events"]
    if case_id == "A03-C06":
        proof = facts["time_proofs"]["TP-JUN1-A03-C06"]
        assert proof["timezone"] is None and proof["offset"] is None
    if case_id == "A05-C04":
        assert "SUP-JUN-REV" in facts["supports"]


@pytest.mark.parametrize(
    "case_id", ["A01-C02", "A01-C03", "A01-C04", "A02-C02", "A03-C07", "A04-C03"]
)
def test_auxiliary_inputs_do_not_expand_discovery(case_id):
    bundle = materialize(case_id)
    facts = bundle["active_discovery_membership"]["facts"]
    assert set(facts["assertions"]) == {"A-APR-01", "A-MAY-01", "A-JUN-01", "A-ORD-01"}
    assert bundle["auxiliary_comparison_inputs"]
    assert bundle["active_discovery_membership"]["receipts"][0]["id"] == "RCPT-E0"


def test_intended_invalidity_and_zero_are_preserved():
    spec_case = materialize("A08-C06")
    ref = spec_case["request"]["spec_ref"]
    assert ref == "SPEC-FS-Q2-1-A08-C06"
    assert spec_case["feature_specs"][ref]["months"] == ["APR", "MAY", "JUN", "JUN"]
    assert spec_case["feature_specs"][ref]["require_unique_months"] is True
    individual = materialize("A08-C05")["active_discovery_membership"]["facts"]
    assert individual["assertions"]["A-MAY-IND-A08-C05"]["reporting_scope"] == "individual"
    zero = materialize("A11-C01")["active_discovery_membership"]["facts"]["assertions"][
        "A-APR-ZERO-A11-C01"
    ]["value"]
    assert type(zero) is int and zero == 0
    missing = materialize("A11-C04")
    assert missing["request"]["spec_ref"] not in missing["feature_specs"]
    for case in ["A08-C03", "A11-C02"]:
        bundle = materialize(case)
        assert "A-MAY-01" not in bundle["active_discovery_membership"]["facts"]["assertions"]
        assert len(bundle["active_discovery_membership"]["receipts"]) == 2


def test_contexts_early_correction_dependency_and_integrity_fault():
    baseline = materialize("A05-C01")
    early = materialize("A05-C05")
    assert baseline["request"]["evidence_set_ref"] == "E0"
    assert early["request"]["evidence_set_ref"] == "E2"
    assert early["request"]["logical_context_designation"] == "M3"
    assert "A-JUN-EARLY-CORR" not in baseline["active_discovery_membership"]["facts"]["assertions"]
    assert (
        early["active_discovery_membership"]["facts"]["assertions"]["A-JUN-EARLY-CORR"]["value"]
        == 305
    )
    replay = materialize("A12-C01")
    new = materialize("A12-C04")
    assert replay["request"]["decision_cutoff"] == new["request"]["decision_cutoff"]
    assert (
        replay["request"]["logical_context_designation"]
        != new["request"]["logical_context_designation"]
    )
    assert "A-JUN-02" in new["active_discovery_membership"]["facts"]["assertions"]
    assert len(new["grid"]) == 4 and new["universe"]["issuers"] == ["SYN-A", "SYN-B"]
    fit = materialize("A09-C02")
    assert "A-JUN-02" not in fit["active_discovery_membership"]["facts"]["assertions"]
    assert "A-JUN-02" in fit["dependency_only_or_fault_schedule_inputs"][0]["assertions"]
    fault = materialize("A12-C05")["dependency_only_or_fault_schedule_inputs"][0]
    before, after = fault["representations"]
    assert before["byte_length"] == after["byte_length"] == 118
    assert before["sha256"] != after["sha256"]
    assert fault["required_raw_ref"]["byte_length"] == 542
    assert fault["preserve_verified_pin"] is True


def test_source_attempt_is_not_a_completed_receipt_or_empty_result():
    for cid, state in [("A06-C01", "NOT_PERFORMED"), ("A06-C06", "FAILED")]:
        bundle = materialize(cid)
        records = bundle["active_discovery_membership"]["receipts"]
        assert len(records) == 1
        body = decode(records[0]["payload"])
        assert body["search_state"] == state and body["terminal"] is None
        assert not body["page_sequence"] and body["completion_at"] is None
        if state == "FAILED":
            assert body["record_kind"] == "search_attempt" and "receipt_id" not in body


def test_collision_is_distinct_from_digest_mismatch():
    collision = integrity_stimulus("RP01-T01")
    mismatch = integrity_stimulus("RP01-T02")
    data = literal_bytes(collision["actual_payload"])
    assert collision["request"]["candidate_declared_sha256"] == hashlib.sha256(data).hexdigest()
    assert mismatch["request"]["declared_sha256"] != hashlib.sha256(data).hexdigest()
    assert collision["verified_representation"] == mismatch["verified_representation"]
    assert len(collision["future_input_description"]["required_representation_refs"]) == 2
    assert materialize("A06-C02")["active_discovery_membership"]["facts"]["subjects"]["SUB-B-APR"]


def test_audit_mutations_leave_source_facts_and_population_unchanged():
    original = materialize("A05-C01")
    for cid in ["A10-C01", "A10-C02", "A10-C03", "A10-C04"]:
        changed = materialize(cid)
        assert changed["active_discovery_membership"] == original["active_discovery_membership"]
        assert changed["grid"] == original["grid"] and changed["universe"] == original["universe"]
        assert changed["audit_annotations"]
    assert copy.deepcopy(original) == original


def assert_receipt_page_closure(receipts, pages):
    """Independent check of returned bytes/bindings, with no harness catalogue lookup."""
    by_id = {page["id"]: page for page in pages}
    assert len(by_id) == len(pages)
    seen = []
    for asset in receipts:
        receipt_data = asset["payload"].encode()
        assert len(receipt_data) == asset["byte_length"]
        assert hashlib.sha256(receipt_data).hexdigest() == asset["sha256"]
        receipt = json.loads(receipt_data)
        if receipt["search_state"] != "COMPLETED":
            assert receipt["page_sequence"] == [] and receipt["terminal"] is None
            assert receipt["completion_at"] is None
            continue
        assert receipt["page_sequence"] and receipt["terminal"] == "END_OF_RESULTS"
        members = []
        for index, binding in enumerate(receipt["page_sequence"]):
            page = by_id[binding["page_id"]]
            data = page["payload"].encode()
            body = json.loads(data)
            assert page["encoding"] == "utf8-literal"
            assert page["id"] == body["page_id"] == binding["page_id"]
            assert len(data) == page["byte_length"] == binding["byte_length"]
            assert hashlib.sha256(data).hexdigest() == page["sha256"] == binding["sha256"]
            assert body["query_id"] == receipt["query_id"]
            assert body["terminal"] == binding["terminal"]
            assert body["next_page"] == binding["next_page"]
            if index == len(receipt["page_sequence"]) - 1:
                assert body["next_page"] is None and body["terminal"] == "END_OF_RESULTS"
            else:
                assert body["next_page"] == receipt["page_sequence"][index + 1]["page_id"]
                assert body["terminal"] is None
            members.extend(body["members"])
            if page["id"] not in seen:
                seen.append(page["id"])
        assert len(members) == len(set(members))
        assert sorted(members) == receipt["exact_member_ids"]
    assert [p["id"] for p in pages] == seen


@pytest.mark.parametrize("case_id", [r["case_id"] for r in load_deltas()])
def test_all_returned_receipt_pages_are_complete_scoped_and_isolated(case_id, monkeypatch):
    first = materialize(case_id)
    second = materialize(case_id)
    active = first["active_discovery_membership"]
    assert_receipt_page_closure(active["receipts"], active["pages"])
    for pending in first["dependency_only_or_fault_schedule_inputs"]:
        if pending.get("kind") == "pending_receipt_append":
            assert_receipt_page_closure([pending["receipt"]], pending["pages"])
    # The public verifier must work after catalogue access has become unavailable.
    with monkeypatch.context() as context:

        def unavailable():
            raise AssertionError("catalogue lookup forbidden")

        context.setattr("wu00_inputs.load_catalogue", unavailable)
        validate_receipt_pages(active["receipts"], active["pages"])
    if active["pages"]:
        active["pages"][0]["payload"] = "CORRUPTED"
    active["receipts"][0]["payload"] = "CORRUPTED"
    assert second == materialize(case_id)
    assert "sealed_source_catalogue" not in second


@pytest.mark.parametrize(
    "case_id,expected",
    [
        ("A05-C01", ["PAGE-E0-1", "PAGE-MAY-E0-1", "PAGE-B-APR-E0-1"]),
        ("A05-C02", ["PAGE-E1-1", "PAGE-B-APR-E1-1"]),
        ("A05-C03", ["PAGE-E1-1", "PAGE-B-APR-E1-1"]),
        ("A08-C03", ["PAGE-E0-A08-C03-1", "PAGE-MAY-A08-C03-1"]),
        ("A11-C02", ["PAGE-E0-A11-C02-1", "PAGE-MAY-A11-C02-1"]),
        ("A06-C02", ["PAGE-B-APR-E0-1"]),
        ("A06-C01", []),
        ("A06-C06", []),
    ],
)
def test_representative_page_sets_and_original_bytes(case_id, expected):
    bundle = materialize(case_id)
    active = bundle["active_discovery_membership"]
    assert [p["id"] for p in active["pages"]] == expected
    assert_receipt_page_closure(active["receipts"], active["pages"])
    if case_id == "A05-C01":
        page = active["pages"][0]
        assert len(page["payload"].encode()) == 171
        assert page["sha256"] == "0f7321040028fd9bd5100070ce332217c209ca874069f9f2c23e45ad96293cb8"
        assert json.loads(page["payload"])["members"] == [
            "A-APR-01",
            "A-JUN-01",
            "A-MAY-01",
            "A-ORD-01",
        ]
    if case_id in {"A05-C02", "A05-C03"}:
        assert "A-JUN-02" in json.loads(active["pages"][0]["payload"])["members"]
        assert "PAGE-E0-1" not in expected
    if case_id in {"A08-C03", "A11-C02"}:
        assert "A-MAY-01" not in active["facts"]["assertions"]
        assert json.loads(active["pages"][1]["payload"])["members"] == []
    if case_id == "A06-C02":
        assert json.loads(active["pages"][0]["payload"])["members"] == []


@pytest.mark.parametrize("case_id", ["A06-C03", "A08-C04", "A11-C03"])
def test_page_material_leads_do_not_create_content_or_time(case_id):
    active = materialize(case_id)["active_discovery_membership"]
    assert "L-ALT" in json.loads(active["pages"][0]["payload"])["members"]
    lead = active["facts"]["leads"]["L-ALT"]
    assert lead["content_version_ref"] is None and lead["source_time_proof_ref"] is None


def test_pending_receipt_page_is_separate_from_sealed_replay():
    original = materialize("A12-C01")
    append = materialize("A12-C08")
    assert append["active_discovery_membership"] == original["active_discovery_membership"]
    assert append["universe"] == original["universe"] and append["grid"] == original["grid"]
    pending = append["dependency_only_or_fault_schedule_inputs"][0]
    assert pending["receipt"]["id"] == "RCPT-UNRELATED-SYN-B-MAR-A12-C08"
    assert [p["id"] for p in pending["pages"]] == ["PAGE-UNRELATED-B-MAR-1"]
    assert_receipt_page_closure([pending["receipt"]], pending["pages"])
    pending["pages"][0]["payload"] = "CORRUPTED"
    assert (
        materialize("A12-C08")["active_discovery_membership"]
        == original["active_discovery_membership"]
    )
    assert (
        materialize("A12-C08")["dependency_only_or_fault_schedule_inputs"][0]["pages"][0]["payload"]
        != "CORRUPTED"
    )
    writer = materialize("A12-C02")["dependency_only_or_fault_schedule_inputs"][0]
    assert writer["kind"] == "pending_append" and "pages" not in writer and "receipt" not in writer


def replace_literal_body(asset, body):
    """Rehash only cloned in-memory negative stimuli; never alter approved fixture files."""
    asset["payload"] = json.dumps(body, separators=(",", ":"))
    data = asset["payload"].encode()
    asset.update(byte_length=len(data), sha256=hashlib.sha256(data).hexdigest())


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "body",
        "hash",
        "length",
        "binding_hash",
        "query",
        "page_id",
        "terminal",
        "next_page",
        "duplicate_members",
        "extra",
        "duplicate_page",
    ],
)
def test_scoped_page_verifier_rejects_missing_corrupt_foreign_or_extra_inputs(fault):
    active = materialize("A05-C01")["active_discovery_membership"]
    page = active["pages"][0]
    if fault == "missing":
        active["pages"].pop(0)
    elif fault == "body":
        page["payload"] += " "
    elif fault == "hash":
        page["sha256"] = "0" * 64
    elif fault == "length":
        page["byte_length"] += 1
    elif fault == "extra":
        active["pages"].append(materialize("A05-C02")["active_discovery_membership"]["pages"][0])
    elif fault == "duplicate_page":
        active["pages"].append(copy.deepcopy(page))
    else:
        receipt = json.loads(active["receipts"][0]["payload"])
        body = json.loads(page["payload"])
        if fault == "binding_hash":
            receipt["page_sequence"][0]["sha256"] = "0" * 64
        else:
            if fault == "query":
                body["query_id"] = "FOREIGN-QUERY"
            elif fault == "page_id":
                body["page_id"] = "FOREIGN-PAGE"
            elif fault == "terminal":
                body["terminal"] = "BROKEN"
                receipt["page_sequence"][0]["terminal"] = "BROKEN"
            elif fault == "next_page":
                body["next_page"] = "PAGE-E1-1"
                receipt["page_sequence"][0]["next_page"] = "PAGE-E1-1"
            elif fault == "duplicate_members":
                body["members"].append(body["members"][0])
            replace_literal_body(page, body)
            receipt["page_sequence"][0].update(
                byte_length=page["byte_length"], sha256=page["sha256"]
            )
        replace_literal_body(active["receipts"][0], receipt)
    with pytest.raises(ValueError):
        validate_receipt_pages(active["receipts"], active["pages"])


def test_page_resolver_rejects_missing_catalogue_page_and_deduplicates_shared_identity():
    world = load_catalogue()
    receipt = next(a for a in world["receipt_assets"] if a["id"] == "RCPT-E0")
    missing = copy.deepcopy(world)
    missing["page_assets"] = [p for p in missing["page_assets"] if p["id"] != "PAGE-E0-1"]
    with pytest.raises(ValueError, match="missing referenced page"):
        selected_receipt_pages(missing, [receipt])
    other = copy.deepcopy(receipt)
    body = json.loads(other["payload"])
    other["id"] = body["receipt_id"] = "CASE-LOCAL-SHARED-PAGE-RECEIPT"
    replace_literal_body(other, body)
    pages = selected_receipt_pages(world, [receipt, other])
    assert [p["id"] for p in pages] == ["PAGE-E0-1"]
    assert_receipt_page_closure([receipt, other], pages)


def test_page_sequence_order_is_not_catalogue_order_and_duplicates_are_not_collapsed():
    # An in-memory verifier probe; no accepted corpus page or receipt is changed.
    active = materialize("A05-C01")["active_discovery_membership"]
    receipt = copy.deepcopy(active["receipts"][0])
    first, second = copy.deepcopy(active["pages"][:2])
    body = json.loads(first["payload"])
    members = body["members"]
    body.update(members=members[:2], next_page="UNIT-PAGE-2", terminal=None)
    replace_literal_body(first, body)
    body.update(
        page_id="UNIT-PAGE-2", members=members[2:], next_page=None, terminal="END_OF_RESULTS"
    )
    second["id"] = "UNIT-PAGE-2"
    replace_literal_body(second, body)
    record = json.loads(receipt["payload"])
    record["page_sequence"] = [
        {
            "page_id": p["id"],
            "byte_length": p["byte_length"],
            "sha256": p["sha256"],
            "next_page": json.loads(p["payload"])["next_page"],
            "terminal": json.loads(p["payload"])["terminal"],
        }
        for p in [first, second]
    ]
    replace_literal_body(receipt, record)
    pages = selected_receipt_pages({"page_assets": [second, first]}, [receipt])
    assert [p["id"] for p in pages] == [first["id"], second["id"]]
    assert_receipt_page_closure([receipt], pages)
    with pytest.raises(ValueError, match="out-of-order"):
        validate_receipt_pages([receipt], list(reversed(pages)))
    body["members"].append(members[0])
    replace_literal_body(second, body)
    record["page_sequence"][1].update(byte_length=second["byte_length"], sha256=second["sha256"])
    replace_literal_body(receipt, record)
    with pytest.raises(ValueError, match="member binding"):
        validate_receipt_pages([receipt], [first, second])


def assert_provider_capture_binding(bundle):
    assert len(bundle["auxiliary_comparison_inputs"]) == 1
    capture = bundle["auxiliary_comparison_inputs"][0]
    assert len(capture["graph_edges"]) == 1
    edge = capture["graph_edges"][0]
    assert edge["id"] == "G-PX-CAPTURE"
    assert edge["from"] == "OBS-P-X-A02-C04"
    assert edge["to"] == "REP-RAW-CV-A02-C04-PX-CAPTURE"
    assert edge["type"] == "provider_lab_capture_only"
    assert edge["evidence"] == "none for issuer publication"
    assert capture["raw_asset"]["id"] == "CV-A02-C04-PX-CAPTURE"
    assert capture["observation"]["observation_id"] == "OBS-P-X-A02-C04"
    assert capture["observation"]["raw_representation_id"] == "REP-RAW-CV-A02-C04-PX-CAPTURE"
    assert capture["observation"]["captured_sha256"] == capture["raw_asset"]["sha256"]
    active = bundle["active_discovery_membership"]["facts"]
    assert all(
        p["content_version_id"] != "CV-A02-C04-PX-CAPTURE" for p in active["time_proofs"].values()
    )
    assert all(
        p["content_version_id"] != "CV-A02-C04-PX-CAPTURE"
        for p in active["publication_events"].values()
    )


def test_provider_capture_exports_the_exact_approved_edge():
    bundle = materialize("A02-C04")
    assert_provider_capture_binding(bundle)
    original = next(e for e in load_catalogue()["graph_edges"] if e["id"] == "G-PX-CAPTURE")
    assert bundle["auxiliary_comparison_inputs"][0]["graph_edges"] == [original]
    assert (
        bundle["active_discovery_membership"]
        == materialize("A05-C01")["active_discovery_membership"]
    )


@pytest.mark.parametrize("fault", ["missing", "from", "to", "type", "duplicate"])
def test_provider_capture_rejects_missing_wrong_or_duplicate_binding(fault, monkeypatch):
    world = copy.deepcopy(load_catalogue())
    edge = next(e for e in world["graph_edges"] if e["id"] == "G-PX-CAPTURE")
    if fault == "missing":
        world["graph_edges"].remove(edge)
    elif fault == "duplicate":
        world["graph_edges"].append(copy.deepcopy(edge))
    else:
        edge[fault] = {
            "from": "OBS-JUN1-LATE",
            "to": "REP-RAW-CV-JUN-01",
            "type": "scoped_publication_support",
        }[fault]
        assert edge["id"] == "G-PX-CAPTURE"
    # Bypass general catalogue validation so the provider branch itself must reject the fault.
    with monkeypatch.context() as context:
        context.setattr("wu00_inputs.load_catalogue", lambda: world)
        with pytest.raises(ValueError, match="provider capture edge"):
            materialize("A02-C04")
    assert_provider_capture_binding(materialize("A02-C04"))
    baseline = materialize("A05-C01")
    assert baseline["auxiliary_comparison_inputs"] == []
    assert not any(
        e["id"] == "G-PX-CAPTURE"
        for e in baseline["active_discovery_membership"]["facts"]["graph_edges"]
    )


def test_provider_capture_export_mutation_does_not_contaminate_other_cases():
    first = materialize("A02-C04")
    first["auxiliary_comparison_inputs"][0]["graph_edges"][0]["type"] = "CORRUPTED"
    assert_provider_capture_binding(materialize("A02-C04"))
    assert materialize("A05-C01")["auxiliary_comparison_inputs"] == []
