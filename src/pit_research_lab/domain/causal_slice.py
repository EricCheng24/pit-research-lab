"""B03 request-only composition and explicit outer disk observation."""

from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

from pit_research_lab.domain.asof_slice import evaluate_asof
from pit_research_lab.domain.causal_derivation import (
    B03_CODE_PATHS,
    FEATURE_KEYS,
    NO_STATE,
    PROFILE,
    UNSUPPORTED,
    B03CodeObservation,
    B03FeatureSpec,
    B03Outcome,
    B03Refusal,
    B03Request,
    B03Result,
    CausalReference,
    FitEvaluation,
    FrozenStandardizer,
    QualifiedSyntheticUniverse,
    RowResult,
    StandardizerRequest,
    UniverseRequest,
    _check_fit_cutoffs,
    _check_role_cutoff,
    _fit_completed,
    _qualify_universe,
    _standardize,
    check_plan,
    check_sources,
    cohort,
    failure,
    identity,
    required_plan,
    selected_training,
    semantic_bytes,
    source_requests,
    validate_code,
    zone_failure,
)
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    CodePin,
    ContractError,
    NotEvaluated,
    SemanticContext,
    require,
)
from pit_research_lab.domain.derivation import DerivedResult
from pit_research_lab.domain.derived_slice import evaluate_derived
from pit_research_lab.domain.pit_slice import CodeObservation
from pit_research_lab.domain.ratio_slice import evaluate_ratio, observe_ratio_code
from pit_research_lab.domain.selection import B02_EVALUATOR_REF, SelectionOutcome


def observe_causal_code(repository: Path) -> B03CodeObservation:
    upstream = observe_ratio_code(repository)
    bodies = tuple((repository / p).read_bytes() for p in B03_CODE_PATHS)
    return B03CodeObservation(
        upstream,
        tuple(
            CodePin(p, sha256(b).hexdigest()) for p, b in zip(B03_CODE_PATHS, bodies, strict=True)
        ),
        tuple(len(b) for b in bodies),
    )


def qualify_universe(
    request: UniverseRequest,
    code: CodeObservation,
    context: SemanticContext,
    /,
) -> QualifiedSyntheticUniverse | B03Refusal | BlockingFailure:
    return _qualify_universe(request, code, context)


def fit_standardizer(
    request: StandardizerRequest,
    code: B03CodeObservation,
    decision: SemanticContext,
    /,
) -> FitEvaluation:
    try:
        require(len(request.rows) <= 8, "FIT_ROW_LIMIT")
        require(
            all(len(s.slots) == 3 for r in request.rows for s in (r.historical, r.fit_time)),
            "INVALID_FIT_ROW_SLOTS",
        )
        _check_fit_cutoffs(request, decision)
        sums = selected_training(request)
        check_sources(tuple(dict.fromkeys(s.request for r in sums for s in r.slots)))
        inputs = tuple(
            evaluate_derived(r.specification, r.slots, code.upstream_ratio.upstream_a04)
            for r in sums
        )
        return FitEvaluation(inputs, _fit_completed(request, code, decision, inputs))
    except ContractError as exc:
        return FitEvaluation((), failure(decision, str(exc)))
    except ZoneInfoNotFoundError:
        return FitEvaluation((), zone_failure(decision))


def _validate_request(request: B03Request, code: B03CodeObservation) -> None:
    check_plan(request.plan)
    require(
        isinstance(request.fit, (StandardizerRequest, type(NO_STATE))), "INVALID_STATE_REFERENCE"
    )
    require(all(len(r.sum_request.slots) == 3 for r in request.rows), "INVALID_DECISION_ROW_SLOTS")
    if isinstance(request.fit, StandardizerRequest):
        require(
            all(len(s.slots) == 3 for r in request.fit.rows for s in (r.historical, r.fit_time)),
            "INVALID_FIT_ROW_SLOTS",
        )
    else:
        require(request.fit == NO_STATE, "INVALID_STATE_REFERENCE")
    validate_code(code, request.retained.code)
    expected = CausalReference(
        request.context,
        request.specifications,
        request.rows,
        request.fit,
        request.universe,
        code,
        request.period_bindings,
        request.allowed_missing,
    )
    require(
        semantic_bytes(request.retained) == semantic_bytes(expected),
        "B03_RETAINED_REFERENCE_MISMATCH",
    )
    require(
        request.evaluator_ref == PROFILE
        and type(request.proxy_constant) is int
        and request.proxy_constant == 1_000_000,
        "INVALID_B03_POLICY",
    )
    require(
        len(request.rows) == 2
        and tuple(sorted(r.entity_id for r in request.rows)) == ("SYN-A", "SYN-B"),
        "INVALID_DECISION_GRID",
    )
    keys = tuple(s.key for s in request.specifications)
    require(1 <= len(keys) <= 4 and len(keys) == len(set(keys)), "INVALID_FEATURE_SET")
    require(all(s == B03FeatureSpec(s.key) for s in request.specifications), "INVALID_FEATURE_SPEC")
    require(len(request.period_bindings) == 2, "INVALID_PERIOD_BINDINGS")
    require(
        len(request.allowed_missing) == len(set(request.allowed_missing))
        and all(k in FEATURE_KEYS for k in request.allowed_missing),
        "INVALID_MISSING_POLICY",
    )
    expected_plan = required_plan(request)
    require(
        tuple(sorted(request.plan.nodes, key=lambda n: n.ref)) == expected_plan.nodes
        and tuple(sorted(request.plan.edges)) == expected_plan.edges,
        "INCOMPLETE_REQUIRED_CLOSURE",
    )
    if isinstance(request.fit, StandardizerRequest):
        _check_fit_cutoffs(request.fit, request.context)
    else:
        _check_role_cutoff(request.context, "INVALID_DECISION_CUTOFF")
    reference = sorted(request.rows, key=lambda r: r.entity_id)[0].sum_request.slots[0].request
    require(
        semantic_bytes(reference.context) == semantic_bytes(request.context),
        "FIXED_CONTEXT_MISMATCH",
    )
    for row in request.rows:
        s = row.sum_request
        require(
            (row.entity_id, s.specification.year, s.specification.quarter)
            in request.period_bindings
            and s.specification.issuer_ref == row.entity_id,
            "PERIOD_OR_ENTITY_MISMATCH",
        )
        for slot in s.slots:
            require(
                cohort(slot.request) == cohort(reference)
                and slot.request.context.information_cutoff == request.context.information_cutoff,
                "MIXED_RECONSTRUCTION_CONTEXT",
            )
    for r in request.universe.requests:
        require(cohort(r) == cohort(reference), "MIXED_UNIVERSE_CONTEXT")
    if isinstance(request.fit, StandardizerRequest):
        require(len(request.fit.rows) <= 8, "FIT_ROW_LIMIT")
        require("quarter_revenue_zscore" in keys, "UNUSED_FITTED_STATE")
        for training in request.fit.rows:
            for s in (training.historical, training.fit_time):
                require(s.specification.issuer_ref in ("SYN-A", "SYN-B"), "UNSUPPORTED_FIT_ENTITY")
                for slot in s.slots:
                    require(cohort(slot.request) == cohort(reference), "MIXED_FIT_CONTEXT")
            require(
                training.historical.specification.feature_ref
                not in {r.sum_request.specification.feature_ref for r in request.rows},
                "CURRENT_ROW_IN_FIT",
            )
    elif "quarter_revenue_zscore" in keys:
        require(False, "MISSING_REQUIRED_STATE")
    check_sources(source_requests(request))
    require(
        all(r.policy.evaluator_ref == B02_EVALUATOR_REF for r in source_requests(request)),
        "MIXED_S3_EVALUATOR",
    )


def evaluate_causal(
    request: B03Request,
    code: B03CodeObservation,
    /,
) -> B03Result | B03Refusal | BlockingFailure:
    try:
        _validate_request(request, code)
        if request.context.mode != "public":
            return B03Refusal("UNSUPPORTED_B03_OBSERVED_PROFILE")
        if request.window != "LAST_N_REFERENCE_PERIODS_3":
            return B03Refusal("UNSUPPORTED_WINDOW_PROFILE")
        for spec in request.specifications:
            if spec.key in UNSUPPORTED:
                return B03Refusal("UNSUPPORTED_FEATURE_FAMILY")
            require(spec.key in FEATURE_KEYS, "INVALID_FEATURE_SPEC")
        source_code = code.upstream_ratio.upstream_a04
        sources = tuple(evaluate_asof(r, source_code) for r in source_requests(request))
        universe = qualify_universe(request.universe, source_code, request.context)
        fitted = (
            fit_standardizer(request.fit, code, request.context)
            if isinstance(request.fit, StandardizerRequest)
            else NO_STATE
        )
        rows = []
        for row in sorted(request.rows, key=lambda r: r.entity_id):
            s = row.sum_request
            ratio = evaluate_ratio(
                row.ratio_specification, s.specification, s.slots, code.upstream_ratio
            )
            summed = ratio.upstream_a04
            require(isinstance(summed, DerivedResult), "INVALID_UPSTREAM_SUM")
            assert isinstance(summed, DerivedResult)
            base = B03Outcome(
                summed.outcome.state,
                summed.outcome.value,
                summed.outcome.reason,
                summed.outcome.upstream_failures,
            )
            share = B03Outcome(
                ratio.outcome.state,
                ratio.outcome.value,
                ratio.outcome.reason,
                ratio.outcome.upstream_failures,
            )
            branch, proxy = "PRIMARY", base
            selection_states = tuple(
                d.actual.selection.state
                for d in summed.dependencies
                if isinstance(d.actual.selection, SelectionOutcome)
            )
            if (
                base.state == "NOT_COMPUTABLE"
                and len(selection_states) == 3
                and "NO_QUALIFIED_CLAIM" in selection_states
                and all(s in {"SELECTED", "NO_QUALIFIED_CLAIM"} for s in selection_states)
            ):
                branch, proxy = (
                    "CONSTANT_PROXY",
                    B03Outcome("VALUE_AVAILABLE", request.proxy_constant),
                )
            z = base
            if isinstance(fitted, FitEvaluation):
                state = fitted.outcome
                if isinstance(state, FrozenStandardizer):
                    try:
                        z = (
                            B03Outcome("VALUE_AVAILABLE", _standardize(base.value, state))
                            if type(base.value) is int
                            else base
                        )
                    except ContractError as exc:
                        fault = failure(request.context, str(exc))
                        z = B03Outcome("CONTRACT_VIOLATION", reason=fault.code, failures=(fault,))
                elif isinstance(state, B03Outcome):
                    z = state
                elif isinstance(state, B03Refusal):
                    z = B03Outcome("UNRESOLVED", reason=state.code)
                else:
                    z = B03Outcome(
                        "CONTRACT_VIOLATION"
                        if state.category == "CONTRACT_VIOLATION"
                        else "OPERATIONAL_ERROR",
                        reason=state.code,
                        failures=(state,),
                    )
            available = {
                "derived_quarter_revenue": base,
                "quarter_revenue_proxy": proxy,
                "quarter_revenue_zscore": z,
                "third_month_share": share,
            }
            rows.append(
                RowResult(
                    row.entity_id,
                    summed,
                    ratio,
                    tuple(
                        (spec.key, available[spec.key])
                        for spec in sorted(request.specifications, key=lambda s: s.key)
                    ),
                    branch,
                )
            )
        faults = [r.selection for r in sources if isinstance(r.selection, BlockingFailure)]
        faults += [f for row in rows for _, o in row.features for f in o.failures]
        if isinstance(universe, BlockingFailure):
            faults.append(universe)
        if isinstance(fitted, FitEvaluation) and isinstance(fitted.outcome, BlockingFailure):
            faults.append(fitted.outcome)
        faults = list(dict.fromkeys(faults))
        exact: tuple[str, ...] | NotEvaluated
        proxies: tuple[str, ...] | NotEvaluated
        if isinstance(universe, QualifiedSyntheticUniverse):
            exact = tuple(
                r.entity_id
                for r in rows
                if r.entity_id in universe.members and r.summed.outcome.state == "VALUE_AVAILABLE"
            )
            proxies = tuple(
                r.entity_id
                for r in rows
                if r.entity_id in universe.members
                and any(
                    k == "quarter_revenue_proxy" and o.state == "VALUE_AVAILABLE"
                    for k, o in r.features
                )
            )
        else:
            exact = proxies = NotEvaluated("B03", "UNQUALIFIED_UNIVERSE_POPULATION")
        result_id = identity(
            (
                request.retained,
                request.plan,
                request.window,
                request.proxy_constant,
                tuple(r.reconstruction_ref for r in sources),
                tuple((r.summed.realization_ref, r.ratio.realization_ref) for r in rows),
                fitted,
                universe,
            )
        )
        return B03Result(
            request,
            code,
            tuple(rows),
            fitted,
            universe,
            sources,
            exact,
            proxies,
            tuple(faults),
            result_id,
        )
    except ContractError as exc:
        return failure(request.context, str(exc))
    except ZoneInfoNotFoundError:
        return zone_failure(request.context)
