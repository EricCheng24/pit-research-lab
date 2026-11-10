"""Frozen PREP02 oracle; real Native owners, portable actual caller observations."""

import base64
import json
import os
import zlib
from dataclasses import FrozenInstanceError, asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

from pit_research_lab.domain import asof_slice
from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.pit_slice import observe_code
from pit_research_lab.mvp.f2 import asof_qualification as aq
from pit_research_lab.mvp.f2 import asof_requests as ar
from pit_research_lab.mvp.f2 import native_requests as nr
from pit_research_lab.mvp.f2.synthetic_temporal import build_pack, build_weekly_requests

DATA = Path(__file__).parent / "data"
ROOT = Path(__file__).parents[3]
CORPUS_BODY = (DATA / "bounded_asof_evidence_v0.1.json").read_bytes()
assert len(CORPUS_BODY) == 1_064_666
assert (
    sha256(CORPUS_BODY).hexdigest()
    == "37e7c10b74d1eab7ff45cc42f571f933a1be769f812d6872402f952704c37524"
)
CORPUS = json.loads(CORPUS_BODY)
ORACLE = CORPUS["hand_authored_oracle"]
assert len(ORACLE) == 49


@pytest.fixture(scope="module")
def inputs():
    base = (DATA / "temporal_qualification_evidence_v0.1.json").read_bytes()
    assert len(base) == 8_803_308 and sha256(base).hexdigest() == ar.S1S2_SHA256
    foundation = json.loads((DATA / "temporal_foundation_v0.1.json").read_bytes())
    pack = build_pack(foundation["input_spec"], foundation["default_seed"])
    return base, pack, build_weekly_requests(pack).requests


@pytest.fixture(scope="module")
def observations():
    before = ar.observe_g03_code()
    assert isinstance(before, ar.G03ObservedCodeInput), before
    records = []
    yield before, records
    after = ar.observe_g03_code()
    assert isinstance(after, ar.G03ObservedCodeInput), after
    assert before == after
    if destination := os.environ.get("G03_EVIDENCE_OUTPUT"):
        path = Path(destination)
        assert path.is_absolute() and not path.is_relative_to(ROOT)
        path.write_text(
            json.dumps(
                {"cases": records, "before": asdict(before.code), "after": asdict(after.code)},
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )


def prepare(inputs, observed, profile="correction"):
    base, pack, ticks = inputs
    cutoff = CORPUS["discovery_source"]["source_views"][profile]["cutoff"]
    tick = next(t for t in ticks if json.loads(t)["cutoff"]["source_text"] == cutoff)
    result = ar.prepare_asof_request(
        pack, tick, ar.G03SourceInput(CORPUS_BODY, base, profile), observed
    )
    assert isinstance(result, ar.G03RequestAssembly), result
    return result


def challenged(request, name):
    """Test-only hostile inputs. Keep the original retained source independent.

    Production prepare never takes a challenge ID, oracle, or caller-selected
    alternate request. Hostile DTO mutations exercise the public Native boundary
    directly; they are never marked as prepared adapter assemblies.
    """
    if name == "none":
        return request
    if name == "missing_descriptor":
        return replace(request, discovery=c.NotEvaluated("S3", "DISCOVERY_EVIDENCE_ABSENT"))
    if name in ("page_missing", "page_missing_repin"):
        evidence = replace(request.discovery, pages=(request.discovery.pages[0][:-1],))
        if name == "page_missing_repin":
            # Explicit accepted hostile whole-descriptor challenge, never repair.
            raw = s.discovery_proposition(evidence)
            evidence = replace(
                evidence,
                raw_bytes=raw,
                origin=replace(
                    evidence.origin, input_digest=c.OriginKnownValue(sha256(raw).hexdigest())
                ),
            )
        return replace(request, discovery=evidence)
    if name == "termination":
        return replace(request, discovery=replace(request.discovery, terminated=False))
    if name == "candidate_missing":
        return replace(request, candidates=request.candidates[:-1])
    if name == "relation_missing":
        return replace(request, relations=())
    if name == "candidate_duplicate":
        return replace(request, candidates=request.candidates + (request.candidates[0],))
    if name == "relation_duplicate":
        return replace(request, relations=request.relations + (request.relations[0],))
    if name == "operation_missing":
        return replace(
            request, coverage=replace(request.coverage, checks=request.coverage.checks[:-1])
        )
    if name == "false_completion":
        check = replace(
            request.coverage.checks[0], evidence_bytes=b"AUTHOR_DECLARED_COMPLETE_WITHIN_PACK"
        )
        return replace(
            request,
            coverage=replace(request.coverage, checks=(check,) + request.coverage.checks[1:]),
        )
    if name in ("forged_binding", "retained_binding_mismatch"):
        relation = request.relations[0]
        notice = relation.notice
        original = notice.request
        binding = original.attempts[0].supplied
        if name == "forged_binding":
            binding = replace(binding, evidence_ref="FORGED-EVIDENCE")
        else:
            binding = replace(
                binding,
                origin=replace(binding.origin, envelope_pointer="/g03/hostile/challenged/support"),
            )
        modified = replace(
            original, attempts=(c.RequestBindingAttempt(original.requested, binding),)
        )
        return replace(
            request,
            relations=(replace(relation, notice=replace(notice, request=modified)),)
            + request.relations[1:],
        )
    if name == "foreign_candidate_descriptor":
        candidate = replace(
            request.candidates[0], historical_lead=c.NotApplicable("S3", "FOREIGN_DESCRIPTOR_ONLY")
        )
        return replace(request, candidates=(candidate,) + request.candidates[1:])
    if name == "reverse_sets":
        evidence = request.discovery
        return replace(
            request,
            candidates=request.candidates[::-1],
            relations=request.relations[::-1],
            coverage=replace(
                request.coverage,
                evaluated_candidate_refs=request.coverage.evaluated_candidate_refs[::-1],
                evaluated_relation_refs=request.coverage.evaluated_relation_refs[::-1],
                checks=request.coverage.checks[::-1],
            ),
            discovery=replace(
                evidence,
                candidates=evidence.candidates[::-1],
                relations=evidence.relations[::-1],
                checks=evidence.checks[::-1],
            ),
        )
    raise AssertionError("Unknown reviewed challenge: " + name)


def summary(result):
    selection = result.selection
    if isinstance(selection, c.BlockingFailure):
        return {
            "state": "BlockingFailure",
            "reason": selection.code,
            "selected_assertion_refs": [],
            "selected_value": None,
        }
    return {
        "state": selection.state,
        "reason": selection.reason,
        "selected_assertion_refs": list(selection.selected_assertion_refs),
        "selected_value": selection.selected_value
        if isinstance(selection.selected_value, int)
        else None,
    }


def diagnostic(assembly):
    attempt = aq.invoke_asof(assembly)
    assert isinstance(attempt, aq.G03NativeAttempt), attempt
    result = aq.finalize_asof_diagnostic(attempt, ar.observe_g03_code())
    assert isinstance(result, aq.G03Diagnostic), result
    assert result.native_result is attempt.native_result
    assert result.source_identity == assembly.source_identity
    return result


@pytest.mark.parametrize("case_id", sorted(ORACLE))
def test_frozen_native_oracle(case_id, inputs, observations, record_property):
    before, records = observations
    case = ORACLE[case_id]
    assembly = prepare(inputs, before, case["profile"])
    request = challenged(assembly.request, case["challenge"])
    if case["challenge"] == "none":
        first = diagnostic(assembly).native_result
        second = diagnostic(assembly).native_result
        mode = "ADAPTER"
    else:
        first = asof_slice.evaluate_asof(request, before.code)
        second = asof_slice.evaluate_asof(request, before.code)
        mode = "PUBLIC_NATIVE_HOSTILE_CONTROL"
    assert first == second
    assert summary(first) == case["expected"]
    assert first.disposition == "INTEGRATED_PROVISIONAL"
    assert first.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert first.source_authentication == "NOT_ESTABLISHED"
    assert first.diagnostic_only is True and first.admission_eligible is False
    entry = {
        "case": case_id,
        "mode": mode,
        "expected": case["expected"],
        "actual": summary(first),
        "reconstruction_ref": first.reconstruction_ref,
        "repeat_equal": first == second,
    }
    if not isinstance(first.selection, c.BlockingFailure):
        entry.update(
            {
                "coverage": asdict(first.selection.coverage),
                "relations": [asdict(x) for x in first.selection.relations],
                "reachability": [asdict(x) for x in first.selection.derived_reachability],
                "audit": [asdict(x) for x in first.selection.research_only_audit],
            }
        )
    else:
        entry["blocking_operation"] = first.selection.attempted_operation
    entry["notices"] = [
        {
            "ref": r.relation.relation_ref,
            "s1": "BlockingFailure"
            if isinstance(r.notice.actual.s1, c.BlockingFailure)
            else r.notice.actual.s1.state,
            "s2": "BlockingFailure"
            if isinstance(r.notice.actual.s2, c.BlockingFailure)
            else r.notice.actual.s2.state,
        }
        for r in first.inputs.relations
    ]
    records.append(entry)
    record_property("g03_case", json.dumps(entry, sort_keys=True))
    if case_id in {"B_correction", "D_chain", "A_t3_no_future_v3"}:
        assert all(n["s1"] == "BOUND" and n["s2"] == "SUPPORTED" for n in entry["notices"])
        assert all(
            r.state == "QUALIFIED" and r.effect == "SUPERSEDES" for r in first.selection.relations
        )
        assert all(r.notice.subject_identity.state == "SAME" for r in first.inputs.relations)
    if case_id == "D_chain":
        assert first.selection.derived_reachability == (
            s.Reachability("W02-ASSERT-SYN-A-DEC-v1", "W02-ASSERT-SYN-A-DEC-v3", ("N12", "N23")),
        )
    if case_id in {"A_early", "A_t3_no_future_v3"}:
        assert all(c.ref != "W02-ASSERT-SYN-A-DEC-v3" for c in first.inputs.candidates)
        assert all(r.relation.relation_ref != "N23" for r in first.inputs.relations)


def test_successful_canonical_reconstruction_and_source_page_order(inputs, observations):
    observed, _ = observations
    assembly = prepare(inputs, observed, "chain")
    chain = diagnostic(assembly).native_result
    reverse = asof_slice.evaluate_asof(challenged(assembly.request, "reverse_sets"), observed.code)
    assert chain == reverse and chain.reconstruction_ref.startswith("B02-RECONSTRUCTION-")
    pages = diagnostic(prepare(inputs, observed, "chain_page_order")).native_result
    assert pages.selection == chain.selection
    assert pages.reconstruction_ref != chain.reconstruction_ref
    assert pages.inputs.discovery.pages == chain.inputs.discovery.pages[::-1]
    with pytest.raises(FrozenInstanceError):
        assembly.request_digest = "changed"


def test_source_replacement_and_cutoff_are_not_authorized(inputs, observations):
    base, pack, ticks = inputs
    observed, _ = observations
    for source in (
        ar.G03SourceInput(CORPUS_BODY + b" ", base, "early"),
        ar.G03SourceInput(CORPUS_BODY, base + b" ", "early"),
    ):
        refusal = ar.prepare_asof_request(pack, ticks[0], source, observed)
        assert isinstance(refusal, ar.G03MappingRefusal)
        assert (refusal.stage, refusal.reason, refusal.native_invocation) == (
            "S01_SOURCE",
            "G03_SOURCE_NOT_ACCEPTED",
            "NOT_RUN",
        )
    refusal = ar.prepare_asof_request(
        pack, ticks[0], ar.G03SourceInput(CORPUS_BODY, base, "correction"), observed
    )
    assert (
        isinstance(refusal, ar.G03MappingRefusal)
        and refusal.reason == "G03_CUTOFF_IDENTITY_MISMATCH"
    )


@pytest.mark.parametrize("replacement", ["raw_pin", "proof_pin", "declared_code_pin"])
def test_unaccepted_source_or_proof_or_declared_pin_replacement(replacement, inputs, observations):
    base, pack, ticks = inputs
    changed = json.loads(CORPUS_BODY)
    changed["status"] = "CALLER_ASSERTED_ADOPTED"
    if replacement == "raw_pin":
        changed["source_notices"]["N12"]["sha256"] = "0" * 64
    elif replacement == "proof_pin":
        changed["source_notices"]["N12"]["native_notice"]["decoded_sha256"] = "0" * 64
    else:
        blob = changed["discovery_source"]["profiles"]["early"]["native_context"]
        context = json.loads(zlib.decompress(base64.b64decode(blob["data"])))
        context["profile"]["code_pins"][0]["sha256"] = "0" * 64
        raw = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
        blob.update(
            data=base64.b64encode(zlib.compress(raw, 9)).decode(),
            decoded_length=len(raw),
            decoded_sha256=sha256(raw).hexdigest(),
        )
    # Even an internally repinned replacement cannot replace the accepted corpus.
    source = ar.G03SourceInput(json.dumps(changed).encode(), base, "early")
    refusal = ar.prepare_asof_request(pack, ticks[0], source, observations[0])
    assert isinstance(refusal, ar.G03MappingRefusal)
    assert refusal.reason == "G03_SOURCE_NOT_ACCEPTED" and refusal.native_invocation == "NOT_RUN"


def test_forged_receipt_and_changed_assembly_never_invoke(inputs, observations):
    observed, _ = observations
    base, pack, ticks = inputs
    fake = ar.G03ObservedCodeInput(observed.code, observed.checkout_root)
    refusal = ar.prepare_asof_request(
        pack, ticks[0], ar.G03SourceInput(CORPUS_BODY, base, "early"), fake
    )
    assert (
        isinstance(refusal, ar.G03MappingRefusal) and refusal.reason == "G03_OBSERVATION_NOT_ISSUED"
    )
    prepared = prepare(inputs, observed)
    with pytest.raises(ValueError, match="NOT_RUN"):
        aq.invoke_asof(replace(prepared, request=challenged(prepared.request, "candidate_missing")))


def test_refusal_priority_and_upstream_identity(inputs):
    base, pack, ticks = inputs
    unavailable = ar.G03ObservationUnavailable("ABSENT")
    source = ar.G03SourceInput(CORPUS_BODY, base, "early")
    bad_pack = replace(pack, payload_sha256="0" * 64)
    first = ar.prepare_asof_request(
        bad_pack, b"bad tick", replace(source, corpus_bytes=b"bad"), unavailable
    )
    assert isinstance(first, ar.G03MappingRefusal) and first.stage == "S01_SOURCE"
    second = ar.prepare_asof_request(bad_pack, b"bad tick", source, unavailable)
    assert isinstance(second, ar.G03MappingRefusal) and second.stage == "S02_PACK"
    assert second.exact_exception_type == "InputError" and second.upstream_code.startswith(
        "PROPOSED_FND_"
    )
    third = ar.prepare_asof_request(pack, b"bad tick", source, unavailable)
    assert isinstance(third, ar.G03MappingRefusal) and third.stage == "S03_TICK"
    fourth = ar.prepare_asof_request(
        pack, ticks[0], replace(source, profile_id="missing"), unavailable
    )
    assert isinstance(fourth, ar.G03MappingRefusal) and fourth.stage == "S04_SOURCE_CONSTRUCTION"
    assert (
        fourth.reason == "G03_SOURCE_CONSTRUCTION_REJECTED"
        and fourth.exact_exception_type == "KeyError"
    )
    fifth = ar.prepare_asof_request(pack, ticks[0], source, unavailable)
    assert isinstance(fifth, ar.G03MappingRefusal) and fifth.stage == "S05_OBSERVATION"
    assert all(x.native_invocation == "NOT_RUN" for x in (first, second, third, fourth, fifth))


def test_pure_preparation_never_observes_or_evaluates(inputs, observations, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("I/O or evaluator in pure preparation")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(ar.subprocess, "check_output", forbidden)
    monkeypatch.setattr(asof_slice, "evaluate_asof", forbidden)
    assert isinstance(prepare(inputs, observations[0]), ar.G03RequestAssembly)


def test_one_real_invocation_and_observation_failure_preserves_result(
    inputs, observations, monkeypatch
):
    prepared = prepare(inputs, observations[0])
    owner = aq.evaluate_asof
    calls = []

    def spy(request, code):
        calls.append((request, code))
        return owner(request, code)

    monkeypatch.setattr(aq, "evaluate_asof", spy)
    attempt = aq.invoke_asof(prepared)
    assert isinstance(attempt, aq.G03NativeAttempt)
    assert calls == [(prepared.request, prepared.before_code)]
    failure = aq.finalize_asof_diagnostic(
        attempt, ar.G03ObservationUnavailable("G03_OBSERVATION_PIN_MISMATCH")
    )
    assert isinstance(failure, aq.G03ObservationFailure)
    assert failure.native_invocation == "RUN" and failure.preserved is attempt
    assert failure.preserved.native_result is attempt.native_result


@pytest.mark.parametrize("error_type", [c.ContractError, RuntimeError])
def test_native_exception_identity_survives_after_observation_failure(
    inputs, observations, monkeypatch, error_type
):
    prepared = prepare(inputs, observations[0])

    def reject(request, code):
        raise error_type("CONTROLLED_NATIVE_EXCEPTION")

    monkeypatch.setattr(aq, "evaluate_asof", reject)
    attempt = aq.invoke_asof(prepared)
    assert isinstance(attempt, aq.G03InvocationFailure)
    assert (attempt.exact_native_exception_type, attempt.code, attempt.native_invocation) == (
        error_type.__name__,
        "CONTROLLED_NATIVE_EXCEPTION",
        "ATTEMPTED",
    )
    assert aq.finalize_asof_diagnostic(attempt, ar.observe_g03_code()) is attempt
    failed = aq.finalize_asof_diagnostic(attempt, ar.G03ObservationUnavailable("DRIFT"))
    assert failed.preserved is attempt and failed.native_invocation == "ATTEMPTED"


def test_actual_observer_rejects_wrong_root_and_foreign_module(monkeypatch, tmp_path):
    monkeypatch.setattr(ar.subprocess, "check_output", lambda *a, **k: str(tmp_path))
    result = ar.observe_g03_code()
    assert (
        isinstance(result, ar.G03ObservationUnavailable)
        and result.reason == "G03_GIT_ROOT_MISMATCH"
    )
    monkeypatch.setattr(ar, "__file__", str(tmp_path / "asof_requests.py"))
    result = ar.observe_g03_code()
    assert (
        isinstance(result, ar.G03ObservationUnavailable)
        and result.reason == "G03_CHECKOUT_LAYOUT_INVALID"
    )


def test_symlink_and_hardlink_refused_without_repo_mutation(tmp_path):
    target = tmp_path / "regular"
    target.write_bytes(b"bounded test")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="SYMLINK"):
        ar._regular_bytes(link)
    hard = tmp_path / "hard"
    os.link(target, hard)
    with pytest.raises(ValueError, match="LINKED_FILE"):
        ar._regular_bytes(hard)


def test_actual_observer_rejects_native_pin_drift(inputs, observations, monkeypatch):
    original = asof_slice.observe_asof_code

    def corrupt(root):
        actual = original(root)
        pins = (
            replace(actual.observed_working_files[0], sha256="0" * 64),
        ) + actual.observed_working_files[1:]
        return replace(actual, observed_working_files=pins)

    monkeypatch.setattr(asof_slice, "observe_asof_code", corrupt)
    after = ar.observe_g03_code()
    assert (
        isinstance(after, ar.G03ObservationUnavailable)
        and after.reason == "G03_OBSERVATION_PIN_MISMATCH"
    )
    attempt = aq.invoke_asof(prepare(inputs, observations[0]))
    failure = aq.finalize_asof_diagnostic(attempt, after)
    assert isinstance(failure, aq.G03ObservationFailure) and failure.native_invocation == "RUN"


def test_valid_after_receipt_with_different_head_withholds_completion(
    inputs, observations, monkeypatch
):
    prepared = prepare(inputs, observations[0])
    attempt = aq.invoke_asof(prepared)
    original = asof_slice.observe_asof_code
    # Controlled observation-metadata drift, not a claimed actual Git HEAD.
    monkeypatch.setattr(
        asof_slice, "observe_asof_code", lambda root: replace(original(root), head="f" * 40)
    )
    after = ar.observe_g03_code()
    assert isinstance(after, ar.G03ObservedCodeInput)
    failed = aq.finalize_asof_diagnostic(attempt, after)
    assert isinstance(failed, aq.G03ObservationFailure)
    assert failed.reason == "G03_CODE_OBSERVATION_CHANGED" and failed.preserved is attempt


def test_status_coexistence_and_unrelated_dirty_fail_closed(observations, monkeypatch):
    code = observe_code(ROOT)
    receipt = nr.CallerObservationReceipt(
        "MVP-F2-WU-02-S1S2-IMPL-01",
        str(ROOT),
        tuple(p[0] for p in nr.NATIVE_CODE_PINS),
        "actual-g03-coexistence",
        "pit_slice.observe_code",
        True,
    )
    actual = nr.ObservedCodeInput(code, receipt)
    assert nr._observation_reason(actual) is None
    # Controlled synthetic negative status only; never logged as observed disk.
    changed = replace(code, worktree_status="?? unrelated.py")
    assert (
        nr._observation_reason(nr.ObservedCodeInput(changed, receipt))
        == nr.W02AdapterReason.OBSERVATION_SCOPE_INVALID
    )
    assert not ar._status_valid("?? unrelated.py")
    assert not ar._status_valid(" M src/pit_research_lab/domain/selection.py")
    assert not ar._status_valid("R  old -> src/pit_research_lab/mvp/f2/asof_requests.py")
    owner = asof_slice.observe_asof_code
    monkeypatch.setattr(
        asof_slice,
        "observe_asof_code",
        lambda root: replace(owner(root), worktree_status="?? unrelated.py"),
    )
    after = ar.observe_g03_code()
    assert (
        isinstance(after, ar.G03ObservationUnavailable)
        and after.reason == "G03_OBSERVATION_SCOPE_INVALID"
    )
    assert (
        nr._observation_reason(nr.ObservedCodeInput(observations[0].code, receipt))
        == nr.W02AdapterReason.OBSERVATION_PIN_MISMATCH
    )


def test_no_bounded_absence_without_source_universe():
    assert "NOT_CONSTRUCTIBLE" in CORPUS["evidence_limits"]["bounded_absence"]
    assert not any(v["expected"]["state"] == "NO_QUALIFIED_CLAIM" for v in ORACLE.values())
