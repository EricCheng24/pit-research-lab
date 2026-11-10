"""One real Native S3 call and observation-gated diagnostic completion."""

from dataclasses import dataclass, field
from typing import Literal

from pit_research_lab.domain.asof_slice import evaluate_asof
from pit_research_lab.domain.selection import AsOfSelectionResult
from pit_research_lab.mvp.f2.asof_requests import (
    G03ObservationUnavailable,
    G03ObservedCodeInput,
    G03RequestAssembly,
    assembly_valid,
    observation_reason,
)


@dataclass(frozen=True, slots=True)
class G03NativeAttempt:
    assembly: G03RequestAssembly
    native_result: AsOfSelectionResult
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)


@dataclass(frozen=True, slots=True)
class G03InvocationFailure:
    assembly: G03RequestAssembly
    exact_native_exception_type: str
    code: str
    native_invocation: Literal["ATTEMPTED"] = field(default="ATTEMPTED", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )


@dataclass(frozen=True, slots=True)
class G03Diagnostic:
    source_identity: tuple[tuple[str, str], ...]
    native_result: AsOfSelectionResult
    observations: tuple[G03ObservedCodeInput, G03ObservedCodeInput]
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )


@dataclass(frozen=True, slots=True)
class G03ObservationFailure:
    reason: str
    preserved: G03NativeAttempt | G03InvocationFailure
    after_observation: G03ObservedCodeInput | G03ObservationUnavailable
    native_invocation: Literal["RUN", "ATTEMPTED"] = field(init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "native_invocation", self.preserved.native_invocation)


def invoke_asof(assembly: G03RequestAssembly, /) -> G03NativeAttempt | G03InvocationFailure:
    """Never construct completed owners or select locally; exceptions stay distinct."""
    if not assembly_valid(assembly):
        raise ValueError("G03 invocation requires an unchanged prepared assembly; NOT_RUN")
    try:
        result = evaluate_asof(assembly.request, assembly.before_code)
    except Exception as error:
        return G03InvocationFailure(assembly, type(error).__name__, str(error))
    return G03NativeAttempt(assembly, result)


def finalize_asof_diagnostic(
    attempt: G03NativeAttempt | G03InvocationFailure,
    after_observation: G03ObservedCodeInput | G03ObservationUnavailable,
    /,
) -> G03Diagnostic | G03InvocationFailure | G03ObservationFailure:
    """Withhold completion on drift while retaining actual RUN/ATTEMPTED evidence."""
    before = attempt.assembly.before_observation
    reason = observation_reason(before) or observation_reason(after_observation)
    if reason is None and isinstance(after_observation, G03ObservedCodeInput):
        if before != after_observation:
            reason = "G03_CODE_OBSERVATION_CHANGED"
    if reason is not None:
        return G03ObservationFailure(reason, attempt, after_observation)
    if isinstance(attempt, G03InvocationFailure):
        return attempt
    assert isinstance(after_observation, G03ObservedCodeInput)
    return G03Diagnostic(
        attempt.assembly.source_identity, attempt.native_result, (before, after_observation)
    )
