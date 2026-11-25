"""Custodian-only receipt checks over the immutable accepted ZIP."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import struct
import time
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from . import contract as c
from .contract import Record, array, choice, fail, fraction, integer, record, require, text

ZIP_LIMIT = 10 * 1024**2
MEMBER_LIMIT = 16 * 1024**2
TOTAL_LIMIT = 48 * 1024**2
MANIFEST_LIMIT = 24 * 1024
CHUNK = 64 * 1024
MANIFEST = "handoff/SHA256SUMS"
PROFILE = "PRIVATE_OWNER_AND_NAMED_REVIEWER_V1"
PROFILE_BASE = "5837c88038dc2ec668882cf6abad56b601f36496"
HISTORICAL = "5ee19b68067e58f29742f67b2db3a2de6dd25152"
ACCEPTANCE = f"{c.HISTORICAL_WU}:ACCEPTED:2026-11-24"
F3 = "f3-producer/"
PEERS = ("f5-run-a/", "f5-run-b/")
PRODUCER = "witness/producer-receipt.json"
PAIR_POST = "witness/pair-post.json"
EFFECTIVE = ("witness/effective-post-a-b.json", "witness/effective-post-b-a.json")
F3_FILES = ("bindings", "folds", "handoff", "predictions", "result", "spec", "states", "targets")
F5_FILES = ("spec", "decisions", "ledger", "metrics", "evidence")
ORIGINAL_POLICIES = (
    "QUALIFIED_EW_CAP50_V1",
    "GROWTH_POSITIVE_EW_CAP50_V1",
    "F3_OOS_POSITIVE_EW_CAP50_V1",
)
MIRROR_POLICIES = tuple(p + "_ZERO_COST_MIRROR" for p in ORIGINAL_POLICIES)
ROOT_RECORD = "files root root_identity"
ATTEMPT_FIELDS = (
    "attempt_id process_id started_at finished_at elapsed_seconds execution_status "
    "comparison_status replay_status completed_stages first_failure evidence_sha256 "
    "peer_evidence_sha256 peer_attempt_id peer_process_id producer_root origin_handoff_status"
)
F3_STAGES = (
    "SPEC_PINNED",
    "F2_INPUTS_QUALIFIED",
    "F1_TRAINING_SELECTED",
    "F1_FITTED",
    "F1_PREDICTIONS_SEALED",
    "F2_TRAINING_SELECTED",
    "F2_FITTED",
    "F2_PREDICTIONS_SEALED",
    "F1_SCORED",
    "F2_SCORED",
    "EVIDENCE_WRITTEN",
)
F5_STAGES = (
    "F3_ORIGIN_AND_SOURCE_SEMANTICS_VERIFIED",
    "TYPED_SLOT_CENSUS_SEALED",
    "PORTFOLIOS_EVALUATED",
    "DETERMINISTIC_EVIDENCE_WRITTEN",
)
HANDOFF = {
    "handoff/Controlled_Commit_and_Quality_Report.md": "ea1b564fb659d0d846d8591e50e6b1b3d98931d3ca4ec831b2f4c910b6e94a81",
    "handoff/Integrated_Research_Acceptance_Report.md": "7cc6198d89eea3f947e580fc987165b1d3ff5bb5ef03ac32ae95c415217619a4",
    "handoff/Evidence_Index.md": "5a099c4d5aa19436cba538112bc1dc7039d07d3c92f57c70789bb3b33e35fcdc",
}
LOGS = (
    "logs/g3-producer.json",
    "logs/g3-producer.stderr",
    "logs/g3-producer.stdout",
    "logs/g3-producer.time",
)
BUILD_FILES = (
    "__init__.py",
    "__main__.py",
    "archive.py",
    "contract.py",
    "projection.py",
    "render.py",
)


@dataclass(frozen=True)
class Release:
    edition: str
    acceptance_ref: str
    release_profile: str
    basename: str
    size: int
    archive_sha256: str
    manifest_sha256: str
    historical_wu: str
    original_revision: str
    f3_sha256: str
    producer_sha256: str
    receipt_id: str
    f5_sha256: str
    effective_sha256: str
    pair_post_sha256: str

    @property
    def identity(self) -> str:
        return c.identify(c.RELEASE_DOMAIN, asdict(self))


_RELEASE = Release(
    edition=c.EDITION,
    acceptance_ref=ACCEPTANCE,
    release_profile=PROFILE,
    basename="MVP-F5-WEEKLY-COMPARE-01_Review_Bundle.zip",
    size=8941837,
    archive_sha256="ec88e757e35d81a28f1055541dae4bcefb45344d077e948b197bb9e9e14886e7",
    manifest_sha256="386f0dccd86142ec57e81c9b3de47c5e806037cb252bc1fcd8173c00b78a71f6",
    historical_wu=c.HISTORICAL_WU,
    original_revision=HISTORICAL,
    f3_sha256="50f9f456691d4e4820e6c855cf0c6f8af3cb127d15a88da287f73b9243977fe2",
    producer_sha256="9d4c9409afb934ee6fdf1a5e8687dd2f261a2ff4712e3d2c30d85555fe79efe2",
    receipt_id="eb3dbf66ee18a888bbba21d4697dc805f11c3e3fb9856c3dc205981dff1965b4",
    f5_sha256="c037be84f9b66f5514ac03d59684f89cea87bc9f6bce7b834612eb7dcfcc30ea",
    effective_sha256="699369eaf5a7395aaac7f60389cf11fc76b76ead721419e25b5fe14fd0278029",
    pair_post_sha256="9bd703d1dae535213909c2312d2ce7a3c4b3793e2277d0f5a16d065d995c441d",
)


def _gate(release: Release | None, edition: str) -> Release:
    require(edition == c.EDITION, "UNKNOWN_EDITION")
    require(release is not None, "EDITION_WITHHELD")
    assert release is not None
    require(release == _RELEASE, "PROVENANCE_MISMATCH")
    return release


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash(value: object) -> str:
    # Historical research JSON has no domain prefix, unlike U1 identities.
    return _sha(c.canonical(value))


class Budget:
    def __init__(self) -> None:
        self.until = time.monotonic() + 60

    def check(self) -> None:
        require(time.monotonic() <= self.until, "BOUNDS_EXCEEDED")


def build_identity() -> str:
    folder = Path(__file__).absolute().parent
    rows = []
    for leaf in BUILD_FILES:
        with (folder / leaf).open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        rows.append({"file": leaf, "sha256": digest})
    return c.identify(c.BUILD_DOMAIN, rows)


def account_home() -> Path:
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        fail("UNSAFE_OUTPUT")


def file_identity(st: os.stat_result) -> tuple[int, ...]:
    return (
        st.st_dev,
        st.st_ino,
        st.st_mode,
        st.st_uid,
        st.st_gid,
        st.st_nlink,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )


def directory_identity(st: os.stat_result) -> tuple[int, ...]:
    return st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid


@dataclass(frozen=True)
class Directory:
    fd: int
    parent: Directory | None
    name: str
    identity: tuple[int, ...]

    def recheck(self, code: str) -> None:
        try:
            if self.parent is not None:
                self.parent.recheck(code)
                named = os.stat(self.name, dir_fd=self.parent.fd, follow_symlinks=False)
                require(directory_identity(named) == self.identity, code)
            require(directory_identity(os.fstat(self.fd)) == self.identity, code)
        except OSError:
            fail(code)


def _native_filesystem(fd: int) -> bool:
    """Recognize local Linux mounts by the kernel's descriptor mount ID."""
    try:
        with Path(f"/proc/self/fdinfo/{fd}").open("rb") as info:
            records = info.read(4096).splitlines()
        mount_ids = [line.split()[1] for line in records if line.startswith(b"mnt_id:\t")]
        if len(mount_ids) != 1:
            return False
        with Path("/proc/self/mountinfo").open("rb") as mounts:
            data = mounts.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            return False
        for line in data.splitlines():
            before, sep, after = line.partition(b" - ")
            if sep and before.split()[0] == mount_ids[0]:
                return after.split()[0] in {
                    b"ext2",
                    b"ext3",
                    b"ext4",
                    b"xfs",
                    b"btrfs",
                    b"zfs",
                    b"f2fs",
                    b"tmpfs",
                    b"overlay",
                }
    except OSError:
        return False
    return False


def open_directory(
    stack: ExitStack,
    parent: Directory | None,
    name: str,
    code: str,
    *,
    private: bool = False,
    missing: str | None = None,
) -> Directory:
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=None if parent is None else parent.fd,
        )
    except FileNotFoundError:
        fail(missing or code)
    except OSError:
        fail(code)
    stack.callback(os.close, fd)
    st = os.fstat(fd)
    mode = stat.S_IMODE(st.st_mode)
    trusted_sticky = st.st_uid == 0 and bool(mode & stat.S_ISVTX)
    require(st.st_uid in (0, os.getuid()) and (mode & 0o022 == 0 or trusted_sticky), code)
    if private:
        require(st.st_uid == os.getuid() and mode == 0o700 and _native_filesystem(fd), code)
    identity = directory_identity(st)
    ancestor = parent
    while ancestor is not None:
        require(ancestor.identity[:2] != identity[:2], code)
        ancestor = ancestor.parent
    result = Directory(fd, parent, name, identity)
    result.recheck(code)
    return result


def open_application(stack: ExitStack, home: Path) -> Directory:
    code = "UNSAFE_OUTPUT"
    require(home.is_absolute() and home.anchor == "/" and ".." not in home.parts, code)
    app = home / ".local/share/pit-research-lab/f6-u1"
    # Checked from the installed/source module, without reading Git or its metadata.
    checkout = Path(__file__).resolve().parents[5]
    require(not app.is_relative_to(checkout) and not checkout.is_relative_to(app), code)
    directory = open_directory(stack, None, "/", code)
    for ix, part in enumerate(app.parts[1:], start=1):
        directory = open_directory(stack, directory, part, code, private=ix == len(app.parts) - 1)
    return directory


def _check_regular(fd: int, directory: Directory, name: str, code: str) -> os.stat_result:
    st = os.fstat(fd)
    require(
        stat.S_ISREG(st.st_mode)
        and stat.S_IMODE(st.st_mode) == 0o600
        and st.st_uid == os.getuid()
        and st.st_nlink == 1
        and st.st_dev == directory.identity[0],
        code,
    )
    named = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
    require(file_identity(st) == file_identity(named), code)
    return st


def _open_file(directory: Directory, name: str) -> int:
    named = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
    require(
        stat.S_ISREG(named.st_mode)
        and named.st_uid == os.getuid()
        and named.st_nlink == 1
        and stat.S_IMODE(named.st_mode) == 0o600,
        "UNSAFE_INPUT",
    )
    return os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory.fd
    )


def marker(directory: Directory) -> None:
    try:
        fd = _open_file(directory, "WITHHOLD")
    except FileNotFoundError:
        return
    except OSError:
        fail("UNSAFE_INPUT")
    try:
        before = _check_regular(fd, directory, "WITHHOLD", "UNSAFE_INPUT")
        require(before.st_size == 9 and os.read(fd, 10) == b"WITHHELD\n", "UNSAFE_INPUT")
        after = _check_regular(fd, directory, "WITHHOLD", "INPUT_CHANGED")
        require(file_identity(before) == file_identity(after), "INPUT_CHANGED")
    except OSError:
        fail("UNSAFE_INPUT")
    finally:
        os.close(fd)
    fail("EDITION_WITHHELD")


@dataclass(frozen=True)
class Input:
    raw: bytes
    fd: int
    directory: Directory
    basename: str
    identity: tuple[int, ...]

    def recheck(self) -> None:
        self.directory.recheck("INPUT_CHANGED")
        marker(self.directory)
        try:
            current = _check_regular(self.fd, self.directory, self.basename, "INPUT_CHANGED")
        except OSError:
            fail("INPUT_CHANGED")
        require(file_identity(current) == self.identity, "INPUT_CHANGED")


def open_input(
    stack: ExitStack,
    directory: Directory,
    release: Release,
    budget: Budget,
) -> Input:
    marker(directory)
    try:
        fd = _open_file(directory, release.basename)
    except FileNotFoundError:
        fail("ARCHIVE_MISSING")
    except OSError:
        fail("UNSAFE_INPUT")
    stack.callback(os.close, fd)
    try:
        st = _check_regular(fd, directory, release.basename, "UNSAFE_INPUT")
        require(st.st_size <= ZIP_LIMIT, "BOUNDS_EXCEEDED")
        require(st.st_size == release.size, "ARCHIVE_PIN")
        raw = bytearray()
        while True:
            budget.check()
            chunk = os.read(fd, min(CHUNK, release.size - len(raw) + 1))
            if not chunk:
                break
            raw.extend(chunk)
            require(len(raw) <= release.size, "INPUT_CHANGED")
    except OSError:
        fail("INPUT_IO")
    result = Input(bytes(raw), fd, directory, release.basename, file_identity(st))
    result.recheck()
    require(
        len(result.raw) == release.size and _sha(result.raw) == release.archive_sha256,
        "ARCHIVE_PIN",
    )
    return result


_EOCD = struct.Struct("<4s4H2IH")
_CENTRAL = struct.Struct("<4s6H3I5H2I")
_LOCAL = struct.Struct("<4s5H3I2H")
_LEAF = re.compile(r"[A-Za-z0-9_.-]+", re.ASCII)
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])", re.ASCII)


def _name(name: str) -> None:
    parts = name.split("/")
    require(0 < len(name) <= 96 and len(parts) <= 2, "ARCHIVE_STRUCTURE")
    for part in parts:
        require(
            _LEAF.fullmatch(part) is not None
            and not part.endswith(".")
            and _RESERVED.fullmatch(part.upper().split(".")[0]) is None,
            "ARCHIVE_STRUCTURE",
        )


@dataclass(frozen=True)
class Member:
    start: int
    stop: int
    size: int
    crc: int


def _zip_layout(raw: bytes) -> dict[str, Member]:
    """Bound central parsing and match each physical local record before inflation."""
    require(len(raw) >= _EOCD.size, "ARCHIVE_STRUCTURE")
    sig, disk, start_disk, on_disk, total, size, central, comment = _EOCD.unpack_from(
        raw, len(raw) - _EOCD.size
    )
    end = len(raw) - _EOCD.size
    require(
        sig == b"PK\x05\x06"
        and disk == start_disk == comment == 0
        and on_disk == total == 200
        and 0 < central < end
        and central + size == end,
        "ARCHIVE_STRUCTURE",
    )
    offset = central
    spans: list[tuple[int, int]] = []
    names: set[str] = set()
    members: dict[str, Member] = {}
    declared = 0
    for _ in range(total):
        require(offset + _CENTRAL.size <= end, "ARCHIVE_STRUCTURE")
        (
            magic,
            creator,
            version,
            flags,
            method,
            stamp,
            day,
            crc,
            packed,
            unpacked,
            name_size,
            extra,
            note,
            volume,
            _internal,
            attrs,
            local,
        ) = _CENTRAL.unpack_from(raw, offset)
        require(
            magic == b"PK\x01\x02"
            and creator == (3 << 8) + 20
            and version == 20
            and flags == extra == note == volume == 0
            and method == zipfile.ZIP_DEFLATED
            and stat.S_IFMT(attrs >> 16) == stat.S_IFREG
            and 0 < name_size <= 96,
            "ARCHIVE_STRUCTURE",
        )
        require(
            packed > 0 and unpacked <= MEMBER_LIMIT and unpacked <= 20 * packed, "BOUNDS_EXCEEDED"
        )
        declared += unpacked
        require(declared <= TOTAL_LIMIT, "BOUNDS_EXCEEDED")
        offset += _CENTRAL.size
        require(offset + name_size <= end and local + _LOCAL.size <= central, "ARCHIVE_STRUCTURE")
        leaf = raw[offset : offset + name_size]
        offset += name_size
        require(leaf.isascii(), "ARCHIVE_STRUCTURE")
        name = leaf.decode("ascii")
        _name(name)
        folded = name.casefold()
        require(folded not in names, "ARCHIVE_STRUCTURE")
        names.add(folded)
        expected = (
            b"PK\x03\x04",
            version,
            flags,
            method,
            stamp,
            day,
            crc,
            packed,
            unpacked,
            name_size,
            0,
        )
        require(_LOCAL.unpack_from(raw, local) == expected, "ARCHIVE_STRUCTURE")
        content = local + _LOCAL.size
        finish = content + name_size + packed
        require(
            finish <= central and raw[content : content + name_size] == leaf, "ARCHIVE_STRUCTURE"
        )
        spans.append((local, finish))
        members[name] = Member(content + name_size, finish, unpacked, crc)
    require(offset == end, "ARCHIVE_STRUCTURE")
    previous = 0
    for start, stop in sorted(spans):
        require(start == previous, "ARCHIVE_STRUCTURE")
        previous = stop
    require(previous == central, "ARCHIVE_STRUCTURE")
    return members


@dataclass(frozen=True)
class Pin:
    size: int
    sha256: str


class Packet:
    def __init__(self, raw: bytes, members: dict[str, Member], budget: Budget) -> None:
        self.archive = raw
        self.members = members
        self.budget = budget
        self.pins: dict[str, Pin] = {}

    def raw(self, name: str, maximum: int = MEMBER_LIMIT) -> bytes:
        return b"".join(self._chunks(name, maximum))

    def _chunks(self, name: str, maximum: int) -> Iterator[bytes]:
        member = self.members.get(name)
        require(member is not None, "ARCHIVE_STRUCTURE")
        assert member is not None
        require(member.size <= maximum, "BOUNDS_EXCEEDED")
        inflated = zlib.decompressobj(-zlib.MAX_WBITS)
        offset, count, crc = member.start, 0, 0
        pending = b""
        while offset < member.stop or pending:
            self.budget.check()
            if not pending:
                end = min(offset + CHUNK, member.stop)
                pending = self.archive[offset:end]
                offset = end
            require(not inflated.eof, "ARCHIVE_STRUCTURE")
            try:
                chunk = inflated.decompress(pending, min(CHUNK, member.size - count + 1))
            except zlib.error:
                fail("ARCHIVE_STRUCTURE")
            pending = inflated.unconsumed_tail
            count += len(chunk)
            require(count <= member.size and not inflated.unused_data, "MEMBER_MISMATCH")
            crc = zlib.crc32(chunk, crc)
            if chunk:
                yield chunk
        require(inflated.eof and count == member.size and crc == member.crc, "MEMBER_MISMATCH")

    def exact_match(self, left: str, right: str) -> None:
        require(self.pins[left] == self.pins[right], "MEMBER_MISMATCH")
        # Equal contents can have different compressed stream/chunk boundaries.
        left_chunks = self._chunks(left, MEMBER_LIMIT)
        right_chunks = self._chunks(right, MEMBER_LIMIT)
        a, b = b"", b""
        while True:
            a, b = a or next(left_chunks, b""), b or next(right_chunks, b"")
            require(bool(a) == bool(b), "MEMBER_MISMATCH")
            if not a:
                return
            size = min(len(a), len(b))
            require(a[:size] == b[:size], "MEMBER_MISMATCH")
            a, b = a[size:], b[size:]

    def verify(self, release: Release) -> None:
        manifest = self.raw(MANIFEST, MANIFEST_LIMIT)
        require(_sha(manifest) == release.manifest_sha256, "MANIFEST_PIN")
        require(manifest.isascii() and manifest.endswith(b"\n"), "ARCHIVE_STRUCTURE")
        expected: dict[str, str] = {}
        rows = manifest.decode("ascii").split("\n")[:-1]
        require(len(rows) == 199, "ARCHIVE_STRUCTURE")
        for row in rows:
            digest, sep, name = row.partition("  ")
            require(sep and name != MANIFEST and name not in expected, "ARCHIVE_STRUCTURE")
            _name(name)
            expected[name] = text(digest, c.HEX64, "ARCHIVE_STRUCTURE")
        names = self.members.keys()
        for peer in PEERS:
            require({peer + n + ".json" for n in (*F5_FILES, "attempt")} <= names, "PEER_MISSING")
        require(names == set(expected) | {MANIFEST}, "ARCHIVE_STRUCTURE")
        count = len(manifest)
        for name, digest in expected.items():
            hashed = hashlib.sha256()
            length = 0
            for chunk in self._chunks(name, self.members[name].size):
                length += len(chunk)
                count += len(chunk)
                require(count <= TOTAL_LIMIT, "BOUNDS_EXCEEDED")
                hashed.update(chunk)
            require(
                length == self.members[name].size and hashed.hexdigest() == digest,
                "MEMBER_MISMATCH",
            )
            self.pins[name] = Pin(length, digest)

    def json(self, name: str) -> Record:
        return _decode(
            self.raw(name), self.budget, producer_post=name == "witness/producer-post.json"
        )

    def payload(self, prefix: str, kind: str, fields: str) -> Record:
        name = prefix + kind + ".json"
        raw = self.raw(name)
        row = record(_decode(raw, self.budget), "schema non_if03 payload")
        schema = (
            f"F3_L1_RESEARCH_{kind.upper()}_V0.1"
            if prefix == F3
            else f"F5_WEEKLY_SYNTHETIC_{kind.upper()}_V1"
        )
        require(row["schema"] == schema and row["non_if03"] is True)
        require(c.canonical(row) == raw, "MALFORMED_JSON")
        return record(row["payload"], fields)


@contextmanager
def _packet(raw: bytes, release: Release, budget: Budget) -> Iterator[Packet]:
    require(len(raw) <= ZIP_LIMIT, "BOUNDS_EXCEEDED")
    require(len(raw) == release.size and _sha(raw) == release.archive_sha256, "ARCHIVE_PIN")
    packet = Packet(raw, _zip_layout(raw), budget)
    packet.verify(release)
    yield packet


_JSON_TOKEN = re.compile(
    rb'[ \t\r\n]+|"(?:[^"\\\x00-\x1f]|\\.){0,8190}"'
    rb'|(?P<oversize>"(?:[^"\\\x00-\x1f]|\\.){8191})|-?[0-9]+(?:\.[0-9]+)?'
    rb"|[{}\[\],:]|true|false|null"
)
_HEAVY = frozenset((b"{", b"["))
_LIGHT = frozenset((b"}", b"]"))


def _unique(pairs: list[tuple[str, Any]]) -> Record:
    row: Record = {}
    for key, value in pairs:
        require(key not in row, "MALFORMED_JSON")
        row[key] = value
    return row


def _decimal_paths(value: object, path: tuple[str, ...] = ()) -> None:
    if type(value) is Decimal:
        allowed = path in (
            ("launch", "invocation", "wall_seconds"),
            ("launch", "invocation", "stage_observations", "previous_sample_seconds"),
        ) or (
            len(path) == 6
            and path[:4] == ("launch", "invocation", "stage_observations", "entries")
            and path[4] in F3_STAGES
            and path[5] in ("lower_seconds", "upper_seconds")
        )
        require(allowed, "MALFORMED_JSON")
    elif type(value) is dict:
        for key, item in cast(Record, value).items():
            _decimal_paths(item, (*path, key))
    elif type(value) is list:
        for item in cast(list[object], value):
            _decimal_paths(item, (*path, "[]"))


def _decode(raw: bytes, budget: Budget, *, producer_post: bool = False) -> Record:
    budget.check()
    require(len(raw) <= MEMBER_LIMIT, "BOUNDS_EXCEEDED")
    depth = position = count = 0
    while position < len(raw):
        match = _JSON_TOKEN.match(raw, position)
        require(match is not None, "MALFORMED_JSON")
        assert match is not None
        require(match.lastgroup != "oversize", "BOUNDS_EXCEEDED")
        position = match.end()
        token = match.group()
        if token[:1] in (b" ", b"\t", b"\r", b"\n"):
            continue
        count += 1
        require(count <= 600_000 and len(token) <= 8192, "BOUNDS_EXCEEDED")
        if count % 4096 == 0:
            budget.check()
        if token in _HEAVY:
            depth += 1
            require(depth <= 16, "BOUNDS_EXCEEDED")
        elif token in _LIGHT:
            depth -= 1
            require(depth >= 0, "MALFORMED_JSON")
        elif token[:1] in b"-0123456789":
            if b"." in token:
                require(
                    producer_post and not token.startswith(b"-") and len(token) <= 32,
                    "MALFORMED_JSON",
                )
            else:
                require(len(token.lstrip(b"-")) <= 24, "BOUNDS_EXCEEDED")
    require(depth == 0, "MALFORMED_JSON")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_float=Decimal)
    except (UnicodeError, ValueError, RecursionError):
        fail("MALFORMED_JSON")
    if producer_post:
        _decimal_paths(value)
    budget.check()
    require(type(value) is dict, "MALFORMED_JSON")
    return cast(Record, value)


def _sha_field(value: object, code: str = "PROVENANCE_MISMATCH") -> str:
    return text(value, c.HEX64, code)


def _recorded_time(value: object, code: str) -> None:
    stamp = text(
        value,
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
        code,
    )
    try:
        datetime.fromisoformat(stamp)
    except ValueError:
        fail(code)


def _inventory(packet: Packet, prefix: str, stems: tuple[str, ...]) -> None:
    expected = {prefix + stem + ".json" for stem in stems}
    require(
        {name for name in packet.pins if name.startswith(prefix)} == expected, "ARCHIVE_STRUCTURE"
    )


def _artifact_pins(packet: Packet, prefix: str, names: tuple[str, ...], pins: object) -> None:
    for name, raw in zip(names, array(pins, len(names)), strict=True):
        row = record(raw, "file byte_length sha256")
        pin = packet.pins[prefix + name + ".json"]
        require(row["file"] == name + ".json", "MEMBER_MISMATCH")
        require(
            integer(row["byte_length"], 0, MEMBER_LIMIT) == pin.size
            and _sha_field(row["sha256"]) == pin.sha256,
            "MEMBER_MISMATCH",
        )


def _provenance(
    obj: object,
    head: str,
    revision: str,
    count: int,
) -> tuple[Record, list[list[Any]]]:
    code = "PROVENANCE_MISMATCH"
    raw = record(obj, f"{head} code_claim files runtime", code)
    require(
        raw[head] == revision
        and raw["code_claim"] == "ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT",
        code,
    )
    runtime = record(raw["runtime"], "implementation python", code)
    require(runtime["implementation"] == "CPython", code)
    text(runtime["python"], r"3\.12\.[0-9]{1,3}(?: [ -~]{1,160})?", code)
    rows: list[list[Any]] = []
    for item in array(raw["files"], count, code):
        row = record(item, "path sha256 byte_length", code)
        name = text(row["path"], r"[A-Za-z0-9._/-]{1,200}", code)
        require(all(part not in ("", ".", "..") for part in name.split("/")), code)
        rows.append([name, _sha_field(row["sha256"]), integer(row["byte_length"], 0, MEMBER_LIMIT)])
    names = [row[0] for row in rows]
    require(names == sorted(set(names)), code)
    return runtime, rows


_F3_SPEC = "protocol protocol_ref dataset_digest provenance"
_F3_PROTOCOL = (
    "exclusion_policy feature folds h0 h1 horizon_sessions limitations method min_issuers "
    "min_test_cutoffs min_test_rows min_train_cutoffs min_train_rows non_if03 numeric_policy "
    "question schema seed temporal_policy"
)
_F3_ATTEMPT = (
    "attempt_id completed_stages elapsed_ns evidence_ref execution_status experiment_ref "
    "finished_at first_failure result_ref started_at"
)
_F3_FACT = (
    "amount available_at basis month native_state publication qualification_ref reason "
    "source_ref state unit version_ref"
)
_F3_PREDICTION = "sample_id issuer tick decision_time binding_id state value reason"
_F3_TARGET = "available_at dataset_digest end marks sample_id start value"


@dataclass(frozen=True)
class Producer:
    spec: Record
    attempt: Record
    runtime: Record
    pins: list[list[Any]]
    cutoffs: list[Any]
    bindings: dict[str, Record]
    handoff: dict[str, Record]
    fits: list[Record]
    receipt: Record


def _bound_protocol(spec: Record) -> None:
    code = "PROVENANCE_MISMATCH"
    protocol = record(spec["protocol"], _F3_PROTOCOL)
    temporal = record(
        protocol["temporal_policy"],
        "feature fit prediction purge score target training_label validation",
    )
    require(
        temporal
        == {
            "feature": "public_delivery < decision",
            "fit": c.FIT_WORDING,
            "prediction": "18:00_LAST_SESSION_OF_WEEK",
            "purge": "outcome_end < first_test_start_mark",
            "score": "sealed_prediction_then_mature_outcome",
            "target": "20_SUBSEQUENT_SESSION_CLOSES",
            "training_label": "available_at <= fit",
            "validation": "NOT_APPLICABLE_NO_TUNING",
        },
        code,
    )
    require(
        protocol["question"] == c.QUESTION
        and protocol["method"] == c.METHOD
        and integer(protocol["seed"], 17, 17, code) == 17
        and integer(protocol["horizon_sessions"], 20, 20, code) == 20
        and protocol["non_if03"] is True
        and _hash(protocol) == spec["protocol_ref"],
        code,
    )
    literals = {
        "schema": "F3_L1_RESEARCH_V0.1",
        "exclusion_policy": "TYPED_UNAVAILABLE_NO_IMPUTATION_NO_OLDER_PAIR_FALLBACK",
        "feature": "LATEST_AVAILABLE_MONTH_OVER_IMMEDIATE_PREDECESSOR_MINUS_ONE",
        "numeric_policy": "FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1",
        "h0": "beta = 0",
        "h1": "beta != 0",
    }
    require(all(protocol[key] == value for key, value in literals.items()), code)
    sizes = {
        "min_issuers": 3,
        "min_train_cutoffs": 40,
        "min_train_rows": 180,
        "min_test_cutoffs": 20,
        "min_test_rows": 80,
    }
    for key, size in sizes.items():
        integer(protocol[key], size, size, code)
    for label in array(protocol["limitations"], 8, code):
        text(label, r"[A-Z0-9_]{1,96}", code)
    _sha_field(spec["dataset_digest"])
    expected_positions = ((48, 72), (72, 96))
    for ix, item in enumerate(array(protocol["folds"], 2)):
        fold = record(item, "name history_end test_start test_end")
        # Historical `history_end` and `test_start` coincide.
        require(
            fold["name"] == ("F1", "F2")[ix]
            and fold["history_end"] == fold["test_start"] == expected_positions[ix][0]
            and fold["test_end"] == expected_positions[ix][1],
            code,
        )


def _producer_attempt(packet: Packet, release: Release, spec: Record) -> Record:
    code = "RECEIPT_MISMATCH"
    evidence = packet.payload(
        F3,
        "evidence",
        "artifacts dataset_digest evidence_scope experiment_ref limitations "
        "protocol_ref result_ref test_execution_attestation",
    )
    _artifact_pins(packet, F3, F3_FILES, evidence["artifacts"])
    result = packet.payload(
        F3,
        "result",
        "aggregate dataset_digest dependence experiment_ref folds_ref "
        "interpretation limitations predictions_ref protocol_ref states_ref targets_ref",
    )
    attempt = packet.payload(F3, "attempt", _F3_ATTEMPT)
    require(
        packet.pins[F3 + "evidence.json"].sha256 == release.f3_sha256
        and evidence["evidence_scope"] == "EXECUTED_AUTHORED_SYNTHETIC_RESEARCH_ONLY"
        and evidence["test_execution_attestation"] == "NOT_ATTESTED_BY_EXPERIMENT_RUNTIME",
        code,
    )
    for key in ("protocol_ref", "dataset_digest"):
        require(evidence[key] == result[key] == spec[key], code)
    for key in ("folds", "predictions", "states", "targets"):
        require(result[key + "_ref"] == packet.pins[F3 + key + ".json"].sha256, code)
    for field, kind in (
        ("experiment_ref", "spec"),
        ("result_ref", "result"),
        ("evidence_ref", "evidence"),
    ):
        pin = packet.pins[F3 + kind + ".json"].sha256
        require(
            attempt[field] == pin
            and evidence.get(field, pin) == pin
            and result.get(field, pin) == pin,
            code,
        )
    c.uuid4_text(attempt["attempt_id"], code)
    _recorded_time(attempt["started_at"], code)
    _recorded_time(attempt["finished_at"], code)
    elapsed = integer(attempt["elapsed_ns"], 0, 10**24 - 1, code)
    require(attempt["execution_status"] == "SUCCEEDED" and attempt["first_failure"] is None, code)
    previous = 0
    for stage, raw in zip(
        F3_STAGES, array(attempt["completed_stages"], len(F3_STAGES)), strict=True
    ):
        observed = record(raw, "elapsed_ns finished_at stage", code)
        require(observed["stage"] == stage, code)
        previous = integer(observed["elapsed_ns"], previous, elapsed, code)
        _recorded_time(observed["finished_at"], code)
    return attempt


def _producer_bindings(packet: Packet, spec: Record) -> tuple[dict[str, Record], list[Any]]:
    code = "PROVENANCE_MISMATCH"
    value = packet.payload(F3, "bindings", "observations qualification_receipts source_summary")
    require(type(value["qualification_receipts"]) is dict, code)
    receipts = value["qualification_receipts"]
    require(len(receipts) == 1575, code)
    for ref, body in receipts.items():
        require(_sha_field(ref) == _hash(body), code)
    summary = record(
        value["source_summary"],
        "admission_eligible calendar_coverage calendar_id cutoffs "
        "dataset_digest invocation_count_scope issuer_roster native_invocations non_if03 "
        "price_marks revenue_declarations scope source_authentication",
    )
    require(
        summary["dataset_digest"] == spec["dataset_digest"]
        and summary["issuer_roster"] == list(c.ISSUERS)
        and summary["admission_eligible"] is False
        and summary["non_if03"] is True
        and summary["scope"] == "AUTHORED_SYNTHETIC_PUBLIC_ONLY"
        and summary["source_authentication"] == "NOT_ESTABLISHED",
        code,
    )
    by_ref: dict[str, Record] = {}
    by_tick: dict[int, str] = {}
    seen: set[tuple[int, str]] = set()
    for raw in array(value["observations"], 480):
        row = record(
            raw,
            "binding_id calendar_id current cutoff dataset_digest issuer previous sample_id tick",
        )
        ref = _sha_field(row["binding_id"])
        expected = _hash({k: v for k, v in row.items() if k != "binding_id"})
        tick = integer(row["tick"], 0, 95, code)
        issuer = choice(row["issuer"], c.ISSUERS, code)
        c.timestamp(row["cutoff"], code=code)
        require(
            ref == expected
            and ref not in by_ref
            and (tick, issuer) not in seen
            and row["sample_id"] == f"{issuer}:t{tick:02d}"
            and row["cutoff"] == by_tick.setdefault(tick, row["cutoff"])
            and row["dataset_digest"] == spec["dataset_digest"]
            and row["calendar_id"] == summary["calendar_id"],
            code,
        )
        for field in ("current", "previous"):
            fact = record(row[field], _F3_FACT)
            choice(fact["state"], ("KNOWN", *c.MISSING))
            if fact["state"] == "KNOWN":
                require(_sha_field(fact["qualification_ref"]) in receipts, code)
            else:
                require(
                    fact["qualification_ref"] is None
                    or _sha_field(fact["qualification_ref"]) in receipts,
                    code,
                )
        by_ref[ref] = row
        seen.add((tick, issuer))
    cutoffs = [by_tick[tick] for tick in range(96)]
    require(summary["cutoffs"] == cutoffs == sorted(set(cutoffs)), code)
    return by_ref, cutoffs


def _folds_and_predictions(
    packet: Packet,
    spec: Record,
    bindings: dict[str, Record],
    cutoffs: list[Any],
) -> tuple[dict[str, Record], list[Record], dict[str, Record]]:
    code = "PROVENANCE_MISMATCH"
    folds = packet.payload(F3, "folds", "folds training")
    states = packet.payload(F3, "states", "states")["states"]
    batches = packet.payload(F3, "predictions", "batches")["batches"]
    predictions: dict[str, Record] = {}
    fit_by_fold: dict[str, Record] = {}
    fits = []
    for ix, chunks in enumerate(
        zip(
            array(folds["folds"], 2),
            array(folds["training"], 2),
            array(states, 2),
            array(batches, 2),
            strict=True,
        )
    ):
        name = ("F1", "F2")[ix]
        fit_time = c.FITS[ix]
        fold, train, state, batch = chunks
        f = record(
            fold,
            "distinct_issuer_month_releases distinct_source_versions excluded "
            "excluded_training exclusion_counts fit_cutoff fold history_candidates "
            "latest_training_label_availability metrics prediction_id scored_cutoffs "
            "scored_ids scoring_cutoff state_id test_ticks training_count training_cutoffs "
            "training_ids training_issuers",
        )
        t = record(
            train,
            "dataset_digest excluded fit_cutoff fold issuers members protocol_ref "
            "schedule test_start_mark training_ref",
        )
        s = record(
            state,
            "alpha beta dataset_digest fit_cutoff fold gbar protocol_ref rbar "
            "state_id training_ids training_ref",
        )
        b = record(
            batch,
            "dataset_digest fold outcomes_in_payload prediction_id protocol_ref rows state_id",
        )
        for row in (t, s, b):
            require(
                row["dataset_digest"] == spec["dataset_digest"]
                and row["protocol_ref"] == spec["protocol_ref"],
                code,
            )
        for row in (f, t, s, b):
            require(row["fold"] == name, code)
        for row in (f, t, s):
            require(row["fit_cutoff"] == fit_time, code)
        count = (206, 326)[ix]
        ids = []
        for raw in array(t["members"], count):
            entry = record(raw, "binding_id target")
            ref = _sha_field(entry["binding_id"])
            require(ref in bindings, code)
            target = record(entry["target"], _F3_TARGET)
            require(
                target["sample_id"] == bindings[ref]["sample_id"]
                and target["dataset_digest"] == spec["dataset_digest"],
                code,
            )
            ids.append(target["sample_id"])
        require(
            len(set(ids)) == count
            and f["training_ids"] == s["training_ids"] == ids
            and f["training_count"] == count
            and t["schedule"] == cutoffs
            and t["issuers"] == list(c.ISSUERS),
            code,
        )
        for obj, key in ((t, "training_ref"), (s, "state_id"), (b, "prediction_id")):
            require(_sha_field(obj[key]) == _hash({k: v for k, v in obj.items() if k != key}), code)
        start = c.FIRST_TICK + ix * 24
        require(
            t["training_ref"] == s["training_ref"]
            and s["state_id"] == b["state_id"] == f["state_id"]
            and b["prediction_id"] == f["prediction_id"]
            and b["outcomes_in_payload"] is False
            and f["test_ticks"] == [start, start + 23],
            code,
        )
        for metric in ("alpha", "beta", "gbar", "rbar"):
            fraction(s[metric])
        scored = []
        for raw in array(b["rows"], 120):
            row = record(raw, _F3_PREDICTION)
            ref = _sha_field(row["binding_id"])
            require(ref in bindings, code)
            bind = bindings[ref]
            require(
                row["issuer"] == bind["issuer"]
                and row["sample_id"] == bind["sample_id"]
                and row["decision_time"] == bind["cutoff"]
                and row["tick"] == bind["tick"]
                and start <= integer(row["tick"], 0, 95) < start + 24
                and row["sample_id"] not in predictions,
                code,
            )
            require(row["state"] == "PREDICTED" and row["reason"] == "NONE", code)
            fraction(row["value"])
            predictions[row["sample_id"]] = row
            scored.append(row["sample_id"])
        require(f["scored_ids"] == scored, code)
        fit_by_fold[name] = s
        fits.append({"fold": name, "fit_at": fit_time})
    return predictions, fits, fit_by_fold


def _producer_handoff(
    packet: Packet,
    spec: Record,
    predictions: dict[str, Record],
    states: dict[str, Record],
) -> dict[str, Record]:
    code = "PROVENANCE_MISMATCH"
    target_ids = set()
    targets = packet.payload(F3, "targets", "scored_targets")
    for raw in array(targets["scored_targets"], 240):
        target = record(raw, _F3_TARGET)
        sample = text(target["sample_id"], r"SYN-L1-[1-5]:t[0-9]{2}", code)
        require(
            sample in predictions
            and sample not in target_ids
            and target["dataset_digest"] == spec["dataset_digest"],
            code,
        )
        target_ids.add(sample)
    actual: dict[str, Record] = {}
    rows = packet.payload(F3, "handoff", "rows")
    for raw in array(rows["rows"], 240):
        row = record(
            raw,
            _F3_PREDICTION + " dataset_digest eligibility fit_cutoff fold horizon "
            "limitations meaning method protocol_ref research_result_ref state_id",
        )
        sample = text(row["sample_id"], r"SYN-L1-[1-5]:t[0-9]{2}", code)
        fold = choice(row["fold"], ("F1", "F2"), code)
        require(sample in predictions and sample not in actual, code)
        predicted = predictions[sample]
        require(all(row[key] == predicted[key] for key in _F3_PREDICTION.split()), code)
        require(
            row["state_id"] == states[fold]["state_id"]
            and row["fit_cutoff"] == states[fold]["fit_cutoff"]
            and row["dataset_digest"] == spec["dataset_digest"]
            and row["method"] == c.METHOD
            and row["horizon"] == "20_SUBSEQUENT_SESSIONS"
            and row["meaning"] == "UNADJUSTED_SIMPLE_RETURN_FORECAST_NOT_ACTION"
            and row["eligibility"] == "AUTHORED_SYNTHETIC_LOCAL_RELEASE_NO_APP_ADMISSION"
            and row["protocol_ref"] == spec["protocol_ref"]
            and row["research_result_ref"] == packet.pins[F3 + "result.json"].sha256,
            code,
        )
        actual[sample] = row
    return actual


def _root_view(value: object) -> Record:
    root = record(value, ROOT_RECORD, "RECEIPT_MISMATCH")
    text(root["root"], r"/[ -~]{1,1023}", "RECEIPT_MISMATCH")
    for item in array(root["root_identity"], 3, "RECEIPT_MISMATCH"):
        integer(item, 0, 10**24 - 1, "RECEIPT_MISMATCH")
    require(type(root["files"]) is dict, "RECEIPT_MISMATCH")
    return root


def _root_file_refs(
    root: Record, pins: dict[str, Pin], prefix: str, names: tuple[str, ...]
) -> None:
    code = "RECEIPT_MISMATCH"
    files = record(root["files"], " ".join(name + ".json" for name in names), code)
    for leaf, raw in files.items():
        row = record(raw, "bytes sha256", code)
        pin = pins[prefix + leaf]
        require(
            integer(row["bytes"], 0, MEMBER_LIMIT, code) == pin.size
            and _sha_field(row["sha256"], code) == pin.sha256,
            code,
        )


def _receipt(
    packet: Packet,
    release: Release,
    spec: Record,
    attempt: Record,
    runtime: Record,
    pins: list[list[Any]],
) -> Record:
    code = "RECEIPT_MISMATCH"
    require(packet.pins[PRODUCER].sha256 == release.producer_sha256, code)
    receipt = record(
        packet.json(PRODUCER),
        "artifact_root evidence_sha256 implementation invocation_logs kind launcher_sha256 "
        "original_attempt_id original_attempt_sha256 post_sha256 pre_sha256 producer_head "
        "producer_pid python receipt_id root source_pins",
        code,
    )
    require(
        receipt["receipt_id"] == release.receipt_id
        and receipt["producer_head"] == release.original_revision
        and receipt["kind"] == "task-local cooperative observation"
        and receipt["evidence_sha256"] == release.f3_sha256
        and receipt["original_attempt_id"] == attempt["attempt_id"]
        and receipt["original_attempt_sha256"] == packet.pins[F3 + "attempt.json"].sha256
        and receipt["source_pins"] == pins
        and {"python": receipt["python"], "implementation": receipt["implementation"]} == runtime,
        code,
    )
    root = _root_view(receipt["artifact_root"])
    _root_file_refs(root, packet.pins, F3, (*F3_FILES, "evidence", "attempt"))
    require(receipt["root"] == root["root"], code)
    pre = record(
        packet.json("witness/producer-pre.json"),
        "absent argv cwd launcher_sha256 observed_utc out root_identity runner_sha256 source",
        code,
    )
    post = record(
        packet.json("witness/producer-post.json"),
        "artifact_root attempt existing_f3_verify_directory launch observed_utc source",
        code,
    )
    launch = record(post["launch"], "evidence_sha256 invocation logs process", code)
    process = record(
        launch["process"], "affinity boot_ticks_at_start executable observed_utc pid", code
    )
    require(
        pre["absent"] is True
        and pre["out"] == receipt["root"]
        and post["artifact_root"] == root
        and post["attempt"] == attempt
        and post["existing_f3_verify_directory"] == "PASS"
        and launch["evidence_sha256"] == release.f3_sha256
        and integer(process["pid"], 1, 2**31 - 1, code)
        == integer(receipt["producer_pid"], 1, 2**31 - 1, code),
        code,
    )
    for key, path in (
        ("pre_sha256", "witness/producer-pre.json"),
        ("post_sha256", "witness/producer-post.json"),
        ("launcher_sha256", "witness/trusted_launcher.py"),
    ):
        require(receipt[key] == packet.pins[path].sha256, code)
    require(pre["launcher_sha256"] == receipt["launcher_sha256"], code)
    log_pins = record(receipt["invocation_logs"], " ".join(LOGS), code)
    for leaf in LOGS:
        require(log_pins[leaf] == packet.pins[leaf].sha256, code)
    for witness in (pre, post):
        source = record(
            witness["source"],
            "clean_status f3_files f5_head git_root producer_head "
            "producer_provenance reviewed_f5_files runtime",
            code,
        )
        require(
            source["clean_status"] is True
            and source["f3_files"] == pins
            and source["producer_head"] == source["f5_head"] == release.original_revision
            and source["producer_provenance"] == spec["provenance"],
            code,
        )
    return receipt


def _f3(packet: Packet, release: Release) -> Producer:
    _inventory(packet, F3, (*F3_FILES, "evidence", "attempt"))
    spec = packet.payload(F3, "spec", _F3_SPEC)
    _bound_protocol(spec)
    runtime, pins = _provenance(spec["provenance"], "base_head", release.original_revision, 46)
    attempt = _producer_attempt(packet, release, spec)
    receipt = _receipt(packet, release, spec, attempt, runtime, pins)
    bindings, cutoffs = _producer_bindings(packet, spec)
    packet.budget.check()
    predictions, fits, states = _folds_and_predictions(packet, spec, bindings, cutoffs)
    handoff = _producer_handoff(packet, spec, predictions, states)
    return Producer(spec, attempt, runtime, pins, cutoffs, bindings, handoff, fits, receipt)


def _attempt_status(attempt: Record) -> str:
    code = "RECEIPT_MISMATCH"
    state = choice(
        attempt["execution_status"],
        ("SUCCEEDED", "EVALUATED_REPLAY_PENDING", "BLOCKED_INPUT", "FAILED"),
        code,
    )
    comparison = choice(
        attempt["comparison_status"],
        (c.COMPLETE, "DEGRADED_DIAGNOSTIC_ONLY", "INCOMPLETE_OR_BLOCKED"),
        code,
    )
    replay = choice(attempt["replay_status"], ("VERIFIED", "NOT_RUN"), code)
    if state == "SUCCEEDED":
        require(
            replay == "VERIFIED"
            and attempt["first_failure"] is None
            and comparison in (c.COMPLETE, "DEGRADED_DIAGNOSTIC_ONLY"),
            code,
        )
    else:
        require(replay == "NOT_RUN" and comparison == "INCOMPLETE_OR_BLOCKED", code)
        require(
            all(
                attempt[key] is None
                for key in ("peer_evidence_sha256", "peer_attempt_id", "peer_process_id")
            ),
            code,
        )
    return state


def _check_pair(
    attempts: tuple[Record, Record],
    producer_root: str,
    evidence: str,
) -> str:
    code = "RECEIPT_MISMATCH"
    for attempt in attempts:
        record(attempt, ATTEMPT_FIELDS, code)
        c.uuid4_text(attempt["attempt_id"], code)
        integer(attempt["process_id"], 1, 2**31 - 1, code)
        _recorded_time(attempt["started_at"], code)
        _recorded_time(attempt["finished_at"], code)
        text(attempt["elapsed_seconds"], r"[0-9]{1,24}(?:\.[0-9]{1,24})?", code)
        require(attempt["producer_root"] == producer_root, code)
    left, right = attempts
    require(
        left["attempt_id"] != right["attempt_id"] and left["process_id"] != right["process_id"],
        code,
    )
    states = tuple(map(_attempt_status, attempts))
    if "FAILED" in states or "BLOCKED_INPUT" in states:
        fail("PAIR_FAILED")
    if states != ("SUCCEEDED", "SUCCEEDED"):
        fail("PAIR_INCOMPLETE")
    for own, peer in ((left, right), (right, left)):
        require(
            own["evidence_sha256"] == evidence
            and own["peer_evidence_sha256"] == evidence
            and c.uuid4_text(own["peer_attempt_id"], code) == peer["attempt_id"]
            and integer(own["peer_process_id"], 1, 2**31 - 1, code) == peer["process_id"]
            and own["origin_handoff_status"] == "ORIGIN_ARTIFACT_AND_SEMANTICS_VERIFIED"
            and own["completed_stages"] == list(F5_STAGES),
            code,
        )
    require(left["comparison_status"] == right["comparison_status"], code)
    return cast(str, left["comparison_status"])


def _pair_record(
    packet: Packet, release: Release, attempts: tuple[Record, Record], kind: str
) -> None:
    code = "RECEIPT_MISMATCH"
    require(packet.pins[PAIR_POST].sha256 == release.pair_post_sha256, code)
    paired = record(
        packet.json(PAIR_POST),
        "completed_attempts effective_class finished_utc idempotence "
        "pending_attempts pid post pre single_root",
        code,
    )
    require(
        paired["completed_attempts"] == list(attempts)
        and paired["effective_class"] == kind
        and paired["idempotence"] == "PASS"
        and paired["single_root"] == "NOT_COMPUTABLE",
        code,
    )
    integer(paired["pid"], 1, 2**31 - 1, code)
    _recorded_time(paired["finished_utc"], code)
    roots: set[str] = set()
    tokens: set[tuple[int, ...]] = set()
    for ix, prefix in enumerate(PEERS):
        pre = _root_view(array(paired["pre"], 2, code)[ix])
        post = _root_view(array(paired["post"], 2, code)[ix])
        root = cast(str, post["root"])
        token = tuple(post["root_identity"])
        require(
            pre["root"] == root
            and pre["root_identity"] == post["root_identity"]
            and root not in roots
            and token not in tokens
            and root.rsplit("/", 1)[-1] == prefix[:-1],
            code,
        )
        roots.add(root)
        tokens.add(token)
        _root_file_refs(post, packet.pins, prefix, (*F5_FILES, "attempt"))
        old = record(array(paired["pending_attempts"], 2, code)[ix], ATTEMPT_FIELDS, code)
        require(_attempt_status(old) == "EVALUATED_REPLAY_PENDING", code)
        updates = {
            "execution_status",
            "comparison_status",
            "replay_status",
            "peer_evidence_sha256",
            "peer_attempt_id",
            "peer_process_id",
        }
        require(all(old[k] == attempts[ix][k] for k in old.keys() - updates), code)
        pre_file_map = record(
            pre["files"], " ".join(n + ".json" for n in (*F5_FILES, "attempt")), code
        )
        for stem in F5_FILES:
            require(pre_file_map[stem + ".json"] == post["files"][stem + ".json"], code)
        previous = c.canonical(
            {"schema": "F5_WEEKLY_SYNTHETIC_ATTEMPT_V1", "non_if03": True, "payload": old}
        )
        require(
            pre_file_map["attempt.json"] == {"bytes": len(previous), "sha256": _sha(previous)}, code
        )


_METRICS = "books candidate_class common_failure coverage limitations"
_DECISIONS = "common_failure coverage observation_coverage observations slot_set_digest slots"
_SPEC = "calendar cutoffs manifest_sha256 non_if03 policies producer_origin protocol provenance source_sha256"
_F5_PIN_NAMES = {
    *(
        "src/pit_research_lab/mvp/f5/" + n + ".py"
        for n in (
            "__init__",
            "accounting",
            "cli",
            "contracts",
            "experiment",
            "inputs",
            "policies",
            "prices",
            "replay",
        )
    ),
    *(
        "tests/unit/mvp_f5/" + n + ".py"
        for n in (
            "__init__",
            "test_accounting",
            "test_inputs",
            "test_policies",
            "test_prices",
            "test_replay",
        )
    ),
}


def _f5_spec(packet: Packet, release: Release, producer: Producer) -> tuple[Record, dict[str, str]]:
    code = "PROVENANCE_MISMATCH"
    spec = packet.payload(PEERS[0], "spec", _SPEC)
    origin = record(
        spec["producer_origin"],
        "evidence_sha256 implementation producer_head python receipt_id source_pins",
        code,
    )
    require(all(origin[k] == producer.receipt[k] for k in origin), code)
    runtime, pins = _provenance(spec["provenance"], "f5_head", release.original_revision, 61)
    lookup = {name: (digest, length) for name, digest, length in pins}
    require(
        runtime == producer.runtime
        and {name for name, _, _ in producer.pins} | _F5_PIN_NAMES == lookup.keys()
        and all(lookup[name] == (digest, size) for name, digest, size in producer.pins),
        code,
    )
    sources = {name: digest for name, digest, _ in producer.pins}
    require(
        spec["source_sha256"] == sources["tests/fixtures/mvp_f3_l1/revenue_growth_panel_v0_1.json"]
        and spec["manifest_sha256"] == sources["tests/fixtures/mvp_f3_l1/manifest_v0_1.json"]
        and spec["cutoffs"] == producer.cutoffs
        and spec["non_if03"] is True
        and spec["policies"] == list(ORIGINAL_POLICIES),
        code,
    )
    policy = record(spec["protocol"], "fee initial_cash seed slippage terminal version")
    require(
        integer(policy["seed"], 17, 17, code) == 17
        and policy["version"] == "F5_WEEKLY_SYNTHETIC_V1"
        and fraction(policy["fee"]) == (3, 5000)
        and fraction(policy["slippage"]) == (1, 2500)
        and fraction(policy["initial_cash"]) == (1000, 1),
        code,
    )
    terminal = c.timestamp(policy["terminal"], code=code)
    require(c.timestamp(producer.cutoffs[-1]) < terminal, code)
    days = set()
    sessions: dict[str, str] = {}
    for raw in array(spec["calendar"], 790):
        day = record(raw, "close date status")
        date = text(day["date"], r"[0-9]{4}-[0-9]{2}-[0-9]{2}", code)
        require(date not in days, code)
        days.add(date)
        status = choice(day["status"], ("SESSION", "CLOSED"), code)
        if status == "SESSION":
            require(c.timestamp(day["close"]).date().isoformat() == date, code)
            sessions[date] = day["close"]
        else:
            require(day["close"] is None, code)
    require(len(sessions) > 241 and sorted(sessions) == list(sessions), code)
    return spec, sessions


def _qualified_facts(issuer: Record, binding: Record, cutoff: str) -> None:
    for name in ("current", "previous"):
        original = record(binding[name], _F3_FACT)
        fact = record(
            issuer[name],
            "amount available_at basis month native_state publication "
            "qualification_digest reason source_id state unit version_id",
        )
        translation = {
            "qualification_digest": "qualification_ref",
            "source_id": "source_ref",
            "version_id": "version_ref",
        }
        require(
            all(value == original[translation.get(key, key)] for key, value in fact.items()),
            "PROVENANCE_MISMATCH",
        )
        require(
            fact["state"] == "KNOWN"
            and fact["reason"] == "NONE"
            and fact["native_state"] == "SELECTED"
            and fact["unit"] == "NTD_thousands"
            and fact["basis"] == "consolidated-v1"
            and c.timestamp(fact["publication"])
            <= c.timestamp(fact["available_at"])
            < c.timestamp(cutoff),
            "PROVENANCE_MISMATCH",
        )
        integer(fact["amount"], 1, 2**63 - 1)


def _observation(
    value: object, tick: int, spec: Record, producer: Producer, calendar_digest: str
) -> Record:
    code = "PROVENANCE_MISMATCH"
    obj = record(
        value, "calendar_digest cutoff dataset_digest information_digest issuers schema tick"
    )
    clock = producer.cutoffs[tick]
    require(
        integer(obj["tick"], 48, 95, code) == tick
        and obj["cutoff"] == clock
        and obj["calendar_digest"] == calendar_digest
        and obj["dataset_digest"] == producer.spec["dataset_digest"]
        and obj["schema"] == "F5_DECISION_OBSERVATION_V1"
        and _sha_field(obj["information_digest"])
        == _hash({k: v for k, v in obj.items() if k != "information_digest"}),
        code,
    )
    require(spec["cutoffs"][tick] == clock, code)
    for name, raw in zip(c.ISSUERS, array(obj["issuers"], 5), strict=True):
        item = record(
            raw,
            "current eligibility_reason forecast growth growth_reason growth_state "
            "issuer observation_binding previous research_eligible sample_id",
        )
        key = f"{name}:t{tick:02d}"
        issued = producer.handoff[key]
        bind = producer.bindings[issued["binding_id"]]
        require(
            item["sample_id"] == key
            and item["issuer"] == name
            and item["observation_binding"] == issued["binding_id"]
            and item["research_eligible"] is True
            and item["growth_state"] == "KNOWN"
            and item["growth_reason"] == item["eligibility_reason"] == "NONE",
            code,
        )
        _qualified_facts(item, bind, clock)
        fraction(item["growth"])
        forecast = record(
            item["forecast"],
            "calendar_digest dataset_digest decision_cutoff f3_protocol_digest "
            "fit_cutoff fold horizon_sessions issuer method model_state_digest observation_binding "
            "reason sample_id state tick value",
        )
        fields = {
            "decision_cutoff": "decision_time",
            "f3_protocol_digest": "protocol_ref",
            "model_state_digest": "state_id",
            "observation_binding": "binding_id",
        }
        require(
            forecast["calendar_digest"] == calendar_digest
            and integer(forecast["horizon_sessions"], 20, 20, code) == 20
            and all(
                forecast[k] == issued[fields.get(k, k)]
                for k in forecast.keys() - {"calendar_digest", "horizon_sessions"}
            ),
            code,
        )
    return obj


def _slot(value: object, policy: str, tick: int, obs: Record) -> Record:
    code = "PROVENANCE_MISMATCH"
    slot = record(
        value,
        "attempted cutoff engine_disposition failure_cause information_digest outcome "
        "policy_action policy_decision_digest policy_id schema slot_digest tick",
    )
    require(
        slot["policy_id"] == policy
        and integer(slot["tick"], 48, 95, code) == tick
        and slot["cutoff"] == obs["cutoff"]
        and slot["information_digest"] == obs["information_digest"]
        and slot["schema"] == "F5_DECISION_SLOT_V1",
        code,
    )
    require(
        slot["outcome"] == "VALID"
        and slot["attempted"] is True
        and slot["engine_disposition"] is None
        and slot["failure_cause"] is None,
        "PAIR_DEGRADED",
    )
    action = record(
        slot["policy_action"],
        "cash_weight cutoff disposition information_digest "
        "issuer_reasons policy_id policy_version reason schema tick weights",
    )
    require(
        all(action[k] == slot[k] for k in ("policy_id", "tick", "cutoff", "information_digest"))
        and action["policy_version"] == "F5_WEEKLY_SYNTHETIC_V1"
        and action["schema"] == "F5_TARGET_ACTION_V1"
        and action["reason"] == "NONE",
        code,
    )
    choice(action["disposition"], ("ALLOCATE", "CASH", "ABSTAIN"))
    for index, alias in enumerate(c.ISSUERS):
        weight = array(array(action["weights"], 5)[index], 2)
        reason = array(array(action["issuer_reasons"], 5)[index], 2)
        require(weight[0] == reason[0] == alias, code)
        n, d = fraction(weight[1])
        require(0 <= 2 * n <= d, code)
        choice(reason[1], c.ISSUER_REASONS)
    n, d = fraction(action["cash_weight"])
    require(0 <= n <= d, code)
    require(
        _sha_field(slot["policy_decision_digest"]) == _hash(action)
        and _sha_field(slot["slot_digest"])
        == _hash({k: v for k, v in slot.items() if k != "slot_digest"}),
        code,
    )
    return slot


def _census(value: object) -> Record:
    expected = {
        "attempted": 144,
        "blocked_not_attempted": 0,
        "committed_engine_fallback": 0,
        "expected_common_mark_cells": 1205,
        "expected_historical_bindings": 480,
        "expected_oos_cells": 240,
        "expected_opportunities_per_book": 48,
        "expected_slots": 144,
        "expected_ticks": 48,
        "expected_weekly_returns_per_book": 48,
        "failed_policy": 0,
        "sealed_slots": 144,
        "valid": 144,
    }
    row = record(value, " ".join(expected.keys()) + " per_policy")
    for field, count in expected.items():
        integer(row[field], count, count, "PAIR_INCOMPLETE")
    per_policy = record(row["per_policy"], " ".join(ORIGINAL_POLICIES))
    for policy in ORIGINAL_POLICIES:
        integer(record(per_policy[policy], "VALID")["VALID"], 48, 48, "PAIR_INCOMPLETE")
    return row


def _decision_records(
    packet: Packet,
    spec: Record,
    producer: Producer,
) -> tuple[dict[int, Record], dict[tuple[int, str], Record], Record, Record]:
    code = "PROVENANCE_MISMATCH"
    data = packet.payload(PEERS[0], "decisions", _DECISIONS)
    require(data["common_failure"] is None, "PAIR_FAILED")
    census = _census(data["coverage"])
    info_census = record(
        data["observation_coverage"],
        "actual_ticks forecast_states q_by_tick "
        "qualified_issuer_ticks revenue_states unavailable_causes "
        "verified_historical_bindings verified_oos_cells",
    )
    calendar_digest = _hash(spec["calendar"])
    ticks = range(c.FIRST_TICK, c.AFTER_LAST_TICK)
    observations = {
        tick: _observation(value, tick, spec, producer, calendar_digest)
        for tick, value in zip(ticks, array(data["observations"], 48), strict=True)
    }
    keys = [(tick, policy) for tick in ticks for policy in ORIGINAL_POLICIES]
    slots = {
        (tick, policy): _slot(raw, policy, tick, observations[tick])
        for (tick, policy), raw in zip(keys, array(data["slots"], 144), strict=True)
    }
    require(
        _sha_field(data["slot_set_digest"])
        == _hash({"slots": data["slots"], "common_failure": data["common_failure"]}),
        code,
    )
    require(
        info_census
        == {
            "actual_ticks": len(observations),
            "forecast_states": {"PREDICTED": len(producer.handoff)},
            "q_by_tick": [[tick, len(observations[tick]["issuers"])] for tick in ticks],
            "qualified_issuer_ticks": len(producer.handoff),
            "revenue_states": {"KNOWN": len(producer.handoff) * 2},
            "unavailable_causes": {},
            "verified_historical_bindings": len(producer.bindings),
            "verified_oos_cells": len(producer.handoff),
        },
        code,
    )
    return observations, slots, census, info_census


def _ledger_data(
    packet: Packet,
    sessions: dict[str, str],
    spec: Record,
    slots: dict[tuple[int, str], Record],
) -> tuple[dict[tuple[int, str], Record], Record]:
    code = "PROVENANCE_MISMATCH"
    data = packet.payload(PEERS[0], "ledger", "events marks valuations")
    days = [
        day
        for day in sessions
        if spec["cutoffs"][48][:10] <= day <= spec["protocol"]["terminal"][:10]
    ]
    require(len(days) == 241, code)
    expected_fills = {
        tick: next((d for d in days if d > spec["cutoffs"][tick][:10]), "")
        for tick in range(c.FIRST_TICK, c.AFTER_LAST_TICK)
    }
    marked: dict[tuple[str, str], str] = {}
    for raw in array(data["marks"], 1205):
        mark = record(
            raw,
            "admission_eligible available_at basis close_time diagnostic_only "
            "disposition evaluation_asof invocation issuer native_reason native_s1_reason "
            "native_s1_state native_s2_state non_if03 original_publication_state session "
            "source_authentication source_digest source_id trust unit value_ticks version_id "
            "witness_kind witness_time",
        )
        day = text(mark["session"], r"[0-9]{4}-[0-9]{2}-[0-9]{2}", code)
        alias = choice(mark["issuer"], c.ISSUERS, code)
        require(
            day in days and (day, alias) not in marked and mark["close_time"] == sessions[day], code
        )
        close = c.timestamp(mark["close_time"])
        available = c.timestamp(mark["available_at"])
        require(
            available == close + timedelta(seconds=1)
            and mark["witness_time"] == mark["available_at"] == mark["evaluation_asof"]
            and mark["admission_eligible"] is False
            and mark["diagnostic_only"] is True
            and mark["non_if03"] is True
            and mark["invocation"] == "RUN"
            and mark["native_s1_state"] == "BOUND"
            and mark["native_s2_state"] == "SUPPORTED"
            and mark["disposition"] == "INTEGRATED_PROVISIONAL"
            and mark["original_publication_state"] == "NOT_PROVIDED_IN_PRICE_ROW"
            and mark["witness_kind"] == "PINNED_AUTHORED_DELIVERY"
            and mark["source_authentication"] == "NOT_ESTABLISHED"
            and mark["trust"] == "NOT_TRUSTED_PIT_EVIDENCE",
            code,
        )
        marked[day, alias] = mark["available_at"]
    mirror_keys = set()
    picked = {}
    for raw in array(data["events"], 288):
        event = record(
            raw, "action_digest event fill mirror policy posted_at reference_time tick traded_legs"
        )
        tick = integer(event["tick"], 48, 95, code)
        policy = choice(event["policy"], ORIGINAL_POLICIES, code)
        kind = choice(event["event"], ("TRADE", "NO_TRADE"), code)
        require(type(event["mirror"]) is bool, code)
        key = tick, policy, event["mirror"]
        day = expected_fills[tick]
        legs = integer(event["traded_legs"], 0, 5, code)
        require(
            key not in mirror_keys
            and day in sessions
            and event["reference_time"] == sessions[day]
            and event["posted_at"] == marked[day, c.ISSUERS[0]]
            and event["action_digest"] == slots[tick, policy]["policy_decision_digest"]
            and (kind == "TRADE") == (legs > 0)
            and type(event["fill"]) is dict,
            code,
        )
        if not event["mirror"]:
            picked[tick, policy] = {
                "event": kind,
                "reference_at": event["reference_time"],
                "posted_at": event["posted_at"],
            }
        mirror_keys.add(key)
    valuation_keys = set()
    for raw in array(data["valuations"], 1446):
        row = record(
            raw,
            "available_at cash mirror policy post_event_equity pre_fill_equity "
            "reference_time session shares",
        )
        day = text(row["session"], r"[0-9]{4}-[0-9]{2}-[0-9]{2}", code)
        policy = choice(row["policy"], ORIGINAL_POLICIES)
        require(type(row["mirror"]) is bool, code)
        valuation_key = day, policy, row["mirror"]
        require(
            day in days
            and row["reference_time"] == sessions[day]
            and row["available_at"] == marked[day, c.ISSUERS[0]]
            and valuation_key not in valuation_keys,
            code,
        )
        valuation_keys.add(valuation_key)
    return picked, {
        "qualified_marks": len(marked),
        "mark_sessions": len(days),
        "rebalance_records": len(mirror_keys),
        "valuation_records": len(valuation_keys),
    }


def _effective(packet: Packet, release: Release, kind: str) -> Record:
    code = "PROVENANCE_MISMATCH"
    for prefix in PEERS:
        require(packet.pins[prefix + "evidence.json"].sha256 == release.f5_sha256, code)
        evidence = packet.payload(
            prefix, "evidence", "artifacts candidate_class scope test_execution_attestation"
        )
        _artifact_pins(packet, prefix, F5_FILES[:-1], evidence["artifacts"])
        require(
            evidence["candidate_class"] == kind
            and evidence["scope"] == "AUTHORED_SYNTHETIC_ONLY"
            and evidence["test_execution_attestation"] == "NOT_ATTESTED_BY_RUNTIME",
            code,
        )
    require(all(packet.pins[leaf].sha256 == release.effective_sha256 for leaf in EFFECTIVE), code)
    packet.exact_match(*EFFECTIVE)
    result = packet.payload(PEERS[0], "metrics", _METRICS)
    effective = record(packet.json(EFFECTIVE[0]), "books comparison_status coverage")
    record(packet.json(EFFECTIVE[1]), "books comparison_status coverage")
    require(
        effective["comparison_status"] == result["candidate_class"] == kind
        and effective["books"] == result["books"]
        and effective["coverage"] == result["coverage"],
        code,
    )
    if kind == "DEGRADED_DIAGNOSTIC_ONLY":
        fail("PAIR_DEGRADED")
    require(kind == c.COMPLETE and result["common_failure"] is None, "PAIR_INCOMPLETE")
    return effective


def _book_metrics(effective: Record, census: Record, ledger_counts: Record) -> Record:
    coverage = record(
        effective["coverage"],
        " ".join(census) + " committed_common_mark_cells "
        "complete_calendar mark_requests native_slice_attempts qualified_common_mark_cells "
        "returned_mark_records successful_native_qualified_reads",
    )
    require(coverage["complete_calendar"] is True, "PAIR_INCOMPLETE")
    require(_census({key: coverage[key] for key in census}) == census, "PROVENANCE_MISMATCH")
    for name in coverage.keys() - census.keys() - {"complete_calendar"}:
        integer(
            coverage[name],
            ledger_counts["qualified_marks"],
            ledger_counts["qualified_marks"],
            "PAIR_INCOMPLETE",
        )
    books = record(effective["books"], " ".join((*ORIGINAL_POLICIES, *MIRROR_POLICIES)))
    for key, raw in books.items():
        book = record(
            raw,
            "applied_fallback candidate_metrics full_period_candidate no_trade_events "
            "processed_opportunities terminal_book total_fee total_slippage trade_events "
            "traded_legs unapplied_fallback weekly_returns_evaluated",
        )
        for count in ("processed_opportunities", "weekly_returns_evaluated"):
            integer(book[count], 48, 48, "PAIR_INCOMPLETE")
        for count in ("applied_fallback", "unapplied_fallback"):
            integer(book[count], 0, 0, "PAIR_DEGRADED")
        require(
            integer(book["trade_events"], 0, 48) + integer(book["no_trade_events"], 0, 48) == 48,
            "PAIR_INCOMPLETE",
        )
        metrics = record(
            book["full_period_candidate"],
            "annualization iid_inference "
            "linked_pre_friction_gross_return maximum_daily_event_drawdown net_return "
            "weekly_mean weekly_return_count weekly_returns weekly_sample_variance "
            "weekly_volatility_display",
        )
        require(
            book["candidate_metrics"] == metrics
            and metrics["annualization"] == metrics["iid_inference"] == "NOT_PERFORMED",
            "PROVENANCE_MISMATCH",
        )
        require(
            integer(metrics["weekly_return_count"], 48, 48)
            == len(array(metrics["weekly_returns"], 48))
        )
        for metric in (
            "linked_pre_friction_gross_return",
            "maximum_daily_event_drawdown",
            "net_return",
        ):
            fraction(metrics[metric])
        for charge in ("total_fee", "total_slippage"):
            numerator, _ = fraction(book[charge])
            require(numerator == 0 if key in MIRROR_POLICIES else numerator >= 0)
        c.decimal12(metrics["weekly_volatility_display"])
    return books


@dataclass(frozen=True)
class Historical:
    """Private, in-process link-check result. Never serialized or passed to the browser."""

    release: Release
    f3_spec: Record
    experiment_ref: str
    f5_spec: Record
    fits: list[Record]
    observations: dict[int, Record]
    slots: dict[tuple[int, str], Record]
    events: dict[tuple[int, str], Record]
    coverage: Record
    books: Record


def _inspect(raw: bytes, release: Release, budget: Budget) -> Historical:
    with _packet(raw, release, budget) as packet:
        for member, pin in HANDOFF.items():
            require(packet.pins[member].sha256 == pin, "PROVENANCE_MISMATCH")
        for prefix in PEERS:
            _inventory(packet, prefix, (*F5_FILES, "attempt"))
        for name in F5_FILES:
            packet.exact_match(PEERS[0] + name + ".json", PEERS[1] + name + ".json")
        producer = _f3(packet, release)
        first = packet.payload(PEERS[0], "attempt", ATTEMPT_FIELDS)
        second = packet.payload(PEERS[1], "attempt", ATTEMPT_FIELDS)
        attempts = first, second
        kind = _check_pair(attempts, producer.receipt["root"], release.f5_sha256)
        _pair_record(packet, release, attempts, kind)
        effective = _effective(packet, release, kind)
        spec, sessions = _f5_spec(packet, release, producer)
        observations, slots, census, info = _decision_records(packet, spec, producer)
        f3_spec, experiment_ref, fits = (
            producer.spec,
            producer.attempt["experiment_ref"],
            producer.fits,
        )
        del producer
        budget.check()
        events, ledger_counts = _ledger_data(packet, sessions, spec, slots)
        books = _book_metrics(effective, census, ledger_counts)
        coverage = {
            "ticks": info["actual_ticks"],
            "valid_slots": census["valid"],
            "oos_cells": info["verified_oos_cells"],
            "historical_bindings": info["verified_historical_bindings"],
            **ledger_counts,
        }
        budget.check()
        return Historical(
            release,
            f3_spec,
            experiment_ref,
            spec,
            fits,
            observations,
            slots,
            events,
            coverage,
            books,
        )
