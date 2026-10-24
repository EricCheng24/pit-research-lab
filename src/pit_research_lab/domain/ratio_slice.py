"""A05 request-based composition; explicit outer ten-plus-two code observation."""

from hashlib import sha256
from pathlib import Path

from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated
from pit_research_lab.domain.derivation import DependencySlot, FeatureSpec
from pit_research_lab.domain.derived_slice import evaluate_derived, observe_derived_code
from pit_research_lab.domain.ratio import (
    RATIO_CODE_PATHS,
    RatioCodeObservation,
    RatioFeatureSpec,
    RatioResult,
    _contract_failure,
    _evaluate_completed,
    _validate_request,
)


def observe_ratio_code(repository: Path) -> RatioCodeObservation:
    """Read fixed disk paths; a local observation, not runtime/source attestation."""
    upstream = observe_derived_code(repository)
    data = tuple((repository / path).read_bytes() for path in RATIO_CODE_PATHS)
    return RatioCodeObservation(
        upstream,
        tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(RATIO_CODE_PATHS, data, strict=True)
        ),
        tuple(len(body) for body in data),
    )


def evaluate_ratio(
    specification: RatioFeatureSpec,
    sum_specification: FeatureSpec,
    slots: tuple[DependencySlot, ...],
    code: RatioCodeObservation,
    /,
) -> RatioResult:
    """Run actual A04, retain it unchanged, then qualify the new share domain."""
    try:
        _validate_request(specification, sum_specification, slots, code)
    except ContractError as exc:
        return _contract_failure(
            specification, code, str(exc), NotEvaluated("S4-A04", "INVALID_A05_REQUEST")
        )
    upstream = evaluate_derived(sum_specification, slots, code.upstream_a04)
    return _evaluate_completed(specification, sum_specification, slots, code, upstream)
