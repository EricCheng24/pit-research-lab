"""D05 data/check boundary. No IF04 resolver, IF05 predicate or live grant.

All current operations deny until genuine verification is separately implemented.
Draft policy validation cannot turn supplied strings/booleans into authorization.
Public denial is constant: neither existence nor private failure detail is exposed.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pit_research_lab.mvp.f2.resource_bodies import DraftBody, native_summary, parse_body
from pit_research_lab.mvp.f2.resource_contracts import (
    Check,
    ParentCore,
    ResourceKey,
    State,
    closed,
    fact,
    fixed_ratio,
    flags,
    parent,
    require,
    revenue,
    text,
    time_record,
)


@dataclass(frozen=True, slots=True)
class AccessRequest:
    principal: str
    operation: str
    target: ParentCore | ResourceKey
    cutoff: str
    cohort: tuple[tuple[str, str], ...]
    exposure: str  # SAFE_REFERENCE, SAFE_BODY, AUDIT_BODY, EVAL_BODY


@dataclass(frozen=True, slots=True)
class GrantDeclaration:
    """Untrusted supplied declaration; NEVER a verified current grant."""

    request: AccessRequest
    valid_from: datetime
    valid_until: datetime
    revoked: bool
    original_evidence: bytes


def authorization_check(request: AccessRequest, grant: GrantDeclaration | None,
                        now: datetime, operation_receipt: bytes | None = None) -> Check:
    """Compare all target/context/action axes and fail closed on missing verifier.

    Even a perfectly matching test declaration/receipt cannot pass the unissued
    IF04/IF05 boundary. No receipt, grant or current-rights claim is generated.
    """
    denied = Check(State.DENIED, ("ACCESS_DENIED",))
    if grant is None or now.tzinfo is None:
        return denied
    if type(grant.revoked) is not bool or grant.revoked or grant.request != request:
        return denied
    if grant.valid_from.tzinfo is None or grant.valid_until.tzinfo is None:
        return denied
    if not grant.valid_from <= now < grant.valid_until:
        return denied
    if not grant.original_evidence or not operation_receipt:
        return denied
    # Verifiers for actual principal rights, policy/version/revocation/receipt and
    # reviewed IF05 positive/negative predicates are intentionally NOT supplied.
    return denied


def safe_observation_structure(value: object) -> None:
    """Strict detached whitelist, shape only. Never traverses a ref or invokes code."""
    d = closed(value, "issuer_ref feature_ref cutoff value unit qualification_ref scope_flags")
    require(d["issuer_ref"] == "SYN-A", "ISSUER_COHORT")
    text(d["feature_ref"], 128)
    time_record(d["cutoff"])
    parent(d["qualification_ref"], "F2-QUALIFICATION")
    flags(d["scope_flags"])
    require(d["unit"] in ("NTD_thousands", "FRACTION"), "UNIT")
    def known(v: object) -> None:
        if d["unit"] == "NTD_thousands":
            revenue(v, d["unit"])
        else:
            fixed_ratio(v)

    fact(d["value"], known)


@dataclass(frozen=True, slots=True)
class ReleaseWithheld:
    """Local refusal, NOT a CAN-07 Withheld fact or a Native outcome.

    A CAN-07 Withheld value needs an actually supplied policy_ref; this interface
    must also refuse when no such resource exists, without inventing one.
    """

    release_state: Literal["WITHHELD"] = field(default="WITHHELD", init=False)
    owner: Literal["F2"] = field(default="F2", init=False)
    reason: Literal["RELEASE_NOT_AUTHORIZED"] = field(default="RELEASE_NOT_AUTHORIZED", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)


def detached_release(native_facts: object, policy: DraftBody | None = None) -> ReleaseWithheld:
    """No original fact mutation and no Native facts in the denial response."""
    native_summary(native_facts)
    if policy is not None:
        require(policy.kind == "OBSERVATION_RELEASE_POLICY", "RESOURCE_KIND")
        parse_body(policy.kind, policy.raw)
    return ReleaseWithheld()
