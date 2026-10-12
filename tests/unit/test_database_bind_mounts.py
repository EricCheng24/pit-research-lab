"""Offline Desktop mount identity and bounded, stopped-container read regressions."""

import copy
import gzip
import io
import json
import subprocess
import sys
import tarfile

import pytest
from test_database_config import config_values
from test_database_safety import ROOT, operator, resources

from pit_research_lab.infrastructure.database.config import PersistenceError, parse_config

PREFIX = "/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/Ubuntu/"
TRANSLATED = PREFIX + "a" * 64
BOOTSTRAP = (ROOT / "scripts/init-postgres.sh").read_bytes()


def archive_bytes(content=BOOTSTRAP, *, name="10-pitlab.sh", kind=tarfile.REGTYPE, extra=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:") as tar:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.size = len(content) if kind == tarfile.REGTYPE else 0
        member.linkname = "elsewhere" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
        tar.addfile(member, io.BytesIO(content))
        if extra:
            tar.addfile(tarfile.TarInfo("unexpected"))
    return output.getvalue()


@pytest.mark.parametrize("target", ["dev", "test"])
@pytest.mark.parametrize("source", [None, TRANSLATED])
@pytest.mark.parametrize("running", [False, True])
def test_direct_and_translated_source_identity(monkeypatch, target, source, running):
    config = parse_config(config_values(target), target)
    groups = resources(config)
    container = groups[0][0]
    container["Running"] = running
    if source:
        container["Mounts"][1]["Source"] = source
    reads = []

    def read(container_id, environ):
        reads.append(container_id)
        return archive_bytes()

    monkeypatch.setattr(operator, "bootstrap_archive", read)
    operator.verify_resources(
        config,
        *groups,
        ROOT,
        bootstrap_verifier=lambda c: operator.verify_bootstrap_content(c, ROOT, {}),
    )
    assert reads == ([container["Id"]] if source else [])


def test_translated_prefix_without_content_proof_refuses():
    config = parse_config(config_values(), "test")
    groups = resources(config)
    groups[0][0]["Mounts"][1]["Source"] = TRANSLATED
    with pytest.raises(PersistenceError, match="unverified"):
        operator.verify_resources(config, *groups, ROOT)


@pytest.mark.parametrize(
    "source",
    [
        "/tmp/foreign-init.sh",
        PREFIX + "foreign",
        TRANSLATED + "/other.sh",
        PREFIX + "../" + "a" * 64,
        PREFIX + "a" * 63,
        None,
    ],
)
def test_foreign_source_cannot_use_matching_content(source):
    config = parse_config(config_values(), "test")
    groups = resources(config)
    groups[0][0]["Mounts"][1]["Source"] = source
    with pytest.raises(PersistenceError, match="Foreign bootstrap"):
        operator.verify_resources(
            config,
            *groups,
            ROOT,
            bootstrap_verifier=lambda c: pytest.fail("Read foreign mount before refusal"),
        )


@pytest.mark.parametrize(
    "fault",
    [
        "destination",
        "writable",
        "missing-ro",
        "type",
        "volume",
        "data-directory",
        "image",
        "label",
        "network",
        "consumer",
        "missing-volume",
    ],
)
def test_translated_source_preserves_all_metadata_checks(fault):
    config = parse_config(config_values(), "test")
    groups = resources(config)
    container = groups[0][0]
    data, bind = container["Mounts"]
    bind["Source"] = TRANSLATED
    if fault == "destination":
        bind["Destination"] = "/tmp/init.sh"
    elif fault == "writable":
        bind["RW"] = True
    elif fault == "missing-ro":
        del bind["RW"]
    elif fault == "type":
        bind["Type"] = "volume"
    elif fault == "volume":
        data["Name"] = "foreign"
    elif fault == "data-directory":
        data["Destination"] = "/tmp/data"
    elif fault == "image":
        container["Image"] = "postgres:latest"
    elif fault == "label":
        groups[1][0]["Labels"]["io.pitlab.purpose"] = "dev"
    elif fault == "network":
        groups[2][0]["Containers"]["foreign"] = {}
    elif fault == "consumer":
        groups[3].add("foreign-stopped")
    else:
        groups[1].clear()
    with pytest.raises(PersistenceError):
        operator.verify_resources(
            config,
            *groups,
            ROOT,
            bootstrap_verifier=lambda c: pytest.fail("Read before full metadata ownership proof"),
        )


@pytest.mark.parametrize(
    "archive",
    [
        archive_bytes(b"x" * len(BOOTSTRAP)),
        archive_bytes(name="foreign.sh"),
        archive_bytes(kind=tarfile.SYMTYPE),
        archive_bytes(kind=tarfile.LNKTYPE),
        archive_bytes(kind=tarfile.DIRTYPE),
        archive_bytes(extra=True),
        archive_bytes(b"x" * (operator.BOOTSTRAP_MAX_BYTES + 1)),
        gzip.compress(archive_bytes()),
        b"not an archive",
        archive_bytes()[:512],
    ],
    ids=[
        "content",
        "name",
        "symlink",
        "hardlink",
        "directory",
        "extra",
        "large",
        "compressed",
        "bad",
        "short",
    ],
)
def test_translated_content_proof_refuses_substitution(monkeypatch, archive):
    monkeypatch.setattr(operator, "bootstrap_archive", lambda *a: archive)
    with pytest.raises(PersistenceError, match="Bootstrap"):
        operator.verify_bootstrap_content({"Id": "c" * 64}, ROOT, {})


@pytest.mark.parametrize("fault", ["missing", "symlink", "directory", "large", "empty"])
def test_local_bootstrap_reference_must_be_bounded_regular_file(monkeypatch, tmp_path, fault):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    if fault == "symlink":
        path.symlink_to(ROOT / "scripts/init-postgres.sh")
    elif fault == "directory":
        path.mkdir()
    elif fault == "large":
        path.write_bytes(b"x" * (operator.BOOTSTRAP_MAX_BYTES + 1))
    elif fault == "empty":
        path.touch()
    monkeypatch.setattr(
        operator, "bootstrap_archive", lambda *a: pytest.fail("Read invalid reference")
    )
    with pytest.raises(PersistenceError):
        operator.verify_bootstrap_content({"Id": "c" * 64}, tmp_path, {})


@pytest.mark.parametrize("fault", [None, "large", "timeout", "exit", "stderr"])
def test_copy_is_read_only_bounded_and_reaps_child(monkeypatch, tmp_path, fault):
    archive = tmp_path / "bootstrap.tar"
    archive.write_bytes(archive_bytes())
    code = "import sys; sys.stdout.buffer.write(open(sys.argv[1], 'rb').read())"
    if fault == "large":
        code = f"import sys; sys.stdout.buffer.write(b'x' * {operator.BOOTSTRAP_ARCHIVE_MAX_BYTES + 1})"
    elif fault == "timeout":
        code = "import time; time.sleep(60)"
    elif fault == "exit":
        code = "import sys; sys.exit(1)"
    elif fault == "stderr":
        code = "import sys; sys.stderr.write('redacted' * 100000); " + code
    popen = subprocess.Popen
    children = []

    def fake_docker(args, **kwargs):
        assert args == ["docker", "cp", "c" * 64 + ":" + operator.BOOTSTRAP_DESTINATION, "-"]
        assert kwargs["stdin"] == kwargs["stderr"] == subprocess.DEVNULL
        child = popen([sys.executable, "-c", code, str(archive)], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(operator.subprocess, "Popen", fake_docker)
    monkeypatch.setattr(operator, "BOOTSTRAP_COPY_TIMEOUT", 0.1 if fault == "timeout" else 5)
    if fault in ("large", "timeout", "exit"):
        with pytest.raises(PersistenceError, match="Bootstrap"):
            operator.bootstrap_archive("c" * 64, {})
    else:
        assert operator.bootstrap_archive("c" * 64, {}) == archive_bytes()
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdout.closed


def test_copy_access_denied_is_redacted_and_not_retried(monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(args)
        raise PermissionError("private daemon detail")

    monkeypatch.setattr(operator.subprocess, "Popen", unavailable)
    with pytest.raises(PersistenceError, match="Bootstrap") as error:
        operator.bootstrap_archive("c" * 64, {})
    assert "private" not in str(error.value)
    assert len(calls) == 1


def test_copy_requires_exact_container_id(monkeypatch):
    monkeypatch.setattr(
        operator.subprocess, "Popen", lambda *a, **kw: pytest.fail("Invalid ID used")
    )
    with pytest.raises(PersistenceError, match="container identity"):
        operator.bootstrap_archive("container-name", {})


def fake_lifecycle(monkeypatch, target):
    """Exercise real inventory/preflight with a deterministic Docker CLI transcript."""
    config = parse_config(config_values(target), target)
    state = list(resources(config)[:3])
    state[0][0]["Mounts"][1]["Source"] = TRANSLATED
    state[0][0]["Running"] = False
    planned = copy.deepcopy(state)
    calls, reads = [], []

    def run(args, *a, **kw):
        calls.append(args)
        if args[1:3] == ["context", "show"]:
            return "default"
        if args[1:3] == ["context", "inspect"]:
            return json.dumps([{"Endpoints": {"docker": {"Host": "unix:///var/run/docker.sock"}}}])
        if args[1] == "info":
            return "test-version"
        if args[1] == "compose":
            if "config" in args:
                return json.dumps(operator.expected_model(config, ROOT))
            if "up" in args:
                # Recreation produces a new container ID and opaque source, never a new volume.
                if not state[0]:
                    state[:] = copy.deepcopy(planned)
                state[0][0]["Id"] = "d" * 64
                state[0][0]["Mounts"][1]["Source"] = PREFIX + "b" * 64
                state[2][0]["Containers"] = {state[0][0]["Id"]: {}}
            elif "down" in args:
                state[0], state[2] = [], []
                if "--volumes" in args:
                    state[1] = []
            return ""
        if args[1] == "inspect":
            if args[3] == "{{.State.Running}}":
                return "true" if state[0][0]["Running"] else "false"
            return json.dumps(state[0][0])
        if args[1] == "ps":
            return state[0][0]["Id"] if state[0] else ""
        if args[1] in ("volume", "network"):
            group = state[1 if args[1] == "volume" else 2]
            return (
                json.dumps(group) if args[2] == "inspect" else (group[0]["Name"] if group else "")
            )
        pytest.fail(f"Unexpected operation: {args}")

    def read(container_id, environ):
        reads.append((container_id, state[0][0]["Mounts"][1]["Source"]))
        return archive_bytes()

    monkeypatch.setattr(operator, "run", run)
    monkeypatch.setattr(operator, "child_env", lambda c: {})
    monkeypatch.setattr(operator, "check_ports", lambda *a: None)
    monkeypatch.setattr(operator, "probe_database", lambda c: None)
    monkeypatch.setattr(operator, "bootstrap_archive", read)
    return config, state, calls, reads


@pytest.mark.parametrize(
    "target,action",
    [
        ("dev", "preflight"),
        ("dev", "up"),
        ("dev", "down"),
        ("test", "preflight"),
        ("test", "up"),
        ("test", "down"),
        ("test", "destroy-test"),
    ],
)
def test_lifecycle_accepts_fresh_proof_and_changed_opaque_path(monkeypatch, target, action):
    config, state, calls, reads = fake_lifecycle(monkeypatch, target)
    before_volume = copy.deepcopy(state[1])
    operator.lifecycle(action, config, ROOT)
    assert reads[0] == ("c" * 64, TRANSLATED)
    if action == "up":
        assert reads == [("c" * 64, TRANSLATED), ("d" * 64, PREFIX + "b" * 64)]
    if action == "destroy-test":
        assert state == [[], [], []]
        assert len([call for call in calls if "--volumes" in call]) == 1
    else:
        assert state[1] == before_volume
        assert not any("--volumes" in call for call in calls)
    assert not any("--remove-orphans" in call for call in calls)


@pytest.mark.parametrize("action", ["preflight", "up", "down", "destroy-test"])
@pytest.mark.parametrize("fault", ["content", "unavailable"])
def test_unverified_translated_mount_blocks_lifecycle_mutation(monkeypatch, action, fault):
    config, state, calls, _ = fake_lifecycle(monkeypatch, "test")
    before = copy.deepcopy(state)

    def unverified(*a):
        if fault == "content":
            return archive_bytes(b"foreign content")
        raise PersistenceError("Bootstrap read unavailable")

    monkeypatch.setattr(operator, "bootstrap_archive", unverified)
    with pytest.raises(PersistenceError, match="Bootstrap"):
        operator.lifecycle(action, config, ROOT)
    assert state == before
    assert not any("up" in call or "down" in call for call in calls)


def test_empty_preflight_then_translated_mount_after_up(monkeypatch):
    config, state, calls, reads = fake_lifecycle(monkeypatch, "dev")
    state[:] = [[], [], []]
    operator.lifecycle("up", config, ROOT)
    assert reads == [("d" * 64, PREFIX + "b" * 64)]
    assert len([call for call in calls if "up" in call]) == 1


def test_same_container_with_changed_opaque_source_gets_fresh_proof(monkeypatch):
    config, state, _, reads = fake_lifecycle(monkeypatch, "dev")
    operator.inventory(config, ROOT, {})
    state[0][0]["Mounts"][1]["Source"] = PREFIX + "b" * 64
    operator.inventory(config, ROOT, {})
    assert reads == [("c" * 64, TRANSLATED), ("c" * 64, PREFIX + "b" * 64)]


def test_translated_stopped_test_requires_new_proof_immediately_before_deletion(monkeypatch):
    config, state, calls, _ = fake_lifecycle(monkeypatch, "test")
    before = copy.deepcopy(state)
    reads = []

    def changed(container_id, environ):
        reads.append(container_id)
        return archive_bytes(BOOTSTRAP if len(reads) == 1 else b"x" * len(BOOTSTRAP))

    monkeypatch.setattr(operator, "bootstrap_archive", changed)
    with pytest.raises(PersistenceError, match="content identity"):
        operator.lifecycle("destroy-test", config, ROOT)
    assert len(reads) == 2
    assert state == before
    assert not any("down" in call for call in calls)
