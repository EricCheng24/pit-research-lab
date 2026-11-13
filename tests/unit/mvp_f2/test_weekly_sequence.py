"""Real WU04 issuance, isolated read data and immutable historical guard proofs."""

import ast
import json
import os
import resource
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from dataclasses import fields, is_dataclass, replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import ratio, ratio_slice
from pit_research_lab.domain.pit_slice import evaluate_slice, observe_code
from pit_research_lab.mvp.f2 import asof_requests as ar
from pit_research_lab.mvp.f2 import causal_observations as b
from pit_research_lab.mvp.f2 import derived_observations as d
from pit_research_lab.mvp.f2 import native_requests as nr
from pit_research_lab.mvp.f2 import ratio_observations as r
from pit_research_lab.mvp.f2 import weekly_sequence as w

ROOT = Path(__file__).absolute().parents[3]
BASE = "13e9db2bea4f17f4cc9d064be1c3a3e642ccd045"
NEW = (w.MODULE_PATH, w.TEST_PATH)
OLD = (
    "src/pit_research_lab/mvp/f2/native_requests.py",
    "src/pit_research_lab/mvp/f2/asof_requests.py",
    "src/pit_research_lab/mvp/f2/derived_observations.py",
    "src/pit_research_lab/mvp/f2/ratio_observations.py",
    "src/pit_research_lab/mvp/f2/causal_observations.py",
)
VECTORS = (
    ("2027-01-07", 100, 140, "0.714286", "D1"),
    ("2027-01-15", 110, 150, "0.733333", "D2"),
    ("2027-01-29", 110, 150, "0.733333", "D2"),
    ("2027-02-05", 90, 130, "0.692308", "D3"),
)
CASES, RESOURCES, RUNS, CONTROLS = [], [], [], []


def record(case, status, evidence, detail):
    CASES.append(dict(case=case, status=status, evidence=evidence, detail=detail))


def wire(value):
    if is_dataclass(value):
        return {
            f.name: wire(getattr(value, f.name))
            for f in fields(value)
            if not f.name.startswith("_")
        }
    if isinstance(value, tuple):
        return [wire(x) for x in value]
    if isinstance(value, bytes):
        return {"sha256": sha256(value).hexdigest(), "byte_length": len(value)}
    return value


@contextmanager
def count_a05():
    calls = []
    monitor = sys.monitoring
    tool = next(i for i in range(5, -1, -1) if monitor.get_tool(i) is None)
    monitor.use_tool_id(tool, "WU04_PUBLIC_NATIVE_ENTRY_COUNT")
    code = ratio_slice.evaluate_ratio.__code__
    monitor.register_callback(
        tool, monitor.events.PY_START, lambda entered, _offset: calls.append(entered.co_name)
    )
    monitor.set_local_events(tool, code, monitor.events.PY_START)
    try:
        yield calls
    finally:
        monitor.set_local_events(tool, code, 0)
        monitor.register_callback(tool, monitor.events.PY_START, None)
        monitor.free_tool_id(tool)


@contextmanager
def measure(owner, name, label):
    original = getattr(owner, name)

    def measured(*args, **kwargs):
        started = time.perf_counter()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        try:
            return original(*args, **kwargs)
        finally:
            after = resource.getrusage(resource.RUSAGE_SELF)
            RESOURCES.append(
                dict(
                    phase=label,
                    wall_seconds=time.perf_counter() - started,
                    user_cpu_seconds=after.ru_utime - usage.ru_utime,
                    system_cpu_seconds=after.ru_stime - usage.ru_stime,
                    max_rss_kib=after.ru_maxrss,
                    rss_scope="PROCESS_CUMULATIVE_HIGH_WATER",
                )
            )

    with patch.object(owner, name, measured):
        yield


def summarize(audit):
    if isinstance(audit, w._Refusal):
        return {"refusal": wire(audit)}
    rows = []
    for entry in audit.entries:
        item = dict(
            index=entry.index,
            tick_bytes=entry.tick_bytes.decode(),
            native_invocation=entry.native_invocation,
            outcome_type=type(entry.outcome).__name__,
            outer_reason=entry.outer_reason,
            observations=[wire(x) for x in (entry.before, entry.preinvoke, entry.after)],
            timings=entry.timings,
        )
        if isinstance(entry.attempt, r.NativeRatioAttempt):
            result = entry.attempt.native_result
            up = result.upstream_a04
            item.update(
                ratio_outcome=wire(result.outcome),
                ratio_realization=result.realization_ref,
                source_identity=entry.assembly.upstream.source_identity,
            )
            item["A04"] = dict(
                outcome=wire(up.outcome),
                realization=up.realization_ref,
                dependencies=[
                    dict(
                        slot=x.slot.slot_ref,
                        subject=x.slot.expected_subject.subject_ref,
                        reconstruction=x.actual.reconstruction_ref,
                        selection=wire(x.actual.selection),
                        sources=[
                            dict(
                                ref=y.ref,
                                s1=wire(y.actual.s1.state),
                                s2=wire(y.actual.s2.state),
                                reason=y.actual.s2.reason,
                            )
                            for y in x.actual.inputs.candidates
                        ],
                    )
                    for x in up.dependencies
                ],
            )
        elif isinstance(entry.attempt, r.InvocationFailure):
            item.update(
                exception_type=entry.attempt.exact_native_exception_type, code=entry.attempt.code
            )
        rows.append(item)
    return dict(
        initial=wire(audit.initial),
        final=wire(audit.final),
        annotations=wire(audit.annotations),
        entries=rows,
        timings=audit.timings,
        read=wire(audit.read),
    )


def execute(label, ticks=None):
    observed = []
    original = w._execute

    def capture(exact):
        result = original(exact)
        observed.append(result)
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(w, "_execute", capture))
        for owner, name in [
            (w, "build_pack"),
            (w, "build_weekly_requests"),
            (r, "prepare_ratio_request"),
            (r, "invoke_ratio"),
            (r, "finalize_ratio_diagnostic"),
            (w, "_features"),
        ]:
            stack.enter_context(measure(owner, name, label + ":" + name))
        with count_a05() as calls:
            read = w.run_weekly_sequence(ticks)
    assert len(observed) == 1
    RUNS.append(
        dict(
            label=label,
            public_A05_calls=len(calls),
            audit=summarize(observed[0]),
            read_utf8=read.decode() if type(read) is bytes else None,
        )
    )
    return read, observed[0], len(calls)


@pytest.fixture(scope="module", autouse=True)
def evidence():
    yield
    if dest := os.environ.get("WU04_EVIDENCE_DIR"):
        out = Path(dest)
        assert (
            out.is_absolute()
            and str(out).startswith("/tmp/mvp-f2-wu04-impl01-")
            and not out.is_relative_to(ROOT)
        )
        out.mkdir(parents=True, exist_ok=True)
        for name, value in [
            ("case_dispositions", CASES),
            ("phase_resources", RESOURCES),
            ("issued_runs", RUNS),
            ("native_controls", CONTROLS),
        ]:
            (out / (name + ".json")).write_text(json.dumps(value, indent=2, default=str) + "\n")


@pytest.fixture(scope="module")
def positive():
    read, audit, count = execute("positive")
    assert count == 4 and type(read) is bytes and isinstance(audit, w._SequenceAudit)
    return read, audit


def oracle():
    # Independent small expected read oracle, never an input or Native substitute.
    rows = []
    for i, (day, _month, total, fraction, _tag) in enumerate(VECTORS):
        rows.append(
            dict(
                tick_id="SYN-TICK-" + day,
                tick_order=i,
                decision_cutoff=day + "T18:00:00+08:00",
                timezone_name="Asia/Taipei",
                precision="SECOND",
                issuer_ref="SYN-A",
                features={
                    "derived_quarter_revenue": dict(
                        state="VALUE_AVAILABLE", reason="NONE", value=total, unit="NTD_thousands"
                    ),
                    "third_month_share": dict(
                        state="VALUE_AVAILABLE",
                        reason="NONE",
                        value=fraction,
                        unit="FRACTION",
                        scale=6,
                    ),
                },
            )
        )
    return dict(
        schema_version="wu04-weekly-diagnostic-read-v0.1",
        diagnostic_only=True,
        admission_eligible=False,
        trust="NOT_TRUSTED_PIT_EVIDENCE",
        source_authentication="NOT_ESTABLISHED",
        disposition="INTEGRATED_PROVISIONAL",
        ticks=rows,
    )


def strict(body):
    def pairs(items):
        found = {}
        for key, value in items:
            assert key not in found
            found[key] = value
        return found

    def nonexact(_raw):
        raise ValueError("NONEXACT")

    return json.loads(body, object_pairs_hook=pairs, parse_float=nonexact, parse_constant=nonexact)


def assert_tree(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual) == set(expected)
        for k in expected:
            assert_tree(actual[k], expected[k])
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for a, e in zip(actual, expected, strict=True):
            assert_tree(a, e)
    else:
        assert actual == expected


def test_T01_real_four_ticks(positive):
    read, audit = positive
    assert_tree(strict(read), oracle())
    assert tuple(sha256(e.tick_bytes).hexdigest() for e in audit.entries) == w.TICK_SHA256S
    assert all(len(e.tick_bytes) == 672 and e.native_invocation == "RUN" for e in audit.entries)
    assert audit.annotations == (w.WeekAnnotation("2027-W03"),)
    for entry in audit.entries:
        assert type(entry.outcome) is r.RatioDiagnostic
        assert entry.outcome.native_result is entry.attempt.native_result
        assert entry.before == entry.preinvoke == entry.after == audit.initial == audit.final
        assert entry.after is not entry.before
    record(
        "T01",
        "PASS",
        "OBSERVED_PUBLIC_EXECUTION",
        "Four independent public A05 issuances; actual public WU01 regeneration",
    )


def test_T02_original_lineage(positive):
    for entry, (_day, month, total, text, tag) in zip(positive[1].entries, VECTORS, strict=True):
        result = entry.outcome.native_result
        up = result.upstream_a04
        assert up.outcome.value == total and result.outcome.value.decimal_text == text
        assert [x.value for x in up.outcome.lineage] == [17, 23, month]
        for dep, line, source in zip(
            up.dependencies, up.outcome.lineage, ("O", "N", tag), strict=True
        ):
            assert dep.actual.selection.state == "SELECTED"
            assert line.assertion_refs == ("PREP01-A-" + source,)
            assert line.content_version_refs == ("PREP01-CV-" + source,)
            assert line.representation_refs == ("PREP01-REP-" + source,)
            candidate = next(
                c for c in dep.actual.inputs.candidates if c.ref == line.assertion_refs[0]
            )
            assert line.raw_sha256s == (candidate.actual.request.content.raw_sha256,)
            assert candidate.actual.s1.state == "BOUND" and candidate.actual.s2.state == "SUPPORTED"
        assert not result.admission_eligible and result.source_authentication == "NOT_ESTABLISHED"
    last = (
        positive[1].entries[3].outcome.native_result.upstream_a04.dependencies[2].actual.selection
    )
    assert last.derived_reachability[0].direct_relation_path == ("PREP01-N12", "PREP01-N23")
    record(
        "T02",
        "PASS",
        "OBSERVED_PUBLIC_EXECUTION",
        "Original monthly subjects, selected sources and N12/N23 reachability retained",
    )


def test_T03_equal_values_distinct_realizations(positive):
    left, right = (positive[1].entries[i] for i in (1, 2))
    a, b1 = left.outcome.native_result, right.outcome.native_result
    assert a.outcome.value == b1.outcome.value and a.realization_ref != b1.realization_ref
    assert a.upstream_a04.outcome.lineage == b1.upstream_a04.outcome.lineage
    assert a.upstream_a04.realization_ref != b1.upstream_a04.realization_ref
    assert (
        a.upstream_a04.dependencies[2].actual.reconstruction_ref
        != b1.upstream_a04.dependencies[2].actual.reconstruction_ref
    )
    assert left.tick_bytes != right.tick_bytes
    record(
        "T03",
        "PASS",
        "OBSERVED_PUBLIC_EXECUTION",
        "Same selected raw version; distinct tick/reconstruction/realization",
    )


def test_T04_exact_publication_boundary(positive):
    entries = positive[1].entries
    later = entries[3].assembly.upstream.slots[2].request
    for tick, ref in [(0, "PREP01-A-D2"), (2, "PREP01-A-D3")]:
        assembly = entries[tick].assembly.upstream
        src = next(c for c in later.candidates if c.request.assertion.assertion_ref == ref)
        result = evaluate_slice(
            assembly.slots[2].request.context, src.request, assembly.before_observation.code
        )
        assert (result.s2.state, result.s2.reason) == (
            "NOT_ADMISSIBLE",
            "PUBLICATION_NOT_PRE_CUTOFF",
        )
        CONTROLS.append(
            dict(case="T04", source=ref, state=result.s2.state, reason=result.s2.reason)
        )
    record(
        "T04", "PASS", "OBSERVED_PUBLIC_NATIVE_CONTROL", "Original D2 equality and D3 +1s excluded"
    )


@pytest.fixture(scope="module")
def missing(positive):
    assembly = positive[1].entries[0].assembly
    slots = assembly.upstream.slots
    req = replace(slots[0].request, discovery=c.NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT"))
    with count_a05() as calls:
        result = ratio_slice.evaluate_ratio(
            assembly.specification,
            assembly.upstream.specification,
            (replace(slots[0], request=req), *slots[1:]),
            assembly.before_observation.code,
        )
    assert calls == ["evaluate_ratio"]
    CONTROLS.append(
        dict(
            case="T05", public_A05_calls=1, state=result.outcome.state, reason=result.outcome.reason
        )
    )
    return result


def test_T05_missing_is_not_absence(missing):
    assert (missing.outcome.state, missing.outcome.reason) == (
        "UNRESOLVED",
        "DEPENDENCY_UNRESOLVED",
    )
    assert isinstance(missing.outcome.value, c.NotEvaluated)
    record(
        "T05",
        "PASS",
        "OBSERVED_PUBLIC_NATIVE_CONTROL",
        "Existing missing-discovery control is unresolved, not bounded absence",
    )
    record(
        "T05",
        "NOT_CONSTRUCTIBLE",
        "EXISTING_ACADEMIC_FIXTURE",
        "No accepted end-to-end NO_QUALIFIED_CLAIM source cohort; no new fixture",
    )


def test_T06_typed_withholding(missing):
    read = w._features(missing, VECTORS[0][0] + "T18:00:00+08:00")
    assert type(read) is w.DiagnosticReadWithheld and read.reason == "DEPENDENCY_UNRESOLVED"
    assert read.native_invocations == ("RUN",) and not hasattr(read, "audit")
    assert all(type(getattr(read, f.name)) in (str, tuple, bool) for f in fields(read))
    record(
        "T06",
        "PASS",
        "OBSERVED_PUBLIC_NATIVE_CONTROL",
        "Actual no-value Native result withholds read data; no Weekly WITHHELD enum invented",
    )
    record(
        "T06",
        "DEFERRED",
        "NO_ACCEPTED_SOURCE_ORACLE",
        "End-to-end Weekly withheld-source transport not adopted",
    )


@pytest.mark.parametrize(
    "kind", ["duplicate", "swap", "drop", "extra", "foreign", "reencoded", "clock", "order"]
)
def test_T07_hostile_ticks_before_native(positive, kind):
    ticks = tuple(e.tick_bytes for e in positive[1].entries)
    if kind == "duplicate":
        ticks = (ticks[0], ticks[0], *ticks[2:])
    elif kind == "swap":
        ticks = (ticks[1], ticks[0], *ticks[2:])
    elif kind == "drop":
        ticks = ticks[:-1]
    elif kind == "extra":
        ticks = (*ticks, ticks[0])
    elif kind == "foreign":
        ticks = (b"foreign", *ticks[1:])
    else:
        obj = json.loads(ticks[0])
        if kind == "clock":
            obj["cutoff"]["source_text"] = "2027-01-08T00:00:00+08:00"
        if kind == "order":
            obj["tick_order"] = 4
        ticks = (json.dumps(obj, indent=2).encode(), *ticks[1:])
    read, audit, count = execute("T07-" + kind, ticks)
    assert count == 0 and type(read) is w.DiagnosticReadWithheld and isinstance(audit, w._Refusal)
    assert read.reason == "WU04_TICK_TUPLE_MISMATCH" and read.native_invocations == ()
    record("T07", "PASS", "OBSERVED_PRECALL_REFUSAL", kind)


@pytest.mark.parametrize(
    "field",
    [
        "manifest_ref",
        "calendar_ref",
        "config_ref",
        "default_seed",
        "requested_feature_refs",
        "issuer_refs",
        "packet",
    ],
)
def test_T08_changed_source_pin(field, monkeypatch):
    original = w._regular_bytes

    def changed(path):
        body = original(path)
        if path == ROOT / w.SOURCE_PINS[0][0] and field != "packet":
            obj = json.loads(body)
            if field == "default_seed":
                obj[field] = 18
            elif field == "issuer_refs":
                obj["input_spec"]["roster"] = []
            elif field == "requested_feature_refs":
                obj["input_spec"][field] = ["alien"]
            else:
                obj["input_spec"][field] = "alien"
            return json.dumps(obj).encode()
        if path == ROOT / w.SOURCE_PINS[1][0] and field == "packet":
            return body + b"\n"
        return body

    monkeypatch.setattr(w, "_regular_bytes", changed)
    read, _audit, count = execute("T08-" + field)
    assert count == 0 and read.reason == "WU04_SOURCE_PIN_MISMATCH"
    record("T08", "PASS", "OBSERVED_PRECALL_REFUSAL", field)


def test_T09_read_drift_and_real_origins(monkeypatch):
    original = w._regular_bytes
    reads = 0

    def drift(path):
        nonlocal reads
        body = original(path)
        if path == ROOT / w.MODULE_PATH:
            reads += 1
            if reads > 1:
                return body + b"\n"
        return body

    with monkeypatch.context() as m:
        m.setattr(w, "_regular_bytes", drift)
        result = w._observe()
        assert (
            isinstance(result, w._Unavailable)
            and result.reason == "WU04_OBSERVATION_CHANGED_DURING_READ"
        )
    with monkeypatch.context() as m:
        m.setattr(w, "__file__", "/foreign/weekly_sequence.py")
        assert w._observe().reason == "WU04_CHECKOUT_LAYOUT_INVALID"
    with monkeypatch.context() as m:
        m.setattr(r, "__file__", "/foreign/ratio_observations.py")
        assert w._observe().reason == "WU04_LOADED_OWNER_ROOT_MISMATCH"
    record(
        "T09",
        "PASS",
        "OBSERVED_READ_DRIFT_CONTROL",
        "Real observers, lexical origin and double-read own-code refusal",
    )


def after_drift(monkeypatch, failure=False):
    original_read, original_invoke = w._regular_bytes, r.invoke_ratio
    entered = False

    def source_drift(path):
        body = original_read(path)
        return body + b"\n" if entered and path == ROOT / w.SOURCE_PINS[0][0] else body

    def invoked(assembly):
        nonlocal entered
        result = original_invoke(assembly)
        entered = True
        return result

    def fault(_value):
        raise RuntimeError("WU04_CONTROLLED_FORMAT_FAILURE")

    monkeypatch.setattr(w, "_regular_bytes", source_drift)
    monkeypatch.setattr(r, "invoke_ratio", invoked)
    if failure:
        monkeypatch.setattr(ratio, "_canonical", fault)
    return execute("T16-entered-failure" if failure else "T09-after-RUN")


def test_T09_after_real_RUN_is_preserved(monkeypatch):
    read, audit, count = after_drift(monkeypatch)
    assert count == 1 and isinstance(audit, w._SequenceAudit)
    assert tuple(e.native_invocation for e in audit.entries) == (
        "RUN",
        "NOT_RUN",
        "NOT_RUN",
        "NOT_RUN",
    )
    assert isinstance(audit.entries[0].outcome, r.RatioDiagnostic)
    assert audit.entries[0].outcome.native_result is audit.entries[0].attempt.native_result
    assert read.reason == "WU04_SOURCE_PIN_MISMATCH"
    record(
        "T09",
        "PASS",
        "OBSERVED_PUBLIC_EXECUTION_AND_DRIFT",
        "Real RUN retained after source drift, all four positions retained",
    )


def test_T10_closed_detached_read(positive):
    read = positive[0]
    assert type(read) is bytes and not hasattr(read, "__dict__")
    assert_tree(strict(read), oracle())
    first = strict(read)
    first["ticks"][0]["features"]["derived_quarter_revenue"]["value"] = 999
    assert_tree(strict(read), oracle())
    for bad in [read + b"{}", b'{"x":1,"x":2}', b'{"x":1.5}', b'{"x":NaN}']:
        with pytest.raises((ValueError, AssertionError)):
            strict(bad)
    for forbidden in [
        b"payload_bytes",
        b"upstream",
        b"slots",
        b"source_payload",
        b"endpoint",
        b"price",
        b"label",
        b"PREP01",
        b"/home/",
        b"source_packet",
        b"audit",
    ]:
        assert forbidden not in read
    record(
        "T10",
        "PASS",
        "OBSERVED_DETACHED_BYTES",
        "Recursive exact schema/types, independent oracle, no reachable audit/Native/pack; not hostile-process isolation",
    )


def test_T11_no_midnight_B03_admission(positive):
    ticks = tuple(e.tick_bytes for e in positive[1].entries)
    midnight = json.loads(ticks[0])
    midnight["cutoff"]["source_text"] = "2027-01-08T00:00:00+08:00"
    read, _audit, count = execute("T11-midnight", (json.dumps(midnight).encode(), *ticks[1:]))
    assert count == 0 and read.reason == "WU04_TICK_TUPLE_MISMATCH"
    record(
        "T11",
        "PASS",
        "OBSERVED_PRECALL_REFUSAL",
        "Midnight context rejected; INVALID_DECISION_CUTOFF is existing B2 proof, not a new B03 invocation",
    )


def test_T12_mixed_month_cohort(positive):
    first, second = (positive[1].entries[i].assembly for i in (0, 1))
    slots = (first.upstream.slots[0], *second.upstream.slots[1:])
    with count_a05() as calls:
        result = ratio_slice.evaluate_ratio(
            second.specification,
            second.upstream.specification,
            slots,
            second.before_observation.code,
        )
    assert calls == ["evaluate_ratio"]
    assert (result.outcome.state, result.outcome.reason) == (
        "CONTRACT_VIOLATION",
        "MIXED_RECONSTRUCTION_CONTEXT",
    )
    CONTROLS.append(
        dict(
            case="T12", public_A05_calls=1, state=result.outcome.state, reason=result.outcome.reason
        )
    )
    record("T12", "PASS", "OBSERVED_PUBLIC_NATIVE_CONTROL", "No context coercion")


def test_T13_no_F3_F5_feed():
    assert w.__all__ == ["DiagnosticReadWithheld", "run_weekly_sequence"]
    assert not any(
        hasattr(w, x)
        for x in [
            "SnapshotReference",
            "DecisionSchedule",
            "PerDecisionBinding",
            "ResearchRun",
            "get_audit",
            "project_candidate",
        ]
    )
    record(
        "T13",
        "DEFERRED",
        "DEFERRED_F3_F5",
        "No policies or same-info comparison implemented; public exports contain no consumer/admitted reference",
    )


def test_T14_fresh_reissue(positive):
    read, audit, count = execute("reissue")
    assert count == 4 and read == positive[0]
    assert audit.attempt_token is not positive[1].attempt_token
    for original, repeated in zip(positive[1].entries, audit.entries, strict=True):
        assert repeated.attempt is not original.attempt
        assert repeated.attempt.native_result is not original.attempt.native_result
        assert repeated.attempt.native_result == original.attempt.native_result
    record(
        "T14",
        "PASS",
        "OBSERVED_PUBLIC_REEXECUTION",
        "Four fresh independent A05 issuances; local repeatability, not IF03 canonical replay",
    )


def status_block(body, owner):
    key = (
        "permitted"
        if owner.endswith("native_requests.py")
        else "_STATUS_PATHS"
        if owner.endswith("asof_requests.py")
        else "STATUS_PATHS"
    )
    blocks = [
        n
        for n in ast.walk(ast.parse(body))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == key for t in n.targets)
    ]
    if key == "permitted":
        blocks = [
            n
            for n in blocks
            if any(
                isinstance(c, ast.Constant)
                and c.value == "src/pit_research_lab/mvp/f2/causal_observations.py"
                for c in ast.walk(n.value)
            )
        ]
    assert len(blocks) == 1
    n = blocks[0]
    lines = body.splitlines(keepends=True)
    return b"".join(lines[n.lineno - 1 : n.end_lineno])


def fixed(path):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(ROOT), "show", f"{BASE}:{path}"]
    )


def reconstruct_owner(path):
    current, baseline = (ROOT / path).read_bytes(), fixed(path)
    block = status_block(current, path)
    for p in NEW:
        literal = ('        "' + p + '",\n').encode()
        assert current.count(literal) == block.count(literal) == 1
    if path == OLD[-1]:
        # Owner-approved OD03A: exactly this formatted block, no generic normalization.
        expected = (
            b"STATUS_PATHS = frozenset(\n    (\n        *LOCAL_PATHS,\n        FIXTURE_PATH,\n"
            b'        "src/pit_research_lab/mvp/f2/weekly_sequence.py",\n'
            b'        "tests/unit/mvp_f2/test_weekly_sequence.py",\n    )\n)\n'
        )
        original = b"STATUS_PATHS = frozenset((*LOCAL_PATHS, FIXTURE_PATH))\n"
        assert block == expected and status_block(baseline, path) == original
        restored = current.replace(expected, original, 1)
    else:
        restored = current
        for p in NEW:
            literal = ('        "' + p + '",\n').encode()
            restored = restored.replace(literal, b"", 1)
    assert restored == baseline


def outside_functions(body, allowed):
    lines = body.splitlines(keepends=True)
    nodes = [
        n for n in ast.parse(body).body if isinstance(n, ast.FunctionDef) and n.name in allowed
    ]
    assert {n.name for n in nodes} == set(allowed)
    for n in reversed(nodes):
        # Function headers, decorators and every other byte remain immutable.
        del lines[n.body[0].lineno - 1 : n.end_lineno]
    return b"".join(lines)


def test_T15_fixed_B2_guards_and_no_moving_baseline():
    def check():
        for p in OLD:
            reconstruct_owner(p)
        for p, allowed in [
            (
                "tests/unit/mvp_f2/test_ratio_observations.py",
                {"test_B1_T15_existing_adapter_bytes_only_three_literal_insertions"},
            ),
            (
                "tests/unit/mvp_f2/test_causal_observations.py",
                {
                    "test_b2_four_owner_exact_byte_guard_fixed_b1_baseline",
                    "test_only_t15_hunk_in_existing_test_and_post_commit_durability",
                },
            ),
        ]:
            assert outside_functions((ROOT / p).read_bytes(), allowed) == outside_functions(
                fixed(p), allowed
            )

    check()
    original = subprocess.check_output

    def immutable(args, **kwargs):
        assert not any(str(a).startswith("HEAD:") for a in args)
        return original(args, **kwargs)

    with patch.object(subprocess, "check_output", immutable):
        check()
    record(
        "T15",
        "PASS",
        "IMMUTABLE_BYTE_PROOF",
        "Five fixed-B2 owner guards; only named legacy test bodies changed; HEAD: prohibited",
    )


@pytest.fixture(scope="module")
def w02():
    code = observe_code(ROOT)
    receipt = nr.CallerObservationReceipt(
        "MVP-F2-WU-02-S1S2-IMPL-01",
        str(ROOT),
        tuple(p[0] for p in nr.NATIVE_CODE_PINS),
        "WU04_REAL_SIX_PATH_OBSERVATION",
        "pit_slice.observe_code",
        True,
    )
    return nr.ObservedCodeInput(code, receipt)


@pytest.mark.parametrize("path", NEW)
@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("?? ", (True, True, True)),
        (" M ", (True, True, True)),
        ("A  ", (True, False, False)),
        ("M  ", (True, True, False)),
        ("D  ", (False, False, False)),
        ("R  ", (False, False, False)),
        ("UU ", (False, False, False)),
    ],
)
def test_T15_five_parser_grammars(w02, path, prefix, expected):
    raw = prefix + path + "\n"
    controlled = replace(w02, code=replace(w02.code, worktree_status=raw.strip()))
    assert (nr._observation_reason(controlled) is None) == expected[0]
    assert ar._status_valid(raw) == expected[1]
    for owner in (d, r, b):
        assert owner._status_valid(raw) == expected[2]


def test_T15_actual_unstaged_observers(w02):
    assert nr._observation_reason(w02) is None
    assert isinstance(ar.observe_g03_code(), ar.G03ObservedCodeInput)
    assert isinstance(d.observe_wu03_code(), d.WU03ObservedCodeInput)
    assert isinstance(r.observe_ratio_diagnostic_code(), r.ObservedRatioCode)
    assert isinstance(b.observe_causal_diagnostic_code(), b.ObservedCausalCode)
    assert isinstance(w._observe(), w._Observation)
    for raw in [
        "?? unrelated.py\n",
        "R  a -> b\n",
        " D " + NEW[0] + "\n",
        "?? " + NEW[0] + ".bak\n",
    ]:
        assert all(not owner._status_valid(raw) for owner in (ar, d, r, b, w))
    record(
        "T15",
        "PASS",
        "OBSERVED_REAL_UNSTAGED_CHECKOUT",
        "Five actual legacy observers; staged grammar tested as parser controls only; post-commit clean test reserved",
    )


def test_T16_entered_exception_then_after_fault(monkeypatch):
    read, audit, count = after_drift(monkeypatch, failure=True)
    assert count == 1
    first = audit.entries[0]
    assert isinstance(first.attempt, r.InvocationFailure) and first.outcome is first.attempt
    assert first.attempt.exact_native_exception_type == "RuntimeError"
    assert first.attempt.code == "WU04_CONTROLLED_FORMAT_FAILURE"
    assert tuple(e.native_invocation for e in audit.entries) == (
        "ATTEMPTED",
        "NOT_RUN",
        "NOT_RUN",
        "NOT_RUN",
    )
    assert read.reason == "WU04_SOURCE_PIN_MISMATCH" and first.outer_reason == read.reason
    record(
        "T16",
        "PASS",
        "OBSERVED_NATIVE_ENTRY_AND_EXCEPTION",
        "Real Native call/formatter exception retained after actual observer source fault",
    )


def test_T17_no_label_price_authority(positive):
    assert_tree(strict(positive[0]), oracle())
    record(
        "T17",
        "DEFERRED",
        "DEFERRED_F3_F5",
        "Maturity/execution/returns authority deferred; strict read keys exclude them",
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"issuer_ref": "SYN-B"},
        {"feature": "alien"},
        {"source_packet": b"midnight"},
        {"metadata": {}},
        {"pack": object()},
    ],
)
def test_T18_closed_API(kwargs):
    with count_a05() as calls:
        with pytest.raises(TypeError):
            w.run_weekly_sequence(**kwargs)
    assert calls == []
    record("T18", "PASS", "OBSERVED_CLOSED_SIGNATURE_REFUSAL", next(iter(kwargs)))


def test_T18_foreign_source_packets(monkeypatch):
    original = w._regular_bytes
    for name in ["ratio_observations_v0.1.json", "causal_observations_v0.1.json"]:
        alien = (ROOT / "tests/unit/mvp_f2/data" / name).read_bytes()
        with monkeypatch.context() as m:
            m.setattr(
                w,
                "_regular_bytes",
                lambda path, alien=alien: (
                    alien if path == ROOT / w.SOURCE_PINS[1][0] else original(path)
                ),
            )
            read, _audit, count = execute("T18-" + name)
            assert count == 0 and read.reason == "WU04_SOURCE_PIN_MISMATCH"
    record(
        "T18",
        "PASS",
        "OBSERVED_FOREIGN_SOURCE_REFUSAL",
        "B1 negative and B2 midnight packets remain excluded",
    )


def test_owner_regular_file_boundary(tmp_path):
    normal = tmp_path / "owner"
    normal.write_bytes(b"source")
    link = tmp_path / "link"
    link.symlink_to(normal)
    with pytest.raises(ValueError, match="WU04_SYMLINK_REFUSED"):
        w._regular_bytes(link)
    hard = tmp_path / "hard"
    os.link(normal, hard)
    with pytest.raises(ValueError, match="WU04_NONREGULAR_OR_LINKED"):
        w._regular_bytes(normal)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="WU04_NONREGULAR_OR_LINKED"):
        w._regular_bytes(fifo)


def test_T09_preinvoke_source_drift_preserves_NOT_RUN(monkeypatch):
    original_read, original_prepare = w._regular_bytes, r.prepare_ratio_request
    prepared = False

    def prepare(*args):
        nonlocal prepared
        assembly = original_prepare(*args)
        prepared = True
        return assembly

    def changed(path):
        body = original_read(path)
        return body + b"\n" if prepared and path == ROOT / w.SOURCE_PINS[0][0] else body

    monkeypatch.setattr(r, "prepare_ratio_request", prepare)
    monkeypatch.setattr(w, "_regular_bytes", changed)
    read, audit, count = execute("T09-preinvoke")
    assert count == 0 and isinstance(audit, w._SequenceAudit)
    assert isinstance(audit.entries[0].assembly, r.RatioRequestAssembly)
    assert all(e.attempt is None and e.native_invocation == "NOT_RUN" for e in audit.entries)
    assert read.reason == "WU04_SOURCE_PIN_MISMATCH"
    record(
        "T09",
        "PASS",
        "OBSERVED_PREINVOKE_DRIFT",
        "Issued assembly retained; no Native call after source drift",
    )


def test_T06_real_native_malformed_preview_is_withheld(positive, monkeypatch):
    assembly = positive[1].entries[0].assembly
    # Real Native math and replay run; only the nonnumerical formatter is faulted.
    monkeypatch.setattr(ratio, "_canonical", lambda _value: b"{}")
    with count_a05() as calls:
        result = ratio_slice.evaluate_ratio(
            assembly.specification,
            assembly.upstream.specification,
            assembly.upstream.slots,
            assembly.before_observation.code,
        )
    assert calls == ["evaluate_ratio"] and result.outcome.state == "VALUE_AVAILABLE"
    assert result.diagnostic_preview_bytes == b"{}"
    read = w._features(result, "2027-01-07T18:00:00+08:00")
    assert isinstance(read, w.DiagnosticReadWithheld)
    assert read.reason == "WU04_NATIVE_PREVIEW_MISMATCH"
    CONTROLS.append(
        dict(
            case="T06",
            public_A05_calls=1,
            state=result.outcome.state,
            projection_reason=read.reason,
        )
    )
    record(
        "T06",
        "PASS",
        "OBSERVED_NATIVE_FORMATTER_CONTROL",
        "Malformed actual preview withholds read; actual value/result retained as control evidence",
    )
