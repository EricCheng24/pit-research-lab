"""Small explicit operator helper. No shell evaluation, daemon escalation or automatic repair."""

import argparse
import hashlib
import io
import json
import os
import platform
import re
import secrets
import selectors
import shutil
import socket
import stat
import subprocess
import tarfile
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import URL

from pit_research_lab.infrastructure.database.config import (
    IMAGE,
    DatabaseConfig,
    PersistenceError,
    load_config,
    parse_config,
    reject_ambient,
    select_target,
)
from pit_research_lab.infrastructure.database.engine import probe_database

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_DESTINATION = "/docker-entrypoint-initdb.d/10-pitlab.sh"
DESKTOP_BIND_SOURCE = re.compile(
    r"/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/"
    r"[A-Za-z0-9][A-Za-z0-9_.-]*/[a-f0-9]{64}"
)
BOOTSTRAP_MAX_BYTES = 16 * 1024
BOOTSTRAP_ARCHIVE_MAX_BYTES = 64 * 1024
BOOTSTRAP_COPY_TIMEOUT = 15


def bootstrap_archive(container_id: str, environ: dict[str, str]) -> bytes:
    """Bounded read from the exact container, including stopped containers; never extract."""
    if not re.fullmatch(r"[a-f0-9]{64}", container_id):
        raise PersistenceError("Bootstrap container identity unavailable; lifecycle refused.")
    try:
        with subprocess.Popen(
            ["docker", "cp", f"{container_id}:{BOOTSTRAP_DESTINATION}", "-"],
            env=environ,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as process:
            try:
                deadline = time.monotonic() + BOOTSTRAP_COPY_TIMEOUT
                output = bytearray()
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0 or not selector.select(remaining):
                            raise PersistenceError("Bootstrap read timed out; lifecycle refused.")
                        chunk = os.read(process.stdout.fileno(), 8192)
                        if not chunk:
                            selector.unregister(process.stdout)
                        output.extend(chunk)
                        if len(output) > BOOTSTRAP_ARCHIVE_MAX_BYTES:
                            raise PersistenceError(
                                "Bootstrap archive exceeds bound; lifecycle refused."
                            )
                if process.wait(timeout=max(deadline - time.monotonic(), 0.001)):
                    raise PersistenceError("Bootstrap read unavailable; lifecycle refused.")
                return bytes(output)
            finally:
                if process.poll() is None:
                    process.kill()
    except (OSError, subprocess.TimeoutExpired):
        raise PersistenceError("Bootstrap read unavailable/timed out; lifecycle refused.") from None


def read_bootstrap(root: Path) -> bytes:
    """Bounded fixed reference under a trusted resolved root; never follow scripts/leaf links.

    Parents above root are outside this check. Descriptor identity checks reject observed
    substitution during the read; a stable trusted checkout is still required afterwards.
    """
    try:
        scripts = root / "scripts"
        directory = os.open(scripts, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            directory_info = os.fstat(directory)
            before = os.stat("init-postgres.sh", dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError
            descriptor = os.open(
                "init-postgres.sh", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as file:
                opened = os.fstat(file.fileno())
                if not stat.S_ISREG(opened.st_mode) or opened != before:
                    raise ValueError
                content = file.read(BOOTSTRAP_MAX_BYTES + 1)
                after = os.stat("init-postgres.sh", dir_fd=directory, follow_symlinks=False)
                if (
                    not content
                    or len(content) > BOOTSTRAP_MAX_BYTES
                    or any(
                        getattr(info, field) != getattr(opened, field)
                        for info in (os.fstat(file.fileno()), after)
                        for field in (
                            "st_dev",
                            "st_ino",
                            "st_mode",
                            "st_size",
                            "st_mtime_ns",
                            "st_ctime_ns",
                        )
                    )
                    or not os.path.samestat(scripts.lstat(), directory_info)
                ):
                    raise ValueError
            return content
        finally:
            os.close(directory)
    except (OSError, ValueError):
        raise PersistenceError(
            "Local bootstrap proof unavailable/invalid; retain resources and verify the checkout file privately."
        ) from None


def verify_bootstrap_content(container: dict, root: Path, environ: dict[str, str]) -> None:
    """Fresh direct/translated mounted identity after ownership proof; never cache receipts."""
    expected = read_bootstrap(root)
    try:
        archive = bootstrap_archive(container["Id"], environ)
        # Uncompressed tar only: bounded input cannot expand through decompression.
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            members = tar.getmembers()
            if (
                len(members) != 1
                or members[0].name != "10-pitlab.sh"
                or not members[0].isreg()
                or members[0].issparse()
                or members[0].size != len(expected)
            ):
                raise PersistenceError("Bootstrap archive identity disagrees; lifecycle refused.")
            with tar.extractfile(members[0]) as file:
                actual = file.read(BOOTSTRAP_MAX_BYTES + 1)
        if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
            raise PersistenceError("Bootstrap content identity disagrees; lifecycle refused.")
    except (OSError, tarfile.TarError, ValueError):
        raise PersistenceError("Bootstrap content proof unavailable; lifecycle refused.") from None


def setup(root: Path, namespace: str, dev_port: int, test_port: int) -> None:
    reject_ambient(os.environ)
    paths = [root / f".env.{target}.local" for target in ("dev", "test")]
    if any(p.exists() or p.is_symlink() for p in paths):
        raise PersistenceError(
            "Setup refuses existing local files; retain credentials and diagnose privately."
        )
    configs = []
    for target, port, peer in (("dev", dev_port, test_port), ("test", test_port, dev_port)):
        passwords = [secrets.token_hex(32) for _ in range(3)]
        values = {
            "TARGET": target,
            "NAMESPACE": namespace,
            "INSTANCE_ID": str(uuid4()),
            "PORT": str(port),
            "PEER_PORT": str(peer),
            "ADMIN_PASSWORD": passwords[0],
            "MIGRATOR_PASSWORD": passwords[1],
            "APP_PASSWORD": passwords[2],
        }
        for key, suffix, password in (
            ("DATABASE_URL", "app", passwords[2]),
            ("MIGRATION_DATABASE_URL", "migrator", passwords[1]),
        ):
            values[key] = URL.create(
                "postgresql+psycopg",
                username=f"pitlab_{target}_{suffix}",
                password=password,
                host="127.0.0.1",
                port=port,
                database=f"pitlab_{target}",
            ).render_as_string(hide_password=False)
        parse_config(values, select_target(target))
        configs.append(values)
    # Exclusive creation, no overwrite/rotation. If interrupted, retain files and report.
    for path, values in zip(paths, configs, strict=True):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write("".join(f"{key}={value}\n" for key, value in values.items()))


def child_env(config: DatabaseConfig) -> dict[str, str]:
    reject_ambient(os.environ)
    if any(key.startswith("DOCKER_") for key in os.environ):
        raise PersistenceError(
            "Remove ambient DOCKER_* overrides; use the unchanged local Docker context."
        )
    return {
        **{k: os.environ[k] for k in ("PATH", "HOME", "WSL_INTEROP") if k in os.environ},
        "NAMESPACE": config.namespace,
        "INSTANCE_ID": config.instance_id,
        "PORT": str(config.port),
        "ADMIN_PASSWORD": config.admin_password,
        "MIGRATOR_PASSWORD": config.migrator_password,
        "APP_PASSWORD": config.app_password,
    }


def run(
    args: list[str], environ: dict[str, str], timeout: int = 15, *, strict_stderr: bool = False
) -> str:
    try:
        result = subprocess.run(
            args, env=environ, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PersistenceError(
            "Operator command unavailable/timed out; no automatic retry."
        ) from None
    if result.returncode or (strict_stderr and result.stderr):
        diagnostic = result.stderr.lower()
        if "permission denied" in diagnostic:
            raise PersistenceError(
                "Operator/Docker access denied in this execution environment; do not change socket permissions."
            )
        if "cannot connect to the docker daemon" in diagnostic:
            raise PersistenceError(
                "Docker daemon unavailable in this execution environment; verify the user's local context."
            )
        if "port is already allocated" in diagnostic or "address already in use" in diagnostic:
            raise PersistenceError(
                "Selected port collision; retain conflicting resources and stop."
            )
        if strict_stderr:
            raise PersistenceError("Listener inspection unavailable/ambiguous; startup refused.")
        raise PersistenceError(
            "Docker/operator command failed (output redacted); check daemon access, readiness and ports."
        )
    return result.stdout


def compose_args(config: DatabaseConfig, root: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-f",
        str(root / f"compose.{config.target}.yaml"),
        "-p",
        config.project,
    ]


def labels(config: DatabaseConfig) -> dict[str, str]:
    return {
        "io.pitlab.purpose": config.target,
        "io.pitlab.namespace": config.namespace,
        "io.pitlab.instance": config.instance_id,
    }


def expected_model(config: DatabaseConfig, root: Path) -> dict:
    """Exact allowed resolved model; new Compose behavior requires review, never permissive fallback."""
    target = config.target
    return {
        "name": config.project,
        "services": {
            f"postgres_{target}": {
                "image": IMAGE,
                "entrypoint": None,
                "command": [
                    "postgres",
                    "-c",
                    "shared_buffers=64MB",
                    "-c",
                    "max_connections=20",
                    "-c",
                    "log_statement=none",
                    "-c",
                    "log_min_error_statement=panic",
                ],
                "environment": {
                    "POSTGRES_DB": config.database,
                    "POSTGRES_USER": f"pitlab_{target}_admin",
                    "POSTGRES_PASSWORD": config.admin_password,
                    "PITLAB_TARGET": target,
                    "PITLAB_NAMESPACE": config.namespace,
                    "PITLAB_INSTANCE_ID": config.instance_id,
                    "PITLAB_MIGRATOR_PASSWORD": config.migrator_password,
                    "PITLAB_APP_PASSWORD": config.app_password,
                    "POSTGRES_INITDB_ARGS": "--auth-host=scram-sha-256",
                },
                "ports": [
                    {
                        "mode": "ingress",
                        "host_ip": "127.0.0.1",
                        "target": 5432,
                        "published": str(config.port),
                        "protocol": "tcp",
                    }
                ],
                "volumes": [
                    {
                        "type": "volume",
                        "source": f"pgdata_{target}",
                        "target": "/var/lib/postgresql/data",
                        "volume": {},
                    },
                    {
                        "type": "bind",
                        "source": str(root / "scripts/init-postgres.sh"),
                        "target": "/docker-entrypoint-initdb.d/10-pitlab.sh",
                        "read_only": True,
                        "bind": {},
                    },
                ],
                "labels": labels(config),
                "networks": {"default": None},
                "shm_size": "134217728",
                "healthcheck": {
                    "test": [
                        "CMD-SHELL",
                        f"pg_isready -U pitlab_{target}_admin -d {config.database}",
                    ],
                    "interval": "2s",
                    "timeout": "3s",
                    "retries": 20,
                    "start_period": "5s",
                },
                "logging": {"driver": "json-file", "options": {"max-size": "5m", "max-file": "2"}},
            }
        },
        "volumes": {
            f"pgdata_{target}": {
                "name": f"{config.project}_pgdata_{target}",
                "labels": labels(config),
            }
        },
        "networks": {
            "default": {"name": f"{config.project}_default", "ipam": {}, "labels": labels(config)}
        },
    }


def validate_model(model: dict, config: DatabaseConfig, root: Path) -> None:
    if model != expected_model(config, root):
        raise PersistenceError(
            "Resolved Compose model differs from the approved one-service boundary."
        )


def verify_resources(
    config: DatabaseConfig,
    containers: list[dict],
    volumes: list[dict],
    networks: list[dict],
    consumers: set[str],
    root: Path,
    *,
    bootstrap_verifier: Callable[[dict], None] | None = None,
) -> None:
    """Prove all metadata/consumers before reading any approved bootstrap mount."""
    project = config.project
    volume_name = f"{project}_pgdata_{config.target}"
    if len(containers) > 1 or len(volumes) > 1 or len(networks) > 1:
        raise PersistenceError("Unexpected project resources; lifecycle refused.")
    for kind, resources in (("container", containers), ("volume", volumes), ("network", networks)):
        for resource in resources:
            expected_labels = {**labels(config), "com.docker.compose.project": project}
            if kind == "container":
                expected_labels["com.docker.compose.service"] = f"postgres_{config.target}"
                expected_labels["com.docker.compose.oneoff"] = "False"
                expected_labels["com.docker.compose.container-number"] = "1"
            else:
                expected_labels[f"com.docker.compose.{kind}"] = (
                    f"pgdata_{config.target}" if kind == "volume" else "default"
                )
            actual = resource.get("Labels") or {}
            if any(actual.get(k) != v for k, v in expected_labels.items()):
                raise PersistenceError("Resource ownership labels disagree; lifecycle refused.")
            expected_name = (
                f"/{project}-postgres_{config.target}-1"
                if kind == "container"
                else volume_name
                if kind == "volume"
                else f"{project}_default"
            )
            if resource.get("Name") != expected_name:
                raise PersistenceError("Unexpected resource name; lifecycle refused.")
            if kind == "container":
                mounts = resource.get("Mounts", [])
                data = [m for m in mounts if m.get("Type") == "volume"]
                binds = [m for m in mounts if m.get("Type") == "bind"]
                if (
                    len(mounts) != 2
                    or len(data) != 1
                    or len(binds) != 1
                    or data[0].get("Name") != volume_name
                    or data[0].get("Destination") != "/var/lib/postgresql/data"
                    or data[0].get("RW") is not True
                    or binds[0].get("Destination") != BOOTSTRAP_DESTINATION
                    or binds[0].get("RW") is not False
                    or resource.get("Image") != IMAGE
                    or set(resource.get("Networks", {})) != {f"{project}_default"}
                ):
                    raise PersistenceError("Unexpected image/mount/network; lifecycle refused.")
                source = binds[0].get("Source")
                if source != str(root / "scripts/init-postgres.sh"):
                    if not isinstance(source, str) or not DESKTOP_BIND_SOURCE.fullmatch(source):
                        raise PersistenceError("Foreign bootstrap source; lifecycle refused.")
                ports = resource.get("Ports") or {}
                if ports != {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(config.port)}]}:
                    raise PersistenceError("Unexpected published ports; lifecycle refused.")
            if kind == "network" and not set(resource.get("Containers", {})) <= {
                c["Id"] for c in containers
            }:
                raise PersistenceError("Foreign network consumer; lifecycle refused.")
            if kind == "network" and not set(resource.get("Consumers", ())) <= {
                c["Id"] for c in containers
            }:
                raise PersistenceError(
                    "Foreign stopped/running network consumer; lifecycle refused."
                )
    if not consumers <= {c["Id"] for c in containers}:
        raise PersistenceError("Foreign volume consumer; lifecycle refused.")
    if containers and (not volumes or not networks):
        raise PersistenceError("Incomplete resource ownership proof; lifecycle refused.")
    for container in containers:
        if bootstrap_verifier is None:
            raise PersistenceError("Bootstrap source unverified; lifecycle refused.")
        bootstrap_verifier(container)


def inventory(
    config: DatabaseConfig, root: Path, environ: dict[str, str], *, report: bool = False
) -> tuple[list, list, list]:
    """Read ownership metadata and approved bootstrap only; never environments or DB data."""
    result = []
    for kind in ("container", "volume", "network"):
        listing = (
            ["docker", "ps", "-a", "-q"] if kind == "container" else ["docker", kind, "ls", "-q"]
        )
        found = set(
            run(
                [*listing, "--filter", f"label=com.docker.compose.project={config.project}"],
                environ,
            ).split()
        )
        if kind != "container":
            name = (
                f"{config.project}_pgdata_{config.target}"
                if kind == "volume"
                else f"{config.project}_default"
            )
            # Also detect exact-name collisions lacking the project label.
            found.update(run([*listing, "--filter", f"name=^{name}$"], environ).split())
        else:
            found.update(
                run(
                    [*listing, "--filter", f"name=^/{config.project}-postgres_{config.target}-1$"],
                    environ,
                ).split()
            )
        resources = []
        for name in sorted(found):
            if kind == "container":
                template = (
                    '{"Id":{{json .Id}},"Name":{{json .Name}},"Labels":{{json .Config.Labels}},'
                    '"Mounts":{{json .Mounts}},"Image":{{json .Config.Image}},'
                    '"Ports":{{json .HostConfig.PortBindings}},"Networks":{{json .NetworkSettings.Networks}},'
                    '"Running":{{json .State.Running}}}'
                )
                resources.append(
                    json.loads(run(["docker", "inspect", "--format", template, name], environ))
                )
            else:
                resources.extend(json.loads(run(["docker", kind, "inspect", name], environ)))
        result.append(resources)
    volume = f"{config.project}_pgdata_{config.target}"
    consumers = set(
        run(
            ["docker", "ps", "-a", "-q", "--no-trunc", "--filter", f"volume={volume}"], environ
        ).split()
    )
    network_consumers = set(
        run(
            [
                "docker",
                "ps",
                "-a",
                "-q",
                "--no-trunc",
                "--filter",
                f"network={config.project}_default",
            ],
            environ,
        ).split()
    )
    if network_consumers and not result[2]:
        raise PersistenceError(
            "Network consumers found without owned network proof; lifecycle refused."
        )
    for network in result[2]:
        network["Consumers"] = network_consumers
    if report:
        print_resources(tuple(result))
    verify_resources(
        config,
        *result,
        consumers,
        root,
        bootstrap_verifier=lambda container: verify_bootstrap_content(container, root, environ),
    )
    return tuple(result)


def print_resources(resources: tuple) -> None:
    for group in resources:
        for resource in group:
            print(f"Resource: {resource['Name']} {resource.get('Id', resource.get('ID', ''))}")


def check_ports(config: DatabaseConfig, containers: list[dict], environ: dict[str, str]) -> None:
    macos = platform.system() == "Darwin"
    listeners = run(
        ["netstat", "-an", "-p", "tcp"] if macos else ["ss", "-H", "-ltn"],
        environ,
        strict_stderr=True,
    )
    occupied = any(
        re.search(rf"[:.]{config.port}\s", line) and (not macos or "LISTEN" in line)
        for line in listeners.splitlines()
    )
    published = run(["docker", "ps", "--format", "{{.ID}} {{.Ports}}"], environ)
    owned = any(
        c.get("Running")
        and any(
            line.startswith(c["Id"][:12]) and re.search(rf"127\.0\.0\.1:{config.port}->", line)
            for line in published.splitlines()
        )
        for c in containers
    )
    for line in published.splitlines():
        if re.search(rf":{config.port}->", line) and not any(
            line.startswith(c["Id"][:12]) for c in containers
        ):
            raise PersistenceError(
                "Selected port is published by another container; retain it and stop."
            )
    if occupied and not owned:
        raise PersistenceError(
            "Selected port occupied; do not change ports or stop a conflicting service."
        )
    if not owned:
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", config.port))
        except OSError:
            raise PersistenceError(
                "Selected loopback port unavailable; no startup attempted."
            ) from None
    if "microsoft" in platform.release().lower():
        executable = shutil.which("powershell.exe")
        if not executable:
            raise PersistenceError(
                "Windows port proof unavailable. Run the documented PowerShell checks; startup refused."
            )
        # Each host query must succeed independently; a later query cannot mask an earlier failure.
        command = (
            f"$ErrorActionPreference='Stop'; $p={config.port}; "
            "$c=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | "
            "Where-Object LocalPort -eq $p); Write-Output $c.Count"
        )
        prefix = [executable, "-NoProfile", "-NonInteractive", "-Command"]
        count = run([*prefix, command], environ, strict_stderr=True).strip()
        if not count.isdecimal():
            raise PersistenceError("Windows listener proof ambiguous; startup refused.")
        if int(count) and not owned:
            raise PersistenceError("Windows listener occupies selected port; startup refused.")
        for family in ("ipv4", "ipv6"):
            command = (
                f"netsh interface {family} show excludedportrange protocol=tcp; exit $LASTEXITCODE"
            )
            output = run([*prefix, command], environ, strict_stderr=True)
            ranges = re.findall(r"(?m)^\s*(\d+)\s+(\d+)\s*\*?\s*$", output)
            empty_known = ("start port" in output.lower() and "end port" in output.lower()) or (
                "no excluded port ranges" in output.lower()
            )
            if (not ranges and not empty_known) or any(
                int(a) > int(b) or int(a) <= config.port <= int(b) for a, b in ranges
            ):
                raise PersistenceError(
                    "Windows reservation proof ambiguous/occupied; startup refused."
                )


def preflight(config: DatabaseConfig, root: Path, *, ports: bool) -> tuple[dict[str, str], tuple]:
    environ = child_env(config)
    read_bootstrap(root)
    context = run(["docker", "context", "show"], environ).strip()
    endpoint = json.loads(run(["docker", "context", "inspect", context], environ))[0]["Endpoints"][
        "docker"
    ]["Host"]
    if not endpoint.startswith("unix://"):
        raise PersistenceError(
            "Only the existing local Unix Docker context is supported; context unchanged."
        )
    run(["docker", "info", "--format", "{{.ServerVersion}}"], environ)
    model = json.loads(run([*compose_args(config, root), "config", "--format", "json"], environ))
    validate_model(model, config, root)
    resources = inventory(config, root, environ)
    if ports:
        check_ports(config, resources[0], environ)
    print(f"Verified Docker context {context}; target {config.target}, project {config.project}.")
    print_resources(resources)
    return environ, resources


def lifecycle(action: str, config: DatabaseConfig, root: Path) -> None:
    if action == "probe":
        probe_database(config)
        print(f"{config.target} guarded runtime SQL probe passed.")
        return
    if action == "destroy-test" and config.target != "test":
        raise PersistenceError("Destruction is permitted only for test.")
    environ, resources = preflight(config, root, ports=action in ("preflight", "up"))
    if action == "preflight":
        return
    # A reachable server mismatch blocks lifecycle too. Down/stopped containers need no TCP proof.
    if resources[0]:
        running = run(
            ["docker", "inspect", "--format", "{{.State.Running}}", resources[0][0]["Id"]], environ
        ).strip()
        if running == "true":
            probe_database(config)
    args = [*compose_args(config, root)]
    if action == "up":
        read_bootstrap(root)
        run([*args, "up", "-d", "--wait", "--wait-timeout", "60"], environ, timeout=180)
        inventory(config, root, environ)
        probe_database(config)
    else:
        # Inventory immediately precedes mutation. No orphan removal or broadened retry.
        inventory(config, root, environ)
        read_bootstrap(root)
        try:
            run(
                [*args, "down", *(["--volumes"] if action == "destroy-test" else [])],
                environ,
                timeout=60,
            )
        except PersistenceError:
            print("Deletion/shutdown failed; remaining exact resources (no retry):")
            inventory(config, root, environ, report=True)
            raise
        remaining = inventory(config, root, environ)
        if remaining[0] or remaining[2] or (action == "destroy-test" and remaining[1]):
            print_resources(remaining)
            raise PersistenceError(
                "Partial shutdown/deletion; retain remaining resources, no broadened retry."
            )
    print(f"{config.target} {action} completed; dev volume deletion is never supported.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["setup", "preflight", "up", "down", "probe", "destroy-test"]
    )
    parser.add_argument("target", nargs="?", choices=["dev", "test"])
    parser.add_argument("--namespace")
    parser.add_argument("--dev-port", type=int, default=55432)
    parser.add_argument("--test-port", type=int, default=55433)
    args = parser.parse_args()
    try:
        if args.action == "setup":
            if not args.namespace or args.target:
                raise PersistenceError(
                    "Setup requires --namespace and creates two separate local files once."
                )
            setup(ROOT, args.namespace, args.dev_port, args.test_port)
            print("Created separate ignored mode-0600 local configs; no secrets printed.")
        else:
            target = select_target(
                "test"
                if args.action == "destroy-test" and args.target is None
                else args.target or ""
            )
            lifecycle(args.action, load_config(target, ROOT), ROOT)
        return 0
    except PersistenceError as error:
        print(str(error))
        return 1
    except Exception:
        print(
            "Operator operation failed; details redacted. Retain resources and diagnose privately."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
