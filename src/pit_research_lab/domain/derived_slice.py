"""A04 three-request composition; disk observation is explicit and separate."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from pit_research_lab.domain.asof_slice import evaluate_asof, observe_asof_code
from pit_research_lab.domain.contracts import CodePin
from pit_research_lab.domain.derivation import (
    S4_CODE_PATHS,
    CompletedDependency,
    DependencySlot,
    DerivedResult,
    FeatureSpec,
    _evaluate_completed,
)
from pit_research_lab.domain.pit_slice import CodeObservation


def observe_derived_code(repository: Path) -> CodeObservation:
    """Read fixed owner/composer disk bytes; HEAD is not complete executed code."""
    base = observe_asof_code(repository)
    data = tuple((repository / path).read_bytes() for path in S4_CODE_PATHS)
    return replace(
        base,
        observed_working_files=base.observed_working_files
        + tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(S4_CODE_PATHS, data, strict=True)
        ),
        byte_lengths=base.byte_lengths + tuple(len(body) for body in data),
    )


def evaluate_derived(
    specification: FeatureSpec, slots: tuple[DependencySlot, ...], code: CodeObservation, /
) -> DerivedResult:
    """Accept requests, never caller-asserted successful S3 results.

    Retain actual completed owners; the internal transport check replays these
    owners for consistency. No I/O, clock, source lookup or admission operation.
    """
    completed = tuple(
        CompletedDependency(slot, evaluate_asof(slot.request, code)) for slot in slots
    )
    return _evaluate_completed(specification, completed, code)
