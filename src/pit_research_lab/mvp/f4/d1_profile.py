"""Closed, owner-pinned fixture profiles and one-role local configuration."""

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pit_research_lab.infrastructure.database.config import reject_ambient

LIMIT = 8 * 1024 * 1024
MAX_ROWS = 2000
NAMESPACE = "SYNTHETIC_F4_D1"
ISSUER = "fixture-issuer-v1"
REVENUE = "fixture-revenue-v1"
COLUMNS = {
    ISSUER: ("namespace", "code", "key", "name", "sector", "listed_date"),
    REVENUE: (
        "namespace",
        "code",
        "key",
        "name",
        "period",
        "basis",
        "currency",
        "unit",
        "amount",
        "report_date",
    ),
}
AUDIENCE = "LOCAL_FIXTURE_REVIEW"
ROLES = ("admin", "migrator", "custodian", "publisher", "reader")


class Refusal(ValueError):
    """A bounded reason that is safe to return to the operator."""


def require(condition: object, reason: str) -> None:
    if not condition:
        raise Refusal(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check_json(value: object, depth: int = 0) -> None:
    require(depth <= 20, "JSON_DEPTH_LIMIT")
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "INVALID_JSON_KEY")
        for item in value.values():
            check_json(item, depth + 1)
    elif isinstance(value, list | tuple):
        for item in value:
            check_json(item, depth + 1)
    elif type(value) is int:
        require(-(2**63) <= value < 2**63, "JSON_INTEGER_LIMIT")
    else:
        require(value is None or type(value) in (str, bool), "NONEXACT_JSON_VALUE")


def json_bytes(value: object) -> bytes:
    check_json(value)
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", errors="strict")


def digest(kind: str, value: object) -> str:
    require(
        kind in {"profile", "subject", "assertion", "receipt", "export"},
        "BAD_DIGEST_KIND",
    )
    return sha(f"pitlab-f4-d1/{kind}/v1\0".encode("ascii") + json_bytes(value))


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def decode(raw: bytes) -> Any:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        check_json(value)
        return value
    except (UnicodeError, ValueError, RecursionError):
        raise Refusal("INVALID_JSON") from None


def hex_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def timestamp(value: datetime) -> str:
    require(
        value.tzinfo is not None and value.utcoffset() is not None,
        "CLOCK_ZONE_REQUIRED",
    )
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def uuid4_text(value: object) -> str:
    try:
        parsed = UUID(str(value))
    except ValueError:
        raise Refusal("INVALID_UUID") from None
    require(parsed.version == 4 and str(parsed) == value, "INVALID_UUID")
    return str(parsed)


def profile_body(profile: str) -> dict[str, Any]:
    require(profile in COLUMNS, "UNKNOWN_FIXTURE_PROFILE")
    return {
        "profile": profile,
        "namespace": NAMESPACE,
        "mode": "SYNTHETIC_ONLY",
        "method": "FIXTURE_IMPORT",
        "audience": AUDIENCE,
        "attribution": "PIT Research Lab authored fictional fixture",
        "schema": list(COLUMNS[profile]),
        "parser": "csv-utf8-v1",
        "row_codes": ["0001", "0002"],
        "max_rows": MAX_ROWS,
        "max_bytes": LIMIT,
    }


def filename(name: object, suffix: str) -> str:
    require(
        isinstance(name, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.[a-z]+", name)
        and name.endswith(suffix),
        "UNSAFE_FILE_NAME",
    )
    return str(name)


def private_root(path: Path) -> None:
    require(path.is_absolute() and path.resolve() == path, "UNSAFE_PRIVATE_ROOT")
    info = path.lstat()
    require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.geteuid()
        and stat.S_IMODE(info.st_mode) == 0o700,
        "UNSAFE_PRIVATE_ROOT",
    )


def private_read(path: Path, limit: int) -> bytes:
    private_root(path.parent)
    parent = os.open(path.parent, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with os.fdopen(
            os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent),
            "rb",
        ) as opened:
            info = os.fstat(opened.fileno())
            require(
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_size <= limit,
                "UNSAFE_PRIVATE_FILE",
            )
            raw = opened.read(limit + 1)
            require(len(raw) == info.st_size and len(raw) <= limit, "UNSTABLE_PRIVATE_FILE")
            return raw
    finally:
        os.close(parent)


@dataclass(frozen=True)
class Target:
    target: str
    namespace: str
    instance: str
    port: int
    role: str
    password: str = field(repr=False)
    root: Path
    profiles: dict[str, str]
    inputs: dict[str, str]

    @property
    def marker(self) -> str:
        return f"pitlab:{self.target}:{self.namespace}:{self.instance}"

    @property
    def database(self) -> str:
        return f"pitlab_{self.target}"

    @property
    def user(self) -> str:
        return self.account(self.role)

    def account(self, role: str) -> str:
        require(role in ROLES, "UNKNOWN_ROLE")
        suffix = role if role in {"admin", "migrator"} else f"f4_{role}"
        return f"pitlab_{self.target}_{suffix}"

    def pin(self, profile: str, name: str) -> tuple[str, str]:
        require(self.role == "custodian", "CUSTODIAN_REQUIRED")
        profile_sha = digest("profile", profile_body(profile))
        require(self.profiles.get(profile) == profile_sha, "FIXTURE_PROFILE_NOT_PINNED")
        filename(name, ".csv")
        expected = self.inputs.get(f"{profile}/{name}")
        require(hex_digest(expected), "FIXTURE_FILE_NOT_PINNED")
        assert expected is not None
        return profile_sha, expected


def load_target(path: Path) -> Target:
    reject_ambient(os.environ)
    path = path.absolute()
    value = decode(private_read(path, 64 * 1024))
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "mode",
            "target",
            "namespace",
            "instance",
            "port",
            "role",
            "password",
            "root",
            "profiles",
            "inputs",
        }
        and value["mode"] == "SYNTHETIC_ONLY",
        "INVALID_FIXTURE_TARGET_CONFIG",
    )
    require(
        value["target"] in ("dev", "test") and value["role"] in ROLES,
        "INVALID_TARGET_ROLE",
    )
    require(
        isinstance(value["namespace"], str)
        and re.fullmatch(r"f4d1[a-z0-9]{3,16}", value["namespace"]),
        "NOT_DEDICATED_F4_NAMESPACE",
    )
    require(
        type(value["port"]) is int
        and 1024 <= value["port"] <= 65535
        and value["port"] not in {5432, 55432, 55433},
        "INVALID_F4_PORT",
    )
    require(hex_digest(value["password"]), "INVALID_ROLE_SECRET")
    require(isinstance(value["root"], str), "INVALID_PRIVATE_ROOT")
    root = Path(value["root"])
    private_root(root)
    profiles = value["profiles"]
    inputs = value["inputs"]
    require(
        isinstance(profiles, dict)
        and all(
            key in COLUMNS and val == digest("profile", profile_body(key))
            for key, val in profiles.items()
        )
        and isinstance(inputs, dict)
        and all(
            len(key.split("/")) == 2 and key.split("/")[0] in profiles and hex_digest(val)
            for key, val in inputs.items()
        ),
        "INVALID_PROFILE_PINS",
    )
    return Target(
        value["target"],
        value["namespace"],
        uuid4_text(value["instance"]),
        value["port"],
        value["role"],
        value["password"],
        root,
        profiles,
        inputs,
    )


def acquire() -> None:
    """Deliberate pre-configuration refusal. This edition has no real transport."""
    raise Refusal("REAL_ACQUISITION_NOT_GRANTED")
