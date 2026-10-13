"""Passive prerequisite diagnosis. Invoke with Python -I -S -B; stdlib only."""

from __future__ import annotations

import os
import re
import selectors
import shutil
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

PASS, WARN, FAIL, NC = "PASS", "WARN", "FAIL", "NOT CHECKED"
USAGE = "Usage: sh scripts/doctor.sh [--profile core|test] | --help"
LIMIT = 4096
GIT_PREFIX = ("--no-optional-locks", "-c", "core.fsmonitor=false", "rev-parse")
CONTEXT_FORMAT = "{{.Endpoints.docker.Host}}"
DAEMON_ARGS = ("info", "--format", "{{.ServerVersion}}")
ALLOWLIST = {
    "uv": {("--version",)},
    "git": {
        ("--version",),
        (*GIT_PREFIX, "--is-inside-work-tree"),
        (*GIT_PREFIX, "--show-toplevel"),
    },
    "docker": {("--version",), ("compose", "version", "--short"), ("context", "show"), DAEMON_ARGS},
}
TEST_IDS = (
    "ROUTING",
    "DOCKER_CLI",
    "COMPOSE_V2",
    "DOCKER_CONTEXT",
    "DOCKER_DAEMON",
    "TEST_CONFIG",
    "TEST_PATHS",
)
VERSION = r"([0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4})"
UV_VERSION = (
    r"uv "
    + VERSION
    + r"(?: \((?:[a-f0-9]{7,40} [0-9]{4}-[0-9]{2}-[0-9]{2}"
    + r"|(?:x86_64|aarch64)-(?:unknown-linux-gnu|apple-darwin))\))?"
)
GIT_VERSION = r"git version " + VERSION + r"(?: \(Apple Git-[0-9.]{1,20}\))?"
DOCKER_VERSION = r"Docker version " + VERSION + r", build [a-f0-9]{7,40}"


class Check(NamedTuple):
    id: str
    state: str
    reason: str
    required: bool = True
    group: str = "core"


class Probe(NamedTuple):
    code: int = 0
    out: bytes = b""
    err: bytes = b""
    issue: str = ""


def valid_context(name: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name, re.ASCII) is not None


def child_environment(tool: str, environ) -> dict[str, str]:
    # Read values only for these explicitly justified child-process settings.
    keys = ("PATH", "HOME", "WSL_INTEROP") if tool == "docker" else ("PATH",)
    result = {key: environ[key] for key in keys if key in environ}
    result.update(LANG="C", LC_ALL="C")
    if tool == "git":
        result.update(
            GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null"
        )
    return result


def run_probe(
    tool: str, args: tuple[str, ...], root: Path, environ, *, context: str | None = None
) -> Probe:
    """Closed argv; IC-01 permits only a validated current-context inspect name."""
    context_allowed = (
        tool == "docker"
        and isinstance(context, str)
        and valid_context(context)
        and args == ("context", "inspect", "--format", CONTEXT_FORMAT, context)
    )
    if args not in ALLOWLIST.get(tool, ()) and not context_allowed:
        return Probe(issue="forbidden")
    timeout = 5 if tool == "docker" and args == DAEMON_ARGS else 3
    process = None
    try:
        executable = shutil.which(tool, path=environ.get("PATH", os.defpath))
        if executable is None:
            return Probe(issue="missing")
        deadline = time.monotonic() + timeout
        process = subprocess.Popen(
            [executable, *args],
            cwd=root,
            env=child_environment(tool, environ),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        buffers = [bytearray(), bytearray()]
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, 0)
            selector.register(process.stderr, selectors.EVENT_READ, 1)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return Probe(issue="timeout")
                ready = selector.select(remaining)
                if not ready:
                    return Probe(issue="timeout")
                for key, _ in ready:
                    chunk = os.read(key.fd, 1024)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif len(buffers[key.data]) + len(chunk) > LIMIT:
                        return Probe(issue="overflow")
                    else:
                        buffers[key.data].extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return Probe(issue="timeout")
        code = process.wait(timeout=remaining)
        return Probe(code, bytes(buffers[0]), bytes(buffers[1]))
    except FileNotFoundError:
        return Probe(issue="missing")
    except PermissionError:
        return Probe(issue="denied")
    except subprocess.TimeoutExpired:
        return Probe(issue="timeout")
    except (OSError, ValueError):
        return Probe(issue="unavailable")
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


def line(data: bytes) -> str:
    # One terminal newline is permitted; embedded/trailing controls are not.
    value = data.decode("utf-8")
    if value.endswith("\n"):
        value = value[:-1]
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError
    return value


def probe_problem(
    id: str, probe: Probe, group: str = "core", *, uncertain_nonzero: bool = False
) -> Check | None:
    if probe.issue:
        state = FAIL if probe.issue in ("missing", "denied") else NC
        messages = {
            "missing": "Tool unavailable; install/select it separately.",
            "denied": "Tool access denied; seek Lead review.",
            "timeout": "Probe timed out; seek Lead review, no retry.",
            "overflow": "Probe exceeded output bound; seek Lead review.",
        }
        return Check(
            id,
            state,
            messages.get(probe.issue, "Probe unavailable or unsafe; seek Lead review."),
            group=group,
        )
    if probe.code:
        return Check(
            id,
            NC if uncertain_nonzero else FAIL,
            "Tool query unsuccessful; review tool/access separately.",
            group=group,
        )
    if probe.err:
        return Check(id, NC, "Unexpected diagnostic output; seek Lead review.", group=group)
    return None


def version_check(id: str, probe: Probe, pattern: str, group: str = "core") -> Check:
    problem = probe_problem(id, probe, group)
    if problem:
        return problem
    try:
        match = re.fullmatch(pattern, line(probe.out), re.ASCII)
        if match is None:
            raise ValueError
        version = match[1]
        if id == "COMPOSE_V2" and version.split(".")[0] != "2":
            return Check(id, FAIL, "Compose v2 required; review setup separately.", group=group)
        return Check(id, PASS, "Version " + version + " recognized.", group=group)
    except (ValueError, UnicodeError):
        return Check(id, NC, "Version output indeterminate; seek Lead review.", group=group)


def platform_checks() -> list[Check]:
    try:
        platform = sys.platform
        info = os.uname()
        bits = struct.calcsize("P") * 8
        if platform not in ("linux", "darwin"):
            state = FAIL if platform in ("win32", "cygwin", "freebsd") else NC
            return [
                Check("PLATFORM", state, "Unsupported/unknown process platform; seek Lead review.")
            ]
        if info.sysname != {"linux": "Linux", "darwin": "Darwin"}[platform]:
            raise ValueError
        if not re.fullmatch(r"[A-Za-z0-9_]{1,32}", info.machine):
            raise ValueError
        supported = bits == 64 and (
            (platform == "linux" and info.machine == "x86_64")
            or (platform == "darwin" and info.machine in ("arm64", "aarch64"))
        )
        if not supported:
            return [
                Check(
                    "PLATFORM",
                    FAIL,
                    "Process architecture outside target; native ARM64 not established on Darwin.",
                )
            ]
        label = "Linux x86_64" if platform == "linux" else "Darwin ARM64"
        checks = [Check("PLATFORM", PASS, label + " process signal; workflows not verified.")]
        if platform == "linux":
            try:
                release = info.release.lower()
            except (AttributeError, TypeError):
                checks.append(
                    Check(
                        "WSL2_SIGNAL",
                        NC,
                        "Kernel signal unavailable; Linux Core independent.",
                        False,
                    )
                )
                return checks
            if "microsoft-standard-wsl2" in release:
                checks.append(Check("WSL2_SIGNAL", PASS, "WSL2 kernel signal only.", False))
            else:
                reason = (
                    "WSL generation ambiguous; Linux Core remains independent."
                    if "microsoft" in release or "wsl" in release
                    else "WSL2 not established; generic Linux Core remains independent."
                )
                checks.append(Check("WSL2_SIGNAL", NC, reason, False))
        return checks
    except (AttributeError, OSError, TypeError, ValueError):
        return [Check("PLATFORM", NC, "Process platform indeterminate; seek Lead review.")]


def metadata_check(
    root: Path, names: tuple[str, ...], id: str, *, private: bool = False, group: str = "core"
) -> Check:
    try:
        for name in names:
            info = (root / name).lstat()
            valid = stat.S_ISREG(info.st_mode)
            if name == "scripts":
                valid = stat.S_ISDIR(info.st_mode)
            if private:
                valid = valid and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600
            if not valid:
                return Check(
                    id,
                    FAIL,
                    "Expected file metadata invalid; retain it and seek Lead review.",
                    group=group,
                )
        reason = (
            "Regular, operator-owned mode-0600 file; contents not read."
            if private
            else "Expected source-file metadata present; contents not validated."
        )
        return Check(id, PASS, reason, group=group)
    except FileNotFoundError:
        return Check(
            id, FAIL, "Expected file missing; review setup/source separately.", group=group
        )
    except (OSError, AttributeError):
        return Check(id, NC, "File metadata unavailable; seek Lead review, no repair.", group=group)


def checkout_check(root: Path, environ) -> Check:
    for argument in ("--is-inside-work-tree", "--show-toplevel"):
        result = run_probe("git", (*GIT_PREFIX, argument), root, environ)
        if result.code and b"not a git repository" in result.err.lower():
            return Check("CHECKOUT", FAIL, "Not a Git worktree; review checkout separately.")
        problem = probe_problem("CHECKOUT", result, uncertain_nonzero=True)
        if problem:
            return problem
        try:
            expected = "true" if argument == "--is-inside-work-tree" else str(root)
            if line(result.out) != expected:
                return Check(
                    "CHECKOUT", FAIL, "Worktree root mismatch; review checkout separately."
                )
        except (ValueError, UnicodeError):
            return Check("CHECKOUT", NC, "Checkout identity indeterminate; seek Lead review.")
    return Check("CHECKOUT", PASS, "Expected Git worktree root observed.")


def routing_check(environ) -> Check:
    # Deliberately never retrieve values, even for empty exports or hostile names.
    families = [
        prefix + "*"
        for prefix in ("PG", "COMPOSE_", "PITLAB_", "DOCKER_")
        if any(key.startswith(prefix) for key in environ)
    ]
    if families:
        return Check(
            "ROUTING",
            FAIL,
            "Restricted names present: "
            + ", ".join(families)
            + "; review shell exports separately.",
            group="test",
        )
    return Check("ROUTING", PASS, "No restricted routing names present.", group="test")


def context_check(root: Path, environ) -> Check:
    result = run_probe("docker", ("context", "show"), root, environ)
    problem = probe_problem("DOCKER_CONTEXT", result, "test", uncertain_nonzero=True)
    if problem:
        return problem
    try:
        name = line(result.out)
        if not valid_context(name):
            raise ValueError
        result = run_probe(
            "docker",
            ("context", "inspect", "--format", CONTEXT_FORMAT, name),
            root,
            environ,
            context=name,
        )
        problem = probe_problem("DOCKER_CONTEXT", result, "test", uncertain_nonzero=True)
        if problem:
            return problem
        endpoint = line(result.out)
        if re.fullmatch(r"unix:///[^\x00-\x20\x7f?#]+", endpoint, re.ASCII):
            return Check(
                "DOCKER_CONTEXT",
                PASS,
                "Local Unix endpoint signal; ownership not proven.",
                group="test",
            )
        if re.fullmatch(r"(?:tcp|ssh|http|https|npipe)://[^\x00-\x20\x7f]+", endpoint):
            return Check(
                "DOCKER_CONTEXT",
                FAIL,
                "Nonlocal/non-Unix context; retain it, seek Lead review.",
                group="test",
            )
        raise ValueError
    except (ValueError, UnicodeError):
        return Check(
            "DOCKER_CONTEXT", NC, "Current-context proof ambiguous; seek Lead review.", group="test"
        )


def daemon_check(root: Path, environ) -> Check:
    result = run_probe("docker", DAEMON_ARGS, root, environ)
    if result.code and any(
        phrase in result.err.lower()
        for phrase in (b"permission denied", b"cannot connect to the docker daemon")
    ):
        return Check(
            "DOCKER_DAEMON",
            FAIL,
            "Daemon access/response unavailable; seek Lead review, no socket repair.",
            group="test",
        )
    problem = probe_problem("DOCKER_DAEMON", result, "test", uncertain_nonzero=True)
    if problem:
        return problem
    return version_check("DOCKER_DAEMON", result, VERSION + r"(?:-[A-Za-z0-9.-]{1,32})?", "test")


def diagnose(root: Path, profile: str, environ, checks: list[Check]) -> None:
    checks.extend(platform_checks())
    checks.append(Check("PYTHON", PASS, "Python 3.12 interpreter observed."))
    uv = version_check("UV", run_probe("uv", ("--version",), root, environ), UV_VERSION)
    checks.append(uv)
    if uv.state == PASS and uv.reason != "Version 0.11.29 recognized.":
        checks.append(
            Check("UV_REFERENCE", WARN, "CI uses uv 0.11.29; local version differs.", False)
        )
    git = version_check("GIT", run_probe("git", ("--version",), root, environ), GIT_VERSION)
    checks.append(git)
    checkout = (
        checkout_check(root, environ)
        if git.state == PASS
        else Check("CHECKOUT", NC, "Git prerequisite unavailable; identity not checked.")
    )
    checks.append(checkout)
    manifests = metadata_check(root, ("pyproject.toml", "uv.lock", ".python-version"), "MANIFESTS")
    checks.append(manifests)
    make = shutil.which("make", path=environ.get("PATH", os.defpath))
    shortcut = metadata_check(root, ("Makefile",), "MAKE")
    checks.append(
        Check(
            "MAKE",
            PASS if make and shortcut.state == PASS else WARN,
            "Optional shortcut; direct uv quality commands are in README.md.",
            False,
        )
    )
    checks.append(
        Check("SHELL_GUIDANCE", PASS, "Use sh launcher or explicit Python; Make optional.", False)
    )
    if profile == "core":
        checks.extend(Check(id, NC, "Excluded by core profile.", False, "test") for id in TEST_IDS)
        return
    routing = routing_check(environ)
    checks.append(routing)
    docker = (
        version_check(
            "DOCKER_CLI", run_probe("docker", ("--version",), root, environ), DOCKER_VERSION, "test"
        )
        if routing.state == PASS
        else Check("DOCKER_CLI", NC, "Routing prerequisite failed; no Docker probe.", group="test")
    )
    checks.append(docker)
    if docker.state == PASS:
        checks.append(
            version_check(
                "COMPOSE_V2",
                run_probe("docker", ("compose", "version", "--short"), root, environ),
                "v?" + VERSION,
                "test",
            )
        )
        context = context_check(root, environ)
        checks.append(context)
        checks.append(
            daemon_check(root, environ)
            if context.state == PASS
            else Check(
                "DOCKER_DAEMON", NC, "Local-context proof absent; daemon not queried.", group="test"
            )
        )
    else:
        checks.extend(
            Check(id, NC, "Docker prerequisite unavailable; probe excluded.", group="test")
            for id in ("COMPOSE_V2", "DOCKER_CONTEXT", "DOCKER_DAEMON")
        )
    if checkout.state == PASS and manifests.state == PASS:
        checks.append(
            metadata_check(root, (".env.test.local",), "TEST_CONFIG", private=True, group="test")
        )
        checks.append(
            metadata_check(
                root,
                ("scripts", "compose.test.yaml", "scripts/database.py", "scripts/init-postgres.sh"),
                "TEST_PATHS",
                group="test",
            )
        )
    else:
        checks.extend(
            Check(id, NC, "Checkout/source proof absent; metadata excluded.", group="test")
            for id in ("TEST_CONFIG", "TEST_PATHS")
        )


def exit_code(checks: list[Check]) -> int:
    required = [check.state for check in checks if check.required]
    if FAIL in required:
        return 1
    # WARN may never substitute for a required property's PASS.
    return 2 if any(state != PASS for state in required) else 0


def render(profile: str, checks: list[Check]) -> int:
    code = exit_code(checks)
    print("PIT Research Lab Environment Doctor — profile " + profile)
    for check in checks:
        print(f"{check.state:<13} {check.id:<16} {check.reason}")
    summaries = {0: "satisfied", 1: "incomplete (failure)", 2: "indeterminate"}
    core = [check for check in checks if check.group == "core"]
    test = [check for check in checks if check.group == "test"]
    print("Core prerequisites: " + summaries[exit_code(core)])
    print(
        "Test prerequisites: " + (summaries[exit_code(test)] if profile == "test" else "excluded")
    )
    print(
        "Next: review docs/development/environment-doctor.md; operator DB work needs separate approval."
    )
    print("Exit: " + str(code))
    return code


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--help"]:
        print(USAGE)
        print("Diagnose prerequisites only; no dependency sync or DB operations.")
        return 0
    if not args:
        profile = "core"
    elif len(args) == 2 and args[0] == "--profile" and args[1] in ("core", "test"):
        profile = args[1]
    else:
        print(USAGE)
        return 64
    checks: list[Check] = []
    try:
        if sys.version_info[:2] != (3, 12):
            checks.append(
                Check("PYTHON", FAIL, "Python 3.12 required; select/install it separately.")
            )
            checks.extend(
                Check(
                    id, NC, "Interpreter incompatible; probe excluded.", profile == "test", "test"
                )
                for id in TEST_IDS
            )
        else:
            diagnose(Path(__file__).resolve().parents[1], profile, os.environ, checks)
    except Exception:
        checks.append(Check("INTERNAL", NC, "Diagnosis indeterminate; seek Lead review."))
        observed = {check.id for check in checks}
        for id in ("PLATFORM", "PYTHON", "UV", "GIT", "CHECKOUT", "MANIFESTS"):
            if id not in observed:
                checks.append(Check(id, NC, "Diagnosis interrupted; prerequisite not checked."))
        for id in TEST_IDS:
            if id not in observed:
                checks.append(
                    Check(
                        id,
                        NC,
                        "Diagnosis interrupted; Test probe not checked.",
                        profile == "test",
                        "test",
                    )
                )
    checks.append(
        Check(
            "DB_RUNTIME",
            NC,
            "PostgreSQL identity, SQL, ownership, ports and health not queried.",
            False,
            "excluded",
        )
    )
    return render(profile, checks)


if __name__ == "__main__":
    raise SystemExit(main())
