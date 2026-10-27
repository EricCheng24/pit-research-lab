"""Bounded B03 causal semantics; synthetic consistency, never source authentication.

G01: a MEMBERSHIP_FLAG is a publisher's nonadditive all-dates declaration over
a Duration reference span. It is not a financial flow or an exchange listing.
S2 qualifies publication; this owner separately checks interval applicability.
"""

import json
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    FloatOperation,
    InvalidOperation,
    Overflow,
    localcontext,
)
from fractions import Fraction
from hashlib import sha256
from zoneinfo import ZoneInfoNotFoundError

from pit_research_lab.domain.asof_slice import AsOfRequest, evaluate_asof
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    CodePin,
    ContractError,
    Known,
    NotApplicable,
    NotEvaluated,
    Record,
    SemanticContext,
    require,
)
from pit_research_lab.domain.derivation import (
    DependencySlot,
    DerivedResult,
    DerivedState,
    FeatureSpec,
)
from pit_research_lab.domain.derived_slice import evaluate_derived
from pit_research_lab.domain.pit_slice import CodeObservation
from pit_research_lab.domain.ratio import (
    FixedRatio,
    RatioCodeObservation,
    RatioFeatureSpec,
    RatioResult,
)
from pit_research_lab.domain.selection import (
    B02_EVALUATOR_REF,
    AsOfSelectionResult,
    DiscoveryEvidence,
)
from pit_research_lab.domain.temporal import _instant

PROFILE = "b03-causal-diagnostic-v0.1"
PUBLISHER = "SYN-B03-UNIVERSE-AUTHORITY"
UNIVERSE_SOURCE = "SYN-B03-UNIVERSE-SOURCE"
ROSTER = ("SYN-A", "SYN-B")
MEMBER_MAPPING = tuple(
    (entity, "BENCHMARK_MEMBER_" + entity, "SUB-B03-MEMBER-" + entity) for entity in ROSTER
)


@dataclass(frozen=True)
class B03Refusal(Record):
    code: str


@dataclass(frozen=True)
class UniverseSpec(Record):
    valid_from: date
    valid_through: date
    publisher: str = PUBLISHER
    source_ref: str = UNIVERSE_SOURCE
    mapping: tuple[tuple[str, str, str], ...] = MEMBER_MAPPING
    policy_ref: str = "B03-ALL-DATES-MEMBERSHIP-v0.1"


@dataclass(frozen=True)
class UniverseReference(Record):
    specification: UniverseSpec
    requests: tuple[AsOfRequest, ...]
    code: CodeObservation


@dataclass(frozen=True)
class UniverseRequest(Record):
    specification: UniverseSpec
    requests: tuple[AsOfRequest, ...]
    retained: UniverseReference


@dataclass(frozen=True)
class QualifiedSyntheticUniverse(Record):
    request: UniverseRequest
    members: tuple[str, ...]
    completed: tuple[AsOfSelectionResult, ...]


def failure(context: SemanticContext, code: str) -> BlockingFailure:
    return BlockingFailure("CONTRACT_VIOLATION", code, (), code, context.origin, "B03")


def zone_failure(context: SemanticContext) -> BlockingFailure:
    return BlockingFailure(
        "OPERATIONAL_ERROR",
        "ZONE_DATA_UNAVAILABLE",
        (),
        "ZONE_DATA_UNAVAILABLE",
        context.origin,
        "B03",
    )


def cohort(request: AsOfRequest) -> tuple[object, ...]:
    c = request.context
    return (
        c.mode,
        c.evidence_set_ref,
        c.calendar_ref,
        c.numeric_ref,
        c.profile,
        tuple(sorted(p for p in c.policy_refs if p != request.policy.policy_ref)),
        c.opaque_spec_ref,
        c.opaque_fit_refs,
        c.temporal_rule,
        request.policy.version,
        request.policy.evaluator_ref,
    )


def _qualify_universe(
    request: UniverseRequest,
    code: CodeObservation,
    context: SemanticContext,
) -> QualifiedSyntheticUniverse | B03Refusal | BlockingFailure:
    completed: list[AsOfSelectionResult] = []
    try:
        spec = request.specification
        require(
            type(spec.valid_from) is date
            and type(spec.valid_through) is date
            and spec == UniverseSpec(spec.valid_from, spec.valid_through)
            and spec.valid_from <= spec.valid_through,
            "INVALID_UNIVERSE_POLICY",
        )
        require(
            request.retained.code == code
            and semantic_bytes(request.retained)
            == semantic_bytes(UniverseReference(spec, request.requests, code)),
            "INVALID_UNIVERSE_POLICY",
        )
        subjects = [r.subject.subject_ref for r in request.requests]
        require(len(subjects) == len(set(subjects)), "DUPLICATE_UNIVERSE_MEMBER")
        if set(subjects) != {m[2] for m in spec.mapping}:
            return B03Refusal("UNQUALIFIED_UNIVERSE")
        if context.mode != "public":
            return B03Refusal("UNSUPPORTED_B03_OBSERVED_PROFILE")
        day = _instant(context.information_cutoff).date()
        reference = request.requests[0]
        members = []
        for entity, metric, subject_ref in spec.mapping:
            r = next(x for x in request.requests if x.subject.subject_ref == subject_ref)
            require(
                r.context.information_cutoff == context.information_cutoff
                and r.context.mode == context.mode
                and r.context.evidence_set_ref == context.evidence_set_ref
                and r.context.calendar_ref == context.calendar_ref
                and r.context.numeric_ref == context.numeric_ref
                and r.context.profile == context.profile
                and r.context.temporal_rule == context.temporal_rule
                and cohort(r) == cohort(reference)
                and r.context.profile.code_pins == code.observed_working_files
                and r.policy.evaluator_ref == B02_EVALUATOR_REF,
                "MIXED_UNIVERSE_CONTEXT",
            )
            s = r.subject
            for name, expected in (
                ("economic_entity_ref", spec.publisher),
                ("metric", metric),
                ("period_kind", "DURATION"),
                ("period_start", spec.valid_from),
                ("period_end", spec.valid_through),
                ("canonical_unit", "MEMBERSHIP_FLAG"),
                ("currency", "NOT_APPLICABLE"),
                ("reporting_scope", "synthetic_benchmark_policy"),
                ("basis_ref", "ALL_DATES_MEMBERSHIP_DECLARATION-v0.1"),
            ):
                fact = getattr(s, name)
                require(
                    isinstance(fact, Known) and fact.value == expected, "INVALID_MEMBERSHIP_SUBJECT"
                )
            require(
                r.policy.issuer_ref == spec.publisher
                and r.policy.source_refs == (spec.source_ref,),
                "INVALID_UNIVERSE_PUBLISHER",
            )
            actual = evaluate_asof(r, code)
            completed.append(actual)
            selection = actual.selection
            if isinstance(selection, BlockingFailure):
                return selection
            if selection.state != "SELECTED":
                return B03Refusal("UNQUALIFIED_UNIVERSE")
            require(
                type(selection.selected_value) is int and selection.selected_value in (0, 1),
                "INVALID_MEMBERSHIP_FLAG",
            )
            if selection.selected_value == 1:
                members.append(entity)
        # Publication eligibility and reference-span applicability are independent.
        if not spec.valid_from <= day <= spec.valid_through:
            return B03Refusal("UNIVERSE_OUTSIDE_VALIDITY")
        return QualifiedSyntheticUniverse(request, tuple(members), tuple(completed))
    except ContractError as exc:
        return failure(context, str(exc))
    except ZoneInfoNotFoundError:
        return zone_failure(context)


# New B03 owners below are deliberately separate from legacy A04/A05 definitions.


B03_CODE_PATHS = tuple(
    "src/pit_research_lab/domain/" + name + ".py"
    for name in ("causal_derivation", "causal_slice", "diagnostic_projection")
)
FEATURE_KEYS = (
    "derived_quarter_revenue",
    "quarter_revenue_proxy",
    "quarter_revenue_zscore",
    "third_month_share",
)
UNSUPPORTED = ("H1", "TTM", "RANK", "LAST_N_ELIGIBLE_OBSERVATIONS", "TARGET_ENCODING")
NO_STATE = NotApplicable("B03", "LABEL_FREE_OR_NO_FIT")
MISSING = NotEvaluated("B03", "NO_VALUE")
NUMERIC = "POPULATION_RATIONAL_DECIMAL50_HALF_EVEN6-v0.1"
type Value = int | FixedRatio | "FixedScalar6" | NotEvaluated


@dataclass(frozen=True)
class B03CodeObservation(Record):
    upstream_ratio: RatioCodeObservation
    extension_pins: tuple[CodePin, ...]
    extension_byte_lengths: tuple[int, ...]
    profile_ref: str = PROFILE


@dataclass(frozen=True)
class B03FeatureSpec(Record):
    key: str
    version: str = "v0.1"
    definition_ref: str = "B03-FIXED-SEMANTICS-v0.1"


@dataclass(frozen=True)
class SumRequest(Record):
    specification: FeatureSpec
    slots: tuple[DependencySlot, ...]


@dataclass(frozen=True)
class DecisionRow(Record):
    entity_id: str
    sum_request: SumRequest
    ratio_specification: RatioFeatureSpec


@dataclass(frozen=True)
class TrainingRow(Record):
    row_ref: str
    historical: SumRequest
    fit_time: SumRequest


@dataclass(frozen=True)
class FitReference(Record):
    rows: tuple[TrainingRow, ...]
    view: str
    context: SemanticContext
    code: B03CodeObservation


@dataclass(frozen=True)
class StandardizerRequest(Record):
    rows: tuple[TrainingRow, ...]
    view: str
    context: SemanticContext
    retained: FitReference
    numerical_policy: str = NUMERIC
    labels: NotApplicable | tuple[str, ...] = NO_STATE


@dataclass(frozen=True)
class FixedScalar6(Record):
    scaled_units: int
    decimal_text: str

    def __post_init__(self) -> None:
        super().__post_init__()
        require(
            type(self.scaled_units) is int and -(2**63) <= self.scaled_units < 2**63,
            "INVALID_SCALED_INT64",
        )
        require(self.decimal_text == scalar_text(self.scaled_units), "NONCANONICAL_SCALAR")


@dataclass(frozen=True)
class B03Outcome(Record):
    state: DerivedState
    value: Value = MISSING
    reason: str = "NONE"
    failures: tuple[BlockingFailure, ...] = ()


@dataclass(frozen=True)
class FrozenStandardizer(Record):
    request: StandardizerRequest
    mean: tuple[int, int]
    variance: tuple[int, int]
    sigma50: str
    state_ref: str


@dataclass(frozen=True)
class FitEvaluation(Record):
    inputs: tuple[DerivedResult, ...]
    outcome: FrozenStandardizer | B03Outcome | B03Refusal | BlockingFailure


@dataclass(frozen=True)
class PlanNode(Record):
    ref: str
    kind: str


@dataclass(frozen=True)
class CausalPlan(Record):
    nodes: tuple[PlanNode, ...]
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CausalReference(Record):
    context: SemanticContext
    specifications: tuple[B03FeatureSpec, ...]
    rows: tuple[DecisionRow, ...]
    fit: StandardizerRequest | NotApplicable
    universe: UniverseRequest
    code: B03CodeObservation
    period_bindings: tuple[tuple[str, int, int], ...]
    allowed_missing: tuple[str, ...] = FEATURE_KEYS


@dataclass(frozen=True)
class B03Request(Record):
    context: SemanticContext
    specifications: tuple[B03FeatureSpec, ...]
    rows: tuple[DecisionRow, ...]
    fit: StandardizerRequest | NotApplicable
    universe: UniverseRequest
    plan: CausalPlan
    retained: CausalReference
    period_bindings: tuple[tuple[str, int, int], ...]
    window: str = "LAST_N_REFERENCE_PERIODS_3"
    proxy_constant: int = 1_000_000
    evaluator_ref: str = PROFILE
    allowed_missing: tuple[str, ...] = FEATURE_KEYS


@dataclass(frozen=True)
class RowResult(Record):
    entity_id: str
    summed: DerivedResult
    ratio: RatioResult
    features: tuple[tuple[str, B03Outcome], ...]
    proxy_branch: str


@dataclass(frozen=True)
class B03Result(Record):
    request: B03Request
    code: B03CodeObservation
    rows: tuple[RowResult, ...]
    fit: FitEvaluation | NotApplicable
    universe: QualifiedSyntheticUniverse | B03Refusal | BlockingFailure
    source_results: tuple[AsOfSelectionResult, ...]
    exact_population: tuple[str, ...] | NotEvaluated
    proxy_population: tuple[str, ...] | NotEvaluated
    failures: tuple[BlockingFailure, ...]
    realization_ref: str
    research_only_audit: tuple[str, ...] = ()
    admission_eligible: bool = field(default=False, init=False)
    diagnostic_only: bool = field(default=True, init=False)
    admission_state: str = field(default="WITHHELD", init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)


def scalar_text(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) // 1_000_000}.{abs(value) % 1_000_000:06d}"


def _numeric_context() -> Context:
    return Context(
        prec=50,
        rounding=ROUND_HALF_EVEN,
        Emin=-999,
        Emax=999,
        traps=[InvalidOperation, DivisionByZero, Overflow, FloatOperation],
    )


def _json_value(value: object) -> object:
    """Audit/identity canonicalization only. NEVER a candidate serializer."""
    if is_dataclass(value) and not isinstance(value, type):
        result = {}
        set_fields = {
            "rows",
            "specifications",
            "period_bindings",
            "nodes",
            "edges",
            "slots",
            "candidates",
            "relations",
            "checks",
            "evaluated_candidate_refs",
            "evaluated_relation_refs",
            "source_refs",
            "provider_refs",
            "policy_refs",
            "input_members",
            "raw_pins",
            "requests",
            "leads",
            "exclusions",
        }
        for f in fields(value):
            if f.name in {
                "research_only_audit",
                "annotations",
                "decision_wall_times",
                "computation_attempt_time",
            }:
                continue
            item = _json_value(getattr(value, f.name))
            if f.name in set_fields and isinstance(item, list):
                item = sorted(item, key=lambda v: json.dumps(v, sort_keys=True))
            result[f.name] = item
        return result
    if isinstance(value, tuple):
        return [_json_value(v) for v in value]
    if isinstance(value, bytes):
        return {"retained_bytes_hex": value.hex()}
    if isinstance(value, date):
        return value.isoformat()
    return value


def semantic_bytes(value: object) -> bytes:
    return json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def identity(value: object) -> str:
    return "B03-" + sha256(semantic_bytes(value)).hexdigest()


def validate_code(code: B03CodeObservation, expected: B03CodeObservation) -> None:
    require(code == expected and code.profile_ref == PROFILE, "B03_CODE_REFERENCE_MISMATCH")
    require(
        tuple(p.path for p in code.extension_pins) == B03_CODE_PATHS, "INVALID_B03_EXTENSION_PATHS"
    )
    require(
        len(code.extension_byte_lengths) == 3
        and all(type(n) is int and n > 0 for n in code.extension_byte_lengths),
        "INVALID_B03_CODE_LENGTHS",
    )


def check_plan(plan: CausalPlan) -> None:
    refs = tuple(n.ref for n in plan.nodes)
    require(len(refs) == len(set(refs)), "DUPLICATE_PLAN_NODE")
    require(len([n for n in plan.nodes if n.kind != "SOURCE"]) <= 20, "S4_NODE_LIMIT")
    require(len([n for n in plan.nodes if n.kind == "SOURCE"]) <= 40, "S3_REQUEST_LIMIT")
    require(len(plan.edges) <= 64, "EDGE_LIMIT")
    require(len(plan.edges) == len(set(plan.edges)), "DUPLICATE_PLAN_EDGE")
    require(all(a in refs and b in refs for a, b in plan.edges), "MISSING_PLAN_NODE")
    children: dict[str, list[str]] = {r: [] for r in refs}
    parents: dict[str, list[str]] = {r: [] for r in refs}
    for a, b in plan.edges:
        children[a].append(b)
        parents[b].append(a)
    visiting: set[str] = set()
    depths: dict[str, int] = {}

    def depth(node: str) -> int:
        require(node not in visiting, "DEPENDENCY_CYCLE")
        if node in depths:
            return depths[node]
        visiting.add(node)
        value = max((depth(p) + 1 for p in parents[node]), default=0)
        visiting.remove(node)
        depths[node] = value
        return value

    for ref in refs:
        depth(ref)
    require(max(depths.values(), default=0) <= 4, "DEPTH_LIMIT")
    require(all(len(v) <= 9 for v in parents.values()), "FAN_IN_LIMIT")
    require(all(len(v) <= 8 for v in children.values()), "FAN_OUT_LIMIT")


def selected_training(request: StandardizerRequest) -> tuple[SumRequest, ...]:
    return tuple(
        r.historical if request.view == "HISTORICAL_OBSERVATION_VIEW" else r.fit_time
        for r in sorted(
            request.rows,
            key=lambda row: (
                _instant(row.historical.slots[0].request.context.information_cutoff),
                row.historical.specification.issuer_ref,
                row.row_ref,
            ),
        )
    )


def source_requests(request: B03Request) -> tuple[AsOfRequest, ...]:
    sums = tuple(r.sum_request for r in request.rows)
    if isinstance(request.fit, StandardizerRequest):
        sums += selected_training(request.fit)
    return tuple(
        sorted(
            dict.fromkeys(
                [s.request for r in sums for s in r.slots] + list(request.universe.requests)
            ),
            key=identity,
        )
    )


def required_plan(request: B03Request) -> CausalPlan:
    """Fixed composition, not caller code or a DAG runtime."""
    nodes: dict[str, str] = {}
    edges: set[tuple[str, str]] = set()

    def node(ref: str, kind: str) -> str:
        require(ref not in nodes or nodes[ref] == kind, "PLAN_IDENTITY_COLLISION")
        nodes[ref] = kind
        return ref

    def summed(s: SumRequest) -> str:
        ref = node("sum:" + identity(s), "SUM")
        for slot in s.slots:
            leaf = node("source:" + identity(slot.request), "SOURCE")
            edges.add((leaf, ref))
        return ref

    fit_ref = ""
    if isinstance(request.fit, StandardizerRequest):
        fit_ref = node("fit", "FIT")
        for r in selected_training(request.fit):
            edges.add((summed(r), fit_ref))
    u = node("universe", "UNIVERSE")
    for membership in request.universe.requests:
        edges.add((node("source:" + identity(membership), "SOURCE"), u))
    p = node("projection", "PROJECT")
    edges.add((u, p))
    for row in sorted(request.rows, key=lambda r: r.entity_id):
        s = summed(row.sum_request)
        for spec in request.specifications:
            if spec.key == "derived_quarter_revenue":
                value = s
            else:
                value = node(row.entity_id + ":" + spec.key, spec.key)
                edges.add((s, value))
                if spec.key == "quarter_revenue_zscore" and fit_ref:
                    edges.add((fit_ref, value))
            edges.add((value, p))
    return CausalPlan(tuple(PlanNode(k, v) for k, v in sorted(nodes.items())), tuple(sorted(edges)))


def check_sources(requests: tuple[AsOfRequest, ...]) -> None:
    bodies: dict[tuple[str, str], object] = {}
    distinct: dict[bytes, int] = {}
    require(len(requests) <= 40, "S3_REQUEST_LIMIT")
    for r in requests:
        sources = list(r.candidates)
        sources += [x.notice for x in r.relations if not isinstance(x.notice, NotEvaluated)]
        if isinstance(r.discovery, DiscoveryEvidence):
            sources += [x.notice for x in r.discovery.leads]
            sources += [x.source for x in r.discovery.exclusions]
        for c in sources:
            body = c.request.content
            require(body.raw_length <= 65536, "RAW_BODY_LIMIT")
            distinct[body.raw_bytes] = len(body.raw_bytes)
            for kind, ref, signature in (
                ("content", body.content_version_ref, body),
                ("representation", body.representation_ref, body),
                ("assertion", c.request.requested.target_ref, c.request),
            ):
                key = (kind, ref)
                require(
                    key not in bodies or bodies[key] == signature,
                    "CONTRADICTORY_IMMUTABLE_IDENTITY",
                )
                bodies[key] = signature
    require(sum(distinct.values()) <= 1048576, "TOTAL_RAW_BODY_LIMIT")


def _check_role_cutoff(context: SemanticContext, reason: str) -> None:
    """B03 role policy only; S2 still owns instant interpretation and evidence."""
    cutoff = context.information_cutoff
    moment = _instant(cutoff)
    require(
        moment.hour == moment.minute == moment.second == 0
        and cutoff.timezone_name == "Asia/Taipei"
        and cutoff.offset == "+08:00",
        reason,
    )


def _check_fit_cutoffs(request: StandardizerRequest, decision: SemanticContext) -> None:
    _check_role_cutoff(decision, "INVALID_DECISION_CUTOFF")
    _check_role_cutoff(request.context, "INVALID_FIT_CUTOFF")
    require(
        all(len(s.slots) == 3 for row in request.rows for s in (row.historical, row.fit_time)),
        "INVALID_FIT_ROW_SLOTS",
    )
    for row in request.rows:
        for slot in row.historical.slots:
            _check_role_cutoff(slot.request.context, "INVALID_HISTORICAL_OBSERVATION_CUTOFF")
        for slot in row.fit_time.slots:
            _check_role_cutoff(slot.request.context, "INVALID_FIT_CUTOFF")


def _fit_completed(
    request: StandardizerRequest,
    code: B03CodeObservation,
    decision: SemanticContext,
    inputs: tuple[DerivedResult, ...],
) -> FrozenStandardizer | B03Outcome | B03Refusal | BlockingFailure:
    try:
        validate_code(code, request.retained.code)
        require(
            semantic_bytes(request.retained)
            == semantic_bytes(FitReference(request.rows, request.view, request.context, code)),
            "FIT_REFERENCE_MISMATCH",
        )
        require(request.numerical_policy == NUMERIC, "INVALID_FIT_NUMERICAL_POLICY")
        if request.labels != NO_STATE:
            return B03Refusal("UNSUPPORTED_FIT_FAMILY")
        if request.view not in {
            "HISTORICAL_OBSERVATION_VIEW",
            "FIT_TIME_AVAILABLE_HISTORICAL_DATA_VIEW",
        }:
            return B03Refusal("UNSUPPORTED_TRAINING_VIEW")
        if request.context.mode != "public" or decision.mode != "public":
            return B03Refusal("UNSUPPORTED_B03_OBSERVED_PROFILE")
        if len(request.rows) < 2:
            return B03Refusal("INSUFFICIENT_FIT_ROWS")
        require(len(request.rows) <= 8, "FIT_ROW_LIMIT")
        _check_fit_cutoffs(request, decision)
        first = min(
            request.rows,
            key=lambda r: (
                _instant(r.historical.slots[0].request.context.information_cutoff),
                r.historical.specification.issuer_ref,
                r.row_ref,
            ),
        )
        require(
            semantic_bytes(request.context)
            == semantic_bytes(first.fit_time.slots[0].request.context),
            "FIT_CONTEXT_REFERENCE_MISMATCH",
        )
        refs = [r.row_ref for r in request.rows]
        require(len(refs) == len(set(refs)), "DUPLICATE_FIT_ROW")
        row_keys = [
            (
                r.historical.specification.issuer_ref,
                r.historical.slots[0].request.context.information_cutoff.source_text,
            )
            for r in request.rows
        ]
        require(len(row_keys) == len(set(row_keys)), "DUPLICATE_FIT_OBSERVATION")
        fit_time = _instant(request.context.information_cutoff)
        if fit_time > _instant(decision.information_cutoff):
            return B03Refusal("FUTURE_DEPENDENCY")
        for row in request.rows:
            historical = row.historical
            observed = historical.slots[0].request
            at_fit = row.fit_time.slots[0].request
            require(historical.specification == row.fit_time.specification, "FIT_ROW_SPEC_MISMATCH")
            require(cohort(observed) == cohort(at_fit), "MIXED_FIT_CONTEXT")
            require(
                _instant(at_fit.context.information_cutoff) == fit_time, "FIT_VIEW_CUTOFF_MISMATCH"
            )
            require(
                at_fit.context.mode == request.context.mode
                and at_fit.context.evidence_set_ref == request.context.evidence_set_ref
                and at_fit.context.calendar_ref == request.context.calendar_ref
                and at_fit.context.numeric_ref == request.context.numeric_ref
                and at_fit.context.profile == request.context.profile
                and at_fit.context.temporal_rule == request.context.temporal_rule,
                "MIXED_FIT_CONTEXT",
            )
            for old, new in zip(historical.slots, row.fit_time.slots, strict=True):
                require(
                    old.request.candidates == new.request.candidates
                    and old.request.relations == new.request.relations
                    and old.expected_subject == new.expected_subject,
                    "FIT_VIEW_SOURCE_MISMATCH",
                )
            t = _instant(observed.context.information_cutoff)
            if t > fit_time or t >= _instant(decision.information_cutoff):
                return B03Refusal("FUTURE_DEPENDENCY")
        replay = tuple(
            evaluate_derived(s.specification, s.slots, code.upstream_ratio.upstream_a04)
            for s in selected_training(request)
        )
        require(semantic_bytes(inputs) == semantic_bytes(replay), "COMPLETED_FIT_OWNER_MISMATCH")
        faults = tuple(f for result in inputs for f in result.outcome.upstream_failures)
        if faults:
            return next((f for f in faults if f.category == "CONTRACT_VIOLATION"), faults[0])
        for result in inputs:
            if result.outcome.state in {"CONTRACT_VIOLATION", "OPERATIONAL_ERROR"}:
                return failure(decision, result.outcome.reason)
        if any(r.outcome.state != "VALUE_AVAILABLE" for r in inputs):
            return B03Refusal("UNQUALIFIED_STATE")
        values = tuple(r.outcome.value for r in inputs)
        require(all(type(x) is int for x in values), "INVALID_FIT_INTEGER")
        numbers = tuple(x for x in values if type(x) is int)
        require(len(numbers) == len(request.rows), "FIT_ROW_COUNT_MISMATCH")
        mean = Fraction(sum(numbers), len(numbers))
        variance = sum(
            ((Fraction(x) - mean) * (Fraction(x) - mean) for x in numbers), Fraction(0)
        ) / len(numbers)
        if variance == 0:
            return B03Outcome("NOT_COMPUTABLE", reason="ZERO_TRAINING_VARIANCE")
        with localcontext(_numeric_context()):
            sigma = (Decimal(variance.numerator) / Decimal(variance.denominator)).sqrt()
        return FrozenStandardizer(
            request,
            (mean.numerator, mean.denominator),
            (variance.numerator, variance.denominator),
            str(sigma),
            identity((request, tuple(r.realization_ref for r in inputs))),
        )
    except ContractError as exc:
        return failure(decision, str(exc))
    except ZoneInfoNotFoundError:
        return zone_failure(decision)
    except DecimalException:
        return failure(decision, "FIT_NUMERICAL_FAILURE")


def _standardize(value: int, state: FrozenStandardizer) -> FixedScalar6:
    """Numeric kernel only; the owner must first replay and qualify fitted state."""
    require(type(value) is int and -(2**63) <= value < 2**63, "INVALID_FIT_INTEGER")
    with localcontext(_numeric_context()):
        mean = Decimal(state.mean[0]) / Decimal(state.mean[1])
        z = ((Decimal(value) - mean) / Decimal(state.sigma50)).quantize(Decimal("0.000001"))
        scaled = int(z * 1_000_000)
    return FixedScalar6(scaled, scalar_text(scaled))


def label_eligibility(
    row_cutoff: SemanticContext,
    label_request: AsOfRequest,
    fit_context: SemanticContext,
    code: CodeObservation,
    *,
    own_row_encoding: bool = False,
) -> B03Refusal | AsOfSelectionResult | BlockingFailure:
    """Four calendar weeks; maturity guard only, no supervised fitting."""
    from datetime import timedelta

    try:
        _check_role_cutoff(row_cutoff, "INVALID_HISTORICAL_OBSERVATION_CUTOFF")
        _check_role_cutoff(fit_context, "INVALID_FIT_CUTOFF")
        row_time = _instant(row_cutoff.information_cutoff)
        fit_time = _instant(fit_context.information_cutoff)
        horizon = row_time + timedelta(weeks=4)
        if horizon >= fit_time:
            return B03Refusal("IMMATURE_LABEL")
        require(label_request.context == fit_context, "LABEL_CONTEXT_MISMATCH")
        subject = label_request.subject
        for name, expected in (
            ("metric", "FORWARD_FOUR_WEEK_LABEL"),
            ("canonical_unit", "LABEL_UNITS"),
            ("currency", "NOT_APPLICABLE"),
            ("reporting_scope", "synthetic_label_guard"),
            ("basis_ref", "FOUR_WEEK_BINARY_OUTCOME-v0.1"),
            ("period_start", row_time.date()),
            ("period_end", horizon.date()),
        ):
            fact = getattr(subject, name)
            require(isinstance(fact, Known) and fact.value == expected, "INVALID_LABEL_SUBJECT")
        actual = evaluate_asof(label_request, code)
        if isinstance(actual.selection, BlockingFailure):
            return actual.selection
        if actual.selection.state != "SELECTED":
            return B03Refusal("UNQUALIFIED_LABEL")
        require(
            type(actual.selection.selected_value) is int
            and actual.selection.selected_value in (0, 1),
            "INVALID_LABEL_VALUE",
        )
        from pit_research_lab.domain.contracts import TimeProof

        for leaf in actual.inputs.candidates:
            if leaf.ref in actual.selection.selected_assertion_refs:
                s2 = leaf.actual.s2
                if isinstance(s2, BlockingFailure):
                    return s2
                proof = s2.evaluated_evidence
                if not isinstance(proof, TimeProof):
                    return B03Refusal("UNSUPPORTED_LABEL_TIME_PROFILE")
                if _instant(proof.timestamp) < horizon:
                    return B03Refusal("IMMATURE_LABEL")
        if own_row_encoding:
            return B03Refusal("WITHIN_SAMPLE_TARGET_LEAKAGE")
        return actual
    except ContractError as exc:
        return failure(fit_context, str(exc))
    except ZoneInfoNotFoundError:
        return zone_failure(fit_context)
