"""Pure S1 operations. BOUND describes content attribution, never temporal support."""

import json
from dataclasses import replace
from datetime import date
from hashlib import sha256
from typing import NamedTuple

from pit_research_lab.domain.contracts import (
    TEMPORAL_PROOF_TYPES,
    AssertionFacts,
    BindingAssessment,
    BlockingFailure,
    CaptureFacts,
    CompleteScopedProvenance,
    ContentFacts,
    ContentInventoryRequest,
    ContractError,
    Derivation,
    DimensionComparison,
    EvidenceOutcome,
    ExactAmount,
    ExactUnitMapping,
    FieldOrigin,
    IdentityOutcome,
    IssuerBindingRequest,
    Known,
    NotApplicable,
    NotEvaluated,
    NumericContract,
    OriginKnownValue,
    ProviderCaptureRequest,
    PublicationEventFacts,
    RequestBindingAttempt,
    RequestedTuple,
    S1Scope,
    ScopedPath,
    SemanticContext,
    SourceAttribution,
    SubjectComparisonRequest,
    SubjectFacts,
    SubjectOperand,
    SupportBinding,
    Unknown,
    UnknownCause,
    Visibility,
    identifier,
    int64,
    require,
)

NA = NotApplicable("S1", "NO_SOURCE_REFERENCE")


def _failure(operation: str, scope: S1Scope, origin: FieldOrigin, code: str) -> BlockingFailure:
    return BlockingFailure("CONTRACT_VIOLATION", code, scope.input_members, code, origin, operation)


def _content(content: ContentFacts, scope: S1Scope) -> None:
    require(
        len(content.raw_bytes) == content.raw_length
        and sha256(content.raw_bytes).hexdigest() == content.raw_sha256,
        "PINNED_INPUT_INVALID",
    )
    matches = [p for p in scope.raw_pins if p.representation_ref == content.representation_ref]
    require(len(matches) == 1, "MISSING_RAW_PIN")
    pin = matches[0]
    require(
        (pin.content_version_ref, pin.raw_length, pin.raw_sha256)
        == (content.content_version_ref, content.raw_length, content.raw_sha256),
        "IMMUTABLE_ID_CONFLICT",
    )


def _tuple_values(target: RequestedTuple) -> tuple[object, ...]:
    return (
        target.target_kind,
        target.target_ref,
        target.subject_scope_refs,
        target.content_version_ref,
        target.representation_ref,
        target.fragment_selector,
    )


class _Statement(NamedTuple):
    position: int
    assertion_ref: str
    subject_ref: str
    amount: int
    unit: str
    period: tuple[date, date]
    issuer_ref: str
    dimensions: tuple[tuple[str, str], ...]


def _json_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_SOURCE_KEY")
        result[key] = value
    return result


def _invalid_json_number(value: str) -> object:
    raise ContractError("INVALID_NUMERIC_TYPE")


def _statement(content: ContentFacts, assertion_ref: str) -> _Statement:
    """Single interpretation of the bounded notice schema; no source discovery."""
    try:
        body = json.loads(
            content.raw_bytes.decode("utf-8"),
            object_pairs_hook=_json_pairs,
            parse_float=_invalid_json_number,
            parse_constant=_invalid_json_number,
        )
        require(
            type(body) is dict
            and set(body)
            == {"schema", "content_version_id", "issuer_id", "source_locator", "statements"},
            "CONTENT_STATEMENT_CONTRACT_INVALID",
        )
        require(
            body["schema"] == content.source_schema == "synthetic-notice-v1",
            "UNSUPPORTED_SOURCE_SCHEMA",
        )
        require(body["content_version_id"] == content.content_version_ref, "CONTENT_ID_MISMATCH")
        require(
            isinstance(content.issuer_ref, Known) and content.issuer_ref.value == body["issuer_id"],
            "SOURCE_ATTRIBUTION_MISMATCH",
        )
        require(
            isinstance(content.source_locator, Known)
            and content.source_locator.value == body["source_locator"],
            "SOURCE_ATTRIBUTION_MISMATCH",
        )
        identifier(body["issuer_id"])
        require(
            type(body["statements"]) is list and bool(body["statements"]),
            "CONTENT_STATEMENT_CONTRACT_INVALID",
        )
        statements: list[_Statement] = []
        required = {"assertion_id", "subject_id", "period", "metric", "unit", "value"}
        optional = {"reporting_scope", "basis_id", "currency"}
        for index, row in enumerate(body["statements"]):
            require(
                type(row) is dict and required <= set(row) <= required | optional,
                "CONTENT_STATEMENT_CONTRACT_INVALID",
            )
            for key in set(row) - {"period", "value"}:
                identifier(row[key])
            int64(row["value"])
            require(
                type(row["period"]) is list and len(row["period"]) == 2,
                "CONTENT_STATEMENT_CONTRACT_INVALID",
            )
            start, end = (date.fromisoformat(v) for v in row["period"])
            require(
                start <= end and [start.isoformat(), end.isoformat()] == row["period"],
                "CONTENT_STATEMENT_CONTRACT_INVALID",
            )
            statements.append(
                _Statement(
                    index,
                    row["assertion_id"],
                    row["subject_id"],
                    row["value"],
                    row["unit"],
                    (start, end),
                    body["issuer_id"],
                    tuple(
                        (key, row[key])
                        for key in ("metric", "reporting_scope", "basis_id", "currency")
                        if key in row
                    ),
                )
            )
        members = tuple(row.assertion_ref for row in statements)
        require(len(members) == len(set(members)), "DUPLICATE_STATEMENT_ID")
        require(members == content.statement_members, "CONTENT_STATEMENT_MISMATCH")
        selected = tuple(row for row in statements if row.assertion_ref == assertion_ref)
        require(len(selected) == 1, "ASSERTION_CONTENT_MISMATCH")
        return selected[0]
    except (KeyError, TypeError, ValueError, IndexError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("CONTENT_STATEMENT_CONTRACT_INVALID") from error


def _assertion_content_tuple(content: ContentFacts, source: _Statement) -> tuple[object, ...]:
    return (
        "ASSERTION",
        source.assertion_ref,
        (source.subject_ref,),
        content.content_version_ref,
        content.representation_ref,
        "/statements/" + str(source.position),
    )


def _requested_content(requested: RequestedTuple, content: ContentFacts) -> _Statement:
    require(
        requested.content_version_ref == content.content_version_ref
        and requested.representation_ref == content.representation_ref,
        "REQUEST_CONTENT_MISMATCH",
    )
    source = _statement(content, requested.target_ref)
    require(
        _tuple_values(requested) == _assertion_content_tuple(content, source),
        "REQUEST_TARGET_CONTENT_MISMATCH",
    )
    return source


def _assertion_source(assertion: AssertionFacts, content: ContentFacts, source: _Statement) -> None:
    int64(assertion.source_amount.value)
    require(
        (
            assertion.assertion_ref,
            assertion.subject_ref,
            assertion.source_amount.value,
            assertion.source_unit.value,
            assertion.reference_period,
            assertion.content_version_ref,
        )
        == (
            source.assertion_ref,
            source.subject_ref,
            source.amount,
            source.unit,
            source.period,
            content.content_version_ref,
        ),
        "SOURCE_ASSERTION_MISMATCH",
    )


def _subject_source(
    subject: SubjectFacts, source: _Statement, mapping: ExactUnitMapping | NotApplicable
) -> None:
    dimensions = dict(source.dimensions)
    facts = (
        (subject.economic_entity_ref, source.issuer_ref),
        (subject.metric, dimensions["metric"]),
        (subject.period_kind, "DURATION"),
        (subject.period_start, source.period[0]),
        (subject.period_end, source.period[1]),
        (subject.reporting_scope, dimensions.get("reporting_scope")),
        (subject.basis_ref, dimensions.get("basis_id")),
        (subject.currency, dimensions.get("currency")),
    )
    for fact, value in facts:
        require(
            isinstance(fact, Unknown)
            and fact.cause == UnknownCause.ABSENT_SOURCE_FIELD
            and fact.source_text is None
            if value is None
            else isinstance(fact, Known) and fact.value == value,
            "SOURCE_SUBJECT_MISMATCH",
        )
    require(subject.subject_ref == source.subject_ref, "SOURCE_SUBJECT_MISMATCH")
    require(
        isinstance(subject.canonical_unit, Known)
        and (
            subject.canonical_unit.value == source.unit
            or isinstance(mapping, ExactUnitMapping)
            and mapping.from_unit == source.unit
            and mapping.to_unit == subject.canonical_unit.value
        ),
        "SOURCE_SUBJECT_MISMATCH",
    )


def _member(scope: S1Scope, visibility: Visibility, role: str, ref: str) -> None:
    require(
        (visibility.value, role, ref) in {m.key for m in scope.input_members},
        "UNDECLARED_PATH_MEMBER",
    )


def _binding_origins(binding: SupportBinding, scope: S1Scope) -> None:
    visibility = binding.origin.visibility
    require(visibility in {Visibility.ACTIVE, Visibility.AUXILIARY}, "NESTED_ORIGIN_SCOPE_MISMATCH")
    require(binding.target.origin.visibility == visibility, "NESTED_ORIGIN_SCOPE_MISMATCH")
    _member(scope, visibility, "supports", binding.support_ref)
    _member(scope, visibility, "evidence", binding.evidence_ref)
    require(
        isinstance(binding.origin.object_id, OriginKnownValue)
        and binding.origin.object_id.value == binding.support_ref
        and isinstance(binding.target.origin.object_id, OriginKnownValue)
        and binding.target.origin.object_id.value == binding.evidence_ref,
        "BINDING_ORIGIN_IDENTITY_MISMATCH",
    )
    for value, role in (
        (binding.event, "publication_events"),
        (binding.proof_candidate, "time_proofs"),
    ):
        if isinstance(value, (PublicationEventFacts, *TEMPORAL_PROOF_TYPES)):
            require(value.origin.visibility == visibility, "NESTED_ORIGIN_SCOPE_MISMATCH")
            ref = value.event_ref if isinstance(value, PublicationEventFacts) else value.proof_ref
            _member(scope, value.origin.visibility, role, ref)
            require(
                isinstance(value.origin.object_id, OriginKnownValue)
                and value.origin.object_id.value == ref,
                "NESTED_ORIGIN_IDENTITY_MISMATCH",
            )


def _path(binding: SupportBinding, role: str) -> ScopedPath:
    return ScopedPath(
        binding.target,
        binding.evidence_ref,
        binding.support_ref,
        binding.event.event_ref if isinstance(binding.event, PublicationEventFacts) else NA,
        binding.proof_candidate.proof_ref
        if isinstance(binding.proof_candidate, TEMPORAL_PROOF_TYPES)
        else NA,
        binding.origin.visibility,
        role,
        binding.origin,
    )


def _provenance(
    scope: S1Scope,
    paths: tuple[ScopedPath, ...],
    rejected: tuple[BindingAssessment, ...] = (),
    derived: tuple[Derivation, ...] = (),
) -> CompleteScopedProvenance:
    used: set[tuple[str, str, str]] = set()
    for path in paths:
        require(
            path.visibility in {Visibility.ACTIVE, Visibility.AUXILIARY}, "FORBIDDEN_VISIBILITY"
        )
        if path.path_role == "CAPTURE_ONLY":
            require(path.target.target_kind == "PROVIDER_CAPTURE", "INVALID_PATH_ROLE")
            if not isinstance(path.origin.object_id, OriginKnownValue):
                raise ContractError("MISSING_CAPTURE_EDGE_ORIGIN")
            targets: tuple[tuple[str, object], ...] = (
                ("observations", path.target.target_ref),
                ("raw_assets", path.target.representation_ref),
                ("graph_edges", path.origin.object_id.value),
            )
        else:
            require(path.path_role in {"ISSUER_BINDING", "IDENTITY_CONTENT"}, "INVALID_PATH_ROLE")
            target_role = "assertions" if path.target.target_kind == "ASSERTION" else "reports"
            targets = (
                (target_role, path.target.target_ref),
                ("content_versions", path.target.content_version_ref),
                ("raw_assets", path.target.representation_ref),
                ("supports", path.support_ref),
                ("evidence", path.evidence_ref),
                ("publication_events", path.event_ref),
                ("time_proofs", path.time_proof_ref),
                *(("subjects", ref) for ref in path.target.subject_scope_refs),
            )
        for role, ref in targets:
            if isinstance(ref, str):
                _member(scope, path.visibility, role, ref)
                used.add((path.visibility.value, role, ref))
    ordered = tuple(
        sorted(
            paths,
            key=lambda p: (
                p.visibility.value,
                p.path_role,
                p.target.target_ref,
                p.target.content_version_ref,
                str(p.support_ref),
            ),
        )
    )
    require(len(ordered) == len(set(ordered)), "DUPLICATE_PATH")
    return CompleteScopedProvenance(
        scope.input_members,
        ordered,
        rejected,
        tuple(r for r in scope.input_members if r.key not in used),
        tuple(NotEvaluated(owner, "OWNER_OUTSIDE_S1") for owner in ("S2", "S3", "S4", "C-07")),
        derived,
    )


def normalize_exact_unit(
    amount: int,
    source_unit: str,
    /,
    *,
    mapping: ExactUnitMapping,
    subject: SubjectFacts,
    numeric: NumericContract,
) -> ExactAmount | BlockingFailure:
    """Compute an explicitly applicable rational scale with exact integer division."""
    try:
        int64(amount)
        require(
            type(mapping.numerator) is int and type(mapping.denominator) is int,
            "INVALID_NUMERIC_TYPE",
        )
        require(mapping.numerator > 0 and mapping.denominator > 0, "INVALID_MAPPING")
        require(source_unit == mapping.from_unit, "MAPPING_UNIT_MISMATCH")
        if not isinstance(subject.canonical_unit, Known):
            raise ContractError("UNSUPPORTED_UNIT_MAP")
        require(
            mapping.to_unit == subject.canonical_unit.value == numeric.unit, "MAPPING_UNIT_MISMATCH"
        )
        require(mapping.subject_ref == subject.subject_ref, "MAPPING_NOT_APPLICABLE")
        dimensions = {
            "entity": subject.economic_entity_ref,
            "period_start": subject.period_start,
            "period_end": subject.period_end,
            "basis": subject.basis_ref,
        }
        require(len(mapping.applicability) == len(dimensions), "MAPPING_NOT_APPLICABLE")
        require(len(dict(mapping.applicability)) == len(mapping.applicability), "INVALID_MAPPING")
        for key, value in mapping.applicability:
            fact = dimensions.get(key)
            require(isinstance(fact, Known) and str(fact.value) == value, "MAPPING_NOT_APPLICABLE")
        quotient, remainder = divmod(amount * mapping.numerator, mapping.denominator)
        require(remainder == 0, "NONINTEGRAL_CANONICAL_AMOUNT")
        int64(quotient)
        derivation = Derivation(
            mapping.mapping_version,
            (subject.subject_ref, mapping.mapping_ref),
            (amount, mapping.numerator, mapping.denominator),
            quotient,
            mapping.origin,
        )
        return ExactAmount(
            amount, source_unit, quotient, mapping.to_unit, mapping.mapping_ref, derivation
        )
    except ContractError as error:
        return _failure("NORMALIZE_EXACT_UNIT", S1Scope((), ()), mapping.origin, str(error))


def _operand(operand: SubjectOperand, scope: S1Scope) -> _Statement | None:
    for content in operand.contents:
        _content(content, scope)
    if isinstance(operand.assertion, AssertionFacts):
        assertion = operand.assertion
        int64(assertion.source_amount.value)
        require(assertion.subject_ref == operand.subject.subject_ref, "ASSERTION_SUBJECT_MISMATCH")
        contents = tuple(
            c for c in operand.contents if c.content_version_ref == assertion.content_version_ref
        )
        require(len(contents) == 1, "ASSERTION_CONTENT_MISMATCH")
        content = contents[0]
        source = _statement(content, assertion.assertion_ref)
        _assertion_source(assertion, content, source)
        start, end = operand.subject.period_start, operand.subject.period_end
        if isinstance(start, Known) and isinstance(end, Known):
            require(
                assertion.reference_period == (start.value, end.value), "ASSERTION_PERIOD_MISMATCH"
            )
        source_target = _assertion_content_tuple(content, source)
        require(source_target[2] == (assertion.subject_ref,), "ASSERTION_SUBJECT_MISMATCH")
        for binding in operand.supports:
            _binding_origins(binding, scope)
            require(
                _tuple_values(binding.target) == source_target
                and binding.origin.visibility == content.origin.visibility,
                "IDENTITY_OPERAND_SUPPORT_MISMATCH",
            )
            event = binding.event
            if isinstance(event, PublicationEventFacts):
                require(
                    event in operand.events
                    and event.event_kind == "issuer_publication"
                    and event.content_version_ref == content.content_version_ref
                    and event.origin.visibility == binding.origin.visibility,
                    "IDENTITY_OPERAND_EVENT_MISMATCH",
                )
                for fact, ref in (
                    (content.issuer_ref, event.issuer_ref),
                    (content.source_ref, event.source_ref),
                ):
                    require(
                        not isinstance(fact, Known) or fact.value == ref,
                        "IDENTITY_OPERAND_EVENT_MISMATCH",
                    )
            proof = binding.proof_candidate
            if isinstance(proof, TEMPORAL_PROOF_TYPES):
                require(
                    (
                        proof.target_kind,
                        proof.target_ref,
                        proof.content_version_ref,
                        proof.fragment_selector,
                    )
                    == (source_target[0], source_target[1], source_target[3], source_target[5])
                    and proof.origin.visibility == binding.origin.visibility,
                    "IDENTITY_OPERAND_PROOF_MISMATCH",
                )
        return source
    return None


def compare_subjects(
    context: SemanticContext, request: SubjectComparisonRequest, /
) -> IdentityOutcome | BlockingFailure:
    """Compare dimensions; source amounts never participate in economic identity."""
    try:
        left_source = _operand(request.left, request.scope)
        right_source = _operand(request.right, request.scope)
        left, right = request.left.subject, request.right.subject
        comparisons: list[DimensionComparison] = []
        for name in (
            "economic_entity_ref",
            "metric",
            "period_kind",
            "period_start",
            "period_end",
            "reporting_scope",
            "basis_ref",
            "currency",
            "canonical_unit",
        ):
            a = getattr(left, name)
            b = getattr(right, name)
            if name == "canonical_unit":
                if isinstance(request.left.assertion, AssertionFacts):
                    a = request.left.assertion.source_unit
                if isinstance(request.right.assertion, AssertionFacts):
                    b = request.right.assertion.source_unit
            if name == "basis_ref":
                if left.mapping_state == "UNMAPPED":
                    a = Unknown(UnknownCause.UNMAPPED, None, left.origin)
                if right.mapping_state == "UNMAPPED":
                    b = Unknown(UnknownCause.UNMAPPED, None, right.origin)
            relation = (
                "UNKNOWN"
                if isinstance(a, Unknown) or isinstance(b, Unknown)
                else ("EQUAL" if a.value == b.value else "DIFFERENT")
            )
            if (
                name == "canonical_unit"
                and relation == "DIFFERENT"
                and isinstance(request.unit_mapping, ExactUnitMapping)
            ):
                if (a.value, b.value) == (
                    request.unit_mapping.from_unit,
                    request.unit_mapping.to_unit,
                ):
                    relation = "MAPPED"
            comparisons.append(DimensionComparison(name, a, b, relation))
        relations = {d.relation for d in comparisons}
        require(not {"UNKNOWN", "DIFFERENT"} <= relations, "UNSUPPORTED_SEMANTIC_COMBINATION")
        for operand, source, mapping in (
            (request.left, left_source, request.unit_mapping),
            (request.right, right_source, NA),
        ):
            if source is not None:
                _subject_source(operand.subject, source, mapping)
        canonical: Known[int] | NotEvaluated = NotEvaluated("S1", "IDENTITY_ONLY")
        mapping_ref: Known[str] | NotApplicable = NA
        derived: tuple[Derivation, ...] = ()
        if isinstance(request.unit_mapping, ExactUnitMapping):
            if not isinstance(request.left.assertion, AssertionFacts):
                raise ContractError("MAPPING_OPERAND_ABSENT")
            assertion = request.left.assertion
            result = normalize_exact_unit(
                assertion.source_amount.value,
                assertion.source_unit.value,
                mapping=request.unit_mapping,
                subject=left,
                numeric=request.numeric,
            )
            if isinstance(result, BlockingFailure):
                return replace(result, affected_scope=request.scope.input_members)
            canonical = Known(result.canonical_amount, request.unit_mapping.origin)
            mapping_ref = Known(result.mapping_ref, request.unit_mapping.origin)
            derived = (result.derivation,)
        for operand in (request.left, request.right):
            if isinstance(operand.assertion, AssertionFacts):
                unit = operand.subject.canonical_unit
                if not isinstance(unit, Known):
                    raise ContractError("UNSUPPORTED_UNIT_MAP")
                if operand.assertion.source_unit.value != unit.value:
                    require(
                        operand is request.left
                        and isinstance(request.unit_mapping, ExactUnitMapping),
                        "UNSUPPORTED_UNIT_MAP",
                    )
        state, reason = ("SAME", "NONE")
        if "UNKNOWN" in relations:
            state, reason = "UNRESOLVED", "BASIS_UNRESOLVED"
        elif "DIFFERENT" in relations:
            state, reason = "DIFFERENT", "SUBJECT_MISMATCH"
        assertions = tuple(
            operand.assertion
            for operand in (request.left, request.right)
            if isinstance(operand.assertion, AssertionFacts)
        )
        paths = tuple(
            _path(binding, "IDENTITY_CONTENT")
            for operand in (request.left, request.right)
            if isinstance(operand.assertion, AssertionFacts)
            for binding in operand.supports
        )
        events: dict[str, PublicationEventFacts] = {}
        for operand in (request.left, request.right):
            for event in operand.events:
                if event.event_ref in events:
                    require(events[event.event_ref] == event, "IMMUTABLE_ID_CONFLICT")
                events[event.event_ref] = event
        return IdentityOutcome(
            state,
            reason,
            context.context_ref,
            left.subject_ref,
            right.subject_ref,
            tuple(a.assertion_ref for a in assertions),
            tuple(a.content_version_ref for a in assertions),
            tuple(comparisons),
            assertions,
            tuple(events[k] for k in sorted(events)),
            canonical,
            mapping_ref,
            _provenance(request.scope, paths, derived=derived),
        )
    except ContractError as error:
        return _failure("COMPARE_SUBJECTS", request.scope, request.left.subject.origin, str(error))


def _assessment(
    attempt: RequestBindingAttempt,
    content: ContentFacts,
    scope: S1Scope,
    events: tuple[PublicationEventFacts, ...],
) -> BindingAssessment:
    requested, binding = attempt.requested, attempt.supplied
    _binding_origins(binding, scope)
    keys = (
        "target_kind",
        "target_ref",
        "subject_scope",
        "content_version",
        "representation",
        "fragment",
    )
    mismatches = [
        name
        for name, a, b in zip(
            keys, _tuple_values(requested), _tuple_values(binding.target), strict=True
        )
        if a != b
    ]
    if binding.attestation_scope != "assertion_fragment":
        mismatches.append("attestation_scope")
    visible = {member.key for member in scope.input_members}
    visibility = binding.origin.visibility.value
    for role, ref in (("supports", binding.support_ref), ("evidence", binding.evidence_ref)):
        if (visibility, role, ref) not in visible:
            mismatches.append(role + "_visibility")
    event = binding.event
    if not isinstance(event, PublicationEventFacts):
        mismatches.append("missing_issuer_event")
    else:
        source_events = tuple(e for e in events if e.event_ref == event.event_ref)
        if not source_events:
            mismatches.append("event_inventory")
        else:
            require(source_events == (event,), "IMMUTABLE_ID_CONFLICT")
        if (visibility, "publication_events", event.event_ref) not in visible:
            mismatches.append("event_visibility")
        if event.event_kind != "issuer_publication":
            mismatches.append("event_kind")
        if event.content_version_ref != requested.content_version_ref:
            mismatches.append("event_content_version")
        if (
            not isinstance(content.issuer_ref, Known)
            or event.issuer_ref != content.issuer_ref.value
        ):
            mismatches.append("issuer")
        if isinstance(content.source_ref, Known) and event.source_ref != content.source_ref.value:
            mismatches.append("source")
    proof = binding.proof_candidate
    if not isinstance(proof, TEMPORAL_PROOF_TYPES):
        mismatches.append("missing_content_publication_descriptor")
    else:
        if (visibility, "time_proofs", proof.proof_ref) not in visible:
            mismatches.append("proof_visibility")
        if (
            proof.target_kind,
            proof.target_ref,
            proof.content_version_ref,
            proof.fragment_selector,
        ) != (
            requested.target_kind,
            requested.target_ref,
            requested.content_version_ref,
            requested.fragment_selector,
        ):
            mismatches.append("proof_target_content_fragment")
    return BindingAssessment(
        "REJECTED" if mismatches else "ACCEPTED", requested, binding, tuple(mismatches)
    )


def _captures(
    content: ContentFacts, captures: tuple[CaptureFacts, ...]
) -> tuple[CaptureFacts, ...]:
    require(len({c.observation_ref for c in captures}) == len(captures), "DUPLICATE_CAPTURE_ID")
    selected = tuple(c for c in captures if c.representation_ref == content.representation_ref)
    for capture in selected:
        require(capture.captured_sha256 == content.raw_sha256, "CAPTURE_HASH_MISMATCH")
    return tuple(sorted(selected, key=lambda c: c.observation_ref))


def _provider_source(request: ProviderCaptureRequest) -> None:
    """Reconcile the bounded capture payload after its raw pin has been verified."""
    content = request.content
    try:
        body = json.loads(
            content.raw_bytes.decode("utf-8"),
            object_pairs_hook=_json_pairs,
            parse_float=_invalid_json_number,
            parse_constant=_invalid_json_number,
        )
        require(
            type(body) is dict
            and set(body)
            == {
                "schema",
                "content_version_id",
                "provider_id",
                "source_locator",
                "subject_reference",
                "displayed_value",
                "unit",
            },
            "PROVIDER_PAYLOAD_CONTRACT_INVALID",
        )
        require(
            body["schema"] == content.source_schema == "synthetic-provider-capture-v1",
            "UNSUPPORTED_SOURCE_SCHEMA",
        )
        for key in set(body) - {"displayed_value"}:
            identifier(body[key])
        int64(body["displayed_value"])
        int64(request.displayed_value.value)
        require(
            body["content_version_id"] == content.content_version_ref
            and content.statement_members == content.report_members == (),
            "PROVIDER_SOURCE_MISMATCH",
        )
        for fact, key in (
            (content.provider_ref, "provider_id"),
            (content.source_locator, "source_locator"),
            (request.subject_reference, "subject_reference"),
            (request.displayed_value, "displayed_value"),
            (request.source_unit, "unit"),
        ):
            require(isinstance(fact, Known) and fact.value == body[key], "PROVIDER_SOURCE_MISMATCH")
        require(
            _tuple_values(request.requested)
            == (
                "PROVIDER_CAPTURE",
                request.capture.observation_ref,
                (body["subject_reference"],),
                content.content_version_ref,
                content.representation_ref,
                NA,
            ),
            "PROVIDER_REQUEST_SOURCE_MISMATCH",
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("PROVIDER_PAYLOAD_CONTRACT_INVALID") from error


def _inventory_members(
    values: tuple[CaptureFacts | PublicationEventFacts, ...],
    role: str,
    scope: S1Scope,
) -> None:
    supplied = tuple(
        (
            value.origin.visibility.value,
            role,
            value.observation_ref if isinstance(value, CaptureFacts) else value.event_ref,
        )
        for value in values
    )
    require(len(supplied) == len(set(supplied)), "DUPLICATE_INVENTORY_IDENTITY")
    visible = tuple(
        member.key
        for member in scope.input_members
        if member.role == role and member.visibility in {Visibility.ACTIVE, Visibility.AUXILIARY}
    )
    require(sorted(supplied) == sorted(visible), "INCOMPLETE_INVENTORY_SCOPE")
    for value, (_, _, ref) in zip(values, supplied, strict=True):
        require(
            isinstance(value.origin.object_id, OriginKnownValue)
            and value.origin.object_id.value == ref,
            "INVENTORY_ORIGIN_IDENTITY_MISMATCH",
        )


def assess_evidence(
    context: SemanticContext, request: IssuerBindingRequest | ProviderCaptureRequest, /
) -> EvidenceOutcome | BlockingFailure:
    """Qualify supplied content association; never test timestamps against a cutoff."""
    try:
        _content(request.content, request.scope)
        require(
            request.requested.content_version_ref == request.content.content_version_ref
            and request.requested.representation_ref == request.content.representation_ref,
            "REQUEST_CONTENT_MISMATCH",
        )
        content = request.content
        attribution = SourceAttribution(
            content.issuer_ref, content.provider_ref, content.source_ref
        )
        if isinstance(request, ProviderCaptureRequest):
            _provider_source(request)
            require(isinstance(content.issuer_ref, Unknown), "FABRICATED_PROVIDER_ISSUER")
            require(isinstance(content.provider_ref, Known), "MISSING_PROVIDER")
            require(request.requested.target_kind == "PROVIDER_CAPTURE", "INVALID_PROVIDER_TARGET")
            require(
                request.requested.target_ref == request.capture.observation_ref,
                "INVALID_PROVIDER_TARGET",
            )
            require(len(request.capture_edges) == 1, "PROVIDER_CAPTURE_EDGE_CARDINALITY")
            edge = request.capture_edges[0]
            require(
                edge.edge_role == "provider_lab_capture_only"
                and edge.from_observation == request.capture.observation_ref
                and edge.to_representation == content.representation_ref,
                "PROVIDER_CAPTURE_EDGE_MISMATCH",
            )
            require(
                edge.origin.visibility == request.capture.origin.visibility,
                "NESTED_ORIGIN_SCOPE_MISMATCH",
            )
            _member(request.scope, edge.origin.visibility, "graph_edges", edge.edge_ref)
            for origin, ref in (
                (request.capture.origin, request.capture.observation_ref),
                (edge.origin, edge.edge_ref),
            ):
                require(
                    isinstance(origin.object_id, OriginKnownValue)
                    and origin.object_id.value == ref,
                    "INVENTORY_ORIGIN_IDENTITY_MISMATCH",
                )
            captures = _captures(content, (request.capture,))
            require(len(captures) == 1, "PROVIDER_CAPTURE_CONTENT_MISMATCH")
            path = ScopedPath(
                request.requested,
                NA,
                NA,
                NA,
                NA,
                request.capture.origin.visibility,
                "CAPTURE_ONLY",
                edge.origin,
            )
            return EvidenceOutcome(
                "UNRESOLVED",
                "ATTRIBUTION_UNRESOLVED",
                context.context_ref,
                request.requested,
                attribution,
                request.displayed_value,
                (content.content_version_ref,),
                (),
                (),
                captures,
                (),
                request.capture_edges,
                _provenance(request.scope, (path,)),
            )
        require(
            request.assertion.assertion_ref == request.requested.target_ref,
            "ASSERTION_TARGET_MISMATCH",
        )
        require(
            request.assertion.content_version_ref == content.content_version_ref,
            "ASSERTION_CONTENT_MISMATCH",
        )
        source = _requested_content(request.requested, content)
        _assertion_source(request.assertion, content, source)
        require(len(request.attempts) <= 1, "UNSUPPORTED_SEMANTIC_COMBINATION")
        assessments = tuple(
            _assessment(a, content, request.scope, request.events) for a in request.attempts
        )
        for attempt in request.attempts:
            require(
                _tuple_values(attempt.requested) == _tuple_values(request.requested),
                "ATTEMPT_REQUEST_MISMATCH",
            )
        accepted = tuple(a for a in assessments if a.disposition == "ACCEPTED")
        rejected = tuple(a for a in assessments if a.disposition == "REJECTED")
        events = tuple(
            sorted(
                (e for e in request.events if e.content_version_ref == content.content_version_ref),
                key=lambda e: e.event_ref,
            )
        )
        require(
            len({e.event_ref for e in request.events}) == len(request.events), "DUPLICATE_EVENT_ID"
        )
        return EvidenceOutcome(
            "BOUND" if accepted else "UNRESOLVED",
            "NONE" if accepted else "CONTENT_BINDING_INSUFFICIENT",
            context.context_ref,
            request.requested,
            attribution,
            request.assertion.source_amount,
            (content.content_version_ref,),
            tuple(a.supplied for a in request.attempts),
            assessments,
            _captures(content, request.captures),
            events,
            (),
            _provenance(
                request.scope,
                tuple(_path(a.supplied, "ISSUER_BINDING") for a in accepted),
                rejected,
            ),
        )
    except ContractError as error:
        return _failure("CHECK_BINDING", request.scope, request.content.origin, str(error))


def inventory_content(
    context: SemanticContext, request: ContentInventoryRequest, /
) -> EvidenceOutcome | BlockingFailure:
    """Report actual content-scoped sets, accounting for the complete supplied inventory."""
    try:
        _content(request.content, request.scope)
        _requested_content(request.requested, request.content)
        supplied_supports = tuple(
            (s.origin.visibility.value, "supports", s.support_ref) for s in request.supports
        )
        require(len(supplied_supports) == len(set(supplied_supports)), "DUPLICATE_SUPPORT_ID")
        visible_supports = tuple(
            member.key
            for member in request.scope.input_members
            if member.role == "supports"
            and member.visibility in {Visibility.ACTIVE, Visibility.AUXILIARY}
        )
        require(sorted(supplied_supports) == sorted(visible_supports), "INCOMPLETE_INVENTORY_SCOPE")
        _inventory_members(request.captures, "observations", request.scope)
        _inventory_members(request.events, "publication_events", request.scope)
        captures = _captures(request.content, request.captures)
        require(
            len({e.event_ref for e in request.events}) == len(request.events), "DUPLICATE_EVENT_ID"
        )
        events = tuple(
            sorted(
                (
                    e
                    for e in request.events
                    if e.content_version_ref == request.content.content_version_ref
                ),
                key=lambda e: e.event_ref,
            )
        )
        require(len(events) <= 1, "UNSUPPORTED_EVENT_COMBINATION")
        matches = tuple(
            s
            for s in request.supports
            if _tuple_values(s.target) == _tuple_values(request.requested)
        )
        require(len(matches) <= 1, "UNSUPPORTED_SEMANTIC_COMBINATION")
        assessments = tuple(
            _assessment(
                RequestBindingAttempt(request.requested, s),
                request.content,
                request.scope,
                request.events,
            )
            for s in matches
        )
        accepted = tuple(a for a in assessments if a.disposition == "ACCEPTED")
        rejected = tuple(a for a in assessments if a.disposition == "REJECTED")
        return EvidenceOutcome(
            "BOUND" if accepted else "UNRESOLVED",
            "NONE" if accepted else "CONTENT_BINDING_INSUFFICIENT",
            context.context_ref,
            request.requested,
            SourceAttribution(
                request.content.issuer_ref, request.content.provider_ref, request.content.source_ref
            ),
            NotEvaluated("S1", "INVENTORY_ONLY"),
            (request.content.content_version_ref,),
            matches,
            assessments,
            captures,
            events,
            (),
            _provenance(
                request.scope,
                tuple(_path(a.supplied, "ISSUER_BINDING") for a in accepted),
                rejected,
            ),
        )
    except ContractError as error:
        return _failure("INVENTORY_CONTENT", request.scope, request.content.origin, str(error))
