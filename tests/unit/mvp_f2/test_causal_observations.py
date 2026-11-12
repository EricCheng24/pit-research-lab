"""Frozen independent R1 evidence; genuine public Native positive and controls.

Hostile perturbations below are test inputs, never adopted replacement sources.
No Native test helper or archived executable is imported.
"""

import ast
import base64
import gzip
import inspect
import json
import os
import resource
import subprocess
import time
import zlib
from contextlib import contextmanager
from dataclasses import fields, is_dataclass, replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from pit_research_lab.domain import causal_derivation as n
from pit_research_lab.domain import causal_slice as native
from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import diagnostic_projection as dp
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.derivation import DependencySlot
from pit_research_lab.domain.pit_slice import evaluate_slice
from pit_research_lab.domain.ratio_slice import evaluate_ratio
from pit_research_lab.mvp.f2 import asof_requests as ar
from pit_research_lab.mvp.f2 import causal_observations as b
from pit_research_lab.mvp.f2 import derived_observations as d
from pit_research_lab.mvp.f2 import native_requests as nr
from pit_research_lab.mvp.f2 import ratio_observations as r

ROOT = Path(__file__).parents[3]
BASELINE = "7b722a3e6caf63dcc4f4719a693e5cd6290393e5"
RESULTS = []
PHASE_RESOURCES = []
_PHASE_STACK = []


@contextmanager
def measure(owner, name, label):
    """Instrument actual public calls; always return their original objects."""
    original = getattr(owner, name)

    def measured(*args, **kwargs):
        top = not _PHASE_STACK
        _PHASE_STACK.append(label)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            after = resource.getrusage(resource.RUSAGE_SELF)
            _PHASE_STACK.pop()
            if top:
                PHASE_RESOURCES.append(
                    {
                        "stage": label,
                        "wall_seconds": time.perf_counter() - started,
                        "user_cpu_seconds": after.ru_utime - usage.ru_utime,
                        "system_cpu_seconds": after.ru_stime - usage.ru_stime,
                        "max_rss_kib": after.ru_maxrss,
                        "max_rss_semantics": "PROCESS_CUMULATIVE_HIGH_WATER",
                    }
                )

    with patch.object(owner, name, measured):
        yield


def wire(value):
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            **{
                f.name: wire(getattr(value, f.name))
                for f in fields(value)
                if not f.name.startswith("_")
            },
        }
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, (tuple, list)):
        return [wire(v) for v in value]
    return value


def record(case, value, elapsed=None):
    entry = {
        "case": case,
        "type": type(value).__name__,
        "semantic_sha256": sha256(n.semantic_bytes(value)).hexdigest(),
        "reason": (
            getattr(value, "code", None)
            if isinstance(getattr(value, "code", None), str)
            else getattr(value, "reason", None)
        ),
        "seconds": elapsed,
    }
    if isinstance(value, n.B03Result):
        entry.update(
            realization_ref=value.realization_ref,
            universe_type=type(value.universe).__name__,
            universe_reason=getattr(value.universe, "code", None),
            rows=[
                {
                    "entity": row.entity_id,
                    "sum": wire(row.summed.outcome.value),
                    "features": wire(row.features),
                }
                for row in value.rows
            ],
        )
    RESULTS.append(entry)
    return value


@pytest.fixture(scope="module", autouse=True)
def evidence():
    yield
    if path := os.environ.get("B2_EVIDENCE_DIR"):
        out = Path(path)
        out.mkdir(parents=True, exist_ok=True)
        (out / "b2_typed_summary.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
        (out / "phase_resources.json").write_text(json.dumps(PHASE_RESOURCES, indent=2) + "\n")


@pytest.fixture(scope="module")
def assembly():
    observed = b.observe_causal_diagnostic_code()
    assert isinstance(observed, b.ObservedCausalCode), observed
    with measure(b, "verify_causal_bundle", "SOURCE_VERIFICATION"):
        result = b.prepare_causal_request(observed)
    assert isinstance(result, b.CausalRequestAssembly), result
    return result


@pytest.fixture(scope="module")
def positive(assembly):
    with (
        measure(native, "qualify_universe", "UNIVERSE"),
        measure(native, "evaluate_causal", "B03"),
        measure(dp, "project_candidate", "PROJECTION"),
    ):
        attempt = b.invoke_causal(assembly)
    assert isinstance(attempt, b.NativeCausalAttempt), attempt
    assert attempt.native_invocation == "RUN", attempt.reason
    assert isinstance(attempt.native_result, n.B03Result), attempt.native_result
    assert isinstance(attempt.projection, dp.DiagnosticProjectionCandidate), attempt.projection
    final = b.finalize_causal_diagnostic(attempt)
    assert isinstance(final, b.CausalDiagnostic), final
    record("MD1", attempt.native_result)
    if path := os.environ.get("B2_EVIDENCE_DIR"):
        out = Path(path)
        out.mkdir(parents=True, exist_ok=True)
        with gzip.open(out / "md1_native_result.json.gz", "wt") as f:
            json.dump(wire(attempt.native_result), f, separators=(",", ":"))
        (out / "candidate_bytes.json").write_bytes(attempt.projection.candidate_bytes)
        receipt = {
            "before": wire(final.observations[0]),
            "after": wire(final.observations[1]),
            "verification_seconds": assembly.verification_seconds,
            "native_seconds": dict(attempt.timings),
            "projection_type": type(attempt.projection).__name__,
            "audit_matches_original": attempt.projection.audit.result is attempt.native_result,
        }
        (out / "md1_observations.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return final


def coherent(request, code, **changes):
    """Test-only retained INPUT reference; the public Native planner owns closure."""
    q = replace(request, **changes)
    ref = n.CausalReference(
        q.context,
        q.specifications,
        q.rows,
        q.fit,
        q.universe,
        code,
        q.period_bindings,
        q.allowed_missing,
    )
    q = replace(q, retained=ref)
    return replace(q, plan=n.required_plan(q))


def universe(request, code, members):
    spec = request.universe.specification
    return n.UniverseRequest(
        spec, members, n.UniverseReference(spec, members, code.upstream_ratio.upstream_a04)
    )


def rows_from(assembly, profile="MD1", other="B", unfinished=False):
    views = dict(assembly.inputs.views)
    rows = []
    for index, row in enumerate(assembly.request.rows):
        short = "A" if index == 0 else other
        requests = [views[f"{profile}-{short}-M{i}"] for i in (1, 2, 3)]
        if index == 1 and unfinished:
            requests[2] = views["MD1-B-UNRESOLVED-M3"]
        slots = tuple(DependencySlot("M" + str(i), q.subject, q) for i, q in enumerate(requests, 1))
        rows.append(replace(row, sum_request=replace(row.sum_request, slots=slots)))
    return tuple(rows)


def run_control(case, request, code):
    start = time.perf_counter()
    actual = native.evaluate_causal(request, code)
    record(case, actual, time.perf_counter() - start)
    u = (
        actual.universe
        if isinstance(actual, n.B03Result)
        else native.qualify_universe(
            request.universe, code.upstream_ratio.upstream_a04, request.context
        )
    )
    start = time.perf_counter()
    projected = dp.project_candidate(
        request.context,
        request.specifications,
        actual,
        u,
        dp.ProjectionPolicy(
            tuple(sorted(x.key for x in request.specifications)), request.allowed_missing
        ),
        code,
    )
    record(case + "-projection", projected, time.perf_counter() - start)
    return actual, projected


def test_md1_positive_and_independent_oracle(positive):
    a = positive.attempt
    actual, projected = a.native_result, a.projection
    assert isinstance(actual, n.B03Result)
    assert isinstance(projected, dp.DiagnosticProjectionCandidate)
    assert actual.universe == a.universe
    assert actual.universe.members == ("SYN-A", "SYN-B")
    assert [x.selection.selected_value for x in actual.universe.completed] == [1, 1]
    assert len(actual.source_results) == 8
    assert all(x.selection.state == "SELECTED" for x in actual.source_results)
    assert actual.failures == ()
    for row, amount, share, months in zip(
        actual.rows,
        (150, 100),
        ("0.733333", "0.500000"),
        ((17, 23, 110), (19, 31, 50)),
        strict=True,
    ):
        assert row.summed.outcome.value == amount
        assert row.ratio.outcome.value.decimal_text == share
        assert tuple(x.value for x in row.summed.outcome.lineage) == months
        assert len(row.summed.outcome.lineage) == 3
        for line in row.summed.outcome.lineage:
            assert all(
                len(getattr(line, name)) == 1
                for name in (
                    "assertion_refs",
                    "content_version_refs",
                    "representation_refs",
                    "raw_sha256s",
                )
            )
        assert all(o.state == "VALUE_AVAILABLE" for _, o in row.features)
    candidate = projected.candidate_bytes
    assert len(candidate) == 307
    assert (
        sha256(candidate).hexdigest()
        == "7639f50bf8c36366e0a21ff533d23be8cd50e2d65f71cf076d94c3115a48ee42"
    )
    oracle = json.loads(a.assembly.inputs.oracle_bytes)
    assert candidate == oracle["MD1"]["candidate_bytes"]["utf8"].encode()
    assert projected.audit.result is actual
    payload = json.loads(candidate)
    assert set(payload) == {"candidate_schema_version", "decision_cutoff", "rows"}
    assert payload["decision_cutoff"] == b.MD1_CUTOFF
    assert [x["entity_id"] for x in payload["rows"]] == ["SYN-A", "SYN-B"]
    assert all(set(x["features"]) == set(b.FEATURE_KEYS) for x in payload["rows"])
    for obj in (positive, projected, actual):
        assert obj.diagnostic_only and not obj.admission_eligible
        assert obj.trust == "NOT_TRUSTED_PIT_EVIDENCE"
        assert obj.source_authentication == "NOT_ESTABLISHED"


def test_deterministic_same_issued_inputs_and_real_projector_replay(positive):
    old = positive.attempt
    with (
        measure(native, "qualify_universe", "REPLAY_UNIVERSE"),
        measure(native, "evaluate_causal", "REPLAY_B03"),
        measure(dp, "project_candidate", "REPLAY_PROJECTION"),
    ):
        replay = b.invoke_causal(old.assembly)
    assert isinstance(replay, b.NativeCausalAttempt) and replay.native_invocation == "RUN"
    assert replay.native_result == old.native_result
    assert n.semantic_bytes(replay.native_result) == n.semantic_bytes(old.native_result)
    assert replay.projection == old.projection
    assert isinstance(b.finalize_causal_diagnostic(replay), b.CausalDiagnostic)
    record("MD1-repeat-real-owners", replay.native_result)


def test_request_shape_plan_and_nested_code(assembly):
    request = assembly.request
    assert request.context.information_cutoff.source_text == b.MD1_CUTOFF
    assert request.context.calendar_ref == b.MD1_CALENDAR
    assert request.fit == n.NO_STATE and request.allowed_missing == ()
    assert request.proxy_constant == 1_000_000 and request.window == "LAST_N_REFERENCE_PERIODS_3"
    assert request.specifications == tuple(n.B03FeatureSpec(k) for k in b.FEATURE_KEYS)
    assert request.plan == n.required_plan(request)
    assert len(request.plan.nodes) == 14 and len(request.plan.edges) == 15
    assert sum(x.kind == "SOURCE" for x in request.plan.nodes) == 8
    incoming = {x.ref: [] for x in request.plan.nodes}
    outgoing = {x.ref: [] for x in request.plan.nodes}
    for a, z in request.plan.edges:
        incoming[z].append(a)
        outgoing[a].append(z)

    def depth(ref):
        return max((depth(p) + 1 for p in incoming[ref]), default=0)

    assert max(map(depth, incoming)) == 3
    assert max(map(len, incoming.values())) == 5 and max(map(len, outgoing.values())) == 2
    code = assembly.before_observation.code
    assert len(code.upstream_ratio.upstream_a04.observed_working_files) == 10
    assert len(code.upstream_ratio.extension_pins) == 2 and len(code.extension_pins) == 3
    for q in n.source_requests(request):
        assert (
            q.context.profile.code_pins == code.upstream_ratio.upstream_a04.observed_working_files
        )
    assert request.retained.code is code
    assert request.universe.retained.code is code.upstream_ratio.upstream_a04
    for row in request.rows:
        spec = row.sum_request.specification
        assert spec == d.FeatureSpec(spec.feature_ref, 2026, 4, row.entity_id)
        assert row.ratio_specification.prior_derived_sum_ref == spec.feature_ref


def test_lossless_transport_and_all_source_evidence(assembly):
    inputs = assembly.inputs
    assert (len(inputs.packet_bytes), sha256(inputs.packet_bytes).hexdigest()) == b.PACKET_PIN
    assert (len(inputs.oracle_bytes), sha256(inputs.oracle_bytes).hexdigest()) == b.ORACLE_PIN
    assert (len(inputs.bundle_bytes), sha256(inputs.bundle_bytes).hexdigest()) == b.FIXTURE_PIN
    wrapper = json.loads(inputs.bundle_bytes)
    for name, expected in (("packet", inputs.packet_bytes), ("oracle", inputs.oracle_bytes)):
        assert zlib.decompress(base64.b64decode(wrapper[name]["data"], validate=True)) == expected
    assert len(inputs.sources) == 15 and len(inputs.views) == 20
    old_raw = (ROOT / b.OLD_SOURCE_PATH).read_bytes()
    assert (len(old_raw), sha256(old_raw).hexdigest()) == (d.FIXTURE_LENGTH, d.FIXTURE_SHA256)
    old = json.loads(old_raw)
    packet = json.loads(inputs.packet_bytes)
    for ref, source in zip(packet["source_records"][:7], old["sources"], strict=True):
        assert ref["fixture_path"] == b.OLD_SOURCE_PATH
        assert ref["record_canonical_sha256"] == sha256(b._canonical(source["source"])).hexdigest()
        decoded = b._input(source["source"], {}, {})
        assert decoded == dict(inputs.sources)[ref["tag"]]
    assert sum(len(v["operations"]) for v in packet["views"]) == 60
    assert len({v["page_blob"] for v in packet["views"]}) == 20
    assert (
        sum(len(v["operations"]) for v in packet["views"] if v["view_id"] in b.PRIMARY_VIEWS) == 24
    )


@pytest.mark.parametrize(
    "body", [b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}', b'{"x":Infinity}', b"\xff"]
)
def test_strict_json(body):
    with pytest.raises((ValueError, UnicodeError)):
        b._json(body, 100)


@pytest.mark.parametrize(
    "kind", ["byte", "length", "packet-hash", "oracle-hash", "duplicate", "provenance"]
)
def test_hostile_bundle_fails_before_invocation(assembly, kind):
    original = assembly.inputs.bundle_bytes
    obj = json.loads(original)
    if kind == "byte":
        raw = original[:-2] + b"x\n"
    elif kind == "length":
        raw = original + b" "
    elif kind == "duplicate":
        raw = b'{"schema":"x",' + original[1:]
    else:
        if kind.endswith("hash"):
            obj[kind.split("-")[0]]["sha256"] = "0" * 64
        else:
            obj["provenance"]["old_source_fixture"]["path"] = "/foreign/source"
        raw = b._canonical(obj)
    result = b.prepare_causal_request(assembly.before_observation, raw)
    assert isinstance(result, b.Refusal) and result.native_invocation == "NOT_RUN"
    assert result.reason == "B2_BUNDLE_NOT_ADOPTED"


@pytest.mark.parametrize(
    "name",
    [
        "AsOfSelectionResult",
        "SelectionOutcome",
        "DerivedResult",
        "RatioResult",
        "QualifiedSyntheticUniverse",
        "B03Result",
        "RowResult",
        "DiagnosticProjectionCandidate",
    ],
)
def test_completed_input_types_refused(name):
    with pytest.raises(c.ContractError, match="B2_INPUT_TYPE_REFUSED"):
        b._input({"type": name}, {}, {})


@pytest.mark.parametrize(
    "kind",
    [
        "old-origin",
        "source-inventory",
        "page",
        "operation",
        "weekly-discovery",
        "clock",
        "code-profile",
    ],
)
def test_hostile_facts_cannot_reconcile(assembly, kind):
    packet = json.loads(assembly.inputs.packet_bytes)
    old = json.loads((ROOT / b.OLD_SOURCE_PATH).read_bytes())
    view = packet["views"][0]
    if kind == "old-origin":
        old["sources"][0]["source"]["request"]["content"]["origin"]["envelope_pointer"] = "/foreign"
    elif kind == "source-inventory":
        view["source_inventory"] = ["B-O"]
    elif kind == "page":
        blob = packet["blobs"][view["page_blob"]]
        blob["utf8"] = blob["utf8"].replace('"terminal":true', '"terminal":false')
        blob["byte_length"] = len(blob["utf8"].encode())
        blob["sha256"] = sha256(blob["utf8"].encode()).hexdigest()
    elif kind == "operation":
        view["operations"].pop()
    elif kind == "weekly-discovery":
        view["request"]["discovery"] = packet["views"][8]["request"]["discovery"]
    elif kind == "clock":
        view["request"]["context"]["information_cutoff"]["timezone_name"] = "UTC"
    else:
        view["request"]["context"]["profile"]["code_pins"].pop()
    with pytest.raises((c.ContractError, ValueError)):
        b._verify_facts(packet, old)


def test_weekly_coherent_native_refusal_and_temporal_non_substitutability(assembly):
    code = assembly.before_observation.code
    rows = rows_from(assembly, "W18")
    views = dict(assembly.inputs.views)
    u = universe(assembly.request, code, (views["W18-MEM-A"], views["W18-MEM-B"]))
    request = coherent(
        assembly.request,
        code,
        rows=rows,
        universe=u,
        context=rows[0].sum_request.slots[0].request.context,
    )
    result, projection = run_control("Weekly18", request, code)
    assert isinstance(result, c.BlockingFailure) and result.code == "INVALID_DECISION_CUTOFF"
    assert isinstance(projection, dp.ProjectionBlocked) and projection.code == result.code
    ratio = evaluate_ratio(
        rows[0].ratio_specification,
        rows[0].sum_request.specification,
        rows[0].sum_request.slots,
        code.upstream_ratio,
    )
    assert (
        ratio.upstream_a04.outcome.value == 140 and ratio.outcome.value.decimal_text == "0.714286"
    )
    record("Weekly18-actual-A05-only", ratio)
    assert request.context.calendar_ref == "SYN-CAL-v1"
    assert request.context.information_cutoff.source_text == "2027-01-07T18:00:00+08:00"


@pytest.mark.parametrize(
    "case",
    [
        "missing-member",
        "wrong-publisher",
        "wrong-source",
        "wrong-basis",
        "wrong-issuer",
        "wrong-subject",
    ],
)
def test_universe_controls_actual_owner(assembly, case):
    request, code = assembly.request, assembly.before_observation.code
    members = request.universe.requests
    if case == "missing-member":
        members = members[:1]
    elif case in {"wrong-publisher", "wrong-source"}:
        policy = replace(
            members[0].policy,
            **(
                {"issuer_ref": "FOREIGN"}
                if case == "wrong-publisher"
                else {"source_refs": ("FOREIGN",)}
            ),
        )
        members = (replace(members[0], policy=policy), members[1])
    else:
        key = {
            "wrong-basis": "basis_ref",
            "wrong-issuer": "economic_entity_ref",
            "wrong-subject": "metric",
        }[case]
        subject = replace(
            members[0].subject, **{key: c.Known("FOREIGN", members[0].subject.origin)}
        )
        members = (replace(members[0], subject=subject), members[1])
    request = coherent(request, code, universe=universe(request, code, members))
    if case != "missing-member":
        result = record(
            case,
            native.qualify_universe(
                request.universe, code.upstream_ratio.upstream_a04, request.context
            ),
        )
        expected = (
            "INVALID_UNIVERSE_PUBLISHER"
            if case in {"wrong-publisher", "wrong-source"}
            else "INVALID_MEMBERSHIP_SUBJECT"
        )
        assert isinstance(result, c.BlockingFailure) and result.code == expected
        return
    result, projection = run_control(case, request, code)
    assert isinstance(result, n.B03Result)
    if case == "missing-member":
        assert (
            isinstance(result.universe, n.B03Refusal)
            and result.universe.code == "UNQUALIFIED_UNIVERSE"
        )
        assert (
            isinstance(projection, dp.ProjectionWithheld)
            and projection.code == "UNQUALIFIED_UNIVERSE"
        )


@pytest.mark.parametrize("case", ["unresolved", "zero"])
def test_independently_frozen_domain_controls(assembly, case):
    code = assembly.before_observation.code
    rows = rows_from(
        assembly, other="Z" if case == "zero" else "B", unfinished=case == "unresolved"
    )
    request = coherent(assembly.request, code, rows=rows)
    result, projection = run_control(case, request, code)
    assert isinstance(result, n.B03Result)
    row = result.rows[1]
    assert isinstance(projection, dp.ProjectionWithheld)
    if case == "zero":
        assert row.summed.outcome.value == 0
        assert all(x.actual.selection.state == "SELECTED" for x in row.summed.dependencies)
        assert row.ratio.outcome.state == "NOT_COMPUTABLE"
        assert row.ratio.outcome.reason == "ZERO_QUARTER_REVENUE_DENOMINATOR"
        assert projection.code == "MISSING_NOT_PERMITTED"
    else:
        assert row.summed.outcome.state == "UNRESOLVED"
        assert row.summed.outcome.reason == "DEPENDENCY_UNRESOLVED"
        assert projection.code == "REQUIRED_FEATURE_UNRESOLVED"


@pytest.mark.parametrize("case", ["plan", "period", "retained", "code", "feature", "cohort"])
def test_native_contract_priority(assembly, case):
    request, code = assembly.request, assembly.before_observation.code
    if case == "plan":
        request = replace(request, plan=replace(request.plan, edges=request.plan.edges[1:]))
        expected = "INCOMPLETE_REQUIRED_CLOSURE"
    elif case == "period":
        request = coherent(request, code, period_bindings=(("SYN-A", 2026, 3), ("SYN-B", 2026, 4)))
        expected = "PERIOD_OR_ENTITY_MISMATCH"
    elif case == "retained":
        request = replace(
            request, retained=replace(request.retained, allowed_missing=b.FEATURE_KEYS)
        )
        expected = "B03_RETAINED_REFERENCE_MISMATCH"
    elif case == "code":
        code = replace(
            code, extension_pins=tuple(replace(p, sha256="0" * 64) for p in code.extension_pins)
        )
        expected = "B03_CODE_REFERENCE_MISMATCH"
    elif case == "feature":
        request = coherent(
            request, code, specifications=(n.B03FeatureSpec("third_month_share", "bad"),)
        )
        expected = "INVALID_FEATURE_SPEC"
    else:
        rows = list(request.rows)
        slots = list(rows[1].sum_request.slots)
        q = slots[0].request
        slots[0] = replace(
            slots[0], request=replace(q, context=replace(q.context, evidence_set_ref="FOREIGN"))
        )
        rows[1] = replace(rows[1], sum_request=replace(rows[1].sum_request, slots=tuple(slots)))
        request = coherent(request, code, rows=tuple(rows))
        expected = "MIXED_RECONSTRUCTION_CONTEXT"
    result, projection = run_control(case, request, code)
    assert isinstance(result, c.BlockingFailure) and result.code == expected
    assert isinstance(projection, dp.ProjectionBlocked) and projection.code == expected


@pytest.mark.parametrize("case", ["policy", "context", "features", "universe", "code"])
def test_projection_drift(positive, case):
    attempt = positive.attempt
    q = attempt.assembly.request
    args = [
        q.context,
        q.specifications,
        attempt.native_result,
        attempt.universe,
        attempt.assembly.policy,
        attempt.assembly.before_observation.code,
    ]
    if case == "policy":
        args[4] = replace(args[4], missing_keys=b.FEATURE_KEYS)
    elif case == "context":
        args[0] = replace(args[0], calendar_ref="FOREIGN")
    elif case == "features":
        args[1] = args[1][:1]
    elif case == "universe":
        args[3] = native.qualify_universe(
            universe(q, args[5], q.universe.requests[:1]),
            args[5].upstream_ratio.upstream_a04,
            q.context,
        )
    else:
        args[5] = replace(args[5], profile_ref="FOREIGN")
    projected = record("projection-drift-" + case, dp.project_candidate(*args))
    assert isinstance(projected, dp.ProjectionBlocked)
    assert projected.code == "PROJECTION_CONTEXT_OR_POLICY_MISMATCH"


@pytest.mark.parametrize("tag,view", [("D2", "W18-A-M3"), ("D3", "MD1-A-M3")])
def test_equal_and_future_publication_native_s2(assembly, tag, view):
    q = dict(assembly.inputs.views)[view]
    source = dict(assembly.inputs.sources)[tag]
    actual = evaluate_slice(
        q.context, source.request, assembly.before_observation.code.upstream_ratio.upstream_a04
    )
    assert actual.s2.state == "NOT_ADMISSIBLE" and actual.s2.reason == "PUBLICATION_NOT_PRE_CUTOFF"
    record(tag + "-at-" + view, actual)


def test_native_source_limits_and_identity_collision(assembly):
    q = assembly.request.rows[0].sum_request.slots[0].request
    with pytest.raises(c.ContractError, match="S3_REQUEST_LIMIT"):
        n.check_sources((q,) * 41)
    source = q.candidates[0]
    raw = b"x" * 65_537
    big = replace(
        source.request.content,
        raw_bytes=raw,
        raw_length=len(raw),
        raw_sha256=sha256(raw).hexdigest(),
    )
    with pytest.raises(c.ContractError, match="RAW_BODY_LIMIT"):
        n.check_sources(
            (
                replace(
                    q, candidates=(replace(source, request=replace(source.request, content=big)),)
                ),
            )
        )
    changed_assertion = replace(
        source.request.assertion, source_amount=c.Known(999, source.request.assertion.origin)
    )
    changed = replace(source, request=replace(source.request, assertion=changed_assertion))
    with pytest.raises(c.ContractError, match="CONTRADICTORY_IMMUTABLE_IDENTITY"):
        n.check_sources((replace(q, candidates=(source, changed)),))


def test_real_candidate_reordering_and_audit_noninterference(positive):
    attempt = positive.attempt
    request, code = attempt.assembly.request, attempt.assembly.before_observation.code
    rows = list(request.rows)
    slots = list(rows[0].sum_request.slots)
    q = slots[2].request
    discovery = replace(q.discovery, candidates=tuple(reversed(q.discovery.candidates)))
    assert s.discovery_proposition(discovery) == discovery.raw_bytes
    slots[2] = replace(
        slots[2], request=replace(q, candidates=tuple(reversed(q.candidates)), discovery=discovery)
    )
    rows[0] = replace(rows[0], sum_request=replace(rows[0].sum_request, slots=tuple(slots)))
    actual, projected = run_control(
        "candidate-order", coherent(request, code, rows=tuple(rows)), code
    )
    assert isinstance(actual, n.B03Result)
    assert actual.realization_ref == attempt.native_result.realization_ref
    assert projected.candidate_bytes == attempt.projection.candidate_bytes
    audited = replace(attempt.native_result, research_only_audit=("audit-only future note",))
    projected = dp.project_candidate(
        request.context,
        request.specifications,
        audited,
        attempt.universe,
        attempt.assembly.policy,
        code,
    )
    assert isinstance(projected, dp.DiagnosticProjectionCandidate)
    assert projected.candidate_bytes == attempt.projection.candidate_bytes
    record("audit-only-replayed", projected)


def test_unissued_or_changed_observation_assembly_attempt_refused(assembly, positive):
    copied = replace(assembly.before_observation)
    assert copied == assembly.before_observation
    assert isinstance(b.prepare_causal_request(copied), b.Refusal)
    assert isinstance(b.prepare_causal_request(assembly.before_observation.code), b.Refusal)
    copied_assembly = replace(assembly)
    object.__setattr__(copied_assembly, "_ticket", assembly._ticket)
    result = b.invoke_causal(copied_assembly)
    assert isinstance(result, b.Refusal) and result.native_invocation == "NOT_RUN"
    copied_attempt = replace(positive.attempt)
    object.__setattr__(copied_attempt, "_ticket", positive.attempt._ticket)
    assert isinstance(b.finalize_causal_diagnostic(copied_attempt), b.Refusal)
    assert isinstance(b.finalize_causal_diagnostic(positive), b.Refusal)
    fresh = b.prepare_causal_request(assembly.before_observation)
    object.__setattr__(fresh, "request", replace(fresh.request, window="FOREIGN"))
    assert isinstance(b.invoke_causal(fresh), b.Refusal)


def test_native_exception_is_attempted_and_preserved(assembly, monkeypatch):
    def broken(*args):
        raise RuntimeError("exact synthetic exception")

    monkeypatch.setattr(native, "qualify_universe", broken)
    attempt = b.invoke_causal(assembly)
    assert isinstance(attempt, b.NativeCausalAttempt)
    assert attempt.native_invocation == "ATTEMPTED" and attempt.stage == "UNIVERSE"
    assert (
        attempt.exact_exception_type == "RuntimeError"
        and attempt.reason == "exact synthetic exception"
    )
    assert attempt.native_result is None and attempt.universe is None
    clean_failure = b.finalize_causal_diagnostic(attempt)
    assert isinstance(clean_failure, b.InvocationFailure)
    assert clean_failure.native_invocation == "ATTEMPTED" and clean_failure.preserved is attempt
    monkeypatch.setattr(
        b, "observe_causal_diagnostic_code", lambda: b.ObservationUnavailable("after-failed")
    )
    result = b.finalize_causal_diagnostic(attempt)
    assert isinstance(result, b.ObservationFailure) and result.native_invocation == "ATTEMPTED"
    assert result.preserved is attempt


@pytest.mark.parametrize(
    "kind", ["native", "source", "adapter", "status", "head", "tree", "symlink", "foreign-origin"]
)
def test_after_observation_drift_preserves_run(positive, monkeypatch, kind):
    original = b._regular_bytes
    original_git = b._git
    if kind in {"native", "source", "adapter", "symlink"}:
        target = {
            "native": b.NATIVE_PINS[-1][0],
            "source": b.FIXTURE_PATH,
            "adapter": r.ADAPTER_PATH,
            "symlink": b.ADAPTER_PATH,
        }[kind]

        def drift(path):
            if path == ROOT / target:
                if kind == "symlink":
                    raise c.ContractError("B2_SYMLINK_REFUSED")
                return original(path) + b" "
            return original(path)

        monkeypatch.setattr(b, "_regular_bytes", drift)
    elif kind in {"head", "tree", "status"}:

        def git(root, *args):
            if kind == "status" and args[0] == "status":
                return "?? unauthorized.py\n"
            if args == ("rev-parse", "HEAD" if kind == "head" else "HEAD^{tree}"):
                return "0" * 40 + "\n"
            return original_git(root, *args)

        monkeypatch.setattr(b, "_git", git)
    else:
        monkeypatch.setattr(dp, "__file__", "/foreign/diagnostic_projection.py")
    result = b.finalize_causal_diagnostic(positive.attempt)
    assert isinstance(result, b.ObservationFailure)
    assert result.native_invocation == "RUN" and result.preserved is positive.attempt
    assert result.preserved.native_result is positive.attempt.native_result


def test_actual_symlink_hardlink_and_nonregular_refusal(tmp_path):
    original = tmp_path / "source"
    original.write_bytes(b"input")
    link = tmp_path / "symlink"
    link.symlink_to(original)
    with pytest.raises(c.ContractError, match="B2_SYMLINK_REFUSED"):
        b._regular_bytes(link)
    hard = tmp_path / "hardlink"
    os.link(original, hard)
    with pytest.raises(c.ContractError, match="B2_NONREGULAR_OR_LINKED"):
        b._regular_bytes(original)
    with pytest.raises(c.ContractError, match="B2_NONREGULAR_OR_LINKED"):
        b._regular_bytes(tmp_path)


def test_observation_concurrent_read_and_stale_before(assembly, monkeypatch):
    original = b._regular_bytes
    counts = {}

    def changed(path):
        counts[path] = counts.get(path, 0) + 1
        raw = original(path)
        return raw + b" " if path == ROOT / b.ADAPTER_PATH and counts[path] > 1 else raw

    monkeypatch.setattr(b, "_regular_bytes", changed)
    observed = b.observe_causal_diagnostic_code()
    assert (
        isinstance(observed, b.ObservationUnavailable)
        and observed.reason == "B2_OBSERVATION_CHANGED_DURING_READ"
    )
    assert isinstance(b.invoke_causal(assembly), b.Refusal)


@pytest.mark.parametrize(
    "raw",
    [
        "A  {p}\n",
        "M  {p}\n",
        " M {p}",
        "?? foreign.py\n",
        " R {p}\n",
        "?? {p}\n?? {p}\n",
        " M {p}\r\n",
        " M {p}\n?? {p}\n",
    ],
)
def test_status_hostility(raw):
    assert not b._status_valid(raw.format(p=b.ADAPTER_PATH))


def test_existing_status_semantics_and_unstaged_observers():
    for path in b.NEW_PATHS:
        assert path in ar._STATUS_PATHS and path in d.STATUS_PATHS and path in r.STATUS_PATHS
        assert b._status_valid("?? " + path + "\n")
        assert b._status_valid(" M " + path + "\n")
        assert not ar._status_valid("A  " + path)
        assert not d._status_valid("A  " + path)
        assert not r._status_valid("A  " + path)
    assert isinstance(b.observe_causal_diagnostic_code(), b.ObservedCausalCode)
    assert isinstance(r.observe_ratio_diagnostic_code(), r.ObservedRatioCode)
    assert isinstance(d.observe_wu03_code(), d.WU03ObservedCodeInput)
    assert isinstance(ar.observe_g03_code(), ar.G03ObservedCodeInput)
    assert len(nr.NATIVE_CODE_PINS) == 6


def test_b2_four_owner_exact_byte_guard_fixed_b1_baseline():
    for path in b.LOCAL_PATHS[1:5]:
        current = (ROOT / path).read_bytes()
        baseline = subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(ROOT), "show", f"{BASELINE}:{path}"]
        )
        block = next(
            node
            for node in ast.walk(ast.parse(current))
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id in {"permitted", "_STATUS_PATHS", "STATUS_PATHS"}
                for t in node.targets
            )
        )
        block_bytes = b"\n".join(current.split(b"\n")[block.lineno - 1 : block.end_lineno])
        for path in b.NEW_PATHS:
            literal = ('        "' + path + '",\n').encode()
            assert current.count(literal) == 1
            assert block_bytes.count(literal.rstrip(b"\n")) == 1
            current = current.replace(literal, b"", 1)
        assert current == baseline


def test_only_t15_hunk_in_existing_test_and_post_commit_durability():
    path = "tests/unit/mvp_f2/test_ratio_observations.py"
    current = (ROOT / path).read_bytes()
    baseline = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(ROOT), "show", f"{BASELINE}:{path}"]
    )
    marker = b"def test_B1_T15_existing_adapter_bytes_only_three_literal_insertions():"
    assert current.split(marker)[0] == baseline.split(marker)[0]
    assert len(current.split(marker)) == len(baseline.split(marker)) == 2
    tree = ast.parse(current)
    assert tree.body[-1].name == marker.decode().split("(")[0].removeprefix("def ")
    t15 = current.split(marker)[1]
    assert b"6a77881afd295ddee0d50f7d7ab5b1e01a4168d5" in t15
    assert b"HEAD" not in t15
    assert "HEAD" not in inspect.getsource(test_b2_four_owner_exact_byte_guard_fixed_b1_baseline)
    # Exercise the actual guard with HEAD lookups prohibited; clean post-commit
    # execution uses precisely the same fixed objects, never a moving baseline.
    original = subprocess.check_output

    def fixed_only(args, **kwargs):
        assert not any(str(arg).startswith("HEAD:") for arg in args)
        return original(args, **kwargs)

    with patch.object(subprocess, "check_output", fixed_only):
        test_b2_four_owner_exact_byte_guard_fixed_b1_baseline()


def test_source_absence_is_explicitly_not_constructible(assembly):
    oracle = json.loads(assembly.inputs.oracle_bytes)
    assert oracle["source_absence"] == "NOT_CONSTRUCTIBLE_NO_AUTHORED_ABSENCE"
    RESULTS.append(
        {"case": "NO_QUALIFIED_CLAIM", "state": "NOT_CONSTRUCTIBLE", "native_invocation": "NOT_RUN"}
    )


@pytest.mark.parametrize("field", ["request", "packet_bytes", "oracle_bytes"])
def test_after_assembly_mutation_retains_real_run(positive, field):
    attempt = positive.attempt
    owner = attempt.assembly if field == "request" else attempt.assembly.inputs
    original = getattr(owner, field)
    altered = replace(original, window="FOREIGN") if field == "request" else original + b" "
    try:
        object.__setattr__(owner, field, altered)
        failed = b.finalize_causal_diagnostic(attempt)
        assert isinstance(failed, b.ObservationFailure)
        assert failed.reason == "B2_ATTEMPT_OR_INPUT_CHANGED"
        assert failed.native_invocation == "RUN"
        assert failed.preserved.native_result is attempt.native_result
    finally:
        object.__setattr__(owner, field, original)


def test_native_observation_boolean_length_is_not_disk_provenance(monkeypatch):
    original = native.observe_causal_code

    def forged(root):
        code = original(root)
        ratio = code.upstream_ratio
        base = ratio.upstream_a04
        lengths = list(base.byte_lengths)
        lengths[1] = False
        return replace(
            code,
            upstream_ratio=replace(ratio, upstream_a04=replace(base, byte_lengths=tuple(lengths))),
        )

    monkeypatch.setattr(native, "observe_causal_code", forged)
    observed = b.observe_causal_diagnostic_code()
    assert isinstance(observed, b.ObservationUnavailable)
    assert observed.reason == "B2_NATIVE_OBSERVATION_MISMATCH"
