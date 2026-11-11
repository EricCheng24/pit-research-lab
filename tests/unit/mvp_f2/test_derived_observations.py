"""Frozen source E2E and explicitly separate direct-Native hostile controls.

Tests never manufacture completed discovery/coverage. Numeric variants and their
proofs were authored in the fixture before the first WU03-A invocation. Hostile
mutations retain original evidence (and may therefore fail at an earlier owner).
"""

import ast
import builtins
import copy
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import derived_slice
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.pit_slice import evaluate_slice, observe_code
from pit_research_lab.mvp.f2 import asof_requests as ar
from pit_research_lab.mvp.f2 import derived_observations as d
from pit_research_lab.mvp.f2 import native_requests as nr
from pit_research_lab.mvp.f2.synthetic_temporal import build_pack, build_weekly_requests

ROOT = Path(__file__).parents[3]
DATA = Path(__file__).parent / "data"
NEW_PATHS = (
    d.ADAPTER_PATH,
    "tests/unit/mvp_f2/data/derived_observations_v0.1.json",
    "tests/unit/mvp_f2/test_derived_observations.py",
)


def w02_observation():
    for path, digest, length in nr.NATIVE_CODE_PINS:
        body = d._regular_bytes(ROOT / path)
        assert sha256(body).hexdigest() == digest and len(body) == length
    code = observe_code(ROOT)
    receipt = nr.CallerObservationReceipt(
        "MVP-F2-WU-02-S1S2-IMPL-01",
        str(ROOT),
        tuple(path for path, _, _ in nr.NATIVE_CODE_PINS),
        "WU03_TEST_ACTUAL_SIX_PIN_OBSERVATION",
        "pit_slice.observe_code",
        True,
    )
    return nr.ObservedCodeInput(code, receipt)


@pytest.fixture(scope="module")
def inputs():
    body = (DATA / "derived_observations_v0.1.json").read_bytes()
    assert len(body) == 5_440_756
    assert (
        sha256(body).hexdigest()
        == "b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e"
    )
    foundation = json.loads((DATA / "temporal_foundation_v0.1.json").read_bytes())
    pack = build_pack(foundation["input_spec"], foundation["default_seed"])
    return body, json.loads(body), pack, build_weekly_requests(pack).requests


@pytest.fixture(scope="module")
def completed(inputs):
    body, _, pack, ticks = inputs
    before = d.observe_wu03_code()
    assert isinstance(before, d.WU03ObservedCodeInput), before
    assemblies, attempts, diagnostics = [], [], []
    for tick in ticks:
        assembly = d.prepare_derived_request(pack, tick, body, before)
        assert isinstance(assembly, d.WU03RequestAssembly), assembly
        attempt = d.invoke_derived(assembly)
        assert isinstance(attempt, d.WU03NativeAttempt), attempt
        diagnostic = d.finalize_derived_diagnostic(attempt, d.observe_wu03_code())
        assert isinstance(diagnostic, d.WU03Diagnostic), diagnostic
        assert diagnostic.native_result is attempt.native_result
        assemblies.append(assembly)
        attempts.append(attempt)
        diagnostics.append(diagnostic)
    after = d.observe_wu03_code()
    assert before == after
    if destination := os.environ.get("WU03_EVIDENCE_OUTPUT"):
        path = Path(destination)
        assert path.is_absolute() and not path.is_relative_to(ROOT)
        path.write_text(
            json.dumps(
                {
                    "fixture_sha256": d.FIXTURE_SHA256,
                    "before": d._wire(before.code),
                    "after": d._wire(after.code),
                    "adapter_sha256": before.adapter_sha256,
                    "status": before.raw_status,
                    "results": [
                        {
                            "execution": attempt.native_invocation,
                            "outcome": d._wire(attempt.native_result.outcome),
                            "realization_ref": attempt.native_result.realization_ref,
                            "preview": attempt.native_result.diagnostic_preview_bytes.decode(),
                            "s3": [
                                d._wire(dep.actual.selection)
                                for dep in attempt.native_result.dependencies
                            ],
                        }
                        for attempt in attempts
                    ],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
    return tuple(assemblies), tuple(attempts), tuple(diagnostics)


@pytest.mark.parametrize(
    "index,december,total", [(0, 100, 140), (1, 110, 150), (2, 110, 150), (3, 90, 130)]
)
def test_t01_four_actual_native_cutoffs(completed, index, december, total):
    assemblies, attempts, diagnostics = completed
    result = attempts[index].native_result
    assert (result.outcome.state, result.outcome.reason, result.outcome.value) == (
        "VALUE_AVAILABLE",
        "NONE",
        total,
    )
    assert [dep.actual.selection.selected_value for dep in result.dependencies] == [
        17,
        23,
        december,
    ]
    assert all(dep.actual.selection.state == "SELECTED" for dep in result.dependencies)
    assert all(
        dep.actual == derived_slice.evaluate_asof(dep.slot.request, result.code)
        for dep in result.dependencies
    )
    for dep in result.dependencies:
        for candidate in dep.actual.inputs.candidates:
            assert candidate.actual.s1.state == "BOUND"
            assert (candidate.actual.s2.state, candidate.actual.s2.reason) == ("SUPPORTED", "NONE")
        for relation in dep.actual.inputs.relations:
            assert relation.notice.actual.s1.state == "BOUND"
            assert relation.notice.actual.s2.state == "SUPPORTED"
    assert result == d.invoke_derived(assemblies[index]).native_result
    assert diagnostics[index].native_result is result


@pytest.mark.parametrize("index,tag", [(0, "D1"), (1, "D2"), (2, "D2"), (3, "D3")])
def test_t02_full_month_source_lineage(inputs, completed, index, tag):
    sources = {x["tag"]: x for x in inputs[1]["sources"]}
    result = completed[1][index].native_result
    assert len(result.outcome.lineage) == 3
    for line, month, source_tag, end in zip(
        result.outcome.lineage, (10, 11, 12), ("O", "N", tag), (31, 30, 31), strict=True
    ):
        assert line.period == (date(2026, month, 1), date(2026, month, end))
        assert line.subject_ref == f"PREP01-SUB-2026-{month}"
        assert line.assertion_refs == ("PREP01-A-" + source_tag,)
        assert line.content_version_refs == ("PREP01-CV-" + source_tag,)
        assert line.representation_refs == ("PREP01-REP-" + source_tag,)
        assert line.raw_sha256s == (sources[source_tag]["raw"]["sha256"],)
        assert line.unit == "NTD_thousands"
    if index == 3:
        selection = result.dependencies[2].actual.selection
        assert selection.derived_reachability == (
            s.Reachability("PREP01-A-D1", "PREP01-A-D3", ("PREP01-N12", "PREP01-N23")),
        )
        assert [(r.state, r.effect) for r in selection.relations] == [
            ("QUALIFIED", "SUPERSEDES"),
            ("QUALIFIED", "SUPERSEDES"),
        ]


def test_t03_frozen_views_exclude_equal_and_future_sources(inputs, completed):
    _, obj, _, _ = inputs
    assert obj["views"][2]["source_tags"] == ["D1"]
    assert obj["views"][8]["source_tags"] == ["D1", "D2"]
    for index, absent in ((0, "PREP01-A-D2"), (2, "PREP01-A-D3")):
        result = completed[1][index].native_result
        assert absent not in [x.ref for x in result.dependencies[2].actual.inputs.candidates]
        assert absent not in result.diagnostic_preview_bytes.decode()
    # Direct Native audit control: frozen t4 December inventory at an earlier cutoff.
    early = completed[0][2]
    later = completed[0][3].slots[2].request
    cutoff_context = early.slots[2].request.context
    # Keep discovery's original retained bytes. A future source is tested through
    # the already frozen request at its own cutoff via S1/S2 below, rather than
    # manufacturing new completed discovery for the earlier request.
    for candidate, cutoff in (
        (later.candidates[1], completed[0][0].slots[2].request.context),
        (later.candidates[2], cutoff_context),
    ):
        result = derived_slice.evaluate_asof(early.slots[2].request, early.before_observation.code)
        assessed = evaluate_slice(cutoff, candidate.request, early.before_observation.code)
        assert (assessed.s2.state, assessed.s2.reason) == (
            "NOT_ADMISSIBLE",
            "PUBLICATION_NOT_PRE_CUTOFF",
        )
        assert result.selection.selected_value == 110
    # Computation metadata is audit-only; no evidence is rewritten or completed.
    slots = tuple(
        replace(
            slot,
            request=replace(
                slot.request,
                context=replace(
                    slot.request.context, decision_wall_times=("LATER_RESEARCH_AUDIT",)
                ),
            ),
        )
        for slot in early.slots
    )
    native = derived_slice.evaluate_derived(
        early.specification, slots, early.before_observation.code
    )
    assert native.outcome.value == 150
    assert native.diagnostic_preview_bytes == completed[1][2].native_result.diagnostic_preview_bytes


def test_t04_replay_and_cutoff_identity(completed):
    results = [a.native_result for a in completed[1]]
    assert results[1].outcome.lineage == results[2].outcome.lineage
    assert results[1].realization_ref != results[2].realization_ref
    assert (
        results[1].dependencies[2].actual.reconstruction_ref
        != results[2].dependencies[2].actual.reconstruction_ref
    )
    assert len({r.realization_ref for r in results}) == 4
    assert results[0].outcome.lineage[2] != results[1].outcome.lineage[2]


@pytest.mark.parametrize("control_index,cutoff_index,total", [(3, 0, 140), (4, 2, 150)])
def test_t03_frozen_post_cutoff_notice_inventory_cannot_change_preview(
    inputs, completed, control_index, cutoff_index, total
):
    control = inputs[1]["native_controls"][control_index]
    request = d._decode(control["request"], {})
    assert request.discovery.raw_bytes == s.discovery_proposition(request.discovery)
    assembly = completed[0][cutoff_index]
    result = run_hostile(assembly, 2, request, request.subject)
    assert (result.outcome.state, result.outcome.reason, result.outcome.value) == (
        "VALUE_AVAILABLE",
        "NONE",
        total,
    )
    original = completed[1][cutoff_index].native_result
    assert result.diagnostic_preview_bytes == original.diagnostic_preview_bytes
    assert result.outcome.lineage == original.outcome.lineage
    assert any(
        c.actual.s2.state == "NOT_ADMISSIBLE"
        for c in result.dependencies[2].actual.inputs.candidates
    )
    assert any(
        r.notice.actual.s2.reason == "PUBLICATION_NOT_PRE_CUTOFF"
        for r in result.dependencies[2].actual.inputs.relations
    )
    assert result.research_only_audit != original.research_only_audit


@pytest.mark.parametrize("kind", ["tick", "cutoff", "manifest", "source"])
def test_t04_adapter_rejects_changed_inputs_before_invocation(inputs, completed, kind):
    body, _, pack, ticks = inputs
    tick = ticks[0]
    if kind == "source":
        body += b" "
    else:
        data = json.loads(tick)
        if kind == "cutoff":
            data["cutoff"]["source_text"] = "2027-01-07T18:00:01+08:00"
        else:
            data["manifest_ref" if kind == "manifest" else "tick_id"] += "-FORGED"
        tick = json.dumps(data).encode()
    refused = d.prepare_derived_request(pack, tick, body, completed[0][0].before_observation)
    assert isinstance(refused, d.WU03MappingRefusal) and refused.native_invocation == "NOT_RUN"
    assert refused.reason in ("WU03_SOURCE_NOT_ACCEPTED", "WU03_TICK_NOT_MEMBER")


def run_hostile(assembly, index, request, expected_subject=None, spec=None):
    """Direct Native hostile input; never issue a prepared adapter receipt."""
    slots = tuple(
        replace(slot, request=request, expected_subject=expected_subject or slot.expected_subject)
        if i == index
        else slot
        for i, slot in enumerate(assembly.slots)
    )
    return derived_slice.evaluate_derived(
        spec or assembly.specification, slots, assembly.before_observation.code
    )


@pytest.mark.parametrize("index", [0, 1])
def test_t05_missing_month_is_unresolved_not_absence(completed, index):
    assembly = completed[0][0]
    old = assembly.slots[index].request
    # Challenge supplied membership and coverage together; retain no claim that
    # this missing descriptor proves bounded completeness.
    coverage = replace(
        old.coverage,
        evaluated_candidate_refs=(),
        checks=tuple(replace(x, status="NOT_PERFORMED") for x in old.coverage.checks),
    )
    request = replace(
        old,
        candidates=(),
        discovery=c.NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT"),
        coverage=coverage,
    )
    result = run_hostile(assembly, index, request)
    assert (result.outcome.state, result.outcome.reason) == ("UNRESOLVED", "DEPENDENCY_UNRESOLVED")
    assert result.dependencies[index].actual.selection.reason == "COVERAGE_INSUFFICIENT"
    assert isinstance(result.outcome.value, c.NotEvaluated)
    assert isinstance(result.diagnostic_preview_bytes, c.NotEvaluated)


def test_t05_valid_unknown_publication_preserves_owner_reason(completed):
    assembly = completed[0][0]
    old = assembly.slots[0].request
    candidate = old.candidates[0]
    request = candidate.request
    binding = request.attempts[0].supplied
    proof = binding.proof_candidate
    desc = dict(proof.raw_descriptor)
    desc.update(
        proof_kind="unparsed_source_time",
        timestamp=None,
        timezone=None,
        offset=None,
        precision="MINUTE",
        unparsed_source_text="synthetic source time unresolved",
    )
    unknown = c.Unknown(c.UnknownCause.AMBIGUOUS_SOURCE, None, proof.origin)
    unresolved = c.UnresolvedSourceTime(
        proof_ref=proof.proof_ref,
        target_kind=proof.target_kind,
        target_ref=proof.target_ref,
        content_version_ref=proof.content_version_ref,
        fragment_selector=proof.fragment_selector,
        raw_descriptor=tuple(sorted(desc.items())),
        origin=proof.origin,
        source_text=desc["unparsed_source_text"],
        timezone=unknown,
        offset=unknown,
        precision=c.Known("MINUTE", proof.origin),
    )
    binding = replace(binding, proof_candidate=unresolved)
    records = replace(request.scope.source_records, supports=(binding,))
    request = replace(
        request,
        attempts=(c.RequestBindingAttempt(request.requested, binding),),
        scope=replace(request.scope, source_records=records),
    )
    context = old.context
    result = evaluate_slice(context, request, assembly.before_observation.code)
    assert result.s1.state == "BOUND"
    assert (result.s2.state, result.s2.reason) == ("UNRESOLVED", "TIMEZONE_UNRESOLVED")
    # Unperformed coverage keeps this owner uncertainty visible at S3/A04.
    # Discovery omitted deliberately: no new completion proof is generated.
    challenged = replace(
        old,
        candidates=(replace(candidate, request=request),),
        discovery=c.NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT"),
        coverage=replace(
            old.coverage,
            checks=tuple(replace(x, status="NOT_PERFORMED") for x in old.coverage.checks),
        ),
    )
    derived = run_hostile(assembly, 0, challenged)
    assert (derived.outcome.state, derived.outcome.reason) == (
        "UNRESOLVED",
        "DEPENDENCY_UNRESOLVED",
    )
    assert (
        derived.dependencies[0].actual.inputs.candidates[0].actual.s2.reason
        == "TIMEZONE_UNRESOLVED"
    )


@pytest.mark.parametrize(
    "name,value,reason",
    [
        ("basis_ref", "FOREIGN", "INCOMPATIBLE_SUBJECT_BASIS_REF"),
        ("currency", "USD", "INCOMPATIBLE_SUBJECT_CURRENCY"),
        ("canonical_unit", "NTD", "INCOMPATIBLE_SUBJECT_CANONICAL_UNIT"),
        ("economic_entity_ref", "SYN-B", "INCOMPATIBLE_SUBJECT_ECONOMIC_ENTITY_REF"),
    ],
)
def test_t05_incompatible_subject_contracts(completed, name, value, reason):
    assembly = completed[0][0]
    old = assembly.slots[0].request
    subject = replace(old.subject, **{name: c.Known(value, old.subject.origin)})
    result = run_hostile(assembly, 0, replace(old, subject=subject), expected_subject=subject)
    assert (result.outcome.state, result.outcome.reason) == ("CONTRACT_VIOLATION", reason)


def test_t05_slot_quarter_and_context_contract(completed):
    assembly = completed[0][0]
    code = assembly.before_observation.code
    result = derived_slice.evaluate_derived(
        assembly.specification, (assembly.slots[0], assembly.slots[0], assembly.slots[2]), code
    )
    assert result.outcome.reason == "MISSING_OR_DUPLICATE_SLOT"
    result = derived_slice.evaluate_derived(
        replace(assembly.specification, quarter=3), assembly.slots, code
    )
    assert result.outcome.reason == "INCOMPATIBLE_SUBJECT_PERIOD_START"
    old = assembly.slots[0].request
    result = run_hostile(
        assembly, 0, replace(old, context=replace(old.context, evidence_set_ref="FOREIGN"))
    )
    assert result.outcome.reason == "MIXED_RECONSTRUCTION_CONTEXT"


@pytest.mark.parametrize(
    "kind",
    [
        "raw",
        "descriptor",
        "page",
        "termination",
        "version",
        "relation",
        "operation_hash",
        "failed",
        "unperformed",
        "check",
        "tag",
        "duplicate",
    ],
)
def test_t06_every_changed_packet_refused_at_external_pin(inputs, completed, kind):
    body, obj, pack, ticks = inputs
    changed = copy.deepcopy(obj)
    view = changed["views"][5]
    if kind == "raw":
        changed["sources"][0]["raw"]["utf8"] += " "
    elif kind in ("descriptor", "page"):
        blob = (
            view["discovery_descriptor"] if kind == "descriptor" else view["pages"][0]["evidence"]
        )
        blob["utf8"] += " "
    elif kind == "termination":
        view["request"]["discovery"]["terminated"] = False
    elif kind == "version":
        changed["sources"][0]["source"]["request"]["content"]["content_version_ref"] = "FORGED"
    elif kind == "relation":
        view["request"]["relations"][0]["relation"]["new_assertion_ref"] = "FORGED"
    elif kind in ("failed", "unperformed"):
        view["operations"][0]["check"]["status"] = "FAILED" if kind == "failed" else "NOT_PERFORMED"
    elif kind == "tag":
        view["request"]["type"] = "CompletedDependency"
    else:
        view["operations"][0]["evidence"]["sha256"] = "0" * 64
    modified = (
        json.dumps(changed).encode() if kind != "duplicate" else body[:-2] + b',"schema":"bad"}\n'
    )
    result = d.prepare_derived_request(pack, ticks[1], modified, completed[0][0].before_observation)
    assert isinstance(result, d.WU03MappingRefusal)
    assert (result.stage, result.reason, result.native_invocation) == (
        "S03_SOURCE",
        "WU03_SOURCE_NOT_ACCEPTED",
        "NOT_RUN",
    )


@pytest.mark.parametrize(
    "raw,reason",
    [
        (b'{"a":1,"a":2}', "WU03_DUPLICATE_JSON_KEY"),
        (b'{"a":NaN}', "WU03_NONINTEGER_JSON"),
        (b'{"a":1.5}', "WU03_NONINTEGER_JSON"),
    ],
)
def test_t06_closed_json_decoder(raw, reason):
    with pytest.raises(c.ContractError, match=reason):
        d._json(raw)


def test_t06_completed_result_tag_never_constructible():
    for name in (
        "CompletedDependency",
        "SelectionOutcome",
        "AsOfSelectionResult",
        "DerivedResult",
        "FeatureSpec",
    ):
        with pytest.raises(c.ContractError, match="WU03_INPUT_TYPE_REFUSED"):
            d._decode({"type": name}, {})


@pytest.mark.parametrize(
    "status,state,reason",
    [
        ("FAILED", "OPERATIONAL_ERROR", "REQUIRED_OPERATION_FAILED"),
        ("NOT_PERFORMED", "CONTRACT_VIOLATION", "DISCOVERY_CHECK_MISMATCH"),
    ],
)
def test_t06_native_operation_status_never_auto_completed(completed, status, state, reason):
    assembly = completed[0][0]
    old = assembly.slots[0].request
    checks = tuple(replace(x, status=status) for x in old.coverage.checks)
    # For FAILED, omit retained discovery to reach Native operational priority;
    # for NOT_PERFORMED, leave its independent descriptor unchanged.
    request = replace(
        old,
        coverage=replace(old.coverage, checks=checks),
        discovery=c.NotEvaluated("S3", "ABSENT") if status == "FAILED" else old.discovery,
    )
    result = run_hostile(assembly, 0, request)
    assert (result.outcome.state, result.outcome.reason) == (state, reason)
    assert all(x.status == status for x in result.dependencies[0].actual.inputs.coverage.checks)


@pytest.mark.parametrize(
    "index,value,state,reason",
    [
        (0, 123, "VALUE_AVAILABLE", "NONE"),
        (1, 82, "VALUE_AVAILABLE", "NONE"),
        (2, None, "CONTRACT_VIOLATION", "INTEGER_SUM_OVERFLOW"),
    ],
)
def test_t07_frozen_numeric_source_controls(inputs, completed, index, value, state, reason):
    control = inputs[1]["native_controls"][index]
    request = d._decode(control["request"], {})
    assert request.discovery.raw_bytes == s.discovery_proposition(request.discovery)
    result = run_hostile(completed[0][0], 0, request, request.subject)
    assert (result.outcome.state, result.outcome.reason) == (state, reason)
    if value is None:
        assert isinstance(result.outcome.value, c.NotEvaluated)
    else:
        assert result.outcome.value == value == control["expected"]["value"]
        assert result.outcome.lineage[0].value == (0 if index == 0 else -41)


@pytest.mark.parametrize(
    "value,reason",
    [
        (1.5, "MUTABLE_OR_UNSUPPORTED_VALUE"),
        (True, "INVALID_NUMERIC_TYPE"),
        (2**63, "NUMERIC_RANGE"),
        (-(2**63) - 1, "NUMERIC_RANGE"),
    ],
)
def test_t07_exact_source_constructor_priority(completed, value, reason):
    assertion = completed[0][0].slots[0].request.candidates[0].request.assertion
    with pytest.raises(c.ContractError, match=reason):
        replace(assertion, source_amount=c.Known(value, assertion.origin))


@pytest.mark.parametrize("count", [6, 8])
def test_t08_native_rejects_short_observation(completed, count):
    assembly = completed[0][0]
    code = assembly.before_observation.code
    short = replace(
        code,
        observed_working_files=code.observed_working_files[:count],
        byte_lengths=code.byte_lengths[:count],
    )
    result = derived_slice.evaluate_derived(assembly.specification, assembly.slots, short)
    assert (result.outcome.state, result.outcome.reason) == (
        "CONTRACT_VIOLATION",
        "INCOMPLETE_CODE_OBSERVATION",
    )


def test_t08_forged_receipt_and_declared_drift(inputs, completed):
    assembly = completed[0][0]
    observation = assembly.before_observation
    forged = replace(observation)
    result = d.prepare_derived_request(inputs[2], inputs[3][0], inputs[0], forged)
    assert result.reason == "WU03_OBSERVATION_NOT_ISSUED" and result.native_invocation == "NOT_RUN"
    code = observation.code
    changed = replace(
        code,
        observed_working_files=(
            *code.observed_working_files[:-1],
            c.CodePin(code.observed_working_files[-1].path, "0" * 64),
        ),
    )
    result = derived_slice.evaluate_derived(assembly.specification, assembly.slots, changed)
    assert result.outcome.reason == "MIXED_DECLARED_CODE"


def test_t08_wrong_loaded_root_refused_before_io(monkeypatch):
    monkeypatch.setattr(
        d, "__file__", "/unapproved/src/pit_research_lab/mvp/f2/derived_observations.py"
    )

    def denied(*args, **kwargs):
        raise AssertionError("I/O through foreign root")

    monkeypatch.setattr(Path, "stat", denied)
    monkeypatch.setattr(subprocess, "check_output", denied)
    assert d.observe_wu03_code().reason == "WU03_LOADED_OWNER_ROOT_MISMATCH"


def test_t08_symlink_fifo_and_hardlink_refused(tmp_path):
    target = tmp_path / "regular"
    target.write_bytes(b"synthetic")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(c.ContractError, match="WU03_SYMLINK_REFUSED"):
        d._regular_bytes(link)
    hard = tmp_path / "hard"
    os.link(target, hard)
    with pytest.raises(c.ContractError, match="WU03_NONREGULAR_OR_LINKED"):
        d._regular_bytes(hard)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(c.ContractError, match="WU03_NONREGULAR_OR_LINKED"):
        d._regular_bytes(fifo)


def test_t08_native_and_adapter_byte_drift_refused(monkeypatch):
    original = d._regular_bytes

    def corrupt(path):
        body = original(path)
        return body + b"# changed" if path == ROOT / d.NATIVE_PATHS[-1] else body

    monkeypatch.setattr(d, "_regular_bytes", corrupt)
    assert d.observe_wu03_code().reason == "WU03_NATIVE_DISK_PIN_MISMATCH"
    reads = 0

    def adapter_drift(path):
        nonlocal reads
        body = original(path)
        if path == ROOT / d.ADAPTER_PATH:
            reads += 1
            if reads > 1:
                return body + b"# changed"
        return body

    monkeypatch.setattr(d, "_regular_bytes", adapter_drift)
    assert d.observe_wu03_code().reason == "WU03_OBSERVATION_CHANGED_DURING_READ"


@pytest.mark.parametrize("code", ["??", " M"])
@pytest.mark.parametrize("path", NEW_PATHS)
def test_t09_three_exact_new_paths_accepted_by_both_old_owners(inputs, path, code):
    status = code + " " + path
    # Existing W02 pure observation check; receipt origin fields must stay real.
    actual = w02_observation()
    controlled = replace(actual, code=replace(actual.code, worktree_status=status))
    assert nr._observation_reason(controlled) is None
    assert ar._status_valid(status)
    assert d._status_valid(status + "\n")


@pytest.mark.parametrize(
    "status",
    [
        "?? unrelated-file",
        " M pyproject.toml",
        "?? tests/unit/mvp_f2/test_derived_observations.py.bak",
        "?? ../escape",
        '?? "quoted"',
        "D  src/pit_research_lab/mvp/f2/derived_observations.py",
        "R  a -> b",
        "UU src/pit_research_lab/mvp/f2/derived_observations.py",
        "malformed",
        "?? tests/unit/mvp_f2/",
    ],
)
def test_t09_unrelated_and_malformed_refused_by_all_status_owners(status):
    actual = w02_observation()
    for value in (status, "?? " + NEW_PATHS[0] + "\n" + status):
        controlled = replace(actual, code=replace(actual.code, worktree_status=value))
        assert nr._observation_reason(controlled) == nr.W02AdapterReason.OBSERVATION_SCOPE_INVALID
        assert not ar._status_valid(value)
        assert not d._status_valid(value)


def test_t09_original_status_semantics_preserved():
    actual = w02_observation()
    staged = "A  " + NEW_PATHS[0]
    assert (
        nr._observation_reason(replace(actual, code=replace(actual.code, worktree_status=staged)))
        is None
    )
    assert not ar._status_valid(staged) and not d._status_valid(staged)
    assert not d._status_valid("M  " + NEW_PATHS[0])


def test_t10_real_attempt_retained_on_missing_after(completed):
    attempt = completed[1][0]
    withheld = d.finalize_derived_diagnostic(
        attempt, d.WU03ObservationUnavailable("CONTROLLED_MISSING_AFTER")
    )
    assert isinstance(withheld, d.WU03ObservationFailure)
    assert withheld.preserved is attempt and withheld.native_invocation == "RUN"
    assert withheld.preserved.native_result is attempt.native_result


def test_t08_after_adapter_drift_preserves_run(completed, monkeypatch):
    original = d._regular_bytes

    def changed_adapter(path):
        body = original(path)
        return body + b"# simulated drift" if path == ROOT / d.ADAPTER_PATH else body

    monkeypatch.setattr(d, "_regular_bytes", changed_adapter)
    after = d.observe_wu03_code()
    assert isinstance(after, d.WU03ObservedCodeInput)
    attempt = completed[1][0]
    failure = d.finalize_derived_diagnostic(attempt, after)
    assert isinstance(failure, d.WU03ObservationFailure)
    assert failure.reason == "WU03_OBSERVATION_CHANGED"
    assert failure.native_invocation == "RUN" and failure.preserved is attempt


def test_t08_root_drift_after_attempt_is_retained(completed, monkeypatch):
    attempt = completed[1][0]
    monkeypatch.setattr(
        d, "__file__", "/unapproved/src/pit_research_lab/mvp/f2/derived_observations.py"
    )
    failure = d.finalize_derived_diagnostic(attempt, d.WU03ObservationUnavailable("ROOT_CHANGED"))
    assert failure.reason == "WU03_ASSEMBLY_CHANGED" and failure.native_invocation == "RUN"
    assert failure.preserved is attempt


def test_t08_changed_retained_packet_cannot_complete(completed):
    attempt = d.invoke_derived(completed[0][0])
    # Unique actual issued attempt; deliberately challenge its immutable binding
    # without ever fabricating an issued witness or a successful Native result.
    object.__setattr__(
        attempt, "assembly", replace(attempt.assembly, source_packet_bytes=b"changed")
    )
    failure = d.finalize_derived_diagnostic(attempt, d.observe_wu03_code())
    assert isinstance(failure, d.WU03ObservationFailure)
    assert failure.native_invocation == "RUN" and failure.preserved is attempt


def test_t09_actual_observer_rejects_bad_status_before_native_observer(monkeypatch):
    original = d._git

    def staged(root, *args):
        return "A  " + NEW_PATHS[0] + "\n" if args[0] == "status" else original(root, *args)

    def denied(*args):
        raise AssertionError("Native observer must not run after dirty refusal")

    monkeypatch.setattr(d, "_git", staged)
    monkeypatch.setattr(derived_slice, "observe_derived_code", denied)
    assert d.observe_wu03_code().reason == "WU03_DIRTY_STATUS_REFUSED"


def test_t10_actual_raised_call_is_attempted_and_retained(completed, monkeypatch):
    def reject(*args):
        raise RuntimeError("CONTROLLED_NATIVE_EXCEPTION")

    monkeypatch.setattr(derived_slice, "evaluate_derived", reject)
    failed = d.invoke_derived(completed[0][0])
    assert isinstance(failed, d.WU03InvocationFailure)
    assert (failed.native_invocation, failed.exact_native_exception_type, failed.code) == (
        "ATTEMPTED",
        "RuntimeError",
        "CONTROLLED_NATIVE_EXCEPTION",
    )
    withheld = d.finalize_derived_diagnostic(failed, d.WU03ObservationUnavailable("AFTER_MISSING"))
    assert withheld.preserved is failed and withheld.native_invocation == "ATTEMPTED"
    assert d.finalize_derived_diagnostic(failed, d.observe_wu03_code()) is failed


def test_t10_unchanged_opaque_bindings_required(completed):
    assembly = completed[0][0]
    with pytest.raises(ValueError, match="NOT_RUN"):
        d.invoke_derived(replace(assembly, exact_tick_bytes=b"forged"))
    attempt = completed[1][0]
    forged = replace(attempt, native_result=completed[1][1].native_result)
    with pytest.raises(ValueError, match="WU03_ISSUED_ATTEMPT_REQUIRED"):
        d.finalize_derived_diagnostic(forged, d.observe_wu03_code())


def test_t11_diagnostic_preview_and_trust_boundary(completed):
    for diagnostic in completed[2]:
        result = diagnostic.native_result
        assert diagnostic.diagnostic_only and not diagnostic.admission_eligible
        assert diagnostic.trust == "NOT_TRUSTED_PIT_EVIDENCE"
        assert diagnostic.source_authentication == "NOT_ESTABLISHED"
        assert diagnostic.disposition == "INTEGRATED_PROVISIONAL"
        preview = json.loads(result.diagnostic_preview_bytes)
        assert set(preview) == {
            "preview_kind",
            "feature_ref",
            "cutoff",
            "mode",
            "value",
            "missingness",
            "disposition",
            "trust",
            "source_authentication",
            "admission_eligible",
            "diagnostic_only",
        }
        assert preview["value"] == result.outcome.value
        assert result.research_only_audit
        assert not hasattr(diagnostic, "to_agent_observation")
        with pytest.raises(FrozenInstanceError):
            diagnostic.admission_eligible = True


def test_t12_no_test_path_source_lookup_or_other_feature_engine():
    tree = ast.parse(Path(d.__file__).read_text())
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(
        "ratio" in name or "causal" in name or "diagnostic_projection" in name or "tests" in name
        for name in imports
    )
    source = Path(d.__file__).read_text()
    assert "/home/" not in source and "/tmp/" not in source
    assert "prepare_asof_request" not in source and "_NativeBuilder" not in source
    assert "sum(" not in source and "eval(" not in source
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"CompletedDependency", "SelectionOutcome", "AsOfSelectionResult"}
        for node in ast.walk(tree)
    )


def test_t12_mapping_and_invocation_are_pure(inputs, completed, monkeypatch):
    body, _, pack, ticks = inputs
    observation = completed[0][0].before_observation

    def denied(*args, **kwargs):
        raise AssertionError("I/O in pure source transport or invocation")

    for obj, name in (
        (builtins, "open"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (subprocess, "check_output"),
        (socket, "socket"),
    ):
        monkeypatch.setattr(obj, name, denied)
    assembly = d.prepare_derived_request(pack, ticks[0], body, observation)
    assert isinstance(assembly, d.WU03RequestAssembly)
    assert d.invoke_derived(assembly).native_result.outcome.value == 140
