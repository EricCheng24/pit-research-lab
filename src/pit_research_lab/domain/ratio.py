"""A05 bounded M3 / actual A04 sum; no source trust or observation admission."""

import json
from dataclasses import dataclass, field, replace
from hashlib import sha256
from typing import Literal

from pit_research_lab.domain.contracts import (
    BlockingFailure,
    CodePin,
    ContractError,
    NotApplicable,
    NotEvaluated,
    Record,
    identifier,
    require,
)
from pit_research_lab.domain.derivation import (
    S4_CODE_PATHS,
    DependencySlot,
    DerivedResult,
    DerivedState,
    FeatureSpec,
)
from pit_research_lab.domain.derived_slice import evaluate_derived
from pit_research_lab.domain.pit_slice import CODE_PATHS, CodeObservation
from pit_research_lab.domain.selection import S3_CODE_PATHS, SelectionOutcome

EVALUATOR_REF = "s4-a05-third-month-share-v0.1-CANDIDATE"
NUMERICAL_POLICY = "FIXED_SIX_DECIMAL_FRACTION_HALF_EVEN-v0.1"
RATIO_CODE_PATHS = (
    "src/pit_research_lab/domain/ratio.py",
    "src/pit_research_lab/domain/ratio_slice.py",
)
NO_EXTRA_DEPENDENCIES = NotApplicable("S4-A05", "NO_STATE_LABEL_WINDOW_POPULATION_FALLBACK")


@dataclass(frozen=True)
class RatioFeatureSpec(Record):
    feature_ref: str
    prior_derived_sum_ref: str
    issuer_ref: str
    year: int
    quarter: int
    transformation_ref: str = "THIRD_MONTH_OVER_ACTUAL_QUARTER_SUM-v0.1"
    output_meaning: str = "THIRD_MONTH_SHARE_OF_DERIVED_QUARTER"
    numerator_role: str = "M3"
    denominator_relation: str = "ACTUAL_A04_QUARTER_SUM"
    unit: str = "FRACTION"
    scale: int = 6
    domain_policy: str = "NONNEGATIVE_MONTHS_POSITIVE_SUM_OR_DOMAIN_MISSING-v0.1"
    numerical_policy: str = NUMERICAL_POLICY
    preview_policy: str = "RESEARCH_DIAGNOSTIC_VALUE_OR_TYPED_MISSING-v0.1"
    extra_dependencies: NotApplicable | tuple[str, ...] = NO_EXTRA_DEPENDENCIES
    evaluator_ref: str = EVALUATOR_REF


@dataclass(frozen=True)
class RatioCodeObservation(Record):
    upstream_a04: CodeObservation
    extension_pins: tuple[CodePin, ...]
    extension_byte_lengths: tuple[int, ...]
    interpretation: str = field(
        default="OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION", init=False
    )
    verification_scope: str = field(
        default="STRUCTURE_AND_COHERENCE_ONLY; SUPPLIED_OBSERVATIONS_NOT_RUNTIME_ATTESTED",
        init=False,
    )


@dataclass(frozen=True)
class FixedRatio(Record):
    scaled_units: int
    decimal_text: str
    scale: Literal[6] = 6
    unit: Literal["FRACTION"] = "FRACTION"
    numerical_policy: str = NUMERICAL_POLICY

    def __post_init__(self) -> None:
        super().__post_init__()
        require(
            type(self.scaled_units) is int and 0 <= self.scaled_units <= 1_000_000,
            "INVALID_SCALED_FRACTION",
        )
        require(
            type(self.scale) is int
            and self.scale == 6
            and self.unit == "FRACTION"
            and self.numerical_policy == NUMERICAL_POLICY,
            "INVALID_FIXED_RATIO_POLICY",
        )
        require(self.decimal_text == _decimal_text(self.scaled_units), "NONCANONICAL_FIXED_RATIO")


@dataclass(frozen=True)
class RatioOutcome(Record):
    state: DerivedState
    reason: str
    value: FixedRatio | NotEvaluated
    upstream_failures: tuple[BlockingFailure, ...]


@dataclass(frozen=True)
class RatioResearchAudit(Record):
    numerator: int | NotEvaluated
    denominator: int | NotEvaluated
    exact_fraction: tuple[int, int] | NotEvaluated
    upstream_reason: str | NotEvaluated
    annotations: tuple[str, ...]


@dataclass(frozen=True)
class RatioResult(Record):
    specification: RatioFeatureSpec
    upstream_a04: DerivedResult | NotEvaluated
    code: RatioCodeObservation
    outcome: RatioOutcome
    realization_ref: str | NotEvaluated
    diagnostic_preview_bytes: bytes | NotEvaluated
    research_only_audit: RatioResearchAudit
    origin_kind: Literal["DERIVED"] = field(default="DERIVED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _decimal_text(scaled: int) -> str:
    return f"{scaled // 1_000_000}.{scaled % 1_000_000:06d}"


def _fixed_ratio(numerator: int, denominator: int) -> FixedRatio:
    """Internal math only; callers must first establish actual owner lineage."""
    require(
        type(numerator) is int
        and type(denominator) is int
        and 0 <= numerator <= denominator < 2**63
        and denominator > 0,
        "INVALID_EXACT_SHARE_OPERANDS",
    )
    quotient, remainder = divmod(numerator * 1_000_000, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and quotient % 2 == 1):
        quotient += 1
    return FixedRatio(quotient, _decimal_text(quotient))


def _validate_request(
    spec: RatioFeatureSpec,
    sum_spec: FeatureSpec,
    slots: tuple[DependencySlot, ...],
    code: RatioCodeObservation,
) -> None:
    identifier(spec.feature_ref)
    require(
        type(spec.year) is int and type(spec.quarter) is int and type(spec.scale) is int,
        "INVALID_RATIO_SPEC_TYPES",
    )
    expected = RatioFeatureSpec(
        spec.feature_ref, sum_spec.feature_ref, sum_spec.issuer_ref, sum_spec.year, sum_spec.quarter
    )
    require(spec == expected, "UNSUPPORTED_RATIO_FEATURE_CONTRACT")
    require(spec.feature_ref != sum_spec.feature_ref, "RATIO_SUM_IDENTITY_COLLISION")
    for slot in slots:
        sources = list(slot.request.candidates)
        sources.extend(
            r.notice for r in slot.request.relations if not isinstance(r.notice, NotEvaluated)
        )
        for source in sources:
            r = source.request
            require(
                spec.feature_ref
                not in {
                    r.requested.target_ref,
                    r.content.content_version_ref,
                    r.content.representation_ref,
                },
                "RATIO_SOURCE_IDENTITY_COLLISION",
            )
    upstream = code.upstream_a04
    require(
        tuple(pin.path for pin in upstream.observed_working_files)
        == (*CODE_PATHS, *S3_CODE_PATHS, *S4_CODE_PATHS),
        "INVALID_UPSTREAM_TEN_PATH_OBSERVATION",
    )
    require(
        tuple(pin.path for pin in code.extension_pins) == RATIO_CODE_PATHS,
        "INVALID_RATIO_EXTENSION_PATHS",
    )
    for pins, lengths in (
        (upstream.observed_working_files, upstream.byte_lengths),
        (code.extension_pins, code.extension_byte_lengths),
    ):
        require(
            len(pins) == len(lengths) and all(type(n) is int and n >= 0 for n in lengths),
            "INVALID_CODE_BYTE_LENGTHS",
        )
    require(all(n > 0 for n in code.extension_byte_lengths), "EMPTY_RATIO_CODE_OBSERVATION")
    require(upstream.interpretation == code.interpretation, "INVALID_CODE_INTERPRETATION")


def _semantic_upstream(upstream: DerivedResult) -> DerivedResult:
    """Remove only research annotations for consistency comparison, not evidence."""
    dependencies = []
    for dependency in upstream.dependencies:
        selection = dependency.actual.selection
        actual = dependency.actual
        if isinstance(selection, SelectionOutcome):
            actual = replace(actual, selection=replace(selection, research_only_audit=()))
        dependencies.append(replace(dependency, actual=actual))
    return replace(upstream, dependencies=tuple(dependencies), research_only_audit=())


def _finish(
    spec: RatioFeatureSpec,
    code: RatioCodeObservation,
    upstream: DerivedResult | NotEvaluated,
    outcome: RatioOutcome,
    numerator: int | NotEvaluated,
    denominator: int | NotEvaluated,
    annotations: tuple[str, ...],
) -> RatioResult:
    unavailable = NotEvaluated("S4-A05", "NO_EXACT_FRACTION")
    audit = RatioResearchAudit(
        numerator,
        denominator,
        (numerator, denominator)
        if type(numerator) is int and type(denominator) is int and denominator != 0
        else unavailable,
        upstream.outcome.reason if isinstance(upstream, DerivedResult) else unavailable,
        annotations,
    )
    preview: bytes | NotEvaluated = NotEvaluated("S4-A05", "DIAGNOSTIC_PREVIEW_WITHHELD")
    realization: str | NotEvaluated = NotEvaluated("S4-A05", "NO_REALIZATION")
    if outcome.state in {"VALUE_AVAILABLE", "NOT_COMPUTABLE"}:
        assert isinstance(upstream, DerivedResult)
        context = upstream.dependencies[0].slot.request.context
        preview = _canonical(
            {
                "preview_kind": "RESEARCH_DIAGNOSTIC_ONLY",
                "feature_ref": spec.feature_ref,
                "cutoff": context.information_cutoff.source_text,
                "mode": context.mode,
                "value": outcome.value.decimal_text
                if isinstance(outcome.value, FixedRatio)
                else None,
                "unit": "FRACTION",
                "scale": 6,
                "absence": outcome.reason if outcome.state == "NOT_COMPUTABLE" else None,
                "disposition": "INTEGRATED_PROVISIONAL",
                "trust": "NOT_TRUSTED_PIT_EVIDENCE",
                "source_authentication": "NOT_ESTABLISHED",
                "admission_eligible": False,
                "diagnostic_only": True,
            }
        )
        identity = (
            spec.feature_ref,
            spec.prior_derived_sum_ref,
            spec.issuer_ref,
            spec.year,
            spec.quarter,
            spec.transformation_ref,
            spec.domain_policy,
            spec.numerical_policy,
            spec.preview_policy,
            spec.evaluator_ref,
            upstream.realization_ref,
            preview.decode(),
            numerator if isinstance(numerator, int) else None,
            denominator if isinstance(denominator, int) else None,
            tuple(
                (p.path, p.sha256, n)
                for p, n in zip(
                    (*code.upstream_a04.observed_working_files, *code.extension_pins),
                    (*code.upstream_a04.byte_lengths, *code.extension_byte_lengths),
                    strict=True,
                )
            ),
        )
        realization = "DERIVED-RATIO-REALIZATION-" + sha256(_canonical(identity)).hexdigest()
    return RatioResult(spec, upstream, code, outcome, realization, preview, audit)


def _contract_failure(
    spec: RatioFeatureSpec,
    code: RatioCodeObservation,
    reason: str,
    upstream: DerivedResult | NotEvaluated,
) -> RatioResult:
    missing = NotEvaluated("S4-A05", "NO_RATIO_VALUE")
    faults = upstream.outcome.upstream_failures if isinstance(upstream, DerivedResult) else ()
    return _finish(
        spec,
        code,
        upstream,
        RatioOutcome("CONTRACT_VIOLATION", reason, missing, faults),
        missing,
        missing,
        (),
    )


def _evaluate_completed(
    spec: RatioFeatureSpec,
    sum_spec: FeatureSpec,
    slots: tuple[DependencySlot, ...],
    code: RatioCodeObservation,
    upstream: DerivedResult,
    *,
    annotations: tuple[str, ...] = (),
) -> RatioResult:
    """Internal seam checks equality to A04 replay, never trusts supplied success.

    Audit annotations are retained separately and never drive numeric branches,
    preview bytes or realization identity. Original upstream objects are retained.
    """
    missing = NotEvaluated("S4-A05", "NO_RATIO_VALUE")
    try:
        _validate_request(spec, sum_spec, slots, code)
        replay = evaluate_derived(sum_spec, slots, code.upstream_a04)
        require(
            _semantic_upstream(upstream) == _semantic_upstream(replay),
            "FORGED_OR_MISMAPPED_A04_RESULT",
        )
        original = upstream.outcome
        if original.state != "VALUE_AVAILABLE":
            reason = (
                "UPSTREAM_REQUIRED_INPUT_ABSENT"
                if original.state == "NOT_COMPUTABLE"
                else original.reason
            )
            outcome = RatioOutcome(original.state, reason, missing, original.upstream_failures)
            return _finish(spec, code, upstream, outcome, missing, missing, annotations)
        lineage = original.lineage
        require(
            tuple(item.slot_ref for item in lineage) == ("M1", "M2", "M3"), "INVALID_RATIO_LINEAGE"
        )
        require(
            type(original.value) is int
            and -(2**63) <= original.value < 2**63
            and all(type(item.value) is int and -(2**63) <= item.value < 2**63 for item in lineage),
            "INVALID_EXACT_UPSTREAM_INTEGER",
        )
        assert isinstance(original.value, int)
        denominator, numerator = original.value, lineage[2].value
        require(
            sum(item.value for item in lineage) == denominator, "CONTRADICTORY_ACTUAL_DENOMINATOR"
        )
        if any(item.value < 0 for item in lineage):
            outcome = RatioOutcome(
                "NOT_COMPUTABLE", "NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN", missing, ()
            )
        elif denominator == 0:
            outcome = RatioOutcome(
                "NOT_COMPUTABLE", "ZERO_QUARTER_REVENUE_DENOMINATOR", missing, ()
            )
        else:
            outcome = RatioOutcome(
                "VALUE_AVAILABLE", "NONE", _fixed_ratio(numerator, denominator), ()
            )
        return _finish(spec, code, upstream, outcome, numerator, denominator, annotations)
    except ContractError as exc:
        return _contract_failure(spec, code, str(exc), upstream)
