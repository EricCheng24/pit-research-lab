"""Offline lifecycle, migration routing and test-selection adversarial probes."""

import copy
import importlib.util
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from test_database_config import config_values

from pit_research_lab.infrastructure.database.config import (
    PersistenceError,
    load_config,
    parse_config,
)

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("database_operator", ROOT / "scripts/database.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


def resources(config):
    common = {**operator.labels(config), "com.docker.compose.project": config.project}
    container = {
        "Id": "c" * 64,
        "Name": f"/{config.project}-postgres_{config.target}-1",
        "Image": operator.IMAGE,
        "Labels": {
            **common,
            "com.docker.compose.service": f"postgres_{config.target}",
            "com.docker.compose.oneoff": "False",
            "com.docker.compose.container-number": "1",
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": f"{config.project}_pgdata_{config.target}",
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            },
            {
                "Type": "bind",
                "Source": str(ROOT / "scripts/init-postgres.sh"),
                "Destination": "/docker-entrypoint-initdb.d/10-pitlab.sh",
                "RW": False,
            },
        ],
        "Networks": {f"{config.project}_default": {}},
        "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(config.port)}]},
    }
    volume = {
        "Name": f"{config.project}_pgdata_{config.target}",
        "Labels": {**common, "com.docker.compose.volume": f"pgdata_{config.target}"},
    }
    network = {
        "Name": f"{config.project}_default",
        "Containers": {container["Id"]: {}},
        "Labels": {**common, "com.docker.compose.network": "default"},
    }
    return [container], [volume], [network], {container["Id"]}


def test_owned_and_missing_resource_plans():
    config = parse_config(config_values(), "test")
    operator.verify_resources(config, *resources(config), ROOT)
    operator.verify_resources(config, [], [], [], set(), ROOT)
    _, volumes, _, _ = resources(config)
    operator.verify_resources(config, [], volumes, [], set(), ROOT)


@pytest.mark.parametrize(
    "fault",
    [
        "label",
        "extra-service",
        "foreign-volume",
        "foreign-network",
        "foreign-stopped-network",
        "data-mount",
        "image",
        "public-port",
        "missing-volume",
        "bind-write",
    ],
)
def test_ambiguous_ownership_refuses(fault):
    config = parse_config(config_values(), "test")
    containers, volumes, networks, consumers = resources(config)
    if fault == "label":
        volumes[0]["Labels"]["io.pitlab.purpose"] = "dev"
    elif fault == "extra-service":
        containers.append(copy.deepcopy(containers[0]))
    elif fault == "foreign-volume":
        consumers.add("foreign")
    elif fault == "foreign-network":
        networks[0]["Containers"]["foreign"] = {}
    elif fault == "foreign-stopped-network":
        networks[0]["Consumers"] = {"foreign"}
    elif fault == "data-mount":
        containers[0]["Mounts"][0]["Name"] = "survivor-volume"
    elif fault == "image":
        containers[0]["Image"] = "postgres:latest"
    elif fault == "public-port":
        containers[0]["Ports"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    elif fault == "missing-volume":
        volumes.clear()
    else:
        containers[0]["Mounts"][1]["RW"] = True
    with pytest.raises(PersistenceError):
        operator.verify_resources(config, containers, volumes, networks, consumers, ROOT)


@pytest.mark.parametrize("fault", ["extra-service", "external-volume", "override-file", "image"])
def test_resolved_compose_cannot_expand_boundary(fault):
    config = parse_config(config_values(), "test")
    model = operator.expected_model(config, ROOT)
    if fault == "extra-service":
        model["services"]["foreign"] = {}
    elif fault == "external-volume":
        model["volumes"]["pgdata_test"]["external"] = True
    elif fault == "override-file":
        model["services"]["postgres_test"]["volumes"][0]["source"] = "dev"
    else:
        model["services"]["postgres_test"]["image"] = "postgres:latest"
    with pytest.raises(PersistenceError, match="model"):
        operator.validate_model(model, config, ROOT)


def test_setup_once_no_rotation_and_separate_secrets(tmp_path):
    operator.setup(tmp_path, "unit", 55432, 55433)
    dev = load_config("dev", tmp_path, environ={})
    test = load_config("test", tmp_path, environ={})
    assert dev.instance_id != test.instance_id
    assert not {dev.admin_password, dev.migrator_password, dev.app_password} & {
        test.admin_password,
        test.migrator_password,
        test.app_password,
    }
    before = (tmp_path / ".env.test.local").read_bytes()
    with pytest.raises(PersistenceError, match="existing"):
        operator.setup(tmp_path, "unit", 55432, 55433)
    assert (tmp_path / ".env.test.local").read_bytes() == before


def test_fixed_compose_and_dev_destruction_refused(monkeypatch):
    config = parse_config(config_values("dev"), "dev")
    args = operator.compose_args(config, ROOT)
    assert args[-3:] == [str(ROOT / "compose.dev.yaml"), "-p", "pitlab-unit-dev"]

    def forbidden(*args, **kwargs):
        pytest.fail("Docker call before target refusal")

    monkeypatch.setattr(operator, "preflight", forbidden)
    with pytest.raises(PersistenceError, match="only for test"):
        operator.lifecycle("destroy-test", config, ROOT)


@pytest.mark.parametrize(
    "args",
    [[], ["-x", "target=unknown"], ["-x", "target=dev"], ["-x", "target=dev", "-x", "target=test"]],
)
def test_direct_alembic_target_negatives(args):
    operation = ["downgrade", "base"] if "target=dev" in args else ["upgrade", "head"]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), *args, *operation],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "target" in result.stderr or "Dev downgrade" in result.stderr


def test_alembic_rejects_unguarded_active_connection(monkeypatch):
    import pit_research_lab.infrastructure.database.config as module

    config = parse_config(config_values(), "test")
    monkeypatch.setattr(module, "load_config", lambda *args: config)
    settings = Config(str(ROOT / "alembic.ini"))
    settings.cmd_opts = Namespace(x=["target=test"])
    settings.attributes["operation"] = "upgrade"
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            settings.attributes["connection"] = connection
            with pytest.raises(SystemExit, match="active guarded"):
                command.upgrade(settings, "head")
    finally:
        engine.dispose()


def test_integration_selection_is_nonempty_and_fast_excludes_it():
    for marker, expected in (("integration", True), ("not integration", False)):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-m",
                marker,
                str(ROOT / "tests/integration/database"),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == (0 if expected else 5)
        assert ("test_connection.py::" in result.stdout) == expected
    for path in (ROOT / "tests/integration/database").glob("test_*.py"):
        assert "pytestmark = pytest.mark.integration" in path.read_text()


def test_empty_integration_and_invalid_marker_fail(tmp_path):
    empty = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            "integration",
            str(ROOT / "tests/unit/test_package_smoke.py"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert empty.returncode == 5
    bad = tmp_path / "test_bad_marker.py"
    bad.write_text("import pytest\n@pytest.mark.not_registered\ndef test_bad(): pass\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--strict-markers", str(bad)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "not_registered" in result.stdout


def test_make_propagates_empty_second_pass(tmp_path):
    if shutil.which("make") is None:
        pytest.skip("make is unavailable; this test checks Make-specific failure propagation")
    calls = tmp_path / "calls"
    uv = tmp_path / "uv"
    uv.write_text(
        f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
        f"with Path({str(calls)!r}).open('a') as f: f.write(repr(sys.argv[1:])+'\\n')\n"
        "sys.exit(5 if sys.argv[-1] == 'integration' else 0)\n"
    )
    uv.chmod(0o700)
    result = subprocess.run(
        ["make", "-f", str(ROOT / "Makefile"), "test-all"],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Error 5" in result.stderr
    assert len(calls.read_text().splitlines()) == 2


def test_listener_warning_is_not_evidence(monkeypatch):
    def warning(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, "", "Cannot open netlink socket")

    monkeypatch.setattr(operator.subprocess, "run", warning)
    with pytest.raises(PersistenceError):
        operator.run(["ss", "-H", "-ltn"], {}, strict_stderr=True)


def test_stopped_owned_container_does_not_authorize_occupied_port(monkeypatch):
    config = parse_config(config_values(), "test")
    containers, *_ = resources(config)
    containers[0]["Running"] = False
    monkeypatch.setattr(operator.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        operator,
        "run",
        lambda args, *a, **kw: "LISTEN 0 10 127.0.0.1:55433 0.0.0.0:*" if args[0] == "ss" else "",
    )
    with pytest.raises(PersistenceError, match="occupied"):
        operator.check_ports(config, containers, {})


def test_running_identity_failure_prevents_test_deletion(monkeypatch):
    config = parse_config(config_values(), "test")
    groups = resources(config)[:3]
    calls = []
    monkeypatch.setattr(operator, "preflight", lambda *a, **kw: ({}, groups))
    monkeypatch.setattr(operator, "run", lambda args, *a, **kw: calls.append(args) or "true")

    def mismatch(config):
        raise PersistenceError("identity mismatch")

    monkeypatch.setattr(operator, "probe_database", mismatch)
    with pytest.raises(PersistenceError, match="identity mismatch"):
        operator.lifecycle("destroy-test", config, ROOT)
    assert not any("down" in args for args in calls)


def test_partial_deletion_reports_resources_without_retry(monkeypatch, capsys):
    config = parse_config(config_values(), "test")
    groups = resources(config)[:3]
    calls = []
    monkeypatch.setattr(operator, "preflight", lambda *a, **kw: ({}, groups))
    monkeypatch.setattr(operator, "probe_database", lambda config: None)

    def inventory(*args, report=False):
        if report:
            operator.print_resources(groups)
        return groups

    def fail_down(args, *a, **kw):
        calls.append(args)
        if "down" in args:
            raise PersistenceError("partial failure")
        return "true"

    monkeypatch.setattr(operator, "inventory", inventory)
    monkeypatch.setattr(operator, "run", fail_down)
    with pytest.raises(PersistenceError, match="partial failure"):
        operator.lifecycle("destroy-test", config, ROOT)
    assert len([args for args in calls if "down" in args]) == 1
    assert "--volumes" in calls[-1] and "--remove-orphans" not in calls[-1]
    assert groups[1][0]["Name"] in capsys.readouterr().out


@pytest.mark.parametrize(
    "fault", [None, "ipv4-failed", "ipv6-reserved", "unknown-output", "listener"]
)
def test_windows_queries_each_require_positive_proof(monkeypatch, fault):
    from contextlib import nullcontext
    from types import SimpleNamespace

    config = parse_config(config_values(), "test")
    monkeypatch.setattr(operator.platform, "system", lambda: "Linux")
    monkeypatch.setattr(operator.platform, "release", lambda: "microsoft-wsl2")
    monkeypatch.setattr(operator.shutil, "which", lambda name: "/windows/powershell.exe")
    monkeypatch.setattr(
        operator.socket, "socket", lambda: nullcontext(SimpleNamespace(bind=lambda addr: None))
    )
    queries = []

    def output(args, *a, **kw):
        if args[0] in ("ss", "docker"):
            return ""
        queries.append(args[-1])
        if "Get-NetTCPConnection" in args[-1]:
            return "1" if fault == "listener" else "0"
        if "ipv4" in args[-1] and fault == "ipv4-failed":
            raise PersistenceError("host query failed")
        if "ipv6" in args[-1] and fault == "ipv6-reserved":
            return "55400 55500"
        if fault == "unknown-output":
            return "unknown header format"
        return "Start Port    End Port\n----------    --------"  # Valid empty English range list.

    monkeypatch.setattr(operator, "run", output)
    if fault:
        with pytest.raises(PersistenceError):
            operator.check_ports(config, [], {})
    else:
        operator.check_ports(config, [], {})
        assert len(queries) == 3
