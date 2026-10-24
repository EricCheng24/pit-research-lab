"""A03 construction counterexamples, never official Golden executions."""

import ast
import json
import socket
import subprocess
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest
from a03_inputs import invocation, provider, revision, seed, source
from wu01_inputs import AdaptedS1Input, InvocationSelector, materialize_input

from pit_research_lab.domain.asof_slice import evaluate_asof, observe_asof_code
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    NotApplicable,
    NotEvaluated,
    OriginKnownValue,
    Visibility,
)
from pit_research_lab.domain.selection import CandidateSource, SelectionOutcome, select_asof

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_asof_code(ROOT)


def run(code, candidates=(), relations=(), **kwargs):
    return evaluate_asof(invocation(code, candidates, relations, **kwargs), code)


def isolated(result):
    assert result.disposition == "INTEGRATED_PROVISIONAL"
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.admission_eligible is False and result.diagnostic_only is True
    assert asdict(result)["admission_eligible"] is False
    for c in result.inputs.candidates:
        assert c.actual.trust == "NOT_TRUSTED_PIT_EVIDENCE"


def family(code):
    old = source(code, "OLD", 300)
    new = source(code, "NEW", 310, "2025-07-10T14:00:00+08:00")
    rel = revision(code, old, new)
    return old, new, rel


def test_a03_t01_single_supported_issuer_selection(code):
    c = source(code, "ONE")
    result = run(code, (c,))
    assert result.selection.state == "SELECTED"
    assert result.selection.selected_assertion_refs == ("A-ONE",)
    assert result.selection.selected_value == 300
    candidate = result.inputs.candidates[0]
    assert candidate.actual.s1.state == "BOUND" and candidate.actual.s2.state == "SUPPORTED"
    assert candidate.subject_identity.state == "SAME"
    assert result.selection.coverage.state == "SUFFICIENT"
    isolated(result)


@pytest.mark.parametrize(
    "cutoff,selected,value,relation_state",
    [
        ("2025-07-07T00:00:00+08:00", "A-OLD", 300, "EXCLUDED"),
        ("2025-07-10T14:00:00+08:00", "A-OLD", 300, "EXCLUDED"),
        ("2025-07-14T00:00:00+08:00", "A-NEW", 310, "QUALIFIED"),
    ],
)
def test_a03_t02_t03_two_cutoff_independent_revision(code, cutoff, selected, value, relation_state):
    old, new, rel = family(code)
    result = run(code, (old, new), (rel,), cutoff=cutoff)
    assert result.selection.state == "SELECTED"
    assert result.selection.selected_assertion_refs == (selected,)
    assert result.selection.selected_value == value
    assert result.selection.relations[0].state == relation_state
    assert result.inputs.relations[0].notice.actual.request.content.raw_sha256 not in {
        c.actual.request.content.raw_sha256 for c in result.inputs.candidates
    }
    old_result = next(c for c in result.inputs.candidates if c.ref == "A-OLD")
    assert old_result.actual.s2.state == "SUPPORTED"  # Publication is never erased.
    isolated(result)


def test_a03_t04_relation_does_not_require_old_publication(code):
    old = source(code, "OLD", unbound=True, historical=True)
    new = source(code, "NEW", 310, "2025-07-10T14:00:00+08:00")
    rel = revision(code, old, new)
    early = run(code, (old, new), (rel,))
    assert early.selection.state == "UNRESOLVED"
    late = run(code, (old, new), (rel,), cutoff="2025-07-14T00:00:00+08:00")
    assert late.selection.state == "SELECTED" and late.selection.selected_assertion_refs == (
        "A-NEW",
    )
    old_actual = next(c.actual for c in late.inputs.candidates if c.ref == "A-OLD")
    assert old_actual.s1.state == old_actual.s2.state == "UNRESOLVED"
    assert late.selection.relations[0].state == "QUALIFIED"
    isolated(late)


def test_a03_t05_conflicting_qualified_issuers_not_latest_wins(code):
    result = run(
        code, (source(code, "FIRST", 300), source(code, "LAST", 315, "2025-07-05T12:00:00+08:00"))
    )
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.reason == "MATERIAL_CANDIDATE_UNRESOLVED"
    assert not result.selection.selected_assertion_refs


def test_a03_t06_current_provider_discrepancy_is_audit_only(code):
    result = run(code, (source(code, "ISSUER"), provider(code)))
    assert result.selection.state == "SELECTED" and result.selection.selected_assertion_refs == (
        "A-ISSUER",
    )
    assessment = next(c for c in result.selection.candidates if c.candidate_ref == "OBS-PROVIDER")
    assert assessment.qualification == "AUDIT_ONLY" and not assessment.material_unknown
    actual = next(c.actual for c in result.inputs.candidates if c.ref == "OBS-PROVIDER")
    assert actual.s1.state == "UNRESOLVED" and actual.s1.reason == "ATTRIBUTION_UNRESOLVED"
    assert any(a.reason == "PROVIDER_DISCREPANCY" for a in result.selection.research_only_audit)
    isolated(result)


@pytest.mark.parametrize("historical,state", [(False, "SELECTED"), (True, "UNRESOLVED")])
def test_a03_t07_grounded_unknown_only(code, historical, state):
    lead = source(code, "LEAD", 315, unknown=True, historical=historical)
    result = run(code, (source(code, "ONE"), lead))
    assert result.selection.state == state
    assert (
        next(c for c in result.inputs.candidates if c.ref == "A-LEAD").actual.s2.state
        == "UNRESOLVED"
    )
    isolated(result)


@pytest.mark.parametrize(
    "target,state", [("CONTENT_VALUE", "SELECTED"), ("ATTRIBUTED_ASSERTION", "UNRESOLVED")]
)
def test_materiality_is_relative_to_target(code, target, state):
    result = run(
        code,
        (source(code, "ONE"), source(code, "LEAD", 300, unknown=True, historical=True)),
        target=target,
    )
    assert result.selection.state == state


@pytest.mark.parametrize("empty", [False, True])
def test_a03_t08_sufficient_bounded_no_qualified_claim(code, empty):
    candidates = () if empty else (source(code, "LATE", published="2025-07-10T14:00:00+08:00"),)
    result = run(code, candidates)
    assert result.selection.state == "NO_QUALIFIED_CLAIM"
    assert result.selection.reason == "NO_QUALIFIED_WITHIN_SCOPE"
    assert result.selection.coverage.state == "SUFFICIENT"
    if not empty:
        assert result.selection.candidates[0].qualification == "EXCLUDED"
        assert result.selection.candidates[0].reason == "PUBLICATION_NOT_PRE_CUTOFF"
    isolated(result)


@pytest.mark.parametrize("empty", [False, True])
def test_a03_t09_missing_checks_not_no_claim(code, empty):
    candidates = () if empty else (source(code, "LATE", published="2025-07-10T14:00:00+08:00"),)
    result = run(code, candidates, complete=False)
    assert (
        result.selection.state == "UNRESOLVED"
        and result.selection.reason == "COVERAGE_INSUFFICIENT"
    )
    assert result.selection.coverage.missing_checks


@pytest.mark.parametrize(
    "target,state", [("CONTENT_VALUE", "SELECTED"), ("ATTRIBUTED_ASSERTION", "UNRESOLVED")]
)
def test_a03_t10_equal_values_preserve_distinct_assertions(code, target, state):
    result = run(code, (source(code, "ONE"), source(code, "PEER")), target=target)
    assert result.selection.state == state
    if state == "SELECTED":
        assert result.selection.selected_assertion_refs == ("A-ONE", "A-PEER")
        assert result.selection.selected_value == 300
    else:
        assert result.selection.reason == "ATTRIBUTION_UNRESOLVED"
    assert len({c.actual.request.content.raw_sha256 for c in result.inputs.candidates}) == 2
    isolated(result)


@pytest.mark.parametrize(
    "fault",
    [
        "future",
        "unknown_time",
        "missing",
        "foreign_version",
        "foreign_target",
        "wrong_notice",
        "borrowed",
        "source_scope",
    ],
)
def test_a03_t11_unqualified_or_bad_relation_never_replaces(code, fault):
    old, new, rel = family(code)
    if fault == "unknown_time":
        notice = source(
            code,
            "CORRECTION",
            1,
            metric=rel.notice.subject.metric.value,
            unit="relation_declaration",
            unknown=True,
        )
        rel = replace(
            rel, notice=notice, relation=replace(rel.relation, origin=notice.subject.metric.origin)
        )
    elif fault == "missing":
        rel = replace(rel, notice=NotEvaluated("S3", "NO_NOTICE_SUPPLIED"))
    elif fault in {"foreign_version", "foreign_target"}:
        key = "new_version_ref" if fault == "foreign_version" else "new_assertion_ref"
        rel = revision(code, old, new, **{key: "FOREIGN"})
    elif fault == "wrong_notice":
        rel = replace(rel, relation=replace(rel.relation, notice_assertion_ref="FOREIGN"))
    elif fault == "borrowed":
        rel = replace(rel, notice=new)
    elif fault == "source_scope":
        rel = replace(rel, relation=replace(rel.relation, origin=old.subject.metric.origin))
    result = run(
        code,
        (old, new),
        (rel,),
        cutoff="2025-07-14T00:00:00+08:00" if fault != "future" else "2025-07-07T00:00:00+08:00",
    )
    if fault == "future":
        assert (
            result.selection.state == "SELECTED"
            and result.selection.selected_assertion_refs == ("A-OLD",)
        )
    else:
        assert (
            isinstance(result.selection, BlockingFailure) or result.selection.state == "UNRESOLVED"
        )
    isolated(result)


def test_a03_t12_correction_of_x_does_not_supersede_y(code):
    old, new, _ = family(code)
    rel = revision(
        code,
        old,
        new,
        subject_ref="FIELD-X",
        published="2025-07-05T12:00:00+08:00",
        old_assertion_ref="A-X-OLD",
        old_version_ref="CV-X-OLD",
        new_assertion_ref="A-X-NEW",
        new_version_ref="CV-X-NEW",
    )
    result = run(code, (old, new), (rel,))
    assert result.selection.state == "SELECTED" and result.selection.selected_assertion_refs == (
        "A-OLD",
    )
    assert result.selection.relations[0].reason == "RELATION_SCOPE_MISMATCH"
    assert all(a.applicability != "SUPERSEDED" for a in result.selection.candidates)


@pytest.mark.parametrize("kind", ["WITHDRAWS", "REISSUES", "RESTATEMENT"])
def test_a03_t13_unsupported_kind_no_rollback(code, kind):
    old, new, _ = family(code)
    rel = revision(
        code,
        old,
        new,
        kind=kind,
        new_assertion_ref=NotApplicable("S3", "NO_SUCCESSOR"),
        new_version_ref=NotApplicable("S3", "NO_SUCCESSOR"),
    )
    result = run(code, (old, new), (rel,), cutoff="2025-07-14T00:00:00+08:00")
    assert result.selection.state == "UNRESOLVED" and not result.selection.selected_assertion_refs
    assert result.selection.relations[0].reason == "UNSUPPORTED_RELATION_KIND_NO_ROLLBACK"


def test_unsupported_chain_and_cycle_no_direct_edge_invention(code):
    old = source(code, "V0", 100)
    middle = source(code, "V1", 110)
    last = source(code, "V2", 100)
    relations = (revision(code, old, middle, tag="R01"), revision(code, middle, last, tag="R12"))
    result = run(code, (old, middle, last), relations, cutoff="2025-07-14T00:00:00+08:00")
    assert (
        result.selection.state == "UNRESOLVED"
        and result.selection.reason == "UNSUPPORTED_RELATION_GRAPH"
    )
    assert {r.relation_ref for r in result.selection.relations} == {"REL-R01", "REL-R12"}
    assert len(result.inputs.candidates) == 3
    cycle = run(
        code,
        (old, middle),
        (relations[0], revision(code, middle, old, tag="R10")),
        cutoff="2025-07-14T00:00:00+08:00",
    )
    assert cycle.selection.reason == "UNSUPPORTED_RELATION_GRAPH"


def test_a03_t14_new_evidence_new_context_old_replay_preserved(code):
    old = source(code, "OLD")
    early_request = invocation(code, (old,))
    original = evaluate_asof(early_request, code)
    correction = source(code, "EARLY-NEW", 305, "2025-07-05T12:00:00+08:00")
    relation = revision(code, old, correction, published="2025-07-05T12:00:00+08:00")
    changed = run(code, (old, correction), (relation,), snapshot="E-A03-2")
    assert original.selection.selected_value == 300 and changed.selection.selected_value == 305
    assert original.inputs.context.evidence_set_ref != changed.inputs.context.evidence_set_ref
    assert evaluate_asof(early_request, code) == original
    isolated(changed)


def test_a03_t15_permutation_lexical_and_provider_count(code):
    one = source(code, "ZZZ", 300)
    other = source(code, "AAA", 315)
    a = run(code, (one, other))
    b = run(code, (other, one))
    assert a == b and a.selection.state == "UNRESOLVED"
    assert tuple(e.ref for e in a.selection.research_only_audit) == tuple(
        sorted(e.ref for e in a.selection.research_only_audit)
    )
    single = run(code, (one, provider(code, "P1")))
    many = run(code, (provider(code, "P2"), one, provider(code, "P1")))
    assert (
        single.selection.selected_assertion_refs
        == many.selection.selected_assertion_refs
        == ("A-ZZZ",)
    )
    assert len(many.selection.research_only_audit) > len(single.selection.research_only_audit)


def test_a03_t16_mode_separation(code):
    c = source(code, "ONE")
    public = run(code, (c,))
    observed = run(code, (c,), mode="prospective_observed")
    assert public.selection.state == "SELECTED"
    assert observed.inputs.candidates[0].actual.s2.state == "NOT_ADMISSIBLE"
    assert observed.selection.state == "NO_QUALIFIED_CLAIM"
    isolated(observed)


def test_a03_t17_sc01_remains_open_and_untrusted(code):
    base, anchor = seed(code)
    bundle = materialize_input(
        "A02-C01",
        InvocationSelector("CHECK_BINDING", ("A-JUN-01",), "SUP-JUN1-PUB", (Visibility.ACTIVE,)),
        base.context.profile,
    )
    assert isinstance(bundle, AdaptedS1Input)
    binding = bundle.request.attempts[0].supplied
    origin = replace(binding.target.origin, object_id=OriginKnownValue("EVID-ORD1-TIME"))
    binding = replace(
        binding, evidence_ref="EVID-ORD1-TIME", target=replace(binding.target, origin=origin)
    )
    c = CandidateSource(
        anchor,
        replace(bundle.request, attempts=(replace(bundle.request.attempts[0], supplied=binding),)),
        NotApplicable("S3", "NO_HISTORICAL_CLUE"),
    )
    result = run(code, (c,))
    assert result.inputs.candidates[0].actual.s1.state == "BOUND"
    assert result.inputs.candidates[0].actual.s2.state == "SUPPORTED"
    assert result.selection.state == "SELECTED"
    isolated(result)


def test_a03_t18_no_trust_flags_or_agent_export(code):
    result = run(code, (source(code, "ONE"),))
    for key in ("admission_eligible", "trust", "diagnostic_only", "source_authentication"):
        with pytest.raises(ValueError, match="init=False"):
            replace(result, **{key: True})
    assert not hasattr(result, "to_agent_observation") and not hasattr(
        result.selection, "to_agent_observation"
    )
    isolated(result)


def test_a03_t19_replay_code_pins_and_no_io_during_evaluate(code, monkeypatch):
    old, new, rel = family(code)
    request = invocation(code, (old, new), (rel,))
    a = evaluate_asof(request, code)

    def deny(*args, **kwargs):
        raise AssertionError("resource access from pure evaluation")

    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", deny)
        m.setattr(subprocess, "check_output", deny)
        m.setattr(socket, "socket", deny)
        assert evaluate_asof(request, code) == a
    assert observe_asof_code(ROOT) == code
    for pin, size in zip(code.observed_working_files, code.byte_lengths, strict=True):
        raw = (ROOT / pin.path).read_bytes()
        assert sha256(raw).hexdigest() == pin.sha256 and len(raw) == size
    for filename in ("selection.py", "asof_slice.py"):
        tree = ast.parse((ROOT / "src/pit_research_lab/domain" / filename).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(
            "wu0" in name or "oracle" in name or "acceptance" in name for name in imports
        )
    isolated(a)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "version",
        "subject",
        "context",
        "cutoff",
        "coverage_context",
        "coverage_universe",
        "outcome",
        "failed_check",
        "unexplained_check",
        "policy_checks",
    ],
)
def test_a03_t20_structural_errors_are_not_missingness(code, fault):
    c = source(code, "ONE")
    request = invocation(code, (c,))
    if fault == "duplicate":
        request = replace(request, candidates=(c, c))
    elif fault == "version":
        second = source(code, "TWO")
        second = replace(
            second,
            request=replace(
                second.request,
                content=replace(
                    second.request.content,
                    content_version_ref=c.request.content.content_version_ref,
                ),
            ),
        )
        request = replace(request, candidates=(c, second))
    elif fault == "subject":
        foreign = replace(c.subject, subject_ref="FOREIGN")
        request = replace(request, subject=foreign)
        request = replace(request, policy=replace(request.policy, subject_ref="FOREIGN"))
        # Same semantic dimensions with a different caller ID are not a different Subject;
        # a known metric difference, rather than the ID spelling, must fail.
        foreign = replace(foreign, metric=replace(foreign.metric, value="FOREIGN_METRIC"))
        request = replace(request, subject=foreign)
    elif fault in {"context", "cutoff", "outcome"}:
        result = evaluate_asof(request, code)
        candidate = result.inputs.candidates[0]
        if fault == "outcome":
            actual = replace(
                candidate.actual, s1=replace(candidate.actual.s1, content_refs=("FOREIGN",))
            )
        else:
            context = (
                replace(candidate.actual.context, context_ref="FOREIGN")
                if fault == "context"
                else replace(
                    candidate.actual.context,
                    information_cutoff=replace(
                        candidate.actual.context.information_cutoff,
                        source_text="2025-07-14T00:00:00+08:00",
                    ),
                )
            )
            actual = replace(candidate.actual, context=context)
        bundle = replace(result.inputs, candidates=(replace(candidate, actual=actual),))
        assert isinstance(select_asof(bundle), BlockingFailure)
        return
    elif fault == "coverage_context":
        request = replace(request, coverage=replace(request.coverage, context_ref="FOREIGN"))
    elif fault == "coverage_universe":
        request = replace(request, coverage=replace(request.coverage, evaluated_candidate_refs=()))
    elif fault == "policy_checks":
        request = replace(request, policy=replace(request.policy, required_checks=()))
    else:
        check = request.coverage.checks[0]
        check = (
            replace(check, status="FAILED")
            if fault == "failed_check"
            else replace(check, evidence_bytes=b"tampered")
        )
        request = replace(
            request,
            coverage=replace(request.coverage, checks=(check, *request.coverage.checks[1:])),
        )
    result = evaluate_asof(request, code)
    assert isinstance(result.selection, BlockingFailure)
    if fault == "failed_check":
        assert result.selection.category == "OPERATIONAL_ERROR"
    isolated(result)


def test_compact_two_cutoff_demonstration(code):
    old, new, rel = family(code)
    cases = [
        ("before correction", invocation(code, (old, new), (rel,))),
        (
            "after correction",
            invocation(code, (old, new), (rel,), cutoff="2025-07-14T00:00:00+08:00"),
        ),
        ("unresolved conflict", invocation(code, (old, source(code, "CONFLICT", 315)))),
        ("bounded absence", invocation(code, ())),
    ]
    rows = []
    for label, request in cases:
        result = evaluate_asof(request, code)
        assert isinstance(result.selection, SelectionOutcome)
        rows.append(
            {
                "scenario": label,
                "context": request.context.context_ref,
                "cutoff": request.context.information_cutoff.source_text,
                "mode": request.context.mode,
                "policy": request.policy.policy_ref,
                "coverage": asdict(result.selection.coverage),
                "candidates": [
                    {
                        "assertion": c.ref,
                        "content": c.actual.request.content.content_version_ref,
                        "raw_sha256": c.actual.request.content.raw_sha256,
                        "s1": [c.actual.s1.state, c.actual.s1.reason],
                        "s2": [c.actual.s2.state, c.actual.s2.reason],
                        "paths": [asdict(p) for p in c.actual.s1.provenance.accepted_paths],
                    }
                    for c in result.inputs.candidates
                ],
                "notices": [
                    {
                        "assertion": r.notice.ref,
                        "content": r.notice.actual.request.content.content_version_ref,
                        "s1": r.notice.actual.s1.state,
                        "s2": r.notice.actual.s2.state,
                    }
                    for r in result.inputs.relations
                ],
                "relations": [asdict(r) for r in result.selection.relations],
                "s3": result.selection.state,
                "reason": result.selection.reason,
                "selected": result.selection.selected_assertion_refs,
                "value": result.selection.selected_value
                if isinstance(result.selection.selected_value, int)
                else None,
                "trust": result.trust,
                "disposition": result.disposition,
                "admission_eligible": result.admission_eligible,
                "source_authentication": result.source_authentication,
                "code": asdict(code),
            }
        )
        isolated(result)
    print(json.dumps(rows, indent=2, sort_keys=True))


@pytest.mark.parametrize("kind", ["CORRECTS", "REPLACES"])
def test_direct_kinds_qualified_independently(code, kind):
    old, new, _ = family(code)
    rel = revision(code, old, new, kind=kind)
    result = run(code, (old, new), (rel,), cutoff="2025-07-14T00:00:00+08:00")
    assert result.selection.state == "SELECTED"
    assert result.selection.selected_assertion_refs == ("A-NEW",)
    isolated(result)


def test_future_notice_cannot_resolve_an_already_public_conflict(code):
    old = source(code, "OLD")
    new = source(code, "NEW", 310, "2025-07-04T14:00:00+08:00")
    rel = revision(code, old, new)
    result = run(code, (old, new), (rel,))
    assert result.selection.relations[0].state == "EXCLUDED"
    assert result.selection.state == "UNRESOLVED"
    assert all(a.applicability != "SUPERSEDED" for a in result.selection.candidates)


def test_relation_cannot_make_unqualified_successor_selectable(code):
    old = source(code, "OLD")
    new = source(code, "NEW", 310, unknown=True)
    rel = revision(code, old, new)
    result = run(code, (old, new), (rel,), cutoff="2025-07-14T00:00:00+08:00")
    assert result.selection.relations[0].state == "QUALIFIED"
    assert result.selection.state == "UNRESOLVED"
    assert not result.selection.selected_assertion_refs


@pytest.mark.parametrize("fault", ["stale_context", "wrong_sources", "wrong_reference"])
def test_coverage_source_bytes_must_match_scope_and_context(code, fault):
    request = invocation(code, (source(code, "ONE"),))
    check = request.coverage.checks[0]
    raw = json.loads(check.evidence_bytes)
    if fault == "stale_context":
        raw["context_ref"] = "OLD-CONTEXT"
    elif fault == "wrong_sources":
        raw["source_refs"] = ["OTHER-SOURCE"]
    else:
        check = replace(check, evidence_refs=("OTHER-RECORD",))
    data = json.dumps(raw, sort_keys=True).encode()
    check = replace(
        check,
        evidence_bytes=data,
        origin=replace(check.origin, input_digest=OriginKnownValue(sha256(data).hexdigest())),
    )
    request = replace(
        request, coverage=replace(request.coverage, checks=(check, *request.coverage.checks[1:]))
    )
    result = evaluate_asof(request, code)
    assert isinstance(result.selection, BlockingFailure)
    assert result.selection.code == "COVERAGE_EVIDENCE_SCOPE_MISMATCH"


def test_conflicting_immutable_proof_identity_is_structural(code):
    old, new, _ = family(code)
    old_proof = old.request.attempts[0].supplied.proof_candidate
    attempt = new.request.attempts[0]
    proof = attempt.supplied.proof_candidate
    origin = replace(
        proof.origin,
        envelope_pointer=proof.origin.envelope_pointer.replace(
            proof.proof_ref, old_proof.proof_ref
        ),
        object_id=OriginKnownValue(old_proof.proof_ref),
    )
    raw = dict(proof.raw_descriptor)
    raw["proof_id"] = old_proof.proof_ref
    proof = replace(
        proof,
        proof_ref=old_proof.proof_ref,
        origin=origin,
        timestamp=replace(proof.timestamp, origin=origin),
        raw_descriptor=tuple(sorted(raw.items())),
    )
    members = tuple(
        replace(m, object_ref=old_proof.proof_ref) if m.role == "time_proofs" else m
        for m in new.request.scope.input_members
    )
    request = replace(
        new.request,
        attempts=(replace(attempt, supplied=replace(attempt.supplied, proof_candidate=proof)),),
        scope=replace(new.request.scope, input_members=members),
    )
    new = replace(new, request=request)
    result = run(code, (old, new), cutoff="2025-07-14T00:00:00+08:00")
    assert all(
        c.actual.s1.state == "BOUND" and c.actual.s2.state == "SUPPORTED"
        for c in result.inputs.candidates
    )
    assert isinstance(result.selection, BlockingFailure)
    assert result.selection.code == "CONTRADICTORY_PROOF_IDENTITY"


def test_unknown_relation_endpoint_remains_unresolved(code):
    old, new, _ = family(code)
    rel = revision(
        code,
        old,
        new,
        new_assertion_ref=NotApplicable("S3", "UNKNOWN_TARGET"),
        new_version_ref=NotApplicable("S3", "UNKNOWN_TARGET"),
    )
    result = run(code, (old, new), (rel,), cutoff="2025-07-14T00:00:00+08:00")
    assert result.selection.state == "UNRESOLVED"
    assert result.selection.relations[0].reason == "RELATION_TARGET_UNKNOWN"


def test_future_notice_cannot_hide_structurally_contradictory_target(code):
    old, new, _ = family(code)
    rel = revision(code, old, new, new_version_ref="WRONG-VERSION")
    result = run(code, (old, new), (rel,))
    assert isinstance(result.selection, BlockingFailure)
    assert result.selection.code == "RELATION_VERSION_MISMATCH"
    isolated(result)


@pytest.mark.parametrize("layer", ["S1", "S2"])
def test_blocking_failures_are_preserved_separately_from_no_claim(code, layer):
    candidate = source(code, "ONE")
    request = candidate.request
    if layer == "S1":
        request = replace(
            request, requested=replace(request.requested, fragment_selector="/statements/999")
        )
    else:
        attempt = request.attempts[0]
        proof = attempt.supplied.proof_candidate
        stamp = replace(proof.timestamp, source_text="2025-07-03T14:00:00.999999+08:00")
        raw = dict(proof.raw_descriptor)
        raw["timestamp"] = stamp.source_text
        proof = replace(proof, timestamp=stamp, raw_descriptor=tuple(sorted(raw.items())))
        request = replace(
            request,
            attempts=(replace(attempt, supplied=replace(attempt.supplied, proof_candidate=proof)),),
        )
    result = run(code, (replace(candidate, request=request),))
    actual = result.inputs.candidates[0].actual
    expected = actual.s1 if layer == "S1" else actual.s2
    assert isinstance(expected, BlockingFailure) and result.selection == expected
    isolated(result)
