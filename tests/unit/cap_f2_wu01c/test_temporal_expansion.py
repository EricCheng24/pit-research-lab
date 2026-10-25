"""A02 typed synthetic engineering variations; no Golden evaluation or source trust."""

import json
from dataclasses import asdict, replace
from datetime import date

import pytest
from test_pit_slice import assert_isolated, exact_request, inputs
from test_pit_slice import code as code
from wu01_inputs import (
    NA,
    AdaptedS1Input,
    InvocationSelector,
    materialize_input,
    synthetic_proof,
    synthetic_scope,
)

from pit_research_lab.domain import temporal
from pit_research_lab.domain.contracts import (
    AuthenticatedDate,
    BlockingFailure,
    ContractError,
    EvidenceOutcome,
    Known,
    NotEvaluated,
    OriginKnownValue,
    PublicationUpperBound,
    Unknown,
    UnknownCause,
    UnresolvedSourceTime,
    Visibility,
)
from pit_research_lab.domain.information import assess_evidence, compare_subjects
from pit_research_lab.domain.pit_slice import evaluate_slice
from pit_research_lab.domain.temporal import DerivedDateBound, qualify_temporal


def identity(proof):
    return {
        name: getattr(proof, name)
        for name in (
            "proof_ref",
            "target_kind",
            "target_ref",
            "content_version_ref",
            "fragment_selector",
            "origin",
        )
    }


def descriptor(proof, kind, **values):
    raw = dict(proof.raw_descriptor)
    for key in (
        "timestamp",
        "upper_bound",
        "bound",
        "source_date",
        "unparsed_source_text",
        "timezone",
        "offset",
        "precision",
    ):
        raw[key] = None
    raw.update(proof_kind=kind, **values)
    return tuple(sorted(raw.items()))


def upper(request, text="2025-07-07T00:00:00+08:00", closure="OPEN", zone="Asia/Taipei"):
    old = request.attempts[0].supplied.proof_candidate
    stamp = replace(old.timestamp, source_text=text, offset=text[-6:], timezone_name=zone)
    return PublicationUpperBound(
        **identity(old),
        upper_bound=stamp,
        closure=closure,
        raw_descriptor=descriptor(
            old,
            "upper_bound",
            upper_bound=text,
            bound=closure,
            timezone=zone,
            offset=text[-6:],
            precision="SECOND",
        ),
    )


def source_date(
    request, day=date(2025, 7, 6), endpoint="2025-07-07T00:00:00+08:00", zone="Asia/Taipei"
):
    old = request.attempts[0].supplied.proof_candidate
    stamp = replace(old.timestamp, source_text=endpoint, offset=endpoint[-6:], timezone_name=zone)
    return AuthenticatedDate(
        **identity(old),
        source_date=Known(day, old.origin),
        timezone=Known(zone, old.origin),
        declared_upper_bound=stamp,
        raw_descriptor=descriptor(
            old,
            "date_with_upper_bound",
            source_date=day.isoformat(),
            upper_bound=endpoint,
            bound="OPEN",
            timezone=zone,
            offset=endpoint[-6:],
            precision="DAY",
        ),
    )


def unknown_time(request, zone_known=False):
    old = request.attempts[0].supplied.proof_candidate
    unknown = Unknown(UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, old.origin)
    return UnresolvedSourceTime(
        **identity(old),
        source_text="2025-07-07 00:30 (unresolved zone)",
        timezone=Known("Asia/Taipei", old.origin) if zone_known else unknown,
        offset=unknown,
        precision=Known("MINUTE", old.origin),
        raw_descriptor=descriptor(
            old,
            "unparsed_source_time",
            unparsed_source_text="2025-07-07 00:30 (unresolved zone)",
            timezone="Asia/Taipei" if zone_known else None,
            precision="MINUTE",
        ),
    )


def with_proof(request, proof):
    return synthetic_proof(request, proof)


def cutoff(context, text, zone="Asia/Taipei"):
    return replace(
        context,
        information_cutoff=replace(
            context.information_cutoff, source_text=text, offset=text[-6:], timezone_name=zone
        ),
    )


@pytest.mark.parametrize("closure", ["OPEN", "CLOSED"])
@pytest.mark.parametrize(
    "text,relation",
    [
        ("2025-07-06T23:59:59+08:00", "before"),
        ("2025-07-07T00:00:00+08:00", "equal"),
        ("2025-07-07T00:00:01+08:00", "after"),
    ],
)
def test_upper_bound_closure_matrix(code, closure, text, relation):
    b = inputs(code)
    p = upper(b.request, text, closure)
    result = evaluate_slice(b.context, with_proof(b.request, p), code)
    supported = relation == "before" or (relation == "equal" and closure == "OPEN")
    assert (result.s1.state, result.s1.reason) == ("BOUND", "NONE")
    assert result.s2.state == ("SUPPORTED" if supported else "UNRESOLVED")
    assert result.s2.reason == ("NONE" if supported else "TEMPORAL_BOUND_INSUFFICIENT")
    assert result.s2.evaluated_evidence is p
    assert not hasattr(p, "timestamp")
    assert_isolated(result)


@pytest.mark.parametrize(
    "day,endpoint",
    [
        (date(2025, 7, 6), "2025-07-07T00:00:00+08:00"),
        (date(2025, 1, 31), "2025-02-01T00:00:00+08:00"),
        (date(2025, 12, 31), "2026-01-01T00:00:00+08:00"),
        (date(2024, 2, 28), "2024-02-29T00:00:00+08:00"),
        (date(2024, 2, 29), "2024-03-01T00:00:00+08:00"),
        (date(2025, 2, 28), "2025-03-01T00:00:00+08:00"),
    ],
)
def test_date_rollover_and_derived_bound(code, day, endpoint):
    b = inputs(code)
    p = source_date(b.request, day, endpoint)
    c = cutoff(b.context, endpoint)
    result = evaluate_slice(c, with_proof(b.request, p), code)
    assert result.s2.state == "SUPPORTED"
    assert result.s2.derived_bound == DerivedDateBound(p.proof_ref, day, "Asia/Taipei", endpoint)
    assert p.source_precision == "DAY" and p.closure == "OPEN"
    assert not hasattr(p, "timestamp")
    assert_isolated(result)


@pytest.mark.parametrize(
    "text,state",
    [
        ("2025-07-05T00:00:00+08:00", "UNRESOLVED"),
        ("2025-07-06T00:00:00+08:00", "UNRESOLVED"),
        ("2025-07-06T09:00:00+08:00", "UNRESOLVED"),
        ("2025-07-07T00:00:00+08:00", "SUPPORTED"),
        ("2025-07-07T00:00:01+08:00", "SUPPORTED"),
    ],
)
def test_date_cutoff_before_inside_equal_after(code, text, state):
    b = inputs(code)
    result = evaluate_slice(
        cutoff(b.context, text), with_proof(b.request, source_date(b.request)), code
    )
    assert result.s2.state == state
    assert_isolated(result)


@pytest.mark.parametrize(
    "fault",
    [
        "target_ref",
        "content_version_ref",
        "fragment_selector",
        "visibility",
        "origin_pointer",
        "origin_id",
        "membership",
        "descriptor",
        "duplicate",
        "mixed",
        "time_origin",
        "evidence_membership",
    ],
)
def test_bound_provenance_never_yields_temporal_support(code, fault):
    b = inputs(code)
    p = upper(b.request)
    r = b.request
    if fault in {"target_ref", "content_version_ref", "fragment_selector"}:
        p = replace(p, **{fault: "FOREIGN"})
    elif fault == "visibility":
        p = replace(p, origin=replace(p.origin, visibility=Visibility.AUDIT))
    elif fault == "origin_pointer":
        p = replace(p, origin=replace(p.origin, envelope_pointer="/foreign/time_proofs/TP-JUN1"))
    elif fault == "origin_id":
        p = replace(p, origin=replace(p.origin, object_id=OriginKnownValue("FOREIGN")))
    elif fault in {"membership", "evidence_membership"}:
        role = "time_proofs" if fault == "membership" else "evidence"
        r = replace(
            r,
            scope=replace(
                r.scope, input_members=tuple(m for m in r.scope.input_members if m.role != role)
            ),
        )
    elif fault == "time_origin":
        p = replace(
            p,
            upper_bound=replace(
                p.upper_bound, origin=replace(p.origin, envelope_pointer="/foreign")
            ),
        )
    elif fault == "duplicate":
        p = replace(p, raw_descriptor=p.raw_descriptor + (p.raw_descriptor[0],))
    else:
        raw = dict(p.raw_descriptor)
        raw["upper_bound" if fault == "descriptor" else "timestamp"] = "2000-01-01T00:00:00+08:00"
        p = replace(p, raw_descriptor=tuple(sorted(raw.items())))
    result = evaluate_slice(b.context, with_proof(r, p), code)
    assert isinstance(result.s2, BlockingFailure) or result.s2.state == "UNRESOLVED"
    assert_isolated(result)


@pytest.mark.parametrize(
    "fault", ["absent_date", "unknown_zone", "absent_bound", "wrong_bound", "foreign_origin"]
)
def test_date_incomplete_or_contradictory(code, fault):
    b = inputs(code)
    p = source_date(b.request)
    raw = dict(p.raw_descriptor)
    if fault == "absent_date":
        p = replace(p, source_date=Unknown(UnknownCause.ABSENT_SOURCE_FIELD, None, p.origin))
        raw["source_date"] = None
    elif fault == "unknown_zone":
        p = replace(
            p,
            timezone=Unknown(UnknownCause.AMBIGUOUS_SOURCE, None, p.origin),
            declared_upper_bound=NotEvaluated("S2", "NO_SOURCE_ZONE"),
        )
        raw.update(timezone=None, upper_bound=None, offset=None)
    elif fault == "absent_bound":
        p = replace(p, declared_upper_bound=NotEvaluated("S2", "NO_DECLARED_BOUND"))
        raw.update(upper_bound=None, offset=None)
    elif fault == "wrong_bound":
        p = source_date(b.request, endpoint="2025-07-06T00:00:00+08:00")
        raw = dict(p.raw_descriptor)
    else:
        p = replace(
            p,
            source_date=replace(
                p.source_date, origin=replace(p.origin, envelope_pointer="/other/source_date")
            ),
        )
    p = replace(p, raw_descriptor=tuple(sorted(raw.items())))
    result = evaluate_slice(b.context, with_proof(b.request, p), code)
    assert isinstance(result.s2, BlockingFailure) or result.s2.state == "UNRESOLVED"
    if fault == "unknown_zone":
        assert result.s2.reason == "TIMEZONE_UNRESOLVED"
    assert_isolated(result)


@pytest.mark.parametrize("known_zone", [False, True])
def test_unparsed_time_preserves_text_unknowns_and_never_parses(code, known_zone):
    b = inputs(code)
    p = unknown_time(b.request, known_zone)
    result = evaluate_slice(b.context, with_proof(b.request, p), code)
    assert result.s1.state == "BOUND"
    assert result.s2.state == "UNRESOLVED"
    assert result.s2.reason == (
        "TEMPORAL_BOUND_INSUFFICIENT" if known_zone else "TIMEZONE_UNRESOLVED"
    )
    assert result.s2.evaluated_evidence is p
    assert "SOURCE_TIME_UNPARSED" in result.s2.diagnostics
    assert isinstance(result.s2.derived_bound, NotEvaluated)
    assert_isolated(result)


@pytest.mark.parametrize("location", ["publication", "cutoff", "capture", "upper", "date_bound"])
@pytest.mark.parametrize("fault", ["fraction", "zero_fraction", "empty_offset", "malformed_offset"])
def test_instant_defect_rejected_at_s2_boundary(code, location, fault):
    b = inputs(code)
    r, c = b.request, b.context
    stamp = c.information_cutoff
    if location == "publication":
        stamp = r.attempts[0].supplied.proof_candidate.timestamp
    elif location == "capture":
        stamp = next(
            x for x in r.captures if x.representation_ref == r.content.representation_ref
        ).completion.value
    elif location == "upper":
        stamp = upper(r).upper_bound
    elif location == "date_bound":
        stamp = source_date(r).declared_upper_bound
    if fault in {"fraction", "zero_fraction"}:
        text = (
            stamp.source_text[:-6]
            + (".999999" if fault == "fraction" else ".000000")
            + stamp.offset
        )
        stamp = replace(stamp, source_text=text)
    else:
        stamp = replace(stamp, offset="" if fault == "empty_offset" else "08:00")
    # The unchanged AwareInstant constructor still accepts the malformed record.
    if location == "cutoff":
        c = replace(c, information_cutoff=stamp)
    elif location == "capture":
        captures = tuple(
            replace(x, completion=Known(stamp, x.completion.origin))
            if x.representation_ref == r.content.representation_ref
            else x
            for x in r.captures
        )
        r = replace(r, captures=captures, scope=synthetic_scope(r.scope, captures=captures))
        c = replace(c, mode="prospective_observed")
    else:
        p = (
            r.attempts[0].supplied.proof_candidate
            if location == "publication"
            else (upper(r) if location == "upper" else source_date(r))
        )
        raw = dict(p.raw_descriptor)
        raw["timestamp" if location == "publication" else "upper_bound"] = stamp.source_text
        raw["offset"] = stamp.offset
        field = {
            "publication": "timestamp",
            "upper": "upper_bound",
            "date_bound": "declared_upper_bound",
        }[location]
        p = replace(p, **{field: stamp, "raw_descriptor": tuple(sorted(raw.items()))})
        r = with_proof(r, p)
    result = evaluate_slice(c, r, code)
    assert isinstance(result.s2, BlockingFailure)
    assert result.s2.code in {"INVALID_EXPLICIT_OFFSET", "SECOND_PRECISION_REQUIRED"}
    assert_isolated(result)


def test_mismatched_offset_and_invalid_civil_date_fail_closed(code):
    b = inputs(code)
    stamp = b.context.information_cutoff
    with pytest.raises(ContractError, match="OFFSET_MISMATCH"):
        replace(stamp, offset="+09:00")
    with pytest.raises(ValueError):
        date(2025, 2, 29)
    p = source_date(b.request)
    with pytest.raises(ContractError, match="INVALID_SOURCE_DATE"):
        replace(p, source_date=Known("2025-02-29", p.origin))
    with pytest.raises(ContractError, match="INVALID_IDENTIFIER"):
        replace(p, timezone=Known("", p.origin))


def test_date_overflow_does_not_guess_endpoint(code):
    b = inputs(code)
    p = source_date(b.request, date.max, "9999-12-31T00:00:00+08:00")
    result = evaluate_slice(b.context, with_proof(b.request, p), code)
    assert isinstance(result.s2, BlockingFailure) and result.s2.code == "DATE_BOUND_OUT_OF_RANGE"


def test_zone_database_unavailable_is_operational_failure(code, monkeypatch):
    b = inputs(code)

    def unavailable(name):
        raise temporal.ZoneInfoNotFoundError(name)

    monkeypatch.setattr(temporal, "ZoneInfo", unavailable)
    result = evaluate_slice(b.context, with_proof(b.request, source_date(b.request)), code)
    assert isinstance(result.s2, BlockingFailure)
    assert (result.s2.category, result.s2.code) == ("OPERATIONAL_ERROR", "ZONE_DATA_UNAVAILABLE")
    assert_isolated(result)


def test_date_minimum_cannot_overflow_into_a_positive_finding(code):
    b = inputs(code)
    p = source_date(b.request, date.min, "0001-01-02T00:00:00+08:00")
    result = evaluate_slice(b.context, with_proof(b.request, p), code)
    assert isinstance(result.s2, BlockingFailure)
    assert result.s2.code == "DATE_BOUND_OUT_OF_RANGE"
    assert_isolated(result)


@pytest.mark.parametrize(
    "day,endpoint,zone",
    [
        (date(2011, 12, 29), "2011-12-30T00:00:00-10:00", "Pacific/Apia"),
        (date(2011, 12, 30), "2011-12-31T00:00:00+14:00", "Pacific/Apia"),
        (date(2025, 11, 1), "2025-11-02T00:00:00-04:00", "America/Havana"),
    ],
)
def test_nonexistent_or_ambiguous_civil_midnight_blocks(code, day, endpoint, zone):
    b = inputs(code)
    result = evaluate_slice(
        b.context, with_proof(b.request, source_date(b.request, day, endpoint, zone)), code
    )
    assert isinstance(result.s2, BlockingFailure)
    assert result.s2.code == "NONRESOLVABLE_LOCAL_MIDNIGHT"
    assert_isolated(result)


def test_dst_date_derives_local_next_midnight_not_24_hours(code):
    b = inputs(code)
    p = source_date(b.request, date(2025, 3, 9), "2025-03-10T00:00:00-04:00", "America/New_York")
    c = cutoff(b.context, "2025-03-10T04:00:00+00:00", "UTC")
    result = evaluate_slice(c, with_proof(b.request, p), code)
    assert result.s2.state == "SUPPORTED"
    assert result.s2.derived_bound.upper_bound == "2025-03-10T00:00:00-04:00"
    assert_isolated(result)


@pytest.mark.parametrize(
    "text,state",
    [
        ("2025-11-02T01:30:00-04:00", "SUPPORTED"),
        ("2025-11-02T01:30:00-05:00", "NOT_ADMISSIBLE"),
        ("2025-03-09T02:30:00-05:00", "BLOCKED"),
    ],
)
def test_explicit_offset_disambiguates_overlap_but_not_gap(code, text, state):
    b = inputs(code)
    c = cutoff(b.context, "2025-11-02T06:00:00+00:00", "UTC")
    result = evaluate_slice(c, exact_request(b.request, text, "America/New_York"), code)
    if state == "BLOCKED":
        assert isinstance(result.s2, BlockingFailure) and result.s2.code == "ZONE_OFFSET_CONFLICT"
    else:
        assert result.s2.state == state
    assert_isolated(result)


def test_multiple_proofs_are_not_selected_for_favorable_time(code):
    b = inputs(code)
    r = with_proof(b.request, upper(b.request))
    r = replace(r, attempts=(r.attempts[0], r.attempts[0]))
    result = evaluate_slice(b.context, r, code)
    assert isinstance(result.s1, BlockingFailure)
    assert result.s1.code == "UNSUPPORTED_SEMANTIC_COMBINATION"
    assert result.s2.state == "UNRESOLVED"
    s1 = assess_evidence(b.context, with_proof(b.request, upper(b.request)))
    outcome = qualify_temporal(
        b.context,
        with_proof(b.request, upper(b.request)),
        replace(s1, assessments=s1.assessments * 2),
    )
    assert outcome.state == "UNRESOLVED"
    assert outcome.diagnostics == ("S1_OUTCOME_MISMATCH",)


@pytest.mark.parametrize("kind", ["upper", "date", "unknown"])
def test_union_structural_transport_for_identity_and_inventory(code, kind):
    b = inputs(code)
    p = {"upper": upper, "date": source_date, "unknown": unknown_time}[kind](b.request)
    inventory = inputs(code, "A02-C03")
    r = inventory.request
    supports = tuple(
        replace(s, proof_candidate=p) if s.support_ref == "SUP-JUN1-PUB" else s for s in r.supports
    )
    result = evaluate_slice(
        inventory.context,
        replace(r, supports=supports, scope=synthetic_scope(r.scope, supports=supports)),
        code,
    )
    assert isinstance(result.s1, EvidenceOutcome) and result.s1.state == "BOUND"
    assert result.s2.state == ("UNRESOLVED" if kind == "unknown" else "SUPPORTED")
    selector = InvocationSelector(
        "COMPARE_SUBJECTS",
        ("A-JUN-01", "A-JUN-PEER"),
        NA,
        (Visibility.ACTIVE, Visibility.AUXILIARY),
    )
    identity_input = materialize_input("A01-C03", selector, b.context.profile)
    assert isinstance(identity_input, AdaptedS1Input)
    req = identity_input.request
    left = replace(
        req.left, supports=tuple(replace(s, proof_candidate=p) for s in req.left.supports)
    )
    reference = tuple(
        replace(s, proof_candidate=p) if s.support_ref == "SUP-JUN1-PUB" else s
        for s in req.scope.source_records.supports
    )
    actual = compare_subjects(
        identity_input.context,
        replace(req, left=left, scope=synthetic_scope(req.scope, supports=reference)),
    )
    assert actual.state == "SAME"  # S1 computes no temporal eligibility.
    assert_isolated(result)


def test_bound_utc_equivalence_rejected_old_support_and_mode_isolation(code):
    b = inputs(code)
    p = upper(b.request, "2025-07-06T16:00:00+00:00", "OPEN", "UTC")
    assert evaluate_slice(b.context, with_proof(b.request, p), code).s2.state == "SUPPORTED"
    old = inputs(code, "A02-C02")
    result = evaluate_slice(old.context, with_proof(old.request, upper(old.request)), code)
    assert result.s1.state == result.s2.state == "UNRESOLVED"
    assert result.s2.reason == "CONTENT_BINDING_INSUFFICIENT"
    observed = evaluate_slice(
        replace(b.context, mode="prospective_observed"), with_proof(b.request, p), code
    )
    assert (
        observed.s2.state == "NOT_ADMISSIBLE" and observed.s2.reason == "OBSERVATION_AFTER_CUTOFF"
    )
    assert_isolated(observed)


def test_compact_examples_and_deterministic_replay(code):
    b = inputs(code)
    rows = []
    for label, p in [
        ("OPEN at cutoff", upper(b.request)),
        ("CLOSED at cutoff", upper(b.request, closure="CLOSED")),
        ("prior-day source date", source_date(b.request)),
        ("unparsed source time", unknown_time(b.request)),
    ]:
        r = with_proof(b.request, p)
        result = evaluate_slice(b.context, r, code)
        assert evaluate_slice(b.context, r, code) == result
        assert result.s1.provenance == result.s2.provenance
        assert result.request is r and result.context is b.context
        assert result.declared_s1_pins == b.context.profile.code_pins
        assert_isolated(result)
        rows.append(
            {
                "example": label,
                "s1": [result.s1.state, result.s1.reason],
                "s2": [result.s2.state, result.s2.reason],
                "proof": asdict(p),
                "derived_bound": asdict(result.s2.derived_bound),
                "diagnostics": result.s2.diagnostics,
                "content": r.content.content_version_ref,
                "raw_sha256": r.content.raw_sha256,
                "requested": asdict(r.requested),
                "context": b.context.context_ref,
                "cutoff": b.context.information_cutoff.source_text,
                "mode": b.context.mode,
                "trust": result.trust,
                "admission_eligible": result.admission_eligible,
            }
        )
    print(json.dumps(rows, indent=2, sort_keys=True, default=lambda value: value.isoformat()))
