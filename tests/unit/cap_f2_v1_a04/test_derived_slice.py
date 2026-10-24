"""A04 engineering counterexamples; no official Golden execution or admission."""

import ast
import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest
from a03_inputs import revision
from a04_inputs import family, month_source, request, rewrite

from pit_research_lab.domain.asof_slice import evaluate_asof
from pit_research_lab.domain.contracts import BlockingFailure, NotEvaluated, OriginKnownValue
from pit_research_lab.domain.derivation import (
    S4_CODE_PATHS,
    DependencySlot,
    _evaluate_completed,
)
from pit_research_lab.domain.derived_slice import evaluate_derived, observe_derived_code
from pit_research_lab.domain.selection import ResearchAuditEntry

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_derived_code(ROOT)


def isolated(result):
    assert result.disposition == "INTEGRATED_PROVISIONAL"
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.admission_eligible is False and result.diagnostic_only is True
    assert not hasattr(result, "to_agent_observation")


def replace_slot(slots, index, new_request):
    return tuple(replace(s, request=new_request) if i == index else s for i, s in enumerate(slots))


def test_real_four_owner_sum_and_full_lineage(code):
    spec, slots = family(code)
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == "VALUE_AVAILABLE" and result.outcome.value == 56_799_290
    assert result.origin_kind == "DERIVED"
    assert result.realization_ref != spec.feature_ref
    for index, dep in enumerate(result.dependencies):
        assert dep.actual == evaluate_asof(slots[index].request, code)
        assert dep.actual.selection.state == "SELECTED"
        actual = dep.actual.inputs.candidates[0].actual
        assert actual.s1.state == "BOUND" and actual.s2.state == "SUPPORTED"
        content = actual.request.content
        assert sha256(content.raw_bytes).hexdigest() == content.raw_sha256
        line = result.outcome.lineage[index]
        assert line.raw_sha256s == (content.raw_sha256,)
        assert line.content_version_refs == (content.content_version_ref,)
        assert line.representation_refs == (content.representation_ref,)
        assert line.assertion_refs == (actual.request.assertion.assertion_ref,)
        assert (
            actual.request.attempts[0].supplied.proof_candidate.content_version_ref
            == content.content_version_ref
        )
        assert line.unit == "NTD_thousands"
    assert len({s.request.context.context_ref for s in slots}) == 3
    assert len({s.request.policy.policy_ref for s in slots}) == 3
    isolated(result)


def test_genuine_notice_before_after_and_unchanged_earlier_replay(code):
    spec, early = family(code, revised=True)
    _, late = family(code, revised=True, cutoff="2025-07-14T00:00:00+08:00")
    a, b = evaluate_derived(spec, early, code), evaluate_derived(spec, late, code)
    assert (a.outcome.value, b.outcome.value) == (56_799_290, 56_799_300)
    assert a.dependencies[2].actual.selection.relations[0].state == "EXCLUDED"
    assert b.dependencies[2].actual.selection.relations[0].state == "QUALIFIED"
    notice = b.dependencies[2].actual.inputs.relations[0].notice.actual
    assert notice.s1.state == "BOUND" and notice.s2.state == "SUPPORTED"
    assert a.outcome.lineage[2].assertion_refs == ("A-2025-06",)
    assert b.outcome.lineage[2].assertion_refs == ("A-CORRECTED",)
    assert a.outcome.lineage[:2] == b.outcome.lineage[:2]
    assert a == evaluate_derived(spec, early, code)
    assert a.realization_ref != b.realization_ref


@pytest.mark.parametrize(
    "kind,expected", [("conflict", "UNRESOLVED"), ("absent", "NOT_COMPUTABLE")]
)
def test_uncertainty_not_normal_absence_or_zero(code, kind, expected):
    spec, slots = family(code, third=kind)
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == expected and isinstance(result.outcome.value, NotEvaluated)
    assert result.research_only_audit[2].upstream == result.dependencies[2].actual.selection
    if kind == "conflict":
        assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)
    else:
        assert json.loads(result.diagnostic_preview_bytes)["value"] is None
    isolated(result)


def test_empty_with_incomplete_coverage_is_unresolved(code):
    spec, slots = family(code, third="absent", complete=False)
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == "UNRESOLVED"
    assert result.dependencies[2].actual.selection.state == "UNRESOLVED"


def test_failed_coverage_preserves_exact_operational_faults(code):
    spec, slots = family(code, check_status="FAILED")
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == "OPERATIONAL_ERROR"
    assert result.outcome.upstream_failures == tuple(
        d.actual.selection for d in result.dependencies
    )
    assert all(f.code == "REQUIRED_OPERATION_FAILED" for f in result.outcome.upstream_failures)
    assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)


@pytest.mark.parametrize("owner", ["S1", "S2"])
def test_owner_blocking_fault_not_fabricated_missing(code, owner):
    spec, slots = family(code)
    s = slots[2].request.candidates[0]
    r = s.request
    if owner == "S1":
        r = replace(r, requested=replace(r.requested, fragment_selector="/statements/999"))
    else:
        attempt = r.attempts[0]
        proof = attempt.supplied.proof_candidate
        stamp = replace(proof.timestamp, source_text="2025-07-03T14:00:00.999999+08:00")
        descriptor = dict(proof.raw_descriptor)
        descriptor["timestamp"] = stamp.source_text
        proof = replace(proof, timestamp=stamp, raw_descriptor=tuple(sorted(descriptor.items())))
        r = replace(
            r,
            attempts=(replace(attempt, supplied=replace(attempt.supplied, proof_candidate=proof)),),
        )
    s = replace(s, request=r)
    req = request(code, s, (s,))
    result = evaluate_derived(spec, replace_slot(slots, 2, req), code)
    actual = result.dependencies[2].actual.inputs.candidates[0].actual
    fault = actual.s1 if owner == "S1" else actual.s2
    assert isinstance(fault, BlockingFailure)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert result.outcome.upstream_failures == (fault,)


@pytest.mark.parametrize(
    "field,value",
    [
        ("period_kind", "INSTANT"),
        ("basis_ref", "INDIVIDUAL-BASIS"),
        ("reporting_scope", "individual"),
        ("canonical_unit", "NTD"),
        ("currency", "USD"),
        ("economic_entity_ref", "SYN-B"),
        ("metric", "revenue_stock"),
        ("period_start", date(2025, 1, 1)),
    ],
)
def test_no_numeric_only_compatibility(code, field, value):
    spec, slots = family(code)
    s = rewrite(slots[1].request.candidates[0], subject_changes={field: value})
    req = request(code, s, (s,))
    changed = list(slots)
    changed[1] = DependencySlot("M2", s.subject, req)
    result = evaluate_derived(spec, tuple(changed), code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert isinstance(result.diagnostic_preview_bytes, NotEvaluated)


@pytest.mark.parametrize("year,quarter", [(2024, 1), (2025, 1), (2024, 4)])
def test_complete_calendar_quarters_leap_and_year_end(code, year, quarter):
    spec, slots = family(code, year=year, quarter=quarter)
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == "VALUE_AVAILABLE"
    if quarter == 1:
        assert result.outcome.lineage[1].period[1] == date(year, 2, 29 if year == 2024 else 28)
    else:
        assert result.outcome.lineage[2].period[1] == date(year, 12, 31)


@pytest.mark.parametrize(
    "fault",
    ["gap", "duplicate_month", "cross_year", "missing_slot", "duplicate_slot", "self_reference"],
)
def test_dependency_period_and_graph_contract(code, fault):
    spec, slots = family(code)
    if fault == "missing_slot":
        slots = slots[:2]
    elif fault == "duplicate_slot":
        slots = (*slots[:2], replace(slots[2], slot_ref="M2"))
    elif fault == "self_reference":
        spec = replace(spec, feature_ref=slots[1].expected_subject.subject_ref)
    else:
        month, year = {"gap": (3, 2025), "duplicate_month": (4, 2025), "cross_year": (5, 2024)}[
            fault
        ]
        s = month_source(code, "WRONG-PERIOD", month, 99, year=year)
        changed = list(slots)
        changed[1] = DependencySlot("M2", s.subject, request(code, s, (s,)))
        slots = tuple(changed)
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "prospective_observed"),
        ("evidence_set_ref", "FOREIGN-SNAPSHOT"),
        ("calendar_ref", "FOREIGN-CALENDAR"),
        ("numeric_ref", "FOREIGN-NUMERIC"),
        ("policy_refs", ("FOREIGN-TEMPORAL-POLICY",)),
        ("opaque_spec_ref", "FOREIGN-FEATURE-ENV"),
    ],
)
def test_economic_context_mixing_blocks_even_when_other_month_missing(code, field, value):
    spec, slots = family(code, third="absent")
    req = slots[1].request
    req = replace(req, context=replace(req.context, **{field: value}))
    result = evaluate_derived(spec, replace_slot(slots, 1, req), code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert result.outcome.reason == "MIXED_RECONSTRUCTION_CONTEXT"


def test_mixed_cutoff_and_code_observation_block(code):
    spec, slots = family(code)
    _, late = family(code, cutoff="2025-07-14T00:00:00+08:00")
    assert (
        evaluate_derived(spec, (slots[0], late[1], slots[2]), code).outcome.reason
        == "MIXED_RECONSTRUCTION_CONTEXT"
    )
    result = evaluate_derived(spec, slots, code)
    dep = result.dependencies[1]
    forged = replace(
        dep,
        actual=replace(
            dep.actual, inputs=replace(dep.actual.inputs, code=replace(code, head="f" * 40))
        ),
    )
    bad = _evaluate_completed(spec, (result.dependencies[0], forged, result.dependencies[2]), code)
    assert bad.outcome.reason == "MIXED_CODE_OBSERVATION"


@pytest.mark.parametrize(
    "dependency",
    [
        "FIT_STATE",
        "LABEL",
        "WINDOW",
        "FALLBACK",
        "DYNAMIC_UNIVERSE",
        "FUTURE_PARAMETER",
        "POPULATION",
    ],
)
def test_unsupported_dependencies_never_auto_certified(code, dependency):
    spec, slots = family(code)
    result = evaluate_derived(replace(spec, extra_dependencies=(dependency,)), slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert result.outcome.reason == "UNSUPPORTED_FEATURE_DEFINITION_OR_DEPENDENCY"


@pytest.mark.parametrize(
    "field,value",
    [
        ("transformation_ref", "RATIO"),
        ("numerical_policy", "FLOAT"),
        ("preview_policy", "ALL_AUDIT_FIELDS"),
        ("quarter", 5),
        ("year", 0),
    ],
)
def test_unsupported_feature_definitions(code, field, value):
    spec, slots = family(code)
    assert (
        evaluate_derived(replace(spec, **{field: value}), slots, code).outcome.state
        == "CONTRACT_VIOLATION"
    )


@pytest.mark.parametrize("value", [0, -(2**63) + 20_000_000, 2**63 - 1])
def test_exact_zero_signed_values_and_sum_overflow(code, value):
    spec, slots = family(code)
    s = month_source(code, "NUMERIC", 6, value)
    slots = replace_slot(slots, 2, request(code, s, (s,)))
    slots = (*slots[:2], replace(slots[2], expected_subject=s.subject))
    result = evaluate_derived(spec, slots, code)
    if value == 2**63 - 1:
        assert result.outcome.reason == "INTEGER_SUM_OVERFLOW"
    else:
        assert result.outcome.value == 19_741_391 + 19_509_486 + value
        assert result.outcome.lineage[2].value == value


def test_all_three_zero_values_stay_numeric_zero(code):
    spec, slots = family(code)
    changed = []
    for i, slot in enumerate(slots):
        s = month_source(code, "ZERO-" + str(i), i + 4, 0)
        changed.append(replace(slot, expected_subject=s.subject, request=request(code, s, (s,))))
    result = evaluate_derived(spec, tuple(changed), code)
    assert result.outcome.value == 0 and json.loads(result.diagnostic_preview_bytes)["value"] == 0


@pytest.mark.parametrize("fault", ["value", "state", "request", "candidate_actual"])
def test_forged_completed_transport_is_rejected_by_owner_replay(code, fault):
    spec, slots = family(code, third="conflict" if fault == "state" else "selected")
    result = evaluate_derived(spec, slots, code)
    dep = result.dependencies[2]
    actual = dep.actual
    if fault in {"value", "state"}:
        actual = replace(
            actual, selection=replace(actual.selection, state="SELECTED", selected_value=42)
        )
    elif fault == "request":
        dep = replace(dep, slot=slots[1])
    else:
        c = actual.inputs.candidates[0]
        c = replace(c, actual=replace(c.actual, context=slots[0].request.context))
        actual = replace(actual, inputs=replace(actual.inputs, candidates=(c,)))
    dep = replace(dep, actual=actual)
    bad = _evaluate_completed(spec, (*result.dependencies[:2], dep), code)
    assert bad.outcome.state == "CONTRACT_VIOLATION"


@pytest.mark.parametrize("kind", ["assertion", "content_version", "representation"])
def test_notice_nonendpoint_and_cross_month_identity_reuse_guard(code, kind):
    spec, slots = family(code)
    old = slots[2].request.candidates[0]
    new = month_source(code, "CORRECTED", 6, 17_548_423, published="2025-07-04T14:00:00+08:00")
    rel = revision(
        code, old, new, subject_ref=old.subject.subject_ref, published="2025-07-04T14:00:00+08:00"
    )
    # A foreign month's claim is a nonendpoint of June's relation. All individual
    # A03 operations can select; A04 must inspect the separate notice source too.
    foreign = slots[0].request.candidates[0].request
    notice = rel.notice.request
    old_id, collision = {
        "assertion": (notice.assertion.assertion_ref, foreign.assertion.assertion_ref),
        "content_version": (
            notice.content.content_version_ref,
            foreign.content.content_version_ref,
        ),
        "representation": (notice.content.representation_ref, foreign.content.representation_ref),
    }[kind]
    rel = replace(rel, notice=rewrite(rel.notice, ids={old_id: collision}))
    rel = replace(rel, relation=replace(rel.relation, origin=rel.notice.subject.metric.origin))
    if kind == "assertion":
        # Keep declaration anchor and raw relation proposition coherent after rename.
        rel = replace(rel, relation=replace(rel.relation, notice_assertion_ref=collision))
    req = request(code, old, (old, new), (rel,))
    assert evaluate_asof(req, code).selection.state == "SELECTED"
    result = evaluate_derived(spec, replace_slot(slots, 2, req), code)
    assert result.outcome.reason == "CONTRADICTORY_IMMUTABLE_IDENTITY"
    assert result.outcome.state == "CONTRACT_VIOLATION"


@pytest.mark.parametrize("kind", ["selected", "absent", "conflict"])
def test_audit_annotation_and_order_noninterference(code, kind):
    spec, slots = family(code, third=kind, revised=kind == "selected")
    result = evaluate_derived(spec, slots, code)
    changed = []
    for dep in reversed(result.dependencies):
        selection = dep.actual.selection
        audit = tuple(reversed(selection.research_only_audit)) + (
            ResearchAuditEntry("FUTURE", "SECRET-NOTE", "FUTURE-REVISION-TRUTH"),
        )
        changed.append(
            replace(
                dep,
                actual=replace(dep.actual, selection=replace(selection, research_only_audit=audit)),
            )
        )
    altered = _evaluate_completed(spec, tuple(changed), code)
    assert altered.outcome == result.outcome
    assert altered.diagnostic_preview_bytes == result.diagnostic_preview_bytes
    assert altered.realization_ref == result.realization_ref
    assert altered.research_only_audit != result.research_only_audit


def test_preview_strict_allowlist_and_no_future_or_research_fields(code):
    spec, slots = family(code, revised=True)
    result = evaluate_derived(spec, slots, code)
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
    assert "CORRECT" not in result.diagnostic_preview_bytes.decode()
    assert not any(
        key in preview
        for key in (
            "source_ref",
            "proof_ref",
            "reason",
            "evidence_set_ref",
            "computed_at",
            "future_revision",
        )
    )


def test_deterministic_permutation_and_new_snapshot_reconstruction(code):
    spec, slots = family(code, revised=True)
    a = evaluate_derived(spec, slots, code)
    assert a == evaluate_derived(spec, tuple(reversed(slots)), code)
    assert a == evaluate_derived(spec, slots, code)
    _, newer = family(code, revised=True, snapshot="E-A04-NEW")
    b = evaluate_derived(spec, newer, code)
    assert a.outcome.value == b.outcome.value and a.realization_ref != b.realization_ref
    assert a == evaluate_derived(spec, slots, code)


@pytest.mark.parametrize("mode", ["public", "prospective_observed"])
def test_mode_separation_and_no_public_to_capture_promotion(code, mode):
    spec, slots = family(code, mode=mode)
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == ("VALUE_AVAILABLE" if mode == "public" else "NOT_COMPUTABLE")
    isolated(result)


def test_immutable_trust_fields_cannot_be_overridden(code):
    spec, slots = family(code)
    result = evaluate_derived(spec, slots, code)
    with pytest.raises(ValueError):
        replace(result, admission_eligible=True)
    with pytest.raises(FrozenInstanceError):
        result.trust = "TRUSTED"
    assert not hasattr(result, "to_agent_observation")


def test_sc01_apparent_binding_support_and_selection_stay_untrusted(code):
    spec, slots = family(code)
    candidate = slots[2].request.candidates[0]
    r = candidate.request
    binding = r.attempts[0].supplied
    origin = replace(binding.target.origin, object_id=OriginKnownValue("EVID-ORD1-TIME"))
    binding = replace(
        binding, evidence_ref="EVID-ORD1-TIME", target=replace(binding.target, origin=origin)
    )
    foreign_member = replace(
        next(m for m in r.scope.input_members if m.role == "evidence"),
        object_ref="EVID-ORD1-TIME",
    )
    r = replace(
        r,
        attempts=(replace(r.attempts[0], supplied=binding),),
        scope=replace(
            r.scope,
            input_members=tuple(
                sorted((*r.scope.input_members, foreign_member), key=lambda member: member.key)
            ),
        ),
    )
    candidate = replace(candidate, request=r)
    result = evaluate_derived(
        spec, replace_slot(slots, 2, request(code, candidate, (candidate,))), code
    )
    actual = result.dependencies[2].actual.inputs.candidates[0].actual
    assert actual.s1.state == "BOUND" and actual.s2.state == "SUPPORTED"
    assert result.dependencies[2].actual.selection.state == "SELECTED"
    assert result.outcome.state == "VALUE_AVAILABLE"
    isolated(result)  # Known SC-01 remains OPEN; this is not authentication.


def test_failure_priority_retains_all_exact_upstream_results(code):
    spec, slots = family(code, third="conflict")
    first = slots[0].request.candidates[0]
    failed = request(code, first, (first,), check_status="FAILED")
    slots = replace_slot(slots, 0, failed)
    second = slots[1].request.candidates[0]
    bad = replace(
        second,
        request=replace(
            second.request,
            requested=replace(second.request.requested, fragment_selector="/statements/999"),
        ),
    )
    slots = replace_slot(slots, 1, request(code, bad, (bad,)))
    result = evaluate_derived(spec, slots, code)
    assert result.outcome.state == "CONTRACT_VIOLATION"
    assert tuple(f.category for f in result.outcome.upstream_failures) == (
        "OPERATIONAL_ERROR",
        "CONTRACT_VIOLATION",
    )
    assert result.outcome.reason == result.dependencies[1].actual.selection.code
    assert result.research_only_audit[2].upstream.state == "UNRESOLVED"


def test_later_computation_metadata_does_not_move_information_cutoff(code):
    from pit_research_lab.domain.contracts import Known

    spec, slots = family(code)
    original = evaluate_derived(spec, slots, code)
    changed = tuple(
        replace(
            s,
            request=replace(
                s.request,
                context=replace(
                    s.request.context,
                    computation_attempt_time=Known(
                        "2099-01-01T07:30:00+08:00", s.request.context.origin
                    ),
                    decision_wall_times=("2099-01-01T08:00:00+08:00",),
                ),
            ),
        )
        for s in slots
    )
    later = evaluate_derived(spec, changed, code)
    assert original.outcome == later.outcome
    assert original.diagnostic_preview_bytes == later.diagnostic_preview_bytes


def test_single_actual_subject_can_select_value_from_multiple_assertions(code):
    spec, slots = family(code, target="CONTENT_VALUE")
    old = slots[2].request.candidates[0]
    equal = month_source(code, "EQUAL", 6, 17_548_413)
    req = request(code, old, (equal, old), target="CONTENT_VALUE")
    result = evaluate_derived(spec, replace_slot(slots, 2, req), code)
    assert result.outcome.state == "VALUE_AVAILABLE"
    assert len(result.outcome.lineage[2].assertion_refs) == 2


def test_declared_profile_and_observed_code_mismatch_rejected(code):
    spec, slots = family(code)
    bad = replace(
        code,
        observed_working_files=code.observed_working_files[:-1],
        byte_lengths=code.byte_lengths[:-1],
    )
    assert evaluate_derived(spec, slots, bad).outcome.reason == "INCOMPLETE_CODE_OBSERVATION"


def test_observed_disk_hashes_cover_all_owners_and_not_only_head(code):
    paths = tuple(p.path for p in code.observed_working_files)
    assert len(paths) == 10 and paths[-2:] == S4_CODE_PATHS
    assert "HEAD_IS_NOT_COMPLETE_CODE_VERSION" in code.interpretation
    for pin, length in zip(code.observed_working_files, code.byte_lengths, strict=True):
        raw = (ROOT / pin.path).read_bytes()
        assert sha256(raw).hexdigest() == pin.sha256 and len(raw) == length


def test_pure_traversal_does_not_touch_io_or_clock(code, monkeypatch):
    spec, slots = family(code)

    def denied(*args, **kwargs):
        raise AssertionError("unexpected I/O in semantic traversal")

    for obj, name in (
        (builtins, "open"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (subprocess, "check_output"),
        (socket, "socket"),
    ):
        monkeypatch.setattr(obj, name, denied)
    assert evaluate_derived(spec, slots, code).outcome.state == "VALUE_AVAILABLE"


def test_source_architecture_no_oracle_clock_or_database():
    for path in S4_CODE_PATHS:
        tree = ast.parse((ROOT / path).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [
            alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names
        ]
        assert not any(
            any(
                word in module
                for word in ("oracle", "acceptance", "wu00", "sqlalchemy", "psycopg", "requests")
            )
            for module in imports
        )
        assert not any(
            isinstance(n, ast.Attribute) and n.attr in {"now", "today", "utcnow"}
            for n in ast.walk(tree)
        )
