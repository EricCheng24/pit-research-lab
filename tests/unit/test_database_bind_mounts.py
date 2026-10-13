"""Offline fixed-source and direct/Desktop mounted-content safety regressions."""

import copy
import gzip
import io
import json
import os
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
    assert reads == [container["Id"]]


@pytest.mark.parametrize("source", [str(ROOT / "scripts/init-postgres.sh"), TRANSLATED])
def test_translated_prefix_without_content_proof_refuses(source):
    config = parse_config(config_values(), "test")
    groups = resources(config)
    groups[0][0]["Mounts"][1]["Source"] = source
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
        "missing-network",
        "stopped-network-consumer",
        "container-label",
        "container-name",
        "network-label",
        "network-name",
        "volume-name",
        "public-port",
        "extra-mount",
        "extra-container",
    ],
)
@pytest.mark.parametrize("source", [str(ROOT / "scripts/init-postgres.sh"), TRANSLATED])
def test_translated_source_preserves_all_metadata_checks(fault, source):
    config = parse_config(config_values(), "test")
    groups = resources(config)
    container = groups[0][0]
    data, bind = container["Mounts"]
    bind["Source"] = source
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
    elif fault == "missing-volume":
        groups[1].clear()
    elif fault == "missing-network":
        groups[2].clear()
    elif fault == "stopped-network-consumer":
        groups[2][0]["Consumers"] = {"foreign-stopped"}
    elif fault == "container-label":
        container["Labels"]["com.docker.compose.service"] = "foreign"
    elif fault == "container-name":
        container["Name"] = "/foreign"
    elif fault == "network-label":
        groups[2][0]["Labels"]["io.pitlab.instance"] = "foreign"
    elif fault == "network-name":
        groups[2][0]["Name"] = "foreign"
    elif fault == "volume-name":
        groups[1][0]["Name"] = "foreign"
    elif fault == "public-port":
        container["Ports"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    elif fault == "extra-mount":
        container["Mounts"].append(copy.deepcopy(bind))
    else:
        groups[0].append(copy.deepcopy(container))
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
        archive_bytes(kind=tarfile.GNUTYPE_SPARSE),
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
        "sparse",
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


@pytest.mark.parametrize("size", [1, operator.BOOTSTRAP_MAX_BYTES])
def test_fixed_local_reference_accepts_bounded_regular_file(tmp_path, size):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    content = b"x" * size
    path.write_bytes(content)
    assert operator.read_bootstrap(tmp_path) == content


def test_scripts_symlink_refuses_but_parents_above_resolved_root_are_allowed(tmp_path):
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "scripts/init-postgres.sh").write_bytes(BOOTSTRAP)
    alias = tmp_path / "alias"
    alias.symlink_to(checkout, target_is_directory=True)
    assert operator.read_bootstrap(alias.resolve()) == BOOTSTRAP
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    (redirected / "scripts").symlink_to(checkout / "scripts", target_is_directory=True)
    with pytest.raises(PersistenceError, match="Local bootstrap"):
        operator.read_bootstrap(redirected)


@pytest.mark.parametrize("fault", ["unreadable", "substitution", "ancestor-substitution"])
def test_local_open_refuses_unreadable_or_substituted_reference(monkeypatch, tmp_path, fault):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    path.write_bytes(BOOTSTRAP)
    original = os.open
    opens = []

    def changed(name, flags, **kwargs):
        opens.append(name)
        if name == "init-postgres.sh":
            if fault == "unreadable":
                raise PermissionError("synthetic-private-detail")
            if fault == "substitution":
                path.rename(path.with_name("original"))
                path.write_bytes(BOOTSTRAP)
            else:
                path.parent.rename(tmp_path / "old-scripts")
                path.parent.mkdir()
                path.write_bytes(BOOTSTRAP)
        return original(name, flags, **kwargs)

    monkeypatch.setattr(operator.os, "open", changed)
    with pytest.raises(PersistenceError, match="Local bootstrap") as error:
        operator.read_bootstrap(tmp_path)
    assert str(error.value) == (
        "Local bootstrap proof unavailable/invalid; retain resources and verify the checkout file privately."
    )
    assert len(opens) == 2  # One attempt, no permission repair or alternate-path retry.


def test_empty_owned_inventory_needs_local_proof_without_archive_reads(monkeypatch, tmp_path):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    path.write_bytes(BOOTSTRAP)
    config, state, calls, reads = fake_lifecycle(monkeypatch, "test", root=tmp_path)
    state[:] = [[], [], []]
    operator.lifecycle("preflight", config, tmp_path)
    assert reads == [] and calls
    path.unlink()
    calls.clear()
    with pytest.raises(PersistenceError, match="Local bootstrap"):
        operator.lifecycle("preflight", config, tmp_path)
    assert reads == calls == []


@pytest.mark.parametrize("action", ["up", "down", "destroy-test"])
@pytest.mark.parametrize("fault", ["missing", "empty", "directory", "symlink"])
def test_invalid_source_blocks_previously_owned_resources(monkeypatch, tmp_path, action, fault):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    path.write_bytes(BOOTSTRAP)
    config, state, calls, reads = fake_lifecycle(monkeypatch, "test", root=tmp_path)
    operator.inventory(config, tmp_path, {})  # Synthetic owned inventory/content verified first.
    before = copy.deepcopy(state)
    path.unlink()
    if fault == "empty":
        path.touch()
    elif fault == "directory":
        path.mkdir()
    elif fault == "symlink":
        path.symlink_to(ROOT / "scripts/init-postgres.sh")
    calls.clear()
    reads.clear()
    with pytest.raises(PersistenceError, match="Local bootstrap"):
        operator.lifecycle(action, config, tmp_path)
    assert state == before
    assert calls == reads == []  # No Docker access, repair, startup or deletion.
    assert path.exists() == (fault != "missing")


def test_source_rechecked_at_startup_edge(monkeypatch, tmp_path):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    path.write_bytes(BOOTSTRAP)
    config, state, calls, reads = fake_lifecycle(monkeypatch, "test", root=tmp_path)
    state[:] = [[], [], []]
    monkeypatch.setattr(operator, "check_ports", lambda *a: path.unlink())
    with pytest.raises(PersistenceError, match="Local bootstrap"):
        operator.lifecycle("up", config, tmp_path)
    assert not any("up" in call or "down" in call for call in calls)
    assert state == [[], [], []] and reads == []


@pytest.mark.parametrize("action", ["down", "destroy-test"])
def test_source_rechecked_immediately_before_shutdown(monkeypatch, tmp_path, action):
    path = tmp_path / "scripts/init-postgres.sh"
    path.parent.mkdir()
    path.write_bytes(BOOTSTRAP)
    config, state, calls, reads = fake_lifecycle(monkeypatch, "test", root=tmp_path)
    before = copy.deepcopy(state)
    inventory = operator.inventory
    inventories = []

    def changed(*args, **kwargs):
        result = inventory(*args, **kwargs)
        inventories.append(result)
        if len(inventories) == 2:
            path.unlink()
        return result

    monkeypatch.setattr(operator, "inventory", changed)
    with pytest.raises(PersistenceError, match="Local bootstrap"):
        operator.lifecycle(action, config, tmp_path)
    assert len(reads) == len(inventories) == 2
    assert state == before
    assert not any("down" in call for call in calls)


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


def fake_lifecycle(monkeypatch, target, *, root=ROOT, source=TRANSLATED):
    """Exercise real inventory/preflight with a deterministic Docker CLI transcript."""
    config = parse_config(config_values(target), target)
    state = list(resources(config)[:3])
    state[0][0]["Mounts"][1]["Source"] = source or str(root / "scripts/init-postgres.sh")
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
                return json.dumps(operator.expected_model(config, root))
            if "up" in args:
                # Recreation produces a new container ID and opaque source, never a new volume.
                if not state[0]:
                    state[:] = copy.deepcopy(planned)
                state[0][0]["Id"] = "d" * 64
                state[0][0]["Mounts"][1]["Source"] = (
                    PREFIX + "b" * 64 if source else str(root / "scripts/init-postgres.sh")
                )
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
@pytest.mark.parametrize(
    "fault",
    [
        "content",
        "unavailable",
        "name",
        "symlink",
        "hardlink",
        "directory",
        "sparse",
        "extra",
        "large",
        "compressed",
        "bad",
        "short",
    ],
)
@pytest.mark.parametrize("source", [None, TRANSLATED], ids=["direct", "translated"])
def test_unverified_translated_mount_blocks_lifecycle_mutation(monkeypatch, action, fault, source):
    config, state, calls, _ = fake_lifecycle(monkeypatch, "test", source=source)
    before = copy.deepcopy(state)

    def unverified(*a):
        if fault == "unavailable":
            raise PersistenceError("Bootstrap read unavailable")
        return {
            "content": archive_bytes(b"foreign content"),
            "name": archive_bytes(name="foreign.sh"),
            "symlink": archive_bytes(kind=tarfile.SYMTYPE),
            "hardlink": archive_bytes(kind=tarfile.LNKTYPE),
            "directory": archive_bytes(kind=tarfile.DIRTYPE),
            "sparse": archive_bytes(kind=tarfile.GNUTYPE_SPARSE),
            "extra": archive_bytes(extra=True),
            "large": archive_bytes(b"x" * (operator.BOOTSTRAP_MAX_BYTES + 1)),
            "compressed": gzip.compress(archive_bytes()),
            "bad": b"not an archive",
            "short": archive_bytes()[:512],
        }[fault]

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


@pytest.mark.parametrize("source", [None, TRANSLATED], ids=["direct", "translated"])
def test_translated_stopped_test_requires_new_proof_immediately_before_deletion(
    monkeypatch, source
):
    config, state, calls, _ = fake_lifecycle(monkeypatch, "test", source=source)
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
