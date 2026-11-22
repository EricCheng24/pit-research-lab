"""Supplied synthetic identity grammar only; never reads procfs or authenticates OS ownership."""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pit_research_lab.mvp.f6 import contracts as c

from .launch_policy import ModelError, Refusal, decimal_text, require


def boot_text(value: object) -> str:
    require(type(value) is str and len(value) == 36)
    assert isinstance(value, str)
    try:
        require(str(UUID(value)) == value and UUID(value).int != 0)
    except ValueError:
        raise ModelError() from None
    return value


def process_number(value: object) -> int:
    require(type(value) is int and 1 < value <= 2**31 - 1)
    assert isinstance(value, int)
    return value


@dataclass(frozen=True, slots=True)
class SuppliedStat:
    pid: int
    parent_pid: int
    pgid: int
    sid: int
    start_ticks: str
    state: str

    def __post_init__(self) -> None:
        for number in (self.pid, self.pgid, self.sid):
            process_number(number)
        require(type(self.parent_pid) is int and 0 <= self.parent_pid <= 2**31 - 1)
        decimal_text(self.start_ticks, positive=True)
        require(
            type(self.state) is str and self.state in tuple("RSDZTtXxKWPI") and len(self.state) == 1
        )


def parse_supplied_stat(raw: bytes) -> SuppliedStat:
    """Bounded stat-like text; reject ambiguous command delimiters and truncation.

    Accept 20..64 fields after comm, including Linux field22 starttime.
    This is parsing supplied text, not a kernel or namespace observation.
    """
    require(type(raw) is bytes and 0 < len(raw) <= 4096)
    try:
        value = raw.decode("ascii")
    except UnicodeError:
        raise ModelError() from None
    require("\n" not in value and "\r" not in value and value == value.strip())
    match = re.fullmatch(r"([1-9][0-9]{0,9}) \(([^()\x00-\x1f]{1,256})\) (.+)", value)
    require(match is not None)
    assert match is not None
    parts = match[3].split(" ")
    require(20 <= len(parts) <= 64 and len(parts[0]) == 1)
    for item in parts[1:]:
        require(re.fullmatch(r"0|-?[1-9][0-9]{0,19}", item) is not None)
    return SuppliedStat(
        int(match[1]), int(parts[1]), int(parts[2]), int(parts[3]), parts[19], parts[0]
    )


@dataclass(frozen=True, slots=True)
class SyntheticIdentity:
    installation_id: str
    generation: str
    boot_id: str
    pid: int
    start_ticks: str
    pgid: int
    sid: int
    launcher_id: str
    nonce_sha256: str
    lease_dev: str
    lease_ino: str
    executable_sha256: str

    def __post_init__(self) -> None:
        try:
            for value in (self.installation_id, self.generation, self.launcher_id):
                c.uuid4_text(value)
            require(len({self.installation_id, self.generation, self.launcher_id}) == 3)
            for value in (self.nonce_sha256, self.executable_sha256):
                c.sha256_text(value)
        except c.ContractError:
            raise ModelError() from None
        boot_text(self.boot_id)
        for number in (self.pid, self.pgid, self.sid):
            process_number(number)
        for value in (self.start_ticks, self.lease_ino):
            decimal_text(value, positive=True)
        decimal_text(self.lease_dev)

    def live_refusal(self) -> Refusal:
        self.__post_init__()
        return Refusal.B_CORE_AUTHORITY_ABSENT


class Comparison(StrEnum):
    MODEL_MATCH = "MODEL_MATCH"
    MODEL_MISMATCH = "MODEL_MISMATCH"


def compare_supplied(expected: SyntheticIdentity, supplied: SyntheticIdentity) -> Comparison:
    require(type(expected) is SyntheticIdentity and type(supplied) is SyntheticIdentity)
    expected.__post_init__()
    supplied.__post_init__()
    return Comparison.MODEL_MATCH if expected == supplied else Comparison.MODEL_MISMATCH
