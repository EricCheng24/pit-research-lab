"""B-CORE private forms. Every live operation remains unavailable.

Pure validation of supplied bytes is not deployment, source or process evidence.
No environment/filesystem/interpreter discovery occurs in this module.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import PurePosixPath

from pit_research_lab.mvp.f6 import contracts as c


class ModelError(ValueError):
    def __init__(self, code: str = "INVALID_MODEL") -> None:
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str = "INVALID_MODEL") -> None:
    if not condition:
        raise ModelError(code)


def bounded_record(raw: bytes, fields: str, ceiling: int = 16384) -> c.WireObject:
    """Linear bounds precede the strict decoder; require canonical exact bytes."""
    require(type(raw) is bytes and 0 < len(raw) <= ceiling)
    depth = tokens = digits = 0
    quoted = escaped = False
    for ch in raw:
        if quoted:
            if escaped:
                escaped = False
            elif ch == 92:
                escaped = True
            elif ch == 34:
                quoted = False
        elif ch == 34:
            quoted = True
            tokens += 1
        elif ch in (91, 123):
            depth += 1
            tokens += 1
        elif ch in (93, 125):
            depth -= 1
        elif ch == 44:
            tokens += 1
        digits = digits + 1 if not quoted and ch in b"0123456789-+.eE" else 0
        require(0 <= depth <= 16 and tokens <= 1000 and digits <= 32)
    require(depth == 0 and not quoted)
    try:
        value = c.record(c.decode_json(raw), fields)
        require(c.canonical_json(value) == raw)
        return value
    except c.ContractError:
        raise ModelError() from None


def digest(domain: str, raw: bytes) -> str:
    require(
        domain
        in ("INTENT", "EXPECTATION", "OWNER", "EVENT", "LAUNCHER", "CHILD", "WAIT", "QUIESCENCE")
    )
    require(type(raw) is bytes and len(raw) <= 262144)
    return sha256(b"F6B_" + domain.encode("ascii") + b"_V1\0" + raw).hexdigest()


def decimal_text(value: object, *, positive: bool = False) -> str:
    require(type(value) is str and len(value) <= 20)
    assert isinstance(value, str)
    require(re.fullmatch(r"0|[1-9][0-9]*", value) is not None)
    require(int(value) <= 2**63 - 1 and (not positive or int(value) > 0))
    return value


def path_form(value: str) -> str:
    require(type(value) is str and 1 < len(value) <= 4096)
    require(value.startswith("/") and not value.startswith("//"))
    require(str(PurePosixPath(value)) == value and ".." not in value.split("/"))
    require(all(32 <= ord(ch) < 127 and ch not in "\\%" for ch in value))
    return value


EXPECTATION_FIELDS = (
    "version installation_id allocation_id command_policy_sha256 environment_policy_sha256 "
    "source_inventory_sha256 filesystem_profile_sha256 resource_policy_sha256"
)


@dataclass(frozen=True, slots=True)
class Expectations:
    raw: bytes

    def __post_init__(self) -> None:
        obj = self.values()
        require(type(obj["version"]) is int and obj["version"] == 1)
        try:
            for key in ("installation_id", "allocation_id"):
                c.uuid4_text(obj[key])
            require(obj["installation_id"] != obj["allocation_id"])
            for key in EXPECTATION_FIELDS.split()[3:]:
                c.sha256_text(obj[key])
        except c.ContractError:
            raise ModelError() from None

    def values(self) -> c.WireObject:
        return bounded_record(self.raw, EXPECTATION_FIELDS)


@dataclass(frozen=True, slots=True)
class FixedCommandDeclaration:
    """Lexical future argv only. Constructing it never probes or runs Python."""

    python: str
    checkout: str
    output_leaf: str

    def __post_init__(self) -> None:
        for value in (self.python, self.checkout, self.output_leaf):
            path_form(value)
        require(not PurePosixPath(self.output_leaf).is_relative_to(self.checkout))

    def argv(self) -> tuple[str, ...]:
        self.__post_init__()
        return (
            self.python,
            "-B",
            "-m",
            "pit_research_lab.mvp.f3_l1.cli",
            "--output-dir",
            self.output_leaf,
        )


class Refusal(StrEnum):
    B_CORE_AUTHORITY_ABSENT = "B_CORE_AUTHORITY_ABSENT"


def launch_refusal(expectations: Expectations | None = None) -> Refusal:
    if expectations is not None:
        require(type(expectations) is Expectations)
        expectations.__post_init__()
    return Refusal.B_CORE_AUTHORITY_ABSENT


@dataclass(frozen=True, slots=True)
class FinitePolicy:
    """Representation bounds, not chosen or enforceable production quotas."""

    wall_seconds: int
    cpu_seconds: int
    memory_bytes: int
    output_bytes: int
    file_bytes: int
    open_files: int
    processes: int
    log_bytes: int
    approval_ref: str | None = None

    def __post_init__(self) -> None:
        for value in (
            self.wall_seconds,
            self.cpu_seconds,
            self.memory_bytes,
            self.output_bytes,
            self.file_bytes,
            self.open_files,
            self.processes,
            self.log_bytes,
        ):
            require(type(value) is int and 0 < value <= 2**53 - 1)
        if self.approval_ref is not None:
            try:
                c.sha256_text(self.approval_ref)
            except c.ContractError:
                raise ModelError() from None

    def live_refusal(self) -> Refusal:
        self.__post_init__()
        return Refusal.B_CORE_AUTHORITY_ABSENT


def environment_declaration(
    checkout: str, home: str, temporary: str, path: str
) -> tuple[tuple[str, str], ...]:
    """Build from supplied lexical operands, never inherit a parent environment."""
    for item in (checkout, home, temporary):
        path_form(item)
    require(type(path) is str and len(path) <= 4096)
    for item in path.split(":"):
        path_form(item)
    return (
        ("PATH", path),
        ("PYTHONPATH", checkout + "/src"),
        ("HOME", home),
        ("TMPDIR", temporary),
        ("LANG", "C.UTF-8"),
        ("LC_ALL", "C.UTF-8"),
        ("PYTHONDONTWRITEBYTECODE", "1"),
        ("PYTHONNOUSERSITE", "1"),
    )
