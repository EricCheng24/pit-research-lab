"""Coherent A05 numerical input variations, never injected owner outcomes."""

from dataclasses import replace

from a03_inputs import revision
from a04_inputs import family, month_source, request

from pit_research_lab.domain.derivation import DependencySlot
from pit_research_lab.domain.ratio import RatioFeatureSpec


def inputs(code, values=None, *, revision_delta=None, **kwargs):
    upstream = code.upstream_a04
    sum_spec, slots = family(upstream, **kwargs)
    if values is not None:
        changed = []
        for index, (slot, value) in enumerate(zip(slots, values, strict=True)):
            month = 3 * (sum_spec.quarter - 1) + index + 1
            source = month_source(
                upstream, "A05-M" + str(index + 1), month, value, year=sum_spec.year
            )
            req = request(upstream, source, (source,), **kwargs)
            changed.append(DependencySlot(slot.slot_ref, source.subject, req))
        slots = tuple(changed)
    if revision_delta is not None:
        old = slots[2].request.candidates[0]
        new = month_source(
            upstream,
            "A05-REVISION",
            3 * sum_spec.quarter,
            old.request.assertion.source_amount.value + revision_delta,
            year=sum_spec.year,
            published="2025-07-10T14:00:00+08:00",
        )
        relation = revision(
            upstream, old, new, tag="A05-NOTICE", subject_ref=old.subject.subject_ref
        )
        new_request = request(upstream, old, (old, new), (relation,), **kwargs)
        slots = (*slots[:2], replace(slots[2], request=new_request))
    spec = RatioFeatureSpec(
        "FEATURE-A05-M3-SHARE",
        sum_spec.feature_ref,
        sum_spec.issuer_ref,
        sum_spec.year,
        sum_spec.quarter,
    )
    return spec, sum_spec, slots
