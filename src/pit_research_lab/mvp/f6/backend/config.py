"""Closed configuration *forms*, not approved runtime or launch credentials.

No environment, filesystem or interpreter discovery occurs here. Numeric ranges
are representation bounds, not selected production quotas. Even a populated form
cannot establish supervisor, runtime, storage or release authority in P1-03A.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from pit_research_lab.mvp.f6 import contracts as c


class ConfigurationError(ValueError):
    """A fixed, non-disclosing form-validation error."""

    def __init__(self) -> None:
        super().__init__("INVALID_CONFIGURATION")


def _check(condition: bool) -> None:
    if not condition:
        raise ConfigurationError()


def absolute_path(value: str) -> str:
    """Lexical Linux form only; does not prove existence, ownership or safety."""
    _check(type(value) is str and 1 < len(value) <= 4096)
    _check(value.startswith("/") and not value.startswith("//"))
    _check(not any(ch in value for ch in ("\\", "%", "\x00", "\r", "\n")))
    _check(all(ord(ch) >= 32 and ord(ch) < 127 for ch in value))
    _check(str(PurePosixPath(value)) == value and ".." not in value.split("/"))
    return value


class Limit(StrEnum):
    BODY_BYTES = "BODY_BYTES"
    JSON_DEPTH = "JSON_DEPTH"
    WALL_SECONDS = "WALL_SECONDS"
    CPU_SECONDS = "CPU_SECONDS"
    ADDRESS_SPACE_BYTES = "ADDRESS_SPACE_BYTES"
    FILE_BYTES = "FILE_BYTES"
    OPEN_FILES = "OPEN_FILES"
    PROCESSES = "PROCESSES"
    OUTPUT_BYTES = "OUTPUT_BYTES"
    LOG_BYTES = "LOG_BYTES"
    DISK_BYTES = "DISK_BYTES"
    CATALOG_BYTES = "CATALOG_BYTES"
    RUN_COUNT = "RUN_COUNT"
    TERM_GRACE_SECONDS = "TERM_GRACE_SECONDS"
    RETENTION_SECONDS = "RETENTION_SECONDS"


@dataclass(frozen=True, slots=True)
class PolicyForm:
    """Complete immutable form; a supplied approval reference is only a claim."""

    limits: tuple[tuple[Limit, int], ...]
    approval_ref: str | None = None

    def __post_init__(self) -> None:
        _check(type(self.limits) is tuple and len(self.limits) == len(Limit))
        seen: set[Limit] = set()
        for entry in self.limits:
            _check(type(entry) is tuple and len(entry) == 2)
            key, value = entry
            _check(type(key) is Limit and key not in seen)
            _check(type(value) is int and 0 < value <= 2**53 - 1)
            seen.add(key)
        _check(seen == set(Limit))
        if self.approval_ref is not None:
            _digest(self.approval_ref)


def _digest(value: str) -> None:
    _check(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)


@dataclass(frozen=True, slots=True)
class ProvenanceForm:
    """Expected pins supplied independently; no live-byte measurement is made."""

    python_path: str
    python_version: str
    checkout_path: str
    import_path: str
    git_head: str
    code_sha256: str
    lock_sha256: str
    source_sha256: str
    manifest_sha256: str
    protocol_sha256: str
    dataset_sha256: str
    approval_ref: str | None = None

    def __post_init__(self) -> None:
        for path in (self.python_path, self.checkout_path, self.import_path):
            absolute_path(path)
        _check(self.import_path == self.checkout_path + "/src")
        _check(
            type(self.python_version) is str
            and re.fullmatch(r"3\.12\.(0|[1-9][0-9]{0,3})", self.python_version) is not None
        )
        _check(
            type(self.git_head) is str and re.fullmatch(r"[0-9a-f]{40}", self.git_head) is not None
        )
        for pin in (
            self.code_sha256,
            self.lock_sha256,
            self.source_sha256,
            self.manifest_sha256,
            self.protocol_sha256,
            self.dataset_sha256,
        ):
            _digest(pin)
        _check(self.source_sha256 == c.SOURCE_SHA256)
        _check(self.manifest_sha256 == c.MANIFEST_SHA256)
        _check(self.protocol_sha256 == c.PROTOCOL_SHA256)
        _check(self.dataset_sha256 == c.DATASET_SHA256)
        if self.approval_ref is not None:
            _digest(self.approval_ref)


@dataclass(frozen=True, slots=True)
class Configuration:
    """Unconfigured by default. Unknown keyword arguments are rejected by Python."""

    version: str = c.VERSION
    capability_id: str = c.CAPABILITY_ID
    policy: PolicyForm | None = None
    provenance: ProvenanceForm | None = None
    private_root: str | None = None
    port: int | None = None
    installation_id: str | None = None
    storage_approval_ref: str | None = None

    def __post_init__(self) -> None:
        _check(self.version == c.VERSION and self.capability_id == c.CAPABILITY_ID)
        if self.policy is not None:
            _check(type(self.policy) is PolicyForm)
            self.policy.__post_init__()
        if self.provenance is not None:
            _check(type(self.provenance) is ProvenanceForm)
            self.provenance.__post_init__()
        if self.private_root is not None:
            absolute_path(self.private_root)
        if self.port is not None:
            _check(type(self.port) is int and 1 <= self.port <= 65535)
        if self.installation_id is not None:
            try:
                c.uuid4_text(self.installation_id)
            except c.ContractError:
                raise ConfigurationError() from None
        if self.storage_approval_ref is not None:
            _digest(self.storage_approval_ref)


class Unavailability(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAPPROVED_FORM = "UNAPPROVED_FORM"
    B_PHASE_AUTHORITY_ABSENT = "B_PHASE_AUTHORITY_ABSENT"


def launch_refusal(configuration: Configuration) -> Unavailability:
    """Total refusal predicate. No positive permission or authenticity switch exists."""
    _check(type(configuration) is Configuration)
    configuration.__post_init__()
    if (
        configuration.policy is None
        or configuration.provenance is None
        or configuration.private_root is None
        or configuration.port is None
        or configuration.installation_id is None
    ):
        return Unavailability.NOT_CONFIGURED
    if (
        configuration.policy.approval_ref is None
        or configuration.provenance.approval_ref is None
        or configuration.storage_approval_ref is None
    ):
        return Unavailability.UNAPPROVED_FORM
    return Unavailability.B_PHASE_AUTHORITY_ABSENT
