"""Closed supplied-fact models and dormant Linux adapters for OAA-02.

There is deliberately no physical-session issuer in this source-only slice.
An Owner hash, frame, equality result or recorded SQL history is never authority.
The adapters below are authored, not platform-verified or activated.
"""

import fcntl
import os
import re
import signal
import socket
import stat
import struct
from dataclasses import dataclass, fields
from hashlib import sha256
from pathlib import Path

from pit_research_lab.mvp.f6 import contracts as c

from . import launch_policy as p
from .process_identity import boot_text, parse_supplied_stat, process_number

FRAME_LIMIT = 16384
FRAME_COUNT = 32
ENVELOPE = "version type installation_id app_run_id generation launcher_id sequence nonce payload"
LAUNCHER_FIELDS = (
    "version installation_id app_run_id launcher_id generation boot_id pid start_ticks pgid sid "
    "installation_lock_dev installation_lock_ino job_lock_dev job_lock_ino "
    "channel_nonce_sha256 executable_sha256"
)
PAYLOAD_FIELDS = {
    "CONTEXT": (
        "authority_sha256 allocation_id intent_revision intent_event_sha256 owner_record_sha256 "
        "root_path root_dev root_ino command_sha256 environment_sha256 resource_sha256 "
        "deadline_monotonic_ns"
    ),
    "REGISTER": "launcher_record",
    "REGISTER_ACK": "revision event_sha256 launcher_record_sha256",
    "ARM_REQUEST": (
        "permission_id expected_revision expected_run_sequence command_sha256 deadline_monotonic_ns"
    ),
    "ARM_ALLOWED": "request_sha256",
    "ARM_COMMITTED": "permission_id revision event_sha256",
    "GO": "permission_id revision event_sha256",
    "GO_ACK": "permission_id go_sequence",
    "CHILD_CONTEXT": "permission_id child_id command_sha256 deadline_monotonic_ns",
    "CHILD_HELLO": (
        "permission_id child_id boot_id pid parent_pid start_ticks pgid sid "
        "executable_sha256 command_sha256"
    ),
    "CHILD_REGISTERED_ACK": "child_id revision event_sha256",
    "CHILD_REPORT": "child_record_sha256 revision event_sha256",
    "WAIT_REPORT": "wait_record_sha256 revision event_sha256",
    "CLOSED": "job_dev job_ino lease_disposition_sha256 wait_record_sha256",
    "CLOSE": "terminal_revision terminal_event_sha256",
}


class PhysicalNotAuthorized(PermissionError):
    def __init__(self) -> None:
        super().__init__("PHYSICAL_OS_EXECUTION_NOT_AUTHORIZED")


class PhysicalSession:
    """Reserved type: no constructor/decoder/issuer can mint one in OAA-02."""

    def __new__(cls) -> "PhysicalSession":
        raise PhysicalNotAuthorized()


def require_physical_session(session: object, role: str) -> None:
    """Closed admission boundary, intentionally unavailable until a later scope.

    A future independently reviewed issuer must bind actual kernel observations,
    source/runtime/platform and case-scoped Owner permits. Duck typing, object
    construction, a boolean, a nonce or a purported approval hash cannot do that.
    """
    raise PhysicalNotAuthorized()


@dataclass(frozen=True, slots=True)
class ProcessClaim:
    installation_id: str
    generation: str
    launcher_id: str
    boot_id: str
    pid: int
    parent_pid: int
    start_ticks: str
    pgid: int
    sid: int
    nonce_sha256: str
    install_dev: str
    install_ino: str
    job_dev: str
    job_ino: str
    executable_sha256: str
    source_sha256: str
    runtime_sha256: str
    helper_sha256: str

    def __post_init__(self) -> None:
        ids = [
            c.uuid4_text(getattr(self, k)) for k in ("installation_id", "generation", "launcher_id")
        ]
        p.require(len(set(ids)) == 3)
        boot_text(self.boot_id)
        for k in ("pid", "parent_pid", "pgid", "sid"):
            process_number(getattr(self, k))
        for k in ("start_ticks", "install_ino", "job_ino"):
            p.decimal_text(getattr(self, k), positive=True)
        for k in ("install_dev", "job_dev"):
            p.decimal_text(getattr(self, k))
        for descriptor in fields(self):
            if descriptor.name.endswith("sha256"):
                c.sha256_text(getattr(self, descriptor.name))


def same_supplied_identity(expected: ProcessClaim, observed: ProcessClaim) -> bool:
    p.require(type(expected) is ProcessClaim and type(observed) is ProcessClaim)
    expected.__post_init__()
    observed.__post_init__()
    return expected == observed  # Supplied equality, never kernel evidence.


@dataclass(frozen=True, slots=True)
class Credentials:
    pid: int
    uid: int
    gid: int

    def __post_init__(self) -> None:
        process_number(self.pid)
        for value in (self.uid, self.gid):
            p.require(type(value) is int and 0 <= value <= 2**31 - 1)


@dataclass(frozen=True, slots=True)
class Binding:
    installation_id: str
    app_run_id: str
    generation: str
    launcher_id: str
    nonce: str

    def __post_init__(self) -> None:
        ids = [
            c.uuid4_text(getattr(self, k))
            for k in ("installation_id", "app_run_id", "generation", "launcher_id")
        ]
        p.require(len(set(ids)) == 4)
        c.sha256_text(self.nonce)


def _payload(kind: str, value: c.JSONValue) -> c.WireObject:
    p.require(kind in PAYLOAD_FIELDS)
    obj = p.bounded_record(c.canonical_json(value), PAYLOAD_FIELDS[kind])
    for key, item in obj.items():
        if key.endswith("sha256"):
            c.sha256_text(item)
        elif key.endswith("_id") and key != "boot_id":
            c.uuid4_text(item)
        elif key == "boot_id":
            boot_text(item)
        elif key in ("pid", "parent_pid", "pgid", "sid"):
            process_number(item)
        elif key.endswith(("_ns", "_ticks", "_dev", "_ino")):
            p.decimal_text(
                item, positive=key.endswith(("_ino", "_ticks")) or key == "deadline_monotonic_ns"
            )
        elif key.endswith(("revision", "sequence")):
            p.require(
                type(item) is int and (0 if key == "expected_revision" else 1) <= item < 2**53
            )
        elif key == "root_path":
            p.path_form(c.text(item))
        elif key == "launcher_record":
            nested = p.bounded_record(c.canonical_json(item), LAUNCHER_FIELDS)
            p.require(type(nested["version"]) is int and nested["version"] == 1)
            for name, val in nested.items():
                if name.endswith("_id") or name == "generation":
                    boot_text(val) if name == "boot_id" else c.uuid4_text(val)
                elif name.endswith("sha256"):
                    c.sha256_text(val)
                elif name in ("pid", "pgid", "sid"):
                    process_number(val)
                elif name.endswith(("_dev", "_ino", "_ticks")):
                    p.decimal_text(val, positive=not name.endswith("_dev"))
    return obj


def frame(binding: Binding, sequence: int, kind: str, payload: c.WireObject) -> bytes:
    binding.__post_init__()
    p.require(type(sequence) is int and 1 <= sequence <= FRAME_COUNT)
    _payload(kind, payload)
    raw = c.canonical_json(
        {
            "version": 1,
            "type": kind,
            "installation_id": binding.installation_id,
            "app_run_id": binding.app_run_id,
            "generation": binding.generation,
            "launcher_id": binding.launcher_id,
            "sequence": sequence,
            "nonce": binding.nonce,
            "payload": payload,
        }
    )
    p.require(len(raw) <= FRAME_LIMIT)
    return raw


class ChannelWindow:
    """Pure bounded receive state. Any bad frame permanently closes this window."""

    def __init__(self, binding: Binding, sender: Credentials) -> None:
        binding.__post_init__()
        sender.__post_init__()
        self.binding, self.sender = binding, sender
        self.accepted = 0
        self.closed = False

    def accept(
        self,
        raw: bytes,
        ancillary: list[tuple[int, int, bytes]] | tuple[tuple[int, int, bytes], ...],
        flags: int = 0,
    ) -> c.WireObject:
        p.require(not self.closed)
        self.closed = True
        p.require(type(flags) is int and flags == 0)
        # recvmsg supplies an exact list; recorded-only callers also use tuples.
        # Validate supplied structure before unpacking, without granting provenance.
        p.require(type(ancillary) in (list, tuple) and len(ancillary) == 1)
        control = ancillary[0]
        p.require(type(control) is tuple and len(control) == 3)
        level, kind, data = control
        p.require(type(level) is int and type(kind) is int)
        p.require(level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS)
        p.require(type(data) is bytes and len(data) == struct.calcsize("3i"))
        p.require(Credentials(*struct.unpack("3i", data)) == self.sender)
        obj = p.bounded_record(raw, ENVELOPE, FRAME_LIMIT)
        p.require(type(obj["version"]) is int and obj["version"] == 1)
        p.require(self.accepted < FRAME_COUNT)
        p.require(type(obj["sequence"]) is int and obj["sequence"] == self.accepted + 1)
        for name in ("installation_id", "app_run_id", "generation", "launcher_id", "nonce"):
            p.require(obj[name] == getattr(self.binding, name))
        _payload(c.text(obj["type"]), obj["payload"])
        self.accepted += 1
        self.closed = False
        return obj


@dataclass(frozen=True, slots=True)
class FDPlan:
    role: str
    descriptors: tuple[int, ...]

    def __post_init__(self) -> None:
        p.require(self.role in ("watchdog", "supervisor", "launcher", "contender", "child"))
        p.require(type(self.descriptors) is tuple)
        p.require(len(self.descriptors) == (2 if self.role == "launcher" else 1))
        p.require(all(type(fd) is int and 3 <= fd < 32 for fd in self.descriptors))
        p.require(len(set(self.descriptors)) == len(self.descriptors))


@dataclass(frozen=True, slots=True)
class InheritedLeaseClaim:
    original_fd: int
    inherited_fd: int
    device: str
    inode: str
    acquired_by_original_s: bool
    passed_by_original_s: bool
    cloexec_restored: bool

    def consistent_model(self) -> bool:
        p.decimal_text(self.device)
        p.decimal_text(self.inode, positive=True)
        p.require(
            all(
                type(x) is bool
                for x in (
                    self.acquired_by_original_s,
                    self.passed_by_original_s,
                    self.cloexec_restored,
                )
            )
        )
        return (
            type(self.original_fd) is int
            and type(self.inherited_fd) is int
            and self.original_fd >= 3
            and self.inherited_fd >= 3
            and self.acquired_by_original_s
            and self.passed_by_original_s
            and self.cloexec_restored
        )


def signal_refusal(expected: ProcessClaim, observed: ProcessClaim) -> str:
    return (
        "PHYSICAL_NOT_AUTHORIZED"
        if same_supplied_identity(expected, observed)
        else "FOREIGN_TARGET"
    )


class LinuxAdapters:
    """All physical methods check the unavailable session before their first I/O."""

    @staticmethod
    def lock(session: object, root: Path, path: Path, role: str) -> int:
        require_physical_session(session, role)
        p.require(role in ("supervisor", "launcher"))
        p.require(
            re.fullmatch(r"/tmp/pit-p103b-os-helper\.[0-9]+\.[A-Za-z0-9]+", str(root)) is not None
        )
        p.require(path.is_relative_to(root) and path.name in ("installation.lock", "job.lock"))
        for directory in (path.parent, *path.parent.parents):
            info = directory.lstat()
            p.require(stat.S_ISDIR(info.st_mode))
            if directory == root or directory.is_relative_to(root):
                p.require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700)
        before = path.lstat()
        p.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1)
        p.require(before.st_uid == os.getuid() and stat.S_IMODE(before.st_mode) == 0o600)
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            after = os.fstat(fd)
            p.require((after.st_dev, after.st_ino) == (before.st_dev, before.st_ino))
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            now = path.lstat()
            p.require((now.st_dev, now.st_ino) == (after.st_dev, after.st_ino))
            return fd
        except BaseException:
            os.close(fd)  # No LOCK_UN: shared OFD copies are only closed.
            raise

    @staticmethod
    def restore_cloexec(session: object, fd: int) -> None:
        require_physical_session(session, "launcher")
        fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)

    @staticmethod
    def socketpair(session: object) -> tuple[socket.socket, socket.socket]:
        require_physical_session(session, "supervisor")
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            for endpoint in (left, right):
                endpoint.set_inheritable(False)
                endpoint.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
                endpoint.setblocking(False)
            return left, right
        except BaseException:
            left.close()
            right.close()
            raise

    @staticmethod
    def process(session: object, pid: int) -> tuple[str, bytes]:
        require_physical_session(session, "observer")
        process_number(pid)
        with Path("/proc/sys/kernel/random/boot_id").open("rb") as stream:
            boot = stream.read(38).strip().decode("ascii")
        boot_text(boot)
        with Path(f"/proc/{pid}/stat").open("rb") as stream:
            raw = stream.read(4097).removesuffix(b"\n")
        p.require(parse_supplied_stat(raw).pid == pid)
        return boot, raw

    @staticmethod
    def pidfd(session: object, claim: ProcessClaim) -> int:
        require_physical_session(session, "observer")
        p.require(hasattr(os, "pidfd_open"), "PIDFD_UNAVAILABLE")
        claim.__post_init__()
        boot, raw = LinuxAdapters.process(session, claim.pid)
        parsed = parse_supplied_stat(raw)
        p.require(
            (boot, parsed.start_ticks, parsed.parent_pid, parsed.pgid, parsed.sid)
            == (claim.boot_id, claim.start_ticks, claim.parent_pid, claim.pgid, claim.sid)
        )
        fd = os.pidfd_open(claim.pid, 0)
        try:
            after_boot, after_raw = LinuxAdapters.process(session, claim.pid)
            after = parse_supplied_stat(after_raw)
            p.require(
                (after_boot, after.pid, after.start_ticks, after.parent_pid, after.pgid, after.sid)
                == (
                    boot,
                    parsed.pid,
                    parsed.start_ticks,
                    parsed.parent_pid,
                    parsed.pgid,
                    parsed.sid,
                )
            )
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def verify_child(session: object, claim: ProcessClaim) -> None:
        require_physical_session(session, "launcher")
        claim.__post_init__()
        boot, raw = LinuxAdapters.process(session, claim.pid)
        observed = parse_supplied_stat(raw)
        p.require(
            (boot, observed.parent_pid, observed.start_ticks, observed.pgid, observed.sid)
            == (claim.boot_id, os.getpid(), claim.start_ticks, claim.pgid, claim.sid)
        )
        p.require(claim.parent_pid == os.getpid() and observed.state not in ("Z", "X", "x"))
        digest = sha256()
        total = 0
        with Path(f"/proc/{claim.pid}/exe").open("rb") as stream:
            before = os.fstat(stream.fileno())
            p.require(stat.S_ISREG(before.st_mode) and before.st_size <= 64 * 1024 * 1024)
            while chunk := stream.read(65536):
                total += len(chunk)
                p.require(total <= 64 * 1024 * 1024)
                digest.update(chunk)
            after = os.fstat(stream.fileno())
            p.require(
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            )
        p.require(digest.hexdigest() == claim.executable_sha256)

    @staticmethod
    def signal_one(
        session: object, pidfd: int, expected: ProcessClaim, observed: ProcessClaim, number: int
    ) -> None:
        require_physical_session(session, "signal")
        p.require(hasattr(signal, "pidfd_send_signal"), "PIDFD_SIGNAL_UNAVAILABLE")
        p.require(same_supplied_identity(expected, observed))
        p.require(type(pidfd) is int and pidfd >= 3)
        p.require(number in (signal.SIGTERM, signal.SIGKILL))
        boot, raw = LinuxAdapters.process(session, expected.pid)
        live = parse_supplied_stat(raw)
        p.require(
            (boot, live.start_ticks, live.parent_pid, live.pgid, live.sid)
            == (
                expected.boot_id,
                expected.start_ticks,
                expected.parent_pid,
                expected.pgid,
                expected.sid,
            )
        )
        if live.state in ("Z", "X", "x"):
            return
        with Path(f"/proc/self/fdinfo/{pidfd}").open("rb") as stream:
            descriptor = stream.read(4097)
        p.require(len(descriptor) <= 4096 and f"Pid:\t{expected.pid}\n".encode() in descriptor)
        signal.pidfd_send_signal(pidfd, number)
