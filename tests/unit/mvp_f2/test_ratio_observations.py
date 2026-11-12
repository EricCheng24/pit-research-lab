"""B1 adapter positives and explicitly separate public-Native hostile controls.

No source completion is manufactured by a tested candidate list. The zero
fixture and oracle were frozen before its first Native control invocation.
"""

import ast
import gzip
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import ratio, ratio_slice
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.asof_slice import AsOfRequest
from pit_research_lab.domain.derivation import DependencySlot, DerivedResult, FeatureSpec
from pit_research_lab.domain.pit_slice import observe_code
from pit_research_lab.domain.ratio import FixedRatio
from pit_research_lab.mvp.f2 import asof_requests as ar
from pit_research_lab.mvp.f2 import derived_observations as d
from pit_research_lab.mvp.f2 import native_requests as nr
from pit_research_lab.mvp.f2 import ratio_observations as b
from pit_research_lab.mvp.f2.synthetic_temporal import build_pack, build_weekly_requests

ROOT = Path(__file__).parents[3]
DATA = Path(__file__).parent / "data"
NEW_PATHS = (
    b.ADAPTER_PATH,
    "tests/unit/mvp_f2/test_ratio_observations.py",
    "tests/unit/mvp_f2/data/ratio_observations_v0.1.json",
)
ZERO_SHA = "138fbc025ee2c99afda14105f150d9367845ec5eec9f7b2ced009d2813004b29"
ZERO_LENGTH = 344_748
ZERO_ORACLE_SHA = "9c819097cb6c1c38f26b169e4c5a392d53d97659f1242ccc6fcc1d0e6abb725c"
CONTROL_RESULTS = []


def wire(value):
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            **{
                f.name: (
                    {
                        "external_baseline_source": "tests/unit/mvp_f2/data/derived_observations_v0.1.json",
                        "baseline_sha256": d.FIXTURE_SHA256,
                        "supplied_sha256": sha256(getattr(value, f.name)).hexdigest(),
                        "supplied_byte_length": len(getattr(value, f.name)),
                    }
                    if f.name == "source_packet_bytes"
                    else wire(getattr(value, f.name))
                )
                for f in fields(value)
                if not f.name.startswith("_")
            },
        }
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, (tuple, list)):
        return [wire(x) for x in value]
    return value


# Test-local input-only decoder, never imported by production. No result classes.
INPUTS = {
    cls.__name__: cls
    for cls in (
        c.Known,
        c.Unknown,
        c.NotApplicable,
        c.NotEvaluated,
        c.OriginKnownValue,
        c.OriginUnknownValue,
        c.FieldOrigin,
        c.SubjectFacts,
        c.AssertionFacts,
        c.ContentFacts,
        c.RequestedTuple,
        c.PublicationEventFacts,
        c.AwareInstant,
        c.TimeProof,
        c.SupportBinding,
        c.RequestBindingAttempt,
        c.RoleRef,
        c.ContentPin,
        c.SourceRecords,
        c.S1Scope,
        c.IssuerBindingRequest,
        c.CandidateProfile,
        c.CodePin,
        c.TemporalPolicy,
        c.SemanticContext,
        s.CandidateSource,
        s.DirectRelation,
        s.RevisionScope,
        s.SelectionPolicy,
        s.CoverageCheck,
        s.BoundedCoverage,
        s.DiscoveryEvidence,
        s.RelationSource,
        AsOfRequest,
    )
}


def blob(record):
    body = record["utf8"].encode()
    assert type(record["byte_length"]) is int and len(body) == record["byte_length"]
    assert sha256(body).hexdigest() == record["sha256"]
    return body


def decode(value, sources=None, blobs=None):
    sources = sources or {}
    blobs = blobs or {}
    if isinstance(value, list):
        return tuple(decode(x, sources, blobs) for x in value)
    if not isinstance(value, dict):
        return value
    if set(value) == {"source_ref"}:
        return sources[value["source_ref"]]
    if set(value) == {"blob_ref"}:
        return blob(blobs[value["blob_ref"]])
    if set(value) == {"bytes_hex"}:
        return bytes.fromhex(value["bytes_hex"])
    if set(value) == {"date"}:
        return date.fromisoformat(value["date"])
    cls = INPUTS[value["type"]]
    fs = {f.name: f for f in fields(cls)}
    assert set(value) == {"type", *fs}
    kw = {k: decode(v, sources, blobs) for k, v in value.items() if k != "type"}
    if cls in (c.FieldOrigin, c.RoleRef):
        kw["visibility"] = c.Visibility(kw["visibility"])
    if cls in (c.Unknown, c.OriginUnknownValue):
        kw["cause"] = c.UnknownCause(kw["cause"])
    result = cls(**{k: v for k, v in kw.items() if fs[k].init})
    assert all(getattr(result, k) == v for k, v in kw.items())
    return result


@contextmanager
def count_native_calls():
    """Monitor only real owner entry; never replace/mock the Native evaluator."""
    calls = []
    monitor = sys.monitoring
    tool_id = next(i for i in range(5, -1, -1) if monitor.get_tool(i) is None)
    monitor.use_tool_id(tool_id, "WU03B1_NATIVE_ENTRY_COUNTER")
    event = monitor.events.PY_START
    code = ratio_slice.evaluate_ratio.__code__
    monitor.register_callback(
        tool_id, event, lambda entered, _offset: calls.append(entered.co_name)
    )
    monitor.set_local_events(tool_id, code, event)
    try:
        yield calls
    finally:
        monitor.set_local_events(tool_id, code, 0)
        monitor.register_callback(tool_id, event, None)
        monitor.free_tool_id(tool_id)


@pytest.fixture(scope="module", autouse=True)
def retained_control_evidence():
    yield
    if destination := os.environ.get("WU03B1_CONTROL_EVIDENCE_OUTPUT"):
        path = Path(destination)
        assert path.is_absolute() and not path.is_relative_to(ROOT)
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(
                {
                    "kind": "ACTUAL_DIRECT_NATIVE_OR_CONTROLLED_ADAPTER_FAILURES",
                    "cases": CONTROL_RESULTS,
                },
                stream,
                sort_keys=True,
            )


def retain_control(result, boundary):
    CONTROL_RESULTS.append(
        {
            "case": os.environ.get("PYTEST_CURRENT_TEST", "MODULE_SETUP"),
            "boundary": boundary,
            "actual_result": wire(result),
        }
    )
    return result


@pytest.fixture(scope="module")
def inputs():
    body = (DATA / "derived_observations_v0.1.json").read_bytes()
    assert len(body) == d.FIXTURE_LENGTH and sha256(body).hexdigest() == d.FIXTURE_SHA256
    foundation_body = (DATA / "temporal_foundation_v0.1.json").read_bytes()
    assert len(foundation_body) == 72_800
    assert (
        sha256(foundation_body).hexdigest()
        == "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373"
    )
    foundation = json.loads(foundation_body)
    pack = build_pack(foundation["input_spec"], foundation["default_seed"])
    assert pack.payload_sha256 == d.PACK_SHA256
    return body, json.loads(body), pack, build_weekly_requests(pack).requests


@pytest.fixture(scope="module")
def completed(inputs):
    body, _, pack, ticks = inputs
    before = b.observe_ratio_diagnostic_code()
    wu03 = d.observe_wu03_code()
    assert isinstance(before, b.ObservedRatioCode), before
    assert isinstance(wu03, d.WU03ObservedCodeInput), wu03
    assemblies, attempts, diagnostics, timing = [], [], [], []
    for tick in ticks:
        start = time.perf_counter()
        assembly = b.prepare_ratio_request(pack, tick, body, wu03, before)
        prepared = time.perf_counter()
        assert isinstance(assembly, b.RatioRequestAssembly), assembly
        with count_native_calls() as calls:
            attempt = b.invoke_ratio(assembly)
        invoked = time.perf_counter()
        assert calls == ["evaluate_ratio"]
        assert isinstance(attempt, b.NativeRatioAttempt), attempt
        after = b.observe_ratio_diagnostic_code()
        after_wu03 = d.observe_wu03_code()
        diagnostic = b.finalize_ratio_diagnostic(attempt, after, after_wu03)
        assert isinstance(diagnostic, b.RatioDiagnostic), diagnostic
        assert diagnostic.native_result is attempt.native_result
        assemblies.append(assembly)
        attempts.append(attempt)
        diagnostics.append(diagnostic)
        timing.append(
            {
                "prepare_seconds": prepared - start,
                "invoke_seconds": invoked - prepared,
                "finalize_and_observe_seconds": time.perf_counter() - invoked,
            }
        )
    assert before == b.observe_ratio_diagnostic_code()
    if destination := os.environ.get("WU03B1_EVIDENCE_OUTPUT"):
        path = Path(destination)
        assert path.is_absolute() and not path.is_relative_to(ROOT)
        payload = {
            "kind": "ACTUAL_B1_ADAPTER_PUBLIC_NATIVE_FINALIZER",
            "source_fixture_sha256": d.FIXTURE_SHA256,
            "before": wire(before),
            "after": wire(b.observe_ratio_diagnostic_code()),
            "timing": timing,
            "diagnostics": [wire(x) for x in diagnostics],
            "private_process_witnesses": "not portable; actual issuing APIs used",
        }
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
    return tuple(assemblies), tuple(attempts), tuple(diagnostics)


@pytest.mark.parametrize(
    "i,total,month,text,scaled",
    [
        (0, 140, 100, "0.714286", 714286),
        (1, 150, 110, "0.733333", 733333),
        (2, 150, 110, "0.733333", 733333),
        (3, 130, 90, "0.692308", 692308),
    ],
)
def test_B1_T01_T02_actual_adapter_native_finalizer(completed, i, total, month, text, scaled):
    assembly, attempt, diagnostic = (group[i] for group in completed)
    result = diagnostic.native_result
    assert result is attempt.native_result
    assert (result.outcome.state, result.outcome.reason) == ("VALUE_AVAILABLE", "NONE")
    assert isinstance(result.outcome.value, FixedRatio)
    assert (result.outcome.value.decimal_text, result.outcome.value.scaled_units) == (text, scaled)
    up = result.upstream_a04
    assert isinstance(up, DerivedResult) and up.outcome.value == total
    assert [line.value for line in up.outcome.lineage] == [17, 23, month]
    assert [line.slot_ref for line in up.outcome.lineage] == ["M1", "M2", "M3"]
    assert len({line.subject_ref for line in up.outcome.lineage}) == 3
    assert [line.period[0].month for line in up.outcome.lineage] == [10, 11, 12]
    for dep, line in zip(up.dependencies, up.outcome.lineage, strict=True):
        assert dep.actual.selection.state == "SELECTED"
        selected = [x for x in dep.actual.inputs.candidates if x.ref in line.assertion_refs]
        assert len(selected) == 1
        actual = selected[0].actual
        assert actual.s1.state == "BOUND" and actual.s2.state == "SUPPORTED"
        assert line.raw_sha256s == (actual.request.content.raw_sha256,)
        assert line.content_version_refs == (actual.request.content.content_version_ref,)
        assert line.representation_refs == (actual.request.content.representation_ref,)
        assert (
            dep.slot.request.context.profile.code_pins
            == result.code.upstream_a04.observed_working_files
        )
    assert result.research_only_audit.exact_fraction == (month, total)
    assert json.loads(result.diagnostic_preview_bytes)["value"] == text
    assert ("packet_sha256", d.FIXTURE_SHA256) in diagnostic.source_identity
    assert ("oracle_sha256", d.ORACLE_SHA256) in diagnostic.source_identity
    assert assembly.upstream.before_observation.code == result.code.upstream_a04


@pytest.mark.parametrize("index", range(4))
def test_B1_T03_adapter_replay_and_stable_identity(completed, index):
    assembly = completed[0][index]
    replay = b.invoke_ratio(assembly)
    assert isinstance(replay, b.NativeRatioAttempt)
    final = b.finalize_ratio_diagnostic(
        replay, b.observe_ratio_diagnostic_code(), d.observe_wu03_code()
    )
    assert final == completed[2][index]
    assert replay.native_result == completed[1][index].native_result


def test_B1_T03_equal_values_keep_cutoff_identity(completed):
    left, right = (completed[2][i] for i in (1, 2))
    assert left.native_result.outcome.value == right.native_result.outcome.value
    assert left.identity != right.identity
    assert left.native_result.realization_ref != right.native_result.realization_ref
    ldep = left.native_result.upstream_a04.dependencies[2]
    rdep = right.native_result.upstream_a04.dependencies[2]
    assert ldep.actual.reconstruction_ref != rdep.actual.reconstruction_ref
    assert (
        ldep.slot.request.context.information_cutoff != rdep.slot.request.context.information_cutoff
    )


def test_B1_T04_original_equal_and_future_exclusion(inputs, completed):
    from pit_research_lab.domain.pit_slice import evaluate_slice

    sources = {x["tag"]: decode(x["source"]) for x in inputs[1]["sources"]}
    for index, tag, excluded in (
        (0, "D2", {"PREP01-A-D2", "PREP01-A-N12"}),
        (2, "D3", {"PREP01-A-D3", "PREP01-A-N23"}),
    ):
        result = completed[1][index].native_result
        actual = result.upstream_a04.dependencies[2]
        assert not excluded & {x.ref for x in actual.actual.inputs.candidates}
        assessed = evaluate_slice(
            actual.slot.request.context, sources[tag].request, result.code.upstream_a04
        )
        assert (assessed.s2.state, assessed.s2.reason) == (
            "NOT_ADMISSIBLE",
            "PUBLICATION_NOT_PRE_CUTOFF",
        )
        retain_control(assessed, "DIRECT_PUBLIC_NATIVE_S1S2_EQUAL_OR_FUTURE_SOURCE")


def native_control(completed, index=0, slots=None, spec=None, sum_spec=None, code=None):
    """DIRECT PUBLIC NATIVE control; never represented as B1 prepared input."""
    a = completed[0][index]
    result = ratio_slice.evaluate_ratio(
        spec or a.specification,
        sum_spec or a.upstream.specification,
        a.upstream.slots if slots is None else slots,
        code or a.before_observation.code,
    )
    return retain_control(result, "DIRECT_PUBLIC_NATIVE")


def test_B1_T04_direct_native_audit_only_context_does_not_change_preview(completed):
    a = completed[0][0]
    slots = tuple(
        replace(
            slot,
            request=replace(
                slot.request,
                context=replace(
                    slot.request.context, decision_wall_times=("FUTURE_NOTICE_AUDIT_ONLY",)
                ),
            ),
        )
        for slot in a.upstream.slots
    )
    actual = native_control(completed, slots=slots)
    assert actual.diagnostic_preview_bytes == completed[1][0].native_result.diagnostic_preview_bytes
    assert actual.outcome.value == completed[1][0].native_result.outcome.value


def test_B1_T05_direct_native_independently_authored_signed_source(inputs, completed):
    control = next(x for x in inputs[1]["native_controls"] if x["tag"] == "SIGNED")
    request = decode(control["request"])
    slots = (
        DependencySlot("M1", request.subject, request),
        *completed[0][0].upstream.slots[1:],
    )
    result = native_control(completed, slots=slots)
    assert result.upstream_a04.outcome.value == 82
    assert result.upstream_a04.outcome.lineage[0].value == -41
    assert (result.outcome.state, result.outcome.reason) == (
        "NOT_COMPUTABLE",
        "NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN",
    )


def test_B1_T06_direct_native_frozen_three_distinct_zero_sources(completed):
    body = (DATA / "ratio_observations_v0.1.json").read_bytes()
    assert len(body) == ZERO_LENGTH and sha256(body).hexdigest() == ZERO_SHA
    packet = json.loads(body)
    assert packet["oracle_sha256"] == ZERO_ORACLE_SHA
    canonical = json.dumps(packet["oracle"], sort_keys=True, separators=(",", ":")).encode()
    assert sha256(canonical).hexdigest() == ZERO_ORACLE_SHA
    sources = {}
    for source in packet["sources"]:
        blob(source["raw"])
        blob(source["publication_descriptor"])
        blob(source["source_records_raw"])
        sources[source["tag"]] = decode(source["source"])
    for raw in packet["blobs"].values():
        blob(raw)
    requests = []
    for view in packet["views"]:
        request = decode(view["request"], sources, packet["blobs"])
        assert s.discovery_proposition(request.discovery) == request.discovery.raw_bytes
        page = json.loads(blob(packet["blobs"][view["page_blob"]]))
        assert page["terminal"] is True and page["next_page"] is None
        assert (tuple(page["members"]),) == request.discovery.pages
        assert len(view["operations"]) == 3
        for operation, check in zip(view["operations"], request.coverage.checks, strict=True):
            assert operation["source_author_declaration"]["status"] == check.status == "COMPLETED"
            assert blob(packet["blobs"][operation["raw_blob"]]) == check.evidence_bytes
        requests.append(request)
    slots = tuple(DependencySlot(f"M{i + 1}", r.subject, r) for i, r in enumerate(requests))
    sum_spec = FeatureSpec("B1-ZERO-DIRECT-NATIVE-SUM", 2026, 4, "SYN-A")
    spec = ratio.RatioFeatureSpec(
        "B1-ZERO-DIRECT-NATIVE-SHARE", sum_spec.feature_ref, "SYN-A", 2026, 4
    )
    result = native_control(completed, slots=slots, spec=spec, sum_spec=sum_spec)
    assert result.upstream_a04.outcome.value == 0
    assert len(result.upstream_a04.outcome.lineage) == 3
    assert all(d.actual.selection.state == "SELECTED" for d in result.upstream_a04.dependencies)
    assert (result.outcome.state, result.outcome.reason) == (
        "NOT_COMPUTABLE",
        "ZERO_QUARTER_REVENUE_DENOMINATOR",
    )
    assert isinstance(result.outcome.value, c.NotEvaluated)
    # The production source boundary does not admit the new control profile.
    a = completed[0][0]
    refused = b.prepare_ratio_request(
        a.pack,
        a.upstream.exact_tick_bytes,
        body,
        a.upstream.before_observation,
        a.before_observation,
    )
    assert isinstance(refused, b.MappingRefusal) and refused.reason == "WU03_SOURCE_NOT_ACCEPTED"


@pytest.mark.parametrize(
    "changes",
    [{"scale": 2}, {"numerator_role": "M1"}, {"prior_derived_sum_ref": "UNRELATED_SUM"}],
)
def test_B1_T07_direct_native_invalid_ratio_contract(completed, changes):
    result = native_control(completed, spec=replace(completed[0][0].specification, **changes))
    assert (result.outcome.state, result.outcome.reason) == (
        "CONTRACT_VIOLATION",
        "UNSUPPORTED_RATIO_FEATURE_CONTRACT",
    )
    assert isinstance(result.upstream_a04, c.NotEvaluated)


@pytest.mark.parametrize(
    "kind,state,reason",
    [
        ("missing_discovery", "UNRESOLVED", "DEPENDENCY_UNRESOLVED"),
        ("missing_candidate", "CONTRACT_VIOLATION", "COVERAGE_UNIVERSE_MISMATCH"),
    ],
)
def test_B1_T08_direct_native_no_invented_absence(completed, kind, state, reason):
    a = completed[0][0]
    first = a.upstream.slots[0]
    req = (
        replace(first.request, discovery=c.NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT"))
        if kind == "missing_discovery"
        else replace(first.request, candidates=())
    )
    result = native_control(completed, slots=(replace(first, request=req), *a.upstream.slots[1:]))
    assert (result.outcome.state, result.outcome.reason) == (state, reason)
    assert isinstance(result.outcome.value, c.NotEvaluated)
    assert isinstance(result.diagnostic_preview_bytes, c.NotEvaluated)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("economic_entity_ref", "SYN-B", "INCOMPATIBLE_SUBJECT_ECONOMIC_ENTITY_REF"),
        ("canonical_unit", "NTD", "INCOMPATIBLE_SUBJECT_CANONICAL_UNIT"),
        ("basis_ref", "FOREIGN_BASIS", "INCOMPATIBLE_SUBJECT_BASIS_REF"),
        ("period_start", date(2026, 10, 2), "INCOMPATIBLE_SUBJECT_PERIOD_START"),
    ],
)
def test_B1_T09_direct_native_subject_fault_priority(completed, field, value, reason):
    a = completed[0][0]
    first = a.upstream.slots[0]
    subject = replace(
        first.expected_subject, **{field: c.Known(value, first.expected_subject.origin)}
    )
    req = replace(first.request, subject=subject)
    result = native_control(
        completed,
        slots=(replace(first, expected_subject=subject, request=req), *a.upstream.slots[1:]),
    )
    assert (result.outcome.state, result.outcome.reason) == ("CONTRACT_VIOLATION", reason)
    assert result.upstream_a04.dependencies[0].actual.selection.code == "DISCOVERY_CONTEXT_MISMATCH"


@pytest.mark.parametrize("kind", ["missing", "duplicate"])
def test_B1_T09_direct_native_slots(completed, kind):
    slots = completed[0][0].upstream.slots
    changed = slots[:2] if kind == "missing" else (slots[0], slots[0], slots[2])
    assert native_control(completed, slots=changed).outcome.reason == "MISSING_OR_DUPLICATE_SLOT"


@pytest.mark.parametrize("kind", ["packet", "clock", "manifest", "pack"])
def test_B1_T09_precall_refusal_never_calls_native(inputs, completed, kind):
    body, _, pack, ticks = inputs
    tick = ticks[0]
    if kind == "packet":
        body += b" "
    elif kind in {"clock", "manifest"}:
        parsed = json.loads(tick)
        if kind == "clock":
            parsed["cutoff"]["source_text"] = "2027-01-08T00:00:00+08:00"
        else:
            parsed["manifest_ref"] = "UNRELATED_MANIFEST"
        tick = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    else:
        pack = replace(pack, payload_sha256="0" * 64)
    a = completed[0][0]
    with count_native_calls() as calls:
        refused = b.prepare_ratio_request(
            pack, tick, body, a.upstream.before_observation, a.before_observation
        )
    assert calls == []
    assert isinstance(refused, b.MappingRefusal) and refused.native_invocation == "NOT_RUN"
    retain_control(refused, "ADAPTER_PRECALL_NOT_RUN")


def test_B1_T10_actual_ten_plus_two_and_local_pin(completed):
    value = completed[0][0].before_observation
    core = value.code.upstream_a04
    assert len(core.observed_working_files) == 10
    assert len(value.code.extension_pins) == 2
    assert value.checkout_root == str(ROOT)
    assert value.local_pins[0] == (
        b.ADAPTER_PATH,
        sha256((ROOT / b.ADAPTER_PATH).read_bytes()).hexdigest(),
        (ROOT / b.ADAPTER_PATH).stat().st_size,
    )
    assert b._observation_reason(value) is None


@pytest.mark.parametrize("upstream_count,extension_count", [(6, 0), (8, 0), (9, 2), (10, 3)])
def test_B1_T10_controlled_forged_observation_refused(
    inputs, completed, upstream_count, extension_count
):
    actual = b.observe_ratio_diagnostic_code()
    assert isinstance(actual, b.ObservedRatioCode)
    code = actual.code
    core = replace(
        code.upstream_a04,
        observed_working_files=code.upstream_a04.observed_working_files[:upstream_count],
        byte_lengths=code.upstream_a04.byte_lengths[:upstream_count],
    )
    extensions = (*code.extension_pins, code.extension_pins[0])[:extension_count]
    lengths = (*code.extension_byte_lengths, code.extension_byte_lengths[0])[:extension_count]
    # Controlled hostile metadata on an issued receipt; never labeled actual disk.
    object.__setattr__(
        actual,
        "code",
        replace(code, upstream_a04=core, extension_pins=extensions, extension_byte_lengths=lengths),
    )
    a = completed[0][0]
    result = b.prepare_ratio_request(
        inputs[2], inputs[3][0], inputs[0], a.upstream.before_observation, actual
    )
    assert isinstance(result, b.MappingRefusal)
    assert result.reason == "B1_OBSERVATION_PIN_OR_SCOPE_MISMATCH"
    retain_control(result, "ADAPTER_PRECALL_CONTROLLED_MALFORMED_OBSERVATION_NOT_RUN")


def test_B1_T11_unissued_receipts_and_assembly_rejected(inputs, completed):
    a = completed[0][0]
    fake = replace(a.before_observation)
    assert b._observation_reason(fake) == "B1_OBSERVATION_NOT_ISSUED"
    refusal = b.invoke_ratio(replace(a))
    assert isinstance(refusal, b.MappingRefusal) and refusal.native_invocation == "NOT_RUN"
    fake_after_wu03 = replace(a.upstream.before_observation)
    failure = b.finalize_ratio_diagnostic(completed[1][0], a.before_observation, fake_after_wu03)
    assert isinstance(failure, b.ObservationFailure)
    assert failure.reason == "B1_UPSTREAM_AFTER_REFUSED:WU03_OBSERVATION_NOT_ISSUED"
    retain_control(failure, "ADAPTER_CONTROLLED_UNISSUED_UPSTREAM_AFTER_REAL_RUN")
    with pytest.raises(ValueError, match="B1_ISSUED_ATTEMPT_REQUIRED"):
        b.finalize_ratio_diagnostic(
            b.NativeRatioAttempt(a, completed[1][0].native_result),
            a.before_observation,
            fake_after_wu03,
        )


def test_B1_T11_before_after_and_attempt_assembly_drift(completed):
    a = completed[0][0]
    attempt = b.invoke_ratio(a)
    assert isinstance(attempt, b.NativeRatioAttempt)
    original_result = attempt.native_result
    object.__setattr__(attempt, "assembly", completed[0][1])
    failure = b.finalize_ratio_diagnostic(
        attempt, b.observe_ratio_diagnostic_code(), d.observe_wu03_code()
    )
    assert isinstance(failure, b.ObservationFailure)
    assert failure.reason == "B1_ATTEMPT_ASSEMBLY_CHANGED"
    assert failure.preserved.native_result is original_result
    assert failure.native_invocation == "RUN"
    retain_control(failure, "ADAPTER_CONTROLLED_ATTEMPT_INPUT_SUBSTITUTION_AFTER_REAL_RUN")


def test_B1_T11_after_missing_preserves_real_run(completed):
    attempt = completed[1][0]
    failure = b.finalize_ratio_diagnostic(
        attempt, b.ObservationUnavailable("CONTROLLED_MISSING_AFTER"), d.observe_wu03_code()
    )
    assert isinstance(failure, b.ObservationFailure) and failure.preserved is attempt
    assert failure.reason == "CONTROLLED_MISSING_AFTER" and failure.native_invocation == "RUN"
    retain_control(failure, "ADAPTER_CONTROLLED_MISSING_AFTER_REAL_RUN")


def test_B1_T11_symlink_hardlink_and_loaded_root(tmp_path, monkeypatch):
    target = tmp_path / "regular"
    target.write_bytes(b"synthetic")
    sym = tmp_path / "symlink"
    sym.symlink_to(target)
    with pytest.raises(c.ContractError, match="B1_SYMLINK_REFUSED"):
        b._regular_bytes(sym)
    hard = tmp_path / "hardlink"
    os.link(target, hard)
    with pytest.raises(c.ContractError, match="B1_NONREGULAR_OR_LINKED"):
        b._regular_bytes(hard)
    monkeypatch.setattr(
        b, "__file__", "/unapproved/src/pit_research_lab/mvp/f2/ratio_observations.py"
    )
    observed = b.observe_ratio_diagnostic_code()
    assert isinstance(observed, b.ObservationUnavailable)
    assert observed.reason == "B1_LOADED_OWNER_ROOT_MISMATCH"


def test_B1_T11_disk_byte_drift_control(monkeypatch):
    original = b._regular_bytes

    def corrupt(path):
        data = original(path)
        return data + b"# controlled byte drift" if path == ROOT / b.EXTENSION_PINS[0][0] else data

    monkeypatch.setattr(b, "_regular_bytes", corrupt)
    observed = b.observe_ratio_diagnostic_code()
    assert isinstance(observed, b.ObservationUnavailable)
    assert observed.reason == "B1_NATIVE_DISK_PIN_MISMATCH"


def w02_actual():
    code = observe_code(ROOT)
    receipt = nr.CallerObservationReceipt(
        "MVP-F2-WU-02-S1S2-IMPL-01",
        str(ROOT),
        tuple(p[0] for p in nr.NATIVE_CODE_PINS),
        "B1_ACTUAL_SIX_PATH_OBSERVATION",
        "pit_slice.observe_code",
        True,
    )
    return nr.ObservedCodeInput(code, receipt)


@pytest.mark.parametrize("path", NEW_PATHS)
@pytest.mark.parametrize("prefix", ["?? ", " M "])
def test_B1_T12_exact_literals_all_status_owners(path, prefix):
    # Pure parser hostile/compatibility data, not substituted actual Git output.
    status = prefix + path
    actual = w02_actual()
    controlled = replace(actual, code=replace(actual.code, worktree_status=status))
    assert nr._observation_reason(controlled) is None
    assert ar._status_valid(status) and d._status_valid(status) and b._status_valid(status)


def test_B1_T12_staged_differences_and_unrelated_denial():
    actual = w02_actual()
    staged = "A  " + NEW_PATHS[0]
    controlled = replace(actual, code=replace(actual.code, worktree_status=staged))
    assert nr._observation_reason(controlled) is None
    assert (
        not ar._status_valid(staged) and not d._status_valid(staged) and not b._status_valid(staged)
    )
    assert ar._status_valid("M  " + NEW_PATHS[0])
    assert not d._status_valid("M  " + NEW_PATHS[0])
    for bad in (
        "?? unrelated-file",
        " M pyproject.toml",
        "R  a -> b",
        "UU x",
        "malformed",
        "?? ../escape",
    ):
        assert not ar._status_valid(bad) and not d._status_valid(bad) and not b._status_valid(bad)
        controlled = replace(actual, code=replace(actual.code, worktree_status=bad))
        assert nr._observation_reason(controlled) == nr.W02AdapterReason.OBSERVATION_SCOPE_INVALID


def test_B1_T13_real_owner_entered_formatter_fault_is_attempted(completed, monkeypatch):
    def formatting_fault(_value):
        raise RuntimeError("CONTROLLED_NATIVE_FORMAT_FAILURE")

    # The real public evaluator and all A04 computations run. Only its final
    # nonnumerical JSON formatter is fault-injected; no evaluator/formula mock.
    monkeypatch.setattr(ratio, "_canonical", formatting_fault)
    with count_native_calls() as calls:
        failure = b.invoke_ratio(completed[0][0])
    assert calls == ["evaluate_ratio"]
    assert isinstance(failure, b.InvocationFailure)
    assert failure.native_invocation == "ATTEMPTED"
    assert failure.exact_native_exception_type == "RuntimeError"
    assert failure.code == "CONTROLLED_NATIVE_FORMAT_FAILURE"
    assert failure.diagnostic_only and not failure.admission_eligible
    assert failure.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert failure.source_authentication == "NOT_ESTABLISHED"
    retain_control(failure, "REAL_NATIVE_ENTERED_CONTROLLED_NONNUMERICAL_FORMATTER_FAULT_ATTEMPTED")
    final = b.finalize_ratio_diagnostic(
        failure, b.observe_ratio_diagnostic_code(), d.observe_wu03_code()
    )
    assert final is failure
    after_failure = b.finalize_ratio_diagnostic(
        failure, b.ObservationUnavailable("AFTER_UNAVAILABLE"), d.observe_wu03_code()
    )
    assert isinstance(after_failure, b.ObservationFailure)
    assert after_failure.native_invocation == "ATTEMPTED" and after_failure.preserved is failure
    retain_control(after_failure, "ADAPTER_CONTROLLED_MISSING_AFTER_ATTEMPTED_FAULT")


def test_B1_T14_diagnostic_flags_and_no_extra_runtime(completed):
    diagnostic = completed[2][0]
    a = completed[0][0]
    refused = b.prepare_ratio_request(
        a.pack,
        a.upstream.exact_tick_bytes,
        b"unaccepted",
        a.upstream.before_observation,
        a.before_observation,
    )
    assert isinstance(refused, b.MappingRefusal)
    for output in (diagnostic, a, a.before_observation, completed[1][0], refused):
        assert output.diagnostic_only and not output.admission_eligible
        assert output.disposition == "INTEGRATED_PROVISIONAL"
        assert output.trust == "NOT_TRUSTED_PIT_EVIDENCE"
        assert output.source_authentication == "NOT_ESTABLISHED"
        with pytest.raises(ValueError):
            replace(output, admission_eligible=True)
    assert diagnostic.native_invocation == "RUN" and diagnostic.diagnostic_only
    assert not diagnostic.admission_eligible
    assert diagnostic.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert diagnostic.source_authentication == "NOT_ESTABLISHED"
    assert diagnostic.disposition == "INTEGRATED_PROVISIONAL"
    for forbidden in (
        "candidate_bytes",
        "publish",
        "export",
        "fit",
        "universe",
        "agent_observation",
    ):
        assert not hasattr(diagnostic, forbidden)
    with pytest.raises(ValueError):
        replace(diagnostic, admission_eligible=True)
    with pytest.raises(FrozenInstanceError):
        diagnostic.identity = "UNRELATED"
    tree = ast.parse((ROOT / b.ADAPTER_PATH).read_text())
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        "causal" in name or "diagnostic_projection" in name or "tests" in name for name in imports
    )
    assert "Any" not in (ROOT / b.ADAPTER_PATH).read_text()


def test_B1_T03_direct_native_candidate_order_noninterference(completed):
    a = completed[0][3]
    slots = tuple(
        replace(
            slot,
            request=replace(
                slot.request,
                candidates=tuple(reversed(slot.request.candidates)),
                relations=tuple(reversed(slot.request.relations)),
            ),
        )
        for slot in a.upstream.slots
    )
    result = native_control(completed, index=3, slots=slots)
    original = completed[1][3].native_result
    assert result.outcome == original.outcome
    assert result.realization_ref == original.realization_ref
    assert result.diagnostic_preview_bytes == original.diagnostic_preview_bytes


def test_B1_T11_inputs_changed_after_preparation_never_invoke(inputs, completed):
    a = completed[0][0]
    fresh = b.prepare_ratio_request(
        a.pack,
        a.upstream.exact_tick_bytes,
        inputs[0],
        a.upstream.before_observation,
        a.before_observation,
    )
    assert isinstance(fresh, b.RatioRequestAssembly)
    object.__setattr__(fresh.upstream, "source_packet_bytes", inputs[0] + b" ")
    with count_native_calls() as calls:
        refusal = b.invoke_ratio(fresh)
    assert calls == []
    assert isinstance(refusal, b.MappingRefusal) and refusal.reason == "B1_ASSEMBLY_CHANGED"
    retain_control(refusal, "ADAPTER_PRECALL_NOT_RUN_CONTROLLED_INPUT_DRIFT")


def test_B1_T11_controlled_after_local_metadata_drift(completed):
    after = b.observe_ratio_diagnostic_code()
    assert isinstance(after, b.ObservedRatioCode)
    first, *rest = after.local_pins
    object.__setattr__(after, "local_pins", ((first[0], "0" * 64, first[2]), *rest))
    actual_attempt = completed[1][0]
    failure = b.finalize_ratio_diagnostic(actual_attempt, after, d.observe_wu03_code())
    assert isinstance(failure, b.ObservationFailure)
    assert failure.reason == "B1_OBSERVATION_CHANGED"
    assert failure.preserved is actual_attempt and failure.native_invocation == "RUN"
    retain_control(failure, "CONTROLLED_METADATA_DRIFT_AFTER_ACTUAL_ADAPTER_RUN")


def test_B1_T11_during_read_drift_and_foreign_native_origin(monkeypatch):
    original = b._regular_bytes
    reads = 0

    def drift(path):
        nonlocal reads
        data = original(path)
        if path == ROOT / b.ADAPTER_PATH:
            reads += 1
            if reads > 1:
                return data + b"# controlled second-read drift"
        return data

    with monkeypatch.context() as patch:
        patch.setattr(b, "_regular_bytes", drift)
        observed = b.observe_ratio_diagnostic_code()
        assert isinstance(observed, b.ObservationUnavailable)
        assert observed.reason == "B1_OBSERVATION_CHANGED_DURING_READ"
    with monkeypatch.context() as patch:
        patch.setattr(ratio_slice, "__file__", "/unapproved/ratio_slice.py")
        observed = b.observe_ratio_diagnostic_code()
        assert isinstance(observed, b.ObservationUnavailable)
        assert observed.reason == "B1_LOADED_OWNER_ROOT_MISMATCH"


def test_B1_T15_existing_adapter_bytes_only_three_literal_insertions():
    import subprocess

    expected_paths = {
        "src/pit_research_lab/mvp/f2/native_requests.py",
        "src/pit_research_lab/mvp/f2/asof_requests.py",
        "src/pit_research_lab/mvp/f2/derived_observations.py",
    }
    for path in expected_paths:
        current = (ROOT / path).read_bytes()
        approved_baseline = "6a77881afd295ddee0d50f7d7ab5b1e01a4168d5"

        baseline = subprocess.check_output(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(ROOT),
                "show",
                f"{approved_baseline}:{path}",
            ]
        )
        for new in NEW_PATHS:
            literal = ('        "' + new + '",\n').encode()
            assert current.count(literal) == 1
            current = current.replace(literal, b"", 1)
        assert current == baseline
