"""A04 exact three-month flow sum; conditional engineering analysis only.

Completed transport is checked by replaying the existing A03 owner, never by a
second selector. This is consistency checking, not independent attestation.
Only the research audit may retain upstream reasons or post-cutoff notices.
"""

import calendar
import json
from dataclasses import dataclass, field, replace
from datetime import date
from hashlib import sha256
from typing import Literal

from pit_research_lab.domain.asof_slice import AsOfRequest, evaluate_asof
from pit_research_lab.domain.contracts import (
    BlockingFailure,
    ContractError,
    IssuerBindingRequest,
    Known,
    NotApplicable,
    NotEvaluated,
    Record,
    SubjectFacts,
    require,
)
from pit_research_lab.domain.pit_slice import CODE_PATHS, CodeObservation
from pit_research_lab.domain.selection import (
    S3_CODE_PATHS,
    AsOfSelectionResult,
    SelectionOutcome,
)

EVALUATOR_REF = "s4-a04-monthly-int64-sum-v0.1-CANDIDATE"
S4_CODE_PATHS = (
    "src/pit_research_lab/domain/derivation.py",
    "src/pit_research_lab/domain/derived_slice.py",
)
NO_EXTRA_DEPENDENCIES = NotApplicable("S4", "NO_STATE_WINDOW_POPULATION_FALLBACK_LABEL")
type DerivedState = Literal[
    "VALUE_AVAILABLE", "UNRESOLVED", "NOT_COMPUTABLE", "CONTRACT_VIOLATION", "OPERATIONAL_ERROR"
]


@dataclass(frozen=True)
class FeatureSpec(Record):
    feature_ref: str
    year: int
    quarter: int
    issuer_ref: str
    transformation_ref: str = "MONTHLY_DURATION_SUM-v0.1"
    policy_ref: str = "A04-FIXED-ISSUER-QUARTER-v0.1"
    output_metric: str = "DERIVED_QUARTER_REVENUE"
    input_metric: str = "net_operating_revenue"
    period_kind: str = "DURATION"
    reporting_scope: str = "consolidated"
    basis_ref: str = "BASIS-CONSOLIDATED-V1"
    currency: str = "NTD"
    canonical_unit: str = "NTD_thousands"
    aggregation: str = "THREE_DISTINCT_CALENDAR_MONTH_FLOWS"
    numerical_policy: str = "EXACT_SIGNED_INT64_NO_CONVERSION-v0.1"
    preview_policy: str = "DIAGNOSTIC_VALUE_OR_BOUNDED_NULL-v0.1"
    extra_dependencies: NotApplicable | tuple[str, ...] = NO_EXTRA_DEPENDENCIES


@dataclass(frozen=True)
class DependencySlot(Record):
    slot_ref: str
    expected_subject: SubjectFacts
    request: AsOfRequest


@dataclass(frozen=True)
class CompletedDependency(Record):
    slot: DependencySlot
    actual: AsOfSelectionResult


@dataclass(frozen=True)
class InputLineage(Record):
    slot_ref: str
    subject_ref: str
    period: tuple[date, date]
    unit: str
    value: int
    assertion_refs: tuple[str, ...]
    content_version_refs: tuple[str, ...]
    representation_refs: tuple[str, ...]
    raw_sha256s: tuple[str, ...]


@dataclass(frozen=True)
class DependencyDiagnostic(Record):
    slot_ref: str
    context_ref: str
    upstream: SelectionOutcome | BlockingFailure


@dataclass(frozen=True)
class DerivedOutcome(Record):
    state: DerivedState
    reason: str
    value: int | NotEvaluated
    lineage: tuple[InputLineage, ...]
    upstream_failures: tuple[BlockingFailure, ...]


@dataclass(frozen=True)
class DerivedResult(Record):
    specification: FeatureSpec
    dependencies: tuple[CompletedDependency, ...]
    code: CodeObservation
    outcome: DerivedOutcome
    realization_ref: str | NotEvaluated
    diagnostic_preview_bytes: bytes | NotEvaluated
    research_only_audit: tuple[DependencyDiagnostic, ...]
    declared_s4_evaluator_ref: str = EVALUATOR_REF
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


def _context_key(request: AsOfRequest) -> tuple[object, ...]:
    """Local subject/context/policy/coverage IDs may differ; economic rules may not.

    A04 requires identical explicit cutoff declarations, already evaluated by S2.
    It does not parse another clock or accept alternative encodings at assembly.
    Computation time, decision wall times and origin pointers are audit-only.
    """
    c, p = request.context, request.policy
    t = c.information_cutoff
    return (
        (t.source_text, t.timezone_name, t.offset, t.precision),
        c.mode,
        c.evidence_set_ref,
        c.calendar_ref,
        c.numeric_ref,
        (
            c.profile.contract_ref,
            c.profile.mapping_ref,
            c.profile.reason_ref,
            c.profile.evaluator_ref,
            c.profile.code_pins,
            c.profile.status,
        ),
        tuple(sorted(ref for ref in c.policy_refs if ref != p.policy_ref)),
        c.opaque_spec_ref,
        c.opaque_fit_refs,
        c.temporal_rule,
        p.version,
        p.mode,
        p.issuer_ref,
        p.source_refs,
        p.provider_refs,
        p.required_checks,
        p.materiality_rule,
        p.provider_rule,
        p.evaluator_ref,
    )


def _normal_selection(result: AsOfSelectionResult) -> SelectionOutcome | BlockingFailure:
    s = result.selection
    return replace(s, research_only_audit=()) if isinstance(s, SelectionOutcome) else s


def _validate_identity_reuse(
    dependencies: tuple[CompletedDependency, ...], feature_ref: str
) -> None:
    """Guard A03-R01 locally across ALL candidates AND all notice sources."""
    assertions: dict[str, tuple[object, ...]] = {}
    versions: dict[str, tuple[object, ...]] = {}
    representations: dict[str, tuple[object, ...]] = {}
    for dependency in dependencies:
        request = dependency.slot.request
        sources = list(request.candidates)
        sources.extend(
            r.notice for r in request.relations if not isinstance(r.notice, NotEvaluated)
        )
        for source in sources:
            r = source.request
            c = r.content
            require(
                feature_ref
                not in {r.requested.target_ref, c.content_version_ref, c.representation_ref},
                "FEATURE_IDENTITY_IS_NOT_SOURCE_IDENTITY",
            )
            content_identity = (
                c.raw_bytes,
                c.raw_sha256,
                c.raw_length,
                c.source_schema,
                c.content_version_ref,
                c.representation_ref,
                c.source_ref,
                c.issuer_ref,
                c.provider_ref,
            )
            for index, key, signature in (
                (versions, c.content_version_ref, content_identity),
                (representations, c.representation_ref, content_identity),
            ):
                require(
                    key not in index or index[key] == signature, "CONTRADICTORY_IMMUTABLE_IDENTITY"
                )
                index[key] = signature
            if isinstance(r, IssuerBindingRequest):
                a = r.assertion
                assertion_signature = (
                    a.subject_ref,
                    a.source_amount,
                    a.source_unit,
                    a.reference_period,
                    a.content_version_ref,
                    content_identity,
                )
                require(
                    a.assertion_ref not in assertions
                    or assertions[a.assertion_ref] == assertion_signature,
                    "CONTRADICTORY_IMMUTABLE_IDENTITY",
                )
                assertions[a.assertion_ref] = assertion_signature


def _validate(
    spec: FeatureSpec, dependencies: tuple[CompletedDependency, ...], code: CodeObservation
) -> None:
    require(
        type(spec.year) is int
        and 1 <= spec.year <= 9999
        and type(spec.quarter) is int
        and 1 <= spec.quarter <= 4,
        "INVALID_FEATURE_PERIOD",
    )
    require(spec.feature_ref != "" and spec.issuer_ref != "", "INVALID_FEATURE_IDENTITY")
    expected = FeatureSpec(spec.feature_ref, spec.year, spec.quarter, spec.issuer_ref)
    require(spec == expected, "UNSUPPORTED_FEATURE_DEFINITION_OR_DEPENDENCY")
    require(
        len(dependencies) == 3
        and tuple(d.slot.slot_ref for d in dependencies) == ("M1", "M2", "M3"),
        "MISSING_OR_DUPLICATE_SLOT",
    )
    require(
        len({d.slot.expected_subject.subject_ref for d in dependencies}) == 3,
        "DUPLICATE_SUBJECT_DEPENDENCY",
    )
    paths = tuple(p.path for p in code.observed_working_files)
    require(
        paths == (*CODE_PATHS, *S3_CODE_PATHS, *S4_CODE_PATHS)
        and len(code.byte_lengths) == len(paths),
        "INCOMPLETE_CODE_OBSERVATION",
    )
    _validate_identity_reuse(dependencies, spec.feature_ref)
    first = dependencies[0].slot.request
    for i, dep in enumerate(dependencies):
        slot, actual = dep.slot, dep.actual
        request, subject = slot.request, slot.expected_subject
        require(subject == request.subject, "SUBJECT_TRANSPORT_MISMATCH")
        require(subject.subject_ref != spec.feature_ref, "CYCLIC_FEATURE_DEPENDENCY")
        require(_context_key(request) == _context_key(first), "MIXED_RECONSTRUCTION_CONTEXT")
        require(not request.context.opaque_fit_refs, "UNSUPPORTED_FITTED_STATE")
        require(
            request.context.profile.code_pins == code.observed_working_files, "MIXED_DECLARED_CODE"
        )
        require(actual.inputs.code == code, "MIXED_CODE_OBSERVATION")
        # Replay uses the SAME upstream owners, without interpreting their time/selection rules.
        replay = evaluate_asof(request, code)
        require(
            actual.inputs == replay.inputs
            and _normal_selection(actual) == _normal_selection(replay)
            and actual.declared_s3_evaluator_ref == replay.declared_s3_evaluator_ref,
            "FORGED_OR_MISMAPPED_COMPLETED_RESULT",
        )
        month = 3 * (spec.quarter - 1) + i + 1
        start = date(spec.year, month, 1)
        end = date(spec.year, month, calendar.monthrange(spec.year, month)[1])
        for name, value in (
            ("economic_entity_ref", spec.issuer_ref),
            ("metric", spec.input_metric),
            ("period_kind", spec.period_kind),
            ("period_start", start),
            ("period_end", end),
            ("reporting_scope", spec.reporting_scope),
            ("basis_ref", spec.basis_ref),
            ("currency", spec.currency),
            ("canonical_unit", spec.canonical_unit),
        ):
            fact = getattr(subject, name)
            require(
                isinstance(fact, Known) and fact.value == value,
                "INCOMPATIBLE_SUBJECT_" + name.upper(),
            )
        require(subject.mapping_state == "KNOWN", "UNKNOWN_ACCOUNTING_MAPPING")


def _lineage(dep: CompletedDependency, spec: FeatureSpec) -> InputLineage:
    selection = dep.actual.selection
    require(
        isinstance(selection, SelectionOutcome) and selection.state == "SELECTED", "NOT_SELECTED"
    )
    assert isinstance(selection, SelectionOutcome)
    value = selection.selected_value
    require(type(value) is int and -(2**63) <= value < 2**63, "INVALID_INTEGER_VALUE")
    assert isinstance(value, int)
    refs = selection.selected_assertion_refs
    selected = tuple(c for c in dep.actual.inputs.candidates if c.ref in refs)
    require(bool(refs) and len(selected) == len(refs), "SELECTED_LINEAGE_MISMATCH")
    subject = dep.slot.expected_subject
    assert isinstance(subject.period_start, Known) and isinstance(subject.period_end, Known)
    period = (subject.period_start.value, subject.period_end.value)
    for candidate in selected:
        r = candidate.source.request
        require(isinstance(r, IssuerBindingRequest), "UNSUPPORTED_SELECTED_SOURCE")
        assert isinstance(r, IssuerBindingRequest)
        a = r.assertion
        require(
            a.subject_ref == subject.subject_ref
            and a.reference_period == period
            and isinstance(a.source_unit, Known)
            and a.source_unit.value == spec.canonical_unit
            and isinstance(a.source_amount, Known)
            and a.source_amount.value == value,
            "SELECTED_CONTENT_INCOMPATIBLE",
        )
    return InputLineage(
        dep.slot.slot_ref,
        subject.subject_ref,
        period,
        spec.canonical_unit,
        value,
        refs,
        tuple(c.source.request.content.content_version_ref for c in selected),
        tuple(c.source.request.content.representation_ref for c in selected),
        tuple(c.source.request.content.raw_sha256 for c in selected),
    )


def _evaluate_completed(
    spec: FeatureSpec, dependencies: tuple[CompletedDependency, ...], code: CodeObservation
) -> DerivedResult:
    """Internal pure seam; verifies owner replay, not a trusted admission API.

    Priority: S4 contract contradiction, upstream contract fault, upstream other
    blocking/operational fault, unresolved dependency, bounded absence, value.
    Slot order M1/M2/M3 breaks ties. All upstream outcomes/failures remain intact.
    """
    dependencies = tuple(sorted(dependencies, key=lambda d: d.slot.slot_ref))
    audit = tuple(
        DependencyDiagnostic(
            d.slot.slot_ref, d.slot.request.context.context_ref, d.actual.selection
        )
        for d in dependencies
    )
    faults = tuple(
        d.actual.selection for d in dependencies if isinstance(d.actual.selection, BlockingFailure)
    )
    no_value = NotEvaluated("S4", "NO_DERIVED_VALUE")
    try:
        _validate(spec, dependencies, code)
        contract_faults = tuple(f for f in faults if f.category == "CONTRACT_VIOLATION")
        if faults:
            chosen = (contract_faults or faults)[0]
            state: DerivedState = "CONTRACT_VIOLATION" if contract_faults else "OPERATIONAL_ERROR"
            outcome = DerivedOutcome(state, chosen.code, no_value, (), faults)
        else:
            selections = tuple(d.actual.selection for d in dependencies)
            if any(isinstance(s, SelectionOutcome) and s.state == "UNRESOLVED" for s in selections):
                outcome = DerivedOutcome("UNRESOLVED", "DEPENDENCY_UNRESOLVED", no_value, (), ())
            elif any(
                isinstance(s, SelectionOutcome) and s.state == "NO_QUALIFIED_CLAIM"
                for s in selections
            ):
                outcome = DerivedOutcome(
                    "NOT_COMPUTABLE", "DEPENDENCY_NOT_COMPUTABLE", no_value, (), ()
                )
            else:
                lineage = tuple(_lineage(d, spec) for d in dependencies)
                value = sum(item.value for item in lineage)
                require(-(2**63) <= value < 2**63, "INTEGER_SUM_OVERFLOW")
                outcome = DerivedOutcome("VALUE_AVAILABLE", "NONE", value, lineage, ())
    except ContractError as exc:
        outcome = DerivedOutcome("CONTRACT_VIOLATION", str(exc), no_value, (), faults)
    preview: bytes | NotEvaluated = NotEvaluated("S4", "DIAGNOSTIC_PREVIEW_WITHHELD")
    realization: str | NotEvaluated = NotEvaluated("S4", "NO_REALIZATION")
    if outcome.state in {"VALUE_AVAILABLE", "NOT_COMPUTABLE"}:
        context = dependencies[0].slot.request.context
        # Explicit allowlist. No automatic DTO serialization, audit or upstream IDs.
        preview = _canonical(
            {
                "preview_kind": "RESEARCH_DIAGNOSTIC_ONLY",
                "feature_ref": spec.feature_ref,
                "cutoff": context.information_cutoff.source_text,
                "mode": context.mode,
                "value": outcome.value if isinstance(outcome.value, int) else None,
                "missingness": "BOUNDED_REQUIRED_INPUT_ABSENT"
                if outcome.state == "NOT_COMPUTABLE"
                else None,
                "disposition": "INTEGRATED_PROVISIONAL",
                "trust": "NOT_TRUSTED_PIT_EVIDENCE",
                "source_authentication": "NOT_ESTABLISHED",
                "admission_eligible": False,
                "diagnostic_only": True,
            }
        )
        identity = (
            spec.feature_ref,
            spec.transformation_ref,
            spec.policy_ref,
            spec.year,
            spec.quarter,
            context.evidence_set_ref,
            preview.decode(),
            tuple(
                (
                    d.slot.slot_ref,
                    d.slot.request.context.context_ref,
                    d.slot.request.policy.policy_ref,
                    d.slot.request.coverage.coverage_ref,
                )
                for d in dependencies
            ),
            tuple((p.path, p.sha256) for p in code.observed_working_files),
            tuple(
                (item.slot_ref, item.assertion_refs, item.content_version_refs, item.raw_sha256s)
                for item in outcome.lineage
            ),
        )
        realization = "DERIVED-REALIZATION-" + sha256(_canonical(identity)).hexdigest()
    return DerivedResult(spec, dependencies, code, outcome, realization, preview, audit)
