"""Coherent synthetic source variations; no Golden/Expected/acceptance capability."""

import json
from dataclasses import fields, replace
from hashlib import sha256

from wu01_inputs import CALLER, NA, AdaptedS1Input, InvocationSelector, materialize_input

from pit_research_lab.domain.asof_slice import AsOfRequest
from pit_research_lab.domain.contracts import (
    SCHEMA,
    AssertionFacts,
    CandidateProfile,
    CaptureEdge,
    CaptureFacts,
    ContentFacts,
    ContentPin,
    FieldOrigin,
    IssuerBindingRequest,
    Known,
    NotApplicable,
    OriginKnownValue,
    PublicationEventFacts,
    RequestBindingAttempt,
    RequestedTuple,
    RoleRef,
    S1Scope,
    SourceRecords,
    SupportBinding,
    TimeProof,
    Unknown,
    UnknownCause,
    UnresolvedSourceTime,
    Visibility,
)
from pit_research_lab.domain.selection import (
    REQUIRED_CHECKS,
    BoundedCoverage,
    CandidateSource,
    CoverageCheck,
    DirectRelation,
    HistoricalLead,
    RelationSource,
    SelectionPolicy,
    relation_proposition,
)

NO_LEAD = NotApplicable("S3", "NO_HISTORICAL_CLUE")


def seed(code):
    profile = CandidateProfile(
        SCHEMA,
        "wu01-unit-v0.1-CANDIDATE",
        "wu01-reasons-v0.1-CANDIDATE",
        "s1-information-v0.1-CANDIDATE",
        code.observed_working_files,
        CALLER,
    )
    a, u = Visibility.ACTIVE, Visibility.AUXILIARY
    bundle = materialize_input(
        "A02-C01", InvocationSelector("CHECK_BINDING", ("A-JUN-01",), "SUP-JUN1-PUB", (a,)), profile
    )
    subject_bundle = materialize_input(
        "A01-C03",
        InvocationSelector("COMPARE_SUBJECTS", ("A-JUN-01", "A-JUN-PEER"), NA, (a, u)),
        profile,
    )
    assert isinstance(bundle, AdaptedS1Input) and isinstance(subject_bundle, AdaptedS1Input)
    return bundle, subject_bundle.request.left.subject


def source(
    code,
    tag,
    amount=300,
    published="2025-07-03T14:00:00+08:00",
    *,
    metric=None,
    unit="NTD_thousands",
    historical=False,
    unknown=False,
    unbound=False,
):
    base, anchor = seed(code)
    a, cv, rep, evid, sup, pub, tp, obs = (
        prefix + tag for prefix in ("A-", "CV-", "REP-", "EVID-", "SUP-", "PUB-", "TP-", "OBS-")
    )
    subject_ref = anchor.subject_ref if metric is None else "SUB-DECL-" + tag
    body = json.loads(base.request.content.raw_bytes)
    statement = body["statements"][0]
    statement.update(assertion_id=a, subject_id=subject_ref, value=amount, unit=unit)
    if metric is not None:
        statement["metric"] = metric
    body.update(
        content_version_id=cv, source_locator="synthetic://a03/" + tag, statements=[statement]
    )
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(raw).hexdigest()
    prefix = "/a03_inputs/" + tag + "/facts/"

    def origin(role, ref, suffix=""):
        return FieldOrigin(
            Visibility.ACTIVE,
            prefix + role + "/" + ref + suffix,
            OriginKnownValue(ref),
            OriginKnownValue("synthetic-notice-v1"),
            OriginKnownValue(digest),
        )

    content_origin = origin("raw_assets", rep)
    content = ContentFacts(
        cv,
        rep,
        raw,
        len(raw),
        digest,
        "synthetic-notice-v1",
        Known("SRC-ISSUER-A", content_origin),
        Known("SYN-A", content_origin),
        Unknown(UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, content_origin),
        Known(body["source_locator"], content_origin),
        (a,),
        (),
        content_origin,
    )
    subject_origin = origin("subjects", subject_ref)
    fact_updates = {
        f.name: replace(getattr(anchor, f.name), origin=subject_origin)
        for f in fields(anchor)
        if isinstance(getattr(anchor, f.name), (Known, Unknown))
    }
    fact_updates.update(
        metric=Known(statement["metric"], subject_origin),
        canonical_unit=Known(unit, subject_origin),
    )
    subject = replace(anchor, **fact_updates, subject_ref=subject_ref, origin=subject_origin)
    assertion_origin = origin("assertions", a)
    assertion = AssertionFacts(
        a,
        subject_ref,
        Known(amount, assertion_origin),
        Known(unit, assertion_origin),
        base.request.assertion.reference_period,
        cv,
        assertion_origin,
    )
    requested = RequestedTuple(
        "ASSERTION", a, (subject_ref,), cv, rep, "/statements/0", assertion_origin
    )
    event = PublicationEventFacts(
        pub, "issuer_publication", "SRC-ISSUER-A", "SYN-A", cv, origin("publication_events", pub)
    )
    proof_origin = origin("time_proofs", tp)
    instant = replace(
        base.request.attempts[0].supplied.proof_candidate.timestamp,
        source_text=published,
        offset=published[-6:],
        origin=proof_origin,
    )
    descriptor = dict(base.request.attempts[0].supplied.proof_candidate.raw_descriptor)
    descriptor.update(proof_id=tp, target_id=a, content_version_id=cv, timestamp=published)
    proof = TimeProof(
        tp,
        "ASSERTION",
        a,
        cv,
        "/statements/0",
        instant,
        tuple(sorted(descriptor.items())),
        proof_origin,
    )
    if unknown:
        descriptor.update(
            proof_kind="unparsed_source_time",
            timestamp=None,
            timezone=None,
            offset=None,
            precision="MINUTE",
            unparsed_source_text="contemporaneous notice; time unresolved",
        )
        unknown_fact = Unknown(UnknownCause.AMBIGUOUS_SOURCE, None, proof_origin)
        proof = UnresolvedSourceTime(
            proof_ref=tp,
            target_kind="ASSERTION",
            target_ref=a,
            content_version_ref=cv,
            fragment_selector="/statements/0",
            raw_descriptor=tuple(sorted(descriptor.items())),
            origin=proof_origin,
            source_text=descriptor["unparsed_source_text"],
            timezone=unknown_fact,
            offset=unknown_fact,
            precision=Known("MINUTE", proof_origin),
        )
    binding = SupportBinding(
        sup,
        evid,
        replace(requested, origin=origin("evidence", evid, "/bindings/0")),
        "assertion_fragment",
        event,
        proof,
        origin("supports", sup),
    )
    capture_origin = origin("observations", obs)
    capture_instant = replace(
        instant, source_text="2025-07-16T12:00:00+08:00", origin=capture_origin
    )
    capture = CaptureFacts(
        obs,
        rep,
        digest,
        Known(capture_instant, capture_origin),
        Known("SECOND", capture_origin),
        "LAB_CAPTURE",
        capture_origin,
    )
    members = tuple(
        sorted(
            (
                RoleRef(Visibility.ACTIVE, role, ref, prefix + role)
                for role, ref in [
                    ("subjects", subject_ref),
                    ("assertions", a),
                    ("content_versions", cv),
                    ("raw_assets", rep),
                    ("supports", sup),
                    ("evidence", evid),
                    ("publication_events", pub),
                    ("time_proofs", tp),
                    ("observations", obs),
                ]
            ),
            key=lambda r: r.key,
        )
    )
    scope = S1Scope(members, (ContentPin(cv, rep, len(raw), digest),))
    scope = replace(
        scope,
        source_records=SourceRecords(
            members,
            scope.raw_pins,
            () if unbound else (binding,),
            (capture,),
            (event,),
            (),
        ),
    )
    request = IssuerBindingRequest(
        requested,
        content,
        assertion,
        () if unbound else (RequestBindingAttempt(requested, binding),),
        (capture,),
        (event,),
        scope,
    )
    lead = NO_LEAD
    if historical:
        lead = HistoricalLead(
            "LEAD-" + tag,
            a,
            "A03-SCOPE",
            "CONTEMPORANEOUS_ISSUER_NOTICE",
            next(m for m in members if m.role == "raw_assets"),
            content_origin,
        )
    return CandidateSource(subject, request, lead)


def revision(
    code,
    old,
    new,
    *,
    tag="CORRECTION",
    kind="CORRECTS",
    subject_ref="SUB-A-JUN",
    published="2025-07-10T14:00:00+08:00",
    **overrides,
):
    provisional = DirectRelation(
        "REL-" + tag,
        kind,
        subject_ref,
        old.request.assertion.assertion_ref,
        old.request.content.content_version_ref,
        new.request.assertion.assertion_ref,
        new.request.content.content_version_ref,
        "A-" + tag,
        old.subject.metric.origin,
    )
    provisional = replace(provisional, **overrides)
    notice = source(
        code,
        tag,
        1,
        published,
        metric=relation_proposition(provisional),
        unit="relation_declaration",
    )
    relation = replace(provisional, origin=notice.subject.metric.origin)
    return RelationSource(relation, notice)


def provider(code, tag="PROVIDER", value=999):
    base, _ = seed(code)
    a, u = Visibility.ACTIVE, Visibility.AUXILIARY
    bundle = materialize_input(
        "A02-C04",
        InvocationSelector("CHECK_BINDING", ("OBS-P-X-A02-C04",), NA, (a, u)),
        base.context.profile,
    )
    r = bundle.request
    cv, rep, obs, edge_id = "CV-" + tag, "REP-" + tag, "OBS-" + tag, "EDGE-" + tag
    body = json.loads(r.content.raw_bytes)
    body.update(
        content_version_id=cv, displayed_value=value, source_locator="synthetic://a03/" + tag
    )
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(raw).hexdigest()

    def origin(role, ref):
        return FieldOrigin(
            Visibility.AUXILIARY,
            "/a03_inputs/" + tag + "/" + role + "/" + ref,
            OriginKnownValue(ref),
            OriginKnownValue(r.content.source_schema),
            OriginKnownValue(digest),
        )

    o = origin("raw_assets", rep)
    content = replace(
        r.content,
        content_version_ref=cv,
        representation_ref=rep,
        raw_bytes=raw,
        raw_length=len(raw),
        raw_sha256=digest,
        origin=o,
        source_ref=replace(r.content.source_ref, origin=o),
        issuer_ref=replace(r.content.issuer_ref, origin=o),
        provider_ref=replace(r.content.provider_ref, origin=o),
        source_locator=Known(body["source_locator"], o),
    )
    co = origin("observations", obs)
    capture = replace(
        r.capture,
        observation_ref=obs,
        representation_ref=rep,
        captured_sha256=digest,
        origin=co,
        completion=Known(replace(r.capture.completion.value, origin=co), co),
        precision=Known("SECOND", co),
    )
    edge = CaptureEdge(
        edge_id, obs, rep, "provider_lab_capture_only", origin("graph_edges", edge_id)
    )
    members = tuple(
        sorted(
            (
                RoleRef(Visibility.AUXILIARY, role, ref, "/a03_inputs/" + tag + "/" + role)
                for role, ref in [
                    ("raw_assets", rep),
                    ("observations", obs),
                    ("graph_edges", edge_id),
                ]
            ),
            key=lambda m: m.key,
        )
    )
    pins = (ContentPin(cv, rep, len(raw), digest),)
    scope = S1Scope(members, pins, SourceRecords(members, pins, (), (capture,), (), (edge,)))
    request = replace(
        r,
        requested=replace(
            r.requested, target_ref=obs, content_version_ref=cv, representation_ref=rep, origin=o
        ),
        content=content,
        capture=capture,
        capture_edges=(edge,),
        subject_reference=Known("SUB-A-JUN", o),
        displayed_value=Known(value, o),
        source_unit=Known("NTD_thousands", o),
        scope=scope,
    )
    return CandidateSource(NA, request, NO_LEAD)


def invocation(
    code,
    candidates=(),
    relations=(),
    *,
    cutoff="2025-07-07T00:00:00+08:00",
    target="ATTRIBUTED_ASSERTION",
    mode="public",
    complete=True,
    snapshot="E-A03-1",
):
    base, subject = seed(code)
    ctx_ref = "A03-" + snapshot + "-" + cutoff + "-" + target + "-" + mode
    context = replace(
        base.context,
        context_ref=ctx_ref,
        evidence_set_ref=snapshot,
        target_ref=target,
        mode=mode,
        policy_refs=(*base.context.policy_refs, "POLICY-A03"),
        information_cutoff=replace(base.context.information_cutoff, source_text=cutoff),
        origin=CALLER,
    )
    policy = SelectionPolicy(
        "POLICY-A03",
        "a03-policy-v0.1",
        subject.subject_ref,
        mode,
        target,
        "SYN-A",
        ("SRC-ISSUER-A",),
        ("P-X",),
        "A03-SCOPE",
        REQUIRED_CHECKS,
    )
    refs = tuple(sorted(s.request.requested.target_ref for s in candidates))
    relrefs = tuple(sorted(r.relation.relation_ref for r in relations))
    checks = []
    for check_id in REQUIRED_CHECKS:
        status = "COMPLETED" if complete else "NOT_PERFORMED"
        raw = json.dumps(
            {
                "check": check_id,
                "scope": policy.discovery_scope_ref,
                "source_refs": policy.source_refs,
                "candidate_refs": refs,
                "relation_refs": relrefs,
                "context_ref": ctx_ref,
                "evidence_set_ref": snapshot,
                "policy_ref": policy.policy_ref,
                "policy_version": policy.version,
                "status": status,
            },
            sort_keys=True,
        ).encode()
        o = FieldOrigin(
            Visibility.ACTIVE,
            "/a03_coverage/" + check_id,
            OriginKnownValue("CHECK-" + check_id),
            OriginKnownValue("a03-synthetic-check-v0.1"),
            OriginKnownValue(sha256(raw).hexdigest()),
        )
        checks.append(
            CoverageCheck(
                check_id, policy.discovery_scope_ref, status, ("CHECK-" + check_id,), raw, o
            )
        )
    coverage = BoundedCoverage(
        "COVERAGE-A03",
        ctx_ref,
        snapshot,
        policy.policy_ref,
        policy.version,
        policy.discovery_scope_ref,
        policy.source_refs,
        refs,
        relrefs,
        tuple(checks),
    )
    return AsOfRequest(context, subject, policy, coverage, tuple(candidates), tuple(relations))
