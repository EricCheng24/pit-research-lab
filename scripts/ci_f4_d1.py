"""Prepare and reconcile the fixed F4-D1 targets on the PostgreSQL Actions runner."""

import contextlib
import fcntl
import hashlib
import importlib
import importlib.util
import json
import os
import platform
import pwd
import re
import secrets
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

REPO = "EricCheng24/pit-research-lab"
JOB = "postgres-integration"
WORKFLOW = ".github/workflows/ci.yml"
HELPER = "scripts/ci_f4_d1.py"
VERBS = ("preflight", "arm-legacy", "prepare", "run", "cleanup", "cleanup-legacy")
CLEANUP = {"cleanup", "cleanup-legacy"}
NORMAL_SECONDS = 870
F4_CLEANUP_SECONDS = 225
LEGACY_CLEANUP_SECONDS = 75
# The workflow sends TERM after reserving at least 4s. Finish inner supervision first.
INNER_HEADROOM_SECONDS = 5
_step_interrupted = False
_defer_interrupt = False
REDACTION = "--tb=no --show-capture=no"
PINS = {
    "scripts/database.py": "7b9b8cb7e1a29449b690a207ceb29e7993bcfee0",
    "compose.test.yaml": "a4c4c4ea1a4fad95971bd2ad063261c2b0a6d6ff",
    "scripts/init-postgres.sh": "3f18dbc5672a6c43a0c4b5f673391fcc0996b348",
    "src/pit_research_lab/infrastructure/database/config.py": (
        "2904d8dd26db6d2bb95fc562ba9ea701cf27bcb3"
    ),
    "src/pit_research_lab/infrastructure/database/engine.py": (
        "a85d626470ba828d2ef0290872071bff85cf1805"
    ),
}
BOOTSTRAP = "scripts/init-postgres.sh"
BOOTSTRAP_SHA = "2b8bb32bba7820db0b4e11c2e8c40d24477ffde62fb9933751033d4b900a8aeb"
DEST = "/docker-entrypoint-initdb.d/10-pitlab.sh"
PGDATA = "/var/lib/postgresql/data"
IMAGE = (
    "postgres:17.11-bookworm@"
    "sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826"
)
IMAGE_DIGEST = IMAGE.split("@", 1)[1]
DOCKER_SOCKET_PATH = Path("/var/run/docker.sock")
# Engine 28.0 supports v1.24–v1.48. Pull resolves the same repository and digest
# as this digest-only lookup, without depending on a local tag association.
IMAGE_API_MINOR = 44
IMAGE_LOOKUP = f"postgres@{IMAGE_DIGEST}"
IMAGE_HEADER_LIMIT = 8192
IMAGE_BODY_LIMIT = 256 * 1024
IMAGE_ERROR_LIMIT = 8192
IMAGE_CHUNK_LIMIT = 1024
FIXTURE_DIR = "tests/fixtures/mvp_f4_d1"
FIXTURES = (
    (
        "fixture-issuer-v1",
        "issuer_fixture.csv",
        "50b453473883d39aa01f1a296d3e8bd70b2a7e7c7fef5364dc340168038aa08f",
        246,
        (3, 2, 0, 1),
    ),
    (
        "fixture-revenue-v1",
        "revenue_fixture.csv",
        "3d947924e75b615e6d536c202f7092514b362466ff8b70e7f0718e16f80b8305",
        465,
        (4, 3, 0, 1),
    ),
)
UNITS = {
    "legacy": ("", 55432, 55433),
    "independent": ("s", 56321, 56322),
    "integration": ("i", 56323, 56324),
    "restoration": ("r", 56325, 56326),
}
F4_UNITS = tuple(UNITS)[1:]
F4_NODE = "tests/integration/database/test_f4_d1_foundation.py::test_f4_d1_foundation"
NODE_COUNT = 84
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
PROBE_LABEL = "io.pitlab.ci-f4.bootstrap"
PROBE_SCRIPT = (
    f'p={DEST}; uid=$(id -u) && [ "$uid" -gt 0 ] || exit 41; '
    '[ -f "$p" ] && [ -r "$p" ] || exit 42; sha256sum -- "$p" || exit 43'
)
MAX_OUTPUT = 2 * 1024 * 1024
DESCRIPTOR = "integration-descriptor.json"


class Refusal(RuntimeError):
    """Carries only a fixed, safe status code."""


def require(condition, code):
    if not condition:
        raise Refusal(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def unique_object(pairs):
    value = dict(pairs)
    require(len(value) == len(pairs), "DUPLICATE_JSON_KEY")
    return value


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def image_http_line(stream, limit):
    line = stream.readline(limit + 1)
    require(len(line) <= limit, "IMAGE_HTTP_LIMIT")
    require(line.endswith(b"\r\n"), "IMAGE_HTTP_FRAMING")
    return line[:-2]


def image_http_headers(stream):
    status_line = image_http_line(stream, IMAGE_HEADER_LIMIT)
    status = re.fullmatch(rb"HTTP/1\.1 ([1-5][0-9]{2}) [ -~]*", status_line)
    require(status is not None, "IMAGE_HTTP_FRAMING")
    remaining = IMAGE_HEADER_LIMIT - len(status_line) - 2
    headers = {}
    while True:
        line = image_http_line(stream, remaining)
        remaining -= len(line) + 2
        if not line:
            return int(status[1]), headers
        field = re.fullmatch(rb"([!#$%&'*+.^_`|~0-9A-Za-z-]+):([\t -~]*)", line)
        require(field is not None, "IMAGE_HTTP_FRAMING")
        name = field[1].lower()
        require(name not in headers, "IMAGE_HTTP_FRAMING")
        headers[name] = field[2].strip()


def image_http_body(stream, headers, limit):
    size = headers.get(b"content-length")
    transfer = headers.get(b"transfer-encoding")
    require(
        (size is None) != (transfer is None) and b"trailer" not in headers, "IMAGE_HTTP_FRAMING"
    )
    if size is not None:
        require(re.fullmatch(rb"[0-9]{1,10}", size), "IMAGE_HTTP_FRAMING")
        length = int(size)
        require(length <= limit, "IMAGE_HTTP_LIMIT")
        body = stream.read(length)
        require(len(body) == length, "IMAGE_HTTP_FRAMING")
    else:
        require(transfer.lower() == b"chunked", "IMAGE_HTTP_FRAMING")
        body = bytearray()
        for _ in range(IMAGE_CHUNK_LIMIT):
            chunk_size = image_http_line(stream, 10)
            require(re.fullmatch(rb"[0-9a-fA-F]{1,8}", chunk_size), "IMAGE_HTTP_FRAMING")
            length = int(chunk_size, 16)
            if not length:
                require(stream.read(2) == b"\r\n", "IMAGE_HTTP_FRAMING")
                break
            require(len(body) + length <= limit, "IMAGE_HTTP_LIMIT")
            chunk = stream.read(length)
            require(len(chunk) == length and stream.read(2) == b"\r\n", "IMAGE_HTTP_FRAMING")
            body.extend(chunk)
        else:
            raise Refusal("IMAGE_HTTP_LIMIT")
    # Connection: close makes surplus bytes and truncated framing distinguishable.
    require(not stream.read(1), "IMAGE_HTTP_FRAMING")
    return body


def reject_image_json_constant(_value):
    raise Refusal("IMAGE_JSON")


def image_http_response(stream):
    status, headers = image_http_headers(stream)
    if status == 400:
        # The version middleware also uses 400 for an unsupported client API.
        raise Refusal("IMAGE_API_REJECTED")
    require(status in (200, 404), "IMAGE_HTTP_STATUS")
    # Engine 28's generic JSON 404 bypasses the registered-route middleware.
    # Only the latter supplies these Docker version and platform headers.
    version = re.fullmatch(rb"([1-9][0-9]{0,2})\.([0-9]{1,3})", headers.get(b"api-version", b""))
    require(
        version is not None
        and headers.get(b"ostype") == b"linux"
        and re.fullmatch(rb"Docker/[A-Za-z0-9.+-]+ \(linux\)", headers.get(b"server", b"")),
        "IMAGE_API_ROUTE",
    )
    require(int(version[1]) == 1 and int(version[2]) >= IMAGE_API_MINOR, "IMAGE_API_UNSUPPORTED")
    require(
        re.fullmatch(
            rb"application/json(?:;[ \t]*charset=utf-8)?", headers.get(b"content-type", b"").lower()
        )
        and b"content-encoding" not in headers,
        "IMAGE_HTTP_CONTENT",
    )
    body = image_http_body(
        stream, headers, IMAGE_ERROR_LIMIT if status == 404 else IMAGE_BODY_LIMIT
    )
    try:
        result = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_image_json_constant,
        )
    except (ValueError, RecursionError):
        raise Refusal("IMAGE_JSON") from None
    return status, result


def require_image_socket(binding):
    try:
        info = DOCKER_SOCKET_PATH.lstat()
    except OSError:
        raise Refusal("DOCKER_SOCKET_REPLACED") from None
    require(
        stat.S_ISSOCK(info.st_mode) and [info.st_dev, info.st_ino] == binding,
        "DOCKER_SOCKET_REPLACED",
    )


def uptime():
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def stamp(info):
    return [
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ]


def canonical_directory(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, "UNSAFE_DIRECTORY")
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid(), "DIRECTORY_OWNER")
    return info


@contextlib.contextmanager
def directory_fd(path, *, private=True):
    info = canonical_directory(path)
    require(not private or stat.S_IMODE(info.st_mode) == 0o700, "DIRECTORY_MODE")
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(os.path.samestat(info, os.fstat(descriptor)), "DIRECTORY_REPLACED")
        yield descriptor
        final = canonical_directory(path)
        require(
            os.path.samestat(info, final) and final.st_mode == info.st_mode,
            "DIRECTORY_REPLACED",
        )
    finally:
        os.close(descriptor)


def mkdir(path, *, private_parent=True):
    with directory_fd(path.parent, private=private_parent) as parent:
        os.mkdir(path.name, mode=0o700, dir_fd=parent)
        os.fsync(parent)
    with directory_fd(path):
        pass


def regular(info, mode):
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_uid == os.geteuid()
        and info.st_nlink == 1
        and stat.S_IMODE(info.st_mode) == mode
    )


def read_bound(path, mode=0o600, limit=MAX_OUTPUT, *, private_parent=True):
    with directory_fd(path.parent, private=private_parent) as parent:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(path.name, flags, dir_fd=parent), "rb") as file:
            info = os.fstat(file.fileno())
            require(regular(info, mode) and info.st_size <= limit, "UNSAFE_FILE")
            raw = file.read(limit + 1)
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            require(
                len(raw) == info.st_size
                and stamp(info) == stamp(current) == stamp(os.fstat(file.fileno())),
                "FILE_REPLACED",
            )
    return raw, stamp(info)


def write_new(path, raw, mode=0o600):
    with directory_fd(path.parent) as parent:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        with os.fdopen(os.open(path.name, flags, 0o600, dir_fd=parent), "wb") as file:
            require(regular(os.fstat(file.fileno()), 0o600), "UNSAFE_NEW_FILE")
            file.write(raw)
            file.flush()
            if mode != 0o600:
                require(path.name == Path(BOOTSTRAP).name and mode == 0o644, "UNSAFE_MODE")
                os.fchmod(file.fileno(), mode)
            os.fsync(file.fileno())
            binding = stamp(os.fstat(file.fileno()))
        os.fsync(parent)
    require(read_bound(path, mode) == (raw, binding), "NEW_FILE_REPLACED")
    return binding


def quiet_kill(pid, sig, *, group):
    with contextlib.suppress(ProcessLookupError):
        if group:
            os.killpg(pid, sig)
        else:
            os.kill(pid, sig)


@contextlib.contextmanager
def defer_interruption():
    """Latch TERM/INT during child registration and exact-group termination."""
    global _defer_interrupt
    previous = _defer_interrupt
    _defer_interrupt = True
    try:
        yield
    finally:
        _defer_interrupt = previous


def stop_process(proc, *, group):
    if proc.returncode is not None:
        return
    # Keep the leader's PID reserved until signalling its exact group is done.
    quiet_kill(proc.pid, signal.SIGTERM, group=group)
    time.sleep(0.2)
    quiet_kill(proc.pid, signal.SIGKILL, group=group)
    try:
        proc.wait(timeout=0.3)
    except subprocess.TimeoutExpired:
        raise Refusal("COMMAND_REAP_UNCERTAIN") from None


def worker_exited(pid):
    return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None


def stop_worker(pid):
    quiet_kill(pid, signal.SIGTERM, group=True)
    time.sleep(0.2)
    quiet_kill(pid, signal.SIGKILL, group=True)
    # The fork may have been interrupted before the child called setsid().
    quiet_kill(pid, signal.SIGKILL, group=False)
    quiet_kill(pid, signal.SIGKILL, group=True)
    expiry = time.monotonic() + 0.3
    while not worker_exited(pid):
        require(time.monotonic() < expiry, "WORKER_REAP_UNCERTAIN")
        time.sleep(0.01)
    os.waitpid(pid, 0)


@dataclass(frozen=True)
class JobContext:
    workspace: Path
    private: Path
    sha: str
    workflow_sha: str
    ref: str
    parents: tuple[str, ...] | None
    key: str
    legacy_key: str
    started: int


def event_parents(env, payload):
    ref, commit = env["GITHUB_REF"], env["GITHUB_SHA"]
    require(payload["repository"]["full_name"] == REPO, "EVENT_REPOSITORY")
    if env["GITHUB_EVENT_NAME"] == "push":
        require(
            ref == "refs/heads/main" and payload["ref"] == ref and payload["after"] == commit,
            "PUSH_IDENTITY",
        )
        return None
    number = re.fullmatch(r"refs/pull/([1-9][0-9]{0,11})/merge", ref)
    require(env["GITHUB_EVENT_NAME"] == "pull_request" and number, "PR_REF")
    pr = payload["pull_request"]
    base, head = pr["base"], pr["head"]
    require(
        type(payload["number"]) is int
        and payload["number"] == int(number[1])
        and base["ref"] == "main"
        and base["repo"]["full_name"] == REPO
        and all(HEX40.fullmatch(side["sha"]) and side["sha"] != commit for side in (base, head))
        and base["sha"] != head["sha"],
        "PR_IDENTITY",
    )
    return base["sha"], head["sha"]


def admit(env):
    expected = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_JOB": JOB,
        "GITHUB_WORKFLOW": "CI",
        "PYTEST_ADDOPTS": REDACTION,
    }
    require(all(env.get(key) == value for key, value in expected.items()), "HOSTED_CONTEXT")
    release = platform.release().lower()
    require(
        os.geteuid() != 0
        and platform.system() == "Linux"
        and platform.machine() == "x86_64"
        and "microsoft" not in release
        and "wsl" not in release
        and not any(key.startswith("WSL") for key in env),
        "NATIVE_NONROOT_LINUX",
    )
    os_release = platform.freedesktop_os_release()
    require(
        (os_release.get("ID"), os_release.get("VERSION_ID")) == ("ubuntu", "24.04"),
        "UBUNTU_VERSION",
    )
    forbidden = {
        "ENV",
        "BASH_ENV",
        "LD_PRELOAD",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
        "GIT_REPLACE_REF_BASE",
        "GIT_EXEC_PATH",
        "GIT_CONFIG",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_GLOBAL",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
        "PYTHONINSPECT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
        "UV_PROJECT_ENVIRONMENT",
    }
    require(
        not any(
            key in forbidden
            or key.startswith(("DOCKER_", "PG", "COMPOSE_", "PITLAB_", "GIT_CONFIG_"))
            or key.startswith("F4_D1_")
            or (key.startswith("PYTEST_") and key != "PYTEST_ADDOPTS")
            for key in env
        ),
        "AMBIENT_OVERRIDE",
    )
    require(
        re.fullmatch(r"[1-9][0-9]{0,19}", env["GITHUB_RUN_ID"])
        and re.fullmatch(r"[1-9][0-9]{0,8}", env["GITHUB_RUN_ATTEMPT"])
        and HEX40.fullmatch(env["GITHUB_SHA"])
        and HEX40.fullmatch(env["GITHUB_WORKFLOW_SHA"])
        and re.fullmatch(r"[0-9]{1,12}", env["F4_CI_STARTED"]),
        "RUN_METADATA",
    )
    started = int(env["F4_CI_STARTED"])
    require(0 <= uptime() - started < 1201, "ATTEMPT_CLOCK")
    workspace, temp = (Path(env[key]) for key in ("GITHUB_WORKSPACE", "RUNNER_TEMP"))
    canonical_directory(workspace)
    canonical_directory(temp)
    require(
        workspace == Path.cwd() == Path(__file__).resolve().parents[1]
        and temp != workspace
        and not temp.is_relative_to(workspace)
        and not workspace.is_relative_to(temp),
        "JOB_PATHS",
    )
    ref = env["GITHUB_REF"]
    require(
        env["GITHUB_WORKFLOW_REF"] == f"{REPO}/{WORKFLOW}@{ref}",
        "WORKFLOW_REF",
    )
    event = Path(env["GITHUB_EVENT_PATH"])
    require(
        event == temp / "_github_workflow" / "event.json" and event.resolve() == event,
        "EVENT_PATH",
    )
    info = event.lstat()
    require(
        regular(info, stat.S_IMODE(info.st_mode)) and info.st_size <= MAX_OUTPUT,
        "EVENT_FILE",
    )
    parents = event_parents(env, decode(event.read_bytes()))
    legacy_key = f"{env['GITHUB_RUN_ID']}:{env['GITHUB_RUN_ATTEMPT']}"
    key = f"{REPO}:{JOB}:{legacy_key}"
    return JobContext(
        workspace,
        temp / f"pitlab-ci-f4-{sha(key.encode())[:24]}",
        env["GITHUB_SHA"],
        env["GITHUB_WORKFLOW_SHA"],
        ref,
        parents,
        key,
        legacy_key,
        started,
    )


@dataclass(frozen=True)
class Unit:
    name: str
    root: Path
    namespace: str
    dev: int
    test: int

    @property
    def project(self):
        return f"pitlab-{self.namespace}-test"

    @property
    def bootstrap(self):
        return self.root / BOOTSTRAP

    @property
    def custody(self):
        return self.root / "custody"


def units_for(ctx):
    units = {}
    for name, (tag, dev, test) in UNITS.items():
        if name == "legacy":
            root = ctx.workspace
            namespace = "ci" + sha(ctx.legacy_key.encode())[:18]
        else:
            root = ctx.private / name
            namespace = f"f4d1{tag}" + sha(f"{ctx.key}:{name}".encode())[:15]
        units[name] = Unit(name, root, namespace, dev, test)
    require(
        len({unit.namespace for unit in units.values()}) == 4
        and len({unit.root for unit in units.values()}) == 4
        and len({port for unit in units.values() for port in (unit.dev, unit.test)}) == 8,
        "UNIT_COLLISION",
    )
    return units


class Journal:
    """Separate append-only, hash-linked histories keep unrelated targets reconcilable."""

    def __init__(self, root, identity):
        self.root = root
        self.identity = identity
        self.bindings = {}

    def create(self):
        mkdir(self.root, private_parent=False)
        self.bindings["lock"] = write_new(self.root / "job.lock", b"")[:2]
        for name in ("job", *UNITS):
            leaf = self.root / f"{name}.jsonl"
            binding = write_new(leaf, b"")
            self.bindings[name] = binding[:2]
            self.record(name, "planned", self.identity)
        write_new(self.root / "identity.json", encode([self.identity, self.bindings]))

    def open(self):
        identity, bindings = decode(read_bound(self.root / "identity.json")[0])
        require(
            identity == self.identity and set(bindings) == {"job", "lock", *UNITS}, "STALE_JOURNAL"
        )
        self.bindings = bindings

    @contextlib.contextmanager
    def lock(self):
        with directory_fd(self.root) as parent:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            with os.fdopen(os.open("job.lock", flags, dir_fd=parent), "rb") as file:
                info = os.fstat(file.fileno())
                require(
                    regular(info, 0o600) and stamp(info)[:2] == self.bindings["lock"], "UNSAFE_LOCK"
                )
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    current = os.stat("job.lock", dir_fd=parent, follow_symlinks=False)
                    require(stamp(info) == stamp(current), "LOCK_REPLACED")

    def read(self, name):
        leaf = self.root / f"{name}.jsonl"
        raw, binding = read_bound(leaf, limit=128 * 1024)
        require(binding[:2] == self.bindings[name], "JOURNAL_REPLACED")
        require(raw.endswith(b"\n") and raw, "TRUNCATED_JOURNAL")
        rows = raw.splitlines()
        with directory_fd(self.root) as parent:
            seals = {leaf for leaf in os.listdir(parent) if leaf.startswith(f"{name}.seal.")}
        require(
            seals == {f"{name}.seal.{index}" for index in range(len(rows))},
            "JOURNAL_INCOMPLETE",
        )
        records = {}
        predecessor = "0" * 64
        for index, line in enumerate(rows):
            seq, previous, event, data = decode(line)
            require(
                seq == index
                and previous == predecessor
                and event not in records
                and line == encode([seq, previous, event, data]),
                "INVALID_JOURNAL_CHAIN",
            )
            records[event] = data
            predecessor = sha(line)
            seal = read_bound(self.root / f"{name}.seal.{index}", limit=64)[0]
            require(seal == predecessor.encode(), "JOURNAL_SEAL")
        require(records.get("planned") == self.identity, "JOURNAL_IDENTITY")
        return records, predecessor, binding

    def events(self, name):
        return self.read(name)[0]

    def record(self, name, event, data=None):
        if event == "planned":
            records, previous, binding = {}, "0" * 64, read_bound(self.root / f"{name}.jsonl")[1]
        else:
            records, previous, binding = self.read(name)
        require(event not in records, "REPEATED_OPERATION")
        with directory_fd(self.root) as parent:
            flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(f"{name}.jsonl", flags, dir_fd=parent)
            try:
                require(stamp(os.fstat(fd)) == binding, "JOURNAL_REPLACED")
                line = encode([len(records), previous, event, data])
                write_new(self.root / f"{name}.seal.{len(records)}", sha(line).encode())
                raw = line + b"\n"
                require(os.write(fd, raw) == len(raw), "JOURNAL_WRITE")
                os.fsync(fd)
            finally:
                os.close(fd)


class HostedJob:
    def __init__(self, ctx, verb, home, *, phase_started=None):
        self.ctx = ctx
        self.units = units_for(ctx)
        self.env = {"HOME": home, "PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"}
        self.deadline = ctx.started + NORMAL_SECONDS
        if verb in CLEANUP:
            hard_end = self.deadline + F4_CLEANUP_SECONDS + LEGACY_CLEANUP_SECONDS
            if verb == "cleanup":
                hard_end -= LEGACY_CLEANUP_SECONDS
                phase_limit = F4_CLEANUP_SECONDS
            else:
                phase_limit = LEGACY_CLEANUP_SECONDS
            require(
                type(phase_started) is int and ctx.started <= phase_started <= uptime(),
                "INVALID_PHASE_ENTRY",
            )
            self.deadline = min(hard_end, phase_started + phase_limit)
        self.deadline -= INNER_HEADROOM_SECONDS
        self.in_worker = False

    def budget(self, limit):
        require(not _step_interrupted, "STEP_INTERRUPTED_UNCERTAIN")
        remaining = min(limit, self.deadline - uptime() - 0.6)
        require(remaining > 0, "DEADLINE_EXHAUSTED")
        return remaining

    def command(self, args, *, limit=15, env=None):
        expiry = time.monotonic() + self.budget(limit)
        private_group = not self.in_worker
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            proc = None
            try:
                with defer_interruption():
                    self.budget(limit)
                    proc = subprocess.Popen(
                        args,
                        cwd=self.ctx.workspace,
                        env=self.env if env is None else env,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        start_new_session=private_group,
                    )
                exit_code = proc.wait(timeout=self.budget(expiry - time.monotonic()))
            except BaseException as exc:
                if proc is not None:
                    with defer_interruption():
                        stop_process(proc, group=private_group)
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise Refusal("COMMAND_TIMEOUT_UNCERTAIN") from None
                raise
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(MAX_OUTPUT + 1), stderr.read(MAX_OUTPUT + 1)
            require(len(out) <= MAX_OUTPUT and len(err) <= MAX_OUTPUT, "COMMAND_OUTPUT_LIMIT")
            return exit_code, out, err

    def checked(self, args, *, limit=15, code="COMMAND_REFUSED"):
        exit_code, out, err = self.command(args, limit=limit)
        require(exit_code == 0 and not err, code)
        return out

    def git(self, *args):
        return self.checked(
            ["git", "--no-optional-locks", "--no-replace-objects", *args], code="GIT_REFUSED"
        )

    def clean(self):
        require(
            self.git("status", "--porcelain=v1", "--untracked-files=all") == b"",
            "CHECKOUT_DIRTY",
        )

    def checkout_file(self, rel, *, blob=None, limit=MAX_OUTPUT):
        record = self.git("ls-tree", "-z", self.ctx.sha, "--", rel)
        match = re.fullmatch(
            rb"100644 blob ([0-9a-f]{40})\t" + re.escape(rel.encode()) + rb"\0", record
        )
        require(match and (blob is None or match[1].decode() == blob), "COMMITTED_INPUT")
        raw, _ = read_bound(self.ctx.workspace / rel, 0o644, limit, private_parent=False)
        require(raw == self.git("cat-file", "blob", match[1].decode()), "CHECKOUT_INPUT")
        return raw

    def verify_checkout(self, verb):
        require(self.git("rev-parse", "--is-shallow-repository") == b"false\n", "SHALLOW_CHECKOUT")
        require(self.git("rev-parse", "HEAD").strip().decode() == self.ctx.sha, "CHECKOUT_SHA")
        if self.ctx.parents is not None:
            parents = self.git("show", "-s", "--format=%P", "HEAD").decode().split()
            require(tuple(parents) == self.ctx.parents, "PR_PARENTS")
        tree = self.git("rev-parse", "HEAD^{tree}").strip().decode()
        require(HEX40.fullmatch(tree), "CHECKOUT_TREE")
        if verb not in CLEANUP:
            self.clean()
        workflow = self.checkout_file(WORKFLOW)
        require(
            workflow == self.git("show", f"{self.ctx.workflow_sha}:{WORKFLOW}"),
            "WORKFLOW_CHECKOUT",
        )
        self.checkout_file(HELPER)
        self.f1_inputs = {rel: self.checkout_file(rel, blob=blob) for rel, blob in PINS.items()}
        raw = self.f1_inputs[BOOTSTRAP]
        require(len(raw) == 1773 and sha(raw) == BOOTSTRAP_SHA, "BOOTSTRAP_PIN")
        self.fixture_bytes = {}
        if verb not in CLEANUP:
            for _, name, digest, size, _ in FIXTURES:
                raw = self.checkout_file(f"{FIXTURE_DIR}/{name}", limit=size)
                require(len(raw) == size and sha(raw) == digest, "FIXTURE_PIN")
                self.fixture_bytes[name] = raw
        identity = {
            "key": self.ctx.key,
            "ref": self.ctx.ref,
            "sha": self.ctx.sha,
            "tree": tree,
            "workspace": str(self.ctx.workspace),
            "private": str(self.ctx.private),
            "started": self.ctx.started,
        }
        self.journal = Journal(self.ctx.private, identity)

    def load_modules(self, verb):
        prefix = "pit_research_lab."
        paths = [
            "infrastructure.database.config",
            "infrastructure.database.engine",
        ]
        if verb not in CLEANUP:
            paths.extend(f"mvp.f4.{mod}" for mod in ("d1_profile", "d1", "d1_store", "d1_backup"))
        packages = ["", "infrastructure", "infrastructure/database"]
        if verb not in CLEANUP:
            packages.extend(("mvp", "mvp/f4"))
        for package in packages:
            rel = f"src/pit_research_lab/{package + '/' if package else ''}__init__.py"
            self.checkout_file(rel)
        for name in paths:
            module = prefix + name
            rel = "src/" + module.replace(".", "/") + ".py"
            self.checkout_file(rel, blob=PINS.get(rel))
            expected = self.ctx.workspace / rel
            spec = importlib.util.find_spec(module)
            require(spec is not None and spec.origin == str(expected), "MODULE_ORIGIN")
            loaded = importlib.import_module(module)
            require(loaded.__file__ == str(expected), "MODULE_ORIGIN")
        spec = importlib.util.spec_from_file_location(
            "ci_f4_f1", self.ctx.workspace / "scripts/database.py"
        )
        self.f1 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.f1)
        from pit_research_lab.infrastructure.database import config

        require(config.IMAGE == IMAGE, "F1_IMAGE_PIN")
        self.config = config
        if verb not in CLEANUP:
            from pit_research_lab.mvp.f4 import d1_profile

            self.profile = d1_profile

    def worker(self, function, limit):
        """Run existing guarded functions or pytest in a bounded, private child group."""
        expiry = time.monotonic() + self.budget(limit)
        with tempfile.TemporaryFile() as result, open(os.devnull, "wb") as sink:
            sys.stdout.flush()
            sys.stderr.flush()
            pid = None
            reaped = False
            try:
                with defer_interruption():
                    self.budget(limit)
                    pid = os.fork()
                if pid == 0:
                    try:
                        os.setsid()
                        signal.signal(signal.SIGTERM, signal.SIG_DFL)
                        signal.signal(signal.SIGINT, signal.SIG_DFL)
                        os.dup2(sink.fileno(), 1)
                        os.dup2(sink.fileno(), 2)
                        self.in_worker = True
                        os.environ.clear()
                        os.environ.update(self.env)
                        try:
                            payload = ["ok", function()]
                        except Refusal as exc:
                            payload = ["failure", str(exc)]
                        except self.config.PersistenceError as exc:
                            code = (
                                "F1_TIMEOUT_UNCERTAIN"
                                if "unavailable/timed out" in str(exc)
                                else "F1_GUARD_REFUSED"
                            )
                            payload = ["failure", code]
                        except Exception:
                            payload = ["failure", "CHILD_OPERATION_REFUSED"]
                        result.write(encode(payload))
                        result.flush()
                        os._exit(0)
                    except BaseException:
                        os._exit(125)
                while not worker_exited(pid):
                    require(not _step_interrupted, "STEP_INTERRUPTED_UNCERTAIN")
                    require(time.monotonic() < expiry, "WORKER_TIMEOUT_UNCERTAIN")
                    time.sleep(0.02)
                with defer_interruption():
                    # An exited leader can still have descendants in its session.
                    quiet_kill(pid, signal.SIGKILL, group=True)
                    _, status = os.waitpid(pid, 0)
                    reaped = True
                require(not _step_interrupted, "STEP_INTERRUPTED_UNCERTAIN")
                require(os.waitstatus_to_exitcode(status) == 0, "WORKER_EXIT_UNCERTAIN")
            finally:
                if pid and not reaped:
                    with defer_interruption():
                        stop_worker(pid)
            result.seek(0)
            raw = result.read(MAX_OUTPUT + 1)
            require(len(raw) <= MAX_OUTPUT, "WORKER_OUTPUT_LIMIT")
            status, payload = decode(raw)
            if status == "failure":
                require(re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", payload), "WORKER_FAILURE")
                raise Refusal(payload)
            require(status == "ok", "WORKER_FAILURE")
            return payload

    def docker(self, *args, limit=15):
        return self.checked(["docker", *args], limit=limit, code="DOCKER_REFUSED")

    def endpoint(self):
        require(self.docker("context", "show") == b"default\n", "DOCKER_CONTEXT")
        require(
            self.docker("context", "inspect", "--format", "{{.Endpoints.docker.Host}}", "default")
            == b"unix:///var/run/docker.sock\n",
            "DOCKER_ENDPOINT",
        )
        info = Path("/var/run/docker.sock").stat()
        require(stat.S_ISSOCK(info.st_mode), "DOCKER_SOCKET")
        return [info.st_dev, info.st_ino]

    def inspect_image(self, endpoint, allow_missing):
        request = (
            f"GET /v1.{IMAGE_API_MINOR}/images/{quote(IMAGE_LOOKUP, safe='')}/json HTTP/1.1\r\n"
            "Host: docker\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(self.budget(15))
                require_image_socket(endpoint)
                try:
                    conn.connect(str(DOCKER_SOCKET_PATH))
                    conn.sendall(request)
                    with conn.makefile("rb") as stream:
                        status, data = image_http_response(stream)
                finally:
                    require_image_socket(endpoint)
        except TimeoutError:
            raise Refusal("IMAGE_IO_TIMEOUT") from None
        except OSError:
            raise Refusal("IMAGE_IO_REFUSED") from None

        if status == 404:
            require(
                isinstance(data, dict)
                and data.keys() == {"message"}
                and isinstance(data["message"], str)
                and bool(data["message"].strip()),
                "IMAGE_ERROR_ENVELOPE",
            )
            require(allow_missing, "IMAGE_MISSING")
            return None
        require(isinstance(data, dict) and isinstance(data.get("Config"), dict), "IMAGE_JSON_SHAPE")
        config = data["Config"]
        ident, digests = data.get("Id"), data.get("RepoDigests")
        volumes, labels = config.get("Volumes"), config.get("Labels")
        require(
            isinstance(ident, str)
            and IMAGE_ID.fullmatch(ident)
            and data.get("Os") == "linux"
            and data.get("Architecture") == "amd64"
            and type(digests) is list
            and all(isinstance(ref, str) for ref in digests)
            and any(
                f"{name}@{IMAGE_DIGEST}" in digests
                for name in ("postgres", "library/postgres", "docker.io/library/postgres")
            )
            and volumes == {PGDATA: {}}
            and "Labels" in config
            and (
                labels is None
                or (isinstance(labels, dict) and all(isinstance(v, str) for v in labels.values()))
            ),
            "IMAGE_IDENTITY",
        )
        return {"id": ident, "labels": labels or {}}

    def image(self, endpoint, *, allow_missing=False):
        return self.worker(lambda: self.inspect_image(endpoint, allow_missing), 15)

    def verify_image_socket(self, *, bind=False):
        events = self.journal.events("job")
        require(self.endpoint() == events["socket"], "DOCKER_SOCKET_REPLACED")
        image = self.image(events["socket"])
        previous = events.get("image") or events.get("cached-image")
        require(previous is None or image["id"] == previous, "IMAGE_REPLACED")
        if bind and "image" not in events:
            require(previous is not None or "pull-intent" in events, "IMAGE_NOT_PLANNED")
            self.journal.record("job", "image", image["id"])
        return image

    def scoped_absent(self, project, *, target="test"):
        label = f"label=com.docker.compose.project={project}"
        selectors = (
            (("container", "ls", "-a", "-q"), f"name=^/{project}-postgres_{target}-1$"),
            (("volume", "ls", "-q"), f"name=^{project}_pgdata_{target}$"),
            (("network", "ls", "-q"), f"name=^{project}_default$"),
        )
        for command, name in selectors:
            for selector in (label, name):
                require(not self.docker(*command, "--filter", selector), "PROJECT_PREEXISTS")
        for selector in (f"volume={project}_pgdata_{target}", f"network={project}_default"):
            require(
                not self.docker("container", "ls", "-a", "-q", "--filter", selector),
                "PROJECT_CONSUMER_EXISTS",
            )

    def initial_ports(self):
        listeners = self.checked(["ss", "-H", "-ltn"], code="LISTENER_PROOF")
        published = self.docker("ps", "--format", "{{.ID}} {{.Ports}}")
        for unit in self.units.values():
            for port in (unit.dev, unit.test):
                require(
                    not re.search(rb"[:.]" + str(port).encode() + rb"\s", listeners)
                    and not re.search(rb":" + str(port).encode() + rb"->", published),
                    "PORT_CONFLICT",
                )
                try:
                    with socket.socket() as probe:
                        probe.bind(("127.0.0.1", port))
                except OSError:
                    raise Refusal("PORT_BIND_REFUSED") from None

    def preflight(self):
        for name in (".env.dev.local", ".env.test.local"):
            path = self.ctx.workspace / name
            require(not os.path.lexists(path), "LEGACY_CONFIG_PREEXISTS")
            self.git("check-ignore", "-q", "--", name)
        endpoint = self.endpoint()
        require(self.docker("info", "--format", "{{.ServerVersion}}").strip(), "DOCKER_SERVER")
        version = self.docker("compose", "version", "--short").strip()
        require(re.fullmatch(rb"v?2\.[0-9]+\.[0-9]+[^\s]*", version), "COMPOSE_V2")
        self.initial_ports()
        for unit in self.units.values():
            self.scoped_absent(unit.project)
            self.scoped_absent(f"pitlab-{unit.namespace}-dev", target="dev")
            self.journal.record(unit.name, "initial-absence")
        self.journal.record("job", "socket", endpoint)
        self.journal.record("legacy", "setup-intent")
        image = self.image(endpoint, allow_missing=True)
        if image is None:
            self.journal.record("job", "pull-intent")
            return "IMAGE_ACQUISITION_REQUIRED"
        self.journal.record("job", "cached-image", image["id"])
        return "IMAGE_PRESENT"

    def bootstrap(self, unit):
        private = unit.name != "legacy"
        if private:
            with directory_fd(unit.root):
                pass
        raw, binding = read_bound(unit.bootstrap, 0o644, 1773, private_parent=private)
        require(len(raw) == 1773 and sha(raw) == BOOTSTRAP_SHA, "BOOTSTRAP_CHANGED")
        compose, compose_binding = read_bound(
            unit.root / "compose.test.yaml",
            0o600 if private else 0o644,
            private_parent=private,
        )
        require(compose == self.f1_inputs["compose.test.yaml"], "COMPOSE_CHANGED")
        return [binding, compose_binding]

    def configs(self, unit, recorded=None):
        private = unit.name != "legacy"
        bindings = []
        configs = []
        for target in ("dev", "test"):
            leaf = unit.root / f".env.{target}.local"
            raw, binding = read_bound(leaf, limit=8192, private_parent=private)
            cfg = self.config.load_config(target, unit.root)
            require(
                read_bound(leaf, limit=8192, private_parent=private) == (raw, binding),
                "CONFIG_REPLACED",
            )
            configs.append(cfg)
            bindings.append([sha(raw), binding, cfg.instance_id])
        dev, test = configs
        require(
            (dev.namespace, test.namespace) == (unit.namespace, unit.namespace)
            and (dev.port, dev.peer_port, test.port, test.peer_port)
            == (unit.dev, unit.test, unit.test, unit.dev)
            and dev.instance_id != test.instance_id
            and len(
                {
                    dev.admin_password,
                    dev.migrator_password,
                    dev.app_password,
                    test.admin_password,
                    test.migrator_password,
                    test.app_password,
                }
            )
            == 6,
            "CONFIG_IDENTITY",
        )
        identity = {"configs": bindings, "bootstrap": self.bootstrap(unit)}
        require(recorded is None or identity == recorded, "TARGET_INPUT_REPLACED")
        return dev, test, identity

    def f1_preflight(self, unit, *, fresh=False, running=False, ports=True, known=None):
        self.verify_image_socket()
        events = self.journal.events(unit.name)
        arm = events["config"]
        image = self.journal.events("job")["image"]

        def check():
            dev, test, _ = self.configs(unit, arm)
            env, resources = self.f1.preflight(test, unit.root, ports=ports)
            containers, volumes, networks = resources
            if fresh:
                require(not any(resources), "PROJECT_PREEXISTS")
                self.f1.check_ports(dev, [], env)
            if running:
                require(
                    len(containers) == len(volumes) == len(networks) == 1
                    and containers[0]["Running"] is True,
                    "TARGET_NOT_RUNNING",
                )
                self.f1.lifecycle("probe", test, unit.root)
                self.f1.check_ports(dev, [], env)
            result = {
                "container": None,
                "network": None,
                "volume": None,
            }
            if containers:
                container = containers[0]
                ident = container["Id"]
                require(HEX64.fullmatch(ident), "CONTAINER_ID")
                binds = [mount for mount in container["Mounts"] if mount["Type"] == "bind"]
                require(
                    len(binds) == 1 and binds[0]["Source"] == str(unit.bootstrap),
                    "DATABASE_BIND_SOURCE",
                )
                observed = (
                    self.docker("inspect", "--type", "container", "--format", "{{.Image}}", ident)
                    .strip()
                    .decode()
                )
                require(observed == image, "DATABASE_IMAGE_ID")
                if not running and container["Running"]:
                    self.f1.lifecycle("probe", test, unit.root)
                result["container"] = ident
            if networks:
                ident = networks[0]["Id"]
                require(HEX64.fullmatch(ident), "NETWORK_ID")
                result["network"] = ident
            if volumes:
                volume = volumes[0]
                require(
                    volume["Driver"] == "local" and isinstance(volume.get("CreatedAt"), str),
                    "VOLUME_IDENTITY",
                )
                result["volume"] = [volume["Name"], volume["CreatedAt"]]
            if known is not None:
                require(
                    all(value is None or known[k] == value for k, value in result.items())
                    if not running
                    else result == known,
                    "TARGET_ID_CHANGED",
                )
            return result

        return self.worker(check, 55 if running or fresh else 30)

    def life(self, unit, action, limit):
        self.verify_image_socket()
        binding = self.journal.events(unit.name)["config"]

        def lifecycle():
            _, test, _ = self.configs(unit, binding)
            self.f1.lifecycle(action, test, unit.root)

        self.worker(lifecycle, limit)

    def probe_ids(self, name, ident=None):
        selectors = [f"name=^/{name}$", f"label={PROBE_LABEL}={name}"]
        if ident is not None:
            require(HEX64.fullmatch(ident), "PROBE_ID")
            selectors.append(f"id={ident}")
        rows = [
            self.docker("container", "ls", "-a", "-q", "--no-trunc", "--filter", selector)
            .decode()
            .splitlines()
            for selector in selectors
        ]
        require(
            all(row == rows[0] for row in rows)
            and len(rows[0]) <= 1
            and all(HEX64.fullmatch(item) for item in rows[0])
            and (ident is None or not rows[0] or rows[0] == [ident]),
            "PROBE_OWNERSHIP",
        )
        return rows[0][0] if rows[0] else None

    def inspect_probe(self, unit, name, ident, image):
        raw = self.docker(
            "container",
            "inspect",
            "--format",
            "[{{json .Id}},{{json .Name}},{{json .Image}},{{json .Config}},"
            "{{json .HostConfig}},{{json .Mounts}},{{json .State.Status}},"
            "{{json .NetworkSettings.Networks}}]",
            ident,
        )
        got_id, got_name, got_image, config, host, mounts, status, networks = decode(raw)
        expected_labels = image["labels"] | {PROBE_LABEL: name}
        require(
            (got_id, got_name, got_image) == (ident, f"/{name}", image["id"])
            and config["Image"] == IMAGE
            and config["Labels"] == expected_labels
            and config["Entrypoint"] == ["/bin/sh"]
            and config["Cmd"] == ["-c", PROBE_SCRIPT]
            and config["User"] == "postgres"
            and config["Healthcheck"]["Test"] == ["NONE"]
            and not (config["Tty"] or config["OpenStdin"])
            and host["NetworkMode"] == "none"
            and host["ReadonlyRootfs"] is True
            and host["AutoRemove"] is True
            and host["Privileged"] is False
            and host["CapDrop"] == ["ALL"]
            and host["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges=true"])
            and host["RestartPolicy"]["Name"] in {"", "no"}
            and set(networks or {}) <= {"none"}
            and not any(
                host.get(key)
                for key in (
                    "Binds",
                    "Tmpfs",
                    "PortBindings",
                    "PublishAllPorts",
                    "VolumesFrom",
                    "CapAdd",
                    "Devices",
                    "DeviceRequests",
                    "Links",
                )
            ),
            "PROBE_SPEC",
        )
        configured = host["Mounts"]
        require(len(configured) == 2, "PROBE_MOUNT_COUNT")
        by_type = {mount["Type"]: mount for mount in configured}
        require(set(by_type) == {"bind", "tmpfs"}, "PROBE_MOUNT_TYPE")
        bind, tmp = (by_type[key] for key in ("bind", "tmpfs"))
        require(
            bind["Source"] == str(unit.bootstrap)
            and bind["Target"] == DEST
            and bind["ReadOnly"] is True
            and tmp["Target"] == PGDATA
            and not tmp.get("Source")
            and tmp["TmpfsOptions"]["SizeBytes"] == 1048576
            and tmp["TmpfsOptions"]["Mode"] == 0o700,
            "PROBE_MOUNT_SPEC",
        )
        real_binds = [mount for mount in mounts if mount["Type"] == "bind"]
        require(
            len(real_binds) == 1
            and len(mounts) <= 2
            and real_binds[0]["Source"] == str(unit.bootstrap)
            and real_binds[0]["Destination"] == DEST
            and real_binds[0]["RW"] is False
            and all(
                mount["Type"] == "bind"
                or (mount["Type"] == "tmpfs" and mount["Destination"] == PGDATA)
                for mount in mounts
            ),
            "PROBE_ACTUAL_MOUNTS",
        )
        return status

    def probe_bootstrap(self, unit):
        image = self.verify_image_socket()
        config = self.journal.events(unit.name)["config"]
        require(self.bootstrap(unit) == config["bootstrap"], "BOOTSTRAP_REPLACED")
        name = f"pitlab-ci-{unit.namespace}-probe-{secrets.token_hex(8)}"
        require(self.probe_ids(name) is None, "PROBE_PREEXISTS")
        self.journal.record(unit.name, "probe-create-intent", name)
        ident = (
            self.docker(
                "container",
                "create",
                "--name",
                name,
                "--label",
                f"{PROBE_LABEL}={name}",
                "--rm",
                "--pull=never",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--no-healthcheck",
                "--user",
                "postgres",
                "--mount",
                f"type=bind,source={unit.bootstrap},target={DEST},readonly",
                "--mount",
                f"type=tmpfs,target={PGDATA},tmpfs-size=1048576,tmpfs-mode=0700",
                "--entrypoint",
                "/bin/sh",
                IMAGE,
                "-c",
                PROBE_SCRIPT,
            )
            .strip()
            .decode()
        )
        require(HEX64.fullmatch(ident) and self.probe_ids(name, ident) == ident, "PROBE_ID")
        self.journal.record(unit.name, "probe-id", ident)
        require(self.inspect_probe(unit, name, ident, image) == "created", "PROBE_NOT_FRESH")
        require(self.bootstrap(unit) == config["bootstrap"], "BOOTSTRAP_REPLACED")
        self.verify_image_socket()
        self.journal.record(unit.name, "probe-start-intent")
        code, out, err = self.command(["docker", "container", "start", "--attach", ident], limit=25)
        self.journal.record(unit.name, "probe-exit", code)
        require(
            code == 0 and not err and out == f"{BOOTSTRAP_SHA}  {DEST}\n".encode(),
            "PROBE_READABILITY",
        )
        require(self.probe_ids(name, ident) is None, "PROBE_CLEANUP_UNCONFIRMED")
        self.journal.record(unit.name, "probe-done")
        print(f"phase=bootstrap unit={unit.name} sha256={BOOTSTRAP_SHA}", flush=True)

    def arm(self, unit):
        events = self.journal.events(unit.name)
        legacy = unit.name == "legacy"
        require(
            "initial-absence" in events
            and "config" not in events
            and ("setup-intent" in events) == legacy,
            "UNIT_NOT_FRESH",
        )
        self.verify_image_socket(bind=True)
        self.scoped_absent(unit.project)
        self.scoped_absent(f"pitlab-{unit.namespace}-dev", target="dev")
        if legacy:
            for target in ("dev", "test"):
                self.git("check-ignore", "-q", "--", f".env.{target}.local")
        else:
            self.journal.record(unit.name, "setup-intent")
            mkdir(unit.root)
            mkdir(unit.root / "scripts")
            write_new(unit.root / "compose.test.yaml", self.f1_inputs["compose.test.yaml"])
            write_new(unit.bootstrap, self.f1_inputs[BOOTSTRAP], 0o644)
            self.worker(lambda: self.f1.setup(unit.root, unit.namespace, unit.dev, unit.test), 15)
        _, _, identity = self.configs(unit)
        self.journal.record(unit.name, "config", identity)
        self.f1_preflight(unit, fresh=True)
        self.probe_bootstrap(unit)
        self.verify_image_socket()
        self.f1_preflight(unit, fresh=True)
        self.configs(unit, identity)
        self.journal.record(unit.name, "up-intent")

    def live(self, unit, *, first=False):
        events = self.journal.events(unit.name)
        require("up-intent" in events and "probe-done" in events, "TARGET_NOT_DISPATCHED")
        known = events.get("owned")
        require((known is None) == first, "TARGET_RECORD")
        resources = self.f1_preflight(unit, running=True, known=known)
        if first:
            self.journal.record(unit.name, "owned", resources)
            _, test, _ = self.configs(unit, events["config"])
            print(
                f"phase=target-ready unit={unit.name} project={test.project} "
                f"port={test.port} container={resources['container']}",
                flush=True,
            )
        return resources

    def profile_pins(self):
        profiles = {
            name: self.profile.digest("profile", self.profile.profile_body(name))
            for name, *_ in FIXTURES
        }
        inputs = {f"{profile}/{name}": digest for profile, name, digest, *_ in FIXTURES}
        return profiles, inputs

    def stage_roles(self, unit, config):
        mkdir(unit.custody)
        normal = unit.name != "restoration"
        profiles, inputs = self.profile_pins() if normal else ({}, {})
        if normal:
            mkdir(unit.custody / "inputs")
            for name, raw in self.fixture_bytes.items():
                write_new(unit.custody / "inputs" / name, raw)
        passwords = {
            "admin": config.admin_password,
            "migrator": config.migrator_password,
            **{role: secrets.token_hex(32) for role in ("custodian", "publisher", "reader")},
        }
        bindings = {}
        for role in self.profile.ROLES:
            path = unit.root / f"{role}.json"
            raw = self.profile.json_bytes(
                {
                    "mode": "SYNTHETIC_ONLY",
                    "target": "test",
                    "namespace": config.namespace,
                    "instance": config.instance_id,
                    "port": config.port,
                    "root": str(unit.custody),
                    "role": role,
                    "password": passwords[role],
                    "profiles": profiles if role == "custodian" else {},
                    "inputs": inputs if role == "custodian" else {},
                }
            )
            bindings[role] = [sha(raw), write_new(path, raw)]
        if unit.name == "integration":
            raw = config.app_password.encode("ascii") + b"\n"
            bindings["app"] = [sha(raw), write_new(unit.root / "legacy-app.secret", raw)]
        return bindings

    def role_configs(self, unit, config, bindings):
        normal = unit.name != "restoration"
        profiles, inputs = self.profile_pins() if normal else ({}, {})
        roles = {}
        for role in self.profile.ROLES:
            path = unit.root / f"{role}.json"
            raw, binding = read_bound(path, limit=64 * 1024)
            require([sha(raw), binding] == bindings[role], "ROLE_FILE_REPLACED")
            target = self.profile.load_target(path)
            require(
                read_bound(path, limit=64 * 1024) == (raw, binding)
                and target.role == role
                and target.target == "test"
                and target.marker == config.marker
                and target.port == config.port
                and target.root == unit.custody
                and target.profiles == (profiles if role == "custodian" else {})
                and target.inputs == (inputs if role == "custodian" else {}),
                "ROLE_CONFIG_IDENTITY",
            )
            roles[role] = target
        require(
            roles["admin"].password == config.admin_password
            and roles["migrator"].password == config.migrator_password
            and len({target.password for target in roles.values()} | {config.app_password}) == 6,
            "ROLE_SECRET_ORIGIN",
        )
        if normal:
            for name, expected in self.fixture_bytes.items():
                raw, _ = read_bound(unit.custody / "inputs" / name, limit=len(expected))
                require(raw == expected, "STAGED_FIXTURE_CHANGED")
        if unit.name == "integration":
            raw, binding = read_bound(unit.root / "legacy-app.secret", limit=1024)
            require(
                [sha(raw), binding] == bindings["app"]
                and raw == config.app_password.encode("ascii") + b"\n",
                "APP_SECRET_ORIGIN",
            )
        return roles

    def cli(self, unit, args):
        self.live(unit)
        out = self.checked(
            [sys.executable, "-B", "-m", "pit_research_lab.mvp.f4.d1", *args],
            limit=60,
            code="D1_CLI_REFUSED",
        )
        result = self.profile.decode(out)
        require(type(result) is dict, "D1_RESULT_SHAPE")
        return result

    def init_unit(self, unit, config):
        restore = unit.name == "restoration"
        flags = (
            ["--restore-only"]
            if restore
            else [
                "--profiles-until",
                self.profile.timestamp(datetime.now(UTC) + timedelta(minutes=30)),
            ]
        )
        argv = ["init", "--config", str(unit.root / "migrator.json")]
        for role in ("admin", "custodian", "reader", "publisher"):
            argv.extend([f"--{role}-config", str(unit.root / f"{role}.json")])
        self.journal.record(unit.name, "init-intent", flags)
        result = self.cli(unit, [*argv, *flags])
        require(
            result == {"revision": "d1_001", "marker": config.marker, "closed": restore},
            "D1_INITIALIZATION",
        )
        self.journal.record(unit.name, "init-done")

    def seed_source(self, unit, config):
        receipts = []
        for profile, name, digest, size, counts in FIXTURES:
            attempt = str(uuid4())
            self.journal.record(unit.name, f"import-intent-{profile}", attempt)
            result = self.cli(
                unit,
                [
                    "import-fixture",
                    "--config",
                    str(unit.root / "custodian.json"),
                    "--publisher-config",
                    str(unit.root / "publisher.json"),
                    "--profile",
                    profile,
                    "--file",
                    name,
                    "--attempt",
                    attempt,
                ],
            )
            require(
                result["attempt"] == attempt
                and result["observation"] == f"f4d1:observation:{attempt}"
                and result["deployment"] == config.marker
                and result["profile"] == profile
                and result["artifact"] == f"f4d1:artifact:sha256:{digest}"
                and result["byte_count"] == size
                and result["result"] == "IMPORTED_UNQUALIFIED"
                and result["publication"] == "UNRESOLVED"
                and result["mode"] == "SYNTHETIC_ONLY"
                and result["counts"]
                == dict(zip(("total", "accepted", "rejected", "excluded"), counts, strict=True)),
                "FIXTURE_IMPORT_RECEIPT",
            )
            receipt_sha = self.profile.digest("receipt", result)
            self.journal.record(unit.name, f"import-done-{profile}", receipt_sha)
            receipts.append((attempt, receipt_sha))
        self.verify_source(unit, receipts)

    def inventory(self, unit):
        value = self.cli(unit, ["inspect", "--config", str(unit.root / "reader.json")])
        require(
            value["class"] == "UNQUALIFIED_FOUNDATION"
            and value["mode"] == "SYNTHETIC_ONLY"
            and value["publication"] == "UNRESOLVED",
            "INVENTORY_CLASS",
        )
        return value

    def state(self, unit):
        return self.cli(unit, ["verify", "--config", str(unit.root / "migrator.json")])

    def verify_source(self, unit, receipts):
        inventory, state = self.inventory(unit), self.state(unit)
        require(
            len(inventory["inventory"]) == len(FIXTURES)
            and set(state["bindings"]) == {attempt for attempt, _ in receipts},
            "SOURCE_OBSERVATIONS",
        )
        for fixture, (attempt, receipt_sha), row in zip(
            FIXTURES, receipts, inventory["inventory"], strict=True
        ):
            profile, _, digest, size, counts = fixture
            binding = state["bindings"][attempt]
            require(
                row["id"] == attempt
                and row["profile"] == profile
                and row["artifact_sha"] == digest
                and row["size"] == size
                and row["receipt_sha"] == binding["receipt"] == receipt_sha
                and row["result"] == "IMPORTED_UNQUALIFIED"
                and binding["artifact"] == digest
                and tuple(row[k] for k in ("accepted", "rejected", "excluded")) == counts[1:],
                "SOURCE_BINDING",
            )
        issuer_id, revenue_id = (row[0] for row in receipts)
        issuers = inventory["issuers"]
        values = inventory["values"]
        assertions = state["bindings"][revenue_id]["assertions"]
        require(
            state["artifacts"] == {digest: size for _, _, digest, size, _ in FIXTURES}
            and state["inventory_sha"] == self.profile.sha(self.profile.json_bytes(inventory))
            and [(r["observation"], r["row_no"]) for r in issuers]
            == [(issuer_id, 1), (issuer_id, 2)]
            and len({r["issuer_key"] for r in issuers}) == 2
            and [(r["observation"], r["row_no"]) for r in values]
            == [(revenue_id, 1), (revenue_id, 2), (revenue_id, 3)]
            and [[r["row_no"], r["field"], r["version_sha"]] for r in values] == assertions
            and all(HEX64.fullmatch(r[k]) for r in values for k in ("subject_sha", "version_sha")),
            "SOURCE_SEMANTIC_INVENTORY",
        )

    def verify_empty(self, unit, roles):
        state = self.state(unit)
        require(
            state["artifacts"] == state["bindings"] == {}
            and all(state["tables"][key]["count"] == 0 for key in ("attempt", "observation"))
            and not any(os.path.lexists(unit.custody / name) for name in ("sha256", "attempts")),
            "F4_NOT_EMPTY",
        )
        if unit.name == "restoration":
            marker = self.profile.decode(
                self.profile.private_read(unit.custody / "restore-target.json", 4096)
            )
            require(
                marker == {"marker": roles["migrator"].marker}
                and all(item["count"] == 0 for item in state["tables"].values())
                and {p.name for p in unit.custody.iterdir()}
                == {".f4-custody.lock", "restore-target.json"},
                "RESTORATION_NOT_FRESH",
            )

            def closed():
                from pit_research_lab.mvp.f4.d1_backup import closed_empty
                from pit_research_lab.mvp.f4.d1_store import connect

                target = roles["migrator"]
                with connect(target) as connection:
                    closed_empty(connection, target)

            self.worker(closed, 30)
        else:
            inventory = self.inventory(unit)
            require(
                all(inventory[key] == [] for key in ("inventory", "values", "issuers")),
                "INTEGRATION_NOT_FRESH",
            )

            def profiles_active():
                from pit_research_lab.mvp.f4.d1_store import connect, is_active

                with connect(roles["migrator"]) as connection:
                    for profile, digest in roles["custodian"].profiles.items():
                        require(is_active(connection, profile, digest), "FIXTURE_PROFILE_INACTIVE")

            self.worker(profiles_active, 30)

    def descriptor_value(self):
        integration, restoration = (self.units[name] for name in ("integration", "restoration"))
        container = self.journal.events(integration.name)["owned"]["container"]
        restore_container = self.journal.events(restoration.name)["owned"]["container"]
        require(
            all(HEX64.fullmatch(ident) for ident in (container, restore_container))
            and container != restore_container,
            "DESCRIPTOR_CONTAINER",
        )
        return {
            "integration": str(integration.root),
            "independent": str(self.units["independent"].root),
            "container": container,
            "app_auth": str(integration.root / "legacy-app.secret"),
            "restoration": str(restoration.root),
            "restore_container": restore_container,
        }

    def validate_descriptor(self, *, verify_data=False):
        path = self.ctx.private / DESCRIPTOR
        raw = self.profile.private_read(path, 8192)
        value = self.profile.decode(raw)
        require(value == self.descriptor_value(), "DESCRIPTOR_CONTENT")
        require(
            sha(raw) == self.journal.events("job")["descriptor"],
            "DESCRIPTOR_REPLACED",
        )
        containers, networks, volumes, instances, passwords = set(), set(), set(), set(), set()
        for name, unit in self.units.items():
            events = self.journal.events(name)
            owned = self.live(unit)
            containers.add(owned["container"])
            networks.add(owned["network"])
            volumes.add(owned["volume"][0])
            dev, config, _ = self.configs(unit, events["config"])
            instances.update((dev.instance_id, config.instance_id))
            for f1config in (dev, config):
                passwords.update(
                    (
                        f1config.admin_password,
                        f1config.migrator_password,
                        f1config.app_password,
                    )
                )
            if name != "legacy":
                require("unit-ready" in events and "init-done" in events, "UNIT_NOT_READY")
                roles = self.role_configs(unit, config, events["roles"])
                passwords.update(
                    roles[role].password for role in ("custodian", "publisher", "reader")
                )
                if verify_data:
                    if name == "independent":
                        receipts = [
                            (events[f"import-intent-{profile}"], events[f"import-done-{profile}"])
                            for profile, *_ in FIXTURES
                        ]
                        self.verify_source(unit, receipts)
                    else:
                        self.verify_empty(unit, roles)
        require(
            len(containers) == len(networks) == len(volumes) == 4
            and len(instances) == 8
            and len(passwords) == 33,
            "LIVE_TARGET_COLLISION",
        )
        return path

    def prepare(self):
        self.live(self.units["legacy"], first=True)
        for name in F4_UNITS:
            unit = self.units[name]
            for prior in self.units.values():
                if prior == unit:
                    break
                self.live(prior)
            self.arm(unit)
            try:
                self.life(unit, "up", 205)
            except Refusal as exc:
                if str(exc) == "F1_GUARD_REFUSED":
                    self.journal.record(name, "up-refused")
                raise
            self.journal.record(name, "up-returned")
            self.live(unit, first=True)
            events = self.journal.events(name)
            _, config, _ = self.configs(unit, events["config"])
            self.journal.record(name, "roles-intent")
            bindings = self.stage_roles(unit, config)
            self.journal.record(name, "roles", bindings)
            roles = self.role_configs(unit, config, bindings)
            self.init_unit(unit, config)
            if name == "independent":
                self.seed_source(unit, config)
            else:
                self.verify_empty(unit, roles)
            self.journal.record(name, "unit-ready")
        raw = self.profile.json_bytes(self.descriptor_value())
        self.journal.record("job", "descriptor-intent")
        write_new(self.ctx.private / DESCRIPTOR, raw)
        self.journal.record("job", "descriptor", sha(raw))
        self.validate_descriptor()

    @contextlib.contextmanager
    def lock_config(self, unit):
        with directory_fd(unit.root) as parent:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            leaf = ".env.test.local"
            with os.fdopen(os.open(leaf, flags, dir_fd=parent), "rb") as file:
                info = os.fstat(file.fileno())
                expected = self.journal.events(unit.name)["config"]["configs"][1][1]
                require(regular(info, 0o600) and stamp(info) == expected, "CONFIG_LOCK")
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield

    def test(self):
        with contextlib.ExitStack() as stack:
            for name in F4_UNITS:
                stack.enter_context(self.lock_config(self.units[name]))
            path = self.validate_descriptor(verify_data=True)
            self.journal.record("job", "pytest-intent")

            def pytest_child():
                import pytest

                os.environ["PYTEST_ADDOPTS"] = REDACTION
                os.environ["F4_D1_INTEGRATION"] = str(path)
                observer = IntegrationObserver()
                code = int(pytest.main(["-q", "-m", "integration"], plugins=[observer]))
                return [code, observer.summary()]

            pytest_exit, counts = self.worker(pytest_child, 180)
        print(f"phase=pytest exit={pytest_exit} {encode(counts).decode()}", flush=True)
        try:
            self.journal.record("job", "pytest-result", [pytest_exit, counts])
            self.clean()
        except Exception as exc:
            if pytest_exit == 0:
                raise
            print(f"phase=post-checkout code={safe_code(exc)}", flush=True)
        if pytest_exit != 0:
            return pytest_exit
        return 0 if counts["ok"] else 10

    @contextlib.contextmanager
    def phase_budget(self, seconds):
        previous = self.deadline
        self.deadline = min(self.deadline, uptime() + seconds)
        try:
            yield
        finally:
            self.deadline = previous

    def cleanup_probe(self, unit, events):
        name = events.get("probe-create-intent")
        if name is None:
            return
        require(
            re.fullmatch(f"pitlab-ci-{unit.namespace}-probe-[0-9a-f]{{16}}", name),
            "PROBE_RECORD",
        )
        image = self.verify_image_socket()
        known = events.get("probe-id")
        ident = self.probe_ids(name, known)
        if "probe-done" in events:
            require(known is not None and ident is None, "PROBE_REAPPEARED")
            return
        if ident is None:
            require("probe-exit" in events, "PROBE_ABSENCE_UNCERTAIN")
            return
        status = self.inspect_probe(unit, name, ident, image)
        require(status in {"created", "exited", "running"}, "PROBE_STATE")
        require(known is not None or status == "created", "PROBE_ID_UNCERTAIN")
        require(
            status != "created" or "probe-start-intent" not in events,
            "PROBE_START_UNCERTAIN",
        )
        self.journal.record(unit.name, "probe-cleanup-intent", ident)
        if status == "running":
            self.docker("container", "stop", "--time", "2", ident)
        else:
            self.docker("container", "rm", ident)
        require(self.probe_ids(name, ident) is None, "PROBE_REMAINS")
        self.journal.record(unit.name, "probe-cleanup-done")

    def cleanup_target(self, unit, events):
        self.scoped_absent(f"pitlab-{unit.namespace}-dev", target="dev")
        if "up-intent" not in events:
            self.scoped_absent(unit.project)
            return
        require("probe-done" in events and "config" in events, "UNARMED_UP_RECORD")
        known = events.get("owned")
        resources = self.f1_preflight(unit, ports=False, known=known)
        if not any(resources.values()):
            require(known is not None or "up-refused" in events, "UP_ABSENCE_UNCERTAIN")
            return
        if known is None:
            require(
                unit.name == "legacy" or "up-returned" in events or "up-refused" in events,
                "UP_DISPATCH_UNCERTAIN",
            )
        self.journal.record(unit.name, "destroy-intent", resources)
        self.life(unit, "destroy-test", 72)
        self.scoped_absent(unit.project)
        self.journal.record(unit.name, "destroy-done")

    def cleanup(self, legacy=False):
        failures = 0
        names = ("legacy",) if legacy else (*reversed(F4_UNITS), "legacy")
        job_events = self.journal.events("job")
        if "socket" not in job_events:
            for name in names:
                events = self.journal.events(name)
                require(
                    not events.keys() & {"probe-create-intent", "up-intent"},
                    "MISSING_SOCKET_BINDING",
                )
            return 0
        require(self.endpoint() == job_events["socket"], "DOCKER_SOCKET_REPLACED")
        for name in names:
            unit = self.units[name]
            try:
                events = self.journal.events(name)
                operations = []
                if not legacy and "probe-create-intent" in events:
                    operations.append(("probe-cleanup", self.cleanup_probe, 15))
                if legacy or name != "legacy":
                    operations.append(("target-cleanup", self.cleanup_target, 73))
                for phase, action, limit in operations:
                    try:
                        with self.phase_budget(limit):
                            action(unit, events)
                        print(f"phase={phase} unit={name} code=COMPLETE", flush=True)
                    except Exception as exc:
                        failures += 1
                        print(f"phase={phase} unit={name} code={safe_code(exc)}", flush=True)
            except Exception as exc:
                failures += 1
                print(f"phase=cleanup-record unit={name} code={safe_code(exc)}", flush=True)
        return int(bool(failures))


class IntegrationObserver:
    """Read pytest collection and reports without writing to its selection or outcomes."""

    def __init__(self, expected=NODE_COUNT, required=F4_NODE):
        self.expected = expected
        self.required = required
        self.marked = Counter()
        self.deselected = set()
        self.selected = Counter()
        self.reports = {}
        self.bad = Counter()
        self.bad_nodes = set()
        self.collection_errors = 0
        self.collection_finished = False

    def pytest_itemcollected(self, item):
        if item.get_closest_marker("integration") is not None:
            self.marked[item.nodeid] += 1

    def pytest_deselected(self, items):
        self.deselected.update(
            item.nodeid for item in items if item.get_closest_marker("integration") is not None
        )

    def pytest_collection_finish(self, session):
        self.selected.update(item.nodeid for item in session.items)
        self.collection_finished = True

    def pytest_collectreport(self, report):
        if not report.passed:
            self.collection_errors += 1

    def pytest_runtest_logreport(self, report):
        phases = self.reports.setdefault(report.nodeid, Counter())
        if hasattr(report, "wasxfail"):
            self.bad["xfail_or_xpass"] += 1
            self.bad_nodes.add(report.nodeid)
        elif report.skipped:
            self.bad["skipped"] += 1
            self.bad_nodes.add(report.nodeid)
        elif report.failed or report.when not in {"setup", "call", "teardown"}:
            self.bad["failed_or_error"] += 1
            self.bad_nodes.add(report.nodeid)
        phases[report.when] += 1

    def summary(self):
        phases = {"setup": 1, "call": 1, "teardown": 1}
        complete = {node for node, reports in self.reports.items() if reports == phases}
        ok = (
            self.collection_finished
            and not self.collection_errors
            and not self.deselected
            and self.selected == self.marked
            and len(self.selected) == self.expected
            and self.required in self.selected
            and all(n == 1 for n in self.selected.values())
            and self.reports.keys() == complete == self.selected.keys()
            and not self.bad
        )
        nodes = "".join(f"{node}\n" for node in sorted(self.selected))
        return {
            "ok": ok,
            "marked": len(self.marked),
            "selected": len(self.selected),
            "complete": len(complete),
            "passed": len(complete & self.selected.keys() - self.bad_nodes),
            "integration_deselected": len(self.deselected),
            "collection_errors": self.collection_errors,
            "invalid_report_sequences": len(self.selected.keys() ^ complete),
            **{key: self.bad[key] for key in ("skipped", "xfail_or_xpass", "failed_or_error")},
            "selected_sha256": sha(nodes.encode()),
        }


def safe_code(exc):
    if isinstance(exc, Refusal) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", str(exc)):
        return str(exc)
    return "OPERATION_REFUSED"


def interrupted(_signum, _frame):
    global _step_interrupted
    first = not _step_interrupted
    _step_interrupted = True
    if first and not _defer_interrupt:
        raise Refusal("STEP_INTERRUPTED_UNCERTAIN")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in VERBS:
        print("phase=arguments code=INVALID_VERB", file=sys.stderr)
        return 2
    verb = args[0]
    os.umask(0o077)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        ctx = admit(os.environ)
        home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
        canonical_directory(home)
        require(Path(os.environ["HOME"]) == home, "RUNNER_HOME")
        phase_started = None
        if verb in CLEANUP:
            entry = os.environ.get("F4_CI_CLEANUP_STARTED", "")
            require(re.fullmatch(r"[0-9]{1,12}", entry), "INVALID_PHASE_ENTRY")
            phase_started = int(entry)
        job = HostedJob(ctx, verb, str(home), phase_started=phase_started)
        job.budget(NORMAL_SECONDS)
        job.verify_checkout(verb)
        job.load_modules(verb)
        if verb == "preflight":
            job.journal.create()
        else:
            job.journal.open()
        with job.journal.lock():
            if verb == "preflight":
                print(job.preflight())
            elif verb == "arm-legacy":
                job.arm(job.units["legacy"])
            elif verb == "prepare":
                job.prepare()
            elif verb == "run":
                return job.test()
            else:
                return job.cleanup(legacy=verb == "cleanup-legacy")
        return 0
    except Exception as exc:
        print(f"phase={verb} code={safe_code(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
