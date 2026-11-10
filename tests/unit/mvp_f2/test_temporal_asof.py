"""Literal reviewed W02 oracles; actual observers only at the approved caller boundary."""

import copy
import hashlib
import json
import os
import subprocess
from dataclasses import FrozenInstanceError, asdict, fields, replace
from pathlib import Path

import pytest

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain.pit_slice import evaluate_slice, observe_code
from pit_research_lab.domain.temporal import TemporalOutcome
from pit_research_lab.mvp.f2 import native_requests as nr
from pit_research_lab.mvp.f2 import temporal_qualification as tq
from pit_research_lab.mvp.f2.synthetic_contracts import InputError, input_bytes
from pit_research_lab.mvp.f2.synthetic_temporal import (
    SyntheticInputPack,
    build_pack,
    build_weekly_requests,
)

ROOT = Path(__file__).parents[3]
FIXTURE = Path(__file__).parent / "data/temporal_qualification_evidence_v0.1.json"
FOUNDATION = Path(__file__).parent / "data/temporal_foundation_v0.1.json"
FIXTURE_SHA = "a876570e6bcc92ffe6977aea3d2ca06b4d19f3262f33abe95ff7607db8d46fa8"
# Historical oracle identity for offline review; pytest uses the literal
# assertions below and this explicit coverage inventory, never an external file.
ORACLE_SHA = "2fe5ff71585ff2e56ec69bf1eace0485072ef444e4183a698e4dfbd496fb73df"
REVIEWED_PRIMARY_CASES = (
    "test_w02_t01_a_v1_before_t1",
    "test_w02_t02_a_v2_equal_t1_v1_independent",
    "test_w02_t03_b_v1_after_t1",
    "test_w02_t03_b_v1_before_t2_new_invocation",
    "test_w02_t04_a_v3_after_t3",
    "test_w02_t04_a_v3_before_t4",
    "test_w02_t05_ambiguous_timezone_cause_preserved",
    "test_w02_t05_known_zone_unparsed_time",
    "test_w02_t06_open_bound_equal",
    "test_w02_t06_closed_bound_equal",
)
REVIEWED_NEGATIVE_CASES = (
    "test_w02_t05_absent_publication",
    "test_w02_t05_nonknown_amount_no_zero",
    "test_w02_t07_naive_publication",
    "test_w02_t07_fractional_proof_without_rounding",
    "test_w02_t07_zone_offset_conflict",
    "test_w02_t09_representation_mismatch",
    "test_w02_t09_assertion_unit_mismatch",
    "test_w02_t09_assertion_period_mismatch",
    "test_w02_t09_requested_subject_scope_mismatch",
    "test_w02_t10_conflicting_scope_raw_pin",
    "test_g02_missing_support_attempt",
    "test_g02_missing_source_records",
    "test_g02_contradictory_exact_descriptor",
    "test_w02_t08_supersedes_not_s3_notice",
    "test_w02_t11_no_session_week_no_qualification",
    "test_w02_t12_future_outcome_field_rejected",
    "test_w02_t13_diagnostic_flags_no_app_promotion",
    "test_w02_t14_same_inputs_local_repeatability",
    "test_w02_t15_actual_observation_absent",
    "test_g04_declared_observed_pin_mismatch",
    "test_g04_foreign_root_or_symlink_refused",
    "test_g04_before_after_native_drift_withholds_completion",
    "test_g06_compound_fault_stage_order",
    "test_g06_wrong_cutoff_same_tick_id",
)
PERMIT = "MVP-F2-WU-02-S1S2-IMPL-01"
_counter = 0


def wire(value):
    return nr.WireObject.from_value(value)


def f(value):
    return value["fields"]


@pytest.fixture(scope="module")
def source():
    body = FIXTURE.read_bytes()
    assert len(body) == 8803308 and hashlib.sha256(body).hexdigest() == FIXTURE_SHA
    return body, json.loads(body), json.loads(FOUNDATION.read_bytes())["input_spec"]


def require_no_symlinks(path):
    # Check ancestors first: lstat a child only after its parent was accepted.
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError("Symlink component in observation path")


def trusted_checkout_root():
    """Caller-side I/O: verify loaded source origin before any observer call."""
    anchor = nr._MODULE_CHECKOUT_ROOT
    if anchor is None:
        raise ValueError("Unsupported W02 source-checkout layout")
    root = Path(anchor)
    module_path = root / "src/pit_research_lab/mvp/f2/native_requests.py"
    if root != ROOT or not root.is_absolute() or Path(nr.__file__) != module_path:
        raise ValueError("Unsafe or mismatched W02 module checkout")
    require_no_symlinks(module_path)
    if root.resolve() != root or not module_path.is_file():
        raise ValueError("Unsafe or mismatched W02 module checkout")
    toplevel = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
    if toplevel != str(root):
        raise ValueError("W02 module checkout is not the Git toplevel")
    return root


def observe():
    """Genuine disk receipt; controlled negative copies below are never logged as observed."""
    global _counter
    try:
        root = trusted_checkout_root()
        for rel, digest, length in nr.NATIVE_CODE_PINS:
            path = root / rel
            require_no_symlinks(path)
            if not path.is_file() or path.resolve() != path:
                raise ValueError("Unsafe Native observation path")
            data = path.read_bytes()
            assert len(data) == length and hashlib.sha256(data).hexdigest() == digest
        code = observe_code(root)
    except (ValueError, OSError, subprocess.CalledProcessError):
        return nr.ObservationUnavailable(
            "CALLER_SCOPE_REFUSED", ("/caller/module_checkout",), "Checkout verification failed"
        )
    _counter += 1
    receipt = nr.CallerObservationReceipt(
        PERMIT,
        str(root),
        tuple(p[0] for p in nr.NATIVE_CODE_PINS),
        f"actual-observation-{_counter}",
        "pit_slice.observe_code",
        True,
    )
    result = nr.ObservedCodeInput(code, receipt)
    log = os.environ.get("WU02_OBSERVATION_LOG")
    if log:
        path = Path(log)
        assert str(path).startswith("/tmp/mvp-f2-wu02-s1s2-")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "kind": "GENUINE_OBSERVER_OUTPUT",
                        "receipt": asdict(receipt),
                        "code": asdict(code),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return result


def profile(source):
    return nr._NativeBuilder().build(wire(source[1]["declared_profile"]), c.CandidateProfile)


def unknown_event(event, origin_wire):
    origin = nr._NativeBuilder().build(wire(origin_wire), c.FieldOrigin)
    facts = []
    if event.get("state") == "UNKNOWN":
        facts.append(c.Unknown(c.UnknownCause(event["unknown_cause"]), event["reason"], origin))
    publication = event.get("publication", {})
    if publication.get("state") == "UNKNOWN":
        facts.append(
            c.Unknown(
                c.UnknownCause(publication["unknown_cause"]), publication["source_text"], origin
            )
        )
    return nr.SourceEvent(wire(event), tuple(facts))


def assembly(source, rid="R1", fixture_id=None, profile_id="BASE"):
    body, data, _ = source
    ref = data["records"][rid]
    chosen = ref
    if fixture_id:
        chosen = data["negative_inputs"].get(
            fixture_id, data["independent_proof_variants"].get(fixture_id)
        )
    assert chosen is not None
    event = copy.deepcopy(ref["wu01_event_exact"])
    bindings = [
        nr.SourceSpecBinding(
            "BASE",
            "e844d2d650268c7ecf6802211fe1111e658f6ec83821a773dc9d4e01151491d2",
            17,
            "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373",
            (),
        )
    ]
    for name, value in data["input_contract"]["authored_negative_source_spec_profiles"].items():
        replacement = nr.EventReplacement(
            value["event_index"], wire(value["exact_replacement_event"])
        )
        bindings.append(
            nr.SourceSpecBinding(
                name,
                value["source_spec_local_json_pin"]["sha256"],
                17,
                "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373",
                (replacement,),
            )
        )
        if name == profile_id:
            event = copy.deepcopy(value["exact_replacement_event"])
    record = nr.EvidenceRecord(
        rid,
        profile_id,
        event["event_ref"],
        event["version_ref"],
        event["issuer_ref"],
        ref["raw_notice_utf8"].encode(),
        ref["raw_notice_bytes"]["byte_len"],
        ref["raw_notice_bytes"]["sha256"],
        unknown_event(event, f(ref["subject"])["origin"]),
        wire(chosen),
        (
            nr.FieldProvenance(
                "/records/" + rid,
                "SYNTHETIC_AUTHORED_FOR_W02",
                data["authorship"]["author_ref"],
                FIXTURE_SHA,
            ),
        ),
    )
    contexts = tuple(
        nr.ContextRecord(rid, tick, wire(value))
        for tick, value in data["native_contexts"][rid].items()
    )
    provenance = nr.EvidenceAuthoringProvenance(
        "SYNTHETIC_AUTHORED_FOR_W02",
        data["authorship"]["author_ref"],
        "Owner-accepted independent review, 2026-11-09",
        "OWNER_ACCEPTED",
    )
    approval = nr.EvidenceApprovalBinding(
        "OWNER_ADOPTED_FOR_W02_S1S2",
        PERMIT,
        "OWNER_REPORTED_ACCEPTED_2026-11-09",
        FIXTURE_SHA,
        "w02-native-mapping-v0.1",
        ("BASE", "N_NONKNOWN_AMOUNT", "U1"),
    )
    return nr.EvidenceAssembly(
        "w02-evidence-assembly-v0.1",
        body,
        rid,
        nr.FrozenNativeInput.from_record(wire(chosen)),
        FIXTURE_SHA,
        tuple(bindings),
        (record,),
        contexts,
        provenance,
        approval,
    )


def inputs(source, rid="R1", tick=0, fixture_id=None, profile_id="BASE"):
    evidence = assembly(source, rid, fixture_id, profile_id)
    spec = copy.deepcopy(source[2])
    if profile_id != "BASE":
        replacement = source[1]["input_contract"]["authored_negative_source_spec_profiles"][
            profile_id
        ]
        spec["revenue_events"][replacement["event_index"]] = replacement["exact_replacement_event"]
    pack = build_pack(spec)
    requests = build_weekly_requests(pack)
    return pack, requests.requests[tick], evidence, profile(source)


def prepare(source, rid="R1", tick=0, fixture_id=None, profile_id="BASE", observed=None):
    args = inputs(source, rid, tick, fixture_id, profile_id)
    return nr.prepare_native_request(*args, observed if observed is not None else observe())


def run(source, rid="R1", tick=0):
    prepared = prepare(source, rid, tick)
    assert isinstance(prepared, nr.NativeRequestAssembly), prepared
    attempt = tq.invoke_s1s2(prepared)
    assert isinstance(attempt, tq.NativeAttempt), attempt
    diagnostic = tq.finalize_diagnostic(attempt, observe())
    assert isinstance(diagnostic, tq.W02Diagnostic), diagnostic
    assert diagnostic.native_result is attempt.slice_result
    return prepared, diagnostic


def assert_temporal(result, state, reason="NONE"):
    native = result.native_result
    assert isinstance(native.s1, c.EvidenceOutcome)
    assert (native.s1.state, native.s1.reason) == ("BOUND", "NONE")
    assert isinstance(native.s2, TemporalOutcome)
    assert (native.s2.state, native.s2.reason) == (state, reason)
    assert native.trust == result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert native.source_authentication == result.source_authentication == "NOT_ESTABLISHED"
    assert native.admission_eligible is result.admission_eligible is False
    assert native.diagnostic_only is result.diagnostic_only is True


def assert_refusal(value, stage, reason):
    assert isinstance(value, nr.W02MappingRefusal), value
    assert (value.stage.value, value.reason.value) == (stage, "PROPOSED_W02_" + reason)
    assert value.native_invocation == "NOT_RUN"
    assert value.evidence_paths == tuple(sorted(set(value.evidence_paths)))
    assert value.first_failure.path == value.evidence_paths[0]


def direct(source, fixture_id):
    record = source[1]["negative_inputs"].get(
        fixture_id, source[1]["independent_proof_variants"].get(fixture_id)
    )
    assert record is not None
    builder = nr._NativeBuilder()
    request = builder.build(wire(record["request"]), c.IssuerBindingRequest)
    context = builder.build(wire(source[1]["native_contexts"]["R1"]["t1"]), c.SemanticContext)
    before = observe()
    result = evaluate_slice(context, request, before.code)
    after = observe()
    assert before.code.observed_working_files == after.code.observed_working_files
    assert before.code.byte_lengths == after.code.byte_lengths
    return result


def direct_fault(source, name, code):
    result = direct(source, name)
    assert isinstance(result.s1, c.BlockingFailure)
    assert (result.s1.category, result.s1.code, result.s1.attempted_operation) == (
        "CONTRACT_VIOLATION",
        code,
        "CHECK_BINDING",
    )
    assert isinstance(result.s2, TemporalOutcome)
    assert (result.s2.state, result.s2.reason) == ("UNRESOLVED", "CONTENT_BINDING_INSUFFICIENT")
    assert result.s2.diagnostics == ("S1_BLOCKED:" + code,)


def test_w02_t01_a_v1_before_t1(source):
    prepared, result = run(source)
    assert_temporal(result, "SUPPORTED")
    assert prepared.context.information_cutoff.source_text == "2027-01-07T18:00:00+08:00"
    assert prepared.request.attempts[0].supplied.proof_candidate.timestamp.source_text == (
        "2027-01-07T17:59:59+08:00"
    )
    assert prepared.request.assertion.source_amount.value == 100


def test_w02_t02_a_v2_equal_t1_v1_independent(source):
    _, equal = run(source, "R2")
    assert_temporal(equal, "NOT_ADMISSIBLE", "PUBLICATION_NOT_PRE_CUTOFF")
    _, original = run(source)
    assert_temporal(original, "SUPPORTED")


def test_w02_t03_b_v1_after_t1(source):
    _, result = run(source, "R3")
    assert_temporal(result, "NOT_ADMISSIBLE", "PUBLICATION_NOT_PRE_CUTOFF")


def test_w02_t03_b_v1_before_t2_new_invocation(source):
    prepared, result = run(source, "R3", 1)
    assert_temporal(result, "SUPPORTED")
    assert prepared.cutoff.source_text == "2027-01-15T18:00:00+08:00"


def test_w02_t04_a_v3_after_t3(source):
    _, result = run(source, "R4", 2)
    assert_temporal(result, "NOT_ADMISSIBLE", "PUBLICATION_NOT_PRE_CUTOFF")
    assert source[1]["records"]["R1"]["wu01_event_exact"]["publication"]["instant"][
        "source_text"
    ] == ("2027-01-07T17:59:59+08:00")


def test_w02_t04_a_v3_before_t4(source):
    _, result = run(source, "R4", 3)
    assert_temporal(result, "SUPPORTED")


def test_w02_t05_ambiguous_timezone_cause_preserved(source):
    result = direct(source, "U1")
    assert (result.s1.state, result.s2.state, result.s2.reason) == (
        "BOUND",
        "UNRESOLVED",
        "TIMEZONE_UNRESOLVED",
    )
    proof = result.s2.evaluated_evidence
    assert proof.timezone.cause is c.UnknownCause.AMBIGUOUS_SOURCE
    assert proof.source_text == "2027-01-07 17:59:59 (ambiguous source timezone)"
    assert proof.timezone.source_text == proof.source_text
    assert proof.timezone.origin == proof.origin
    refused = prepare(source, fixture_id="U1")
    assert_refusal(refused, "S05_TYPED_EVIDENCE", "PROOF_SCOPE_UNAPPROVED")


def test_w02_t05_known_zone_unparsed_time(source):
    result = direct(source, "U2")
    assert (result.s1.state, result.s2.state, result.s2.reason) == (
        "BOUND",
        "UNRESOLVED",
        "TEMPORAL_BOUND_INSUFFICIENT",
    )
    assert "SOURCE_TIME_UNPARSED" in result.s2.diagnostics


def test_w02_t06_open_bound_equal(source):
    result = direct(source, "UB_OPEN")
    assert (result.s1.state, result.s2.state, result.s2.reason) == ("BOUND", "SUPPORTED", "NONE")
    assert_refusal(
        prepare(source, fixture_id="UB_OPEN"), "S05_TYPED_EVIDENCE", "PROOF_SCOPE_UNAPPROVED"
    )


def test_w02_t06_closed_bound_equal(source):
    result = direct(source, "UB_CLOSED")
    assert (result.s1.state, result.s2.state, result.s2.reason) == (
        "BOUND",
        "UNRESOLVED",
        "TEMPORAL_BOUND_INSUFFICIENT",
    )
    assert_refusal(
        prepare(source, fixture_id="UB_CLOSED"), "S05_TYPED_EVIDENCE", "PROOF_SCOPE_UNAPPROVED"
    )


def test_w02_t05_absent_publication(source):
    spec = copy.deepcopy(source[2])
    del spec["revenue_events"][0]["publication"]
    body = input_bytes(
        {
            "schema_version": "mvp-f2-synthetic-input-v0.1",
            "encoding": "wu01-local-input-json-v0.1:ascii-sorted-compact",
            "seed": 17,
            "input_spec": spec,
            "prices": [],
        }
    )
    bad = SyntheticInputPack(body, hashlib.sha256(body).hexdigest())
    _, tick, evidence, declared = inputs(source)
    result = nr.prepare_native_request(
        bad, tick, evidence, declared, nr.ObservationUnavailable("ABSENT", (), "Not observed")
    )
    assert_refusal(result, "S01_PACK", "PACK_INVALID")
    assert result.upstream_error.code == "PROPOSED_FND_MISSING_PUBLICATION_FACT"


def test_w02_t05_nonknown_amount_no_zero(source):
    result = prepare(source, profile_id="N_NONKNOWN_AMOUNT")
    assert_refusal(result, "S04_EVIDENCE", "AMOUNT_NOT_KNOWN")
    assert result.retained_unknown_facts[0].cause is c.UnknownCause.EXPLICIT_SOURCE_UNKNOWN
    assert "Known(0)" not in result.safe_detail


def test_w02_t07_naive_publication(source):
    spec = copy.deepcopy(source[2])
    spec["revenue_events"][0]["publication"]["instant"]["source_text"] = "2027-01-07T17:59:59"
    with pytest.raises(InputError) as caught:
        build_pack(spec)
    assert caught.value.code == "PROPOSED_FND_AWARE_INSTANT_REQUIRED"
    origin = nr._NativeBuilder().build(
        wire(f(source[1]["records"]["R1"]["subject"])["origin"]), c.FieldOrigin
    )
    with pytest.raises(c.ContractError, match="INVALID_INSTANT"):
        c.AwareInstant("2027-01-07T17:59:59", "Asia/Taipei", "+08:00", "SECOND", origin)


def test_w02_t07_fractional_proof_without_rounding(source):
    result = direct(source, "N_FRACTION")
    assert result.s1.state == "BOUND"
    assert isinstance(result.s2, c.BlockingFailure)
    assert (result.s2.category, result.s2.code) == (
        "CONTRACT_VIOLATION",
        "SECOND_PRECISION_REQUIRED",
    )
    assert_refusal(prepare(source, fixture_id="N_FRACTION"), "S05_TYPED_EVIDENCE", "PROOF_INVALID")


def test_w02_t07_zone_offset_conflict(source):
    result = direct(source, "N_ZONE")
    assert result.s1.state == "BOUND"
    assert isinstance(result.s2, c.BlockingFailure)
    assert result.s2.code == "ZONE_OFFSET_CONFLICT"
    assert_refusal(prepare(source, fixture_id="N_ZONE"), "S05_TYPED_EVIDENCE", "PROOF_INVALID")


def test_w02_t09_representation_mismatch(source):
    direct_fault(source, "N_REP", "REQUEST_CONTENT_MISMATCH")
    assert_refusal(
        prepare(source, fixture_id="N_REP"), "S03_IDENTITY", "EVIDENCE_IDENTITY_MISMATCH"
    )


def test_w02_t09_assertion_unit_mismatch(source):
    direct_fault(source, "N_UNIT", "SOURCE_ASSERTION_MISMATCH")
    assert_refusal(
        prepare(source, fixture_id="N_UNIT"), "S03_IDENTITY", "EVIDENCE_IDENTITY_MISMATCH"
    )


def test_w02_t09_assertion_period_mismatch(source):
    direct_fault(source, "N_PERIOD", "SOURCE_ASSERTION_MISMATCH")
    assert_refusal(
        prepare(source, fixture_id="N_PERIOD"), "S03_IDENTITY", "EVIDENCE_IDENTITY_MISMATCH"
    )


def test_w02_t09_requested_subject_scope_mismatch(source):
    direct_fault(source, "N_SUBJECT_SCOPE", "REQUEST_TARGET_CONTENT_MISMATCH")
    assert_refusal(
        prepare(source, fixture_id="N_SUBJECT_SCOPE"), "S03_IDENTITY", "EVIDENCE_IDENTITY_MISMATCH"
    )


def test_w02_t10_conflicting_scope_raw_pin(source):
    direct_fault(source, "N_RAW_PIN", "IMMUTABLE_ID_CONFLICT")
    assert_refusal(prepare(source, fixture_id="N_RAW_PIN"), "S05_TYPED_EVIDENCE", "RAW_PIN_INVALID")


def test_g02_missing_support_attempt(source):
    result = direct(source, "N_SUPPORT")
    assert (result.s1.state, result.s2.state, result.s2.reason) == (
        "UNRESOLVED",
        "UNRESOLVED",
        "CONTENT_BINDING_INSUFFICIENT",
    )
    assert result.s2.diagnostics == ("S1_UNRESOLVED:CONTENT_BINDING_INSUFFICIENT",)
    assert_refusal(prepare(source, fixture_id="N_SUPPORT"), "S04_EVIDENCE", "EVIDENCE_MISSING")


def test_g02_missing_source_records(source):
    direct_fault(source, "N_SOURCE_RECORDS", "SOURCE_RECORDS_ABSENT")
    assert_refusal(
        prepare(source, fixture_id="N_SOURCE_RECORDS"), "S04_EVIDENCE", "EVIDENCE_MISSING"
    )


def test_g02_contradictory_exact_descriptor(source):
    result = direct(source, "N_DESCRIPTOR")
    assert result.s1.state == "BOUND"
    assert isinstance(result.s2, c.BlockingFailure)
    assert result.s2.code == "CONTRADICTORY_TIME_DESCRIPTOR"
    assert_refusal(
        prepare(source, fixture_id="N_DESCRIPTOR"), "S05_TYPED_EVIDENCE", "PROOF_INVALID"
    )


def test_w02_t08_supersedes_not_s3_notice(source):
    prepared = prepare(source)
    assert isinstance(prepared, nr.NativeRequestAssembly)
    assert not hasattr(prepared, "selection")
    assert "AsOfRequest" not in Path(nr.__file__).read_text()
    assert "selection" not in {field.name for field in fields(prepared)}


def test_w02_t11_no_session_week_no_qualification(source, monkeypatch):
    pack = build_pack(source[2])
    schedule = build_weekly_requests(pack)
    assert [json.loads(b)["cutoff"]["source_text"] for b in schedule.requests] == [
        "2027-01-07T18:00:00+08:00",
        "2027-01-15T18:00:00+08:00",
        "2027-01-29T18:00:00+08:00",
        "2027-02-05T18:00:00+08:00",
    ]
    assert [(w.iso_week, w.annotation) for w in schedule.annotations] == [
        ("2027-W03", "NO_SESSION_WEEK")
    ]
    assert (
        next(r for r in source[2]["calendar"] if r["date"] == "2027-01-06")["close"]["source_text"]
        == "2027-01-06T12:00:00+08:00"
    )
    tick = json.loads(schedule.requests[0])
    tick["tick_id"] = "SYN-TICK-2027-01-22"
    calls = []
    monkeypatch.setattr(tq, "evaluate_slice", lambda *a: calls.append(a))
    assert_refusal(
        nr.prepare_native_request(
            pack, input_bytes(tick), assembly(source), profile(source), observe()
        ),
        "S02_TICK",
        "TICK_NOT_MEMBER",
    )
    assert not calls


def test_w02_t12_future_outcome_field_rejected(source):
    pack, tick, evidence, declared = inputs(source)
    bad = json.loads(tick)
    bad["outcome_ref"] = "W02-FORBIDDEN-FUTURE-FEB26-OUTCOME"
    result = nr.prepare_native_request(pack, input_bytes(bad), evidence, declared, observe())
    assert_refusal(result, "S02_TICK", "TICK_INVALID")
    assert result.upstream_error.code == "PROPOSED_FND_FORBIDDEN_DECISION_FIELD"
    prepared, diagnostic = run(source)
    assert not any(
        x in {v.name for v in fields(prepared)}
        for x in ["pinned_pack", "prices", "endpoint_facts", "payload_bytes"]
    )
    assert not hasattr(diagnostic, "to_policy_observation")


def test_w02_t13_diagnostic_flags_no_app_promotion(source):
    prepared, result = run(source)
    assert_temporal(result, "SUPPORTED")
    for value in [prepared, result]:
        assert not hasattr(value, "__dict__")
        assert not hasattr(value, "pit_status")
        assert not hasattr(value, "publish")
    with pytest.raises(FrozenInstanceError):
        result.native_result = None
    with pytest.raises(ValueError):
        replace(result, admission_eligible=True)
    assert not any(
        name in Path(tq.__file__).read_text()
        for name in ["causal_derivation", "diagnostic_projection", "asof_slice"]
    )


def test_w02_t14_same_inputs_local_repeatability(source):
    observed = observe()
    args = inputs(source)
    first = nr.prepare_native_request(*args, observed)
    second = nr.prepare_native_request(*args, observed)
    assert first == second
    a, b = tq.invoke_s1s2(first), tq.invoke_s1s2(second)
    assert a == b
    after = observe()
    assert tq.finalize_diagnostic(a, after) == tq.finalize_diagnostic(b, after)
    assert first.pack_payload_sha256 != first.evidence_fixture_sha256
    assert first.pack_payload_sha256 not in [pin[1] for pin in nr.NATIVE_CODE_PINS]


def test_w02_t15_actual_observation_absent(source, monkeypatch):
    calls = []
    monkeypatch.setattr(tq, "evaluate_slice", lambda *a: calls.append(a))
    args = inputs(source)
    result = nr.prepare_native_request(*args, nr.ObservationUnavailable("ABSENT", (), "No receipt"))
    assert_refusal(result, "S06_OBSERVATION", "OBSERVATION_UNAVAILABLE")
    assert not calls


def test_g04_declared_observed_pin_mismatch(source):
    actual = observe()
    # Controlled test-local copy, not actual observed disk metadata.
    pins = (
        replace(actual.code.observed_working_files[0], sha256="0" * 64),
        *actual.code.observed_working_files[1:],
    )
    controlled = replace(actual, code=replace(actual.code, observed_working_files=pins))
    assert_refusal(
        prepare(source, observed=controlled), "S06_OBSERVATION", "OBSERVATION_PIN_MISMATCH"
    )


def test_g04_foreign_root_or_symlink_refused(source):
    actual = observe()
    for receipt in [
        replace(actual.scope_receipt, actual_root="FOREIGN_ROOT_TEST_ONLY"),
        replace(actual.scope_receipt, no_symlink_check_result=False),
    ]:
        # No stat/read/observer call against a foreign root.
        controlled = replace(actual, scope_receipt=receipt)
        assert_refusal(
            prepare(source, observed=controlled), "S06_OBSERVATION", "OBSERVATION_SCOPE_INVALID"
        )


def test_g04_before_after_native_drift_withholds_completion(source):
    prepared = prepare(source)
    attempt = tq.invoke_s1s2(prepared)
    actual = observe()
    # Altered metadata is an explicitly controlled negative, never a disk observation.
    controlled = replace(actual, code=replace(actual.code, byte_lengths=(0,) * 6))
    failed = tq.finalize_diagnostic(attempt, controlled)
    assert isinstance(failed, tq.W02ObservationFailure)
    assert failed.native_invocation == "RUN"
    assert failed.preserved is attempt
    assert failed.preserved.slice_result.s2.state == "SUPPORTED"
    absent = tq.finalize_diagnostic(
        attempt, nr.ObservationUnavailable("ABSENT", (), "No post receipt")
    )
    assert isinstance(absent, tq.W02ObservationFailure) and absent.native_invocation == "RUN"


def test_g06_compound_fault_stage_order(source):
    pack, _, evidence, declared = inputs(source)
    bad = replace(pack, payload_sha256="0" * 64)
    result = nr.prepare_native_request(
        bad, b"not JSON", evidence, declared, nr.ObservationUnavailable("ABSENT", (), "No receipt")
    )
    assert_refusal(result, "S01_PACK", "PACK_INVALID")
    assert result.upstream_error.code == "PROPOSED_FND_PAYLOAD_PIN_MISMATCH"


def test_g06_wrong_cutoff_same_tick_id(source):
    pack, tick, evidence, declared = inputs(source)
    request = json.loads(tick)
    request["cutoff"]["source_text"] = "2027-01-07T00:00:00+08:00"
    assert_refusal(
        nr.prepare_native_request(pack, input_bytes(request), evidence, declared, observe()),
        "S03_IDENTITY",
        "CUTOFF_IDENTITY_MISMATCH",
    )


def test_exact_evidence_digest_not_status_self_approval(source):
    args = inputs(source)
    pack, tick, evidence, declared = args
    edited = source[0].replace(b'"approved_verified": false', b'"approved_verified": true ')
    assert edited != source[0]
    result = nr.prepare_native_request(
        pack, tick, replace(evidence, reference_fixture_bytes=edited), declared, observe()
    )
    assert_refusal(result, "S04_EVIDENCE", "EVIDENCE_NOT_ADOPTED")
    result = nr.prepare_native_request(
        pack,
        tick,
        replace(evidence, approval=replace(evidence.approval, approved_fixture_sha256="0" * 64)),
        declared,
        observe(),
    )
    assert_refusal(result, "S04_EVIDENCE", "EVIDENCE_NOT_ADOPTED")


def test_pure_invocation_failure_retains_actual_attempted_state(source, monkeypatch):
    prepared = prepare(source)

    def fail(*_):
        raise c.ContractError("CONTROLLED_NATIVE_INVOCATION_FAULT")

    monkeypatch.setattr(tq, "evaluate_slice", fail)
    attempt = tq.invoke_s1s2(prepared)
    assert isinstance(attempt, tq.W02InvocationFailure)
    assert attempt.native_invocation == "ATTEMPTED"
    assert attempt.code == "CONTROLLED_NATIVE_INVOCATION_FAULT"
    result = tq.finalize_diagnostic(
        attempt, nr.ObservationUnavailable("ABSENT", (), "No post receipt")
    )
    assert isinstance(result, tq.W02ObservationFailure) and result.preserved is attempt
    assert result.native_invocation == "ATTEMPTED"


def test_no_io_in_mapper_or_native_invocation(source, monkeypatch):
    actual = observe()
    args = inputs(source)

    def forbidden(*_, **__):
        raise AssertionError("Unexpected caller I/O inside pure W02 operations")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "read_bytes", forbidden)
        guard.setattr(Path, "resolve", forbidden)
        guard.setattr(Path, "stat", forbidden)
        guard.setattr(subprocess, "check_output", forbidden)
        prepared = nr.prepare_native_request(*args, actual)
        assert isinstance(prepared, nr.NativeRequestAssembly)
        result = tq.invoke_s1s2(prepared)
        assert isinstance(result, tq.NativeAttempt) and result.slice_result.s2.state == "SUPPORTED"
    assert isinstance(tq.finalize_diagnostic(result, observe()), tq.W02Diagnostic)


@pytest.mark.parametrize("missing", ["subject_ref", "source_amount"])
def test_null_required_evidence_is_missing_not_contradictory(source, missing):
    pack, tick, evidence, declared = inputs(source)
    value = evidence.candidate_input.assertion.to_value()
    value["fields"][missing] = None
    candidate = replace(evidence.candidate_input, assertion=wire(value))
    result = nr.prepare_native_request(
        pack, tick, replace(evidence, candidate_input=candidate), declared, observe()
    )
    assert_refusal(result, "S04_EVIDENCE", "EVIDENCE_MISSING")


def test_field_origin_must_resolve_to_retained_member(source):
    pack, tick, evidence, declared = inputs(source)
    value = evidence.candidate_input.subject.to_value()
    f(f(value)["origin"])["envelope_pointer"] = "/unretained/subject"
    candidate = replace(evidence.candidate_input, subject=wire(value))
    result = nr.prepare_native_request(
        pack, tick, replace(evidence, candidate_input=candidate), declared, observe()
    )
    assert_refusal(result, "S05_TYPED_EVIDENCE", "MEMBERSHIP_INVALID")


def test_exact_retained_source_and_profile_replacements_are_bound(source):
    pack, tick, evidence, declared = inputs(source)
    record = evidence.records[0]
    modified = record.native_fields.to_value()
    subject = next(iter(modified["source_envelope"]["subjects"].values()))
    f(f(subject)["currency"])["value"] = "UNREVIEWED_CURRENCY"
    changed = replace(evidence, records=(replace(record, native_fields=wire(modified)),))
    assert_refusal(
        nr.prepare_native_request(pack, tick, changed, declared, observe()),
        "S05_TYPED_EVIDENCE",
        "CONTEXT_PROFILE_INVALID",
    )
    bad_binding = replace(
        evidence.source_spec_profiles[0],
        exact_event_replacements=(nr.EventReplacement(0, wire({"forged": 1})),),
    )
    changed = replace(
        evidence, source_spec_profiles=(bad_binding, *evidence.source_spec_profiles[1:])
    )
    assert_refusal(
        nr.prepare_native_request(pack, tick, changed, declared, observe()),
        "S04_EVIDENCE",
        "EVIDENCE_NOT_ADOPTED",
    )


def test_earlier_diagnostic_contains_no_future_price_or_endpoint(source):
    prepared, result = run(source)
    forbidden = {"prices", "endpoint_facts", "outcome_ref", "open_price", "close_price"}

    def visit(value):
        if hasattr(value, "__dataclass_fields__"):
            for item in fields(value):
                assert item.name not in forbidden
                yield from visit(getattr(value, item.name))
        elif isinstance(value, tuple):
            for child in value:
                yield from visit(child)
        elif isinstance(value, (bytes, str)):
            yield value.decode() if isinstance(value, bytes) else value

    values = list(visit(prepared)) + list(visit(result))
    assert not any("2027-01-11" in v or "2027-02-26" in v for v in values)
    # January 11 is earlier than t2: the exclusion is the bounded S1/S2 surface,
    # not an assertion that a January 11 fact is future at every decision.
    later, _ = run(source, "R3", 1)
    assert later.cutoff.source_text == "2027-01-15T18:00:00+08:00"


def test_native_constructor_error_retains_exact_operation(source, monkeypatch):
    args = inputs(source)
    actual = observe()

    def rejected(_):
        raise c.ContractError("CONTROLLED_CONSTRUCTOR_FAULT")

    monkeypatch.setattr(c.IssuerBindingRequest, "__post_init__", rejected)
    result = nr.prepare_native_request(*args, actual)
    assert_refusal(result, "S07_NATIVE_CONSTRUCTORS", "NATIVE_CONSTRUCTOR_REJECTED")
    assert result.upstream_error.exception_type == "ContractError"
    assert result.upstream_error.code == "CONTROLLED_CONSTRUCTOR_FAULT"
    assert result.upstream_error.attempted_operation == "IssuerBindingRequest"


def test_raw_pin_precedes_membership_and_paths_are_sorted(source):
    pack, tick, evidence, declared = inputs(source)
    scope = evidence.candidate_input.scope.to_value()
    f(scope)["raw_pins"] = []
    f(scope)["input_members"] = []
    content = evidence.candidate_input.content.to_value()
    f(content)["raw_sha256"] = "0" * 64
    candidate = replace(evidence.candidate_input, content=wire(content), scope=wire(scope))
    changed = replace(
        evidence,
        candidate_input=candidate,
        records=(replace(evidence.records[0], raw_notice=b"altered"),),
    )
    result = nr.prepare_native_request(pack, tick, changed, declared, observe())
    assert_refusal(result, "S05_TYPED_EVIDENCE", "RAW_PIN_INVALID")
    assert result.evidence_paths == ("/content/raw_pin", "/record/raw_notice", "/scope/raw_pins")


def test_reviewed_oracle_names_are_repository_contained():
    assert len(REVIEWED_PRIMARY_CASES) == 10
    assert len(REVIEWED_NEGATIVE_CASES) == 24
    names = REVIEWED_PRIMARY_CASES + REVIEWED_NEGATIVE_CASES
    assert len(set(names)) == 34
    assert all(callable(globals().get(name)) for name in names)


def test_checkout_anchor_is_portable_and_lexical():
    assert nr._MODULE_CHECKOUT_ROOT == str(ROOT) == trusted_checkout_root().as_posix()
    # Derivation-only alternate checkout: no alternate repository is read,
    # created or observed. The same source layout works independently of cwd.
    alternate = ROOT.parent / (ROOT.name + "-portable-checkout")
    module = alternate / "src/pit_research_lab/mvp/f2/native_requests.py"
    assert nr._source_checkout_root(module.as_posix()) == alternate.as_posix()
    assert alternate != ROOT
    for origin in (
        "src/pit_research_lab/mvp/f2/native_requests.py",
        str(module).replace("/src/", "/./src/"),
        str(module).replace("/src/", "/other/../src/"),
        "/" + str(module),
        str(ROOT / "site-packages/pit_research_lab/mvp/f2/native_requests.py"),
    ):
        assert nr._source_checkout_root(origin) is None


@pytest.mark.parametrize("claim", ["relative", "dot", "parent", "trailing", "double", "foreign"])
def test_noncanonical_or_foreign_absolute_receipt_root_refused(source, claim):
    actual = observe()
    roots = {
        "relative": ROOT.name,
        "dot": str(ROOT) + "/.",
        "parent": str(ROOT) + "/unused/..",
        "trailing": str(ROOT) + "/",
        "double": "/" + str(ROOT),
        "foreign": str(ROOT.parent / (ROOT.name + "-foreign-claim-only")),
    }
    # Only controlled metadata changes; no foreign/symlink path I/O.
    controlled = replace(
        actual, scope_receipt=replace(actual.scope_receipt, actual_root=roots[claim])
    )
    assert_refusal(
        prepare(source, observed=controlled), "S06_OBSERVATION", "OBSERVATION_SCOPE_INVALID"
    )


def test_unsupported_module_layout_fails_closed_without_observer_io(source, monkeypatch):
    args = inputs(source)
    actual = observe()
    monkeypatch.setattr(nr, "_MODULE_CHECKOUT_ROOT", None)

    def forbidden(*_, **__):
        raise AssertionError("No observer I/O for an unverifiable module root")

    monkeypatch.setattr(subprocess, "check_output", forbidden)
    unavailable = observe()
    assert isinstance(unavailable, nr.ObservationUnavailable)
    assert unavailable.failure_kind == "CALLER_SCOPE_REFUSED"
    assert_refusal(
        nr.prepare_native_request(*args, actual), "S06_OBSERVATION", "OBSERVATION_SCOPE_INVALID"
    )
    assert_refusal(
        nr.prepare_native_request(*args, unavailable),
        "S06_OBSERVATION",
        "OBSERVATION_SCOPE_INVALID",
    )


def test_caller_git_toplevel_must_match_loaded_module_checkout(source, monkeypatch):
    # Stub only the verification command, never call an observer on that path.
    foreign = str(ROOT.parent / (ROOT.name + "-foreign-toplevel"))
    monkeypatch.setattr(subprocess, "check_output", lambda *_, **__: foreign + "\n")
    unavailable = observe()
    assert isinstance(unavailable, nr.ObservationUnavailable)
    assert_refusal(
        prepare(source, observed=unavailable), "S06_OBSERVATION", "OBSERVATION_SCOPE_INVALID"
    )


@pytest.mark.parametrize("status", [" M pyproject.toml", "?? unrelated-file"])
def test_unrelated_dirty_status_refused_without_disk_mutation(source, status):
    actual = observe()
    controlled = replace(actual, code=replace(actual.code, worktree_status=status))
    assert_refusal(
        prepare(source, observed=controlled), "S06_OBSERVATION", "OBSERVATION_SCOPE_INVALID"
    )


def test_clean_status_metadata_and_native_length_guard(source):
    actual = observe()
    # The Git status gate accepts a clean committed checkout; this controlled
    # copy tests the predicate only and is never labelled a real disk receipt.
    clean = replace(actual, code=replace(actual.code, worktree_status=""))
    assert nr._observation_reason(clean) is None
    bad = replace(
        actual, code=replace(actual.code, byte_lengths=(0, *actual.code.byte_lengths[1:]))
    )
    assert_refusal(prepare(source, observed=bad), "S06_OBSERVATION", "OBSERVATION_PIN_MISMATCH")


def test_caller_rejects_symlink_component_before_git_or_descendant_io(source, monkeypatch):
    args = inputs(source)
    original = Path.is_symlink

    def controlled_symlink(path):
        return True if path == ROOT else original(path)

    def forbidden(*_, **__):
        raise AssertionError("Unsafe root must be refused before descendant/Git I/O")

    monkeypatch.setattr(Path, "is_symlink", controlled_symlink)
    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "is_file", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    unavailable = observe()
    assert isinstance(unavailable, nr.ObservationUnavailable)
    assert_refusal(
        nr.prepare_native_request(*args, unavailable),
        "S06_OBSERVATION",
        "OBSERVATION_SCOPE_INVALID",
    )
