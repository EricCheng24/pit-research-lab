"""E1 lifecycle codecs/audit and an explicitly RECORDED_ONLY SQLite writer.

Physical activation is a separate unavailable session boundary. This class never
inherits SyntheticCatalog, changes its audit, or converts fixture SQL into GO.
OAA-02 OS-F02: without a committed child, no catalog Wait/Q is accepted.
"""

import os
import re
import sqlite3
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol, Self, TypeVar
from uuid import uuid4

from pit_research_lab.mvp.f6 import contracts as c

from . import launch_policy as p
from . import runtime_catalog as core
from . import supervisor as s
from .os_ownership import LAUNCHER_FIELDS, require_physical_session
from .process_identity import boot_text, process_number

APPLICATION_ID = core.APPLICATION_ID
SCHEMA_VERSION = core.SCHEMA_VERSION
SCHEMA_IDENTITY = core.SCHEMA_IDENTITY
STATEMENTS = core.STATEMENTS
PURPOSE = core.PURPOSE
PHYSICAL_PROFILE = "PHYSICAL_HELPER_V1"
RECORDED_ONLY = "RECORDED_ONLY"
DB_LIMIT = 2 * 1024 * 1024
BUSY_MS = 250
CHILD_FIELDS = (
    "version installation_id app_run_id permission_id launcher_id generation boot_id pid "
    "start_ticks pgid sid nonce_sha256 executable_sha256 command_sha256 popen_exec_ack "
    "handshake_kind observed_at"
)
WAIT_FIELDS = (
    "version installation_id app_run_id permission_id launcher_id generation "
    "child_record_sha256 boot_id wait_kind exit_code signal_number reaped_at monotonic_ns "
    "resource_observations_sha256"
)
QUIESCENCE_FIELDS = (
    "version app_run_id basis original_launcher_record_sha256 wait_record_sha256 "
    "child_contract_sha256 process_inventory_sha256 lease_disposition_sha256 "
    "owner_adjudication_sha256 observed_boot_id observed_at"
)
ARM_FIELDS = (
    "app_run_id permission_id launcher_id generation command_sha256 deadline_boot_id "
    "arm_monotonic_ns deadline_monotonic_ns consumed"
)
RECORD_FIELDS = {
    "LAUNCHER": LAUNCHER_FIELDS,
    "CHILD": CHILD_FIELDS,
    "WAIT": WAIT_FIELDS,
    "QUIESCENCE": QUIESCENCE_FIELDS,
    "ARM": ARM_FIELDS,
}
T = TypeVar("T")


class CatalogRefusal(p.ModelError):
    pass


def need(condition: object, code: str = "SCHEMA_REFUSED") -> None:
    if not condition:
        raise CatalogRefusal(code)


def record(kind: str, raw: bytes) -> c.WireObject:
    """Shape validation of supplied bytes, not observation or authority issuance."""
    need(kind in RECORD_FIELDS)
    obj = p.bounded_record(raw, RECORD_FIELDS[kind])
    if kind != "ARM":
        need(type(obj["version"]) is int and obj["version"] == 1)
    ids: list[str] = []
    for key, value in obj.items():
        if key in ("boot_id", "deadline_boot_id", "observed_boot_id"):
            boot_text(value)
        elif key.endswith("_id") or key == "generation":
            ids.append(c.uuid4_text(value))
        elif key.endswith("sha256"):
            if key != "owner_adjudication_sha256":
                c.sha256_text(value)
        elif key in ("pid", "pgid", "sid"):
            process_number(value)
        elif key.endswith(("_ticks", "_ino", "_dev", "_ns")):
            p.decimal_text(value, positive=key.endswith(("_ticks", "_ino")))
        elif key.endswith("_at"):
            c.timestamp(value)
    need(len(ids) == len(set(ids)))
    if kind == "ARM":
        need(type(obj["consumed"]) is int and obj["consumed"] == 1)
        need(int(c.text(obj["deadline_monotonic_ns"])) > int(c.text(obj["arm_monotonic_ns"])))
    if kind == "CHILD":
        need(obj["popen_exec_ack"] is True)
        need(obj["handshake_kind"] == "HELPER_CHALLENGE_RESPONSE")
    if kind == "WAIT":
        code, number = obj["exit_code"], obj["signal_number"]
        need(
            (
                obj["wait_kind"] == "EXIT"
                and type(code) is int
                and 0 <= code <= 255
                and number is None
            )
            or (
                obj["wait_kind"] == "SIGNAL"
                and code is None
                and type(number) is int
                and 1 <= number <= 64
            )
        )
    if kind == "QUIESCENCE":
        need(obj["basis"] == "ORIGINAL_WAIT_NOFORK_HELPER")
        need(obj["owner_adjudication_sha256"] is None)
    return obj


def record_matches_event(
    kind: str, raw: bytes, event: s.ModeledEvent, child_id: str | None = None
) -> bool:
    """Pure closed-byte attribution check, not kernel provenance."""
    obj = record(kind, raw)
    event.__post_init__()
    expected_kind = {
        "LAUNCHER": "LAUNCHER_REGISTERED",
        "ARM": "SPAWN_ARMED",
        "CHILD": "CHILD_REGISTERED",
        "WAIT": "EXIT_OBSERVED",
        "QUIESCENCE": "QUIESCENCE_PROVEN",
    }[kind]
    if event.kind != expected_kind or obj["app_run_id"] != event.app_run_id:
        return False
    if kind != "QUIESCENCE" and obj["generation"] != event.generation:
        return False
    if kind == "LAUNCHER":
        expected: c.WireObject = {
            "launcher_id": obj["launcher_id"],
            "launcher_record_sha256": p.digest(kind, raw),
        }
    elif kind == "ARM":
        expected = {
            k: obj[k]
            for k in ("permission_id", "launcher_id", "command_sha256", "deadline_monotonic_ns")
        }
    elif kind == "CHILD":
        expected = {"child_id": c.uuid4_text(child_id), "child_record_sha256": p.digest(kind, raw)}
    elif kind == "WAIT":
        expected = {
            "wait_record_sha256": p.digest(kind, raw),
            "result_kind": obj["wait_kind"],
            "exit_code": obj["exit_code"],
            "signal_number": obj["signal_number"],
        }
    else:
        expected = {"proof_sha256": p.digest(kind, raw), "basis": obj["basis"]}
    return event.facts == c.canonical_json(expected)


@dataclass(frozen=True, slots=True)
class RecordedLocation:
    root: Path
    filename: str

    def __post_init__(self) -> None:
        p.path_form(str(self.root))
        need(self.root.is_relative_to("/tmp"), "LOCATION_REFUSED")
        need(
            any(
                re.fullmatch(r"pit-p103b-os-source\.[0-9]+\.[A-Za-z0-9]+", part)
                for part in self.root.parts[2:]
            ),
            "LOCATION_REFUSED",
        )
        need(not any(part.startswith("pit-p103b-os-helper.") for part in self.root.parts))
        need(re.fullmatch(r"[a-z][a-z0-9_-]{0,40}\.sqlite3", self.filename), "LOCATION_REFUSED")

    @property
    def path(self) -> Path:
        return self.root / self.filename


@dataclass(frozen=True, slots=True)
class PhysicalLocation:
    """Lexical future storage contract only; construction performs no I/O."""

    root: Path
    filename: str = field(default="catalog.sqlite3", init=False)

    def __post_init__(self) -> None:
        p.path_form(str(self.root))
        need(
            re.fullmatch(r"/tmp/pit-p103b-os-helper\.[0-9]+\.[A-Za-z0-9]+", str(self.root)),
            "LOCATION_REFUSED",
        )

    @property
    def path(self) -> Path:
        return self.root / self.filename


class OwnedCatalogSession(Protocol):
    """Future issuer-bound original observations, not a duck-typed permission.

    require_physical_session must succeed BEFORE accessing this interface. Its
    future issuer must bind source/profile/leases/role and the actual original
    child/reap observations, rather than merely accepting the supplied bytes.
    """

    def validate_record(self, kind: str, raw: bytes) -> None: ...


@dataclass(frozen=True, slots=True)
class _OwnedOwnerAck:
    generation: str
    owner_sha256: str
    _issuer: object = field(repr=False, compare=False)
    _session: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class RecordedOwnerAck:
    generation: str
    owner_sha256: str
    _issuer: object = field(repr=False, compare=False)

    def live_refusal(self) -> str:
        return RECORDED_ONLY


@dataclass(frozen=True, slots=True)
class RecordedIdentity:
    app_run_id: str
    allocation_id: str
    fingerprint: str
    accepted_at: str
    original_generation: str


@dataclass(frozen=True, slots=True)
class RecordedHistory:
    installation_id: str
    revision: int
    active_run: str | None
    models: tuple[s.RunModel, ...]
    evidence_class: str = field(default=RECORDED_ONLY, init=False)


def _owner_columns(obj: c.WireObject, raw: bytes) -> tuple[object, ...]:
    return tuple(
        obj[k]
        for k in (
            "generation",
            "generation_number",
            "installation_id",
            "boot_id",
            "pid",
            "start_ticks",
            "pgid",
            "sid",
            "installation_lock_dev",
            "installation_lock_ino",
            "runtime_sha256",
        )
    ) + (raw,)


def _columns(
    kind: str, obj: c.WireObject, revision: int, child_id: str | None
) -> tuple[object, ...]:
    if kind == "LAUNCHER":
        return tuple(
            obj[k]
            for k in (
                "app_run_id",
                "launcher_id",
                "generation",
                "boot_id",
                "pid",
                "start_ticks",
                "pgid",
                "sid",
                "job_lock_dev",
                "job_lock_ino",
                "channel_nonce_sha256",
            )
        ) + (c.canonical_json(obj), revision)
    if kind == "ARM":
        return tuple(obj[k] for k in ARM_FIELDS.split()) + (revision,)
    if kind == "CHILD":
        c.uuid4_text(child_id)
        return (
            (obj["app_run_id"], child_id)
            + tuple(
                obj[k]
                for k in (
                    "launcher_id",
                    "boot_id",
                    "pid",
                    "start_ticks",
                    "pgid",
                    "sid",
                    "nonce_sha256",
                    "executable_sha256",
                )
            )
            + (c.canonical_json(obj), revision)
        )
    if kind == "WAIT":
        return tuple(
            obj[k]
            for k in (
                "app_run_id",
                "launcher_id",
                "child_record_sha256",
                "wait_kind",
                "exit_code",
                "signal_number",
            )
        ) + (1, c.canonical_json(obj), revision)
    need(kind == "QUIESCENCE")
    raw = c.canonical_json(obj)
    return (obj["app_run_id"], obj["basis"], raw, p.digest("QUIESCENCE", raw), revision)


class OsHelperCatalog:
    """Explicit recorded-fixture methods; reopening never resumes a write session.

    Constructor is inert. The physical activation method refuses before any I/O;
    there is no PHYSICAL_HELPER_V1 installation issuer in this authorization.
    """

    def __init__(self, location: RecordedLocation | PhysicalLocation) -> None:
        need(type(location) in (RecordedLocation, PhysicalLocation))
        self.location = location
        self._connection: sqlite3.Connection | None = None
        self._issuer = object()
        self._acks: set[tuple[str, str]] = set()
        self._uncertain = False
        self._writable = False
        self._physical_session: object | None = None
        self._owned_acks: set[tuple[str, str]] = set()

    def activate_physical(self, session: OwnedCatalogSession) -> Self:
        require_physical_session(session, "catalog")
        need(type(self.location) is PhysicalLocation)
        self.location.__post_init__()
        self._location(False)
        authority_path = self.location.root / "authority.json"
        info = authority_path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid())
        need(stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 16384)
        with authority_path.open("rb") as stream:
            raw = stream.read(16385)
            opened = os.fstat(stream.fileno())
            need(
                (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_uid,
                    opened.st_mode,
                    opened.st_nlink,
                    opened.st_size,
                    opened.st_mtime_ns,
                )
                == (
                    info.st_dev,
                    info.st_ino,
                    info.st_uid,
                    info.st_mode,
                    info.st_nlink,
                    info.st_size,
                    info.st_mtime_ns,
                )
            )
        need(len(raw) <= 16384)
        session.validate_record("AUTHORITY", raw)
        metadata = c.decode_json(raw)
        need(type(metadata) is dict)
        assert isinstance(metadata, dict)
        need(metadata.get("profile") == PHYSICAL_PROFILE)
        installation = c.uuid4_text(metadata.get("installation_id"))
        created = c.timestamp(metadata.get("created_at"))
        # Metadata/hash alone is never authority: the prior session call binds
        # the approved exact bytes and kernel/root/source/role observations.
        self._physical_session = session
        return self._initialize(installation, sha256(raw).hexdigest(), created)

    def register_owner_owned(self, session: OwnedCatalogSession, raw: bytes) -> _OwnedOwnerAck:
        require_physical_session(session, "catalog_OWNER")
        session.validate_record("OWNER", raw)
        obj = core.SyntheticOwner(raw).values()  # Codec only, not a synthetic ACK.

        def work(db: sqlite3.Connection) -> None:
            install = db.execute("SELECT * FROM installation").fetchone()
            need(db.execute("SELECT COUNT(*) FROM owners").fetchone()[0] == 0, "NO_OWNER_ROLLOVER")
            need(obj["installation_id"] == install["installation_id"])
            need(obj["authority_record_sha256"] == install["authority_sha256"])
            need(obj["generation_number"] == 1 and obj["previous_registration_sha256"] is None)
            db.execute(
                "INSERT INTO owners VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", _owner_columns(obj, raw)
            )

        self._write_owned(session, "OWNER", work)
        generation, signature = c.text(obj["generation"]), p.digest("OWNER", raw)
        self._owned_acks.add((generation, signature))
        return _OwnedOwnerAck(generation, signature, self._issuer, session)

    def admit_owned(
        self,
        session: OwnedCatalogSession,
        intent: core.SyntheticIntent,
        ack: _OwnedOwnerAck | None,
        *,
        expected_revision: int,
        expected_capability_revision: str,
    ) -> RecordedIdentity:
        require_physical_session(session, "catalog_INTENT")
        intent.__post_init__()
        session.validate_record("INTENT", intent.admission_bytes)
        request = c.SubmissionRequest.parse(intent.request_bytes).to_wire()
        found = self.lookup_recorded(intent.request_bytes)
        if found is not None:
            return found  # Identity readback is never a usable launch continuation.

        def work(db: sqlite3.Connection) -> RecordedIdentity:
            found = self._lookup(db, request)
            if found is not None:
                return found
            need(type(ack) is _OwnedOwnerAck, "ORIGINAL_OWNER_ACK_REQUIRED")
            assert ack is not None
            need(ack._issuer is self._issuer and ack._session is session)
            need((ack.generation, ack.owner_sha256) in self._owned_acks)
            owner = db.execute(
                "SELECT * FROM owners WHERE generation=?", (ack.generation,)
            ).fetchone()
            need(
                owner is not None
                and p.digest("OWNER", owner["registration_bytes"]) == ack.owner_sha256
            )
            need(request["capability_revision"] == expected_capability_revision)
            need(not db.execute("SELECT * FROM current_slot").fetchall(), "BUSY")
            need(
                db.execute("SELECT COALESCE(MAX(revision),0) FROM events").fetchone()[0]
                == expected_revision
            )
            exp = intent.expectations.values()
            need(exp["installation_id"] == owner["installation_id"])
            app = str(uuid4())
            db.execute(
                "INSERT INTO runs VALUES(?,?,'FIXED_SUBMISSION',?,?,?,?,?,?,?,?,?,1)",
                (
                    app,
                    owner["installation_id"],
                    request["idempotency_key"],
                    intent.request_bytes,
                    c.submission_fingerprint(request),
                    exp["allocation_id"],
                    intent.accepted_at,
                    intent.admission_bytes,
                    p.digest("INTENT", intent.admission_bytes),
                    intent.expectations.raw,
                    p.digest("EXPECTATION", intent.expectations.raw),
                ),
            )
            event = self._event(
                db,
                app,
                "INTENT_COMMITTED",
                s.Phase.INTENT_HELD,
                "ADMISSION",
                {
                    "admission_sha256": p.digest("INTENT", intent.admission_bytes),
                    "expectation_sha256": p.digest("EXPECTATION", intent.expectations.raw),
                    "fingerprint": c.submission_fingerprint(request),
                    "allocation_id": exp["allocation_id"],
                },
                expected_revision,
                intent.accepted_at,
                intent.monotonic_ns,
                ack.generation,
            )
            db.execute("INSERT INTO slot_log VALUES(1,?,'RESERVE',?)", (app, event.revision))
            result = self._lookup(db, request)
            assert result is not None
            return result

        return self._write_owned(session, "INTENT", work)

    def _db(self) -> sqlite3.Connection:
        need(self._connection is not None, "STORAGE_BLOCKED")
        assert self._connection is not None
        return self._connection

    def _location(self, existing: bool) -> None:
        self.location.__post_init__()
        for parent in (self.location.root, *self.location.root.parents):
            need(stat.S_ISDIR(parent.lstat().st_mode), "STORAGE_BLOCKED")
        info = self.location.root.lstat()
        need(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, "STORAGE_BLOCKED")
        for suffix in ("-journal", "-wal", "-shm"):
            need(not os.path.lexists(str(self.location.path) + suffix), "STORAGE_BLOCKED")
        if existing:
            info = self.location.path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "STORAGE_BLOCKED")
            need(
                info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                "STORAGE_BLOCKED",
            )
            need(info.st_size <= DB_LIMIT, "STORAGE_BLOCKED")
        else:
            need(not os.path.lexists(self.location.path), "STORAGE_BLOCKED")

    @staticmethod
    def _pragmas(db: sqlite3.Connection) -> None:
        for key, value in (
            ("foreign_keys", 1),
            ("defer_foreign_keys", 0),
            ("recursive_triggers", 1),
            ("synchronous", 3),
            ("busy_timeout", BUSY_MS),
            ("journal_mode", "delete"),
        ):
            need(db.execute("PRAGMA " + key).fetchone()[0] == value)

    def _connect(self, readonly: bool) -> sqlite3.Connection:
        db = sqlite3.connect(
            self.location.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
            uri=True,
            isolation_level=None,
            timeout=BUSY_MS / 1000,
        )
        db.row_factory = sqlite3.Row
        try:
            for key, value in (
                ("foreign_keys", "ON"),
                ("defer_foreign_keys", "OFF"),
                ("recursive_triggers", "ON"),
                ("synchronous", "EXTRA"),
                ("busy_timeout", str(BUSY_MS)),
            ):
                db.execute("PRAGMA " + key + "=" + value)
            if not readonly:
                page = db.execute("PRAGMA page_size").fetchone()[0]
                db.execute(f"PRAGMA max_page_count={DB_LIMIT // page}")
            self._pragmas(db)
            return db
        except BaseException:
            db.close()
            raise

    def initialize_recorded(
        self, installation_id: str, authority_sha256: str, created_at: str
    ) -> Self:
        need(type(self.location) is RecordedLocation, "RECORDED_ROOT_REQUIRED")
        return self._initialize(installation_id, authority_sha256, created_at)

    def _initialize(self, installation_id: str, authority_sha256: str, created_at: str) -> Self:
        need(self._connection is None and not self._uncertain, "STORAGE_BLOCKED")
        c.uuid4_text(installation_id)
        c.sha256_text(authority_sha256)
        c.timestamp(created_at)
        self._location(False)
        fd = os.open(
            self.location.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        os.close(fd)
        db = self._connect(False)
        try:
            db.execute("BEGIN IMMEDIATE")
            for sql in STATEMENTS:
                db.execute(sql)
            root = self.location.root.lstat()
            db.execute(
                "INSERT INTO installation VALUES(1,?,?,1,?,?,?,?,?)",
                (
                    installation_id,
                    PURPOSE,
                    SCHEMA_IDENTITY,
                    authority_sha256,
                    str(root.st_dev),
                    str(root.st_ino),
                    created_at,
                ),
            )
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            self._audit(db)
            db.commit()
        except BaseException:
            db.rollback()
            db.close()
            raise
        self._connection, self._writable = db, True
        return self

    def open_recorded(self) -> Self:
        need(type(self.location) is RecordedLocation, "RECORDED_ROOT_REQUIRED")
        return self._open_readback()

    def open_physical_readback(self, session: OwnedCatalogSession) -> Self:
        require_physical_session(session, "catalog_readback")
        need(type(self.location) is PhysicalLocation)
        # Readback never sets _physical_session, _writable or owner ACKs.
        return self._open_readback()

    def attach_original_launcher(self, session: OwnedCatalogSession) -> Self:
        """Original prearm L only: live I/J, Tx2 ACK and unused local continuation.

        The future issuer must retain the original in-process registration ACK,
        nonce and FD lineage. Reopen, readback or a replacement L cannot issue it.
        """
        require_physical_session(session, "catalog_ORIGINAL_LAUNCHER_ATTACH")
        need(type(self.location) is PhysicalLocation and self._connection is None)
        self._location(True)
        db = self._connect(True)
        try:
            db.execute("BEGIN")
            history = self._audit(db)
            need(len(history.models) == 1 and history.models[0].phase is s.Phase.OWNER_READY)
            launcher = db.execute("SELECT record_bytes FROM launchers").fetchone()
            need(launcher is not None)
            session.validate_record("ORIGINAL_LAUNCHER_ATTACH", launcher["record_bytes"])
        finally:
            db.rollback()
            db.close()
        writable = self._connect(False)
        try:
            writable.execute("BEGIN")
            self._audit(writable)
            writable.rollback()
        except BaseException:
            writable.close()
            raise
        self._connection = writable
        self._physical_session = session
        self._writable = True
        return self

    def _open_readback(self) -> Self:
        need(self._connection is None, "STORAGE_BLOCKED")
        self._location(True)
        db = self._connect(True)
        try:
            db.execute("BEGIN")
            self._audit(db)
            db.rollback()
        except BaseException:
            db.close()
            raise
        self._connection, self._writable = db, False
        return self

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection, self._writable = None, False
        self._acks.clear()
        self._owned_acks.clear()
        self._physical_session = None

    def _before_commit(self, operation: str) -> None:
        """Inert recorded-only exception seam; no environment selector."""

    def _after_commit(self, operation: str) -> None:
        """Inert recorded-only commit-then-raise seam."""

    def _checkpoint(self, point: str) -> None:
        """Inert recorded-only precommit fault seam."""

    def _write(self, operation: str, work: Callable[[sqlite3.Connection], T]) -> T:
        need(type(self.location) is RecordedLocation, "RECORDED_ROOT_REQUIRED")
        return self._transaction(operation, work)

    def _write_owned(
        self, session: OwnedCatalogSession, operation: str, work: Callable[[sqlite3.Connection], T]
    ) -> T:
        require_physical_session(session, "catalog_" + operation)
        need(type(self.location) is PhysicalLocation and session is self._physical_session)
        return self._transaction(operation, work)

    def _transaction(self, operation: str, work: Callable[[sqlite3.Connection], T]) -> T:
        need(not self._uncertain, "COMMIT_UNKNOWN")
        need(self._writable, "READBACK_ONLY")
        self._location(True)
        db = self._db()
        committing = False
        try:
            db.execute("BEGIN IMMEDIATE")
            self._audit(db)
            result = work(db)
            self._audit(db)
            self._before_commit(operation)
            committing = True
            db.commit()
            self._after_commit(operation)
            return result
        except BaseException:
            if committing:
                self._uncertain = True
                self._acks.clear()
                self._owned_acks.clear()
            try:
                db.rollback()
            except sqlite3.Error:
                self._uncertain = True
                self._acks.clear()
                self._owned_acks.clear()
            if committing:
                raise CatalogRefusal("COMMIT_UNKNOWN") from None
            raise

    def audit_recorded(self) -> RecordedHistory:
        self._location(True)
        db = self._db()
        try:
            db.execute("BEGIN")
            return self._audit(db)
        finally:
            db.rollback()

    def register_owner_recorded(self, raw: bytes) -> RecordedOwnerAck:
        obj = core.SyntheticOwner(raw).values()  # Pure codec; no synthetic catalog API.

        def work(db: sqlite3.Connection) -> None:
            install = db.execute("SELECT * FROM installation").fetchone()
            prior = db.execute(
                "SELECT * FROM owners ORDER BY generation_number DESC LIMIT 1"
            ).fetchone()
            need(obj["installation_id"] == install["installation_id"])
            need(obj["authority_record_sha256"] == install["authority_sha256"])
            need(obj["generation_number"] == (prior["generation_number"] + 1 if prior else 1))
            need(
                obj["previous_registration_sha256"]
                == (p.digest("OWNER", prior["registration_bytes"]) if prior else None)
            )
            db.execute(
                "INSERT INTO owners VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", _owner_columns(obj, raw)
            )
            self._checkpoint("OWNER_INSERTED")

        self._write("OWNER", work)
        generation, signature = c.text(obj["generation"]), p.digest("OWNER", raw)
        self._acks.add((generation, signature))
        return RecordedOwnerAck(generation, signature, self._issuer)

    @staticmethod
    def _lookup(db: sqlite3.Connection, request: c.WireObject) -> RecordedIdentity | None:
        row = db.execute(
            "SELECT * FROM runs WHERE idempotency_key=?", (request["idempotency_key"],)
        ).fetchone()
        if row is None:
            return None
        need(row["fingerprint"] == c.submission_fingerprint(request), "IDEMPOTENCY_CONFLICT")
        event = db.execute(
            "SELECT generation FROM events WHERE app_run_id=? AND run_sequence=1",
            (row["app_run_id"],),
        ).fetchone()
        return RecordedIdentity(
            row["app_run_id"],
            row["allocation_id"],
            row["fingerprint"],
            row["accepted_at"],
            event["generation"],
        )

    def lookup_recorded(self, request_bytes: bytes) -> RecordedIdentity | None:
        request = c.SubmissionRequest.parse(request_bytes).to_wire()
        self.audit_recorded()
        return self._lookup(self._db(), request)

    def admit_recorded(
        self,
        intent: core.SyntheticIntent,
        ack: RecordedOwnerAck | None,
        *,
        expected_revision: int,
        expected_capability_revision: str,
    ) -> RecordedIdentity:
        need(type(intent) is core.SyntheticIntent)
        intent.__post_init__()
        request = c.SubmissionRequest.parse(intent.request_bytes).to_wire()
        found = self.lookup_recorded(intent.request_bytes)
        if found is not None:
            return found

        def work(db: sqlite3.Connection) -> RecordedIdentity:
            found = self._lookup(db, request)
            if found is not None:
                return found
            need(type(ack) is RecordedOwnerAck, "OWNER_ACK_REQUIRED")
            assert ack is not None
            need(ack._issuer is self._issuer and (ack.generation, ack.owner_sha256) in self._acks)
            owner = db.execute(
                "SELECT * FROM owners ORDER BY generation_number DESC LIMIT 1"
            ).fetchone()
            need(owner is not None and owner["generation"] == ack.generation)
            need(p.digest("OWNER", owner["registration_bytes"]) == ack.owner_sha256)
            need(request["capability_revision"] == expected_capability_revision)
            need(not db.execute("SELECT * FROM current_slot").fetchall(), "BUSY")
            need(
                db.execute("SELECT COALESCE(MAX(revision),0) FROM events").fetchone()[0]
                == expected_revision
            )
            exp = intent.expectations.values()
            need(exp["installation_id"] == owner["installation_id"])
            app = str(uuid4())
            db.execute(
                "INSERT INTO runs VALUES(?,?,'FIXED_SUBMISSION',?,?,?,?,?,?,?,?,?,1)",
                (
                    app,
                    owner["installation_id"],
                    request["idempotency_key"],
                    intent.request_bytes,
                    c.submission_fingerprint(request),
                    exp["allocation_id"],
                    intent.accepted_at,
                    intent.admission_bytes,
                    p.digest("INTENT", intent.admission_bytes),
                    intent.expectations.raw,
                    p.digest("EXPECTATION", intent.expectations.raw),
                ),
            )
            self._checkpoint("RUN_INSERTED")
            event = self._event(
                db,
                app,
                "INTENT_COMMITTED",
                s.Phase.INTENT_HELD,
                "ADMISSION",
                {
                    "admission_sha256": p.digest("INTENT", intent.admission_bytes),
                    "expectation_sha256": p.digest("EXPECTATION", intent.expectations.raw),
                    "fingerprint": c.submission_fingerprint(request),
                    "allocation_id": exp["allocation_id"],
                },
                expected_revision,
                intent.accepted_at,
                intent.monotonic_ns,
                ack.generation,
            )
            db.execute("INSERT INTO slot_log VALUES(1,?,'RESERVE',?)", (app, event.revision))
            self._checkpoint("SLOT_INSERTED")
            result = self._lookup(db, request)
            assert result is not None
            return result

        return self._write("INTENT", work)

    def _event(
        self,
        db: sqlite3.Connection,
        app: str,
        kind: str,
        phase: s.Phase,
        actor: str,
        facts: c.WireObject,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
        generation: str | None = None,
    ) -> s.ModeledEvent:
        prior = db.execute("SELECT * FROM events ORDER BY revision DESC LIMIT 1").fetchone()
        revision = prior["revision"] if prior else 0
        need(revision == expected_revision, "STALE_EVENT")
        first = db.execute(
            "SELECT * FROM events WHERE app_run_id=? ORDER BY run_sequence LIMIT 1", (app,)
        ).fetchone()
        if generation is None:
            need(first is not None)
            generation = first["generation"]
        owner = db.execute("SELECT * FROM owners WHERE generation=?", (generation,)).fetchone()
        need(owner is not None)
        sequence = db.execute(
            "SELECT COALESCE(MAX(run_sequence),0)+1 FROM events WHERE app_run_id=?", (app,)
        ).fetchone()[0]
        event = s.ModeledEvent(
            revision + 1,
            app,
            sequence,
            revision,
            kind,
            phase,
            actor,
            generation,
            observed_at,
            owner["boot_id"],
            monotonic_ns,
            c.canonical_json(facts),
            prior["event_sha256"] if prior else s.ZERO_HASH,
        )
        db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event.revision,
                app,
                sequence,
                revision,
                kind,
                phase.value,
                actor,
                generation,
                observed_at,
                owner["boot_id"],
                monotonic_ns,
                1,
                event.facts,
                event.previous_sha256,
                event.event_sha256,
            ),
        )
        return event

    def append_recorded(
        self,
        kind: str,
        raw: bytes,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
        child_id: str | None = None,
    ) -> None:
        self._write(
            kind,
            self._record_work(
                kind,
                raw,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
                child_id=child_id,
            ),
        )

    def append_owned(
        self,
        session: OwnedCatalogSession,
        kind: str,
        raw: bytes,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
        child_id: str | None = None,
    ) -> None:
        require_physical_session(session, "catalog_" + kind)
        session.validate_record(kind, raw)
        self._write_owned(
            session,
            kind,
            self._record_work(
                kind,
                raw,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
                child_id=child_id,
            ),
        )

    def _record_work(
        self,
        kind: str,
        raw: bytes,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
        child_id: str | None = None,
    ) -> Callable[[sqlite3.Connection], None]:
        obj = record(kind, raw)
        app = c.text(obj["app_run_id"])
        specs = {
            "LAUNCHER": ("launchers", "LAUNCHER_REGISTERED", s.Phase.OWNER_READY, "SUPERVISOR"),
            "ARM": ("arms", "SPAWN_ARMED", s.Phase.ARM_CONSUMED, "LAUNCHER"),
            "CHILD": ("children", "CHILD_REGISTERED", s.Phase.CHILD_KNOWN, "LAUNCHER"),
            "WAIT": ("waits", "EXIT_OBSERVED", s.Phase.EXIT_HELD, "LAUNCHER"),
            "QUIESCENCE": ("quiescence", "QUIESCENCE_PROVEN", s.Phase.EXIT_HELD, "SUPERVISOR"),
        }
        table, event_kind, phase, actor = specs[kind]

        def work(db: sqlite3.Connection) -> None:
            if kind == "WAIT":
                need(
                    db.execute("SELECT 1 FROM children WHERE app_run_id=?", (app,)).fetchone(),
                    "REGISTRATION_GAP",
                )
            if kind == "LAUNCHER":
                facts: c.WireObject = {
                    "launcher_id": obj["launcher_id"],
                    "launcher_record_sha256": p.digest(kind, raw),
                }
            elif kind == "ARM":
                need(obj["arm_monotonic_ns"] == monotonic_ns)
                facts = {
                    k: obj[k]
                    for k in (
                        "permission_id",
                        "launcher_id",
                        "command_sha256",
                        "deadline_monotonic_ns",
                    )
                }
            elif kind == "CHILD":
                facts = {
                    "child_id": c.uuid4_text(child_id),
                    "child_record_sha256": p.digest(kind, raw),
                }
            elif kind == "WAIT":
                facts = {
                    "wait_record_sha256": p.digest(kind, raw),
                    "result_kind": obj["wait_kind"],
                    "exit_code": obj["exit_code"],
                    "signal_number": obj["signal_number"],
                }
            else:
                facts = {"proof_sha256": p.digest(kind, raw), "basis": obj["basis"]}
            values = _columns(kind, obj, expected_revision + 1, child_id)
            # arm_owner must see OWNER_READY before the arm event is appended.
            db.execute(
                "INSERT INTO " + table + " VALUES(" + ",".join("?" for _ in values) + ")", values
            )
            self._checkpoint(table.upper() + "_INSERTED")
            self._event(
                db,
                app,
                event_kind,
                phase,
                actor,
                facts,
                expected_revision,
                observed_at,
                monotonic_ns,
            )

        return work

    def failure_recorded(
        self,
        app: str,
        failure: s.Failure,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> None:
        self._write(
            "FIRST_FAILURE",
            self._failure_work(
                app,
                failure,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
            ),
        )

    def failure_owned(
        self,
        session: OwnedCatalogSession,
        app: str,
        failure: s.Failure,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> None:
        require_physical_session(session, "catalog_FIRST_FAILURE")
        session.validate_record(
            "FIRST_FAILURE",
            c.canonical_json(
                {
                    "reason": failure.reason,
                    "first_observed_at": failure.first_observed_at,
                    "source_sha256": failure.source_sha256,
                }
            ),
        )
        self._write_owned(
            session,
            "FIRST_FAILURE",
            self._failure_work(
                app,
                failure,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
            ),
        )

    def _failure_work(
        self,
        app: str,
        failure: s.Failure,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> Callable[[sqlite3.Connection], None]:
        failure.__post_init__()

        def work(db: sqlite3.Connection) -> None:
            row = db.execute(
                "SELECT * FROM current_run_state WHERE app_run_id=?", (app,)
            ).fetchone()
            need(row is not None)
            facts: c.WireObject = {
                "reason": failure.reason,
                "first_observed_at": failure.first_observed_at,
                "source_sha256": failure.source_sha256,
            }
            event = self._event(
                db,
                app,
                "FIRST_FAILURE",
                s.Phase(row["state"]),
                "LAUNCHER",
                facts,
                expected_revision,
                observed_at,
                monotonic_ns,
            )
            db.execute(
                "INSERT INTO first_failures VALUES(?,?,?,?,?,?)",
                (
                    app,
                    failure.reason,
                    failure.first_observed_at,
                    failure.source_sha256,
                    event.facts,
                    event.revision,
                ),
            )

        return work

    def terminal_recorded(
        self,
        app: str,
        disposition: str,
        evidence_sha256: str,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> None:
        self._write(
            "TERMINAL_HELD",
            self._terminal_work(
                app,
                disposition,
                evidence_sha256,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
            ),
        )

    def terminal_owned(
        self,
        session: OwnedCatalogSession,
        app: str,
        disposition: str,
        evidence_sha256: str,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> None:
        require_physical_session(session, "catalog_TERMINAL_HELD")
        session.validate_record(
            "TERMINAL_HELD",
            c.canonical_json({"disposition": disposition, "evidence_sha256": evidence_sha256}),
        )
        self._write_owned(
            session,
            "TERMINAL_HELD",
            self._terminal_work(
                app,
                disposition,
                evidence_sha256,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
            ),
        )

    def _terminal_work(
        self,
        app: str,
        disposition: str,
        evidence_sha256: str,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> Callable[[sqlite3.Connection], None]:
        def work(db: sqlite3.Connection) -> None:
            if disposition in ("HELPER_EXIT_ZERO_HELD", "FAILED_KNOWN"):
                need(db.execute("SELECT 1 FROM quiescence WHERE app_run_id=?", (app,)).fetchone())
            self._event(
                db,
                app,
                "TERMINAL_HELD",
                s.Phase.TERMINAL_HELD,
                "SUPERVISOR",
                {"disposition": disposition, "evidence_sha256": evidence_sha256},
                expected_revision,
                observed_at,
                monotonic_ns,
            )

        return work

    def quarantine_recorded(
        self,
        app: str,
        evidence_sha256: str,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> None:
        self._write(
            "QUARANTINED",
            self._quarantine_work(
                app,
                evidence_sha256,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
            ),
        )

    def quarantine_owned(
        self,
        session: OwnedCatalogSession,
        app: str,
        evidence_sha256: str,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> None:
        require_physical_session(session, "catalog_QUARANTINED")
        session.validate_record(
            "QUARANTINED", c.canonical_json({"evidence_sha256": evidence_sha256})
        )
        self._write_owned(
            session,
            "QUARANTINED",
            self._quarantine_work(
                app,
                evidence_sha256,
                expected_revision=expected_revision,
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
            ),
        )

    def _quarantine_work(
        self,
        app: str,
        evidence_sha256: str,
        *,
        expected_revision: int,
        observed_at: str,
        monotonic_ns: str,
    ) -> Callable[[sqlite3.Connection], None]:
        """Record uncertainty without inventing a wait or replacing first cause."""

        def work(db: sqlite3.Connection) -> None:
            self._event(
                db,
                app,
                "QUARANTINED",
                s.Phase.QUARANTINED,
                "SUPERVISOR",
                {
                    "prior_revision": expected_revision,
                    "evidence_sha256": evidence_sha256,
                    "reason": "EXECUTION_OUTCOME_UNKNOWN",
                },
                expected_revision,
                observed_at,
                monotonic_ns,
            )

        return work

    def _audit(self, db: sqlite3.Connection) -> RecordedHistory:
        try:
            return self._audit_records(db)
        except (
            p.ModelError,
            c.ContractError,
            sqlite3.Error,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
        ):
            raise CatalogRefusal("SCHEMA_REFUSED") from None

    def _audit_records(self, db: sqlite3.Connection) -> RecordedHistory:
        self._pragmas(db)
        need(db.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID)
        need(db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION)
        need(
            [
                r[0]
                for r in db.execute(
                    "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY sql"
                )
            ]
            == sorted(STATEMENTS)
        )
        need([r[0] for r in db.execute("PRAGMA quick_check")] == ["ok"])
        need(not db.execute("PRAGMA foreign_key_check").fetchall())
        install_rows = db.execute("SELECT * FROM installation").fetchall()
        need(len(install_rows) == 1)
        install = install_rows[0]
        installation = c.uuid4_text(install["installation_id"])
        need(
            install["singleton"] == 1
            and install["purpose"] == PURPOSE
            and install["schema_version"] == 1
        )
        need(install["ddl_sha256"] == SCHEMA_IDENTITY)
        c.sha256_text(install["authority_sha256"])
        c.timestamp(install["created_at"])
        info = self.location.root.lstat()
        need((install["root_dev"], install["root_ino"]) == (str(info.st_dev), str(info.st_ino)))
        limits = {
            "owners": 4,
            "runs": 1,
            "events": 128,
            "slot_log": 1,
            "launchers": 1,
            "arms": 1,
            "children": 1,
            "waits": 1,
            "first_failures": 1,
            "quiescence": 1,
        }
        for table, limit in limits.items():
            need(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] <= limit)
        owners: dict[str, c.WireObject] = {}
        predecessor: str | None = None
        for number, row in enumerate(
            db.execute("SELECT * FROM owners ORDER BY generation_number"), 1
        ):
            obj = core.SyntheticOwner(row["registration_bytes"]).values()
            need(tuple(row) == _owner_columns(obj, row["registration_bytes"]))
            need(obj["generation_number"] == number and obj["installation_id"] == installation)
            need(obj["previous_registration_sha256"] == predecessor)
            need(obj["authority_record_sha256"] == install["authority_sha256"])
            need(c.text(obj["observed_at"]) >= install["created_at"])
            owners[c.text(obj["generation"])] = obj
            predecessor = p.digest("OWNER", row["registration_bytes"])
        runs: dict[str, sqlite3.Row] = {}
        for row in db.execute("SELECT * FROM runs"):
            request = c.SubmissionRequest.parse(row["request_bytes"]).to_wire()
            exp = p.Expectations(row["expectation_bytes"])
            core.SyntheticIntent(
                row["request_bytes"], row["admission_bytes"], exp, row["accepted_at"], "0"
            )
            need(row["installation_id"] == installation and row["operation"] == "FIXED_SUBMISSION")
            need(
                row["intent_sequence"] == 1 and row["idempotency_key"] == request["idempotency_key"]
            )
            need(row["fingerprint"] == c.submission_fingerprint(request))
            need(row["admission_sha256"] == p.digest("INTENT", row["admission_bytes"]))
            need(row["expectation_sha256"] == p.digest("EXPECTATION", exp.raw))
            need(
                exp.values()["installation_id"] == installation
                and exp.values()["allocation_id"] == row["allocation_id"]
            )
            ids = [
                installation,
                c.uuid4_text(row["app_run_id"]),
                c.uuid4_text(row["allocation_id"]),
                c.uuid4_text(row["idempotency_key"]),
            ]
            need(len(set(ids)) == 4 and not set(ids[1:]) & set(owners))
            runs[row["app_run_id"]] = row
        models: dict[str, s.RunModel] = {}
        events: dict[int, s.ModeledEvent] = {}
        revision, previous_hash = 0, s.ZERO_HASH
        last_time = datetime.fromisoformat(install["created_at"])
        last_ns = 0
        for row in db.execute("SELECT * FROM events ORDER BY revision"):
            need(row["facts_version"] == 1 and row["kind"] != "SLOT_DISPOSED")
            e = s.ModeledEvent(
                row["revision"],
                row["app_run_id"],
                row["run_sequence"],
                row["expected_previous_revision"],
                row["kind"],
                s.Phase(row["state"]),
                row["actor"],
                row["generation"],
                row["observed_at"],
                row["boot_id"],
                row["monotonic_ns"],
                row["facts"],
                row["previous_sha256"],
            )
            need(
                e.event_sha256 == row["event_sha256"]
                and e.app_run_id in runs
                and e.generation in owners
            )
            owner, run = owners[e.generation], runs[e.app_run_id]
            need(
                e.boot_id == owner["boot_id"]
                and int(e.monotonic_ns) >= int(c.text(owner["monotonic_ns"]))
            )
            need(int(e.monotonic_ns) >= last_ns)
            observed = datetime.fromisoformat(e.observed_at)
            need(
                observed >= last_time
                and observed >= datetime.fromisoformat(c.text(owner["observed_at"]))
            )
            need(observed >= datetime.fromisoformat(run["accepted_at"]))
            if e.app_run_id not in models:
                need(e.kind == "INTENT_COMMITTED" and e.observed_at == run["accepted_at"])
                need(
                    e.facts
                    == c.canonical_json(
                        {
                            "admission_sha256": run["admission_sha256"],
                            "expectation_sha256": run["expectation_sha256"],
                            "fingerprint": run["fingerprint"],
                            "allocation_id": run["allocation_id"],
                        }
                    )
                )
                adm = p.bounded_record(run["admission_bytes"], core.ADMISSION_FIELDS)
                need(
                    adm["runtime_sha256"] == owner["runtime_sha256"]
                    and adm["authority_record_sha256"] == owner["authority_record_sha256"]
                )
                models[e.app_run_id] = s.RunModel(installation, e.app_run_id, e.generation)
            need(e.generation == models[e.app_run_id].original_generation)
            models[e.app_run_id] = s.reduce_model(
                models[e.app_run_id],
                e,
                previous_revision=revision,
                previous_sha256=previous_hash,
                registered_generations=tuple(owners),
            )
            events[e.revision] = e
            revision, previous_hash, last_time = e.revision, e.event_sha256, observed
            last_ns = int(e.monotonic_ns)
        need(set(models) == set(runs))
        self._audit_links(db, installation, owners, runs, models, events)
        slots = db.execute("SELECT * FROM slot_log").fetchall()
        need(len(slots) == len(runs))
        for row in slots:
            need(row["slot_sequence"] == 1 and row["action"] == "RESERVE")
            e = events[row["revision"]]
            need(e.kind == "INTENT_COMMITTED" and e.app_run_id == row["app_run_id"])
        return RecordedHistory(
            installation,
            revision,
            slots[0]["app_run_id"] if slots else None,
            tuple(models.values()),
        )

    @staticmethod
    def _audit_links(
        db: sqlite3.Connection,
        installation: str,
        owners: dict[str, c.WireObject],
        runs: dict[str, sqlite3.Row],
        models: dict[str, s.RunModel],
        events: dict[int, s.ModeledEvent],
    ) -> None:
        kinds = {
            "LAUNCHER": ("launchers", "LAUNCHER_REGISTERED", "record_bytes"),
            "ARM": ("arms", "SPAWN_ARMED", ""),
            "CHILD": ("children", "CHILD_REGISTERED", "registration_bytes"),
            "WAIT": ("waits", "EXIT_OBSERVED", "record_bytes"),
            "QUIESCENCE": ("quiescence", "QUIESCENCE_PROVEN", "proof_bytes"),
        }
        for kind, (table, event_kind, byte_column) in kinds.items():
            rows = db.execute("SELECT * FROM " + table).fetchall()
            need(
                {r["revision"] for r in rows}
                == {e.revision for e in events.values() if e.kind == event_kind}
            )
            for row in rows:
                e = events[row["revision"]]
                obj = (
                    record(kind, c.canonical_json({k: row[k] for k in ARM_FIELDS.split()}))
                    if kind == "ARM"
                    else record(kind, row[byte_column])
                )
                need(
                    record_matches_event(
                        kind, c.canonical_json(obj), e, row["child_id"] if kind == "CHILD" else None
                    )
                )
                facts = p.bounded_record(e.facts, s.FACT_FIELDS[e.kind])
                app = row["app_run_id"]
                need(e.app_run_id == app and obj["app_run_id"] == app)
                owner = owners[e.generation]
                if kind != "QUIESCENCE":
                    need(obj["generation"] == e.generation)
                if kind in ("LAUNCHER", "CHILD", "WAIT"):
                    need(
                        obj["installation_id"] == installation
                        and obj["boot_id"] == owner["boot_id"]
                    )
                need(
                    tuple(row)
                    == _columns(kind, obj, e.revision, row["child_id"] if kind == "CHILD" else None)
                )
                if kind == "LAUNCHER":
                    need(
                        obj["installation_lock_dev"] == owner["installation_lock_dev"]
                        and obj["installation_lock_ino"] == owner["installation_lock_ino"]
                    )
                    need(
                        facts
                        == {
                            "launcher_id": obj["launcher_id"],
                            "launcher_record_sha256": p.digest(kind, row[byte_column]),
                        }
                    )
                elif kind == "ARM":
                    need(
                        obj["deadline_boot_id"] == e.boot_id
                        and obj["arm_monotonic_ns"] == e.monotonic_ns
                    )
                    need(
                        facts
                        == {
                            k: obj[k]
                            for k in (
                                "permission_id",
                                "launcher_id",
                                "command_sha256",
                                "deadline_monotonic_ns",
                            )
                        }
                    )
                    need(obj["launcher_id"] == models[app].launcher_id)
                    need(
                        obj["command_sha256"]
                        == p.Expectations(runs[app]["expectation_bytes"]).values()[
                            "command_policy_sha256"
                        ]
                    )
                elif kind == "CHILD":
                    arm = db.execute("SELECT * FROM arms WHERE app_run_id=?", (app,)).fetchone()
                    need(
                        obj["permission_id"] == arm["permission_id"]
                        and obj["launcher_id"] == arm["launcher_id"]
                    )
                    need(obj["command_sha256"] == arm["command_sha256"])
                    need(
                        obj["observed_at"] == e.observed_at
                        and int(e.monotonic_ns) < int(arm["deadline_monotonic_ns"])
                    )
                    need(
                        facts
                        == {
                            "child_id": row["child_id"],
                            "child_record_sha256": p.digest(kind, row[byte_column]),
                        }
                    )
                elif kind == "WAIT":
                    child = db.execute(
                        "SELECT * FROM children WHERE app_run_id=?", (app,)
                    ).fetchone()
                    need(child is not None, "REGISTRATION_GAP")
                    arm = db.execute("SELECT * FROM arms WHERE app_run_id=?", (app,)).fetchone()
                    need(
                        obj["permission_id"] == arm["permission_id"]
                        and obj["launcher_id"] == child["launcher_id"]
                    )
                    need(
                        obj["child_record_sha256"] == p.digest("CHILD", child["registration_bytes"])
                    )
                    need(
                        obj["reaped_at"] == e.observed_at and obj["monotonic_ns"] == e.monotonic_ns
                    )
                    need(
                        facts
                        == {
                            "wait_record_sha256": p.digest(kind, row[byte_column]),
                            "result_kind": obj["wait_kind"],
                            "exit_code": obj["exit_code"],
                            "signal_number": obj["signal_number"],
                        }
                    )
                else:
                    wait = db.execute("SELECT * FROM waits WHERE app_run_id=?", (app,)).fetchone()
                    launcher = db.execute(
                        "SELECT * FROM launchers WHERE app_run_id=?", (app,)
                    ).fetchone()
                    need(wait is not None and models[app].child_known)
                    need(obj["wait_record_sha256"] == p.digest("WAIT", wait["record_bytes"]))
                    need(
                        obj["original_launcher_record_sha256"]
                        == p.digest("LAUNCHER", launcher["record_bytes"])
                    )
                    need(
                        obj["observed_boot_id"] == e.boot_id and obj["observed_at"] == e.observed_at
                    )
                    need(
                        obj["child_contract_sha256"]
                        == p.Expectations(runs[app]["expectation_bytes"]).values()[
                            "source_inventory_sha256"
                        ]
                    )
                    need(
                        facts
                        == {
                            "proof_sha256": p.digest(kind, row[byte_column]),
                            "basis": "ORIGINAL_WAIT_NOFORK_HELPER",
                        }
                    )
        failures = db.execute("SELECT * FROM first_failures").fetchall()
        need(
            {r["revision"] for r in failures}
            == {e.revision for e in events.values() if e.kind == "FIRST_FAILURE"}
        )
        for row in failures:
            e = events[row["revision"]]
            facts = p.bounded_record(e.facts, s.FACT_FIELDS[e.kind])
            need(
                tuple(row)
                == (
                    e.app_run_id,
                    facts["reason"],
                    facts["first_observed_at"],
                    facts["source_sha256"],
                    e.facts,
                    e.revision,
                )
            )
            need(
                runs[e.app_run_id]["accepted_at"]
                <= c.text(facts["first_observed_at"])
                <= e.observed_at
            )
        for e in events.values():
            if e.kind == "TERMINAL_HELD":
                facts = p.bounded_record(e.facts, s.FACT_FIELDS[e.kind])
                model = models[e.app_run_id]
                if facts["disposition"] in ("HELPER_EXIT_ZERO_HELD", "FAILED_KNOWN"):
                    need(model.quiescent)
                if facts["disposition"] == "HELPER_EXIT_ZERO_HELD":
                    need(
                        model.wait_outcome is not None
                        and model.wait_outcome.exit_code == 0
                        and model.first_failure is None
                    )
                if facts["disposition"] == "FAILED_KNOWN":
                    need(model.first_failure is not None)
