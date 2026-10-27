"""Independent bytes, failure partition and direct/indirect audit controls."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from b03_inputs import causal_request

from pit_research_lab.domain.causal_derivation import B03Outcome, B03Result
from pit_research_lab.domain.causal_slice import evaluate_causal, observe_causal_code
from pit_research_lab.domain.contracts import Known
from pit_research_lab.domain.diagnostic_projection import (
    DiagnosticProjectionCandidate,
    ProjectionBlocked,
    ProjectionPolicy,
    ProjectionWithheld,
    project_candidate,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def code():
    return observe_causal_code(ROOT)


def project(result, code, *, context=None, specs=None, policy=None, universe=None):
    return project_candidate(
        context or result.request.context,
        specs or result.request.specifications,
        result,
        universe or result.universe,
        policy
        or ProjectionPolicy(
            tuple(sorted(s.key for s in result.request.specifications)),
            result.request.allowed_missing,
        ),
        code,
    )


def test_exact_allowlist_bytes_missing_row_and_non_admission(code):
    result = evaluate_causal(causal_request(code, missing=True), code)
    assert isinstance(result, B03Result)
    candidate = project(result, code)
    assert isinstance(candidate, DiagnosticProjectionCandidate)
    expected = (
        b'{"candidate_schema_version":"b03-diagnostic-candidate-v0.1",'
        b'"decision_cutoff":"2025-07-07T00:00:00+08:00","rows":['
        b'{"entity_id":"SYN-A","features":{"derived_quarter_revenue":600,'
        b'"quarter_revenue_proxy":600,"third_month_share":"0.500000"}},'
        b'{"entity_id":"SYN-B","features":{"derived_quarter_revenue":null,'
        b'"quarter_revenue_proxy":1000000,"third_month_share":null}}]}'
    )
    assert candidate.candidate_bytes == expected
    assert candidate.admission_state == "WITHHELD" and not candidate.admission_eligible
    assert candidate.diagnostic_only and candidate.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    for method in ("to_agent_observation", "publish", "export"):
        assert not hasattr(candidate, method)
    with pytest.raises(ValueError):
        replace(candidate, admission_eligible=True)
    with pytest.raises(FrozenInstanceError):
        candidate.admission_state = "ADMITTED"


@pytest.mark.parametrize(
    "kwargs,kind",
    [
        ({"values": (0, 0, 0)}, DiagnosticProjectionCandidate),
        ({"missing": True}, DiagnosticProjectionCandidate),
        ({"conflict": True}, ProjectionWithheld),
        ({"complete": False}, ProjectionWithheld),
        ({"check_status": "FAILED"}, ProjectionBlocked),
        ({"missing": True, "allowed_missing": ()}, ProjectionWithheld),
    ],
)
def test_zero_missing_unresolved_fault_batch_partition(code, kwargs, kind):
    result = evaluate_causal(causal_request(code, **kwargs), code)
    assert isinstance(result, B03Result)
    candidate = project(result, code)
    assert isinstance(candidate, kind)
    if kwargs.get("values") == (0, 0, 0):
        assert dict(result.rows[0].features)["derived_quarter_revenue"].value == 0
        assert dict(result.rows[0].features)["quarter_revenue_proxy"].value == 0
        assert b'"derived_quarter_revenue":0' in candidate.candidate_bytes
        assert b'"third_month_share":null' in candidate.candidate_bytes
    if not isinstance(candidate, DiagnosticProjectionCandidate):
        assert not hasattr(candidate, "candidate_bytes")
        assert tuple(r.entity_id for r in candidate.audit.result.rows) == ("SYN-A", "SYN-B")


@pytest.mark.parametrize(
    "fault", ["value", "branch", "universe", "source", "lineage", "fit", "code", "policy"]
)
def test_projector_replays_every_completed_owner(code, fault):
    request = (
        causal_request(code, view="HISTORICAL_OBSERVATION_VIEW")
        if fault == "fit"
        else causal_request(code)
    )
    result = evaluate_causal(request, code)
    assert isinstance(result, B03Result)
    kwargs = {}
    if fault == "value":
        row = result.rows[0]
        features = ((row.features[0][0], B03Outcome("VALUE_AVAILABLE", 999)), *row.features[1:])
        result = replace(result, rows=(replace(row, features=features), result.rows[1]))
    elif fault == "branch":
        result = replace(
            result, rows=(replace(result.rows[0], proxy_branch="CONSTANT_PROXY"), result.rows[1])
        )
    elif fault == "universe":
        result = replace(result, universe=replace(result.universe, members=("SYN-A",)))
    elif fault == "source":
        source = result.source_results[0]
        altered = replace(source, selection=replace(source.selection, selected_value=999))
        result = replace(result, source_results=(altered, *result.source_results[1:]))
    elif fault == "lineage":
        row = result.rows[0]
        line = replace(row.summed.outcome.lineage[0], value=999)
        summed = replace(
            row.summed,
            outcome=replace(row.summed.outcome, lineage=(line, *row.summed.outcome.lineage[1:])),
        )
        result = replace(result, rows=(replace(row, summed=summed), result.rows[1]))
    elif fault == "fit":
        result = replace(
            result, fit=replace(result.fit, outcome=replace(result.fit.outcome, mean=(999, 1)))
        )
    elif fault == "code":
        code = replace(code, extension_byte_lengths=(1, 1, 1))
    else:
        kwargs["policy"] = ProjectionPolicy(("unapproved_future_flag",), ())
    assert isinstance(project(result, code, **kwargs), ProjectionBlocked)


@pytest.mark.parametrize("with_fit", [False, True])
def test_audit_only_annotations_cannot_change_bytes_or_indirect_decisions(code, with_fit):
    result = evaluate_causal(
        causal_request(
            code, missing=True, view="HISTORICAL_OBSERVATION_VIEW" if with_fit else None
        ),
        code,
    )
    original = project(result, code)
    assert isinstance(original, DiagnosticProjectionCandidate)
    changed = replace(
        result,
        research_only_audit=(
            "FUTURE_RESTATEMENT=true",
            "coverage confidence wording changed",
            "later_reward=-999",
        ),
    )
    from pit_research_lab.domain.selection import ResearchAuditEntry

    sources = tuple(
        replace(
            r,
            selection=replace(
                r.selection,
                research_only_audit=(
                    *r.selection.research_only_audit,
                    ResearchAuditEntry("FUTURE", "RETROSPECTIVE_ONLY", "REVISED_AFTER_DECISION"),
                ),
            ),
        )
        for r in changed.source_results
    )
    changed = replace(changed, source_results=sources)
    candidate = project(changed, code)
    assert isinstance(candidate, DiagnosticProjectionCandidate)
    assert candidate.candidate_bytes == original.candidate_bytes
    assert changed.exact_population == result.exact_population
    assert changed.proxy_population == result.proxy_population
    assert changed.fit == result.fit
    assert tuple((r.entity_id, r.proxy_branch, r.features) for r in changed.rows) == tuple(
        (r.entity_id, r.proxy_branch, r.features) for r in result.rows
    )
    assert candidate.audit != original.audit


def test_cutoff_computation_and_new_snapshot_replay(code):
    request = causal_request(code, keys=("derived_quarter_revenue",))
    original = evaluate_causal(request, code)
    late_context = replace(
        request.context,
        decision_wall_times=("2025-07-07T08:00:00+08:00",),
        computation_attempt_time=Known("2025-07-07T07:30:00+08:00", request.context.origin),
    )
    later = evaluate_causal(replace(request, context=late_context), code)
    assert isinstance(original, B03Result) and isinstance(later, B03Result)
    assert project(original, code).candidate_bytes == project(later, code).candidate_bytes
    late_source = evaluate_causal(
        causal_request(
            code,
            keys=("derived_quarter_revenue",),
            published="2025-07-07T07:00:00+08:00",
            allowed_missing=(),
        ),
        code,
    )
    assert isinstance(late_source, B03Result)
    assert isinstance(project(late_source, code), ProjectionWithheld)
    assert all(r.summed.outcome.state == "NOT_COMPUTABLE" for r in late_source.rows)
    newer = evaluate_causal(
        causal_request(code, keys=("derived_quarter_revenue",), snapshot="E-B03-NEW"), code
    )
    assert isinstance(newer, B03Result)
    assert newer.realization_ref != original.realization_ref
    assert project(newer, code).candidate_bytes == project(original, code).candidate_bytes
    permuted = replace(
        request,
        rows=tuple(reversed(request.rows)),
        plan=replace(
            request.plan,
            nodes=tuple(reversed(request.plan.nodes)),
            edges=tuple(reversed(request.plan.edges)),
        ),
    )
    replay = evaluate_causal(permuted, code)
    assert isinstance(replay, B03Result)
    assert replay.realization_ref == original.realization_ref
    assert project(replay, code).candidate_bytes == project(original, code).candidate_bytes
    assert evaluate_causal(request, code) == original


def test_legitimate_empty_calculation_population_keeps_full_benchmark(code):
    result = evaluate_causal(causal_request(code, all_missing=True), code)
    assert isinstance(result, B03Result)
    assert result.exact_population == ()
    assert result.proxy_population == ("SYN-A", "SYN-B")
    assert result.universe.members == ("SYN-A", "SYN-B")
    candidate = project(result, code)
    assert isinstance(candidate, DiagnosticProjectionCandidate)
    assert candidate.candidate_bytes.count(b'"derived_quarter_revenue":null') == 2


def test_timezone_resource_failure_blocks_all_b03_boundaries(code, monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError

    from pit_research_lab.domain import temporal
    from pit_research_lab.domain.causal_derivation import _fit_completed, label_eligibility
    from pit_research_lab.domain.causal_slice import fit_standardizer, qualify_universe
    from pit_research_lab.domain.contracts import BlockingFailure

    request = causal_request(code, view="HISTORICAL_OBSERVATION_VIEW")
    original = evaluate_causal(request, code)
    assert isinstance(original, B03Result)
    assert isinstance(project(original, code), DiagnosticProjectionCandidate)

    def unavailable(_name):
        raise ZoneInfoNotFoundError("synthetic unavailable zone database")

    monkeypatch.setattr(temporal, "_zone", unavailable)
    failed = evaluate_causal(request, code)
    assert isinstance(failed, BlockingFailure)
    assert failed.category == "OPERATIONAL_ERROR" and failed.code == "ZONE_DATA_UNAVAILABLE"
    fit = fit_standardizer(request.fit, code, request.context)
    assert isinstance(fit.outcome, BlockingFailure)
    assert fit.outcome.category == "OPERATIONAL_ERROR"
    universe = qualify_universe(request.universe, code.upstream_ratio.upstream_a04, request.context)
    assert isinstance(universe, BlockingFailure) and universe.category == "OPERATIONAL_ERROR"
    direct_fit = _fit_completed(request.fit, code, request.context, original.fit.inputs)
    assert isinstance(direct_fit, BlockingFailure) and direct_fit.category == "OPERATIONAL_ERROR"
    source = request.rows[0].sum_request.slots[0].request
    label = label_eligibility(
        source.context, source, request.context, code.upstream_ratio.upstream_a04
    )
    assert isinstance(label, BlockingFailure) and label.category == "OPERATIONAL_ERROR"
    projected = project(original, code)
    assert isinstance(projected, ProjectionBlocked) and projected.code == "ZONE_DATA_UNAVAILABLE"
    assert not hasattr(projected, "candidate_bytes")


def _r1_universe(code, *, flags=(1, 1), kind="valid", snapshot="E-B03-1", tag_suffix=""):
    from datetime import date

    from b03_inputs import asof, membership_sources

    from pit_research_lab.domain.causal_derivation import (
        UniverseReference,
        UniverseRequest,
        UniverseSpec,
    )

    core = code.upstream_ratio.upstream_a04
    period = (
        (date(2025, 6, 1), date(2025, 6, 30))
        if kind == "outside"
        else (date(2025, 7, 1), date(2025, 7, 31))
    )
    candidates = membership_sources(
        core,
        flags,
        period=period,
        published="2025-05-20T10:00:00+08:00",
        unknown=kind == "unknown",
        tag_suffix=tag_suffix,
    )
    requests = tuple(
        asof(
            core,
            c,
            (c,),
            complete=kind != "coverage",
            snapshot=snapshot,
            check_status="FAILED" if kind == "operation" else None,
        )
        for c in candidates
    )
    if kind == "missing":
        requests = requests[:1]
    if kind == "contract":
        first = requests[0]
        requests = (
            replace(first, policy=replace(first.policy, issuer_ref="FALSE-PUBLISHER")),
            requests[1],
        )
    spec = UniverseSpec(*period)
    return UniverseRequest(spec, requests, UniverseReference(spec, requests, core))


@pytest.mark.parametrize("missing", [False, True])
def test_r1_p2_qualified_zero_member_cannot_enter_exact_or_proxy_population(code, missing):
    from pit_research_lab.domain.causal_derivation import QualifiedSyntheticUniverse

    request = causal_request(
        code,
        universe_request=_r1_universe(code, flags=(1, 0)),
        other_values=(100, 100, 300),
        missing=missing,
    )
    result = evaluate_causal(request, code)
    assert isinstance(result, B03Result) and isinstance(result.universe, QualifiedSyntheticUniverse)
    assert result.universe.members == ("SYN-A",)
    for actual, flag in zip(result.universe.completed, (1, 0), strict=True):
        assert actual.selection.state == "SELECTED" and actual.selection.selected_value == flag
        leaf = actual.inputs.candidates[0].actual
        assert leaf.s1.state == "BOUND" and leaf.s2.state == "SUPPORTED"
    assert tuple(r.entity_id for r in result.rows) == ("SYN-A", "SYN-B")
    assert result.rows[0].summed.outcome.value == 600
    if missing:
        assert result.rows[1].summed.outcome.state == "NOT_COMPUTABLE"
        assert dict(result.rows[1].features)["quarter_revenue_proxy"].value == 1_000_000
    else:
        assert result.rows[1].summed.outcome.value == 500
    projected = project(result, code)
    assert isinstance(projected, ProjectionWithheld)
    assert projected.code == "UNSUPPORTED_UNIVERSE_CARDINALITY"
    assert not hasattr(projected, "candidate_bytes")
    print(
        "P2_OWNER_PROOF flags=1/0 U=",
        result.universe.members,
        "P_exact=",
        result.exact_population,
        "P_proxy=",
        result.proxy_population,
        "B_missing=",
        missing,
        "PROJECTED=",
        projected.code,
    )
    assert result.exact_population == ("SYN-A",)
    assert result.proxy_population == ("SYN-A",)


@pytest.mark.parametrize(
    "kind", ["missing", "unknown", "coverage", "outside", "operation", "contract"]
)
def test_r1_p2_unqualified_universe_has_no_qualified_population_claim(code, kind):
    from pit_research_lab.domain.contracts import NotEvaluated

    result = evaluate_causal(
        causal_request(code, universe_request=_r1_universe(code, kind=kind)), code
    )
    assert isinstance(result, B03Result)
    projected = project(result, code)
    assert isinstance(
        projected, ProjectionBlocked if kind in {"operation", "contract"} else ProjectionWithheld
    )
    assert not hasattr(projected, "candidate_bytes")
    print(
        "P2_UNQUALIFIED",
        kind,
        type(result.universe).__name__,
        "P_exact=",
        result.exact_population,
        "P_proxy=",
        result.proxy_population,
        "PROJECTED=",
        type(projected).__name__,
    )
    assert isinstance(result.exact_population, NotEvaluated)
    assert isinstance(result.proxy_population, NotEvaluated)
    assert (
        result.exact_population.reason
        == result.proxy_population.reason
        == "UNQUALIFIED_UNIVERSE_POPULATION"
    )


def test_r1_p2_qualified_empty_universe_is_distinct_from_unqualified(code):
    from pit_research_lab.domain.causal_derivation import QualifiedSyntheticUniverse

    result = evaluate_causal(
        causal_request(code, universe_request=_r1_universe(code, flags=(0, 0))), code
    )
    assert isinstance(result, B03Result) and isinstance(result.universe, QualifiedSyntheticUniverse)
    assert result.universe.members == result.exact_population == result.proxy_population == ()
    projected = project(result, code)
    assert isinstance(projected, ProjectionWithheld) and not hasattr(projected, "candidate_bytes")


def test_r1_p2_audit_only_changes_do_not_qualify_members_and_new_evidence_replays(code):
    request = causal_request(code, universe_request=_r1_universe(code, flags=(1, 0)))
    old = evaluate_causal(request, code)
    assert isinstance(old, B03Result)
    audited = replace(
        old, research_only_audit=("FUTURE_RESTATEMENT", "confidence prose", "later_reward=7")
    )
    assert old.universe == audited.universe
    assert old.exact_population == audited.exact_population == ("SYN-A",)
    assert old.proxy_population == audited.proxy_population == ("SYN-A",)
    assert old.rows == audited.rows
    assert (
        project(old, code).code == project(audited, code).code == "UNSUPPORTED_UNIVERSE_CARDINALITY"
    )
    # A separately retained source assertion, same legitimate flag, distinct evidence identity.
    newer_request = causal_request(
        code,
        snapshot="E-B03-R1-NEW",
        universe_request=_r1_universe(
            code, flags=(1, 0), snapshot="E-B03-R1-NEW", tag_suffix="-NEW-EVIDENCE"
        ),
    )
    newer = evaluate_causal(newer_request, code)
    assert isinstance(newer, B03Result)
    assert newer.universe.members == newer.exact_population == newer.proxy_population == ("SYN-A",)
    assert newer.realization_ref != old.realization_ref
    assert (
        newer.universe.completed[0].selection.selected_assertion_refs
        != old.universe.completed[0].selection.selected_assertion_refs
    )
    assert evaluate_causal(request, code) == old
