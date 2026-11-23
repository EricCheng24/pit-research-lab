"""Dormant W source/policy; OAA-02 never imports or invokes this file.

No current permit issuer, arbitrary command runner, generic PID kill or cleanup
fallback. Actual subreaper/target/platform proof requires later authorization.
"""

from dataclasses import dataclass

STARTS = {"P01": 4, "P02": 4, "P03": 4, "P04": 3, "P05": 4, "P06": 3, "F00": 2, "F01": 4}


def require_future_permit(session, case, operation):
    raise PermissionError("PHYSICAL_OS_EXECUTION_NOT_AUTHORIZED")


@dataclass(frozen=True)
class Target:
    pid: int
    parent_pid: int
    boot_id: str
    start_ticks: str
    pidfd: int
    identity_sha256: str


class Budget:
    def __init__(self, case):
        if case not in STARTS:
            raise ValueError("UNAPPROVED_CASE")
        self.case, self.starts = case, 0
        self.log_bytes, self.total_bytes = 0, 0

    def reserve_start(self):
        if self.starts >= STARTS[self.case]:
            raise ValueError("START_CEILING")
        self.starts += 1

    def account(self, log_bytes, total_bytes):
        if (
            type(log_bytes) is not int
            or type(total_bytes) is not int
            or min(log_bytes, total_bytes) < 0
        ):
            raise ValueError("INVALID_ACCOUNTING")
        self.log_bytes += log_bytes
        self.total_bytes += total_bytes
        if self.log_bytes > 16384 or self.total_bytes > 8 * 1024 * 1024:
            raise ValueError("BYTE_CEILING")


def _apply_limits(session, case):
    require_future_permit(session, case, "limits")
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (1, 2))
    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024, 256 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _subreaper(session, case):
    require_future_permit(session, case, "subreaper")
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    # Linux PR_SET_CHILD_SUBREAPER/PR_GET_CHILD_SUBREAPER; no privilege request.
    state = ctypes.c_int()
    if libc.prctl(36, 1, 0, 0, 0) != 0 or libc.prctl(37, ctypes.byref(state), 0, 0, 0) != 0:
        raise OSError("SUBREAPER_UNAVAILABLE")
    if state.value != 1:
        raise OSError("SUBREAPER_UNVERIFIED")


def _signal_verified(session, case, target, expected, number, deadline):
    require_future_permit(session, case, "signal")  # Separate signal/cleanup permit required.
    import signal
    import time

    if type(target) is not Target or target != expected or time.monotonic() >= deadline:
        raise PermissionError("UNVERIFIED_TARGET_OR_DEADLINE")
    if number not in (signal.SIGTERM, signal.SIGKILL) or target.pidfd < 3:
        raise PermissionError("UNAPPROVED_SIGNAL")
    # A future issuer must retain the original lineage, source/exec and pidfd
    # observation. This check additionally fences the current task/descriptor.
    with open("/proc/sys/kernel/random/boot_id", "rb") as stream:
        boot = stream.read(38).strip().decode("ascii")
    with open(f"/proc/{target.pid}/stat", "rb") as stream:
        raw = stream.read(4097).strip()
    close = raw.find(b") ")
    if close < 0 or len(raw) > 4096:
        raise PermissionError("UNVERIFIED_PROC")
    values = raw[close + 2 :].split()
    if len(values) < 20 or int(values[1]) != target.parent_pid:
        raise PermissionError("CHANGED_PARENT_NO_ADOPTION_AUTHORITY")
    if len(values) < 20 or (boot, values[19].decode("ascii")) != (
        target.boot_id,
        target.start_ticks,
    ):
        raise PermissionError("CHANGED_TARGET")
    if values[0] in (b"Z", b"X", b"x"):
        return  # Terminal observation stops signaling; never act after reap.
    with open(f"/proc/self/fdinfo/{target.pidfd}", "rb") as stream:
        descriptor = stream.read(4097)
    if len(descriptor) > 4096 or f"Pid:\t{target.pid}\n".encode() not in descriptor:
        raise PermissionError("FOREIGN_PIDFD")
    signal.pidfd_send_signal(target.pidfd, number)


def run_case(session, case):
    require_future_permit(session, case, "platform_and_cleanup")
    import time

    budget = Budget(case)
    budget.reserve_start()  # W is included, not a hidden command wrapper.
    _apply_limits(session, case)
    _subreaper(session, case)
    original_io = session.original_watchdog(case)
    original_io.validate_platform_and_cleanup()
    started = time.monotonic()
    shutdown, deadline = started + 6.0, started + 8.0
    seen = set()
    try:
        # The fixed case topology, source/helper pins and no arbitrary commands
        # are owned by the as-yet-unissued physical context.
        original_io.start_fixed_topology(budget)
        while time.monotonic() < shutdown:
            event = original_io.receive_owned_event(min(0.1, shutdown - time.monotonic()))
            if event is None:
                continue
            if event["kind"] == "START_REQUEST":
                original_io.verify_original_start_request(event)
                budget.reserve_start()  # Before granting even a possibly failed OS attempt.
                original_io.allow_one_original_start(event)
            elif event["kind"] == "ROLE_REGISTERED":
                identity = event["identity_sha256"]
                if identity in seen:
                    raise ValueError("DUPLICATE_ROLE_REGISTRATION")
                original_io.verify_original_role(event)
                seen.add(identity)
                # Birth is evidence, not a new grant or a reason to count again.
            elif event["kind"] == "EVIDENCE_BYTES":
                budget.account(event["log_bytes"], event["total_bytes"])
            elif event["kind"] == "LIFECYCLE_DISPOSITION":
                original_io.verify_case_oracle(event)
                break
            else:
                raise ValueError("UNKNOWN_WATCHDOG_EVENT")
        else:
            raise TimeoutError("NODE_WORK_DEADLINE")
        original_io.cooperative_close_bottom_up(deadline)
        original_io.verify_original_reaps_fd_lease_closure()
        return original_io.capture_actual_evidence(budget.starts, deadline)
    except BaseException:
        original_io.stop_admission()
        original_io.cooperative_close_bottom_up(deadline)
        # A separately approved emergency signal context is necessary. If absent
        # or any target is ambiguous, retain residual evidence; no fallback kill.
        original_io.retain_residual_evidence(deadline)
        raise


def main(argv=None):
    require_future_permit(None, "UNSELECTED", "entrypoint")


if __name__ == "__main__":
    main()
