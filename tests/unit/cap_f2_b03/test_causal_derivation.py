"""Independent B03 scenarios, not formal Golden execution."""

from dataclasses import replace
from pathlib import Path

import pytest
from b03_inputs import END, START, asof, causal_request, membership_sources

from pit_research_lab.domain.asof_slice import evaluate_asof
from pit_research_lab.domain.causal_derivation import (
    B03Refusal,
    B03Result,
    CausalPlan,
    PlanNode,
    QualifiedSyntheticUniverse,
    UniverseReference,
    UniverseRequest,
    UniverseSpec,
    check_plan,
)
from pit_research_lab.domain.causal_slice import (
    evaluate_causal,
    observe_causal_code,
    qualify_universe,
)
from pit_research_lab.domain.contracts import BlockingFailure, ContractError
from pit_research_lab.domain.derived_slice import observe_derived_code

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def source_code():
    return observe_derived_code(ROOT)


def universe_request(
    code,
    *,
    flags=(1, 1),
    cutoff="2025-07-07T00:00:00+08:00",
    missing=False,
    complete=True,
    **kwargs,
):
    candidates = membership_sources(code, flags, **kwargs)
    requests = tuple(asof(code, c, (c,), cutoff=cutoff, complete=complete) for c in candidates)
    if missing:
        requests = requests[:1]
    spec = UniverseSpec(START, END)
    return UniverseRequest(spec, requests, UniverseReference(spec, requests, code))


@pytest.mark.parametrize("flags,expected", [((1, 1), ("SYN-A", "SYN-B")), ((1, 0), ("SYN-A",))])
def test_g01_own_source_path_and_explicit_zero(source_code, flags, expected):
    request = universe_request(source_code, flags=flags)
    result = qualify_universe(request, source_code, request.requests[0].context)
    assert isinstance(result, QualifiedSyntheticUniverse)
    assert result.members == expected
    for actual, flag in zip(result.completed, flags, strict=True):
        leaf = actual.inputs.candidates[0]
        assert leaf.actual.s1.state == "BOUND"
        assert leaf.actual.s2.state == "SUPPORTED"
        assert leaf.subject_identity.state == "SAME"
        from pit_research_lab.domain.contracts import NotApplicable, NotEvaluated

        assert isinstance(leaf.subject_identity.canonical_amount, NotEvaluated)
        assert isinstance(leaf.subject_identity.mapping_ref, NotApplicable)
        assert actual.selection.state == "SELECTED"
        assert actual.selection.selected_value == flag
        assert leaf.source.subject.canonical_unit.value == "MEMBERSHIP_FLAG"
        assert leaf.source.subject.economic_entity_ref.value == "SYN-B03-UNIVERSE-AUTHORITY"


@pytest.mark.parametrize(
    "cutoff,eligible",
    [
        ("2025-06-30T00:00:00+08:00", False),
        ("2025-07-07T00:00:00+08:00", True),
        ("2025-08-04T00:00:00+08:00", False),
    ],
)
def test_g01_publication_is_not_interval_applicability(source_code, cutoff, eligible):
    request = universe_request(source_code, cutoff=cutoff)
    # Same source declarations are genuinely published at all three cutoffs.
    assert all(
        evaluate_asof(r, source_code).selection.state == "SELECTED" for r in request.requests
    )
    result = qualify_universe(request, source_code, request.requests[0].context)
    if eligible:
        assert isinstance(result, QualifiedSyntheticUniverse)
    else:
        assert result == B03Refusal("UNIVERSE_OUTSIDE_VALIDITY")


@pytest.mark.parametrize("kind", ["publisher", "subject", "period"])
def test_g01_source_operand_semantics_cannot_be_dto_relabelled(source_code, kind):
    from datetime import timedelta

    from pit_research_lab.domain.contracts import Known

    c = membership_sources(source_code)[0]
    if kind == "publisher":
        c = replace(
            c,
            request=replace(
                c.request,
                content=replace(
                    c.request.content, issuer_ref=Known("FALSE-PUBLISHER", c.request.content.origin)
                ),
            ),
        )
    elif kind == "subject":
        c = replace(
            c, subject=replace(c.subject, economic_entity_ref=Known("SYN-A", c.subject.origin))
        )
    else:
        c = replace(
            c,
            subject=replace(
                c.subject, period_start=Known(START + timedelta(days=1), c.subject.origin)
            ),
        )
    actual = evaluate_asof(asof(source_code, c, (c,)), source_code)
    assert isinstance(actual.selection, BlockingFailure)
    assert actual.selection.category == "CONTRACT_VIOLATION"


@pytest.mark.parametrize("kind", ["missing", "unbound", "unknown", "future", "coverage"])
def test_g01_unknown_is_not_explicit_zero(source_code, kind):
    kwargs = (
        {"missing": True}
        if kind == "missing"
        else {
            "unbound": {"unbound": True},
            "unknown": {"unknown": True},
            "future": {"published": "2025-07-08T10:00:00+08:00"},
            "coverage": {"complete": False},
        }[kind]
    )
    request = universe_request(source_code, **kwargs)
    result = qualify_universe(request, source_code, request.requests[0].context)
    assert result == B03Refusal("UNQUALIFIED_UNIVERSE")


@pytest.mark.parametrize("kind", ["survivors", "mapping", "period", "publisher", "duplicate"])
def test_g01_retained_reference_and_subject_contradictions(source_code, kind):
    request = universe_request(source_code)
    if kind == "survivors":
        request = replace(request, requests=request.requests[:1])
    elif kind == "mapping":
        request = replace(
            request,
            specification=replace(
                request.specification, mapping=tuple(reversed(request.specification.mapping))
            ),
        )
    elif kind == "period":
        request = replace(request, specification=replace(request.specification, valid_from=END))
    elif kind == "duplicate":
        request = replace(request, requests=(request.requests[0], request.requests[0]))
    else:
        r = request.requests[0]
        request = replace(
            request,
            requests=(
                replace(r, policy=replace(r.policy, issuer_ref="SYN-A")),
                request.requests[1],
            ),
        )
    result = qualify_universe(request, source_code, request.retained.requests[0].context)
    assert isinstance(result, BlockingFailure)
    assert result.category == "CONTRACT_VIOLATION"


@pytest.fixture(scope="module")
def code():
    return observe_causal_code(ROOT)


def test_source_to_derived_positive_and_distinct_identities(code):
    request = causal_request(code)
    result = evaluate_causal(request, code)
    assert isinstance(result, B03Result)
    assert result.universe.members == ("SYN-A", "SYN-B")
    assert result.exact_population == ("SYN-A", "SYN-B")
    for row in result.rows:
        assert row.summed.outcome.value == 600
        assert row.ratio.outcome.value.decimal_text == "0.500000"
        assert row.summed.realization_ref != row.summed.specification.feature_ref
        assert row.summed.origin_kind == row.ratio.origin_kind == "DERIVED"
    assert result.admission_state == "WITHHELD" and result.admission_eligible is False


@pytest.mark.parametrize(
    "kind", ["cycle", "missing_edge", "code", "context", "period", "reference"]
)
def test_bounded_closure_context_and_retained_tampering(code, kind):
    request = causal_request(code)
    if kind == "cycle":
        plan = CausalPlan(
            request.plan.nodes + tuple(PlanNode(r, "TEST") for r in ("A", "STATE", "B")),
            request.plan.edges + (("A", "STATE"), ("STATE", "B"), ("B", "A")),
        )
        request = replace(request, plan=plan)
    elif kind == "missing_edge":
        request = replace(request, plan=replace(request.plan, edges=request.plan.edges[:-1]))
    elif kind == "code":
        code = replace(code, extension_pins=tuple(reversed(code.extension_pins)))
    elif kind == "context":
        request = replace(request, context=replace(request.context, evidence_set_ref="FOREIGN"))
    elif kind == "period":
        request = replace(request, period_bindings=(("SYN-A", 2025, 1), ("SYN-B", 2025, 2)))
    else:
        request = replace(request, rows=request.rows[:1])
    result = evaluate_causal(request, code)
    assert isinstance(result, BlockingFailure) and result.category == "CONTRACT_VIOLATION"
    if kind == "cycle":
        assert result.code == "DEPENDENCY_CYCLE"


@pytest.mark.parametrize("family", ["H1", "TTM", "RANK", "LAST_N_ELIGIBLE_OBSERVATIONS"])
def test_known_unsupported_families_have_real_arithmetic_neighbor(code, family):
    result = evaluate_causal(causal_request(code, keys=(family,)), code)
    assert result == B03Refusal("UNSUPPORTED_FEATURE_FAMILY")


@pytest.mark.parametrize("kind", ["s4", "s3", "depth", "fanin", "fanout", "edges"])
def test_graph_ceilings_and_ceiling_plus_one(kind):
    if kind in {"s4", "s3"}:
        limit, category = (20, "SUM") if kind == "s4" else (40, "SOURCE")
        nodes = tuple(PlanNode(str(i), category) for i in range(limit))
        good = CausalPlan(nodes, ())
        bad = CausalPlan((*nodes, PlanNode("EXTRA", category)), ())
    elif kind == "depth":
        nodes = tuple(PlanNode(str(i), "SOURCE" if i == 0 else "SUM") for i in range(6))
        good = CausalPlan(nodes[:5], tuple((str(i), str(i + 1)) for i in range(4)))
        bad = CausalPlan(nodes, (*good.edges, ("4", "5")))
    elif kind in {"fanin", "fanout"}:
        limit = 9 if kind == "fanin" else 8
        nodes = (PlanNode("ROOT", "SUM" if kind == "fanin" else "SOURCE"),) + tuple(
            PlanNode(str(i), "SOURCE" if kind == "fanin" else "SUM") for i in range(limit + 1)
        )
        edges = tuple(
            (str(i), "ROOT") if kind == "fanin" else ("ROOT", str(i)) for i in range(limit + 1)
        )
        good, bad = CausalPlan(nodes, edges[:limit]), CausalPlan(nodes, edges)
    else:
        nodes = tuple(PlanNode("S" + str(i), "SOURCE") for i in range(9)) + tuple(
            PlanNode("T" + str(i), "SUM") for i in range(16)
        )
        edges = tuple(
            ("S" + str((t // 8) * 4 + s), "T" + str(t)) for t in range(16) for s in range(4)
        )
        good, bad = CausalPlan(nodes, edges), CausalPlan(nodes, (*edges, ("S8", "T0")))
    check_plan(good)
    with pytest.raises(ContractError):
        check_plan(bad)


def test_universe_population_and_missing_company_row(code):
    result = evaluate_causal(causal_request(code, missing=True), code)
    assert isinstance(result, B03Result)
    assert result.exact_population == ("SYN-A",)
    assert result.proxy_population == ("SYN-A", "SYN-B")
    assert tuple(r.entity_id for r in result.rows) == ("SYN-A", "SYN-B")
    b = result.rows[1]
    assert b.summed.outcome.state == "NOT_COMPUTABLE"
    assert b.proxy_branch == "CONSTANT_PROXY"
    assert dict(b.features)["quarter_revenue_proxy"].value == 1_000_000


def test_original_amount_revision_and_rounded_collision(code):
    values = (19_741_391, 19_509_486, 17_548_413)
    for delta, late_text in ((10, "0.308955"), (100, "0.308956")):
        early_request = causal_request(code, values=values, revision_delta=delta)
        early = evaluate_causal(early_request, code)
        late = evaluate_causal(
            causal_request(
                code, values=values, revision_delta=delta, cutoff="2025-07-14T00:00:00+08:00"
            ),
            code,
        )
        assert isinstance(early, B03Result) and isinstance(late, B03Result)
        assert early.rows[0].summed.outcome.value == 56_799_290
        assert late.rows[0].summed.outcome.value == 56_799_290 + delta
        assert early.rows[0].ratio.outcome.value.decimal_text == "0.308955"
        assert late.rows[0].ratio.outcome.value.decimal_text == late_text
        assert (
            early.rows[0].summed.outcome.lineage[2].assertion_refs
            != late.rows[0].summed.outcome.lineage[2].assertion_refs
        )
        assert evaluate_causal(early_request, code) == early


def test_raw_body_total_bytes_and_source_inventory_bounds(source_code):
    # Structural budget controls are independent of S1 source-semantic acceptance.
    # The full valid source path is separately tested by G01 and 600 controls.
    from hashlib import sha256

    from pit_research_lab.domain.causal_derivation import check_sources

    c = membership_sources(source_code)[0]
    original = asof(source_code, c, (c,))

    def body_request(i, size):
        raw = bytes([i]) + b"x" * (size - 1)
        content = replace(
            c.request.content,
            content_version_ref="CV-BUDGET-" + str(i),
            representation_ref="REP-BUDGET-" + str(i),
            raw_bytes=raw,
            raw_length=len(raw),
            raw_sha256=sha256(raw).hexdigest(),
        )
        candidate = replace(
            c,
            request=replace(
                c.request,
                content=content,
                requested=replace(c.request.requested, target_ref="A-BUDGET-" + str(i)),
            ),
        )
        return replace(original, candidates=(candidate,))

    check_sources((body_request(0, 65536),))
    with pytest.raises(ContractError, match="RAW_BODY_LIMIT"):
        check_sources((body_request(0, 65537),))
    sixteen = tuple(body_request(i, 65536) for i in range(16))
    check_sources(sixteen)
    with pytest.raises(ContractError, match="TOTAL_RAW_BODY_LIMIT"):
        check_sources((*sixteen, body_request(16, 1)))
    forty = tuple(
        replace(original, context=replace(original.context, context_ref="BUDGET-" + str(i)))
        for i in range(40)
    )
    check_sources(forty)
    with pytest.raises(ContractError, match="S3_REQUEST_LIMIT"):
        check_sources(
            (*forty, replace(original, context=replace(original.context, context_ref="BUDGET-40")))
        )


def test_window_refusal_and_feature_capacity(code):
    request = causal_request(code)
    assert evaluate_causal(
        replace(request, window="LAST_N_ELIGIBLE_OBSERVATIONS"), code
    ) == B03Refusal("UNSUPPORTED_WINDOW_PROFILE")
    from pit_research_lab.domain.causal_derivation import B03FeatureSpec

    full = causal_request(code, view="HISTORICAL_OBSERVATION_VIEW")
    assert len(full.specifications) == 4
    five = (*full.specifications, B03FeatureSpec("H1"))
    too_many = replace(
        full, specifications=five, retained=replace(full.retained, specifications=five)
    )
    assert isinstance(evaluate_causal(too_many, code), BlockingFailure)


@pytest.mark.parametrize("kind", ["digest", "missing", "order", "length", "bool"])
def test_forged_outer_observation_is_not_its_own_authority(code, kind):
    request = causal_request(code)
    if kind == "digest":
        altered = replace(
            code,
            extension_pins=(
                replace(code.extension_pins[0], sha256="0" * 64),
                *code.extension_pins[1:],
            ),
        )
    elif kind == "missing":
        altered = replace(code, extension_pins=code.extension_pins[:2])
    elif kind == "order":
        altered = replace(code, extension_pins=tuple(reversed(code.extension_pins)))
    else:
        altered = replace(
            code,
            extension_byte_lengths=(
                True if kind == "bool" else 1,
                *code.extension_byte_lengths[1:],
            ),
        )
    assert isinstance(evaluate_causal(request, altered), BlockingFailure)


def test_multiple_state_references_are_not_an_additive_fit_api(code):
    request = causal_request(code, view="HISTORICAL_OBSERVATION_VIEW")
    assert isinstance(
        evaluate_causal(replace(request, fit=(request.fit, request.fit)), code), BlockingFailure
    )


@pytest.mark.parametrize("cutoff", ["2025-07-01T00:00:00+08:00", "2025-07-31T00:00:00+08:00"])
def test_g01_interval_endpoints_are_explicitly_inclusive(source_code, cutoff):
    request = universe_request(source_code, cutoff=cutoff)
    assert isinstance(
        qualify_universe(request, source_code, request.requests[0].context),
        QualifiedSyntheticUniverse,
    )
