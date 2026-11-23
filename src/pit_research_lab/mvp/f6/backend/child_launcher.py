"""Original-L single-attempt model and session-gated original Child adapter.

No replacement launcher, recovery token, automatic relaunch or public success.
ModelEffects cannot perform I/O and never returns a PhysicalSession.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from pit_research_lab.mvp.f6 import contracts as c

from . import launch_policy as p
from .os_ownership import FDPlan, LinuxAdapters, ProcessClaim, require_physical_session
from .os_supervisor import HelperSpec


class OriginalLauncherIO(Protocol):
    """Closed future ports held only by the genuine original L session.

    Commit methods must return only on definite ACK, never from a reopened row.
    The channel port owns credentials, binding, sequence and bounded deadlines.
    """

    def validate_original_ownership(self) -> None: ...
    def receive(self, kind: str) -> tuple[bytes, c.WireObject]: ...
    def send(self, kind: str, payload: c.WireObject) -> bytes: ...
    def verify_registration_ack(self, payload: c.WireObject) -> None: ...
    def original_arm_request(self) -> c.WireObject: ...
    def commit_original_arm(self, request: c.WireObject) -> c.WireObject: ...
    def current_go_sequence(self) -> int: ...
    def reserve_original_child_start(self) -> None: ...
    def handshake_and_register_original_child(
        self, child: subprocess.Popen[bytes]
    ) -> ProcessClaim: ...
    def original_child_report(self) -> c.WireObject: ...
    def commit_original_wait(self, observation: SuppliedWait) -> c.WireObject: ...
    def close_original_job_after_wait(self) -> c.WireObject: ...
    def remaining_child_seconds(self) -> float: ...
    def hold_without_retry(self) -> None: ...


STEPS = (
    "REGISTER_ACK",
    "PREARM_AUTHORITY",
    "ARM_COMMIT",
    "ARM_COMMITTED_SEND",
    "GO",
    "START_RESERVATION",
    "FINAL_AUTHORITY",
    "GO_ACK_SEND",
    "SPAWN",
    "CHILD_REGISTER",
    "WAIT",
    "QUIESCENCE",
    "TERMINAL",
)


@dataclass(frozen=True, slots=True)
class SuppliedWait:
    launcher_id: str
    child_registered: bool
    returncode: int | None
    original_parent_retained: bool
    reaped: bool

    def classification(self) -> tuple[str, int | None, int | None]:
        from pit_research_lab.mvp.f6 import contracts as c

        c.uuid4_text(self.launcher_id)
        p.require(
            all(
                type(v) is bool
                for v in (self.child_registered, self.original_parent_retained, self.reaped)
            )
        )
        if not (self.child_registered and self.original_parent_retained and self.reaped):
            return "UNKNOWN_HELD", None, None
        if self.returncode is None:
            return "UNKNOWN_HELD", None, None
        p.require(type(self.returncode) is int and -64 <= self.returncode <= 255)
        if self.returncode < 0:
            return "SIGNAL", None, -self.returncode
        return "EXIT", self.returncode, None


@dataclass(frozen=True, slots=True)
class ExternalWaitEvidence:
    """Bounded OS-F02 held evidence, expressly NOT a Child/Wait/Q catalog record."""

    observation_sha256: str
    recorded_bytes: int
    disposition: str = "REGISTRATION_GAP_UNKNOWN_HELD"


def hold_unregistered_observation(raw: bytes) -> ExternalWaitEvidence:
    p.require(type(raw) is bytes and 0 < len(raw) <= 16384)
    return ExternalWaitEvidence(sha256(raw).hexdigest(), len(raw))


class ModelEffects:
    """Closed finite script: append labels, never call a supplied callable/OS API."""

    def __init__(self, failure_at: str | None = None, ambiguous: bool = False) -> None:
        p.require(failure_at is None or failure_at in STEPS)
        p.require(type(ambiguous) is bool)
        self.failure_at, self.ambiguous = failure_at, ambiguous
        self.calls: list[str] = []

    def observe(self, step: str) -> str:
        p.require(step in STEPS and len(self.calls) < len(STEPS))
        self.calls.append(step)
        return (
            ("UNKNOWN" if self.ambiguous else "REFUSED") if step == self.failure_at else "DEFINITE"
        )


@dataclass(frozen=True, slots=True)
class ModelAttempt:
    phase: str
    spawn_calls: int
    arm_may_be_consumed: bool
    evidence_class: str = "MODEL_ONLY"


class OriginalLauncher:
    def __init__(self) -> None:
        self.attempt_entered = False
        self.spawn_attempted = False
        self._child: subprocess.Popen[bytes] | None = None
        self._claim: ProcessClaim | None = None
        self._wait_entered = False
        self._go_checked = False
        self._spawn_called = False

    def attempt_model(self, effects: ModelEffects) -> ModelAttempt:
        p.require(type(effects) is ModelEffects)
        p.require(not self.attempt_entered)
        self.attempt_entered = True  # Never reset, including prearm errors.
        spent = False
        for step in STEPS:
            if step == "GO_ACK_SEND":
                self.spawn_attempted = True  # Before both ACK and the possible OS call.
            outcome = effects.observe(step)
            if step == "ARM_COMMIT":
                spent = outcome in ("DEFINITE", "UNKNOWN")
            if outcome != "DEFINITE":
                return ModelAttempt(
                    "UNKNOWN_HELD" if spent else "REFUSED_HELD", effects.calls.count("SPAWN"), spent
                )
        return ModelAttempt("HELPER_EXIT_HELD", effects.calls.count("SPAWN"), spent)

    def spawn_owned(self, session: object, spec: HelperSpec, plan: FDPlan) -> None:
        require_physical_session(session, "launcher")
        # This source-only boundary cannot accept a ModelAttempt/GO frame/readback
        # as a session. A later issuer must also bind the definite commit + GO.
        p.require(self.attempt_entered and self.spawn_attempted and self._go_checked)
        p.require(not self._spawn_called and self._child is None)
        spec.__post_init__()
        plan.__post_init__()
        p.require(plan.role == "child")
        self._spawn_called = True  # Even an exception permanently spends this call.
        self._child = subprocess.Popen(
            spec.argv(plan),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=spec.cwd,
            env=spec.environment(),
            shell=False,
            close_fds=True,
            pass_fds=plan.descriptors,
            start_new_session=True,
        )

    def bind_registered_child(self, session: object, claim: ProcessClaim) -> None:
        require_physical_session(session, "launcher")
        claim.__post_init__()
        p.require(self._child is not None and self._claim is None)
        assert self._child is not None
        p.require(self._child.pid == claim.pid)
        LinuxAdapters.verify_child(session, claim)
        self._claim = claim

    def run_owned(
        self, session: object, spec: HelperSpec, plan: FDPlan, io: OriginalLauncherIO
    ) -> None:
        require_physical_session(session, "launcher")
        p.require(not self.attempt_entered)
        self.attempt_entered = True
        try:
            io.validate_original_ownership()
            _, registration = io.receive("REGISTER_ACK")
            io.verify_registration_ack(registration)
            request = io.original_arm_request()
            raw_request = io.send("ARM_REQUEST", request)
            _, allowed = io.receive("ARM_ALLOWED")
            p.require(allowed == {"request_sha256": sha256(raw_request).hexdigest()})
            io.validate_original_ownership()
            committed = io.commit_original_arm(request)
            p.require(committed["permission_id"] == request["permission_id"])
            io.send("ARM_COMMITTED", committed)
            _, go = io.receive("GO")
            p.require(go == committed)  # ARM_ALLOWED, row or partial ACK cannot satisfy GO.
            io.reserve_original_child_start()
            io.validate_original_ownership()
            self._go_checked = True
            self.spawn_attempted = True  # Before GO_ACK and any OS call.
            io.send(
                "GO_ACK",
                {
                    "permission_id": request["permission_id"],
                    "go_sequence": io.current_go_sequence(),
                },
            )
            self.spawn_owned(session, spec, plan)
            assert self._child is not None
            claim = io.handshake_and_register_original_child(self._child)
            self.bind_registered_child(session, claim)
            io.send("CHILD_REPORT", io.original_child_report())
            observation = self.original_wait(session, io.remaining_child_seconds())
            p.require(observation.classification()[0] in ("EXIT", "SIGNAL"))
            wait = io.commit_original_wait(observation)
            io.send("WAIT_REPORT", wait)
            io.send("CLOSED", io.close_original_job_after_wait())
            io.receive("CLOSE")
        except BaseException:
            # In particular, registration failure cannot flow to original_wait
            # persistence, Q or another child. Any raw wait remains external.
            self._go_checked = False
            io.hold_without_retry()
            raise

    def original_wait(self, session: object, remaining: float) -> SuppliedWait:
        require_physical_session(session, "launcher")
        p.require(type(remaining) in (float, int) and 0 < remaining <= 2)
        p.require(self._child is not None and self._claim is not None and not self._wait_entered)
        assert self._child is not None and self._claim is not None
        p.require(self._child.returncode is None)
        self._wait_entered = True
        try:
            code = self._child.wait(timeout=remaining)  # Sole original reaper; no implicit kill.
        except (subprocess.TimeoutExpired, ChildProcessError):
            return SuppliedWait(self._claim.launcher_id, True, None, False, False)
        return SuppliedWait(self._claim.launcher_id, True, code, True, True)
