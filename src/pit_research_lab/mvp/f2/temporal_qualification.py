"""Thin Native S1/S2 invocation and privileged, fail-closed completion. No caller I/O."""

from dataclasses import dataclass, field
from typing import Literal

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain.pit_slice import SliceResult, evaluate_slice
from pit_research_lab.mvp.f2.native_requests import (
    CONTRACT_VERSION,
    CallerObservationReceipt,
    NativeRequestAssembly,
    ObservationUnavailable,
    ObservedCodeInput,
    W02AdapterReason,
    W02Stage,
    _observation_reason,
)

type AssemblyIdentity = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class NativeAttempt:
    assembly_identity: AssemblyIdentity
    slice_result: SliceResult
    actual_unknown_facts: tuple[c.Unknown, ...]
    before_receipt_id: str
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)


@dataclass(frozen=True, slots=True)
class W02Diagnostic:
    contract_version: str
    assembly_identity: AssemblyIdentity
    native_result: SliceResult
    original_unknown_facts: tuple[c.Unknown, ...]
    caller_before_and_after_receipts: tuple[str, CallerObservationReceipt]
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )


@dataclass(frozen=True, slots=True)
class W02InvocationFailure:
    exact_native_exception_type: str
    code: str
    context: NativeRequestAssembly
    stage: W02Stage = field(default=W02Stage.S08_NATIVE_INVOCATION, init=False)
    reason: W02AdapterReason = field(
        default=W02AdapterReason.NATIVE_INVOCATION_REJECTED, init=False
    )
    native_invocation: Literal["ATTEMPTED"] = field(default="ATTEMPTED", init=False)


@dataclass(frozen=True, slots=True)
class W02ObservationFailure:
    before_receipt: str | CallerObservationReceipt
    after_receipt: CallerObservationReceipt | ObservationUnavailable
    preserved: NativeAttempt | W02InvocationFailure
    stage: W02Stage = field(default=W02Stage.S09_POST_OBSERVATION, init=False)
    reason: W02AdapterReason = field(default=W02AdapterReason.OBSERVATION_CHANGED, init=False)
    native_invocation: Literal["RUN", "ATTEMPTED"] = field(init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "native_invocation", self.preserved.native_invocation)


def _identity(assembly: NativeRequestAssembly) -> AssemblyIdentity:
    return (
        ("record_id", assembly.record_id),
        ("tick_id", assembly.tick_id),
        ("decision_cutoff", assembly.cutoff.source_text),
        ("native_context_ref", assembly.context.context_ref),
        ("pack_payload_sha256", assembly.pack_payload_sha256),
        ("exact_tick_bytes_sha256", assembly.exact_tick_bytes_sha256),
        ("evidence_fixture_sha256", assembly.evidence_fixture_sha256),
        ("original_wu01_context_ref", assembly.original_wu01_context_ref),
        ("original_wu01_manifest_ref", assembly.original_wu01_manifest_ref),
        ("original_wu01_config_ref", assembly.original_wu01_config_ref),
        ("original_wu01_calendar_ref", assembly.original_wu01_calendar_ref),
    )


def invoke_s1s2(assembly: NativeRequestAssembly, /) -> NativeAttempt | W02InvocationFailure:
    """Consume a validated immutable assembly; all observation stays with the trusted caller."""
    if _observation_reason(assembly.code_input) is not None:
        # Not a Native invocation; never manufacture ATTEMPTED or an S1/S2 result.
        raise ValueError("W02 invocation requires prepare_native_request's validated assembly")
    try:
        result = evaluate_slice(assembly.context, assembly.request, assembly.code_input.code)
    except c.ContractError as error:
        return W02InvocationFailure(type(error).__name__, str(error), assembly)
    return NativeAttempt(
        _identity(assembly),
        result,
        assembly.original_unknown_facts,
        assembly.code_input.scope_receipt.before_receipt_id,
    )


def finalize_diagnostic(
    attempt: NativeAttempt | W02InvocationFailure,
    after_observation: ObservedCodeInput | ObservationUnavailable,
    /,
) -> W02Diagnostic | W02InvocationFailure | W02ObservationFailure:
    """Complete only after caller-supplied actual native byte identity is confirmed again."""
    before = (
        attempt.before_receipt_id
        if isinstance(attempt, NativeAttempt)
        else attempt.context.code_input.scope_receipt
    )
    after = (
        after_observation.scope_receipt
        if isinstance(after_observation, ObservedCodeInput)
        else after_observation
    )
    if _observation_reason(after_observation) is not None:
        return W02ObservationFailure(before, after, attempt)
    assert isinstance(after_observation, ObservedCodeInput)
    original_code = (
        attempt.slice_result.code_observation
        if isinstance(attempt, NativeAttempt)
        else attempt.context.code_input.code
    )
    if (
        original_code.observed_working_files != after_observation.code.observed_working_files
        or original_code.byte_lengths != after_observation.code.byte_lengths
    ):
        return W02ObservationFailure(before, after, attempt)
    if isinstance(attempt, W02InvocationFailure):
        return attempt
    return W02Diagnostic(
        CONTRACT_VERSION,
        attempt.assembly_identity,
        attempt.slice_result,
        attempt.actual_unknown_facts,
        (attempt.before_receipt_id, after_observation.scope_receipt),
    )
