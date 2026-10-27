"""B03 input-only synthetic declarations; no expected-oracle or B03 evaluator access."""

import calendar
import json
from dataclasses import fields, is_dataclass, replace
from datetime import date
from hashlib import sha256

from a03_inputs import b02_request, scoped_revision, source
from a04_inputs import request as monthly_request

from pit_research_lab.domain.contracts import (
    AssertionFacts,
    CaptureFacts,
    ContentFacts,
    ContentPin,
    FieldOrigin,
    Known,
    OriginKnownValue,
    SubjectFacts,
)
from pit_research_lab.domain.selection import discovery_proposition, relation_proposition

PUBLISHER = "SYN-B03-UNIVERSE-AUTHORITY"
SOURCE = "SYN-B03-UNIVERSE-SOURCE"
ROSTER = ("SYN-A", "SYN-B")
START, END = date(2025, 7, 1), date(2025, 7, 31)


def statement(
    code,
    tag,
    value,
    period,
    published,
    *,
    issuer="SYN-A",
    metric="net_operating_revenue",
    unit="NTD_thousands",
    scope="consolidated",
    basis="BASIS-CONSOLIDATED-V1",
    currency="NTD",
    source_ref=None,
    subject_ref=None,
    unknown=False,
    unbound=False,
):
    """Construct NEW bodies, dates, own proofs and retained references before challenge.

    Duration is the reference span of a declaration. Only the revenue metric is
    a financial flow; MEMBERSHIP_FLAG is a nonadditive all-dates policy predicate.
    """
    candidate = source(
        code,
        "B03-" + tag,
        value,
        published,
        metric=metric,
        unit=unit,
        unknown=unknown,
        unbound=unbound,
    )
    old = candidate.request
    source_ref = source_ref or "SRC-" + issuer
    mapping = {
        "SYN-A": issuer,
        "SRC-ISSUER-A": source_ref,
        candidate.subject.subject_ref: subject_ref or "SUB-B03-" + tag,
        old.content.source_locator.value: "synthetic://b03/" + tag,
    }
    body = json.loads(old.content.raw_bytes)
    body["issuer_id"] = issuer
    body["source_locator"] = mapping[old.content.source_locator.value]
    row = body["statements"][0]
    row.update(
        subject_id=mapping[candidate.subject.subject_ref],
        period=[d.isoformat() for d in period],
        metric=metric,
        unit=unit,
        reporting_scope=scope,
        basis_id=basis,
        currency=currency,
    )
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(raw).hexdigest()

    def transport(obj):
        if isinstance(obj, FieldOrigin):
            pointer = obj.envelope_pointer.replace("/a03_inputs/", "/b03_inputs/")
            for a, b in mapping.items():
                pointer = pointer.replace("/" + a, "/" + b)
            return replace(
                obj,
                envelope_pointer=pointer,
                object_id=transport(obj.object_id),
                input_digest=OriginKnownValue(digest),
            )
        if isinstance(obj, ContentFacts):
            updates = {f.name: transport(getattr(obj, f.name)) for f in fields(obj) if f.init}
            updates.update(raw_bytes=raw, raw_length=len(raw), raw_sha256=digest)
            return replace(obj, **updates)
        if isinstance(obj, ContentPin):
            return replace(obj, raw_length=len(raw), raw_sha256=digest)
        if is_dataclass(obj):
            updates = {f.name: transport(getattr(obj, f.name)) for f in fields(obj) if f.init}
            if isinstance(obj, SubjectFacts):
                for key, value in {
                    "economic_entity_ref": issuer,
                    "metric": metric,
                    "period_kind": "DURATION",
                    "period_start": period[0],
                    "period_end": period[1],
                    "reporting_scope": scope,
                    "basis_ref": basis,
                    "currency": currency,
                    "canonical_unit": unit,
                }.items():
                    updates[key] = Known(value, transport(obj.origin))
            if isinstance(obj, AssertionFacts):
                updates["reference_period"] = period
            if isinstance(obj, CaptureFacts):
                updates["captured_sha256"] = digest
                completion = updates["completion"]
                updates["completion"] = replace(
                    completion,
                    value=replace(completion.value, source_text="2026-10-26T12:00:00+08:00"),
                )
            return replace(obj, **updates)
        if isinstance(obj, tuple):
            return tuple(transport(x) for x in obj)
        if type(obj) is str:
            return mapping.get(obj, obj).replace("/a03_inputs/", "/b03_inputs/")
        return obj

    return transport(candidate)


def asof(
    code,
    anchor,
    candidates,
    relations=(),
    *,
    cutoff="2025-07-07T00:00:00+08:00",
    snapshot="E-B03-1",
    complete=True,
    check_status=None,
    mode="public",
    cutoff_timezone="Asia/Taipei",
):
    # Legacy helper accepts +08:00 only. Construct the B03 caller descriptor and
    # its coverage/discovery references together, before any owner evaluation.
    helper_cutoff = cutoff[:-6] + "+08:00"
    req = monthly_request(
        code,
        anchor,
        tuple(candidates),
        tuple(relations),
        cutoff=helper_cutoff,
        snapshot=snapshot,
        complete=complete,
        check_status=check_status,
        mode=mode,
        target="CONTENT_VALUE",
    )
    req = replace(
        req,
        context=replace(
            req.context,
            context_ref=req.context.context_ref.replace(helper_cutoff, cutoff)
            + ("-ZONE-" + cutoff_timezone if cutoff_timezone != "Asia/Taipei" else ""),
            information_cutoff=replace(
                req.context.information_cutoff,
                source_text=cutoff,
                timezone_name=cutoff_timezone,
                offset=cutoff[-6:],
            ),
            calendar_ref="B03-FIXED-SYNTHETIC-WEEKLY-v0.1",
            opaque_spec_ref="B03-FEATURE-ENV-v0.1",
        ),
    )
    issuer = anchor.subject.economic_entity_ref.value
    refs = (anchor.request.content.source_ref.value,)
    policy = replace(req.policy, issuer_ref=issuer, source_refs=refs)
    coverage = replace(req.coverage, source_refs=refs, context_ref=req.context.context_ref)
    checks = []
    for check in coverage.checks:
        body = json.loads(check.evidence_bytes)
        body["source_refs"] = refs
        body["context_ref"] = coverage.context_ref
        raw = json.dumps(body, sort_keys=True).encode()
        checks.append(
            replace(
                check,
                evidence_bytes=raw,
                origin=replace(
                    check.origin, input_digest=OriginKnownValue(sha256(raw).hexdigest())
                ),
            )
        )
    req = b02_request(replace(req, policy=policy, coverage=replace(coverage, checks=tuple(checks))))
    # NEW retained discovery scope, not an in-place relabel of old historical evidence.
    discovery = replace(
        req.discovery,
        window=(f"{anchor.subject.period_start.value.year}-01-01T00:00:00+08:00", cutoff),
    )
    raw = discovery_proposition(discovery)
    discovery = replace(
        discovery,
        raw_bytes=raw,
        origin=replace(discovery.origin, input_digest=OriginKnownValue(sha256(raw).hexdigest())),
    )
    return replace(req, discovery=discovery)


def membership_sources(
    code,
    flags=(1, 1),
    *,
    period=(START, END),
    published="2025-06-20T10:00:00+08:00",
    tag_suffix="",
    **kwargs,
):
    return tuple(
        statement(
            code,
            "MEMBER-" + entity + tag_suffix,
            flag,
            period,
            published,
            issuer=PUBLISHER,
            source_ref=SOURCE,
            subject_ref="SUB-B03-MEMBER-" + entity,
            metric="BENCHMARK_MEMBER_" + entity,
            unit="MEMBERSHIP_FLAG",
            scope="synthetic_benchmark_policy",
            basis="ALL_DATES_MEMBERSHIP_DECLARATION-v0.1",
            currency="NOT_APPLICABLE",
            **kwargs,
        )
        for entity, flag in zip(ROSTER, flags, strict=True)
    )


def quarter(
    code,
    tag,
    *,
    year=2025,
    quarter=2,
    issuer="SYN-A",
    values=(100, 200, 300),
    cutoff="2025-07-07T00:00:00+08:00",
    published="2025-07-03T10:00:00+08:00",
    missing=False,
    conflict=False,
    complete=True,
    check_status=None,
    revision_delta=None,
    correction_time="2025-07-10T14:00:00+08:00",
    snapshot="E-B03-1",
):
    from pit_research_lab.domain.derivation import DependencySlot, FeatureSpec

    slots = []
    for index, value in enumerate(values):
        month = 3 * (quarter - 1) + index + 1
        period = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
        subject_ref = f"SUB-B03-{issuer}-{year}-{month:02d}"
        anchor = statement(
            code,
            f"{tag}-M{index}",
            value,
            period,
            published,
            issuer=issuer,
            subject_ref=subject_ref,
        )
        candidates, relations = (anchor,), ()
        if index == 2:
            if missing:
                candidates = ()
            if conflict:
                other = statement(
                    code,
                    tag + "-PEER",
                    value + 99,
                    period,
                    published,
                    issuer=issuer,
                    subject_ref=subject_ref,
                )
                candidates += (other,)
            if revision_delta is not None:
                new = statement(
                    code,
                    tag + "-CORRECTED",
                    value + revision_delta,
                    period,
                    correction_time,
                    issuer=issuer,
                    subject_ref=subject_ref,
                )
                relation = scoped_revision(
                    code, anchor, new, tag="B03-" + tag + "-NOTICE", published=correction_time
                )
                notice = statement(
                    code,
                    tag + "-NOTICE",
                    1,
                    period,
                    correction_time,
                    issuer=issuer,
                    metric=relation_proposition(relation.relation),
                    unit="relation_declaration",
                )
                declaration = replace(
                    relation.relation,
                    origin=notice.subject.metric.origin,
                    scope=replace(relation.relation.scope, origin=notice.subject.metric.origin),
                )
                relation = replace(relation, relation=declaration, notice=notice)
                candidates += (new,)
                relations = (relation,)
        req = asof(
            code,
            anchor,
            candidates,
            relations,
            cutoff=cutoff,
            snapshot=snapshot,
            complete=complete,
            check_status=check_status,
        )
        slots.append(DependencySlot("M" + str(index + 1), anchor.subject, req))
    return FeatureSpec("B03-SUM-" + tag, year, quarter, issuer), tuple(slots)


def universe(
    code, *, cutoff="2025-07-07T00:00:00+08:00", flags=(1, 1), complete=True, snapshot="E-B03-1"
):
    from datetime import timedelta

    from pit_research_lab.domain.causal_derivation import (
        UniverseReference,
        UniverseRequest,
        UniverseSpec,
    )

    day = date.fromisoformat(cutoff[:10])
    start = day.replace(day=1)
    end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    candidates = membership_sources(
        code,
        flags,
        period=(start, end),
        published=(start - timedelta(days=10)).isoformat() + "T10:00:00+08:00",
    )
    requests = tuple(
        asof(code, c, (c,), cutoff=cutoff, complete=complete, snapshot=snapshot) for c in candidates
    )
    spec = UniverseSpec(start, end)
    return UniverseRequest(spec, requests, UniverseReference(spec, requests, code))


def view_at(code, summed, cutoff, *, snapshot="E-B03-1", cutoff_timezone="Asia/Taipei"):
    from pit_research_lab.domain.causal_derivation import SumRequest

    slots = []
    for slot in summed.slots:
        req = slot.request
        anchor = req.candidates[0]
        rebuilt = asof(
            code,
            anchor,
            req.candidates,
            req.relations,
            cutoff=cutoff,
            snapshot=snapshot,
            cutoff_timezone=cutoff_timezone,
        )
        slots.append(replace(slot, request=rebuilt))
    return SumRequest(summed.specification, tuple(slots))


def fitted(
    code,
    *,
    view="HISTORICAL_OBSERVATION_VIEW",
    fit_cutoff="2025-01-06T00:00:00+08:00",
    row_values=((2, 3, 5), (2, 5, 7)),
    corrected=True,
    snapshot="E-B03-1",
    historical_cutoffs=("2024-07-29T00:00:00+08:00", "2024-10-28T00:00:00+08:00"),
    correction_time="2024-12-10T10:00:00+08:00",
):
    from pit_research_lab.domain.causal_derivation import (
        FitReference,
        StandardizerRequest,
        SumRequest,
        TrainingRow,
    )

    core = code.upstream_ratio.upstream_a04
    first, slots = quarter(
        core,
        "FIT-R1",
        year=2024,
        quarter=2,
        values=row_values[0],
        cutoff=historical_cutoffs[0],
        published="2024-07-04T10:00:00+08:00",
        revision_delta=2 if corrected else None,
        correction_time=correction_time,
        snapshot=snapshot,
    )
    second, other = quarter(
        core,
        "FIT-R2",
        year=2024,
        quarter=3,
        values=row_values[1],
        cutoff=historical_cutoffs[1],
        published="2024-10-04T10:00:00+08:00",
        snapshot=snapshot,
    )
    historical = (SumRequest(first, slots), SumRequest(second, other))
    rows = tuple(
        TrainingRow("R" + str(i + 1), s, view_at(core, s, fit_cutoff, snapshot=snapshot))
        for i, s in enumerate(historical)
    )
    context = rows[0].fit_time.slots[0].request.context
    retained = FitReference(rows, view, context, code)
    return StandardizerRequest(rows, view, context, retained)


def causal_request(
    code,
    *,
    view=None,
    keys=None,
    missing=False,
    all_missing=False,
    conflict=False,
    complete=True,
    check_status=None,
    values=(100, 200, 300),
    other_values=(100, 200, 300),
    cutoff=None,
    published=None,
    revision_delta=None,
    snapshot="E-B03-1",
    allowed_missing=None,
    fit_request=None,
    universe_request=None,
):
    from pit_research_lab.domain.causal_derivation import (
        FEATURE_KEYS,
        NO_STATE,
        B03FeatureSpec,
        B03Request,
        CausalPlan,
        CausalReference,
        DecisionRow,
        SumRequest,
        required_plan,
    )
    from pit_research_lab.domain.ratio import RatioFeatureSpec

    is_fit = view is not None or fit_request is not None
    cutoff = cutoff or ("2025-01-13T00:00:00+08:00" if is_fit else "2025-07-07T00:00:00+08:00")
    published = published or (
        "2025-01-09T10:00:00+08:00" if is_fit else "2025-07-03T10:00:00+08:00"
    )
    year, q = (2024, 4) if is_fit else (2025, 2)
    if is_fit and values == (100, 200, 300):
        values = (5, 5, 6)
    core = code.upstream_ratio.upstream_a04
    rows = []
    for entity, amounts in (("SYN-A", values), ("SYN-B", other_values)):
        spec, slots = quarter(
            core,
            "DECISION-" + entity,
            year=year,
            quarter=q,
            issuer=entity,
            values=amounts,
            cutoff=cutoff,
            published=published,
            missing=all_missing or (missing and entity == "SYN-B"),
            conflict=conflict and entity == "SYN-B",
            complete=complete,
            check_status=check_status,
            revision_delta=revision_delta if entity == "SYN-A" else None,
            snapshot=snapshot,
        )
        ratio = RatioFeatureSpec("B03-SHARE-" + entity, spec.feature_ref, entity, year, q)
        rows.append(DecisionRow(entity, SumRequest(spec, slots), ratio))
    fit = fit_request or (fitted(code, view=view, snapshot=snapshot) if is_fit else NO_STATE)
    if keys is None:
        keys = (
            FEATURE_KEYS
            if is_fit
            else tuple(k for k in FEATURE_KEYS if k != "quarter_revenue_zscore")
        )
    specifications = tuple(B03FeatureSpec(k) for k in keys)
    u = universe_request or universe(core, cutoff=cutoff, snapshot=snapshot)
    context = rows[0].sum_request.slots[0].request.context
    bindings = tuple((r.entity_id, year, q) for r in rows)
    missing_keys = FEATURE_KEYS if allowed_missing is None else allowed_missing
    reference = CausalReference(
        context, specifications, tuple(rows), fit, u, code, bindings, missing_keys
    )
    request = B03Request(
        context,
        specifications,
        tuple(rows),
        fit,
        u,
        CausalPlan((), ()),
        reference,
        bindings,
        allowed_missing=missing_keys,
    )
    return replace(request, plan=required_plan(request))
