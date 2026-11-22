"""Pure B-CORE modeled ledger reducer; no supervisor loop or executable permission.

All events and recovery outcomes are private supplied claims. Even a modeled arm,
wait, quiescence or disposition cannot activate a process or public success view.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256

from pit_research_lab.mvp.f6 import contracts as c

from .launch_policy import ModelError, Refusal, bounded_record, decimal_text, digest, require
from .process_identity import boot_text


class Phase(StrEnum):
    INTENT_HELD = "INTENT_HELD"
    OWNER_READY = "OWNER_READY"
    ARM_CONSUMED = "ARM_CONSUMED"
    CHILD_KNOWN = "CHILD_KNOWN"
    EXIT_HELD = "EXIT_HELD"
    RECONCILING = "RECONCILING"
    QUARANTINED = "QUARANTINED"
    TERMINAL_HELD = "TERMINAL_HELD"
    DISPOSED = "DISPOSED"


FACT_FIELDS = {
    "INTENT_COMMITTED": "admission_sha256 expectation_sha256 fingerprint allocation_id",
    "LAUNCHER_REGISTERED": "launcher_id launcher_record_sha256",
    "SPAWN_ARMED": "permission_id launcher_id command_sha256 deadline_monotonic_ns",
    "CHILD_REGISTERED": "child_id child_record_sha256",
    "SPAWN_ERROR": "permission_id failure_class source_sha256",
    "EXIT_OBSERVED": "wait_record_sha256 result_kind exit_code signal_number",
    "FIRST_FAILURE": "reason first_observed_at source_sha256",
    "SECONDARY_FAILURE": "reason source_sha256",
    "RECONCILING": "prior_revision evidence_sha256 reason",
    "QUARANTINED": "prior_revision evidence_sha256 reason",
    "QUIESCENCE_PROVEN": "proof_sha256 basis",
    "TERMINAL_HELD": "disposition evidence_sha256",
    "SLOT_DISPOSED": "quiescence_sha256 terminal_revision lease_disposition_sha256",
}
FAILURE_REASONS = frozenset(
    (
        "LAUNCH_INTERRUPTED",
        "CHILD_TIMEOUT",
        "CHILD_NONZERO_EXIT",
        "SUPERVISOR_LOST",
        "EXECUTION_OUTCOME_UNKNOWN",
        "RECOVERY_BLOCKED",
        "STORAGE_BLOCKED",
        "RESOURCE_LIMIT",
        "SERVICE_NOT_READY",
    )
)
ZERO_HASH = "0" * 64


def counter(value: object, *, zero: bool = False) -> int:
    require(type(value) is int and (0 if zero else 1) <= value < 2**63)
    assert isinstance(value, int)
    return value


@dataclass(frozen=True, slots=True)
class Failure:
    reason: str
    first_observed_at: str
    source_sha256: str

    def __post_init__(self) -> None:
        require(type(self.reason) is str and self.reason in FAILURE_REASONS)
        try:
            c.timestamp(self.first_observed_at)
            c.sha256_text(self.source_sha256)
        except c.ContractError:
            raise ModelError() from None


@dataclass(frozen=True, slots=True)
class ModeledEvent:
    revision: int
    app_run_id: str
    run_sequence: int
    expected_previous_revision: int
    kind: str
    state: Phase
    actor: str
    generation: str
    observed_at: str
    boot_id: str
    monotonic_ns: str
    facts: bytes
    previous_sha256: str

    def __post_init__(self) -> None:
        counter(self.revision)
        counter(self.run_sequence)
        counter(self.expected_previous_revision, zero=True)
        require(type(self.kind) is str and self.kind in FACT_FIELDS)
        require(type(self.state) is Phase)
        require(self.actor in ("ADMISSION", "SUPERVISOR", "LAUNCHER", "RECOVERY"))
        boot_text(self.boot_id)
        decimal_text(self.monotonic_ns)
        try:
            c.uuid4_text(self.app_run_id)
            c.uuid4_text(self.generation)
            c.timestamp(self.observed_at)
            c.sha256_text(self.previous_sha256)
            obj = bounded_record(self.facts, FACT_FIELDS[self.kind])
            identifiers = [c.uuid4_text(value) for key, value in obj.items() if key.endswith("_id")]
            require(len(set(identifiers)) == len(identifiers))
            require(not set(identifiers) & {self.app_run_id, self.generation})
            for key, value in obj.items():
                if key.endswith("sha256") or key == "fingerprint":
                    c.sha256_text(value)
                elif key.endswith("_id"):
                    c.uuid4_text(value)
                elif key == "reason":
                    require(type(value) is str and value in FAILURE_REASONS)
                elif key == "first_observed_at":
                    c.timestamp(value)
                elif key == "deadline_monotonic_ns":
                    decimal_text(value, positive=True)
                elif key in ("prior_revision", "terminal_revision"):
                    counter(value, zero=key == "prior_revision")
            if self.kind == "SPAWN_ERROR":
                require(
                    obj["failure_class"]
                    in ("PRESPAWN_VALIDATION", "EXEC_ERROR", "POPEN_AMBIGUOUS", "HANDSHAKE_TIMEOUT")
                )
            if self.kind == "EXIT_OBSERVED":
                code, signal = obj["exit_code"], obj["signal_number"]
                require(
                    (
                        obj["result_kind"] == "EXIT"
                        and type(code) is int
                        and 0 <= code <= 255
                        and signal is None
                    )
                    or (
                        obj["result_kind"] == "SIGNAL"
                        and code is None
                        and type(signal) is int
                        and 1 <= signal <= 64
                    )
                )
            if self.kind == "QUIESCENCE_PROVEN":
                require(
                    obj["basis"]
                    in (
                        "ORIGINAL_WAIT_NOFORK_HELPER",
                        "PREARM_ORIGINAL_OWNER_CLOSED",
                        "COLD_OWNER_ADJUDICATION",
                    )
                )
            if self.kind == "TERMINAL_HELD":
                require(
                    obj["disposition"]
                    in ("ABORTED_PREARM", "HELPER_EXIT_ZERO_HELD", "FAILED_KNOWN", "UNKNOWN_HELD")
                )
        except c.ContractError:
            raise ModelError() from None

    def preimage(self) -> bytes:
        return c.canonical_json(
            {
                "version": 1,
                "revision": self.revision,
                "app_run_id": self.app_run_id,
                "run_sequence": self.run_sequence,
                "expected_previous_revision": self.expected_previous_revision,
                "kind": self.kind,
                "state": self.state.value,
                "actor": self.actor,
                "generation": self.generation,
                "observed_at": self.observed_at,
                "boot_id": self.boot_id,
                "monotonic_ns": self.monotonic_ns,
                "facts_version": 1,
                "facts_sha256": sha256(self.facts).hexdigest(),
                "previous_sha256": self.previous_sha256,
            }
        )

    @property
    def event_sha256(self) -> str:
        self.__post_init__()
        return digest("EVENT", self.preimage())


@dataclass(frozen=True, slots=True)
class WaitOutcome:
    """Immutable supplied exit event retained by replay, never an OS wait attestation."""

    event: ModeledEvent

    def __post_init__(self) -> None:
        require(type(self.event) is ModeledEvent)
        self.event.__post_init__()
        require(self.event.kind == "EXIT_OBSERVED" and self.event.actor == "LAUNCHER")
        require(self.event.state is Phase.EXIT_HELD)
        require(self.event.revision == self.event.expected_previous_revision + 1)

    @property
    def result_kind(self) -> str:
        return c.text(bounded_record(self.event.facts, FACT_FIELDS["EXIT_OBSERVED"])["result_kind"])

    @property
    def exit_code(self) -> int | None:
        value = bounded_record(self.event.facts, FACT_FIELDS["EXIT_OBSERVED"])["exit_code"]
        assert value is None or isinstance(value, int)
        return value

    @property
    def signal_number(self) -> int | None:
        value = bounded_record(self.event.facts, FACT_FIELDS["EXIT_OBSERVED"])["signal_number"]
        assert value is None or isinstance(value, int)
        return value

    def is_nonzero_exit(self) -> bool:
        code = self.exit_code
        return self.result_kind == "EXIT" and type(code) is int and 1 <= code <= 255


@dataclass(frozen=True, slots=True)
class RunModel:
    installation_id: str
    app_run_id: str
    original_generation: str
    sequence: int = 0
    phase: Phase | None = None
    first_failure: Failure | None = None
    armed: bool = False
    child_known: bool = False
    wait_observed: bool = False
    quiescent: bool = False
    launcher_id: str | None = None
    permission_id: str | None = None
    child_id: str | None = None
    wait_outcome: WaitOutcome | None = None

    def __post_init__(self) -> None:
        try:
            for value in (self.installation_id, self.app_run_id, self.original_generation):
                c.uuid4_text(value)
            require(len({self.installation_id, self.app_run_id, self.original_generation}) == 3)
        except c.ContractError:
            raise ModelError() from None
        counter(self.sequence, zero=True)
        require(self.phase is None or type(self.phase) is Phase)
        for flag in (self.armed, self.child_known, self.wait_observed, self.quiescent):
            require(type(flag) is bool)
        require(not self.child_known or self.armed)
        require(not self.wait_observed or self.armed)
        require(self.wait_observed == (self.wait_outcome is not None))
        require(self.phase is not Phase.EXIT_HELD or self.wait_observed)
        if self.wait_outcome is not None:
            require(type(self.wait_outcome) is WaitOutcome)
            self.wait_outcome.__post_init__()
            observed = self.wait_outcome.event
            require(observed.app_run_id == self.app_run_id)
            require(observed.generation == self.original_generation)
            require(observed.run_sequence <= self.sequence)
            require(
                self.phase
                in (
                    Phase.EXIT_HELD,
                    Phase.RECONCILING,
                    Phase.QUARANTINED,
                    Phase.TERMINAL_HELD,
                    Phase.DISPOSED,
                )
            )
        identities = [self.installation_id, self.app_run_id, self.original_generation]
        for identifier in (self.launcher_id, self.permission_id, self.child_id):
            if identifier is not None:
                try:
                    identities.append(c.uuid4_text(identifier))
                except c.ContractError:
                    raise ModelError() from None
        require(len(set(identities)) == len(identities))
        require(not self.armed or (self.launcher_id is not None and self.permission_id is not None))
        require(not self.child_known or self.child_id is not None)
        require((self.sequence == 0) == (self.phase is None))
        if self.first_failure is not None:
            require(type(self.first_failure) is Failure)
            self.first_failure.__post_init__()
            if self.first_failure.reason == "CHILD_NONZERO_EXIT":
                require(
                    self.child_known
                    and self.wait_outcome is not None
                    and self.wait_outcome.is_nonzero_exit()
                )

    def live_refusal(self) -> Refusal:
        return Refusal.B_CORE_AUTHORITY_ABSENT


def reduce_model(
    model: RunModel,
    event: ModeledEvent,
    *,
    previous_revision: int,
    previous_sha256: str,
    registered_generations: tuple[str, ...],
) -> RunModel:
    """Replay private supplied facts. No returned value is executable authority."""
    model.__post_init__()
    event.__post_init__()
    require(event.app_run_id == model.app_run_id)
    require(
        event.revision == previous_revision + 1
        and event.expected_previous_revision == previous_revision
    )
    require(event.previous_sha256 == previous_sha256 and event.run_sequence == model.sequence + 1)
    require(type(registered_generations) is tuple and event.generation in registered_generations)
    require(event.generation == model.original_generation or event.actor == "RECOVERY")
    old, kind = model.phase, event.kind
    facts = bounded_record(event.facts, FACT_FIELDS[kind])
    first_failure = model.first_failure
    armed, child_known = model.armed, model.child_known
    wait_observed, quiescent = model.wait_observed, model.quiescent
    wait_outcome = model.wait_outcome
    launcher_id, permission_id, child_id = model.launcher_id, model.permission_id, model.child_id
    if kind == "INTENT_COMMITTED":
        require(old is None and event.actor == "ADMISSION" and event.state is Phase.INTENT_HELD)
        require(event.generation == model.original_generation)
    else:
        require(old is not None and old is not Phase.DISPOSED)
        if kind == "LAUNCHER_REGISTERED":
            require(
                old is Phase.INTENT_HELD
                and event.actor == "SUPERVISOR"
                and event.state is Phase.OWNER_READY
            )
            require(event.generation == model.original_generation and model.first_failure is None)
            require(model.launcher_id is None)
            launcher_id = c.uuid4_text(facts["launcher_id"])
        elif kind == "SPAWN_ARMED":
            require(
                old is Phase.OWNER_READY
                and event.actor == "LAUNCHER"
                and event.state is Phase.ARM_CONSUMED
            )
            require(
                event.generation == model.original_generation
                and not model.armed
                and model.first_failure is None
            )
            armed = True
            require(facts["launcher_id"] == model.launcher_id)
            permission_id = c.uuid4_text(facts["permission_id"])
        elif kind == "CHILD_REGISTERED":
            require(
                old is Phase.ARM_CONSUMED
                and event.actor == "LAUNCHER"
                and event.state is Phase.CHILD_KNOWN
            )
            child_known = True
            child_id = c.uuid4_text(facts["child_id"])
        elif kind == "EXIT_OBSERVED":
            require(
                old in (Phase.ARM_CONSUMED, Phase.CHILD_KNOWN)
                and event.actor == "LAUNCHER"
                and event.state is Phase.EXIT_HELD
            )
            require(not model.wait_observed)
            wait_outcome = WaitOutcome(event)
            wait_observed = True
        elif kind == "SPAWN_ERROR":
            require(
                old is Phase.ARM_CONSUMED
                and event.actor == "LAUNCHER"
                and event.state is Phase.QUARANTINED
            )
            require(facts["permission_id"] == model.permission_id)
        elif kind == "FIRST_FAILURE":
            require(event.actor in ("SUPERVISOR", "LAUNCHER", "RECOVERY") and event.state is old)
            require(model.first_failure is None)
            reason = c.text(facts["reason"])
            require(reason not in ("CHILD_TIMEOUT", "CHILD_NONZERO_EXIT") or model.child_known)
            if reason == "CHILD_NONZERO_EXIT":
                require(
                    model.wait_observed
                    and model.wait_outcome is not None
                    and model.wait_outcome.is_nonzero_exit()
                )
            first_failure = Failure(
                reason, c.text(facts["first_observed_at"]), c.text(facts["source_sha256"])
            )
        elif kind == "SECONDARY_FAILURE":
            require(
                model.first_failure is not None
                and event.state is old
                and event.actor in ("SUPERVISOR", "LAUNCHER", "RECOVERY")
            )
        elif kind in ("RECONCILING", "QUARANTINED"):
            require(event.actor in ("SUPERVISOR", "RECOVERY") and event.state.value == kind)
            require(old not in (Phase.TERMINAL_HELD, Phase.DISPOSED))
            require(old is not Phase.QUARANTINED or kind == "QUARANTINED")
            require(facts["prior_revision"] == previous_revision)
        elif kind == "QUIESCENCE_PROVEN":
            require(event.state is old and event.actor in ("SUPERVISOR", "RECOVERY"))
            require(
                (model.wait_observed and model.child_known)
                or (not model.armed and not model.child_known)
            )
            require((facts["basis"] == "ORIGINAL_WAIT_NOFORK_HELPER") == model.armed)
            quiescent = True
        elif kind == "TERMINAL_HELD":
            require(
                event.state is Phase.TERMINAL_HELD and event.actor in ("SUPERVISOR", "RECOVERY")
            )
            require(
                old in (Phase.INTENT_HELD, Phase.EXIT_HELD, Phase.RECONCILING, Phase.QUARANTINED)
            )
        elif kind == "SLOT_DISPOSED":
            require(
                old is Phase.TERMINAL_HELD and model.quiescent and event.state is Phase.DISPOSED
            )
            require(event.actor in ("SUPERVISOR", "RECOVERY"))
        else:
            raise ModelError()
    # Explicit replacement fields avoid a mutable generic snapshot or live token.
    return replace(
        model,
        sequence=event.run_sequence,
        phase=event.state,
        first_failure=first_failure,
        armed=armed,
        child_known=child_known,
        wait_observed=wait_observed,
        quiescent=quiescent,
        launcher_id=launcher_id,
        permission_id=permission_id,
        child_id=child_id,
        wait_outcome=wait_outcome,
    )


class Window(StrEnum):
    W00 = "W00"
    W01 = "W01"
    W02 = "W02"
    W03 = "W03"
    W04 = "W04"
    W05 = "W05"
    W06 = "W06"
    W07 = "W07"
    W08 = "W08"
    W09 = "W09"
    W10 = "W10"
    W11 = "W11"
    W12 = "W12"
    W13 = "W13"
    W14 = "W14"


@dataclass(frozen=True, slots=True)
class RecoveryFacts:
    window: Window
    owner_committed: bool = False
    intent_committed: bool = False
    launcher_registered: bool = False
    arm_consumed: bool = False
    child_known: bool = False
    wait_observed: bool = False
    original_owner_survives: bool = False
    lease_attributed: bool = False
    storage_readable: bool = True
    boot_matches: bool = True
    database_ack_ambiguous: bool = False
    supervisor_loss_observed: bool = False
    wait_owner_lost: bool = False
    first_failure: Failure | None = None

    def __post_init__(self) -> None:
        require(type(self.window) is Window)
        for value in (
            self.owner_committed,
            self.intent_committed,
            self.launcher_registered,
            self.arm_consumed,
            self.child_known,
            self.wait_observed,
            self.original_owner_survives,
            self.lease_attributed,
            self.storage_readable,
            self.boot_matches,
            self.database_ack_ambiguous,
            self.supervisor_loss_observed,
            self.wait_owner_lost,
        ):
            require(type(value) is bool)
        require(not self.intent_committed or self.owner_committed)
        require(not self.launcher_registered or self.intent_committed)
        require(not self.arm_consumed or self.launcher_registered)
        require(not self.child_known or self.arm_consumed)
        require(not self.wait_observed or self.arm_consumed)
        require(self.intent_committed or self.first_failure is None)
        if self.first_failure is not None:
            self.first_failure.__post_init__()


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    classification: str
    reason: str | None
    first_failure: Failure | None

    def __post_init__(self) -> None:
        require(
            self.classification
            in (
                "NO_INTENT",
                "OWNER_ONLY",
                "IDENTITY_ONLY",
                "HOLD_ORIGINAL",
                "EXIT_HELD",
                "QUARANTINED",
                "STORAGE_BLOCKED",
            )
        )
        require(self.reason is None or self.reason in FAILURE_REASONS)
        if self.first_failure is not None:
            self.first_failure.__post_init__()

    def live_refusal(self) -> Refusal:
        return Refusal.B_CORE_AUTHORITY_ABSENT


def reconcile_model(facts: RecoveryFacts) -> RecoveryDecision:
    """Deterministic W00..W14 model; reason classification never invents a first failure."""
    facts.__post_init__()
    label = "QUARANTINED"
    reason: str | None = "RECOVERY_BLOCKED"
    if not facts.storage_readable or facts.window is Window.W12:
        label, reason = "STORAGE_BLOCKED", "STORAGE_BLOCKED"
    elif not facts.intent_committed:
        label, reason = ("OWNER_ONLY" if facts.owner_committed else "NO_INTENT"), None
    elif facts.window is Window.W14:
        label, reason = "IDENTITY_ONLY", None
    elif not facts.boot_matches or not facts.lease_attributed or facts.window is Window.W13:
        pass
    elif facts.database_ack_ambiguous:
        reason = "EXECUTION_OUTCOME_UNKNOWN" if facts.arm_consumed else "STORAGE_BLOCKED"
    elif facts.window is Window.W01:
        label, reason = "IDENTITY_ONLY", None
    elif facts.window in (Window.W03, Window.W06) and facts.original_owner_survives:
        label, reason = "HOLD_ORIGINAL", None
    elif facts.window in (Window.W09, Window.W10) and facts.wait_observed:
        label, reason = "EXIT_HELD", None
    elif (
        facts.window is Window.W07 and facts.supervisor_loss_observed and not facts.wait_owner_lost
    ):
        reason = "SUPERVISOR_LOST"
    elif facts.arm_consumed:
        reason = "EXECUTION_OUTCOME_UNKNOWN"
    if facts.first_failure is not None:
        reason = facts.first_failure.reason
    return RecoveryDecision(label, reason, facts.first_failure)
