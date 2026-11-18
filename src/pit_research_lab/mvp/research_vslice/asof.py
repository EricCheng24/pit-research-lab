"""Strict original-publication selection for the four bounded SYN-A cutoffs."""

from dataclasses import replace

from .contracts import (
    CUTOFFS,
    POLICY_STATES,
    SOURCE_KEYS,
    Feature,
    InputEvent,
    ResearchObservation,
    instant,
    require,
)
from .sources import EventLedger


def asof_view(ledger: EventLedger, cutoff: str) -> ResearchObservation:
    require(type(ledger) is EventLedger, "LEDGER_REQUIRED")
    require(cutoff in CUTOFFS, "CUTOFF_NOT_IN_PROFILE")
    eligible = [e for e in ledger.events if instant(e.provenance.publication) < instant(cutoff)]

    def order(event: InputEvent) -> tuple[int, str, str, str, str]:
        depth = 0
        current = event
        while current.predecessor is not None:
            current = next(
                e
                for e in ledger.events
                if e.key == event.key and e.provenance.version == current.predecessor
            )
            depth += 1
        p = event.provenance
        return depth, p.publication, p.source, p.version, p.record

    features = []
    for key in SOURCE_KEYS:
        candidates = [e for e in eligible if e.key == key]
        if not candidates:
            features.append(Feature(key, "ABSENT", None, "NONE", None))
        else:
            selected = max(candidates, key=order)
            features.append(
                Feature(
                    key, selected.state, selected.value, selected.unit, replace(selected.provenance)
                )
            )
    features.extend(Feature(key, state, None, "NONE", None) for key, state in POLICY_STATES)
    return ResearchObservation(CUTOFFS.index(cutoff), cutoff, tuple(features))
