"""ENGINEERING_TEST: real S1 mechanisms; no Golden runtime certification."""

import hashlib
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from wu01_actual import ActualInputAssociation, observe_actual, project
from wu01_inputs import (
    CALLER,
    NA,
    AdaptedS1Input,
    InvocationSelector,
    adapt,
    materialize,
    materialize_input,
)

from pit_research_lab.domain.contracts import (
    SCHEMA,
    BlockingFailure,
    CandidateProfile,
    CodePin,
    ContentInventoryRequest,
    ContentPin,
    ContractError,
    EvidenceOutcome,
    IdentityOutcome,
    IssuerBindingRequest,
    Known,
    OriginKnownValue,
    ProviderCaptureRequest,
    SubjectComparisonRequest,
    Unknown,
    UnknownCause,
    Visibility,
)
from pit_research_lab.domain.information import (
    assess_evidence,
    compare_subjects,
    inventory_content,
    normalize_exact_unit,
)

A = Visibility.ACTIVE
U = Visibility.AUXILIARY
SELECTORS = {
    "A01-C01": InvocationSelector("COMPARE_SUBJECTS", ("A-APR-NTD-A01-C01", "SUB-A-APR"), NA, (A,)),
    "A01-C02": InvocationSelector(
        "COMPARE_SUBJECTS", ("A-H1-A01-C02", "A-Q2-REPORTED-A01-C02"), NA, (A, U)
    ),
    "A01-C03": InvocationSelector("COMPARE_SUBJECTS", ("A-JUN-01", "A-JUN-PEER"), NA, (A, U)),
    "A01-C04": InvocationSelector(
        "COMPARE_SUBJECTS", ("A-JUN-01", "A-JUN-SCOPE-A01-C04"), NA, (A, U)
    ),
    "A02-C01": InvocationSelector("CHECK_BINDING", ("A-JUN-01",), "SUP-JUN1-PUB", (A,)),
    "A02-C02": InvocationSelector("CHECK_BINDING", ("A-JUN-02",), "SUP-JUN1-PUB", (A, U)),
    "A02-C03": InvocationSelector("INVENTORY_CONTENT", ("A-JUN-01", "CV-JUN-01"), NA, (A,)),
    "A02-C04": InvocationSelector("CHECK_BINDING", ("OBS-P-X-A02-C04",), NA, (A, U)),
}


def engineering_profile():
    root = Path(__file__).resolve().parents[3]
    paths = (
        "src/pit_research_lab/domain/contracts.py",
        "src/pit_research_lab/domain/information.py",
        "tests/unit/cap_f2_wu01/wu01_actual.py",
    )
    pins = tuple(
        CodePin(path, hashlib.sha256((root / path).read_bytes()).hexdigest()) for path in paths
    )
    return CandidateProfile(
        SCHEMA,
        "wu01-unit-v0.1-CANDIDATE",
        "wu01-reasons-v0.1-CANDIDATE",
        "s1-information-v0.1-CANDIDATE",
        pins,
        CALLER,
    )


def inputs(case):
    value = materialize_input(case, SELECTORS[case], engineering_profile())
    assert isinstance(value, AdaptedS1Input), value
    return value


def execute(bundle):
    request = bundle.request
    if isinstance(request, SubjectComparisonRequest):
        return compare_subjects(bundle.context, request)
    if isinstance(request, ContentInventoryRequest):
        return inventory_content(bundle.context, request)
    return assess_evidence(bundle.context, request)


def actual_projection(bundle, actual):
    c = bundle.context
    association = ActualInputAssociation(
        bundle.selector.operation,
        c.context_ref,
        c.target_ref,
        bundle.selector.concrete_targets,
        c.mode,
        c.information_cutoff.source_text,
        bundle.request,
        bundle.source_members,
        bundle.source_captures,
        bundle.source_events,
        bundle.source_assertion_refs,
        bundle.source_attempt_refs,
    )
    return project(actual, association, (observe_actual(actual, association),))


def test_engineering_a01_c01_exact_supplied_unit_conversion():
    bundle = inputs("A01-C01")
    actual = execute(bundle)
    assert isinstance(actual, IdentityOutcome)
    assert (actual.state, actual.reason) == ("SAME", "NONE")
    assert type(actual.canonical_amount.value) is int and actual.canonical_amount.value == 100
    assert actual.source_assertions[0].source_amount.value == 100000
    assert actual.source_assertions[0].source_unit.value == "NTD"
    assert actual.mapping_ref.value == "MAP-UNIT-A01-C01"
    assert actual.provenance.derived_facts[0].exact_operands == (100000, 1, 1000)
    assert not any(m.object_ref == "A-APR-01" for m in actual.provenance.input_members)
    assert all(d.owner in {"S2", "S3", "S4", "C-07"} for d in actual.provenance.not_evaluated)
    assert actual_projection(bundle, actual).system_outcome == actual


def test_engineering_a01_c02_same_600_different_duration():
    bundle = inputs("A01-C02")
    actual = execute(bundle)
    assert (actual.state, actual.reason) == ("DIFFERENT", "SUBJECT_MISMATCH")
    assert tuple(a.source_amount.value for a in actual.source_assertions) == (600, 600)
    periods = next(d for d in actual.compared_dimensions if d.dimension == "period_start")
    assert (str(periods.left.value), str(periods.right.value)) == ("2025-01-01", "2025-04-01")
    assert len(set(actual.assertion_refs)) == 2
    assert actual.publication_event_facts == ()
    assert all(p.visibility == U for p in actual.provenance.accepted_paths)
    actual_projection(bundle, actual)


def test_engineering_a01_c03_same_subject_distinct_claim_content_event():
    bundle = inputs("A01-C03")
    actual = execute(bundle)
    assert (actual.state, actual.reason) == ("SAME", "NONE")
    assert actual.assertion_refs == ("A-JUN-01", "A-JUN-PEER")
    assert actual.content_version_refs == ("CV-JUN-01", "CV-JUN-PEER")
    assert tuple(e.event_ref for e in actual.publication_event_facts) == (
        "PUB-JUN-01",
        "PUB-JUN-PEER",
    )
    assert {p.visibility for p in actual.provenance.accepted_paths} == {A, U}
    actual_projection(bundle, actual)


def test_engineering_a01_c04_source_absence_is_normal_unknown():
    envelope = materialize("A01-C04")
    row = envelope["auxiliary_comparison_inputs"][0]["subjects"]["SUB-A-JUN-CAND-A01-C04"]
    assert "reporting_scope" not in row
    bundle = adapt(envelope, SELECTORS["A01-C04"], engineering_profile())
    scope = bundle.request.right.subject.reporting_scope
    assert isinstance(scope, Unknown) and scope.cause == UnknownCause.ABSENT_SOURCE_FIELD
    actual = execute(bundle)
    assert isinstance(actual, IdentityOutcome)
    assert (actual.state, actual.reason) == ("UNRESOLVED", "BASIS_UNRESOLVED")
    assert bundle.request.right.subject.mapping_state == "UNMAPPED"
    actual_projection(bundle, actual)


def test_engineering_a02_c01_content_specific_issuer_binding():
    bundle = inputs("A02-C01")
    actual = execute(bundle)
    assert isinstance(actual, EvidenceOutcome)
    assert (actual.state, actual.reason, actual.source_amount.value) == ("BOUND", "NONE", 300)
    (path,) = actual.provenance.accepted_paths
    assert (
        path.target.target_ref,
        path.target.content_version_ref,
        path.target.fragment_selector,
        path.support_ref,
        path.evidence_ref,
        path.event_ref,
        path.time_proof_ref,
    ) == (
        "A-JUN-01",
        "CV-JUN-01",
        "/statements/0",
        "SUP-JUN1-PUB",
        "EVID-JUN1-TIME",
        "PUB-JUN-01",
        "TP-JUN1",
    )
    assert actual.source_attribution.issuer.value == "SYN-A"
    supplied = actual.assessments[0].supplied
    assert supplied.target.origin.object_id.value == "EVID-JUN1-TIME"
    assert supplied.event.origin.object_id.value == "PUB-JUN-01"
    assert supplied.event.origin.envelope_pointer.endswith("/publication_events/PUB-JUN-01")
    assert supplied.proof_candidate.origin.object_id.value == "TP-JUN1"
    assert supplied.proof_candidate.origin.envelope_pointer.endswith("/time_proofs/TP-JUN1")
    assert actual.assessments[0].supplied.proof_candidate.timestamp.source_text == (
        "2025-07-03T14:00:00+08:00"
    )
    assert any(d.owner == "S2" for d in actual.provenance.not_evaluated)
    actual_projection(bundle, actual)


def test_engineering_a02_c02_foreign_support_valid_input_rejected_use():
    bundle = inputs("A02-C02")
    assert isinstance(bundle.request, IssuerBindingRequest)
    assert bundle.request.attempts[0].supplied.target.content_version_ref == "CV-JUN-01"
    actual = execute(bundle)
    assert (actual.state, actual.reason, actual.source_amount.value) == (
        "UNRESOLVED",
        "CONTENT_BINDING_INSUFFICIENT",
        310,
    )
    assert actual.requested_tuple.content_version_ref == "CV-JUN-02"
    (rejected,) = actual.provenance.rejected_attempts
    assert rejected.supplied.support_ref == "SUP-JUN1-PUB"
    assert {"target_ref", "content_version", "representation"} <= set(rejected.mismatches)
    assert actual.provenance.accepted_paths == ()
    assert isinstance(bundle.request.content.source_ref, Unknown)
    assert not any(
        m.object_ref in {"SUP-JUN2-PUB", "TP-JUN2", "PUB-JUN-02"}
        for m in actual.provenance.input_members
    )
    actual_projection(bundle, actual)


def test_engineering_a02_c03_two_captures_one_content_scoped_event():
    bundle = inputs("A02-C03")
    assert len(bundle.source_events) > 1
    actual = execute(bundle)
    assert (actual.state, actual.reason) == ("BOUND", "NONE")
    assert tuple(c.observation_ref for c in actual.capture_facts) == (
        "OBS-JUN1-LATE",
        "OBS-JUN1-REPEAT",
    )
    assert tuple(e.event_ref for e in actual.publication_event_facts) == ("PUB-JUN-01",)
    assert len({c.captured_sha256 for c in actual.capture_facts}) == 1
    assert tuple(c.completion.value.source_text for c in actual.capture_facts) == (
        "2025-07-15T12:00:00+08:00",
        "2025-07-16T12:00:00+08:00",
    )
    actual_projection(bundle, actual)


def test_engineering_a02_c04_provider_capture_without_issuer_invention():
    bundle = inputs("A02-C04")
    assert isinstance(bundle.request, ProviderCaptureRequest)
    actual = execute(bundle)
    assert (actual.state, actual.reason, actual.source_amount.value) == (
        "UNRESOLVED",
        "ATTRIBUTION_UNRESOLVED",
        300,
    )
    assert actual.source_attribution.provider.value == "P-X"
    assert isinstance(actual.source_attribution.issuer, Unknown)
    assert actual.supplied_bindings == actual.publication_event_facts == ()
    assert actual.capture_edges[0].edge_role == "provider_lab_capture_only"
    assert all(p.path_role == "CAPTURE_ONLY" for p in actual.provenance.accepted_paths)
    assert bundle.source_events  # Original ACTIVE issuer events were not erased.
    actual_projection(bundle, actual)


@pytest.mark.parametrize("value", [True, 100000.0, "100000"])
def test_sensitivity_numeric_coercion_is_blocking(value):
    bundle = inputs("A01-C01")
    r = bundle.request
    result = normalize_exact_unit(
        value, "NTD", mapping=r.unit_mapping, subject=r.left.subject, numeric=r.numeric
    )
    assert isinstance(result, BlockingFailure) and result.code == "INVALID_NUMERIC_TYPE"


@pytest.mark.parametrize(
    "change,amount,code",
    [
        ({"denominator": 0}, 100000, "INVALID_MAPPING"),
        ({"numerator": True}, 100000, "INVALID_NUMERIC_TYPE"),
        ({}, 1, "NONINTEGRAL_CANONICAL_AMOUNT"),
        ({"numerator": 1000, "denominator": 1}, 2**63 - 1, "NUMERIC_RANGE"),
        ({"from_unit": "USD"}, 100000, "MAPPING_UNIT_MISMATCH"),
        ({"subject_ref": "OTHER"}, 100000, "MAPPING_NOT_APPLICABLE"),
        ({"applicability": (("basis", "OTHER"),)}, 100000, "MAPPING_NOT_APPLICABLE"),
    ],
)
def test_sensitivity_exact_mapping_failure_modes(change, amount, code):
    r = inputs("A01-C01").request
    actual = normalize_exact_unit(
        amount,
        "NTD",
        mapping=replace(r.unit_mapping, **change),
        subject=r.left.subject,
        numeric=r.numeric,
    )
    assert isinstance(actual, BlockingFailure) and actual.code == code


def test_sensitivity_amount_changes_do_not_change_economic_subject():
    bundle = inputs("A01-C01")
    r = bundle.request
    old = r.left.contents[0]
    body = json.loads(old.raw_bytes)
    body["content_version_id"] = "CV-ENGINEERING-SCALE"
    body["statements"][0].update(assertion_id="A-ENGINEERING-SCALE", value=200000)
    raw = json.dumps(body, separators=(",", ":")).encode()
    raw_digest = hashlib.sha256(raw).hexdigest()
    o = replace(
        old.origin,
        object_id=OriginKnownValue(body["content_version_id"]),
        input_digest=OriginKnownValue(raw_digest),
    )
    content = replace(
        old,
        content_version_ref=body["content_version_id"],
        representation_ref="REP-ENGINEERING-SCALE",
        raw_bytes=raw,
        raw_length=len(raw),
        raw_sha256=raw_digest,
        origin=o,
        statement_members=("A-ENGINEERING-SCALE",),
    )
    assertion = replace(
        r.left.assertion,
        assertion_ref="A-ENGINEERING-SCALE",
        content_version_ref=content.content_version_ref,
        source_amount=Known(200000, o),
        origin=o,
    )
    scope = replace(
        r.scope,
        raw_pins=(
            ContentPin(
                content.content_version_ref, content.representation_ref, len(raw), raw_digest
            ),
        ),
    )
    changed = replace(
        r,
        left=replace(
            r.left, assertion=assertion, contents=(content,), supports=(), events=(), captures=()
        ),
        scope=scope,
    )
    actual = compare_subjects(bundle.context, changed)
    assert (actual.state, actual.reason, actual.canonical_amount.value) == ("SAME", "NONE", 200)


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_ref", "A-ORD-01"),
        ("content_version_ref", "OTHER-CV"),
        ("representation_ref", "OTHER-RAW"),
        ("fragment_selector", "/statements/1"),
        ("subject_scope_refs", ("SUB-A-JUN-ORDERS",)),
    ],
)
def test_sensitivity_foreign_tuple_components_are_rejected(field, value):
    bundle = inputs("A02-C01")
    r = bundle.request
    supplied = replace(
        r.attempts[0].supplied, target=replace(r.attempts[0].supplied.target, **{field: value})
    )
    changed = replace(r, attempts=(replace(r.attempts[0], supplied=supplied),))
    actual = assess_evidence(bundle.context, changed)
    assert (actual.state, actual.reason) == ("UNRESOLVED", "CONTENT_BINDING_INSUFFICIENT")
    assert actual.provenance.rejected_attempts and actual.provenance.accepted_paths == ()


def test_sensitivity_orders_support_cannot_replace_revenue_support():
    envelope = materialize("A02-C01")
    envelope["request"]["supplied_support_ref"] = "SUP-ORD1-PUB"
    selector = replace(SELECTORS["A02-C01"], supplied_support_ref="SUP-ORD1-PUB")
    bundle = adapt(envelope, selector, engineering_profile())
    actual = execute(bundle)
    assert actual.state == "UNRESOLVED"
    assert actual.assessments[0].disposition == "REJECTED"
    assert actual.assessments[0].supplied.target.fragment_selector == "/statements/1"


@pytest.mark.parametrize("kind", ["drop", "duplicate", "hash", "provider_edge"])
def test_sensitivity_capture_inventory_and_provider_roles(kind):
    bundle = inputs("A02-C04" if kind == "provider_edge" else "A02-C03")
    r = bundle.request
    if kind == "provider_edge":
        r = replace(r, capture_edges=(replace(r.capture_edges[0], edge_role="issuer_publication"),))
        actual = assess_evidence(bundle.context, r)
        assert actual.code == "PROVIDER_CAPTURE_EDGE_MISMATCH"
        return
    if kind == "drop":
        r = replace(r, captures=r.captures[:-1])
    elif kind == "duplicate":
        r = replace(r, captures=r.captures + (r.captures[0],))
    else:
        r = replace(
            r,
            captures=tuple(
                replace(c, captured_sha256="0" * 64)
                if c.representation_ref == "REP-RAW-CV-JUN-01"
                else c
                for c in r.captures
            ),
        )
    assert isinstance(inventory_content(bundle.context, r), BlockingFailure)


def test_sensitivity_projector_requires_observed_complete_scope_and_distinct_ids():
    bundle = inputs("A01-C03")
    actual = execute(bundle)
    for changed in (
        replace(actual, assertion_refs=("A-JUN-01",)),
        replace(actual, publication_event_facts=actual.publication_event_facts[:1]),
        replace(actual, provenance=replace(actual.provenance, input_members=())),
        replace(actual, provenance=replace(actual.provenance, excluded_uses=())),
    ):
        with pytest.raises(ContractError):
            actual_projection(bundle, changed)


@pytest.mark.parametrize(
    "fault", ["may_target", "representation", "fragment", "subject_scope", "target_kind"]
)
def test_ir01_inventory_rejects_request_content_mismatch(fault):
    bundle = inputs("A02-C03")
    r = bundle.request
    may = next(s for s in r.supports if s.target.content_version_ref == "CV-MAY-01")
    if fault == "may_target":
        requested = may.target
    else:
        changes = {
            "representation": {"representation_ref": may.target.representation_ref},
            "fragment": {"fragment_selector": "/statements/1"},
            "subject_scope": {"subject_scope_refs": may.target.subject_scope_refs},
            "target_kind": {"target_kind": "REPORT"},
        }
        requested = replace(r.requested, **changes[fault])
    result = inventory_content(bundle.context, replace(r, requested=requested))
    assert isinstance(result, BlockingFailure), result
    assert result.category == "CONTRACT_VIOLATION"
    assert result.code == (
        "REQUEST_CONTENT_MISMATCH"
        if fault in {"may_target", "representation"}
        else "REQUEST_TARGET_CONTENT_MISMATCH"
    )


@pytest.mark.parametrize(
    "fault",
    ["cross_content", "cv", "representation", "fragment", "scope", "kind", "event", "proof"],
)
def test_ir02_identity_support_requires_complete_own_content_tuple(fault):
    envelope = materialize("A01-C03")
    view = envelope["active_discovery_membership"]["facts"]
    if fault == "cross_content":
        # Real May content/representation, preserving the June assertion identity.
        support = view["supports"]["SUP-JUN1-PUB"]
        evidence_binding = view["evidence"][support["evidence_id"]]["bindings"][0]
        support["content_version_id"] = "CV-MAY-01"
        evidence_binding["content_version_id"] = "CV-MAY-01"
        evidence_binding["raw_representation_id"] = "REP-RAW-CV-MAY-01"
    bundle = adapt(envelope, SELECTORS["A01-C03"], engineering_profile())
    assert isinstance(bundle, AdaptedS1Input), bundle
    r = bundle.request
    binding = r.left.supports[0]
    if fault not in {"cross_content", "event", "proof"}:
        changes = {
            "cv": {"content_version_ref": "CV-MAY-01"},
            "representation": {"representation_ref": "REP-RAW-CV-MAY-01"},
            "fragment": {"fragment_selector": "/statements/1"},
            "scope": {"subject_scope_refs": ("SUB-A-MAY",)},
            "kind": {"target_kind": "REPORT"},
        }
        binding = replace(binding, target=replace(binding.target, **changes[fault]))
    elif fault == "event":
        may_event = next(e for e in bundle.source_events if e.content_version_ref == "CV-MAY-01")
        binding = replace(binding, event=may_event)
    elif fault == "proof":
        binding = replace(
            binding, proof_candidate=replace(binding.proof_candidate, target_ref="A-MAY-01")
        )
    request = replace(r, left=replace(r.left, supports=(binding,)))
    assert request.left.supports[0] == binding
    result = compare_subjects(bundle.context, request)
    assert isinstance(result, BlockingFailure), result
    assert result.category == "CONTRACT_VIOLATION"
    assert result.code == {
        "event": "IDENTITY_OPERAND_EVENT_MISMATCH",
        "proof": "IDENTITY_OPERAND_PROOF_MISMATCH",
    }.get(fault, "IDENTITY_OPERAND_SUPPORT_MISMATCH")


@pytest.mark.parametrize("fault", ["omit", "duplicate", "substitute", "visibility"])
def test_ir03_inventory_requires_complete_role_scoped_supports(fault):
    bundle = inputs("A02-C03")
    r = bundle.request
    june = next(s for s in r.supports if s.target.content_version_ref == "CV-JUN-01")
    if fault == "omit":
        supports = tuple(s for s in r.supports if s != june)
    elif fault == "duplicate":
        may = next(s for s in r.supports if s.target.content_version_ref == "CV-MAY-01")
        supports = (*r.supports, may)
    else:
        changed = (
            replace(june, support_ref="SUP-UNDECLARED")
            if fault == "substitute"
            else replace(june, origin=replace(june.origin, visibility=U))
        )
        supports = tuple(changed if s == june else s for s in r.supports)
    request = replace(r, supports=supports)
    assert request.scope == r.scope
    result = inventory_content(bundle.context, request)
    assert isinstance(result, BlockingFailure), result
    assert result.category == "CONTRACT_VIOLATION"
    assert result.code == (
        "DUPLICATE_SUPPORT_ID" if fault == "duplicate" else "INCOMPLETE_INVENTORY_SCOPE"
    )


@pytest.mark.parametrize("fragment", ["/statements/999", "/statements/1"])
def test_r2_ir01_coordinated_issuer_fragment_must_exist_in_pinned_source(fragment):
    bundle = inputs("A02-C01")
    r = bundle.request
    requested = replace(r.requested, fragment_selector=fragment)
    supplied = replace(
        r.attempts[0].supplied,
        target=replace(r.attempts[0].supplied.target, fragment_selector=fragment),
        proof_candidate=replace(r.attempts[0].supplied.proof_candidate, fragment_selector=fragment),
    )
    changed = replace(
        r,
        requested=requested,
        attempts=(replace(r.attempts[0], requested=requested, supplied=supplied),),
    )
    assert changed.content == r.content and changed.scope == r.scope
    result = assess_evidence(bundle.context, changed)
    assert isinstance(result, BlockingFailure), result
    assert (result.category, result.code) == (
        "CONTRACT_VIOLATION",
        "REQUEST_TARGET_CONTENT_MISMATCH",
    )


@pytest.mark.parametrize("case,value", [("A01-C01", 900000), ("A02-C01", 900)])
def test_r2_ir02_typed_amount_cannot_override_pinned_statement(case, value):
    bundle = inputs(case)
    r = bundle.request
    if isinstance(r, SubjectComparisonRequest):
        changed = replace(
            r,
            left=replace(
                r.left, assertion=replace(r.left.assertion, source_amount=Known(value, CALLER))
            ),
        )
        assert changed.left.contents == r.left.contents and changed.scope == r.scope
        result = compare_subjects(bundle.context, changed)
    else:
        changed = replace(r, assertion=replace(r.assertion, source_amount=Known(value, CALLER)))
        assert changed.content == r.content and changed.scope == r.scope
        result = assess_evidence(bundle.context, changed)
    assert isinstance(result, BlockingFailure), result
    assert (result.category, result.code) == ("CONTRACT_VIOLATION", "SOURCE_ASSERTION_MISMATCH")


@pytest.mark.parametrize("visibility", [Visibility.DEPENDENCY, Visibility.AUDIT])
@pytest.mark.parametrize("nested", ["proof", "event"])
def test_r2_ir03_nested_origin_cannot_be_laundered_into_active_binding(nested, visibility):
    bundle = inputs("A02-C01")
    r = bundle.request
    supplied = r.attempts[0].supplied
    events = r.events
    if nested == "proof":
        proof = replace(
            supplied.proof_candidate,
            origin=replace(supplied.proof_candidate.origin, visibility=visibility),
        )
        supplied = replace(supplied, proof_candidate=proof)
    else:
        event = replace(
            supplied.event, origin=replace(supplied.event.origin, visibility=visibility)
        )
        supplied = replace(supplied, event=event)
        # One source event, consistently referenced in both typed positions;
        # its declared scope membership remains ACTIVE and unchanged.
        events = tuple(event if e.event_ref == event.event_ref else e for e in events)
    changed = replace(r, attempts=(replace(r.attempts[0], supplied=supplied),), events=events)
    assert changed.scope == r.scope and supplied.origin.visibility == A
    result = assess_evidence(bundle.context, changed)
    assert isinstance(result, BlockingFailure), result
    assert (result.category, result.code) == ("CONTRACT_VIOLATION", "NESTED_ORIGIN_SCOPE_MISMATCH")


@pytest.mark.parametrize("role", ["assertions", "subjects", "content_versions"])
@pytest.mark.parametrize("fault", ["omit", "role", "visibility"])
def test_r2_ir04_accepted_issuer_path_requires_declared_source_members(role, fault):
    bundle = inputs("A02-C01")
    r = bundle.request
    ref = {
        "assertions": r.requested.target_ref,
        "subjects": r.requested.subject_scope_refs[0],
        "content_versions": r.requested.content_version_ref,
    }[role]
    member = next(m for m in r.scope.input_members if m.key == (A, role, ref))
    members = tuple(m for m in r.scope.input_members if m != member)
    if fault != "omit":
        changed_member = (
            replace(member, role="opaque")
            if fault == "role"
            else replace(member, visibility=Visibility.DEPENDENCY)
        )
        members = (*members, changed_member)
    scope = replace(r.scope, input_members=tuple(sorted(members, key=lambda m: m.key)))
    changed = replace(r, scope=scope)
    assert changed.scope.raw_pins == r.scope.raw_pins
    result = assess_evidence(bundle.context, changed)
    assert isinstance(result, BlockingFailure), result
    assert (result.category, result.code) == ("CONTRACT_VIOLATION", "UNDECLARED_PATH_MEMBER")


@pytest.mark.parametrize("case", ["A01-C01", "A02-C01"])
@pytest.mark.parametrize("field", ["unit", "period"])
def test_r2_inv1_typed_unit_period_must_match_original_raw(case, field):
    bundle = inputs(case)
    r = bundle.request
    assertion = r.left.assertion if isinstance(r, SubjectComparisonRequest) else r.assertion
    changed_assertion = (
        replace(assertion, source_unit=Known("USD", assertion.origin))
        if field == "unit"
        else replace(assertion, reference_period=(date(2025, 1, 1), date(2025, 1, 31)))
    )
    if isinstance(r, SubjectComparisonRequest):
        request = replace(r, left=replace(r.left, assertion=changed_assertion))
        assert request.left.contents == r.left.contents
        result = compare_subjects(bundle.context, request)
    else:
        request = replace(r, assertion=changed_assertion)
        assert request.content == r.content
        result = assess_evidence(bundle.context, request)
    assert request.scope == r.scope
    assert isinstance(result, BlockingFailure), result
    assert result.code == "SOURCE_ASSERTION_MISMATCH"


@pytest.mark.parametrize(
    "field",
    ["economic_entity_ref", "metric", "reporting_scope", "basis_ref", "currency", "canonical_unit"],
)
def test_r2_inv1_subject_dimensions_are_source_backed(field):
    bundle = inputs("A01-C03")
    r = bundle.request
    subject = replace(r.left.subject, **{field: Known("OTHER", r.left.subject.origin)})
    result = compare_subjects(bundle.context, replace(r, left=replace(r.left, subject=subject)))
    assert isinstance(result, BlockingFailure), result
    assert result.code == "SOURCE_SUBJECT_MISMATCH"


def test_r2_inv1_absent_scope_cannot_be_filled_and_orders_omissions_stay_absent():
    bundle = inputs("A01-C04")
    r = bundle.request
    guessed = replace(r.right.subject, reporting_scope=Known("consolidated", CALLER))
    result = compare_subjects(bundle.context, replace(r, right=replace(r.right, subject=guessed)))
    assert isinstance(result, BlockingFailure) and result.code == "SOURCE_SUBJECT_MISMATCH"
    june = inputs("A02-C01")
    orders = json.loads(june.request.content.raw_bytes)["statements"][1]
    assert orders["metric"] == "orders_count"
    assert not {"reporting_scope", "basis_id", "currency"} & orders.keys()
    result = execute(june)
    assert result.state == "BOUND" and result.source_amount.value == 300
    assert result.requested_tuple.fragment_selector == "/statements/0"


@pytest.mark.parametrize("case", ["A01-C03", "A02-C01", "A02-C03"])
@pytest.mark.parametrize(
    "role",
    [
        "assertions",
        "subjects",
        "content_versions",
        "raw_assets",
        "supports",
        "evidence",
        "publication_events",
        "time_proofs",
    ],
)
def test_r2_inv4_each_accepted_source_role_is_required_across_entries(case, role):
    bundle = inputs(case)
    r = bundle.request
    binding = (
        r.left.supports[0]
        if isinstance(r, SubjectComparisonRequest)
        else r.attempts[0].supplied
        if isinstance(r, IssuerBindingRequest)
        else next(s for s in r.supports if s.target.target_ref == r.requested.target_ref)
    )
    refs = {
        "assertions": binding.target.target_ref,
        "subjects": binding.target.subject_scope_refs[0],
        "content_versions": binding.target.content_version_ref,
        "raw_assets": binding.target.representation_ref,
        "supports": binding.support_ref,
        "evidence": binding.evidence_ref,
        "publication_events": binding.event.event_ref,
        "time_proofs": binding.proof_candidate.proof_ref,
    }
    member = next(m for m in r.scope.input_members if m.key == (A, role, refs[role]))
    scope = replace(r.scope, input_members=tuple(m for m in r.scope.input_members if m != member))
    request = replace(r, scope=scope)
    result = (
        compare_subjects(bundle.context, request)
        if isinstance(r, SubjectComparisonRequest)
        else assess_evidence(bundle.context, request)
        if isinstance(r, IssuerBindingRequest)
        else inventory_content(bundle.context, request)
    )
    assert isinstance(result, BlockingFailure), result
    assert result.category == "CONTRACT_VIOLATION"
    assert scope.raw_pins == r.scope.raw_pins


@pytest.mark.parametrize("case", ["A01-C03", "A02-C01", "A02-C03"])
@pytest.mark.parametrize("nested", ["event", "proof"])
def test_r2_inv3_nested_visibility_checked_at_every_binding_entry(case, nested):
    bundle = inputs(case)
    r = bundle.request
    binding = (
        r.left.supports[0]
        if isinstance(r, SubjectComparisonRequest)
        else r.attempts[0].supplied
        if isinstance(r, IssuerBindingRequest)
        else next(s for s in r.supports if s.target.target_ref == r.requested.target_ref)
    )
    value = binding.event if nested == "event" else binding.proof_candidate
    changed_value = replace(value, origin=replace(value.origin, visibility=Visibility.AUDIT))
    changed_binding = replace(
        binding, **{"event" if nested == "event" else "proof_candidate": changed_value}
    )
    if isinstance(r, SubjectComparisonRequest):
        operand = replace(r.left, supports=(changed_binding,))
        result = compare_subjects(bundle.context, replace(r, left=operand))
    elif isinstance(r, IssuerBindingRequest):
        request = replace(r, attempts=(replace(r.attempts[0], supplied=changed_binding),))
        result = assess_evidence(bundle.context, request)
    else:
        request = replace(
            r, supports=tuple(changed_binding if s == binding else s for s in r.supports)
        )
        result = inventory_content(bundle.context, request)
    assert isinstance(result, BlockingFailure) and result.code == "NESTED_ORIGIN_SCOPE_MISMATCH"


@pytest.mark.parametrize("fault", ["schema", "membership"])
def test_r2_inv1_notice_schema_and_statement_membership_are_checked(fault):
    bundle = inputs("A02-C01")
    r = bundle.request
    content = (
        replace(r.content, source_schema="unreviewed-notice")
        if fault == "schema"
        else replace(r.content, statement_members=("A-JUN-01",))
    )
    result = assess_evidence(bundle.context, replace(r, content=content))
    assert isinstance(result, BlockingFailure), result
    assert result.code == (
        "UNSUPPORTED_SOURCE_SCHEMA" if fault == "schema" else "CONTENT_STATEMENT_MISMATCH"
    )


@pytest.mark.parametrize("role", ["observations", "raw_assets", "graph_edges"])
def test_r2_inv4_provider_closure_uses_capture_roles_only(role):
    bundle = inputs("A02-C04")
    r = bundle.request
    ref = {
        "observations": r.capture.observation_ref,
        "raw_assets": r.content.representation_ref,
        "graph_edges": r.capture_edges[0].edge_ref,
    }[role]
    members = tuple(m for m in r.scope.input_members if m.key != (U, role, ref))
    result = assess_evidence(
        bundle.context, replace(r, scope=replace(r.scope, input_members=members))
    )
    assert isinstance(result, BlockingFailure) and result.code == "UNDECLARED_PATH_MEMBER"


def test_r2_inv4_provider_edge_is_accounted_for_without_issuer_roles():
    bundle = inputs("A02-C04")
    result = execute(bundle)
    assert (result.state, result.reason) == ("UNRESOLVED", "ATTRIBUTION_UNRESOLVED")
    edge = bundle.request.capture_edges[0]
    assert (U, "graph_edges", edge.edge_ref) not in {m.key for m in result.provenance.excluded_uses}
    assert result.provenance.rejected_attempts == ()
    assert all(p.path_role == "CAPTURE_ONLY" for p in result.provenance.accepted_paths)
    assert actual_projection(bundle, result).system_outcome == result


@pytest.mark.parametrize(
    "field",
    ["value", "provider", "subject", "unit", "locator", "scope", "fragment", "target"],
)
def test_r3_ir01_provider_facts_must_match_unchanged_pinned_payload(field):
    bundle = inputs("A02-C04")
    r = bundle.request
    if field == "value":
        changed = replace(r, displayed_value=replace(r.displayed_value, value=999))
    elif field == "provider":
        changed = replace(
            r, content=replace(r.content, provider_ref=Known("OTHER", r.content.origin))
        )
    elif field == "subject":
        changed = replace(r, subject_reference=Known("OTHER", r.content.origin))
    elif field == "unit":
        changed = replace(r, source_unit=replace(r.source_unit, value="USD"))
    elif field == "locator":
        changed = replace(
            r, content=replace(r.content, source_locator=Known("OTHER", r.content.origin))
        )
    elif field == "scope":
        changed = replace(r, requested=replace(r.requested, subject_scope_refs=("OTHER",)))
    elif field == "fragment":
        changed = replace(r, requested=replace(r.requested, fragment_selector="/statements/0"))
    else:
        changed = replace(r, requested=replace(r.requested, target_ref="OTHER"))
    assert changed.content.raw_bytes == r.content.raw_bytes and changed.scope == r.scope
    result = assess_evidence(bundle.context, changed)
    assert isinstance(result, BlockingFailure), result
    assert result.category == "CONTRACT_VIOLATION"


def _r3_replace_binding(request, binding):
    if isinstance(request, SubjectComparisonRequest):
        return replace(request, left=replace(request.left, supports=(binding,)))
    if isinstance(request, IssuerBindingRequest):
        return replace(request, attempts=(replace(request.attempts[0], supplied=binding),))
    old = next(s for s in request.supports if s.target.target_ref == request.requested.target_ref)
    return replace(request, supports=tuple(binding if s == old else s for s in request.supports))


@pytest.mark.parametrize("case", ["A01-C03", "A02-C01", "A02-C03"])
@pytest.mark.parametrize("field", ["support", "evidence", "support_origin", "evidence_origin"])
def test_r3_ir02_source_identity_cannot_be_replaced_by_an_existing_scope_id(case, field):
    bundle = inputs(case)
    r = bundle.request
    binding = (
        r.left.supports[0]
        if isinstance(r, SubjectComparisonRequest)
        else r.attempts[0].supplied
        if isinstance(r, IssuerBindingRequest)
        else next(s for s in r.supports if s.target.target_ref == r.requested.target_ref)
    )
    foreign = next(s for s in inputs("A02-C03").request.supports if s.support_ref == "SUP-ORD1-PUB")
    if field == "support":
        changed = replace(binding, support_ref=foreign.support_ref)
    elif field == "evidence":
        changed = replace(binding, evidence_ref=foreign.evidence_ref)
    elif field == "support_origin":
        changed = replace(
            binding, origin=replace(binding.origin, object_id=foreign.origin.object_id)
        )
    else:
        target = replace(
            binding.target,
            origin=replace(binding.target.origin, object_id=foreign.target.origin.object_id),
        )
        changed = replace(binding, target=target)
    request = _r3_replace_binding(r, changed)
    result = execute(replace(bundle, request=request))
    assert isinstance(result, BlockingFailure), result
    code = (
        "DUPLICATE_SUPPORT_ID"
        if case == "A02-C03" and field == "support"
        else "BINDING_ORIGIN_IDENTITY_MISMATCH"
    )
    assert (result.category, result.code) == ("CONTRACT_VIOLATION", code)


@pytest.mark.parametrize("role", ["capture", "event"])
@pytest.mark.parametrize("visibility", [Visibility.AUDIT, Visibility.DEPENDENCY])
def test_r3_ir03_inventory_preserves_full_source_visibility(role, visibility):
    bundle = inputs("A02-C03")
    r = bundle.request
    values = r.captures if role == "capture" else r.events
    original = (
        next(c for c in values if c.representation_ref == r.content.representation_ref)
        if role == "capture"
        else values[0]
    )
    changed = replace(original, origin=replace(original.origin, visibility=visibility))
    supplied = tuple(changed if v == original else v for v in values)
    request = replace(r, **{"captures" if role == "capture" else "events": supplied})
    assert request.scope == r.scope
    result = inventory_content(bundle.context, request)
    assert isinstance(result, BlockingFailure), result
    assert (result.category, result.code) == ("CONTRACT_VIOLATION", "INCOMPLETE_INVENTORY_SCOPE")


def _r3_synthetic_provider_bytes(bundle, raw):
    """Artificial same-schema input, explicitly repinned; never a fixed R10 assertion."""
    r = bundle.request
    digest = hashlib.sha256(raw).hexdigest()
    content = replace(r.content, raw_bytes=raw, raw_length=len(raw), raw_sha256=digest)
    pins = tuple(
        replace(p, raw_length=len(raw), raw_sha256=digest)
        if p.representation_ref == content.representation_ref
        else p
        for p in r.scope.raw_pins
    )
    return replace(
        bundle,
        request=replace(
            r,
            content=content,
            capture=replace(r.capture, captured_sha256=digest),
            scope=replace(r.scope, raw_pins=pins),
        ),
    )


@pytest.mark.parametrize(
    "fault",
    ["bool", "float", "string", "nan", "duplicate", "extra", "missing", "schema", "utf8", "range"],
)
def test_r3_provider_bounded_schema_is_strict_even_with_synthetic_valid_pins(fault):
    bundle = inputs("A02-C04")
    body = json.loads(bundle.request.content.raw_bytes)
    if fault in {"bool", "float", "string", "range"}:
        body["displayed_value"] = {"bool": True, "float": 300.0, "string": "300", "range": 2**63}[
            fault
        ]
    elif fault == "extra":
        body["issuer_id"] = "FABRICATED"
    elif fault == "missing":
        del body["unit"]
    elif fault == "schema":
        body["schema"] = "synthetic-notice-v1"
    raw = json.dumps(body, separators=(",", ":")).encode()
    if fault == "nan":
        raw = raw.replace(b'"displayed_value":300', b'"displayed_value":NaN')
    elif fault == "duplicate":
        raw = raw[:-1] + b',"provider_id":"P-X"}'
    elif fault == "utf8":
        raw = b"\xff"
    synthetic = _r3_synthetic_provider_bytes(bundle, raw)
    result = execute(synthetic)
    assert isinstance(result, BlockingFailure), result
    assert result.category == "CONTRACT_VIOLATION"
    assert result.code in {
        "INVALID_NUMERIC_TYPE",
        "NUMERIC_RANGE",
        "DUPLICATE_SOURCE_KEY",
        "PROVIDER_PAYLOAD_CONTRACT_INVALID",
        "UNSUPPORTED_SOURCE_SCHEMA",
    }


def test_r3_provider_consistent_alternative_payload_is_not_a_hardcoded_expected_value():
    bundle = inputs("A02-C04")
    r = bundle.request
    assert (r.content.raw_length, r.content.raw_sha256) == (
        237,
        "2adcf78f2a9e3d8b141adda02d0fa6e6d80799a15d6fd8c36fa83063de7212a8",
    )
    body = json.loads(r.content.raw_bytes)
    body.update(
        provider_id="P-SYNTHETIC",
        subject_reference="SUB-SYNTHETIC",
        displayed_value=999,
        unit="USD",
        source_locator="synthetic://alternative",
    )
    synthetic = _r3_synthetic_provider_bytes(bundle, json.dumps(body).encode())
    request = synthetic.request
    content = replace(
        request.content,
        provider_ref=Known(body["provider_id"], r.content.origin),
        source_locator=Known(body["source_locator"], r.content.origin),
    )
    request = replace(
        request,
        content=content,
        subject_reference=Known(body["subject_reference"], r.content.origin),
        displayed_value=Known(body["displayed_value"], r.content.origin),
        source_unit=Known(body["unit"], r.content.origin),
        requested=replace(r.requested, subject_scope_refs=(body["subject_reference"],)),
    )
    result = assess_evidence(bundle.context, request)
    assert isinstance(result, EvidenceOutcome), result
    assert (result.state, result.reason) == ("UNRESOLVED", "ATTRIBUTION_UNRESOLVED")
    assert result.source_amount.value == 999 and type(result.source_amount.value) is int
    assert result.source_attribution.provider.value == "P-SYNTHETIC"
    assert len(result.provenance.accepted_paths) == 1
    assert result.supplied_bindings == result.publication_event_facts == result.assessments == ()
    assert result.provenance.rejected_attempts == ()
    assert isinstance(result.source_attribution.issuer, Unknown)


@pytest.mark.parametrize("field", ["cv", "representation"])
def test_r3_provider_requested_content_identity_cannot_disagree_with_source(field):
    bundle = inputs("A02-C04")
    r = bundle.request
    if field == "representation":
        changed = replace(r, requested=replace(r.requested, representation_ref="OTHER"))
        code = "REQUEST_CONTENT_MISMATCH"
    else:
        # Make caller-owned CV positions consistent; the unchanged pinned payload still disagrees.
        content = replace(r.content, content_version_ref="OTHER")
        pins = tuple(
            replace(p, content_version_ref="OTHER")
            if p.representation_ref == content.representation_ref
            else p
            for p in r.scope.raw_pins
        )
        changed = replace(
            r,
            content=content,
            requested=replace(r.requested, content_version_ref="OTHER"),
            scope=replace(r.scope, raw_pins=pins),
        )
        code = "PROVIDER_SOURCE_MISMATCH"
    assert changed.content.raw_bytes == r.content.raw_bytes
    result = assess_evidence(bundle.context, changed)
    assert isinstance(result, BlockingFailure) and result.code == code


@pytest.mark.parametrize("role", ["capture", "event"])
@pytest.mark.parametrize("fault", ["duplicate", "origin", "omit"])
def test_r3_inventory_full_identity_cannot_be_duplicated_omitted_or_forged(role, fault):
    bundle = inputs("A02-C03")
    r = bundle.request
    values = r.captures if role == "capture" else r.events
    if fault == "duplicate":
        changed = (*values, values[0])
        code = "DUPLICATE_INVENTORY_IDENTITY"
    elif fault == "omit":
        changed = values[1:]
        code = "INCOMPLETE_INVENTORY_SCOPE"
    else:
        changed = (
            replace(
                values[0], origin=replace(values[0].origin, object_id=OriginKnownValue("OTHER"))
            ),
            *values[1:],
        )
        code = "INVENTORY_ORIGIN_IDENTITY_MISMATCH"
    result = inventory_content(
        bundle.context, replace(r, **{"captures" if role == "capture" else "events": changed})
    )
    assert isinstance(result, BlockingFailure) and result.code == code


def test_r3_inventory_preserves_explicitly_supplied_auxiliary_capture_membership():
    bundle = inputs("A02-C03")
    r = bundle.request
    capture = next(c for c in r.captures if c.representation_ref == r.content.representation_ref)
    captures = tuple(
        replace(c, origin=replace(c.origin, visibility=U)) if c == capture else c
        for c in r.captures
    )
    members = tuple(
        sorted(
            (
                replace(m, visibility=U)
                if m.key == (A, "observations", capture.observation_ref)
                else m
                for m in r.scope.input_members
            ),
            key=lambda m: m.key,
        )
    )
    result = inventory_content(
        bundle.context, replace(r, captures=captures, scope=replace(r.scope, input_members=members))
    )
    assert isinstance(result, EvidenceOutcome), result
    assert (result.state, result.reason) == ("BOUND", "NONE")
    assert len(result.capture_facts) == 2 and len(result.publication_event_facts) == 1
    observed = next(c for c in result.capture_facts if c.observation_ref == capture.observation_ref)
    assert observed.origin.visibility == U


@pytest.mark.parametrize("nested", ["event", "proof"])
def test_r2_inv3_existing_member_id_cannot_replace_its_source_origin(nested):
    bundle = inputs("A02-C01")
    r = bundle.request
    inventory = inputs("A02-C03").request
    may = next(s for s in inventory.supports if s.target.content_version_ref == "CV-MAY-01")
    binding = r.attempts[0].supplied
    changed = (
        replace(binding, event=replace(binding.event, event_ref=may.event.event_ref))
        if nested == "event"
        else replace(
            binding,
            proof_candidate=replace(
                binding.proof_candidate, proof_ref=may.proof_candidate.proof_ref
            ),
        )
    )
    result = assess_evidence(
        bundle.context, replace(r, attempts=(replace(r.attempts[0], supplied=changed),))
    )
    assert isinstance(result, BlockingFailure) and result.code == "NESTED_ORIGIN_IDENTITY_MISMATCH"


@pytest.mark.parametrize("field", ["event_kind", "event_ref", "proof_ref", "proof_target"])
def test_sensitivity_event_and_proof_cannot_substitute_for_content_binding(field):
    bundle = inputs("A02-C01")
    r = bundle.request
    supplied = r.attempts[0].supplied
    events = r.events
    if field == "event_kind":
        event = replace(supplied.event, event_kind="capture_only")
        events = tuple(event if e.event_ref == event.event_ref else e for e in events)
        supplied = replace(supplied, event=event)
    elif field == "event_ref":
        supplied = replace(supplied, event=replace(supplied.event, event_ref="UNSUPPLIED-EVENT"))
    elif field == "proof_ref":
        supplied = replace(
            supplied, proof_candidate=replace(supplied.proof_candidate, proof_ref="TP-ORD-01")
        )
    else:
        supplied = replace(
            supplied, proof_candidate=replace(supplied.proof_candidate, target_ref="A-ORD-01")
        )
    changed = replace(r, attempts=(replace(r.attempts[0], supplied=supplied),), events=events)
    result = assess_evidence(bundle.context, changed)
    if field in {"event_ref", "proof_ref"}:
        # INV-3/INV-4: a fabricated source member is malformed input, not
        # the complete, valid foreign support represented by A02-C02.
        assert isinstance(result, BlockingFailure), result
        assert (result.category, result.code) == ("CONTRACT_VIOLATION", "UNDECLARED_PATH_MEMBER")
        return
    assert (result.state, result.reason) == ("UNRESOLVED", "CONTENT_BINDING_INSUFFICIENT")
    assert result.assessments[0].disposition == "REJECTED"
    assert result.provenance.accepted_paths == ()


def test_sensitivity_conflicting_issuer_identity_and_projected_lineage_are_detected():
    bundle = inputs("A02-C01")
    r = bundle.request
    binding = r.attempts[0].supplied
    forged = replace(binding, event=replace(binding.event, issuer_ref="OTHER-ISSUER"))
    result = assess_evidence(
        bundle.context, replace(r, attempts=(replace(r.attempts[0], supplied=forged),))
    )
    assert isinstance(result, BlockingFailure) and result.code == "IMMUTABLE_ID_CONFLICT"
    actual = execute(bundle)
    path = actual.provenance.accepted_paths[0]
    for field, value in (
        ("event_ref", "PUB-MAY-01"),
        ("evidence_ref", "EVID-ORD-01"),
        ("time_proof_ref", "TP-MAY-01"),
    ):
        changed = replace(
            actual,
            provenance=replace(
                actual.provenance, accepted_paths=(replace(path, **{field: value}),)
            ),
        )
        with pytest.raises(ContractError):
            actual_projection(bundle, changed)
