"""Target-selected configuration. Reading a local file is always explicit."""

import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy.engine import URL, make_url

Target = Literal["dev", "test"]
Use = Literal["runtime", "migration"]
IMAGE = "postgres:17.11-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826"
KEYS = frozenset(
    {
        "TARGET",
        "NAMESPACE",
        "INSTANCE_ID",
        "PORT",
        "PEER_PORT",
        "ADMIN_PASSWORD",
        "MIGRATOR_PASSWORD",
        "APP_PASSWORD",
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
    }
)


class PersistenceError(RuntimeError):
    """A redacted boundary failure, safe to show to an operator."""


def select_target(value: str) -> Target:
    if value not in ("dev", "test"):
        raise PersistenceError("Explicit target must be dev or test.")
    return "dev" if value == "dev" else "test"


def reject_ambient(environ: Mapping[str, str]) -> None:
    if any(k.startswith(("PG", "COMPOSE_", "PITLAB_")) for k in environ):
        raise PersistenceError(
            "Remove ambient PG*, COMPOSE_* and PITLAB_* settings; select one local target file."
        )


@dataclass(frozen=True)
class DatabaseConfig:
    target: Target
    namespace: str
    instance_id: str
    port: int
    peer_port: int
    admin_password: str = field(repr=False)
    migrator_password: str = field(repr=False)
    app_password: str = field(repr=False)
    runtime_url: URL = field(repr=False)
    migration_url: URL = field(repr=False)

    def __post_init__(self) -> None:
        select_target(self.target)
        if not re.fullmatch(r"[a-z][a-z0-9]{0,19}", self.namespace):
            raise PersistenceError("NAMESPACE must be 1–20 lowercase alphanumeric characters.")
        try:
            parsed = UUID(self.instance_id)
            valid_uuid = str(parsed) == self.instance_id and parsed.version == 4
        except (ValueError, AttributeError):
            valid_uuid = False
        if not valid_uuid:
            raise PersistenceError("INSTANCE_ID must be a canonical UUID4 from one-time setup.")
        if (
            not 1024 <= self.port <= 65535
            or not 1024 <= self.peer_port <= 65535
            or self.port == self.peer_port
            or self.port == {"dev": 55433, "test": 55432}[self.target]
        ):
            raise PersistenceError("PORT/PEER_PORT conflict with the selected target.")
        passwords = (self.admin_password, self.migrator_password, self.app_password)
        if len(set(passwords)) != 3 or any(not re.fullmatch(r"[a-f0-9]{64}", p) for p in passwords):
            raise PersistenceError("Use three independent 64-character hex passwords from setup.")
        for url, use, password in (
            (self.runtime_url, "runtime", self.app_password),
            (self.migration_url, "migration", self.migrator_password),
        ):
            if (
                url.drivername != "postgresql+psycopg"
                or url.host != "127.0.0.1"
                or url.port != self.port
                or url.database != self.database
                or url.username != self.role(use)
                or url.password != password
                or url.query
            ):
                raise PersistenceError("Database URL violates target, role or credential policy.")

    @property
    def database(self) -> str:
        return f"pitlab_{self.target}"

    @property
    def project(self) -> str:
        return f"pitlab-{self.namespace}-{self.target}"

    @property
    def marker(self) -> str:
        return f"pitlab:{self.target}:{self.namespace}:{self.instance_id}"

    def role(self, use: str) -> str:
        if use not in ("runtime", "migration"):
            raise PersistenceError("Connection use must be runtime or migration.")
        suffix = "app" if use == "runtime" else "migrator"
        return f"pitlab_{self.target}_{suffix}"


def parse_config(values: Mapping[str, str], target: Target) -> DatabaseConfig:
    if set(values) != KEYS or values.get("TARGET") != target:
        raise PersistenceError(
            "Local config has missing, unknown, duplicate or swapped target keys."
        )
    try:
        return DatabaseConfig(
            target,
            values["NAMESPACE"],
            values["INSTANCE_ID"],
            int(values["PORT"]),
            int(values["PEER_PORT"]),
            values["ADMIN_PASSWORD"],
            values["MIGRATOR_PASSWORD"],
            values["APP_PASSWORD"],
            make_url(values["DATABASE_URL"]),
            make_url(values["MIGRATION_DATABASE_URL"]),
        )
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(
            "Malformed target configuration; values have been redacted."
        ) from None


def load_config(
    target: Target, root: Path, *, environ: Mapping[str, str] | None = None
) -> DatabaseConfig:
    select_target(target)
    reject_ambient(os.environ if environ is None else environ)
    path = root / f".env.{target}.local"
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise PersistenceError(
                "Local config must be an operator-owned regular file, mode 0600."
            )
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep or key not in KEYS or key in values or not value or value.strip() != value:
                raise PersistenceError(
                    "Malformed local config; only unquoted KEY=VALUE is supported."
                )
            values[key] = value
    except PersistenceError:
        raise
    except OSError:
        raise PersistenceError(
            "Local target config unavailable; run one-time database.py setup."
        ) from None
    except UnicodeError:
        raise PersistenceError("Local target config must be UTF-8.") from None
    return parse_config(values, target)
