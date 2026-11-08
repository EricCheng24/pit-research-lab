"""Independent tiny WU-01 input oracles; no Native/financial runtime acceptance."""

import ast
import builtins
import copy
import json
import socket
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from pit_research_lab.mvp.f2.synthetic_contracts import (
    REQUEST_KEYS,
    InputError,
    compare_input_instants,
    decode_input_bytes,
    input_bytes,
    parse_instant,
    payload_pin,
    serialize_tick_request,
    validate_price_record,
)
from pit_research_lab.mvp.f2.synthetic_temporal import (
    SyntheticInputPack,
    build_pack,
    build_weekly_requests,
    verify_input_pack,
)

FIXTURE = Path(__file__).parent / "data/temporal_foundation_v0.1.json"
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def spec(fixture):
    return copy.deepcopy(fixture["input_spec"])


def instant(raw):
    # Hand-authored test inputs; do not ask the generator to construct the oracle.
    return {
        "source_text": raw,
        "timezone_name": "Asia/Taipei",
        "offset": "+08:00",
        "precision": "SECOND",
        "origin_ref": "SYN-TEST-AUTHOR",
    }


def fail(code, operation):
    with pytest.raises(InputError) as caught:
        operation()
    assert caught.value.code == "PROPOSED_FND_" + code
    return caught.value


def price(pack, ref):
    return next(p for p in pack.source_payload()["prices"] if p["price_ref"] == ref)


def repin(payload):
    # Negative transport vector only; a hash does not make modified content lawful.
    body = input_bytes(payload)
    return SyntheticInputPack(body, payload_pin(body))


def test_CAL_01_complete_schedule_and_calendar(fixture, spec):
    pack = build_pack(spec, fixture["default_seed"])
    schedule = build_weekly_requests(pack)
    requests = [json.loads(r) for r in schedule.requests]
    oracle = fixture["manual_oracle"]
    assert [r["cutoff"]["source_text"] for r in requests] == oracle["cutoffs"]
    assert [parse_instant(r["cutoff"]).isoformat() for r in requests] == oracle["UTC_cutoffs"]
    assert [asdict(x) for x in schedule.annotations] == oracle["annotations"]
    assert [r["tick_order"] for r in requests] == [0, 1, 2, 3]
    assert len(spec["calendar"]) == oracle["calendar_date_count"] == 87
    assert sum(r["status"] == "SESSION" for r in spec["calendar"]) == oracle["session_count"] == 57
    assert len(pack.source_payload()["prices"]) == oracle["price_cell_count"] == 228
    assert all(r["issuer_refs"] == ["SYN-A", "SYN-B"] for r in requests)
    assert not any("2027-01-22" in r["tick_id"] for r in requests)


def test_CAL_02_closure_and_early_close_do_not_move_cutoff(spec):
    early = next(r for r in spec["calendar"] if r["date"] == "2027-01-06")
    assert early["close"]["source_text"] == "2027-01-06T12:00:00+08:00"
    assert next(r for r in spec["calendar"] if r["date"] == "2027-01-08")["status"] == "CLOSED"
    first = json.loads(build_weekly_requests(build_pack(spec)).requests[0])
    assert first["cutoff"]["source_text"] == "2027-01-07T18:00:00+08:00"


def test_CAL_03_duplicate_session_id(spec):
    spec["calendar"].append(copy.deepcopy(spec["calendar"][0]))
    fail("DUPLICATE_SESSION_ID", lambda: build_pack(spec))


def test_CAL_04_contradictory_session(spec):
    spec["calendar"][0]["status"] = "CLOSED"
    fail("CONTRADICTORY_SESSION", lambda: build_pack(spec))


def test_CAL_05_missing_closed_date_is_not_assumed_holiday(spec):
    spec["calendar"] = [r for r in spec["calendar"] if r["date"] != "2027-01-20"]
    fail("CALENDAR_COVERAGE_GAP", lambda: build_pack(spec))


def test_CAL_06_out_of_coverage_session(spec):
    row = copy.deepcopy(spec["calendar"][0])
    row.update(date="2027-04-01", session_id="SYN-OUTSIDE")
    spec["calendar"].append(row)
    fail("SESSION_OUT_OF_COVERAGE", lambda: build_pack(spec))


def test_calendar_uses_explicit_sessions_even_on_a_saturday(spec):
    row = next(r for r in spec["calendar"] if r["date"] == "2027-01-09")
    row.clear()
    row.update(
        date="2027-01-09",
        status="SESSION",
        session_id="SYN-EXPLICIT-SATURDAY",
        open=instant("2027-01-09T09:00:00+08:00"),
        close=instant("2027-01-09T13:30:00+08:00"),
        origin_ref="SYN-TEST-AUTHOR",
    )
    result = json.loads(build_weekly_requests(build_pack(spec)).requests[0])
    assert result["cutoff"]["source_text"] == "2027-01-09T18:00:00+08:00"


@pytest.mark.parametrize("index", [0, 1, 2], ids=["TIME-01", "TIME-02", "TIME-03"])
def test_publication_before_equal_after_is_relational_only(fixture, spec, index):
    vector = fixture["manual_oracle"]["time_vectors"][index]
    event = next(e for e in spec["revenue_events"] if e["version_ref"] == vector["version_ref"])
    result = compare_input_instants(event["publication"], instant(vector["cutoff"]))
    assert result.relation == vector["relation"]
    assert result.reason is None and result.unknown_causes == ()
    assert set(vars(result)) == {"relation", "reason", "unknown_causes"}
    assert vector["native_reference_only"]["execution"] == "NOT_RUN"


@pytest.mark.parametrize(
    "raw,change,code",
    [
        ("2027-01-07T18:00:00", {}, "AWARE_INSTANT_REQUIRED"),
        ("2027-01-07T18:00:00+00:00", {}, "ZONE_OFFSET_MISMATCH"),
        ("2027-01-07T18:00:00.100000+08:00", {}, "SECOND_PRECISION_REQUIRED"),
        ("2027-01-07T18:00:00+0800", {"offset": "+0800"}, "OFFSET_FORMAT"),
    ],
    ids=["TIME-04", "TIME-05", "TIME-06", "TIME-09"],
)
def test_instant_diagnostics(raw, change, code):
    value = instant(raw)
    value.update(change)
    fail(code, lambda: parse_instant(value))


def test_missing_declared_offset_is_not_assumed_from_source_text():
    value = instant("2027-01-07T18:00:00+08:00")
    del value["offset"]
    fail("AWARE_INSTANT_REQUIRED", lambda: parse_instant(value))


def test_TIME_07_unknown_publication_has_no_effective_time_fallback(spec):
    unknown = {
        "state": "UNKNOWN",
        "unknown_cause": "AMBIGUOUS_SOURCE",
        "source_text": "ambiguous original source",
        "origin_ref": "SYN-UNKNOWN",
    }
    spec["revenue_events"][0]["publication"] = unknown
    pack = build_pack(spec)
    retained = pack.source_payload()["input_spec"]["revenue_events"][0]
    assert retained["publication"] == unknown
    assert retained["effective_time"] is not None
    result = compare_input_instants(retained["publication"], instant("2027-01-07T18:00:00+08:00"))
    assert result.relation == "UNKNOWN"
    assert result.reason == "PROPOSED_FND_INSTANT_UNRESOLVED"
    assert result.unknown_causes == ("AMBIGUOUS_SOURCE",)


def test_TIME_08_missing_exact_proof_ref(spec):
    del spec["revenue_events"][0]["publication"]["proof_ref"]
    fail("TIME_PROOF_MISSING", lambda: build_pack(spec))


def test_unknown_and_absent_publication_are_different(spec):
    del spec["revenue_events"][0]["publication"]
    fail("MISSING_PUBLICATION_FACT", lambda: build_pack(spec))


def test_unsupported_bound_variant_is_not_reinterpreted_as_exact(spec):
    spec["revenue_events"][0]["publication"]["proof_kind"] = "UPPER_BOUND_OPEN"
    fail("UNSUPPORTED_PROOF_KIND", lambda: build_pack(spec))


def test_REV_01_revisions_and_original_source_bytes_are_preserved(fixture, spec):
    original = copy.deepcopy(spec)
    pack = build_pack(spec)
    events = pack.source_payload()["input_spec"]["revenue_events"]
    by_version = {e["version_ref"]: e for e in events}
    assert [e["amount"] for e in events] == [100, 110, 200, 90]
    assert by_version["SYN-A-DEC-v2"]["supersedes_ref"] == "SYN-A-DEC-v1"
    assert by_version["SYN-A-DEC-v3"]["supersedes_ref"] == "SYN-A-DEC-v2"
    for row in fixture["manual_oracle"]["revision_clock_vectors"]:
        assert (
            compare_input_instants(
                by_version[row["version_ref"]]["publication"], instant(row["cutoff"])
            ).relation
            == row["relation"]
        )
    assert spec == original
    old_bytes = pack.payload_bytes
    spec["revenue_events"][0]["amount"] = 999
    assert pack.payload_bytes == old_bytes
    assert pack.source_payload()["input_spec"]["revenue_events"][0]["amount"] == 100
    assert build_pack(spec).payload_sha256 != pack.payload_sha256


def test_REV_02_broken_revision_link(spec):
    spec["revenue_events"][1]["supersedes_ref"] = "SYN-NONEXISTENT"
    fail("BROKEN_REVISION_LINK", lambda: build_pack(spec))


def test_revision_cycle_is_not_valid_structure(spec):
    spec["revenue_events"][0]["supersedes_ref"] = "SYN-A-DEC-v3"
    fail("REVISION_CYCLE", lambda: build_pack(spec))


def test_REV_03_missing_coverage_declaration(spec):
    del spec["source_coverage"]
    fail("SOURCE_COVERAGE_MISSING", lambda: build_pack(spec))


def test_VALUE_01_missing_halt_are_source_facts_not_orders(fixture, spec):
    pack = build_pack(spec)
    for row in fixture["manual_oracle"]["source_state_vectors"]:
        actual = price(pack, row["price_ref"])
        assert actual["state"] == row["state"]
        assert "coefficient" not in actual
        assert row["action_basis"] == "NONE" and row["scope"] == "WU01_INPUT_ONLY"
        assert not ({"action", "order", "fill", "return"} & actual.keys())


@pytest.mark.parametrize("state", ["UNKNOWN", "WITHHELD"])
def test_VALUE_01_unknown_and_withheld_price_not_zero(spec, state):
    row = {
        "issuer_ref": "SYN-B",
        "session_ref": "SYN-2027-01-12",
        "kind": "OPEN",
        "state": state,
        "reason": "EXPLICIT_SOURCE_STATE",
        "origin_ref": "SYN-TEST",
    }
    if state == "UNKNOWN":
        row["unknown_cause"] = "ABSENT_SOURCE_FIELD"
    spec["price_template"]["overrides"].append(row)
    actual = price(build_pack(spec), "SYN-B:SYN-2027-01-12:OPEN")
    assert actual["state"] == state and "coefficient" not in actual
    if state == "UNKNOWN":
        assert actual["unknown_cause"] == "ABSENT_SOURCE_FIELD"


@pytest.mark.parametrize("value", [0, -(2**63), 2**63 - 1])
def test_VALUE_01_known_zero_and_signed_int64_revenue_retained(spec, value):
    spec["revenue_events"][0]["amount"] = value
    assert build_pack(spec).source_payload()["input_spec"]["revenue_events"][0]["amount"] == value


@pytest.mark.parametrize("state", ["UNKNOWN", "MISSING", "WITHHELD"])
def test_nonknown_revenue_amount_is_absent(spec, state):
    event = spec["revenue_events"][0]
    del event["amount"]
    event.update(state=state, reason="SOURCE_AMOUNT_UNAVAILABLE")
    if state == "UNKNOWN":
        event["unknown_cause"] = "EXPLICIT_SOURCE_UNKNOWN"
    retained = build_pack(spec).source_payload()["input_spec"]["revenue_events"][0]
    assert retained["state"] == state and "amount" not in retained


@pytest.mark.parametrize(
    "key,value,code",
    [
        ("coefficient", 0, "NONPOSITIVE_PRICE"),
        ("coefficient", False, "EXACT_INTEGER_REQUIRED"),
        ("coefficient", 1.0, "EXACT_INTEGER_REQUIRED"),
        ("coefficient", float("nan"), "EXACT_INTEGER_REQUIRED"),
        ("scale", 3, "PRICE_SCALE_MISMATCH"),
        ("currency", "USD", "CURRENCY_MISMATCH"),
    ],
    ids=["VALUE-02", "VALUE-03-bool", "VALUE-03-float", "VALUE-03-NaN", "VALUE-04", "VALUE-05"],
)
def test_exact_price_contract(spec, key, value, code):
    row = price(build_pack(spec), "SYN-A:SYN-2027-01-11:OPEN")
    row[key] = value
    fail(code, lambda: validate_price_record(row))


def test_VALUE_06_revenue_overflow(spec):
    spec["revenue_events"][0]["amount"] = 2**63
    fail("REVENUE_INT64_RANGE", lambda: build_pack(spec))


def test_VALUE_07_revenue_price_unit_not_interchangeable(spec):
    spec["revenue_events"][0]["unit"] = "NTD_price"
    fail("REVENUE_UNIT_MISMATCH", lambda: build_pack(spec))


def test_AVAIL_01_event_availability_and_request_access_are_separate(fixture, spec):
    pack = build_pack(spec)
    row = price(pack, "SYN-A:SYN-2027-01-11:OPEN")
    assert row["event_time"]["source_text"] == "2027-01-11T09:00:00+08:00"
    assert row["available_at"]["source_text"] == "2027-01-11T09:00:01+08:00"
    assert (
        compare_input_instants(row["available_at"], instant("2027-01-07T18:00:00+08:00")).relation
        == "AFTER"
    )
    for expected in fixture["manual_oracle"]["price_vectors"]:
        assert price(pack, expected["price_ref"])["coefficient"] == expected["coefficient"]
    for body in build_weekly_requests(pack).requests:
        request = json.loads(body)
        assert set(request) == REQUEST_KEYS
        assert pack.payload_sha256 in request["manifest_ref"]
        assert pack.payload_sha256 in request["context_ref"]
        assert not any(
            word in body
            for word in (
                b"outcome_ref",
                b"future_quote",
                b"audit_resolver",
                b"coefficient",
                b"label_value",
                b"prices",
            )
        )


def test_AVAIL_02_availability_cannot_precede_event(spec):
    row = price(build_pack(spec), "SYN-A:SYN-2027-01-11:OPEN")
    row["available_at"] = instant("2027-01-11T08:59:59+08:00")
    fail("AVAILABILITY_PRECEDES_EVENT", lambda: validate_price_record(row))


def test_LABEL_01_endpoint_clock_only_no_label_calculation(fixture, spec):
    pack = build_pack(spec)
    endpoints = {
        e["endpoint_ref"]: e for e in pack.source_payload()["input_spec"]["endpoint_facts"]
    }
    for vector in fixture["manual_oracle"]["endpoint_clock_vectors"]:
        row = endpoints[vector["endpoint_ref"]]
        assert (
            compare_input_instants(row["maturity_at"], instant(vector["fit_time"])).relation
            == vector["relation"]
        )
        assert not ({"label_value", "return", "fit_eligible"} & row.keys())


def test_LABEL_02_endpoint_outside_tail(spec):
    spec["endpoint_facts"][1]["source_date"] = "2027-04-01"
    fail("ENDPOINT_OUT_OF_COVERAGE", lambda: build_pack(spec))


def test_LABEL_03_missing_price_cell_even_with_matching_supplied_hash(spec):
    payload = build_pack(spec).source_payload()
    payload["prices"] = [
        p for p in payload["prices"] if p["price_ref"] != "SYN-A:SYN-2027-02-26:CLOSE"
    ]
    fail("PRICE_GRID_COVERAGE_GAP", lambda: verify_input_pack(repin(payload)))


@pytest.mark.parametrize(
    "key",
    ["outcome_ref", "future_quote", "audit_resolver", "label_value", "action"],
    ids=["ACCESS-01", "ACCESS-02-quote", "ACCESS-02-audit", "ACCESS-02-label", "ACCESS-02-action"],
)
def test_request_rejects_forbidden_fields(spec, key):
    request = json.loads(build_weekly_requests(build_pack(spec)).requests[0])
    request[key] = "FORBIDDEN"
    exc = fail("FORBIDDEN_DECISION_FIELD", lambda: serialize_tick_request(request))
    assert exc.path == key


def test_nested_future_field_and_raw_pack_cannot_serialize_as_request(spec):
    pack = build_pack(spec)
    request = json.loads(build_weekly_requests(pack).requests[0])
    request["cutoff"]["outcome_ref"] = "FORBIDDEN"
    assert (
        fail("FORBIDDEN_DECISION_FIELD", lambda: serialize_tick_request(request)).path
        == "cutoff.outcome_ref"
    )
    fail("OBJECT_REQUIRED", lambda: serialize_tick_request(pack))
    fail("FORBIDDEN_DECISION_FIELD", lambda: serialize_tick_request(pack.source_payload()))


def test_PINS_01_altered_payload_requires_new_pin_and_consistency(spec):
    pack = build_pack(spec)
    altered = pack.payload_bytes.replace(b'"seed":17', b'"seed":18')
    assert altered != pack.payload_bytes
    fail("PAYLOAD_PIN_MISMATCH", lambda: verify_input_pack(replace(pack, payload_bytes=altered)))
    payload = pack.source_payload()
    payload["prices"][0]["coefficient"] += 1
    fail("GENERATED_PRICE_MISMATCH", lambda: verify_input_pack(repin(payload)))


def test_PINS_02_deterministic_input_and_seed_oracle_independence(fixture, spec):
    a = build_pack(spec, 17)
    assert a == build_pack(copy.deepcopy(spec), 17)
    assert a.payload_sha256 != build_pack(spec, 18).payload_sha256
    fixture["manual_oracle"]["cutoffs"] = ["DELIBERATELY_WRONG_EXPECTATION"]
    assert build_pack(fixture["input_spec"], 17) == a
    verify_input_pack(a)
    detached = a.source_payload()
    detached["seed"] = 99
    assert a.source_payload()["seed"] == 17


def check_oracle_scope(case):
    # Test-only specification check, not a policy/order/fill implementation.
    if case.get("scope") == "WU01_INPUT_ONLY" and str(case.get("expected_result", "")).startswith(
        "NO_FILL_"
    ):
        raise InputError("ORACLE_SCOPE_VIOLATION")


def test_SCOPE_01_unreachable_fill_expectation_is_rejected(fixture):
    wrong = fixture["manual_oracle"]["unreachable_fill_negative"]
    assert wrong["action_basis"] == "NONE"
    fail("ORACLE_SCOPE_VIOLATION", lambda: check_oracle_scope(wrong))
    assert all(
        x["status"] == "ORACLE_INCOMPLETE" and x["gate"] == "F5_POLICY_GATE"
        for x in fixture["manual_oracle"]["deferred_F5"]
    )


@pytest.mark.parametrize(
    "cadence", ["MONTHLY", "DAILY"], ids=["SCOPE-02-monthly", "SCOPE-02-daily"]
)
def test_SCOPE_02_unsupported_cadence_does_not_fallback(spec, cadence):
    spec["decision_frequency"] = cadence
    fail("UNSUPPORTED_FREQUENCY", lambda: build_pack(spec))


def test_SCOPE_03_real_mode_not_supported(spec):
    spec["data_mode"] = "REAL_TWSE_PILOT"
    fail("UNSUPPORTED_DATA_MODE", lambda: build_pack(spec))


@pytest.mark.parametrize("membership", [0, "UNKNOWN"])
def test_complete_roster_includes_zero_and_unknown_membership(spec, membership):
    row = spec["roster"][1]
    row["membership"] = (
        {"state": "KNOWN", "value": 0, "origin_ref": "SYN-TEST"}
        if membership == 0
        else {
            "state": "UNKNOWN",
            "unknown_cause": "UNMAPPED",
            "source_text": None,
            "origin_ref": "SYN-TEST",
        }
    )
    pack = build_pack(spec)
    assert len(pack.source_payload()["prices"]) == 228
    assert json.loads(build_weekly_requests(pack).requests[0])["issuer_refs"] == ["SYN-A", "SYN-B"]


def test_exact_json_rejects_duplicate_keys_floats_and_nan():
    fail("DUPLICATE_JSON_KEY", lambda: decode_input_bytes(b'{"x":1,"x":2}'))
    fail("EXACT_INTEGER_REQUIRED", lambda: decode_input_bytes(b'{"x":1.0}'))
    fail("EXACT_INTEGER_REQUIRED", lambda: decode_input_bytes(b'{"x":NaN}'))


def test_source_import_closure_and_no_native_or_application_authority():
    folder = ROOT / "src/pit_research_lab/mvp/f2"
    allowed = {
        "json",
        "re",
        "dataclasses",
        "datetime",
        "hashlib",
        "typing",
        "zoneinfo",
        "synthetic_contracts",
    }
    for name in ("synthetic_contracts.py", "synthetic_temporal.py"):
        tree = ast.parse((folder / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name in allowed for a in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            if isinstance(node, ast.Attribute):
                assert node.attr not in {
                    "now",
                    "today",
                    "utcnow",
                    "read_bytes",
                    "write_bytes",
                    "read_text",
                    "write_text",
                }
        names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
        assert not names & {
            "ResearchRun",
            "SnapshotReference",
            "DatasetManifest",
            "ResearchClient",
            "evaluate_slice",
            "evaluate_asof",
            "publish",
            "fill",
            "evaluate_policy",
        }
    assert not any(
        n.startswith(("pit_research_lab.domain", "pit_research_lab.infrastructure"))
        for n in sys.modules
    )


def test_generation_and_request_construction_do_not_call_external_io(spec, monkeypatch):
    build_pack(spec)  # Installed ZoneInfo data is an explicit, already-inspected resource.

    def denied(*args, **kwargs):
        raise AssertionError("Unexpected I/O in source generation/request construction")

    for obj, name in (
        (builtins, "open"),
        (socket, "socket"),
        (subprocess, "run"),
        (subprocess, "check_output"),
        (Path, "read_bytes"),
        (Path, "write_bytes"),
    ):
        monkeypatch.setattr(obj, name, denied)
    pack = build_pack(spec)
    verify_input_pack(pack)
    assert len(build_weekly_requests(pack).requests) == 4


def test_manual_case_registry_is_complete_and_not_runtime_acceptance(fixture):
    expected = {
        *(f"CAL-{i:02}" for i in range(1, 7)),
        *(f"TIME-{i:02}" for i in range(1, 10)),
        *(f"REV-{i:02}" for i in range(1, 4)),
        *(f"VALUE-{i:02}" for i in range(1, 8)),
        "AVAIL-01",
        "AVAIL-02",
        "LABEL-01",
        "LABEL-02",
        "LABEL-03",
        "ACCESS-01",
        "ACCESS-02",
        "PINS-01",
        "PINS-02",
        "SCOPE-01",
        "SCOPE-02",
        "SCOPE-03",
    }
    cases = fixture["manual_oracle"]["case_registry"]
    assert len(cases) == len({x["case_id"] for x in cases})
    assert {x["case_id"] for x in cases} == expected
    assert all(
        x["status"] == "SPECIFIED_NOT_RUN" and x["input_scope"] == "WU01_INPUT_ONLY" for x in cases
    )


@pytest.mark.parametrize("clock", ["18:00:00", "19:00:00"], ids=["R1-A01-equal", "R1-A02-after"])
def test_R1_A_selected_session_must_close_strictly_before_cutoff(spec, clock):
    session = next(row for row in spec["calendar"] if row["date"] == "2027-01-07")
    session["close"] = instant(f"2027-01-07T{clock}+08:00")
    pack = build_pack(spec)  # General source shape remains valid, not Weekly request validity.
    exc = fail("SESSION_CLOSE_NOT_BEFORE_CUTOFF", lambda: build_weekly_requests(pack))
    assert exc.path == "SYN-2027-01-07:2027-W01"


def test_R1_A03_last_second_before_cutoff_retains_session_binding(spec):
    session = next(row for row in spec["calendar"] if row["date"] == "2027-01-07")
    session["close"] = instant("2027-01-07T17:59:59+08:00")
    pack = build_pack(spec)
    first = json.loads(build_weekly_requests(pack).requests[0])
    assert first["tick_id"] == "SYN-TICK-2027-01-07"
    assert first["cutoff"]["source_text"] == "2027-01-07T18:00:00+08:00"
    assert first["context_ref"] == "SYN-CONTEXT-" + pack.payload_sha256 + ":2027-01-07"


@pytest.mark.parametrize(
    "day", ["2027-01-06", "2027-03-31"], ids=["R1-A04-nonselected", "R1-A05-outside-window"]
)
def test_R1_A_guard_does_not_reject_nonselected_or_out_of_window_sessions(fixture, spec, day):
    session = next(row for row in spec["calendar"] if row["date"] == day)
    session["close"] = instant(day + "T19:00:00+08:00")
    requests = build_weekly_requests(build_pack(spec))
    assert [json.loads(r)["cutoff"]["source_text"] for r in requests.requests] == fixture[
        "manual_oracle"
    ]["cutoffs"]
    assert [asdict(a) for a in requests.annotations] == [
        {"iso_week": "2027-W03", "annotation": "NO_SESSION_WEEK"}
    ]


@pytest.mark.parametrize(
    "day,week",
    [
        ("2027-01-07", "2027-W01"),
        ("2027-01-15", "2027-W02"),
        ("2027-01-29", "2027-W04"),
        ("2027-02-05", "2027-W05"),
    ],
    ids=["R1-A06-t1", "R1-A06-t2", "R1-A06-t3", "R1-A06-t4"],
)
def test_R1_A_guard_checks_every_emitted_week(spec, day, week):
    session = next(row for row in spec["calendar"] if row["date"] == day)
    session["close"] = instant(day + "T19:00:00+08:00")
    exc = fail("SESSION_CLOSE_NOT_BEFORE_CUTOFF", lambda: build_weekly_requests(build_pack(spec)))
    assert exc.path == "SYN-" + day + ":" + week


@pytest.mark.parametrize(
    "clock", ["18:00:00", "19:00:00"], ids=["R1-A07-saturday-equal", "R1-A07-saturday-after"]
)
def test_R1_A_actual_pinned_saturday_session_also_obeys_close_guard(spec, clock):
    row = next(r for r in spec["calendar"] if r["date"] == "2027-01-09")
    row.clear()
    row.update(
        date="2027-01-09",
        status="SESSION",
        session_id="SYN-EXPLICIT-SATURDAY",
        open=instant("2027-01-09T09:00:00+08:00"),
        close=instant(f"2027-01-09T{clock}+08:00"),
        origin_ref="SYN-TEST-AUTHOR",
    )
    exc = fail("SESSION_CLOSE_NOT_BEFORE_CUTOFF", lambda: build_weekly_requests(build_pack(spec)))
    assert exc.path == "SYN-EXPLICIT-SATURDAY:2027-W01"


def test_R1_A08_prebuilt_source_bytes_do_not_bypass_weekly_guard(spec):
    session = next(row for row in spec["calendar"] if row["date"] == "2027-01-07")
    session["close"] = instant("2027-01-07T19:00:00+08:00")
    source = build_pack(spec)
    prebuilt = SyntheticInputPack(bytes(source.payload_bytes), source.payload_sha256)
    assert verify_input_pack(prebuilt) is None  # Source consistency is distinct from scheduling.
    exc = fail("SESSION_CLOSE_NOT_BEFORE_CUTOFF", lambda: build_weekly_requests(prebuilt))
    assert exc.path == "SYN-2027-01-07:2027-W01"


def test_R1_A09_default_input_and_request_bytes_remain_identical(spec):
    # Literal byte pins from the verified submitted export, not regenerated expectations.
    assert (
        payload_pin(FIXTURE.read_bytes())
        == "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373"
    )
    pack = build_pack(spec, 17)
    assert pack.payload_sha256 == "c0c8d440f1127f0ede57863cfb544eaaac184e1a3436670c1bf8d46f1385195c"
    result = build_weekly_requests(pack)
    assert [payload_pin(r) for r in result.requests] == [
        "909050c0cc90f0e16361891e9fa2b2233a363aa35de5278a38b838d97baea046",
        "be50dadac52fee5a266b56dbd4448275cf331078af554050713bcdf4471fe1fa",
        "56c8ca0ff123301adc894e65738209c7987e91d31a9c9b35597e3ae44c0abed8",
        "beaf6dff59c87f22f9384a5d1ce3017a1192dbf2167e51b0c9b54d389eb107e8",
    ]
    assert [asdict(a) for a in result.annotations] == [
        {"iso_week": "2027-W03", "annotation": "NO_SESSION_WEEK"}
    ]


@pytest.mark.parametrize(
    "with_amount", [False, True], ids=["R1-B01-no-amount", "R1-B02-with-amount"]
)
def test_R1_B_revenue_halt_rejected_before_numeric_shape(spec, with_amount):
    event = spec["revenue_events"][0]
    event.update(state="HALT", reason="TRADING_HALT_IS_NOT_REVENUE_STATE")
    if not with_amount:
        del event["amount"]
    # All other fields valid. Domain-state check precedes numeric shape in _source_value.
    fail("INVALID_REVENUE_STATE", lambda: build_pack(spec))


@pytest.mark.parametrize(
    "domain,code",
    [
        ("revenue", "INVALID_REVENUE_STATE"),
        ("price", "INVALID_SOURCE_STATE"),
    ],
    ids=["R1-B03-revenue", "R1-B03-price"],
)
def test_R1_B_unrecognized_states_remain_rejected(spec, domain, code):
    if domain == "revenue":
        spec["revenue_events"][0]["state"] = "UNRECOGNIZED"
        fail(code, lambda: build_pack(spec))
    else:
        row = price(build_pack(spec), "SYN-A:SYN-2027-01-11:OPEN")
        row["state"] = "UNRECOGNIZED"
        fail(code, lambda: validate_price_record(row))


@pytest.mark.parametrize(
    "state",
    ["UNKNOWN", "MISSING", "WITHHELD"],
    ids=["R1-B04-unknown", "R1-B04-missing", "R1-B04-withheld"],
)
def test_R1_B_revenue_nonknown_reason_origin_and_cause_unchanged(spec, state):
    event = spec["revenue_events"][0]
    del event["amount"]
    event.update(state=state, reason="SOURCE_VALUE_ABSENT", origin_ref="SYN-HAND-STATE-ORIGIN")
    if state == "UNKNOWN":
        event["unknown_cause"] = "AMBIGUOUS_SOURCE"
    retained = build_pack(spec).source_payload()["input_spec"]["revenue_events"][0]
    assert retained == event
    assert "amount" not in retained
    event["amount"] = 0
    fail("NONKNOWN_NUMERIC_VALUE_FORBIDDEN", lambda: build_pack(spec))


@pytest.mark.parametrize("value", [False, 1.0], ids=["R1-B05-bool", "R1-B05-float"])
def test_R1_B_revenue_never_coerces_boolean_or_float(spec, value):
    spec["revenue_events"][0]["amount"] = value
    fail("EXACT_INTEGER_REQUIRED", lambda: build_pack(spec))


def test_R1_B06_revenue_negative_int64_overflow_rejected(spec):
    spec["revenue_events"][0]["amount"] = -(2**63) - 1
    fail("REVENUE_INT64_RANGE", lambda: build_pack(spec))


def test_R1_B07_price_halt_remains_only_a_source_fact(spec):
    row = price(build_pack(spec), "SYN-A:SYN-2027-01-25:OPEN")
    assert validate_price_record(row) is None
    assert row["state"] == "HALT" and row["reason"] == "SYNTHETIC_OPEN_HALT"
    assert row["origin_ref"] == "SYN-PRICE-AUTHOR"
    assert row["unit"] == "NTD_price" and row["currency"] == "NTD" and row["scale"] == 6
    assert not {"coefficient", "action", "order", "fill", "pit_status"} & row.keys()
