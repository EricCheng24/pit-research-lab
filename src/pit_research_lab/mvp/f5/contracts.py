"""Detached cooperative decision values and exact, separately named research bytes."""

import hmac
import re
import secrets
from dataclasses import dataclass, field, fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Any

from pit_research_lab.mvp.f2.research_panel import PanelError, instant
from pit_research_lab.mvp.f3_l1.contracts import fraction_wire
from pit_research_lab.mvp.research_vslice.contracts import research_bytes

from . import VERSION

ISSUERS = tuple(f"SYN-L1-{i}" for i in range(1, 6))
POLICIES = ("QUALIFIED_EW_CAP50_V1", "GROWTH_POSITIVE_EW_CAP50_V1", "F3_OOS_POSITIVE_EW_CAP50_V1")
STATES = ("KNOWN", "UNKNOWN", "WITHHELD", "ABSENT", "NOT_EVALUATED", "REJECTED")
CALENDAR_SHA = "e28bfeafcfcb94a3828a0ef72e3c6f780a8b57458fb368c6cc3fee7414937046"
CUTOFFS_SHA = "d282bcfcf3cb669fa3ed3ce7eb49f439984191e0edd3aaabdd434a311e423ec5"
FIT_TIMES = ("2025-02-14T17:00:00+08:00", "2025-08-01T17:00:00+08:00")
COMPLETE = "COMPLETE_COMPARABLE_SYNTHETIC"
DEGRADED = "DEGRADED_DIAGNOSTIC_ONLY"
INCOMPLETE = "INCOMPLETE_OR_BLOCKED"


class F5Error(ValueError):
    """Closed safe cause; no arbitrary caller/source text in diagnostics."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise F5Error(code)


def safe_reason(error: Exception) -> str:
    value = str(error)
    return (
        value
        if isinstance(error, (F5Error, PanelError))
        and re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", value)
        else "INTERNAL_ERROR"
    )


def hex64(value: str) -> None:
    require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "INVALID_DIGEST"
    )


def wire(value: Any) -> Any:
    if type(value) is Fraction:
        return fraction_wire(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: wire(getattr(value, f.name)) for f in fields(value)}
    if type(value) in (tuple, list):
        return [wire(x) for x in value]
    if type(value) is dict:
        return {k: wire(v) for k, v in value.items()}
    require(value is None or type(value) in (str, int, bool), "UNSAFE_WIRE_VALUE")
    return value


def digest(value: Any) -> str:
    return sha256(research_bytes(wire(value))).hexdigest()


def envelope(kind: str, payload: Any) -> bytes:
    require(kind in {"SPEC", "DECISIONS", "LEDGER", "METRICS", "EVIDENCE", "ATTEMPT"}, "SCHEMA")
    return research_bytes(
        {"schema": f"F5_WEEKLY_SYNTHETIC_{kind}_V1", "non_if03": True, "payload": wire(payload)}
    )


@dataclass(frozen=True, slots=True)
class Protocol:
    seed: int = 17
    fee: Fraction = Fraction(6, 10000)
    slippage: Fraction = Fraction(4, 10000)
    initial_cash: Fraction = Fraction(1000)
    terminal: str = "2026-01-16T18:00:00+08:00"
    version: str = VERSION

    def validate(self) -> None:
        require(
            type(self) is Protocol
            and self == Protocol()
            and type(self.seed) is int
            and all(type(v) is Fraction for v in (self.fee, self.slippage, self.initial_cash)),
            "UNSUPPORTED_PROTOCOL",
        )


@dataclass(frozen=True, slots=True)
class DecisionFact:
    month: str
    state: str
    amount: int | None
    unit: str
    basis: str
    source_id: str | None
    version_id: str | None
    publication: str | None
    available_at: str | None
    native_state: str
    reason: str
    qualification_digest: str | None

    def validate(self, cutoff: str) -> None:
        require(
            type(self) is DecisionFact
            and all(
                type(v) is str
                for v in (
                    self.month,
                    self.state,
                    self.unit,
                    self.basis,
                    self.native_state,
                    self.reason,
                )
            ),
            "UNSAFE_DECISION_FACT",
        )
        require(
            all(
                v is None or type(v) is str
                for v in (
                    self.source_id,
                    self.version_id,
                    self.publication,
                    self.available_at,
                    self.qualification_digest,
                )
            ),
            "UNSAFE_DECISION_FACT",
        )
        if self.available_at is not None:
            require(instant(self.available_at) < instant(cutoff), "FUTURE_FEATURE_REFUSED")
        if any(v is not None for v in (self.source_id, self.version_id, self.publication)):
            require(self.available_at is not None, "UNAVAILABLE_PROVENANCE")
        if self.publication is not None and self.available_at is not None:
            require(
                instant(self.publication) <= instant(self.available_at), "FUTURE_FEATURE_REFUSED"
            )
        require(self.state in STATES, "INFORMATION_STATE")
        require(
            self.unit == "NTD_thousands" and self.basis == "consolidated-v1", "FEATURE_UNIT_BASIS"
        )
        if self.state == "KNOWN":
            require(type(self.amount) is int and self.amount > 0, "REVENUE_VALUE")
            require(
                self.publication is not None
                and self.available_at is not None
                and self.source_id is not None,
                "QUALIFIED_VALUE_REQUIRED",
            )
            assert self.publication and self.available_at and self.source_id
            require(
                instant(self.publication) <= instant(self.available_at) < instant(cutoff),
                "FUTURE_FEATURE_REFUSED",
            )
            require(self.version_id == self.source_id + "-VERSION", "SOURCE_VERSION_MISMATCH")
            require(self.qualification_digest is not None, "QUALIFICATION_REQUIRED")
        else:
            require(self.amount is None, "STATE_VALUE_CONTAMINATION")
        if self.qualification_digest is not None:
            hex64(self.qualification_digest)


@dataclass(frozen=True, slots=True)
class DecisionForecast:
    sample_id: str
    issuer: str
    tick: int
    decision_cutoff: str
    dataset_digest: str
    calendar_digest: str
    observation_binding: str
    fold: str
    fit_cutoff: str
    f3_protocol_digest: str
    model_state_digest: str
    method: str
    horizon_sessions: int
    state: str
    value: Fraction | None
    reason: str

    def validate(self) -> None:
        require(type(self.tick) is int and 48 <= self.tick < 96, "FORECAST_TICK")
        index = int(self.tick >= 72)
        require(
            self.fold == ("F1", "F2")[index] and self.fit_cutoff == FIT_TIMES[index],
            "FORECAST_FOLD_FIT",
        )
        require(instant(self.fit_cutoff) < instant(self.decision_cutoff), "FORECAST_FUTURE_FIT")
        require(
            self.method == "OLS_INTERCEPT_ONE_REGRESSOR_V1"
            and type(self.horizon_sessions) is int
            and self.horizon_sessions == 20,
            "FORECAST_METHOD",
        )
        require(self.sample_id == f"{self.issuer}:t{self.tick:02}", "FORECAST_SAMPLE")
        for ref in (
            self.dataset_digest,
            self.calendar_digest,
            self.observation_binding,
            self.f3_protocol_digest,
            self.model_state_digest,
        ):
            hex64(ref)
        require(self.calendar_digest == CALENDAR_SHA, "CALENDAR_PIN")
        if self.state == "PREDICTED":
            require(type(self.value) is Fraction and self.reason == "NONE", "FORECAST_VALUE")
            assert isinstance(self.value, Fraction)
            fraction_wire(self.value)
        else:
            require(
                self.state == "UNAVAILABLE"
                and self.value is None
                and self.reason in tuple("INFORMATION_" + s for s in STATES if s != "KNOWN"),
                "FORECAST_UNAVAILABLE",
            )


@dataclass(frozen=True, slots=True)
class IssuerInput:
    issuer: str
    sample_id: str
    observation_binding: str
    current: DecisionFact
    previous: DecisionFact
    growth: Fraction | None
    growth_state: str
    growth_reason: str
    forecast: DecisionForecast
    research_eligible: bool
    eligibility_reason: str


@dataclass(frozen=True, slots=True)
class DecisionObservation:
    tick: int
    cutoff: str
    calendar_digest: str
    dataset_digest: str
    issuers: tuple[IssuerInput, ...]
    schema: str = "F5_DECISION_OBSERVATION_V1"

    @property
    def information_digest(self) -> str:
        return digest(self)

    @property
    def availability_mask(self) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            (i.issuer, i.current.state, i.previous.state, i.forecast.state) for i in self.issuers
        )

    def validate(self, *, production: bool = False) -> None:
        require(type(self) is DecisionObservation, "UNSAFE_OBSERVATION")
        require(
            type(self.tick) is int
            and 48 <= self.tick < 96
            and self.schema == "F5_DECISION_OBSERVATION_V1",
            "OBSERVATION_TICK",
        )
        instant(self.cutoff)
        require(type(self.issuers) is tuple and bool(self.issuers), "ISSUER_GRID")
        names = tuple(i.issuer for i in self.issuers)
        require(names == tuple(sorted(set(names))), "ISSUER_GRID")
        if production:
            require(names == ISSUERS, "ISSUER_GRID")
        hex64(self.dataset_digest)
        require(self.calendar_digest == CALENDAR_SHA, "CALENDAR_PIN")
        for i in self.issuers:
            require(type(i) is IssuerInput and type(i.research_eligible) is bool, "ISSUER_INPUT")
            require(
                type(i.issuer) is str
                and type(i.sample_id) is str
                and type(i.current) is DecisionFact
                and type(i.previous) is DecisionFact
                and type(i.forecast) is DecisionForecast,
                "UNSAFE_ISSUER_INPUT",
            )
            hex64(i.observation_binding)
            i.current.validate(self.cutoff)
            i.previous.validate(self.cutoff)
            i.forecast.validate()
            f = i.forecast
            require(
                (
                    f.sample_id,
                    f.issuer,
                    f.tick,
                    f.decision_cutoff,
                    f.dataset_digest,
                    f.observation_binding,
                )
                == (
                    i.sample_id,
                    i.issuer,
                    self.tick,
                    self.cutoff,
                    self.dataset_digest,
                    i.observation_binding,
                ),
                "FORECAST_BINDING",
            )
            year, month = map(int, i.current.month.split("-"))
            require(
                i.previous.month == f"{year - (month == 1)}-{(month - 2) % 12 + 1:02}",
                "IMMEDIATE_PREDECESSOR",
            )
            known = i.current.state == i.previous.state == "KNOWN"
            require(i.research_eligible == known, "ELIGIBILITY_STATE")
            if known:
                assert i.current.amount is not None and i.previous.amount is not None
                require(
                    i.growth == Fraction(i.current.amount, i.previous.amount) - 1
                    and type(i.growth) is Fraction
                    and i.growth_state == "KNOWN"
                    and i.growth_reason == i.eligibility_reason == "NONE",
                    "GROWTH_VALUE",
                )
                require(f.state == "PREDICTED", "FORECAST_SOURCE_STATE")
            else:
                reason = "INFORMATION_" + next(
                    x.state for x in (i.current, i.previous) if x.state != "KNOWN"
                )
                require(
                    i.growth is None
                    and i.growth_state == "UNAVAILABLE"
                    and i.growth_reason == i.eligibility_reason == f.reason == reason
                    and f.state == "UNAVAILABLE",
                    "UNAVAILABLE_STATE",
                )


@dataclass(frozen=True, slots=True)
class TargetAction:
    policy_id: str
    tick: int
    cutoff: str
    information_digest: str
    disposition: str
    weights: tuple[tuple[str, Fraction], ...]
    cash_weight: Fraction
    issuer_reasons: tuple[tuple[str, str], ...]
    reason: str
    policy_version: str = VERSION
    schema: str = "F5_TARGET_ACTION_V1"

    @property
    def action_digest(self) -> str:
        return digest(self)

    def validate(self, obs: DecisionObservation, policy: str) -> None:
        require(
            type(self) is TargetAction
            and self.policy_id == policy
            and policy in POLICIES
            and self.policy_version == VERSION
            and self.schema == "F5_TARGET_ACTION_V1",
            "INVALID_ACTION",
        )
        require(
            (self.tick, self.cutoff, self.information_digest)
            == (obs.tick, obs.cutoff, obs.information_digest),
            "ACTION_BINDING",
        )
        names = tuple(i.issuer for i in obs.issuers)
        require(
            type(self.weights) is tuple
            and tuple(i for i, _ in self.weights) == names
            and tuple(i for i, _ in self.issuer_reasons) == names,
            "ACTION_ISSUERS",
        )
        require(
            all(type(w) is Fraction and 0 <= w <= Fraction(1, 2) for _, w in self.weights),
            "INVALID_WEIGHTS",
        )
        require(
            type(self.cash_weight) is Fraction
            and self.cash_weight >= 0
            and sum((w for _, w in self.weights), self.cash_weight) == 1,
            "INVALID_WEIGHTS",
        )
        require(
            all(
                i.research_eligible or w == 0
                for i, (_, w) in zip(obs.issuers, self.weights, strict=True)
            ),
            "UNQUALIFIED_ALLOCATION",
        )
        require(
            self.disposition in {"ALLOCATE", "CASH", "ABSTAIN"}
            and (self.disposition == "ALLOCATE") == any(w > 0 for _, w in self.weights),
            "ACTION_DISPOSITION",
        )


@dataclass(frozen=True, slots=True)
class EngineFailureDisposition:
    parent_failed_decision_digest: str
    origin: str = "ENGINE"
    disposition: str = "HOLD_EXISTING"


@dataclass(frozen=True, slots=True)
class DecisionSlot:
    tick: int
    cutoff: str
    policy_id: str
    information_digest: str | None
    outcome: str
    attempted: bool
    policy_decision_digest: str | None
    policy_action: TargetAction | None
    failure_cause: str | None
    engine_disposition: EngineFailureDisposition | None
    schema: str = "F5_DECISION_SLOT_V1"

    @property
    def slot_digest(self) -> str:
        return digest(self)

    def validate(self) -> None:
        require(self.policy_id in POLICIES and 48 <= self.tick < 96, "SLOT_KEY")
        instant(self.cutoff)
        if self.outcome == "VALID":
            require(
                self.attempted is True
                and self.policy_action is not None
                and self.failure_cause is None
                and self.engine_disposition is None,
                "SLOT_VARIANT",
            )
            assert self.policy_action is not None
            require(
                self.policy_decision_digest == self.policy_action.action_digest
                and (
                    self.policy_action.tick,
                    self.policy_action.cutoff,
                    self.policy_action.policy_id,
                    self.policy_action.information_digest,
                )
                == (self.tick, self.cutoff, self.policy_id, self.information_digest),
                "SLOT_ACTION_BINDING",
            )
        elif self.outcome == "FAILED_POLICY":
            require(
                self.attempted is True
                and self.policy_action is None
                and self.failure_cause is not None
                and self.engine_disposition is not None,
                "SLOT_VARIANT",
            )
            failure = digest(
                {
                    "tick": self.tick,
                    "cutoff": self.cutoff,
                    "policy_id": self.policy_id,
                    "information_digest": self.information_digest,
                    "failure_cause": self.failure_cause,
                }
            )
            require(
                self.policy_decision_digest == failure
                and self.engine_disposition == EngineFailureDisposition(failure),
                "FALLBACK_BINDING",
            )
        else:
            require(
                self.outcome == "BLOCKED_NOT_ATTEMPTED"
                and self.attempted is False
                and self.policy_action is None
                and self.policy_decision_digest is None
                and self.engine_disposition is None
                and self.failure_cause is not None,
                "SLOT_VARIANT",
            )
        if self.failure_cause is not None:
            require(
                re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", self.failure_cause) is not None,
                "UNSAFE_CAUSE",
            )


_BARRIER_KEY = secrets.token_bytes(32)


@dataclass(frozen=True, slots=True)
class SealedDecisions:
    slots: tuple[DecisionSlot, ...]
    common_failure: str | None
    slot_set_digest: str
    _seal: bytes = field(repr=False, compare=False)

    def payload(self) -> dict[str, Any]:
        return {
            "slots": [wire(s) | {"slot_digest": s.slot_digest} for s in self.slots],
            "common_failure": self.common_failure,
        }


def seal_slots(slots: tuple[DecisionSlot, ...], common_failure: str | None) -> SealedDecisions:
    require(
        type(slots) is tuple
        and tuple((s.tick, s.policy_id) for s in slots)
        == tuple((t, p) for t in range(48, 96) for p in POLICIES),
        "EXPECTED_SLOT_CENSUS",
    )
    for slot in slots:
        slot.validate()
    require(
        (common_failure is not None) == any(s.outcome == "BLOCKED_NOT_ATTEMPTED" for s in slots),
        "SLOT_COMMON_FAILURE",
    )
    body = SealedDecisions(slots, common_failure, "", b"").payload()
    return SealedDecisions(
        slots,
        common_failure,
        digest(body),
        hmac.digest(_BARRIER_KEY, research_bytes(body), "sha256"),
    )


def verify_barrier(value: SealedDecisions) -> None:
    require(
        type(value) is SealedDecisions and value.common_failure is None and len(value.slots) == 144,
        "BARRIER_NOT_OPEN",
    )
    require(
        value.slot_set_digest == digest(value.payload())
        and hmac.compare_digest(
            value._seal, hmac.digest(_BARRIER_KEY, research_bytes(value.payload()), "sha256")
        ),
        "BARRIER_SEAL",
    )
    require(
        tuple((s.tick, s.policy_id) for s in value.slots)
        == tuple((t, p) for t in range(48, 96) for p in POLICIES)
        and all(s.outcome in {"VALID", "FAILED_POLICY"} for s in value.slots),
        "BARRIER_CENSUS",
    )
    for slot in value.slots:
        slot.validate()
