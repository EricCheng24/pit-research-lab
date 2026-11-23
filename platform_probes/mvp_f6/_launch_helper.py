"""Dormant fixed-role source. Do not import or execute under OAA-02.

The child body uses stdlib only. No permit issuer exists here or in environment,
argv, a JSON profile or a hash. Native execution is not a role.
Protocol refusal uses EXIT 70; intentional EXIT 0/7 requires completed release.
"""

import argparse

ROLES = ("supervisor", "launcher", "contender", "child")
PROTOCOL_REFUSAL_EXIT = 70


def require_future_permit(session, role):
    raise PermissionError("PHYSICAL_OS_EXECUTION_NOT_AUTHORIZED")


def parse_fixed_arguments(argv):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--context-fd", type=int)
    parser.add_argument("--control-fd", type=int)
    parser.add_argument("--installation-fd", type=int)
    parser.add_argument("--exit-code", type=int, choices=(0, 7))
    args = parser.parse_args(argv)
    expected = {
        "supervisor": (True, False, False, False),
        "contender": (True, False, False, False),
        "launcher": (False, True, True, False),
        "child": (False, True, False, True),
    }[args.role]
    actual = tuple(
        v is not None
        for v in (args.context_fd, args.control_fd, args.installation_fd, args.exit_code)
    )
    if actual != expected:
        parser.error("closed role argument mismatch")
    descriptors = [
        fd for fd in (args.context_fd, args.control_fd, args.installation_fd) if fd is not None
    ]
    if any(not 3 <= fd < 32 for fd in descriptors) or len(set(descriptors)) != len(descriptors):
        parser.error("invalid inherited descriptors")
    return args


def _child_body(session, control_fd, exit_code):
    require_future_permit(session, "child")  # Before every import capable of OS activity.
    if type(exit_code) is not int or exit_code not in (0, 7):
        return PROTOCOL_REFUSAL_EXIT
    import json
    import os
    import selectors
    import socket
    import struct
    import time

    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("DUPLICATE_KEY")
            obj[key] = value
        return obj

    def bad_number(value):
        raise ValueError("NONINTEGER_NUMBER")

    deadline = time.monotonic() + 2.0
    parent = os.getppid()
    endpoint = socket.socket(fileno=control_fd)
    endpoint.set_inheritable(False)
    endpoint.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    endpoint.setblocking(False)
    selector = selectors.DefaultSelector()
    selector.register(endpoint, selectors.EVENT_READ)
    envelope_keys = {
        "version",
        "type",
        "installation_id",
        "app_run_id",
        "generation",
        "launcher_id",
        "sequence",
        "nonce",
        "payload",
    }

    def receive(sequence):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not selector.select(remaining):
            raise TimeoutError("CHILD_DEADLINE")
        raw, ancillary, flags, _ = endpoint.recvmsg(16385, socket.CMSG_SPACE(struct.calcsize("3i")))
        if not raw or len(raw) > 16384 or flags or len(ancillary) != 1:
            raise ValueError("INVALID_FRAME")
        level, kind, credentials = ancillary[0]
        if level != socket.SOL_SOCKET or kind != socket.SCM_CREDENTIALS:
            raise ValueError("INVALID_CREDENTIALS")
        if len(credentials) != struct.calcsize("3i"):
            raise ValueError("INVALID_CREDENTIALS")
        pid, uid, gid = struct.unpack("3i", credentials)
        if (pid, uid, gid) != (parent, os.getuid(), os.getgid()):
            raise ValueError("FOREIGN_PARENT")
        message = json.loads(
            raw, object_pairs_hook=pairs, parse_float=bad_number, parse_constant=bad_number
        )
        if (
            set(message) != envelope_keys
            or type(message["version"]) is not int
            or message["version"] != 1
        ):
            raise ValueError("INVALID_ENVELOPE")
        if type(message["sequence"]) is not int or message["sequence"] != sequence:
            raise ValueError("REPLAY")
        if (
            json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            != raw
        ):
            raise ValueError("NONCANONICAL")
        return message

    try:
        context = receive(1)
        if context["type"] != "CHILD_CONTEXT" or set(context["payload"]) != {
            "permission_id",
            "child_id",
            "command_sha256",
            "deadline_monotonic_ns",
        }:
            return PROTOCOL_REFUSAL_EXIT
        if time.monotonic_ns() >= int(context["payload"]["deadline_monotonic_ns"]):
            return PROTOCOL_REFUSAL_EXIT
        with open("/proc/sys/kernel/random/boot_id", "rb") as stream:
            boot = stream.read(38).strip().decode("ascii")
        with open("/proc/self/stat", "rb") as stream:
            raw_stat = stream.read(4097).strip()
        if len(raw_stat) > 4096:
            return PROTOCOL_REFUSAL_EXIT
        # The reviewed Python helper comm must not contain ambiguous delimiters.
        close = raw_stat.find(b") ")
        if (
            close < 0
            or b"(" in raw_stat[raw_stat.find(b"(") + 1 : close]
            or b")" in raw_stat[close + 2 :]
        ):
            return PROTOCOL_REFUSAL_EXIT
        values = raw_stat[close + 2 :].split()
        if len(values) < 20 or int(values[1]) != parent:
            return PROTOCOL_REFUSAL_EXIT
        import hashlib
        import sys

        with open(sys.executable, "rb") as stream:
            executable = hashlib.file_digest(stream, "sha256").hexdigest()
        hello = dict(context)
        hello["type"], hello["sequence"] = "CHILD_HELLO", 1
        hello["payload"] = {
            "permission_id": context["payload"]["permission_id"],
            "child_id": context["payload"]["child_id"],
            "boot_id": boot,
            "pid": os.getpid(),
            "parent_pid": parent,
            "start_ticks": values[19].decode("ascii"),
            "pgid": int(values[2]),
            "sid": int(values[3]),
            "executable_sha256": executable,
            "command_sha256": context["payload"]["command_sha256"],
        }
        encoded = json.dumps(hello, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > 16384 or endpoint.send(encoded) != len(encoded):
            return PROTOCOL_REFUSAL_EXIT
        release = receive(2)
        if release["type"] != "CHILD_REGISTERED_ACK" or set(release["payload"]) != {
            "child_id",
            "revision",
            "event_sha256",
        }:
            return PROTOCOL_REFUSAL_EXIT
        if release["payload"]["child_id"] != context["payload"]["child_id"]:
            return PROTOCOL_REFUSAL_EXIT
        if any(
            release[key] != context[key] for key in envelope_keys - {"type", "sequence", "payload"}
        ):
            return PROTOCOL_REFUSAL_EXIT
        if time.monotonic() >= deadline:
            return PROTOCOL_REFUSAL_EXIT
        # Fixed finite output; never include nonce plaintext or environment values.
        print(
            json.dumps(
                {
                    "helper": "NOFORK_EXIT_ONLY",
                    "pid": os.getpid(),
                    "environment_keys": sorted(os.environ),
                },
                sort_keys=True,
            )
        )
        return exit_code
    except (OSError, ValueError, KeyError, TypeError, TimeoutError):
        return PROTOCOL_REFUSAL_EXIT
    finally:
        selector.close()
        endpoint.close()


def _supervisor_body(session, context_fd):
    require_future_permit(session, "supervisor")
    # The unavailable genuine session owns bootstrap, observed Tx0 registration,
    # Tx1 admission and the one L handle. It cannot come from argv/JSON/env.
    runtime, original_io = session.original_supervisor(context_fd)
    runtime.run_owned(session, original_io)


def _launcher_body(session, control_fd, installation_fd):
    require_future_permit(session, "launcher")
    runtime, spec, plan, original_io = session.original_launcher(control_fd, installation_fd)
    runtime.run_owned(session, spec, plan, original_io)


def _contender_body(session, context_fd):
    require_future_permit(session, "contender")
    # Only the fixed original installation/job inode probes, never a GO/arm.
    session.original_contender(context_fd).probe_fixed_leases_nonblocking()


def main(argv=None):
    # Fail before argument parsing/import/bootstrap; CLI input never supplies authority.
    require_future_permit(None, "entrypoint")
    return 7


if __name__ == "__main__":
    raise SystemExit(main())
