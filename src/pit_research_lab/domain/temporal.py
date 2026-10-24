"""Bounded WU-01A §§4.7–4.8/7 temporal rules, conditional on supplied evidence.

Exact publication, supported upper bounds, source-date attestations and unknown
source time stay distinct. This owner authenticates no source or final PIT claim.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pit_research_lab.domain.contracts import (
    TEMPORAL_PROOF_TYPES,
    AwareInstant,
    BlockingFailure,
    CaptureFacts,
    CompleteScopedProvenance,
    ContentInventoryRequest,
    ContractError,
    EvidenceOutcome,
    IssuerBindingRequest,
    Known,
    NotEvaluated,
    OriginKnownValue,
    ProviderCaptureRequest,
    PublicationUpperBound,
    Record,
    RequestedTuple,
    SemanticContext,
    SupportBinding,
    TemporalProof,
    TimeProof,
    Unknown,
    UnresolvedSourceTime,
    Visibility,
    require,
)

EVALUATOR_REF = "s2-a02-temporal-profiles-v0.1-CANDIDATE"
type EvidenceRequest = IssuerBindingRequest | ContentInventoryRequest | ProviderCaptureRequest
type TemporalState = Literal["SUPPORTED", "NOT_ADMISSIBLE", "UNRESOLVED"]


@dataclass(frozen=True)
class DerivedDateBound(Record):
    proof_ref: str
    source_date: date
    timezone_name: str
    upper_bound: str
    closure: str = "OPEN"
    derivation: str = "NEXT_LOCAL_MIDNIGHT"


@dataclass(frozen=True)
class TemporalOutcome(Record):
    state: TemporalState
    reason: str
    context: SemanticContext
    requested_tuple: RequestedTuple
    path_kind: Literal["PUBLICATION", "OBSERVATION"]
    evaluated_evidence: TemporalProof | CaptureFacts | NotEvaluated
    accepted_binding_refs: tuple[str, ...]
    provenance: CompleteScopedProvenance | NotEvaluated
    diagnostics: tuple[str, ...]
    evaluator_ref: str = EVALUATOR_REF
    derived_bound: DerivedDateBound | NotEvaluated = NotEvaluated("S2", "NO_DATE_DERIVATION")

    @property
    def source_authentication(self) -> Literal["NOT_ESTABLISHED"]:
        return "NOT_ESTABLISHED"


def _zone(name: str) -> ZoneInfo:
    require(type(name) is str and bool(name), "INVALID_TIMEZONE")
    try:
        return ZoneInfo(name)
    except ValueError as error:
        raise ContractError("INVALID_TIMEZONE") from error


def _instant(value: AwareInstant) -> datetime:
    """Fail closed at S2 input, leaving the original S1 constructor unchanged."""
    require(
        re.fullmatch(r"[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]", value.offset) is not None,
        "INVALID_EXPLICIT_OFFSET",
    )
    require(
        value.precision == "SECOND"
        and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}",
            value.source_text,
        )
        is not None,
        "SECOND_PRECISION_REQUIRED",
    )
    parsed = datetime.fromisoformat(value.source_text)
    sign = 1 if value.offset[0] == "+" else -1
    declared = sign * timedelta(hours=int(value.offset[1:3]), minutes=int(value.offset[4:6]))
    require(
        parsed.utcoffset() == declared and value.source_text.endswith(value.offset),
        "OFFSET_MISMATCH",
    )
    # The offset resolves a repeated wall time, but cannot legalize a DST gap.
    try:
        localized = parsed.astimezone(_zone(value.timezone_name))
    except OverflowError as error:
        raise ContractError("INSTANT_OUT_OF_RANGE") from error
    require(
        localized.utcoffset() == declared
        and localized.replace(tzinfo=None) == parsed.replace(tzinfo=None),
        "ZONE_OFFSET_CONFLICT",
    )
    return parsed


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, time.min)
    candidates = {}
    for fold in (0, 1):
        local = naive.replace(tzinfo=zone, fold=fold)
        try:
            utc = local.astimezone(UTC)
            if utc.astimezone(zone).replace(tzinfo=None) == naive:
                candidates[utc] = local
        except OverflowError as error:
            raise ContractError("DATE_BOUND_OUT_OF_RANGE") from error
    require(len(candidates) == 1, "NONRESOLVABLE_LOCAL_MIDNIGHT")
    return next(iter(candidates.values()))


def _descriptor(proof: TemporalProof, values: dict[str, str | None]) -> None:
    raw = dict(proof.raw_descriptor)
    require(len(raw) == len(proof.raw_descriptor), "DUPLICATE_TIME_DESCRIPTOR_KEY")
    expected: dict[str, str | None] = {
        "proof_id": proof.proof_ref,
        "target_kind": proof.target_kind.lower(),
        "target_id": proof.target_ref,
        "content_version_id": proof.content_version_ref,
        "fragment_selector": proof.fragment_selector,
        "proof_kind": proof.proof_kind,
        "timestamp": None,
        "timezone": None,
        "offset": None,
        "precision": None,
        "upper_bound": None,
        "bound": None,
        "source_date": None,
        "unparsed_source_text": None,
    }
    expected.update(values)
    require(raw == expected, "CONTRADICTORY_TIME_DESCRIPTOR")


def _publication(
    proof: TemporalProof,
    cutoff: datetime,
) -> tuple[TemporalState, str, tuple[str, ...], DerivedDateBound | NotEvaluated]:
    derived: DerivedDateBound | NotEvaluated = NotEvaluated("S2", "NO_DATE_DERIVATION")
    if isinstance(proof, TimeProof):
        # Legacy exact DTOs with changed tags are not new A02 typed witnesses.
        if proof.proof_kind != "exact":
            return (
                "UNRESOLVED",
                "TEMPORAL_BOUND_INSUFFICIENT",
                ("UNSUPPORTED_PROOF_VARIANT:" + proof.proof_kind,),
                derived,
            )
        stamp = proof.timestamp
        _descriptor(
            proof,
            {
                "timestamp": stamp.source_text,
                "timezone": stamp.timezone_name,
                "offset": stamp.offset,
                "precision": stamp.precision,
            },
        )
        require(stamp.origin == proof.origin, "TIME_ORIGIN_MISMATCH")
        before = _instant(stamp) < cutoff
        return (
            "SUPPORTED" if before else "NOT_ADMISSIBLE",
            "NONE" if before else "PUBLICATION_NOT_PRE_CUTOFF",
            (),
            derived,
        )
    if isinstance(proof, UnresolvedSourceTime):
        _descriptor(
            proof,
            {
                "unparsed_source_text": proof.source_text,
                "timezone": proof.timezone.value if isinstance(proof.timezone, Known) else None,
                "offset": proof.offset.value if isinstance(proof.offset, Known) else None,
                "precision": proof.precision.value if isinstance(proof.precision, Known) else None,
            },
        )
        require(
            all(f.origin == proof.origin for f in (proof.timezone, proof.offset, proof.precision)),
            "TIME_ORIGIN_MISMATCH",
        )
        reason = (
            "TIMEZONE_UNRESOLVED"
            if isinstance(proof.timezone, Unknown)
            else "TEMPORAL_BOUND_INSUFFICIENT"
        )
        return (
            "UNRESOLVED",
            reason,
            ("SOURCE_TIME_UNPARSED",),
            NotEvaluated("S2", "SOURCE_TIME_UNPARSED"),
        )
    if isinstance(proof, PublicationUpperBound):
        stamp = proof.upper_bound
        _descriptor(
            proof,
            {
                "upper_bound": stamp.source_text,
                "bound": proof.closure,
                "timezone": stamp.timezone_name,
                "offset": stamp.offset,
                "precision": stamp.precision,
            },
        )
        require(stamp.origin == proof.origin, "TIME_ORIGIN_MISMATCH")
        endpoint = _instant(stamp)
        closure = proof.closure
    else:
        zone_name = proof.timezone.value if isinstance(proof.timezone, Known) else None
        day = proof.source_date.value if isinstance(proof.source_date, Known) else None
        declared_bound = proof.declared_upper_bound
        _descriptor(
            proof,
            {
                "source_date": day.isoformat() if day is not None else None,
                "timezone": zone_name,
                "precision": proof.source_precision,
                "bound": proof.closure,
                "upper_bound": declared_bound.source_text
                if isinstance(declared_bound, AwareInstant)
                else None,
                "offset": declared_bound.offset
                if isinstance(declared_bound, AwareInstant)
                else None,
            },
        )
        require(
            proof.source_date.origin == proof.timezone.origin == proof.origin,
            "TIME_ORIGIN_MISMATCH",
        )
        if zone_name is None:
            return "UNRESOLVED", "TIMEZONE_UNRESOLVED", ("SOURCE_ZONE_UNKNOWN",), derived
        if day is None or not isinstance(declared_bound, AwareInstant):
            return (
                "UNRESOLVED",
                "TEMPORAL_BOUND_INSUFFICIENT",
                ("DATE_OR_DECLARED_BOUND_ABSENT",),
                derived,
            )
        zone = _zone(zone_name)
        _midnight(day, zone)  # Reject unsupported skipped/repeated civil-date boundaries.
        try:
            next_day = day + timedelta(days=1)
        except OverflowError as error:
            raise ContractError("DATE_BOUND_OUT_OF_RANGE") from error
        endpoint = _midnight(next_day, zone)
        require(
            declared_bound.origin == proof.origin and declared_bound.timezone_name == zone_name,
            "TIME_ORIGIN_OR_ZONE_MISMATCH",
        )
        require(_instant(declared_bound) == endpoint, "DECLARED_DATE_BOUND_MISMATCH")
        derived = DerivedDateBound(proof.proof_ref, day, zone_name, endpoint.isoformat())
        closure = "OPEN"
    before = endpoint < cutoff or (endpoint == cutoff and closure == "OPEN")
    return (
        "SUPPORTED" if before else "UNRESOLVED",
        "NONE" if before else "TEMPORAL_BOUND_INSUFFICIENT",
        (),
        derived,
    )


def _target(value: RequestedTuple) -> tuple[object, ...]:
    return (
        value.target_kind,
        value.target_ref,
        value.subject_scope_refs,
        value.content_version_ref,
        value.representation_ref,
        value.fragment_selector,
    )


def qualify_temporal(
    context: SemanticContext,
    request: EvidenceRequest,
    s1: EvidenceOutcome | BlockingFailure,
    /,
) -> TemporalOutcome | BlockingFailure:
    """Evaluate one path from this invocation; do not search for substitute evidence.

    Provider observed findings remain diagnostic-only when S1 attribution is
    unresolved. All findings are conditional, including apparent S1 BOUNDs.
    Multi-observation/proof precedence and final S3 applicability are out of scope.
    """
    path: Literal["PUBLICATION", "OBSERVATION"] = (
        "PUBLICATION" if context.mode == "public" else "OBSERVATION"
    )
    provenance = s1.provenance if isinstance(s1, EvidenceOutcome) else NotEvaluated("S1", s1.code)

    def unresolved(reason: str, diagnostic: str) -> TemporalOutcome:
        return TemporalOutcome(
            "UNRESOLVED",
            reason,
            context,
            request.requested,
            path,
            NotEvaluated("S2", diagnostic),
            (),
            provenance,
            (diagnostic,),
        )

    if isinstance(s1, BlockingFailure):
        return unresolved("CONTENT_BINDING_INSUFFICIENT", "S1_BLOCKED:" + s1.code)
    if s1.context_ref != context.context_ref or s1.requested_tuple != request.requested:
        return unresolved("CONTENT_BINDING_INSUFFICIENT", "INVOCATION_MISMATCH")
    provider_observation = isinstance(request, ProviderCaptureRequest) and path == "OBSERVATION"
    if s1.state != "BOUND" and not provider_observation:
        return unresolved("CONTENT_BINDING_INSUFFICIENT", "S1_UNRESOLVED:" + s1.reason)
    try:
        cutoff = _instant(context.information_cutoff)
        if path == "OBSERVATION":
            captures = (
                (request.capture,)
                if isinstance(request, ProviderCaptureRequest)
                else tuple(
                    c
                    for c in request.captures
                    if c.representation_ref == request.requested.representation_ref
                )
            )
            if len(captures) != 1:
                return unresolved("TEMPORAL_BOUND_INSUFFICIENT", "ABSENT_OR_MULTIPLE_OBSERVATIONS")
            capture = captures[0]
            if (
                capture.origin.visibility not in {Visibility.ACTIVE, Visibility.AUXILIARY}
                or capture.representation_ref != request.content.representation_ref
                or capture.captured_sha256 != request.content.raw_sha256
                or capture not in s1.capture_facts
            ):
                return unresolved("CONTENT_BINDING_INSUFFICIENT", "OBSERVATION_BINDING_MISMATCH")
            if not isinstance(capture.completion, Known):
                return unresolved("TEMPORAL_BOUND_INSUFFICIENT", "COMPLETION_UNKNOWN")
            if not isinstance(capture.precision, Known) or capture.precision.value != "SECOND":
                return unresolved("TEMPORAL_BOUND_INSUFFICIENT", "UNSUPPORTED_CAPTURE_PRECISION")
            before = _instant(capture.completion.value) < cutoff
            return TemporalOutcome(
                "SUPPORTED" if before else "NOT_ADMISSIBLE",
                "NONE" if before else "OBSERVATION_AFTER_CUTOFF",
                context,
                request.requested,
                path,
                capture,
                (),
                provenance,
                ("CONDITIONAL_ON_UNVERIFIED_SOURCE_FACTS",),
            )
        if isinstance(request, ProviderCaptureRequest):
            return unresolved("CONTENT_BINDING_INSUFFICIENT", "CAPTURE_IS_NOT_PUBLICATION")
        # Use the supplied assessment's exact binding, never the projected path list.
        accepted = tuple(a for a in s1.assessments if a.disposition == "ACCEPTED")
        if len(accepted) != 1:
            return unresolved("TEMPORAL_BOUND_INSUFFICIENT", "ABSENT_OR_MULTIPLE_PUBLICATION_PATHS")
        assessment = accepted[0]
        binding: SupportBinding = assessment.supplied
        supplied = (
            tuple(a.supplied for a in request.attempts)
            if isinstance(request, IssuerBindingRequest)
            else request.supports
        )
        if (
            assessment.requested != request.requested
            or binding not in supplied
            or _target(binding.target) != _target(request.requested)
            or binding.origin.visibility not in {Visibility.ACTIVE, Visibility.AUXILIARY}
        ):
            return unresolved("CONTENT_BINDING_INSUFFICIENT", "PUBLICATION_BINDING_MISMATCH")
        proof = binding.proof_candidate
        if not isinstance(proof, TEMPORAL_PROOF_TYPES):
            return unresolved("TEMPORAL_BOUND_INSUFFICIENT", "PUBLICATION_PROOF_ABSENT")
        if (
            proof.target_kind,
            proof.target_ref,
            proof.content_version_ref,
            proof.fragment_selector,
        ) != (
            request.requested.target_kind,
            request.requested.target_ref,
            request.requested.content_version_ref,
            request.requested.fragment_selector,
        ) or proof.origin.visibility != binding.origin.visibility:
            return unresolved("CONTENT_BINDING_INSUFFICIENT", "TIME_PROOF_BINDING_MISMATCH")
        require(
            isinstance(proof.origin.object_id, OriginKnownValue)
            and proof.origin.object_id.value == proof.proof_ref
            and any(
                member.role == "time_proofs"
                and member.object_ref == proof.proof_ref
                and member.visibility == proof.origin.visibility
                and proof.origin.envelope_pointer == member.envelope_pointer + "/" + proof.proof_ref
                for member in request.scope.input_members
            ),
            "TIME_PROOF_ORIGIN_MEMBERSHIP_MISMATCH",
        )
        state, reason, diagnostics, derived = _publication(proof, cutoff)
        if isinstance(proof, TimeProof) and proof.proof_kind != "exact":
            return unresolved(reason, diagnostics[0])
        return TemporalOutcome(
            state,
            reason,
            context,
            request.requested,
            path,
            proof,
            (binding.support_ref,),
            provenance,
            ("CONDITIONAL_ON_UNVERIFIED_SOURCE_FACTS", *diagnostics),
            derived_bound=derived,
        )
    except ZoneInfoNotFoundError:
        return BlockingFailure(
            "OPERATIONAL_ERROR",
            "ZONE_DATA_UNAVAILABLE",
            request.scope.input_members,
            "ZONE_DATA_UNAVAILABLE",
            context.origin,
            "QUALIFY_TEMPORAL",
        )
    except ContractError as error:
        return BlockingFailure(
            "CONTRACT_VIOLATION",
            str(error),
            request.scope.input_members,
            str(error),
            context.origin,
            "QUALIFY_TEMPORAL",
        )
