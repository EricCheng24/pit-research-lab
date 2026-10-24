"""A04-only coherent monthly variations of the WU-00/A03 input seam."""

import calendar
import json
from dataclasses import fields, is_dataclass, replace
from datetime import date
from hashlib import sha256

from a03_inputs import invocation, revision, source

from pit_research_lab.domain.contracts import (
    ContentFacts,
    ContentPin,
    FieldOrigin,
    Known,
    OriginKnownValue,
    SubjectFacts,
)
from pit_research_lab.domain.derivation import DependencySlot, FeatureSpec


def rewrite(candidate, *, month=None, year=2025, subject_changes=None, ids=None):
    """Rebuild bytes, digest, period, bindings and every origin together.

    Only test data is adapted. Dates are explicit civil month boundaries, never
    inferred publication times. `ids` allows coherent adversarial ID collisions.
    """
    r = candidate.request
    body = json.loads(r.content.raw_bytes)
    statement = body["statements"][0]
    old_subject = candidate.subject.subject_ref
    changes = dict(subject_changes or {})
    if month is not None:
        changes.update(
            period_start=date(year, month, 1),
            period_end=date(year, month, calendar.monthrange(year, month)[1]),
        )
        new_subject = f"SUB-A-{year}-{month:02d}"
    else:
        new_subject = old_subject
    replacements = {old_subject: new_subject, **(ids or {})}
    row_names = {
        "reporting_scope": "reporting_scope",
        "basis_ref": "basis_id",
        "metric": "metric",
        "currency": "currency",
        "canonical_unit": "unit",
    }
    statement["subject_id"] = new_subject
    if month is not None:
        statement["period"] = [
            changes["period_start"].isoformat(),
            changes["period_end"].isoformat(),
        ]
    for key, name in row_names.items():
        if key in changes:
            statement[name] = changes[key]
    for key in ("assertion_id",):
        statement[key] = replacements.get(statement[key], statement[key])
    body["content_version_id"] = replacements.get(
        body["content_version_id"], body["content_version_id"]
    )
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(raw).hexdigest()

    def transport(value):
        if isinstance(value, FieldOrigin):
            pointer = value.envelope_pointer
            for old, new in replacements.items():
                pointer = pointer.replace("/" + old, "/" + new)
            return replace(
                value,
                envelope_pointer=pointer,
                object_id=transport(value.object_id),
                input_digest=OriginKnownValue(digest),
            )
        if isinstance(value, ContentFacts):
            updates = {
                f.name: transport(getattr(value, f.name))
                for f in fields(value)
                if f.name != "schema_version"
            }
            updates.update(raw_bytes=raw, raw_length=len(raw), raw_sha256=digest)
            return replace(value, **updates)
        if isinstance(value, ContentPin):
            return replace(
                value,
                content_version_ref=transport(value.content_version_ref),
                representation_ref=transport(value.representation_ref),
                raw_length=len(raw),
                raw_sha256=digest,
            )
        if isinstance(value, SubjectFacts):
            updates = {
                f.name: transport(getattr(value, f.name))
                for f in fields(value)
                if f.name != "schema_version"
            }
            for name, new in changes.items():
                fact = updates[name]
                updates[name] = replace(fact, value=new) if isinstance(fact, Known) else new
            return replace(value, **updates)
        if is_dataclass(value):
            updates = {
                f.name: transport(getattr(value, f.name))
                for f in fields(value)
                if f.init and f.name != "schema_version"
            }
            if "reference_period" in updates and month is not None:
                updates["reference_period"] = (changes["period_start"], changes["period_end"])
            if "captured_sha256" in updates:
                updates["captured_sha256"] = digest
            if "source_unit" in updates and "canonical_unit" in changes:
                updates["source_unit"] = replace(
                    updates["source_unit"], value=changes["canonical_unit"]
                )
            return replace(value, **updates)
        if isinstance(value, tuple):
            return tuple(transport(v) for v in value)
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    return transport(candidate)


def month_source(code, tag, month, value, *, year=2025, **kwargs):
    return rewrite(source(code, tag, value, **kwargs), month=month, year=year)


def request(
    code,
    anchor,
    candidates,
    relations=(),
    *,
    cutoff="2025-07-07T00:00:00+08:00",
    complete=True,
    snapshot="E-A04-1",
    check_status=None,
    **kwargs,
):
    base = invocation(
        code, candidates, relations, cutoff=cutoff, complete=complete, snapshot=snapshot, **kwargs
    )
    subject = anchor.subject
    suffix = subject.subject_ref
    context = replace(
        base.context,
        context_ref=base.context.context_ref + "-" + suffix,
        policy_refs=tuple(p for p in base.context.policy_refs if p != "POLICY-A03")
        + ("POLICY-" + suffix,),
    )
    policy = replace(
        base.policy,
        policy_ref="POLICY-" + suffix,
        subject_ref=suffix,
        discovery_scope_ref="SCOPE-" + suffix,
    )
    coverage = replace(
        base.coverage,
        context_ref=context.context_ref,
        policy_ref=policy.policy_ref,
        coverage_ref="COVERAGE-" + suffix,
        scope_ref=policy.discovery_scope_ref,
    )
    checks = []
    for check in coverage.checks:
        status = check_status or check.status
        raw = json.dumps(
            {
                "check": check.check_ref,
                "scope": coverage.scope_ref,
                "source_refs": coverage.source_refs,
                "candidate_refs": coverage.evaluated_candidate_refs,
                "relation_refs": coverage.evaluated_relation_refs,
                "context_ref": coverage.context_ref,
                "evidence_set_ref": coverage.evidence_set_ref,
                "policy_ref": coverage.policy_ref,
                "policy_version": coverage.policy_version,
                "status": status,
            },
            sort_keys=True,
        ).encode()
        checks.append(
            replace(
                check,
                scope_ref=coverage.scope_ref,
                status=status,
                evidence_bytes=raw,
                origin=replace(
                    check.origin, input_digest=OriginKnownValue(sha256(raw).hexdigest())
                ),
            )
        )
    return replace(
        base,
        context=context,
        subject=subject,
        policy=policy,
        coverage=replace(coverage, checks=tuple(checks)),
    )


def family(
    code,
    *,
    cutoff="2025-07-07T00:00:00+08:00",
    revised=False,
    third="selected",
    year=2025,
    quarter=2,
    snapshot="E-A04-1",
    **kwargs,
):
    months = tuple(3 * (quarter - 1) + i for i in (1, 2, 3))
    values = (19_741_391, 19_509_486, 17_548_413)
    sources = tuple(
        month_source(code, f"{year}-{m:02d}", m, v, year=year)
        for m, v in zip(months, values, strict=True)
    )
    slots = []
    for i, anchor in enumerate(sources):
        candidates = (anchor,)
        relations = ()
        if i == 2:
            if revised:
                new = month_source(
                    code,
                    "CORRECTED",
                    months[2],
                    values[2] + 10,
                    year=year,
                    published="2025-07-10T14:00:00+08:00",
                )
                candidates += (new,)
                relations = (revision(code, anchor, new, subject_ref=anchor.subject.subject_ref),)
            if third == "conflict":
                candidates += (month_source(code, "COMPETITOR", months[2], 700, year=year),)
            if third == "absent":
                candidates = ()
        actual_request = request(
            code, anchor, candidates, relations, cutoff=cutoff, snapshot=snapshot, **kwargs
        )
        slots.append(DependencySlot(f"M{i + 1}", anchor.subject, actual_request))
    return FeatureSpec("FEATURE-A04-QUARTER", year, quarter, "SYN-A"), tuple(slots)
