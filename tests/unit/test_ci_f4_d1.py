"""Offline hosted-job contracts with stubbed Docker and database I/O."""

import hashlib
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from pit_research_lab.infrastructure.database import config
from pit_research_lab.mvp.f4 import d1, d1_profile

ROOT = Path(__file__).resolve().parents[2]
SENTINEL = "private-credential-sentinel"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ci = load_script("ci_f4_d1_test", ROOT / "scripts/ci_f4_d1.py")
f1 = load_script("f1_ci_test", ROOT / "scripts/database.py")


def baseline(*args):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "--no-replace-objects", *args], cwd=ROOT
    )


def call_job(tmp_path):
    ctx = ci.JobContext(
        ROOT,
        tmp_path / "attempt",
        "a" * 40,
        "a" * 40,
        "refs/heads/main",
        None,
        f"{ci.REPO}:{ci.JOB}:123:2",
        "123:2",
        int(ci.uptime()),
    )
    job = ci.HostedJob(ctx, "preflight", str(tmp_path))
    job.journal = ci.Journal(ctx.private, {"key": ctx.key, "sha": ctx.sha})
    job.journal.create()
    job.config = config
    job.profile = d1_profile
    job.f1 = f1
    job.f1_inputs = {path: (ROOT / path).read_bytes() for path in ci.PINS}
    job.fixture_bytes = {
        fixture[1]: (ROOT / ci.FIXTURE_DIR / fixture[1]).read_bytes() for fixture in ci.FIXTURES
    }
    return job


@pytest.fixture
def job(tmp_path):
    mode = os.umask(0o077)
    try:
        yield call_job(tmp_path)
    finally:
        os.umask(mode)


def staged(job, name):
    unit = job.units[name]
    ci.mkdir(unit.root)
    ci.mkdir(unit.root / "scripts")
    compose = unit.root / "compose.test.yaml"
    ci.write_new(compose, job.f1_inputs["compose.test.yaml"])
    if name == "legacy":
        compose.chmod(0o644)
    ci.write_new(unit.bootstrap, job.f1_inputs[ci.BOOTSTRAP], 0o644)
    job.f1.setup(unit.root, unit.namespace, unit.dev, unit.test)
    _, cfg, binding = job.configs(unit)
    job.journal.record(name, "config", binding)
    return unit, cfg


def test_fixed_verbs_and_refusal_does_not_disclose():
    assert ci.VERBS == ("preflight", "arm-legacy", "prepare", "run", "cleanup", "cleanup-legacy")
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
        "DOCKER_HOST": SENTINEL,
    }
    for args, code, message in (
        (["run", SENTINEL], 2, "INVALID_VERB"),
        (["preflight"], 1, "HOSTED_CONTEXT"),
    ):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / ci.HELPER), *args],
            env=environment,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert result.returncode == code
        assert message in result.stderr
        assert SENTINEL not in result.stdout + result.stderr


@pytest.fixture
def native_metadata(tmp_path, monkeypatch):
    temp = tmp_path.resolve()
    event = temp / "_github_workflow" / "event.json"
    event.parent.mkdir()
    payload = {
        "repository": {"full_name": ci.REPO},
        "ref": "refs/heads/main",
        "after": "a" * 40,
    }
    event.write_text(json.dumps(payload))
    monkeypatch.setattr(ci.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ci.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(ci.platform, "release", lambda: "6.14.0-azure")
    monkeypatch.setattr(
        ci.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "24.04"}
    )
    return {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
        "GITHUB_REPOSITORY": ci.REPO,
        "GITHUB_JOB": ci.JOB,
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_SHA": "a" * 40,
        "GITHUB_RUN_ID": "9876543210",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REF": payload["ref"],
        "GITHUB_WORKFLOW_REF": f"{ci.REPO}/{ci.WORKFLOW}@refs/heads/main",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_WORKSPACE": str(ROOT),
        "RUNNER_TEMP": str(temp),
        "GITHUB_EVENT_PATH": str(event),
        "F4_CI_STARTED": str(int(ci.uptime())),
        "PYTEST_ADDOPTS": ci.REDACTION,
    }


@pytest.mark.parametrize(
    ("key", "value", "code"),
    [
        ("RUNNER_ENVIRONMENT", "self-hosted", "HOSTED_CONTEXT"),
        ("GITHUB_JOB", "quality", "HOSTED_CONTEXT"),
        ("GITHUB_RUN_ID", "9" * 30, "RUN_METADATA"),
        ("GITHUB_SHA", "deadbeef", "RUN_METADATA"),
        ("GITHUB_WORKFLOW_REF", "other/other", "WORKFLOW_REF"),
        ("GITHUB_EVENT_PATH", "/tmp/event.json", "EVENT_PATH"),
        ("DOCKER_HOST", "tcp://invalid:1", "AMBIENT_OVERRIDE"),
        ("COMPOSE_FILE", "other.yaml", "AMBIENT_OVERRIDE"),
        ("PGHOST", "example.invalid", "AMBIENT_OVERRIDE"),
        ("PYTEST_PLUGINS", "other", "AMBIENT_OVERRIDE"),
        ("F4_D1_INTEGRATION", "/tmp/given", "AMBIENT_OVERRIDE"),
        ("PYTHONPATH", "/tmp/given", "AMBIENT_OVERRIDE"),
    ],
)
def test_hosted_metadata_refuses_before_dispatch(native_metadata, key, value, code):
    assert ci.admit(native_metadata).parents is None
    with pytest.raises(ci.Refusal, match=f"^{code}$"):
        ci.admit(native_metadata | {key: value})


def test_native_kernel_and_pr_parent_order(native_metadata, monkeypatch):
    env = native_metadata
    env.update(
        GITHUB_EVENT_NAME="pull_request",
        GITHUB_REF="refs/pull/5/merge",
        GITHUB_WORKFLOW_REF=f"{ci.REPO}/{ci.WORKFLOW}@refs/pull/5/merge",
    )
    payload = {
        "repository": {"full_name": ci.REPO},
        "number": 5,
        "pull_request": {
            "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": ci.REPO}},
            "head": {"sha": "c" * 40},
        },
    }
    event = Path(env["GITHUB_EVENT_PATH"])
    event.write_text(json.dumps(payload))
    assert ci.admit(env).parents == ("b" * 40, "c" * 40)
    payload["pull_request"]["head"]["sha"] = env["GITHUB_SHA"]
    event.write_text(json.dumps(payload))
    with pytest.raises(ci.Refusal, match="PR_IDENTITY"):
        ci.admit(env)
    monkeypatch.setattr(ci.platform, "release", lambda: "microsoft-WSL2")
    with pytest.raises(ci.Refusal, match="NATIVE_NONROOT_LINUX"):
        ci.admit(env)


def test_checkout_guard_with_actual_git_and_separate_dirty_cleanup(job):
    sha = baseline("rev-parse", "HEAD").decode().strip()
    job.ctx = replace(job.ctx, sha=sha, workflow_sha=sha)
    assert job.checkout_file(ci.BOOTSTRAP) == job.f1_inputs[ci.BOOTSTRAP]
    with pytest.raises(ci.Refusal, match="COMMITTED_INPUT"):
        job.checkout_file(ci.BOOTSTRAP, blob="0" * 40)
    with pytest.raises(ci.Refusal, match="GIT_REFUSED"):
        job.git("show", f"{'0' * 40}:Makefile")
    job.ctx = replace(job.ctx, sha="0" * 40)
    with pytest.raises(ci.Refusal, match="CHECKOUT_SHA"):
        job.verify_checkout("prepare")


def test_attempt_paths_namespaces_and_stale_locked_journal(job):
    assert [(unit.dev, unit.test) for unit in job.units.values()] == [
        (55432, 55433),
        (56321, 56322),
        (56323, 56324),
        (56325, 56326),
    ]
    assert len({unit.project for unit in job.units.values()}) == 4
    assert len({unit.root for unit in job.units.values()}) == 4
    other = replace(job.ctx, legacy_key="123:3", key=job.ctx.key + "3")
    assert {u.namespace for u in ci.units_for(other).values()}.isdisjoint(
        u.namespace for u in job.units.values()
    )
    with pytest.raises(ci.Refusal, match="STALE_JOURNAL"):
        ci.Journal(job.ctx.private, {"wrong": "attempt"}).open()
    with job.journal.lock(), pytest.raises(BlockingIOError), job.journal.lock():
        pytest.fail("double lock")


@pytest.mark.parametrize("operation", ["tear", "truncate", "replace", "change"])
def test_journal_refuses_modified_record(job, operation):
    name = "integration"
    job.journal.record(name, "setup-intent")
    job.journal.record(name, "up-intent")
    leaf = job.ctx.private / f"{name}.jsonl"
    body = leaf.read_bytes()
    if operation == "tear":
        leaf.write_bytes(body[:-1])
    elif operation == "truncate":
        leaf.write_bytes(b"\n".join(body.splitlines()[:-1]) + b"\n")
    elif operation == "replace":
        leaf.rename(leaf.with_suffix(".old"))
        ci.write_new(leaf, body)
    else:
        leaf.write_bytes(body.replace(b"up-intent", b"destroyed"))
    with pytest.raises(ci.Refusal, match="JOURNAL"):
        job.journal.events(name)
    assert job.journal.events("restoration") == {"planned": job.journal.identity}


def test_private_staging_and_real_config_parsers(job):
    unit, cfg = staged(job, "integration")
    ids = job.stage_roles(unit, cfg)
    roles = job.role_configs(unit, cfg, ids)
    assert set(roles) == set(d1_profile.ROLES)
    assert roles["admin"].password == cfg.admin_password
    assert roles["migrator"].password == cfg.migrator_password
    assert ci.read_bound(unit.root / "legacy-app.secret")[0] == cfg.app_password.encode() + b"\n"
    assert roles["publisher"].inputs == {}
    assert set(roles["custodian"].profiles) == {r[0] for r in ci.FIXTURES}
    for path in (unit.root, unit.root / "scripts", unit.custody, unit.custody / "inputs"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    assert stat.S_IMODE(unit.bootstrap.stat().st_mode) == 0o644
    assert ci.sha(unit.bootstrap.read_bytes()) == ci.BOOTSTRAP_SHA
    for path in (
        unit.root / "compose.test.yaml",
        unit.root / ".env.test.local",
        unit.root / ".env.dev.local",
        unit.root / "legacy-app.secret",
        *(unit.root / f"{role}.json" for role in roles),
        *tuple((unit.custody / "inputs").iterdir()),
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("kind", ["preexisting", "symlink", "hardlink", "fifo", "mode", "bytes"])
def test_file_boundary_refuses_without_clobber(job, kind):
    unit, cfg = staged(job, "integration")
    path = unit.bootstrap
    expected = job.journal.events(unit.name)["config"]
    if kind == "preexisting":
        with pytest.raises(FileExistsError):
            ci.write_new(path, b"replacement", 0o644)
        assert ci.sha(path.read_bytes()) == ci.BOOTSTRAP_SHA
        return
    if kind == "hardlink":
        os.link(path, path.with_name("extra"))
    elif kind == "symlink":
        path.unlink()
        path.symlink_to(ROOT / ci.BOOTSTRAP)
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path, 0o644)
    elif kind == "mode":
        path.chmod(0o600)
    else:
        path.write_bytes(b"changed")
    with pytest.raises((ci.Refusal, OSError)):
        job.configs(unit, expected)


def test_instance_replacement_and_restore_role_maps(job):
    unit, cfg = staged(job, "restoration")
    bindings = job.stage_roles(unit, cfg)
    roles = job.role_configs(unit, cfg, bindings)
    assert not (unit.custody / "inputs").exists()
    assert not (unit.root / "legacy-app.secret").exists()
    assert all(not role.inputs and not role.profiles for role in roles.values())
    leaf = unit.root / ".env.test.local"
    leaf.write_bytes(leaf.read_bytes().replace(cfg.instance_id.encode(), b"0" * 36))
    with pytest.raises(config.PersistenceError):
        job.configs(unit, job.journal.events(unit.name)["config"])


@pytest.mark.parametrize("source", ["legacy", "independent", "integration", "restoration"])
def test_probe_exact_spec_and_exit_gate(job, monkeypatch, source):
    if source == "legacy":
        unit = replace(job.units[source], root=job.ctx.private / "legacy-test")
        ci.mkdir(unit.root)
        ci.mkdir(unit.root / "scripts")
        ci.write_new(unit.bootstrap, job.f1_inputs[ci.BOOTSTRAP], 0o644)
        # Legacy uses checkout-mode Compose. The offline copy is private.
        compose = unit.root / "compose.test.yaml"
        ci.write_new(compose, job.f1_inputs["compose.test.yaml"])
        compose.chmod(0o644)
        job.journal.record(source, "config", {"bootstrap": job.bootstrap(unit)})
    else:
        unit, _ = staged(job, source)
    ident = "b" * 64
    image = {"id": f"sha256:{'e' * 64}", "labels": {}}
    monkeypatch.setattr(job, "verify_image_socket", lambda: image)
    docker_actions = []
    call_state = {"created": False, "started": False}

    def docker(*args, **kwargs):
        docker_actions.append(args)
        if args[:2] == ("container", "ls"):
            return (
                b""
                if not call_state["created"] or call_state["started"]
                else (ident + "\n").encode()
            )
        if args[:2] == ("container", "create"):
            assert "probe-create-intent" in job.journal.events(source)
            assert "--rm" in args and "--network=none" in args and "--pull=never" in args
            assert "--cap-drop=ALL" in args and "--no-healthcheck" in args
            assert args[-4:] == ("/bin/sh", ci.IMAGE, "-c", ci.PROBE_SCRIPT)
            assert "PGPASSWORD" not in " ".join(args)
            call_state["created"] = True
            return (ident + "\n").encode()
        if args[:2] == ("container", "inspect"):
            name = job.journal.events(source)["probe-create-intent"]
            return ci.encode(probe_inspection(unit, name, ident, image))
        pytest.fail(f"unexpected Docker call {args[:2]}")

    def command(args, *, limit):
        assert args == ["docker", "container", "start", "--attach", ident]
        assert limit == 25 and "probe-start-intent" in job.journal.events(source)
        call_state["started"] = True
        return 0, f"{ci.BOOTSTRAP_SHA}  {ci.DEST}\n".encode(), b""

    monkeypatch.setattr(job, "docker", docker)
    monkeypatch.setattr(job, "command", command)
    job.probe_bootstrap(unit)
    assert "probe-done" in job.journal.events(source)
    assert [a[:2] for a in docker_actions].count(("container", "create")) == 1


def probe_inspection(unit, name, ident, image):
    cfg = {
        "Image": ci.IMAGE,
        "Labels": {ci.PROBE_LABEL: name},
        "Entrypoint": ["/bin/sh"],
        "Cmd": ["-c", ci.PROBE_SCRIPT],
        "User": "postgres",
        "Healthcheck": {"Test": ["NONE"]},
        "Tty": False,
        "OpenStdin": False,
    }
    host = {
        "NetworkMode": "none",
        "ReadonlyRootfs": True,
        "AutoRemove": True,
        "Privileged": False,
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"],
        "RestartPolicy": {"Name": "no"},
        "Mounts": [
            {"Type": "bind", "Source": str(unit.bootstrap), "Target": ci.DEST, "ReadOnly": True},
            {
                "Type": "tmpfs",
                "Target": ci.PGDATA,
                "TmpfsOptions": {"SizeBytes": 1048576, "Mode": 0o700},
            },
        ],
    }
    mounts = [{"Type": "bind", "Source": str(unit.bootstrap), "Destination": ci.DEST, "RW": False}]
    return [ident, "/" + name, image["id"], cfg, host, mounts, "created", {"none": {}}]


@pytest.mark.parametrize("defect", ["volume", "uid", "capability", "source"])
def test_probe_must_pass_fixed_inspection(job, monkeypatch, defect):
    unit, _ = staged(job, "integration")
    name, ident = "probe", "b" * 64
    image = {"id": f"sha256:{'e' * 64}", "labels": {}}
    fields = probe_inspection(unit, name, ident, image)
    if defect == "volume":
        fields[5].append({"Type": "volume", "Destination": ci.PGDATA})
    elif defect == "uid":
        fields[3]["User"] = "root"
    elif defect == "capability":
        fields[4]["CapDrop"] = []
    else:
        fields[4]["Mounts"][0]["Source"] = "/tmp/other"
    monkeypatch.setattr(job, "docker", lambda *args: ci.encode(fields))
    with pytest.raises(ci.Refusal, match="PROBE_"):
        job.inspect_probe(unit, name, ident, image)


def image_record(repository="postgres", labels=None):
    return {
        "Id": f"sha256:{'4' * 64}",
        "RepoDigests": [f"{repository}@{ci.IMAGE.rsplit('@', 1)[1]}"],
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {"Volumes": {ci.PGDATA: {}}, "Labels": labels},
    }


def image_reply(status, body, *, changes=None):
    headers = {
        "Server": "Docker/28.0.4 (linux)",
        "Api-Version": "1.48",
        "Ostype": "linux",
        "Connection": "close",
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    headers.update(changes or {})
    lines = [f"HTTP/1.1 {status} Test reply"]
    lines.extend(f"{key}: {val}" for key, val in headers.items() if val is not None)
    return "\r\n".join(lines).encode() + b"\r\n\r\n" + body


FAKE_IMAGE_DAEMON = r"""
import os
import sys
from pathlib import Path

raw_root, mode, *fds = sys.argv[1:]
root = Path(raw_root)
for index, fd in enumerate(fds):
    with os.fdopen(int(fd), "r+b", buffering=0) as conn:
        request = bytearray()
        while not request.endswith(b"\r\n\r\n"):
            data = conn.read(1024)
            assert data and len(request) + len(data) <= 4096
            request.extend(data)
        (root / f"request-{index}").write_bytes(request)
        if mode == "replace":
            (root / "replacement").touch()
        if mode == "stall":
            assert conn.read(1) == b""
            (root / f"peer-saw-eof-{index}").touch()
        else:
            response = (root / f"response-{index}").read_bytes()
            assert os.write(conn.fileno(), response) == len(response)
"""


@pytest.fixture
def image_daemon(monkeypatch):
    @contextmanager
    def serve(*responses, mode="reply"):
        with TemporaryDirectory(prefix="f4-image-") as directory, ExitStack() as connections:
            root = Path(directory)
            path = Path("/var/run/docker.sock")
            request = (
                b"GET /v1.44/images/postgres%40sha256%3A"
                b"3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826/json "
                b"HTTP/1.1\r\nHost: docker\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
            )
            clients, peers = [], []
            for index, response in enumerate(responses):
                (root / f"response-{index}").write_bytes(response)
                client, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
                clients.append(connections.enter_context(client))
                peers.append(connections.enter_context(peer))
            # Exchange real bytes with a private AF_UNIX peer. The test adapter
            # supplies socket identity and uses inherited, already-connected fds.
            info = os.fstat(clients[0].fileno())
            replacement = os.fstat(peers[0].fileno())
            assert (info.st_dev, info.st_ino) != (replacement.st_dev, replacement.st_ino)
            inherited = tuple(peer.fileno() for peer in peers)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    FAKE_IMAGE_DAEMON,
                    str(root),
                    mode,
                    *map(str, inherited),
                ],
                pass_fds=inherited,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for peer in peers:
                peer.close()
            position = 0
            original_lstat, original_fork = Path.lstat, os.fork

            def lstat(leaf, *args, **kwargs):
                if leaf == path:
                    return replacement if (root / "replacement").is_file() else info
                return original_lstat(leaf, *args, **kwargs)

            def fork():
                nonlocal position
                pid = original_fork()
                if pid:
                    clients[position].close()
                    position += 1
                return pid

            class ConnectedSocket:
                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    clients[position].close()
                    (root / f"closed-{position}").touch()

                def __getattr__(self, attr):
                    return getattr(clients[position], attr)

                def connect(self, address):
                    assert address == str(path)

                def sendall(self, data):
                    assert os.write(clients[position].fileno(), data) == len(data)

            def connectable(family, kind):
                assert (family, kind) == (socket.AF_UNIX, socket.SOCK_STREAM)
                return ConnectedSocket()

            with process, monkeypatch.context() as patch:
                patch.setattr(Path, "lstat", lstat)
                patch.setattr(ci.os, "fork", fork)
                patch.setattr(ci.socket, "socket", connectable)
                try:
                    yield [info.st_dev, info.st_ino]
                    assert process.wait(timeout=6) == 0
                    for index in range(len(responses)):
                        assert (root / f"request-{index}").read_bytes() == request
                        receipt = "peer-saw-eof" if mode == "stall" else "closed"
                        assert (root / f"{receipt}-{index}").is_file()
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=3)

    return serve


@pytest.mark.parametrize(
    "defect", ["digest", "extra-volume", "architecture", "not-found", "daemon"]
)
def test_exact_image_and_distinguish_missing(job, image_daemon, defect):
    record = image_record()
    if defect == "digest":
        record["RepoDigests"] = ["postgres@sha256:" + "0" * 64]
    elif defect == "extra-volume":
        record["Config"]["Volumes"]["/other"] = {}
    elif defect == "architecture":
        record["Architecture"] = "arm64"
    if defect == "not-found":
        response = image_reply(404, ci.encode({"message": SENTINEL}))
        with image_daemon(response, response) as endpoint:
            assert job.image(endpoint, allow_missing=True) is None
            with pytest.raises(ci.Refusal, match="^IMAGE_MISSING$"):
                job.image(endpoint)
    else:
        if defect == "daemon":
            response = image_reply(500, ci.encode({"message": SENTINEL}))
            code = "IMAGE_HTTP_STATUS"
        else:
            response = image_reply(200, ci.encode(record))
            code = "IMAGE_IDENTITY"
        with image_daemon(response) as endpoint, pytest.raises(ci.Refusal, match=f"^{code}$"):
            job.image(endpoint, allow_missing=True)


@pytest.mark.parametrize(
    "repository", ["postgres", "library/postgres", "docker.io/library/postgres"]
)
def test_image_inspect_accepts_digest_aliases(job, image_daemon, capsys, repository):
    labels = {"example": SENTINEL}
    record = image_record(repository, labels)
    body = ci.encode(record)
    chunks = (body[:41], body[41:])
    encoded = b"".join(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n" for chunk in chunks)
    response = image_reply(
        200,
        encoded + b"0\r\n\r\n",
        changes={"Content-Length": None, "Transfer-Encoding": "chunked"},
    )
    with image_daemon(response) as endpoint:
        assert job.image(endpoint) == {"id": record["Id"], "labels": labels}
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("Id", "sha256:" + "X" * 64, "IMAGE_IDENTITY"),
        ("Id", 5, "IMAGE_IDENTITY"),
        ("Os", "windows", "IMAGE_IDENTITY"),
        ("RepoDigests", [], "IMAGE_IDENTITY"),
        ("RepoDigests", "postgres", "IMAGE_IDENTITY"),
        ("Volumes", {}, "IMAGE_IDENTITY"),
        ("Volumes", {ci.PGDATA: {"unexpected": 1}}, "IMAGE_IDENTITY"),
        ("Labels", [SENTINEL], "IMAGE_IDENTITY"),
        ("Labels", {"example": 1}, "IMAGE_IDENTITY"),
        ("Config", None, "IMAGE_JSON_SHAPE"),
    ],
)
def test_image_inspect_validates_exact_fields(job, image_daemon, field, value, code):
    record = image_record()
    target = record["Config"] if field in {"Volumes", "Labels"} else record
    target[field] = value
    with image_daemon(image_reply(200, ci.encode(record))) as endpoint:
        with pytest.raises(ci.Refusal, match=f"^{code}$"):
            job.image(endpoint, allow_missing=True)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "IMAGE_API_REJECTED"),
        *[
            (status, "IMAGE_HTTP_STATUS")
            for status in (100, 201, 302, 307, 401, 403, 429, 500, 503)
        ],
    ],
)
def test_image_inspect_refuses_other_statuses(job, image_daemon, capsys, status, code):
    response = image_reply(status, ci.encode({"message": SENTINEL}), changes={"Location": SENTINEL})
    with image_daemon(response) as endpoint, pytest.raises(ci.Refusal, match=f"^{code}$") as exc:
        job.image(endpoint, allow_missing=True)
    assert ci.safe_code(exc.value) == code
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({"Api-Version": None, "Ostype": None, "Server": None}, "IMAGE_API_ROUTE"),
        ({"Api-Version": "1.43"}, "IMAGE_API_UNSUPPORTED"),
        ({"Api-Version": "2.0"}, "IMAGE_API_UNSUPPORTED"),
        ({"Api-Version": "1.48, 1.43"}, "IMAGE_API_ROUTE"),
        ({"Server": "proxy"}, "IMAGE_API_ROUTE"),
        ({"Content-Type": "text/html"}, "IMAGE_HTTP_CONTENT"),
        ({"Content-Encoding": "gzip"}, "IMAGE_HTTP_CONTENT"),
        ({"Content-Length": None}, "IMAGE_HTTP_FRAMING"),
        ({"Content-Length": "2, 2"}, "IMAGE_HTTP_FRAMING"),
        ({"Content-Length": "1000"}, "IMAGE_HTTP_FRAMING"),
        ({"Content-Length": "2"}, "IMAGE_HTTP_FRAMING"),
        ({"content-length": "3"}, "IMAGE_HTTP_FRAMING"),
        ({"Transfer-Encoding": "chunked"}, "IMAGE_HTTP_FRAMING"),
        ({"Content-Length": None, "Transfer-Encoding": "identity"}, "IMAGE_HTTP_FRAMING"),
        ({"Content-Length": str(ci.IMAGE_ERROR_LIMIT + 1)}, "IMAGE_HTTP_LIMIT"),
        ({"X-Huge": "a" * ci.IMAGE_HEADER_LIMIT}, "IMAGE_HTTP_LIMIT"),
    ],
    ids=[
        "generic-route",
        "old-api",
        "wrong-major",
        "ambiguous-api",
        "proxy",
        "html",
        "encoding",
        "missing-frame",
        "mixed-length",
        "truncated",
        "surplus",
        "duplicate-length",
        "ambiguous-frame",
        "unknown-transfer",
        "oversized-body",
        "oversized-header",
    ],
)
def test_image_inspect_refuses_ambiguous_404(job, image_daemon, headers, code):
    response = image_reply(404, ci.encode({"message": SENTINEL}), changes=headers)
    with image_daemon(response) as endpoint, pytest.raises(ci.Refusal, match=f"^{code}$"):
        job.image(endpoint, allow_missing=True)


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (b"not-json", "IMAGE_JSON"),
        (b"\xff", "IMAGE_JSON"),
        (b'{"message": NaN}', "IMAGE_JSON"),
        (b'{"message":"first","message":"second"}', "DUPLICATE_JSON_KEY"),
        (b'{"message":"missing"}{}', "IMAGE_JSON"),
        (b"{}", "IMAGE_ERROR_ENVELOPE"),
        (b"[]", "IMAGE_ERROR_ENVELOPE"),
        (b'{"message":"missing","extra":3}', "IMAGE_ERROR_ENVELOPE"),
        (b'{"message":"  "}', "IMAGE_ERROR_ENVELOPE"),
        (b'{"message":2}', "IMAGE_ERROR_ENVELOPE"),
    ],
    ids=[
        "invalid-json",
        "invalid-utf8",
        "invalid-constant",
        "duplicate-json-key",
        "second-json",
        "missing-message",
        "array",
        "extra-key",
        "blank",
        "not-string",
    ],
)
def test_image_inspect_requires_strict_error_envelope(job, image_daemon, body, code):
    with image_daemon(image_reply(404, body)) as endpoint:
        with pytest.raises(ci.Refusal, match=f"^{code}$"):
            job.image(endpoint, allow_missing=True)


@pytest.mark.parametrize("body", [b"z\r\n", b"3\r\n{}", b"0\r\n", b"0\r\nX-Trailer: no\r\n\r\n"])
def test_image_inspect_refuses_invalid_chunk_framing(job, image_daemon, body):
    response = image_reply(
        404, body, changes={"Content-Length": None, "Transfer-Encoding": "chunked"}
    )
    with (
        image_daemon(response) as endpoint,
        pytest.raises(ci.Refusal, match="^IMAGE_HTTP_FRAMING$"),
    ):
        job.image(endpoint, allow_missing=True)


@pytest.mark.parametrize("mode", ["cached", "missing", "refused"])
def test_image_preflight_preserves_gate_order_and_journal(
    job, image_daemon, monkeypatch, capsys, mode
):
    record = image_record()
    status = {"cached": 200, "missing": 404, "refused": 503}[mode]
    body = ci.encode(record if mode == "cached" else {"message": SENTINEL})
    with image_daemon(image_reply(status, body)) as endpoint:
        monkeypatch.setattr(job, "endpoint", lambda: endpoint)
        monkeypatch.setattr(
            job, "docker", lambda *args: b"28.0.4\n" if args[0] == "info" else b"2.38.2\n"
        )
        monkeypatch.setattr(job, "git", lambda *args: b"")
        calls = []
        monkeypatch.setattr(job, "initial_ports", lambda: calls.append("ports"))
        monkeypatch.setattr(job, "scoped_absent", lambda project, **kw: calls.append(project))
        prior = job.image

        def inspect_after_gates(binding, *, allow_missing=False):
            assert binding == job.journal.events("job")["socket"] == endpoint
            assert calls[0] == "ports" and len(calls) == 9
            assert all("initial-absence" in job.journal.events(name) for name in ci.UNITS)
            return prior(binding, allow_missing=allow_missing)

        monkeypatch.setattr(job, "image", inspect_after_gates)
        if mode == "refused":
            with pytest.raises(ci.Refusal, match="^IMAGE_HTTP_STATUS$"):
                job.preflight()
        else:
            assert job.preflight() == (
                "IMAGE_PRESENT" if mode == "cached" else "IMAGE_ACQUISITION_REQUIRED"
            )
    journal = job.journal.events("job")
    assert ("pull-intent" in journal) == (mode == "missing")
    assert ("cached-image" in journal) == (mode == "cached")
    if mode == "cached":
        assert journal["cached-image"] == record["Id"]
    assert "image" not in journal
    assert capsys.readouterr() == ("", "")


def test_image_inspect_refuses_endpoint_replacement(job, image_daemon):
    absent = image_reply(404, ci.encode({"message": SENTINEL}))
    with image_daemon(absent, mode="replace") as endpoint:
        with pytest.raises(ci.Refusal, match="^DOCKER_SOCKET_REPLACED$"):
            job.image(endpoint, allow_missing=True)


@pytest.mark.parametrize("defect", ["regular", "symlink", "inode"])
def test_image_inspect_never_connects_to_unbound_path(job, monkeypatch, defect):
    assert ci.DOCKER_SOCKET_PATH == Path("/var/run/docker.sock")
    with TemporaryDirectory(prefix="f4-image-") as directory:
        path = Path(directory) / "engine.sock"
        binding = [1, 1]
        if defect == "regular":
            path.touch()
        elif defect == "symlink":
            path.symlink_to(path.with_name("other"))
        else:
            lstat = Path.lstat

            def different_inode(leaf, *args, **kwargs):
                if leaf == path:
                    return SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFSOCK)
                return lstat(leaf, *args, **kwargs)

            monkeypatch.setattr(Path, "lstat", different_inode)
        monkeypatch.setattr(ci, "DOCKER_SOCKET_PATH", path)
        with pytest.raises(ci.Refusal, match="^DOCKER_SOCKET_REPLACED$"):
            job.image(binding, allow_missing=True)


def test_image_inspect_refuses_socket_io(job, monkeypatch):
    def refused(*_):
        raise ConnectionRefusedError(SENTINEL)

    monkeypatch.setattr(ci.socket, "socket", refused)
    with pytest.raises(ci.Refusal, match="^IMAGE_IO_REFUSED$"):
        job.image([1, 2], allow_missing=True)


@pytest.mark.parametrize("bound", ["socket", "worker"])
def test_image_inspect_stalled_socket_closes_under_supervision(
    job, image_daemon, monkeypatch, bound
):
    with image_daemon(b"", mode="stall") as endpoint:
        if bound == "socket":
            budget = job.budget
            monkeypatch.setattr(
                job,
                "budget",
                lambda limit: min(budget(limit), 0.4) if job.in_worker else budget(limit),
            )
            with pytest.raises(ci.Refusal, match="^IMAGE_IO_TIMEOUT$"):
                job.image(endpoint, allow_missing=True)
        else:
            worker, stop_worker = job.worker, ci.stop_worker
            stopped = []

            def short_worker(action, limit):
                assert limit == 15
                return worker(action, 0.8)

            def stop(pid):
                stop_worker(pid)
                stopped.append(pid)

            monkeypatch.setattr(job, "worker", short_worker)
            monkeypatch.setattr(ci, "stop_worker", stop)
            with pytest.raises(ci.Refusal, match="^WORKER_TIMEOUT_UNCERTAIN$"):
                job.image(endpoint, allow_missing=True)
            assert len(stopped) == 1
            with pytest.raises(ChildProcessError):
                os.waitpid(stopped[0], os.WNOHANG)


@pytest.mark.parametrize("mode", ["exact", "missing", "wrong-digest", "replacement", "unplanned"])
def test_exact_image_binding_after_preflight(job, image_daemon, monkeypatch, mode):
    record = image_record()
    if mode == "wrong-digest":
        record["RepoDigests"] = ["postgres@sha256:" + "0" * 64]
    response = (
        image_reply(404, ci.encode({"message": SENTINEL}))
        if mode == "missing"
        else image_reply(200, ci.encode(record))
    )
    with image_daemon(response) as endpoint:
        job.journal.record("job", "socket", endpoint)
        if mode == "replacement":
            job.journal.record("job", "cached-image", "sha256:" + "0" * 64)
        elif mode != "unplanned":
            job.journal.record("job", "pull-intent")
        monkeypatch.setattr(job, "endpoint", lambda: endpoint)
        if mode == "exact":
            assert job.verify_image_socket(bind=True) == {"id": record["Id"], "labels": {}}
        else:
            code = {
                "missing": "IMAGE_MISSING",
                "wrong-digest": "IMAGE_IDENTITY",
                "replacement": "IMAGE_REPLACED",
                "unplanned": "IMAGE_NOT_PLANNED",
            }[mode]
            with pytest.raises(ci.Refusal, match=f"^{code}$"):
                job.verify_image_socket(bind=True)
    assert job.journal.events("job").get("image") == (record["Id"] if mode == "exact" else None)


def test_listener_and_foreign_project_refusals(job, monkeypatch):
    monkeypatch.setattr(job, "checked", lambda *a, **kw: b"LISTEN 0 64 127.0.0.1:55432 *:*\n")
    monkeypatch.setattr(job, "docker", lambda *a: b"")
    with pytest.raises(ci.Refusal, match="PORT_CONFLICT"):
        job.initial_ports()

    def docker(*args):
        selector = args[-1]
        return b"foreign-id\n" if selector == "name=^pitlab-any-test_pgdata_test$" else b""

    monkeypatch.setattr(job, "docker", docker)
    with pytest.raises(ci.Refusal, match="PROJECT_PREEXISTS"):
        job.scoped_absent("pitlab-any-test")


@pytest.mark.parametrize("name", ["independent", "integration", "restoration"])
def test_init_cli_contract_real_parser(job, monkeypatch, name):
    unit, cfg = staged(job, name)

    def cli(target, args):
        parsed = d1.arguments(args)
        assert target == unit and parsed.action == "init"
        assert parsed.config == unit.root / "migrator.json"
        assert parsed.admin_config == unit.root / "admin.json"
        assert parsed.custodian_config == unit.root / "custodian.json"
        assert parsed.publisher_config == unit.root / "publisher.json"
        assert parsed.reader_config == unit.root / "reader.json"
        assert "init-intent" in job.journal.events(name)
        assert parsed.restore_only == (name == "restoration")
        assert bool(parsed.profiles_until) != parsed.restore_only
        if parsed.profiles_until is not None:
            end = ci.datetime.fromisoformat(parsed.profiles_until)
            remaining = (end - ci.datetime.now(ci.UTC)).total_seconds()
            assert 1700 < remaining <= 1800
        return {"revision": "d1_001", "marker": cfg.marker, "closed": parsed.restore_only}

    monkeypatch.setattr(job, "cli", cli)
    job.init_unit(unit, cfg)
    assert "init-done" in job.journal.events(name)


def test_seed_uses_exact_chronological_fixtures_and_verified_receipts(job, monkeypatch):
    unit, cfg = staged(job, "independent")
    receipts = []

    def cli(target, args):
        assert target == unit
        parsed = d1.arguments(args)
        assert parsed.config == unit.root / (
            "custodian.json"
            if parsed.action == "import-fixture"
            else "reader.json"
            if parsed.action == "inspect"
            else "migrator.json"
        )
        if parsed.action == "import-fixture":
            fixture = ci.FIXTURES[len(receipts)]
            profile, name, digest, size, counts = fixture
            assert parsed.publisher_config == unit.root / "publisher.json"
            assert parsed.profile == profile and parsed.file == name
            assert job.journal.events(unit.name)[f"import-intent-{profile}"] == parsed.attempt
            result = {
                "attempt": parsed.attempt,
                "observation": f"f4d1:observation:{parsed.attempt}",
                "deployment": cfg.marker,
                "profile": profile,
                "artifact": f"f4d1:artifact:sha256:{digest}",
                "byte_count": size,
                "result": "IMPORTED_UNQUALIFIED",
                "publication": "UNRESOLVED",
                "mode": "SYNTHETIC_ONLY",
                "counts": dict(
                    zip(("total", "accepted", "rejected", "excluded"), counts, strict=True)
                ),
            }
            receipts.append(result)
            return result
        inventory = {
            "class": "UNQUALIFIED_FOUNDATION",
            "mode": "SYNTHETIC_ONLY",
            "publication": "UNRESOLVED",
            "inventory": [
                {
                    "id": receipt["attempt"],
                    "profile": receipt["profile"],
                    "artifact_sha": f[2],
                    "size": f[3],
                    "receipt_sha": d1_profile.digest("receipt", receipt),
                    "result": receipt["result"],
                    **receipt["counts"],
                }
                for f, receipt in zip(ci.FIXTURES, receipts, strict=True)
            ],
            "issuers": [
                {"observation": receipts[0]["attempt"], "row_no": i, "issuer_key": str(i)}
                for i in (1, 2)
            ],
            "values": [
                {
                    "observation": receipts[1]["attempt"],
                    "row_no": i,
                    "field": "value",
                    "subject_sha": str(i) * 64,
                    "version_sha": str(i) * 64,
                }
                for i in (1, 2, 3)
            ],
        }
        if parsed.action == "inspect":
            return inventory
        return {
            "inventory_sha": d1_profile.sha(d1_profile.json_bytes(inventory)),
            "artifacts": {f[2]: f[3] for f in ci.FIXTURES},
            "bindings": {
                receipt["attempt"]: {
                    "receipt": d1_profile.digest("receipt", receipt),
                    "artifact": f[2],
                    "assertions": [[i, "value", str(i) * 64] for i in (1, 2, 3)] if index else [],
                }
                for index, (f, receipt) in enumerate(zip(ci.FIXTURES, receipts, strict=True))
            },
        }

    monkeypatch.setattr(job, "cli", cli)
    job.seed_source(unit, cfg)
    assert len({item["attempt"] for item in receipts}) == 2


def test_restoration_refuses_seeded_state_before_any_close_check(job, monkeypatch):
    unit, cfg = staged(job, "restoration")
    roles = job.role_configs(unit, cfg, job.stage_roles(unit, cfg))
    monkeypatch.setattr(job, "state", lambda unit: {"artifacts": {"fake": 1}, "bindings": {}})
    with pytest.raises(ci.Refusal, match="F4_NOT_EMPTY"):
        job.verify_empty(unit, roles)


@pytest.mark.parametrize(
    "defect", ["missing", "extra", "duplicate", "bad-json", "id", "path", "mode"]
)
def test_descriptor_refuses_before_connection(job, defect):
    for unit, ident in (("integration", "a" * 64), ("restoration", "b" * 64)):
        job.journal.record(unit, "owned", {"container": ident})
    path = job.ctx.private / ci.DESCRIPTOR
    value = job.descriptor_value()
    assert set(value) == {
        "integration",
        "independent",
        "container",
        "app_auth",
        "restoration",
        "restore_container",
    }
    if defect == "extra":
        value["extra"] = SENTINEL
    elif defect == "id":
        value["restore_container"] = "0" * 64
    elif defect == "path":
        value["app_auth"] = value["restoration"] + "/legacy-app.secret"
    raw = d1_profile.json_bytes(value)
    if defect == "duplicate":
        raw = b'{"container":"wrong",' + raw[1:]
    elif defect == "bad-json":
        raw = raw[:-1]
    if defect != "missing":
        ci.write_new(path, raw)
    if defect == "mode":
        path.chmod(0o644)
    job.journal.record("job", "descriptor", ci.sha(raw))
    with pytest.raises((ci.Refusal, d1_profile.Refusal, FileNotFoundError)):
        job.validate_descriptor()


@pytest.mark.parametrize("defect", ["app_auth", "publisher", "input"])
def test_role_files_and_secret_replacement_refused(job, defect):
    unit, cfg = staged(job, "integration")
    mappings = {
        "app_auth": unit.root / "legacy-app.secret",
        "publisher": unit.root / "publisher.json",
        "input": unit.custody / "inputs" / "issuer_fixture.csv",
    }
    ids = job.stage_roles(unit, cfg)
    file = mappings[defect]
    raw = file.read_bytes()
    file.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with pytest.raises(ci.Refusal):
        job.role_configs(unit, cfg, ids)


def test_cleanup_partial_requires_proof_and_only_calls_f1_destroy(job, monkeypatch):
    unit, _ = staged(job, "integration")
    events = job.journal.events(unit.name)
    calls = []
    monkeypatch.setattr(job, "scoped_absent", lambda project, **options: calls.append(project))
    monkeypatch.setattr(
        job,
        "f1_preflight",
        lambda *a, **kw: {"container": None, "network": "a" * 64, "volume": None},
    )
    monkeypatch.setattr(job, "life", lambda unit, action, limit: calls.append((unit.name, action)))
    job.cleanup_target(unit, events)
    assert calls == [f"pitlab-{unit.namespace}-dev", unit.project]
    events |= {"up-intent": None, "probe-done": None}
    with pytest.raises(ci.Refusal, match="UP_DISPATCH_UNCERTAIN"):
        job.cleanup_target(unit, events)
    assert not any(isinstance(call, tuple) for call in calls)
    job.cleanup_target(unit, events | {"up-refused": None})
    assert calls[-2:] == [("integration", "destroy-test"), unit.project]
    assert "destroy-done" in job.journal.events(unit.name)


def test_cleanup_continues_and_redacts_with_separate_corrupt_record(job, monkeypatch, capsys):
    job.journal.record("job", "socket", [1, 2])
    monkeypatch.setattr(job, "endpoint", lambda: [1, 2])
    leaf = job.ctx.private / "integration.jsonl"
    leaf.write_bytes(b"torn")
    attempted = []

    def clean(unit, events):
        attempted.append(unit.name)
        if unit.name == "restoration":
            raise ValueError(SENTINEL)

    monkeypatch.setattr(job, "cleanup_target", clean)
    assert job.cleanup() == 1
    assert attempted == ["restoration", "independent"]
    out = capsys.readouterr().out
    assert "JOURNAL" in out and "OPERATION_REFUSED" in out
    assert SENTINEL not in out


@pytest.mark.parametrize("status", ["running", "created", "conflicting", "absent-uncertain"])
def test_probe_partial_cleanup_uses_only_exact_identified_container(job, monkeypatch, status):
    unit, _ = staged(job, "integration")
    name = f"pitlab-ci-{unit.namespace}-probe-{'a' * 16}"
    ident = "b" * 64
    events = {"probe-create-intent": name, "probe-id": ident}
    actions = []

    def ids(given_name, given_id):
        assert (given_name, given_id) == (name, ident)
        return None if actions or status == "absent-uncertain" else ident

    def inspect(*args):
        if status == "conflicting":
            raise ci.Refusal("PROBE_SPEC")
        return status

    monkeypatch.setattr(job, "probe_ids", ids)
    monkeypatch.setattr(job, "inspect_probe", inspect)
    monkeypatch.setattr(job, "verify_image_socket", lambda: {})
    monkeypatch.setattr(job, "docker", lambda *args: actions.append(args))
    if status in {"conflicting", "absent-uncertain"}:
        with pytest.raises(ci.Refusal):
            job.cleanup_probe(unit, events)
        assert actions == []
    else:
        job.cleanup_probe(unit, events)
        expected = (
            ("container", "stop", "--time", "2") if status == "running" else ("container", "rm")
        )
        assert actions == [(*expected, ident)]


def test_worker_deadline_and_redaction(job, capsys):
    def leak():
        print(SENTINEL, flush=True)
        raise ValueError(SENTINEL)

    with pytest.raises(ci.Refusal, match="CHILD_OPERATION_REFUSED"):
        job.worker(leak, 4)
    assert SENTINEL not in str(capsys.readouterr())
    with pytest.raises(ci.Refusal, match="WORKER_TIMEOUT_UNCERTAIN"):
        job.worker(lambda: ci.time.sleep(2), 0.05)
    job.deadline = ci.uptime()
    with pytest.raises(ci.Refusal, match="DEADLINE_EXHAUSTED"):
        job.budget(15)


OBSERVER_CONTROL = """
import importlib.util
import json
import os
import sys
import pytest
spec = importlib.util.spec_from_file_location('observer_control', sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
observer = module.IntegrationObserver(int(sys.argv[2]), sys.argv[3])
rc = pytest.main(['-q', '-m', 'integration', *sys.argv[4:]], plugins=[observer])
print(json.dumps([int(rc), observer.summary()]))
"""


@pytest.mark.parametrize(
    ("case", "body", "exit_code", "flag"),
    [
        ("pass", "assert True", 0, None),
        ("skip", "pytest.skip('injected')", 0, "skipped"),
        ("xfail", "pytest.xfail('injected')", 0, "xfail_or_xpass"),
        ("xpass", "assert True", 0, "xfail_or_xpass"),
        ("failure", "assert False", 1, "failed_or_error"),
        ("teardown", "assert True", 1, "failed_or_error"),
        ("deselected", "assert True", 0, "integration_deselected"),
        ("wrong-count", "assert True", 0, None),
        ("wrong-node", "assert True", 0, None),
        ("collect-error", "assert True", 2, "collection_errors"),
    ],
)
def test_actual_pytest_observer_hooks(tmp_path, case, body, exit_code, flag):
    control = tmp_path / "control.py"
    control.write_text(OBSERVER_CONTROL)
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers = integration: offline-controls\n")
    case_file = tmp_path / "test_observer.py"
    extra_marks = "@pytest.mark.xfail(reason='injected')\n" if case == "xpass" else ""
    fixture = (
        "@pytest.fixture(autouse=True)\ndef cleanup():\n    yield\n    assert False\n"
        if case == "teardown"
        else ""
    )
    bad_collection = (
        "raise RuntimeError('injected collection failure')\n" if case == "collect-error" else ""
    )
    case_file.write_text(
        f"import pytest\n{bad_collection}{fixture}"
        f"@pytest.mark.integration\n{extra_marks}def test_subject():\n    {body}\n"
        "@pytest.mark.integration\ndef test_second():\n    assert True\n"
        "def test_ordinary():\n    assert True\n"
    )
    extra_args = ["-k", "second"] if case == "deselected" else []
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(control),
            str(ROOT / ci.HELPER),
            "1" if case == "wrong-count" else "2",
            "test_observer.py::test_missing"
            if case == "wrong-node"
            else "test_observer.py::test_subject",
            *extra_args,
        ],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTEST_ADDOPTS": ci.REDACTION},
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    real_code, summary = json.loads(result.stdout.splitlines()[-1])
    assert real_code == exit_code and summary["ok"] == (case == "pass")
    if flag:
        assert summary[flag] == (2 if case == "teardown" else 1)
    if case == "pass":
        assert summary["passed"] == summary["complete"] == summary["selected"] == 2


def test_missing_and_duplicate_phase_fails_passive_observer():
    observer = ci.IntegrationObserver(expected=1, required=ci.F4_NODE)
    item = SimpleNamespace(nodeid=ci.F4_NODE, get_closest_marker=lambda name: name)
    observer.pytest_itemcollected(item)
    observer.pytest_collection_finish(SimpleNamespace(items=[item]))
    for phase in ("setup", "call", "call"):
        observer.pytest_runtest_logreport(
            SimpleNamespace(nodeid=ci.F4_NODE, when=phase, passed=True, failed=False, skipped=False)
        )
    result = observer.summary()
    assert result["marked"] == result["selected"] == 1
    assert not result["ok"] and result["invalid_report_sequences"] == 1


def test_workflow_preserves_quality_and_guarded_steps():
    base = baseline("show", f"5fafe231b35cf68d4548e1dfdbd3f6aea27eeb74:{ci.WORKFLOW}")
    candidate = (ROOT / ci.WORKFLOW).read_bytes()
    split = b"  postgres-integration:\n"
    protected, lane = candidate.split(split, 1)
    assert protected == base.split(split, 1)[0]
    assert b"name: PostgreSQL Integration" in lane and b"timeout-minutes: 20" in lane
    assert b"fetch-depth: 0" in lane and b"persist-credentials: false" in lane
    assert lane.count(b"image pull") == 1 and ci.IMAGE.encode() in lane
    assert b"((remaining <= 120))" in lane and b"+ 870 -" in lane
    assert b"id: setup" in lane
    steps = [
        b"Record integration deadline anchor",
        b"Checkout",
        b"Verify hosted scope and acquire pinned PostgreSQL image",
        b"Generate ephemeral configuration once",
        b"Preflight Test PostgreSQL",
        b"Arm guarded legacy Test PostgreSQL",
        b"Start guarded Test PostgreSQL",
        b"Probe guarded Test PostgreSQL",
        b"Prepare guarded F4 integration targets",
        b"Run mandatory integration tests",
        b"Destroy guarded F4 test resources",
        b"Destroy guarded Test resources",
    ]
    assert sorted(steps, key=lane.index) == steps
    assert b"if: ${{ always() }}\n" in lane
    assert b"if: ${{ always() && steps.setup.outcome == 'success' }}\n" in lane
    assert b"upload-artifact" not in lane and b"continue-on-error" not in lane
    assert b"F4_D1_INTEGRATION" not in lane
    assert b"uv run --locked python scripts/ci_f4_d1.py run" in lane
    assert ci.NORMAL_SECONDS + ci.F4_CLEANUP_SECONDS + ci.LEGACY_CLEANUP_SECONDS == 1170


def test_fixture_and_guard_pins_match_protected_blobs():
    for path, oid in ci.PINS.items():
        actual = baseline("ls-tree", "5fafe231b35cf68d4548e1dfdbd3f6aea27eeb74", "--", path)
        assert actual == f"100644 blob {oid}\t{path}\n".encode()
        assert baseline("cat-file", "blob", oid) == (ROOT / path).read_bytes()
    for _, name, digest, size, _ in ci.FIXTURES:
        raw = (ROOT / ci.FIXTURE_DIR / name).read_bytes()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == (size, digest)


@pytest.mark.parametrize(
    "fault", ["nonroot", "unreadable", "stderr", "digest", "timeout", "leftover"]
)
def test_probe_failure_never_reaches_database_arm(job, monkeypatch, fault):
    unit = job.units["integration"]
    job.journal.record(unit.name, "initial-absence")
    ident = "f" * 64
    phase = {"created": False, "attached": False}
    monkeypatch.setattr(job, "verify_image_socket", lambda **kwargs: {})
    monkeypatch.setattr(job, "scoped_absent", lambda *args, **kwargs: None)
    monkeypatch.setattr(job, "f1_preflight", lambda *args, **kwargs: None)
    # Setup is the only worker in arm(); it uses the real parser and writes only scratch files.
    monkeypatch.setattr(job, "worker", lambda action, limit: action())
    monkeypatch.setattr(job, "inspect_probe", lambda *args: "created")

    def docker(*args, **kwargs):
        assert args[:2] == ("container", "create")
        assert "probe-create-intent" in job.journal.events(unit.name)
        phase["created"] = True
        return (ident + "\n").encode()

    def ids(name, full_id=None):
        assert not full_id or full_id == ident
        return (
            ident if phase["created"] and (not phase["attached"] or fault == "leftover") else None
        )

    def command(args, *, limit):
        assert args == ["docker", "container", "start", "--attach", ident]
        assert limit == 25
        phase["attached"] = True
        if fault == "timeout":
            raise ci.Refusal("COMMAND_TIMEOUT_UNCERTAIN")
        good = f"{ci.BOOTSTRAP_SHA}  {ci.DEST}\n".encode()
        if fault == "nonroot":
            return 41, b"", b""
        if fault == "unreadable":
            return 42, b"", b""
        if fault == "stderr":
            return 0, good, SENTINEL.encode()
        if fault == "digest":
            return 0, b"0" * 64 + good[64:], b""
        return 0, good, b""

    monkeypatch.setattr(job, "docker", docker)
    monkeypatch.setattr(job, "probe_ids", ids)
    monkeypatch.setattr(job, "command", command)
    with pytest.raises(ci.Refusal):
        job.arm(unit)
    events = job.journal.events(unit.name)
    assert "probe-create-intent" in events and "probe-start-intent" in events
    assert "probe-done" not in events and "up-intent" not in events


def test_descriptor_reconciles_four_distinct_live_bindings(job, monkeypatch):
    legacy = replace(job.units["legacy"], root=job.ctx.private / "offline-legacy")
    job.units["legacy"] = legacy
    ids = {}
    for index, name in enumerate(ci.UNITS, 1):
        unit, cfg = staged(job, name)
        if name != "legacy":
            bindings = job.stage_roles(unit, cfg)
            job.journal.record(name, "roles", bindings)
            job.journal.record(name, "init-done")
            job.journal.record(name, "unit-ready")
        ids[name] = {
            "container": str(index) * 64,
            "network": str(index + 4) * 64,
            "volume": [unit.project + "_pgdata_test", "synthetic"],
        }
        job.journal.record(name, "owned", ids[name])
    monkeypatch.setattr(job, "live", lambda unit: ids[unit.name])
    raw = d1_profile.json_bytes(job.descriptor_value())
    ci.write_new(job.ctx.private / ci.DESCRIPTOR, raw)
    job.journal.record("job", "descriptor", ci.sha(raw))
    assert job.validate_descriptor() == job.ctx.private / ci.DESCRIPTOR
    ids["legacy"]["network"] = ids["integration"]["network"]
    with pytest.raises(ci.Refusal, match="LIVE_TARGET_COLLISION"):
        job.validate_descriptor()


@pytest.mark.parametrize(
    ("pytest_exit", "ok", "expected"), [(0, True, 0), (0, False, 10), (2, False, 2)]
)
def test_pytest_step_exit_reconciliation(job, monkeypatch, pytest_exit, ok, expected):
    for unit in ci.F4_UNITS:
        staged(job, unit)
    monkeypatch.setattr(
        job, "validate_descriptor", lambda **kwargs: job.ctx.private / ci.DESCRIPTOR
    )

    def worker(action, limit):
        assert callable(action) and limit == 180
        assert "pytest-intent" in job.journal.events("job")
        return pytest_exit, {"ok": ok}

    def clean():
        if pytest_exit:
            raise ci.Refusal("CHECKOUT_DIRTY")

    monkeypatch.setattr(job, "worker", worker)
    monkeypatch.setattr(job, "clean", clean)
    assert job.test() == expected
    assert job.journal.events("job")["pytest-result"] == [pytest_exit, {"ok": ok}]


def test_image_binding_records_only_verified_id(job, monkeypatch):
    job.journal.record("job", "socket", [1, 2])
    job.journal.record("job", "pull-intent")
    identity = "sha256:" + "0" * 64
    image = {"id": identity, "labels": {"unrelated-image-label": SENTINEL}}
    monkeypatch.setattr(job, "endpoint", lambda: [1, 2])
    monkeypatch.setattr(job, "image", lambda endpoint: image)
    assert job.verify_image_socket(bind=True) == image
    assert job.journal.events("job")["image"] == identity
    assert SENTINEL.encode() not in (job.ctx.private / "job.jsonl").read_bytes()
    image["id"] = "sha256:" + "1" * 64
    with pytest.raises(ci.Refusal, match="IMAGE_REPLACED"):
        job.verify_image_socket()


DEADLINE_STEPS = (
    "Verify uv version",
    "Sync locked dependencies",
    "Verify project Python version",
    "Verify runner prerequisites",
    "Verify hosted scope and acquire pinned PostgreSQL image",
    "Generate ephemeral configuration once",
    "Verify configuration file metadata",
    "Preflight Test PostgreSQL",
    "Arm guarded legacy Test PostgreSQL",
    "Start guarded Test PostgreSQL",
    "Probe guarded Test PostgreSQL",
    "Prepare guarded F4 integration targets",
    "Run mandatory integration tests",
    "Destroy guarded F4 test resources",
    "Destroy guarded Test resources",
)
PREFLIGHT_STEP = DEADLINE_STEPS[4]
INTEGRATION_STEP = DEADLINE_STEPS[-3]


def deadline_workflow():
    lane = (ROOT / ci.WORKFLOW).read_text().split("  postgres-integration:\n", 1)[1]
    clock = lane.split("      F4_CI_CLOCK: |\n", 1)[1].split("    steps:\n", 1)[0]
    clock = "\n".join(row[8:] for row in clock.splitlines())
    blocks = {}
    for section in lane.split("      - name: ")[1:]:
        name, body = section.split("\n", 1)
        if "        run: |\n" in body:
            run = body.split("        run: |\n", 1)[1]
            blocks[name] = "\n".join(row[10:] for row in run.splitlines()) + "\n"
    return clock, blocks


UPTIME_INPUT = "< /proc/uptime"
ANCHOR_STEP = "Record integration deadline anchor"


def adapt_uptime(body, reader, expected_read=None):
    from shlex import quote

    assert reader.is_absolute()
    assert [line.strip() for line in body.splitlines() if "/proc/uptime" in line] == (
        [] if expected_read is None else [expected_read]
    )
    replacement = f"< <({quote(str(reader))})"
    expected = int(expected_read is not None)
    assert body.count(UPTIME_INPUT) == expected and replacement not in body
    adapted = body.replace(UPTIME_INPUT, replacement)
    assert adapted.count(replacement) == expected
    assert adapted.replace(replacement, UPTIME_INPUT) == body
    return adapted


class ScenarioUptime:
    def __init__(self, directory):
        self.reader = directory / "read-uptime"
        self.state = directory / "uptime-state"
        self.reader.write_text(
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            "from time import monotonic_ns\n"
            "base, epoch = map(int, Path(__file__).with_name('uptime-state').read_text().split())\n"
            "ticks = base + ((monotonic_ns() - epoch) // 10_000_000 if epoch else 0)\n"
            "print(f'{ticks // 100}.{ticks % 100:02d} 0.00')\n"
        )
        self.reader.chmod(0o700)

    def start(self, raw_age, *, advancing=False):
        from time import monotonic_ns

        # The offset makes historical anchors representable even at simulated boot.
        seconds = 2_000 + raw_age
        epoch = monotonic_ns() if advancing else 0
        self.state.write_text(f"{seconds * 100 + 37} {epoch}\n")
        return seconds

    def read(self):
        raw = subprocess.check_output([str(self.reader)], text=True, timeout=3)
        return float(raw.split()[0])


@pytest.fixture
def scenario_uptime(tmp_path):
    return ScenarioUptime(tmp_path)


PROCESS_RECEIPT = r"""
import os
from pathlib import Path

def register_process(path):
    pid = os.getpid()
    start = Path("/proc/self/stat").read_text().rsplit(") ", 1)[1].split()[19]
    pending = path.with_suffix(".ownership.tmp")
    identity = f"{pid} {start}"
    pending.write_text(identity)
    pending.replace(path.with_suffix(".ownership"))
    path.write_text(str(pid))
    return identity
"""


def shell_step(body, env, *, cwd=ROOT, timeout=12):
    return subprocess.run(
        ["/usr/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", body],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


LAUNCHER_STUB = (
    PROCESS_RECEIPT
    + r"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["SHIM_STATE"])
with (root / "argv").open("a") as out:
    out.write(json.dumps([Path(sys.argv[0]).name, sys.argv[1:],
                          os.environ.get("F4_CI_CLEANUP_STARTED")]) + "\n")
mode = os.environ.get("SHIM_MODE")
if mode == "preflight-refusal":
    print("injected-raw-decision")
    raise SystemExit(23)
if mode == "pull" and Path(sys.argv[0]).name == "uv":
    print("IMAGE_ACQUISITION_REQUIRED")
elif mode == "pull":
    print("injected-docker-output")
    raise SystemExit(29)
elif mode in {"stall", "resist"}:
    if mode == "resist":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    grandchild = Path(__file__).with_name("owned-dummy.py")
    register_process(root / "child")
    (root / "child.pgid").write_text(str(os.getpgrp()))
    child = subprocess.Popen([sys.executable, str(grandchild), str(root / "grandchild")])
    child.wait()
elif mode == "exit":
    raise SystemExit(37)
"""
)


OWNED_DUMMY = (
    PROCESS_RECEIPT
    + r"""
import signal
import sys
import time

signal.signal(signal.SIGTERM, signal.SIG_IGN)
marker = Path(sys.argv[1])
identity = register_process(marker)
Path(sys.argv[1] + ".pgid").write_text(str(os.getpgrp()))
stop = marker.with_suffix(".stop")
expiry = time.monotonic() + 30
while time.monotonic() < expiry and not (marker.parent / "end-dummy-processes").exists():
    if stop.exists() and stop.read_text() == identity:
        break
    time.sleep(0.02)
"""
)


@pytest.fixture
def deadline_shell(tmp_path, scenario_uptime):
    clock, steps = deadline_workflow()
    reads = {
        ANCHOR_STEP: "read -r uptime _ < /proc/uptime",
        **{name: "IFS=' ' read -r ci_entry _ < /proc/uptime" for name in DEADLINE_STEPS[-2:]},
    }
    reader = scenario_uptime.reader
    steps = {name: adapt_uptime(body, reader, reads.get(name)) for name, body in steps.items()}
    clock = adapt_uptime(clock, reader, "if ! IFS=' ' read -r clock _ < /proc/uptime ||")
    tools = tmp_path / "bin"
    tools.mkdir()
    gnu = Path("/usr/bin/gnutimeout")
    if not gnu.exists():
        gnu = Path("/usr/bin/timeout")
    (tools / "timeout").symlink_to(gnu)
    for name in ("uv", "docker", "python"):
        shim = tools / name
        shim.write_text(f"#!{sys.executable}\n{LAUNCHER_STUB}")
        shim.chmod(0o700)
    (tools / "owned-dummy.py").write_text(OWNED_DUMMY)
    env = {
        "HOME": str(tmp_path),
        "PATH": f"{tools}:/usr/bin:/bin",
        "F4_CI_CLOCK": clock,
        "F4_CI_STARTED": str(scenario_uptime.start(0)),
        "SHIM_STATE": str(tmp_path),
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    try:
        yield env, steps
    finally:
        # Only these dummy scripts read this private marker. It also covers a
        # child that had not published its identity when the test failed.
        (tmp_path / "end-dummy-processes").touch()
        for name in ("grandchild", "owned-grandchild", "worker", "child", "helper"):
            stop_owned_process(tmp_path / name)


def captured_launches(env):
    path = Path(env["SHIM_STATE"]) / "argv"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize(
    ("anchor", "code"),
    [
        (None, "INVALID_ANCHOR"),
        ("001x", "INVALID_ANCHOR"),
        ("1+870", "INVALID_ANCHOR"),
        ("-1", "INVALID_ANCHOR"),
        ("future", "FUTURE_ANCHOR"),
        ("exhausted", "DEADLINE_EXHAUSTED"),
        ("zero-duration", "DEADLINE_EXHAUSTED"),
    ],
)
def test_normal_deadline_refuses_before_dispatch(deadline_shell, scenario_uptime, anchor, code):
    env, steps = deadline_shell
    now = int(scenario_uptime.read())
    if anchor is None:
        env.pop("F4_CI_STARTED")
    else:
        env["F4_CI_STARTED"] = {
            "future": str(now + 10),
            "exhausted": str(now - ci.NORMAL_SECONDS),
            "zero-duration": str(now - ci.NORMAL_SECONDS + 4),
        }.get(anchor, anchor)
    result = shell_step(steps[INTEGRATION_STEP], env)
    assert result.returncode == 1 and code in result.stderr
    assert not captured_launches(env)


def test_every_step_body_uses_deadline_gate_and_valid_shell(deadline_shell):
    env, steps = deadline_shell
    assert list(steps)[1:] == list(DEADLINE_STEPS)
    original_clock, original_steps = deadline_workflow()
    syntax = shell_step(
        '/usr/bin/bash -n <<< "$F4_CI_CLOCK"', env | {"F4_CI_CLOCK": original_clock}
    )
    assert syntax.returncode == 0
    for name, block in original_steps.items():
        parse = subprocess.run(
            ["/usr/bin/bash", "--noprofile", "--norc", "-n"],
            input=block,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        assert parse.returncode == 0, (name, parse.stderr)
    env.pop("F4_CI_STARTED")
    for name in DEADLINE_STEPS:
        result = shell_step(steps[name], env)
        assert result.returncode == 1 and "INVALID_ANCHOR" in result.stderr, name
    assert not captured_launches(env)


def test_post_sync_deadline_launches_exact_locked_no_sync_argv(deadline_shell):
    env, steps = deadline_shell
    for name in (*DEADLINE_STEPS[1:3], *DEADLINE_STEPS[4:6], *DEADLINE_STEPS[7:]):
        result = shell_step(steps[name], env, cwd=Path(env["SHIM_STATE"]))
        if name == PREFLIGHT_STEP:
            assert "IMAGE_DECISION_REFUSED" in result.stderr
        else:
            assert result.returncode == 0, (name, result.stderr)
    launched = captured_launches(env)
    assert launched[0] == ["uv", ["sync", "--locked", "--python", "3.12"], None]
    assert all(
        call[0] == "uv" and call[1][:4] == ["run", "--locked", "--no-sync", "--offline"]
        for call in launched[1:]
    )
    assert [call[1][-1] for call in launched[-3:]] == ["run", "cleanup", "cleanup-legacy"]
    assert all(call[2] is None for call in launched[:-2])
    assert all(call[2].isdigit() for call in launched[-2:])


@pytest.mark.parametrize(
    ("mode", "step", "status", "code"),
    [
        ("exit", INTEGRATION_STEP, 37, ""),
        ("preflight-refusal", PREFLIGHT_STEP, 23, ""),
        ("pull", PREFLIGHT_STEP, 29, "PINNED_IMAGE_PULL_REFUSED"),
    ],
)
def test_launch_status_and_substitution_are_preserved(deadline_shell, mode, step, status, code):
    env, steps = deadline_shell
    result = shell_step(steps[step], env | {"SHIM_MODE": mode})
    assert result.returncode == status
    assert code in result.stderr
    assert "injected-" not in result.stdout + result.stderr
    launched = captured_launches(env)
    assert [item[0] for item in launched] == (["uv", "docker"] if mode == "pull" else ["uv"])
    if mode == "pull":
        assert launched[-1][1] == ["--context", "default", "image", "pull", "--quiet", ci.IMAGE]


@pytest.mark.parametrize("outcome", ["cached", "acquired", "pull-timeout"])
def test_workflow_only_pulls_after_exact_absence(deadline_shell, scenario_uptime, outcome):
    env, steps = deadline_shell
    tools = Path(env["SHIM_STATE"]) / "bin"
    decision = "IMAGE_PRESENT" if outcome == "cached" else "IMAGE_ACQUISITION_REQUIRED"
    launch_log = LAUNCHER_STUB.split('mode = os.environ.get("SHIM_MODE")', 1)[0]
    header = f"#!{sys.executable}\n{launch_log}"
    (tools / "uv").write_text(header + f"print({decision!r})\n")
    delay = "import time\ntime.sleep(15)\n" if outcome == "pull-timeout" else ""
    (tools / "docker").write_text(header + delay)
    if outcome == "pull-timeout":
        now = scenario_uptime.start(0, advancing=True)
        env["F4_CI_STARTED"] = str(now - ci.NORMAL_SECONDS + 7)
    result = shell_step(steps[PREFLIGHT_STEP], env)
    launches = captured_launches(env)
    if outcome == "cached":
        assert result.returncode == 0 and result.stdout == "IMAGE_PRESENT\n"
        assert [item[0] for item in launches] == ["uv"]
    else:
        assert [item[0] for item in launches] == ["uv", "docker"]
        assert launches[-1][1] == ["--context", "default", "image", "pull", "--quiet", ci.IMAGE]
        if outcome == "acquired":
            assert (
                result.returncode == 0
                and result.stdout == "phase=image code=PINNED_IMAGE_ACQUIRED\n"
            )
        else:
            assert result.returncode != 0 and "ACQUIRED" not in result.stdout
            assert (
                "PINNED_IMAGE_PULL_REFUSED" in result.stderr
                or "LAUNCH_TIMEOUT_UNCERTAIN" in result.stderr
            )


def owned_process_state(pid, start):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    except FileNotFoundError:
        return None
    return fields[0] if fields[19] == start else None


def active_process(path):
    if not path.exists():
        pytest.fail(f"owned dummy process did not record {path.name}")
    pid, start = path.with_suffix(".ownership").read_text().split()
    assert path.read_text() == pid
    return owned_process_state(int(pid), start) not in {None, "Z", "X"}


def stop_owned_process(path):
    from time import monotonic, sleep

    receipt = path.with_suffix(".ownership")
    if not receipt.exists():
        return
    identity = receipt.read_text()
    recorded_pid, start = identity.split()
    pid = int(recorded_pid)
    if owned_process_state(pid, start) in {None, "Z", "X"}:
        return
    path.with_suffix(".stop").write_text(identity)
    expiry = monotonic() + 1
    while owned_process_state(pid, start) not in {None, "Z", "X"}:
        assert monotonic() < expiry, f"owned dummy process did not exit: {path.name}"
        sleep(0.02)


@pytest.mark.parametrize(
    ("step", "mode"), [(INTEGRATION_STEP, "stall"), (PREFLIGHT_STEP, "resist")]
)
def test_outer_deadline_stops_launcher_and_grandchild_before_helper_entry(
    deadline_shell, scenario_uptime, step, mode
):
    from time import monotonic

    env, steps = deadline_shell
    root = Path(env["SHIM_STATE"])
    now = scenario_uptime.start(0, advancing=True)
    env.update(F4_CI_STARTED=str(now - ci.NORMAL_SECONDS + 6), SHIM_MODE=mode)
    clock_start = scenario_uptime.read()
    start = monotonic()
    result = shell_step(steps[step], env)
    elapsed = monotonic() - start
    assert scenario_uptime.read() - clock_start == pytest.approx(elapsed, abs=0.15)
    assert result.returncode in (124, 137) and "LAUNCH_TIMEOUT_UNCERTAIN" in result.stderr
    assert not active_process(root / "child") and not active_process(root / "grandchild")
    assert (root / "child.pgid").read_text() == (root / "grandchild.pgid").read_text()
    assert int((root / "child.pgid").read_text()) != os.getpgrp()
    assert elapsed <= 6.1
    assert [c[0] for c in captured_launches(env)] == ["uv"]


@pytest.mark.parametrize(
    ("phase", "entry_age", "job_age", "remaining"),
    [
        ("f4", 0, 50, 175),
        ("legacy", 0, 50, 25),
        ("f4", 50, 100, 175),
        ("f4", 890, 900, 195),
        ("legacy", 1100, 1120, 50),
        ("f4", 1093, 1095, 0),
        ("legacy", 1168, 1171, -1),
    ],
)
def test_cleanup_clock_external_entry_and_absolute_cap(
    deadline_shell, scenario_uptime, phase, entry_age, job_age, remaining
):
    env, _ = deadline_shell
    now = int(scenario_uptime.read())
    anchor = now - job_age
    entered = anchor + entry_age
    env["F4_CI_STARTED"] = str(anchor)
    result = shell_step(
        f"""source /dev/stdin <<< "$F4_CI_CLOCK"
ci_entry={entered}.00
ci_remaining {phase}
printf '%s %s\n' "$remaining" "$F4_CI_CLEANUP_STARTED"
ci_duration
printf '%s\n' "$duration"
""",
        env,
    )
    data = result.stdout.splitlines()
    got, got_entry = map(int, data[0].split())
    assert got_entry == entered and got == remaining
    if remaining <= 4:
        assert result.returncode == 1 and "DEADLINE_EXHAUSTED" in result.stderr
    else:
        assert result.returncode == 0 and int(data[1]) == got - 4


def test_cleanup_failure_does_not_consume_independent_later_launch(deadline_shell, scenario_uptime):
    env, steps = deadline_shell
    first, second = DEADLINE_STEPS[-2:]
    result = shell_step(steps[first], env | {"SHIM_MODE": "exit"})
    assert result.returncode == 37
    result = shell_step(steps[second], env)
    assert result.returncode == 0
    assert [c[1][-1] for c in captured_launches(env)] == ["cleanup", "cleanup-legacy"]
    assert all(c[2] is not None for c in captured_launches(env))
    prior = len(captured_launches(env))
    env["F4_CI_STARTED"] = str(int(scenario_uptime.read()) - 1170)
    for name in (first, second):
        result = shell_step(steps[name], env)
        assert result.returncode == 1 and "DEADLINE_EXHAUSTED" in result.stderr
    assert len(captured_launches(env)) == prior


@pytest.mark.parametrize(
    ("verb", "entry_age", "expected"), [("cleanup", 40, 265), ("cleanup-legacy", 1130, 1170)]
)
def test_python_cleanup_uses_step_entry_and_spends_launcher_delay(
    job, monkeypatch, verb, entry_age, expected
):
    monkeypatch.setattr(ci, "uptime", lambda: job.ctx.started + entry_age + 20)
    with pytest.raises(ci.Refusal, match="INVALID_PHASE_ENTRY"):
        ci.HostedJob(job.ctx, verb, job.env["HOME"])
    cleanup = ci.HostedJob(
        job.ctx, verb, job.env["HOME"], phase_started=job.ctx.started + entry_age
    )
    assert cleanup.deadline == job.ctx.started + expected - ci.INNER_HEADROOM_SECONDS
    assert cleanup.budget(225) == pytest.approx(
        expected - entry_age - 20 - ci.INNER_HEADROOM_SECONDS - 0.6
    )


SUPERVISION_CONTROL = (
    PROCESS_RECEIPT
    + r"""
import importlib.util
import os
import signal
import subprocess
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("deadline_control_ci", sys.argv[1])
ci = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ci
spec.loader.exec_module(ci)
root, mode = Path(sys.argv[2]), sys.argv[3]
# The outer scenario clock ends at the shell. The dummy helper uses a fresh
# real-uptime context and never admits the adapted workflow environment.
outer_anchor = os.environ.pop("F4_CI_STARTED")
assert "F4_CI_CLEANUP_STARTED" not in os.environ
inner_started = int(ci.uptime())
ctx = ci.JobContext(root, root, "a" * 40, "a" * 40, "refs/heads/main",
                    None, "offline", "1:1", inner_started)
job = ci.HostedJob(ctx, "prepare", str(root))
signal.signal(signal.SIGTERM, ci.interrupted)
signal.signal(signal.SIGINT, ci.interrupted)
register_process(root / "helper")
(root / "helper.pgid").write_text(str(os.getpgrp()))
(root / "clock-sources").write_text(ci.encode([outer_anchor, job.ctx.started, job.budget(30)]).decode())
command = [sys.executable, str(root / "bin/owned-dummy.py"), str(root / "owned-grandchild")]

def hold():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    register_process(root / "worker")
    child = subprocess.Popen(command)
    child.wait()

try:
    if mode == "worker":
        job.worker(hold, 30)
    else:
        job.command(command, limit=30)
except ci.Refusal as exc:
    (root / "refusal").write_text(ci.safe_code(exc))
    try:
        job.budget(2)
    except ci.Refusal as followup:
        (root / "after").write_text(ci.safe_code(followup))
    raise SystemExit(41)
"""
)


@pytest.mark.parametrize("mode", ["command", "worker"])
def test_outer_timeout_with_actual_locked_uv_quiesces_private_helper_group(
    deadline_shell, scenario_uptime, tmp_path, mode
):
    from shutil import which
    from time import monotonic

    env, _ = deadline_shell
    uv = which("uv")
    assert uv, "the locked uv launcher is required"
    shim = tmp_path / "bin/uv"
    shim.unlink()
    shim.symlink_to(Path(uv).resolve())
    control = tmp_path / "control.py"
    control.write_text(SUPERVISION_CONTROL)
    now = scenario_uptime.start(30, advancing=True)
    env.update(
        F4_CI_STARTED=str(now - ci.NORMAL_SECONDS + 7),
        UV_OFFLINE="1",
        UV_CACHE_DIR=str(tmp_path / "uv-cache"),
        PYTHONDONTWRITEBYTECODE="1",
        CONTROL=str(control),
        CI_SOURCE=str(ROOT / ci.HELPER),
        CONTROL_MODE=mode,
    )
    clock_start = scenario_uptime.read()
    real_start = int(ci.uptime())
    start = monotonic()
    result = shell_step(
        """source /dev/stdin <<< "$F4_CI_CLOCK"
ci_uv run --locked python "$CONTROL" "$CI_SOURCE" "$SHIM_STATE" "$CONTROL_MODE"
""",
        env,
    )
    assert result.returncode in (124, 137) and "LAUNCH_TIMEOUT_UNCERTAIN" in result.stderr
    elapsed = monotonic() - start
    assert scenario_uptime.read() - clock_start == pytest.approx(elapsed, abs=0.15)
    outer_anchor, inner_started, inner_budget = json.loads((tmp_path / "clock-sources").read_text())
    assert outer_anchor == env["F4_CI_STARTED"]
    assert real_start <= inner_started <= int(ci.uptime()) and inner_budget == 30
    assert (tmp_path / "refusal").read_text() == "STEP_INTERRUPTED_UNCERTAIN"
    assert (tmp_path / "after").read_text() == "STEP_INTERRUPTED_UNCERTAIN"
    assert not active_process(tmp_path / "owned-grandchild")
    expected_group = tmp_path / ("worker" if mode == "worker" else "owned-grandchild")
    if mode == "worker":
        assert not active_process(expected_group)
    group = (tmp_path / "owned-grandchild.pgid").read_text()
    assert group == expected_group.read_text()
    assert group != (tmp_path / "helper.pgid").read_text()


def test_late_f4_cleanup_timeout_preserves_legacy_cleanup_attempt(deadline_shell, scenario_uptime):
    from time import monotonic

    env, steps = deadline_shell
    root = Path(env["SHIM_STATE"])
    now = scenario_uptime.start(59, advancing=True)
    env["F4_CI_STARTED"] = str(now - 1095 + 6)
    clock_start = scenario_uptime.read()
    start = monotonic()
    f4_step, legacy_step = DEADLINE_STEPS[-2:]
    f4_result = shell_step(steps[f4_step], env | {"SHIM_MODE": "resist"})
    assert f4_result.returncode in (124, 137)
    assert "LAUNCH_TIMEOUT_UNCERTAIN" in f4_result.stderr
    elapsed = monotonic() - start
    assert elapsed <= 6.1
    assert scenario_uptime.read() - clock_start == pytest.approx(elapsed, abs=0.15)
    assert not active_process(root / "child") and not active_process(root / "grandchild")
    assert shell_step(steps[legacy_step], env).returncode == 0
    f4_launch, legacy_launch = captured_launches(env)
    assert [call[1][-1] for call in (f4_launch, legacy_launch)] == ["cleanup", "cleanup-legacy"]
    assert int(f4_launch[2]) < int(legacy_launch[2])


def test_deadline_pin_mutations_fail_in_memory(monkeypatch):
    rs2 = "tests/unit/cap_f2_v1_a06_ic3_rs2/b01_preservation.py"
    b01 = load_script("ci_deadline_b01", ROOT / rs2)
    b03 = load_script("ci_deadline_b03", ROOT / "tests/unit/cap_f2_b03/test_b03_preservation.py")
    for name in (ci.WORKFLOW, rs2):
        b03.verify_baseline_path(ROOT, name)
    original = Path.read_bytes
    for name in (ci.WORKFLOW, rs2):
        with monkeypatch.context() as scope:
            scope.setattr(
                Path,
                "read_bytes",
                lambda path, name=name: (
                    original(path) + b"\n# injected\n" if path == ROOT / name else original(path)
                ),
            )
            with pytest.raises(AssertionError, match="BASELINE_PIN_MISMATCH"):
                b03.verify_baseline_path(ROOT, name)
            if name == ci.WORKFLOW:
                history = baseline("show", f"{b01.FROZEN}:{name}")
                with pytest.raises(AssertionError, match="B01_CURRENT_PIN_MISMATCH"):
                    b01.verify_preserved(
                        ROOT, name, len(history), hashlib.sha256(history).hexdigest()
                    )


@pytest.mark.parametrize("raw_age", [0, 30, 59, 300, 1180])
def test_deadline_guards_on_simulated_host_age(deadline_shell, scenario_uptime, raw_age):
    env, steps = deadline_shell
    now = scenario_uptime.start(raw_age)
    assert scenario_uptime.read() == pytest.approx(now + 0.37)
    scenarios = (
        (INTEGRATION_STEP, 0, None, 0, None),
        (INTEGRATION_STEP, 870, None, 1, "DEADLINE_EXHAUSTED"),
        (INTEGRATION_STEP, 866, None, 1, "DEADLINE_EXHAUSTED"),
        (DEADLINE_STEPS[-2], 1089, None, 0, None),
        (DEADLINE_STEPS[-1], 1170, None, 1, "DEADLINE_EXHAUSTED"),
        (DEADLINE_STEPS[-1], 1171, None, 1, "DEADLINE_EXHAUSTED"),
        (INTEGRATION_STEP, -1, None, 1, "FUTURE_ANCHOR"),
        (INTEGRATION_STEP, 0, "1+870", 1, "INVALID_ANCHOR"),
        (INTEGRATION_STEP, 0, "-1", 1, "INVALID_ANCHOR"),
    )
    for name, age, invalid, status, code in scenarios:
        anchor = now - age
        assert anchor >= 0
        launched = len(captured_launches(env))
        result = shell_step(steps[name], env | {"F4_CI_STARTED": invalid or str(anchor)})
        assert result.returncode == status, (raw_age, name, age, result.stderr)
        if code:
            assert code in result.stderr
        assert len(captured_launches(env)) == launched + (status == 0)
    assert [call[2] for call in captured_launches(env)] == [None, str(now)]


def test_unadapted_production_uptime_positive_and_negative_smoke(deadline_shell, tmp_path):
    env, _ = deadline_shell
    clock, steps = deadline_workflow()
    env_file = tmp_path / "github-env"
    original_env = env | {"F4_CI_CLOCK": clock, "GITHUB_ENV": str(env_file)}
    before = int(ci.uptime())
    assert shell_step(steps[ANCHOR_STEP], original_env).returncode == 0
    key, anchor = env_file.read_text().strip().split("=", 1)
    assert key == "F4_CI_STARTED" and before <= int(anchor) <= int(ci.uptime())
    original_env[key] = anchor
    assert shell_step(steps[INTEGRATION_STEP], original_env).returncode == 0
    assert shell_step(steps[DEADLINE_STEPS[-2]], original_env).returncode == 0
    assert [call[1][-1] for call in captured_launches(env)] == ["run", "cleanup"]
    result = shell_step(steps[INTEGRATION_STEP], original_env | {key: "-1"})
    assert result.returncode == 1 and "INVALID_ANCHOR" in result.stderr
    assert len(captured_launches(env)) == 2


def test_uptime_adapter_refuses_unexpected_read_shape_or_count(scenario_uptime):
    expected = "read -r uptime _ < /proc/uptime"
    for changed in (
        "",
        expected + "\n" + expected,
        expected.replace("uptime _", "clock _"),
        expected + "\ncat /proc/uptime",
    ):
        with pytest.raises(AssertionError):
            adapt_uptime(changed, scenario_uptime.reader, expected)


def test_process_fallback_stops_only_the_recorded_identity(deadline_shell, tmp_path):
    from time import monotonic, sleep

    marker = tmp_path / "child"
    script = tmp_path / "bin/owned-dummy.py"
    with subprocess.Popen([sys.executable, str(script), str(marker)]) as child:
        try:
            deadline = monotonic() + 3
            while not marker.exists() or not marker.read_text():
                assert monotonic() < deadline, "owned dummy did not start"
                sleep(0.01)
            assert active_process(marker)
            receipt = marker.with_suffix(".ownership")
            pid, ticks = receipt.read_text().split()
            receipt.write_text(f"{pid} {int(ticks) + 1}")
            stop_owned_process(marker)
            assert child.poll() is None
            receipt.write_text(f"{pid} {ticks}")
            stop_owned_process(marker)
            assert child.wait(timeout=2) == 0
            assert not active_process(marker)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2)
