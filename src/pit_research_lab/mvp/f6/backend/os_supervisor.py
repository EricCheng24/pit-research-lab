"""Inert helper specification and private supplied-fact S protocol.

Protocol output is modeled traffic, never a live permission. Physical adapters
have a separate unavailable session boundary; no configuration enables them.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Protocol

from pit_research_lab.mvp.f6 import contracts as c

from . import launch_policy as p
from .os_ownership import Binding, FDPlan, frame, require_physical_session
from .os_runtime_catalog import record

CANDIDATE_PYTHON = (
    "/home/rooki/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12"
)
CANDIDATE_PYTHON_SHA256 = "9544d2a29138833e6177d45dbc57468d37710b5080c901fbb579d53f251cdd6f"
CHECKOUT = "/home/rooki/projects/pit-research-lab-mvp-f6"
HELPER = CHECKOUT + "/platform_probes/mvp_f6/_launch_helper.py"
WATCHDOG = CHECKOUT + "/platform_probes/mvp_f6/_bounded_harness.py"
CASES = ("P01", "P02", "P03", "P04", "P05", "P06", "F00", "F01")


@dataclass(frozen=True, slots=True)
class CandidateBudget:
    """Unapproved finite planning values; representation is not enforcement."""

    node_seconds: int = 8
    shutdown_seconds: int = 6
    child_seconds: int = 2
    cpu_soft: int = 1
    cpu_hard: int = 2
    address_bytes: int = 128 * 1024 * 1024
    open_fds: int = 32
    file_bytes: int = 256 * 1024
    log_bytes: int = 16 * 1024
    node_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        p.require(
            all(
                type(value) is int
                for value in (
                    self.node_seconds,
                    self.shutdown_seconds,
                    self.child_seconds,
                    self.cpu_soft,
                    self.cpu_hard,
                    self.address_bytes,
                    self.open_fds,
                    self.file_bytes,
                    self.log_bytes,
                    self.node_bytes,
                )
            )
        )
        p.require(
            (
                self.node_seconds,
                self.shutdown_seconds,
                self.child_seconds,
                self.cpu_soft,
                self.cpu_hard,
                self.address_bytes,
                self.open_fds,
                self.file_bytes,
                self.log_bytes,
                self.node_bytes,
            )
            == (8, 6, 2, 1, 2, 128 * 1024 * 1024, 32, 256 * 1024, 16 * 1024, 8 * 1024 * 1024)
        )

    def live_refusal(self) -> str:
        return "UNAPPROVED_PHYSICAL_BUDGET"


@dataclass(frozen=True, slots=True)
class HelperSpec:
    root: str
    case: str
    exit_code: int

    def __post_init__(self) -> None:
        p.path_form(self.root)
        path = PurePosixPath(self.root)
        p.require(path.parent == PurePosixPath("/tmp"))
        parts = path.name.split(".")
        p.require(len(parts) == 3 and parts[0] == "pit-p103b-os-helper")
        p.require(parts[1].isdigit() and parts[2].isascii() and parts[2].isalnum())
        p.require(self.case in CASES and type(self.exit_code) is int and self.exit_code in (0, 7))
        p.require((self.exit_code == 7) == (self.case == "P03"))

    @property
    def cwd(self) -> str:
        return self.root + "/tmp"

    def environment(self) -> dict[str, str]:
        self.__post_init__()
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": self.root + "/home",
            "TMPDIR": self.cwd,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }

    def argv(self, plan: FDPlan) -> tuple[str, ...]:
        self.__post_init__()
        plan.__post_init__()
        fd = str(plan.descriptors[-1])
        if plan.role == "watchdog":
            return (
                CANDIDATE_PYTHON,
                "-I",
                "-S",
                "-B",
                WATCHDOG,
                "--case",
                self.case,
                "--context-fd",
                fd,
            )
        prefix = (CANDIDATE_PYTHON, "-I", "-S", "-B", HELPER, "--role", plan.role)
        if plan.role == "launcher":
            return prefix + ("--control-fd", fd, "--installation-fd", str(plan.descriptors[0]))
        if plan.role == "child":
            return prefix + ("--control-fd", fd, "--exit-code", str(self.exit_code))
        return prefix + ("--context-fd", fd)

    def command_digest(self, plan: FDPlan) -> str:
        return sha256(c.canonical_json(list(self.argv(plan)))).hexdigest()


@dataclass(frozen=True, slots=True)
class SuppliedCommit:
    """Recorded/model ACK only; no issuer or path to PhysicalSession."""

    operation: str
    revision: int
    event_sha256: str
    definite: bool

    def __post_init__(self) -> None:
        p.require(self.operation in ("TX0", "TX1", "TX2", "TX3", "TX4", "TX5", "TX6", "TX7"))
        p.require(type(self.revision) is int and 0 <= self.revision < 2**53)
        c.sha256_text(self.event_sha256)
        p.require(type(self.definite) is bool)


class OriginalSupervisorIO(Protocol):
    """Future original-session-bound ports, not an authorization interface.

    All commit methods return only after a definite commit. receive() enforces
    the original credential/nonce/sequence ChannelWindow, including its deadline.
    No implementation/issuer of these physical ports is activated in OAA-02.
    """

    def validate_original_ownership(self) -> None: ...
    def start_original_launcher(self) -> None:
        """Reserve W's one start before the fixed L spawn; no retry on failure."""
        ...

    def receive(self, kind: str) -> tuple[bytes, c.WireObject]: ...
    def send(self, kind: str, payload: c.WireObject) -> None: ...
    def commit_launcher(self, raw: bytes) -> SuppliedCommit: ...
    def validate_original_arm_commit(self, report: c.WireObject) -> SuppliedCommit: ...
    def validate_registered_child_report(self, report: c.WireObject) -> None: ...
    def validate_original_wait_report(self, report: c.WireObject) -> None: ...
    def verify_job_close_and_nofork(self, report: c.WireObject) -> None: ...
    def commit_quiescence_and_terminal(self) -> SuppliedCommit: ...
    def hold_without_retry(self) -> None: ...


class SupervisorProtocol:
    """Single-run pure S state; refusal is irreversible, with no restart API."""

    def __init__(self, binding: Binding, command_sha256: str, intent: SuppliedCommit) -> None:
        binding.__post_init__()
        intent.__post_init__()
        c.sha256_text(command_sha256)
        p.require(intent.operation == "TX1" and intent.definite and intent.revision > 0)
        self.binding, self.command_sha256 = binding, command_sha256
        self.revision = intent.revision
        self.run_sequence = 1
        self.phase = "INTENT_HELD"
        self.refused = False
        self._permission: str | None = None
        self._arm_payload: bytes | None = None
        self._sequence = 0

    def _begin(self, phase: str) -> None:
        p.require(not self.refused)
        self.refused = True
        p.require(self.phase == phase)

    def register_model(self, launcher_bytes: bytes, receipt: SuppliedCommit) -> None:
        self._begin("INTENT_HELD")
        obj = record("LAUNCHER", launcher_bytes)
        for key in ("installation_id", "app_run_id", "generation", "launcher_id"):
            p.require(obj[key] == getattr(self.binding, key))
        receipt.__post_init__()
        p.require(
            receipt.operation == "TX2"
            and receipt.definite
            and receipt.revision == self.revision + 1
        )
        self.phase, self.revision, self.refused = "OWNER_READY", receipt.revision, False
        self.run_sequence += 1

    def allow_arm_model(self, request: c.WireObject) -> bytes:
        self._begin("OWNER_READY")
        # frame() validates the exact type-specific grammar without touching a socket.
        encoded = frame(self.binding, 1, "ARM_REQUEST", request)
        p.require(request["command_sha256"] == self.command_sha256)
        p.require(request["expected_revision"] == self.revision)
        p.require(request["expected_run_sequence"] == self.run_sequence)
        self._permission = c.uuid4_text(request["permission_id"])
        self.phase, self.refused = "PREARM_ONLY", False
        return c.canonical_json({"request_sha256": sha256(encoded).hexdigest()})

    def observe_arm_model(self, report: c.WireObject, receipt: SuppliedCommit) -> None:
        self._begin("PREARM_ONLY")
        frame(self.binding, 1, "ARM_COMMITTED", report)
        receipt.__post_init__()
        p.require(receipt.operation == "TX3" and receipt.definite)
        p.require(receipt.revision == self.revision + 1)
        p.require(
            report
            == {
                "permission_id": self._permission,
                "revision": receipt.revision,
                "event_sha256": receipt.event_sha256,
            }
        )
        self._arm_payload = c.canonical_json(report)
        self.phase, self.revision, self.refused = "ARM_COMMITTED", receipt.revision, False

    def go_model(self) -> bytes:
        self._begin("ARM_COMMITTED")
        p.require(self._arm_payload is not None)
        assert self._arm_payload is not None
        payload = p.bounded_record(self._arm_payload, "permission_id revision event_sha256")
        self._sequence += 1
        raw = frame(self.binding, self._sequence, "GO", payload)
        self.phase = "GO_SPENT"
        return raw  # Refusal remains latched: even reading this again is forbidden.

    def disconnect(self) -> None:
        self.refused = True

    def run_owned(self, session: object, io: OriginalSupervisorIO | None = None) -> None:
        require_physical_session(session, "supervisor")
        p.require(io is not None)
        assert io is not None
        try:
            io.validate_original_ownership()
            io.start_original_launcher()
            _, registration = io.receive("REGISTER")
            launcher_raw = c.canonical_json(registration["launcher_record"])
            receipt = io.commit_launcher(launcher_raw)
            self.register_model(launcher_raw, receipt)
            io.send(
                "REGISTER_ACK",
                {
                    "revision": receipt.revision,
                    "event_sha256": receipt.event_sha256,
                    "launcher_record_sha256": p.digest("LAUNCHER", launcher_raw),
                },
            )
            request_raw, request = io.receive("ARM_REQUEST")
            self.allow_arm_model(request)  # Legal model transition, not a permission.
            io.validate_original_ownership()
            io.send("ARM_ALLOWED", {"request_sha256": sha256(request_raw).hexdigest()})
            _, report = io.receive("ARM_COMMITTED")
            # Readback may confirm history but this port must also retain the
            # original L's synchronous commit ACK on the same private channel.
            arm_receipt = io.validate_original_arm_commit(report)
            self.observe_arm_model(report, arm_receipt)
            io.validate_original_ownership()
            self.go_model()  # Latch this S before sending the one real GO.
            io.send("GO", report)
            _, acknowledgement = io.receive("GO_ACK")
            p.require(acknowledgement["permission_id"] == self._permission)
            _, child = io.receive("CHILD_REPORT")
            io.validate_registered_child_report(child)
            _, wait = io.receive("WAIT_REPORT")
            io.validate_original_wait_report(wait)
            _, closed = io.receive("CLOSED")
            io.verify_job_close_and_nofork(closed)
            terminal = io.commit_quiescence_and_terminal()
            p.require(terminal.operation == "TX7" and terminal.definite)
            io.send(
                "CLOSE",
                {
                    "terminal_revision": terminal.revision,
                    "terminal_event_sha256": terminal.event_sha256,
                },
            )
        except BaseException:
            self.refused = True
            io.hold_without_retry()
            raise
