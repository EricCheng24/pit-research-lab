"""P1-03A TEST-ONLY SQLite intent ledger. Never a runner or public receipt.

Explicit open/init are the only I/O entry points. A reservation cannot be cleared
in A, including after a preparatory block. There is no transition to execution,
verification or release. SQL commit proves a SQLite transaction, not publication
or power-loss durability. The private test harness is trusted against same-uid
concurrent filesystem replacement; production dirfd/lease proof is deferred.
"""

import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Self, cast
from uuid import uuid4

from pit_research_lab.mvp.f6 import contracts as c

from .config import absolute_path
from .security import parse_submission

SCHEMA_VERSION = 1
APPLICATION_ID = 0x46364131
TEST_DB_CEILING = 32 * 1024 * 1024
TEST_BUSY_MILLISECONDS = 1000


class CatalogCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSAFE_TEST_LOCATION = "UNSAFE_TEST_LOCATION"
    SCHEMA_REFUSED = "SCHEMA_REFUSED"
    STORAGE_REFUSED = "STORAGE_REFUSED"
    BUSY = "BUSY"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    TRANSITION_REFUSED = "TRANSITION_REFUSED"


class CatalogError(ValueError):
    def __init__(self, code: CatalogCode) -> None:
        self.code = code
        super().__init__(code.value)


def _require(condition: bool, code: CatalogCode = CatalogCode.INVALID_INPUT) -> None:
    if not condition:
        raise CatalogError(code)


class PreparatoryFailure(StrEnum):
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    STORAGE_BLOCKED = "STORAGE_BLOCKED"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"


_TABLES = (
    """CREATE TABLE metadata (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        installation_id TEXT NOT NULL UNIQUE,
        schema_identity TEXT NOT NULL
    ) STRICT""",
    """CREATE TABLE intents (
        app_run_id TEXT PRIMARY KEY,
        allocation_id TEXT NOT NULL UNIQUE,
        operation TEXT NOT NULL CHECK(operation = 'TEST_FIXED_SUBMISSION'),
        idempotency_key TEXT NOT NULL,
        request_bytes BLOB NOT NULL CHECK(length(request_bytes) BETWEEN 1 AND 262144),
        fingerprint TEXT NOT NULL CHECK(length(fingerprint) = 64),
        expected_revision TEXT NOT NULL CHECK(length(expected_revision) = 64),
        expected_build TEXT NOT NULL CHECK(length(expected_build) = 64),
        accepted_at TEXT NOT NULL,
        initial_sequence INTEGER NOT NULL DEFAULT 1 CHECK(initial_sequence = 1),
        UNIQUE(operation, idempotency_key),
        FOREIGN KEY(app_run_id, initial_sequence) REFERENCES events(app_run_id, sequence)
            DEFERRABLE INITIALLY DEFERRED
    ) STRICT""",
    """CREATE TABLE active_slot (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        app_run_id TEXT NOT NULL UNIQUE REFERENCES intents(app_run_id)
    ) STRICT""",
    """CREATE TABLE events (
        app_run_id TEXT NOT NULL REFERENCES intents(app_run_id),
        sequence INTEGER NOT NULL CHECK(sequence IN (1, 2)),
        revision INTEGER NOT NULL UNIQUE CHECK(revision > 0),
        phase TEXT NOT NULL CHECK(phase IN ('INTENT_RECORDED', 'BLOCKED')),
        first_failure TEXT,
        PRIMARY KEY(app_run_id, sequence),
        CHECK((phase = 'INTENT_RECORDED' AND sequence = 1 AND first_failure IS NULL)
          OR (phase = 'BLOCKED' AND sequence = 2 AND first_failure IS NOT NULL
            AND first_failure IN ('SERVICE_NOT_READY', 'STORAGE_BLOCKED',
                                  'RECOVERY_BLOCKED', 'RESOURCE_LIMIT')))
    ) STRICT""",
)
_TRIGGERS = (
    """CREATE TRIGGER event_order BEFORE INSERT ON events BEGIN
        SELECT CASE WHEN NEW.revision != (SELECT COALESCE(MAX(revision), 0) + 1 FROM events)
          OR NEW.sequence != (SELECT COALESCE(MAX(sequence), 0) + 1 FROM events
                              WHERE app_run_id = NEW.app_run_id)
          OR NOT EXISTS(SELECT 1 FROM active_slot WHERE app_run_id = NEW.app_run_id)
          THEN RAISE(ABORT, 'CATALOG_INVARIANT') END;
    END""",
    *(
        f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} "
        f"WHEN EXISTS(SELECT 1 FROM {table}) "
        "BEGIN SELECT RAISE(ABORT, 'CATALOG_IMMUTABLE'); END"
        for table in ("metadata", "intents", "active_slot")
    ),
    *(
        f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
        "BEGIN SELECT RAISE(ABORT, 'CATALOG_IMMUTABLE'); END"
        for table in ("metadata", "intents", "active_slot", "events")
        for action in ("UPDATE", "DELETE")
    ),
)
_STATEMENTS = (*_TABLES, *_TRIGGERS)
SCHEMA_IDENTITY = sha256(c.canonical_json(list(_STATEMENTS))).hexdigest()


@dataclass(frozen=True, slots=True)
class TestLocation:
    """Explicit existing private Linux /tmp directory and simple catalog leaf.

    No discovery, mkdir, production path or default filename. Construction only
    checks lexical form. Filesystem ownership/type checks occur on explicit open.
    """

    root: Path
    filename: str

    def __post_init__(self) -> None:
        _require(isinstance(self.root, Path), CatalogCode.UNSAFE_TEST_LOCATION)
        try:
            absolute_path(str(self.root))
        except ValueError:
            raise CatalogError(CatalogCode.UNSAFE_TEST_LOCATION) from None
        _require(
            self.root.is_relative_to(Path("/tmp")) and self.root != Path("/tmp"),
            CatalogCode.UNSAFE_TEST_LOCATION,
        )
        _require(
            type(self.filename) is str
            and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}\.sqlite3", self.filename) is not None,
            CatalogCode.UNSAFE_TEST_LOCATION,
        )

    @property
    def path(self) -> Path:
        return self.root / self.filename


def _location(location: TestLocation, *, existing: bool) -> None:
    _require(type(location) is TestLocation, CatalogCode.UNSAFE_TEST_LOCATION)
    location.__post_init__()
    try:
        for part in (location.root, *location.root.parents):
            info = part.lstat()
            _require(stat.S_ISDIR(info.st_mode), CatalogCode.UNSAFE_TEST_LOCATION)
        root_info = location.root.lstat()
        _require(
            root_info.st_uid == os.getuid() and stat.S_IMODE(root_info.st_mode) == 0o700,
            CatalogCode.UNSAFE_TEST_LOCATION,
        )
        paths = (
            location.path,
            *(Path(str(location.path) + s) for s in ("-journal", "-wal", "-shm")),
        )
        for path in paths:
            if path == location.path and not existing:
                _require(not path.exists() and not path.is_symlink(), CatalogCode.STORAGE_REFUSED)
                continue
            try:
                info = path.lstat()
            except FileNotFoundError:
                _require(path != location.path, CatalogCode.STORAGE_REFUSED)
                continue
            _require(
                stat.S_ISREG(info.st_mode)
                and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1
                and info.st_size <= TEST_DB_CEILING,
                CatalogCode.UNSAFE_TEST_LOCATION,
            )
            # A never uses WAL. Existing sidecars are ambiguous, not repair inputs.
            _require(path == location.path, CatalogCode.STORAGE_REFUSED)
    except OSError:
        raise CatalogError(CatalogCode.STORAGE_REFUSED) from None


@dataclass(frozen=True, slots=True)
class SyntheticIntent:
    """Prevalidated synthetic operands, never production admission authority."""

    request_bytes: bytes
    fingerprint: str
    expected_revision: str
    expected_build: str
    accepted_at: str

    def __post_init__(self) -> None:
        try:
            request = parse_submission(self.request_bytes, self.expected_revision)
            _require(request.serialize() == self.request_bytes)
            _require(c.submission_fingerprint(request.to_wire()) == self.fingerprint)
            c.sha256_text(self.expected_build)
            c.timestamp(self.accepted_at)
        except c.ContractError:
            raise CatalogError(CatalogCode.INVALID_INPUT) from None


@dataclass(frozen=True, slots=True)
class CatalogIdentity:
    """Application-private TEST row identity, deliberately not an F6 receipt."""

    installation_id: str
    app_run_id: str
    allocation_id: str
    fingerprint: str
    accepted_at: str
    intent_revision: int


@dataclass(frozen=True, slots=True)
class Event:
    sequence: int
    revision: int
    phase: str
    first_failure: PreparatoryFailure | None


def _schema(connection: sqlite3.Connection) -> str:
    """Validate without modifying any persistent bytes, including unknown DBs."""
    _require(
        connection.execute("PRAGMA user_version").fetchone()[0] == 1, CatalogCode.SCHEMA_REFUSED
    )
    _require(
        connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID,
        CatalogCode.SCHEMA_REFUSED,
    )
    actual = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' ORDER BY sql"
    ).fetchall()
    _require([row[0] for row in actual] == sorted(_STATEMENTS), CatalogCode.SCHEMA_REFUSED)
    rows = connection.execute("SELECT installation_id, schema_identity FROM metadata").fetchall()
    _require(len(rows) == 1 and rows[0][1] == SCHEMA_IDENTITY, CatalogCode.SCHEMA_REFUSED)
    try:
        installation = c.uuid4_text(rows[0][0])
        for row in connection.execute(
            "SELECT app_run_id, allocation_id, idempotency_key, request_bytes, fingerprint, "
            "expected_revision, expected_build, accepted_at FROM intents"
        ):
            c.uuid4_text(row[0])
            c.uuid4_text(row[1])
            intent = SyntheticIntent(row[3], row[4], row[5], row[6], row[7])
            request = c.SubmissionRequest.parse(intent.request_bytes)
            _require(request.to_wire()["idempotency_key"] == row[2], CatalogCode.SCHEMA_REFUSED)
    except (c.ContractError, CatalogError):
        raise CatalogError(CatalogCode.SCHEMA_REFUSED) from None
    _require(
        connection.execute("PRAGMA quick_check").fetchall() == [("ok",)], CatalogCode.SCHEMA_REFUSED
    )
    _require(
        not connection.execute("PRAGMA foreign_key_check").fetchall(), CatalogCode.SCHEMA_REFUSED
    )
    # Ledger cardinality is especially small in A: one held slot, one intent,
    # and at most two events. Check state as well as schema on each transaction.
    count = connection.execute("SELECT COUNT(*) FROM intents").fetchone()[0]
    slots = connection.execute("SELECT COUNT(*) FROM active_slot").fetchone()[0]
    events = connection.execute(
        "SELECT sequence, revision FROM events ORDER BY revision"
    ).fetchall()
    _require(
        count == slots
        and count in (0, 1)
        and (events == [] if count == 0 else events in ([(1, 1)], [(1, 1), (2, 2)])),
        CatalogCode.SCHEMA_REFUSED,
    )
    return installation


class TestCatalog:
    """Inert constructor; explicit initialize/open_existing manage test SQLite."""

    def __init__(self, location: TestLocation) -> None:
        _require(type(location) is TestLocation, CatalogCode.UNSAFE_TEST_LOCATION)
        self.location = location
        self._connection: sqlite3.Connection | None = None

    def initialize(self, installation_id: str) -> Self:
        _require(self._connection is None)
        try:
            c.uuid4_text(installation_id)
        except c.ContractError:
            raise CatalogError(CatalogCode.INVALID_INPUT) from None
        _location(self.location, existing=False)
        try:
            fd = os.open(
                self.location.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            os.close(fd)
            connection = self._connect(readonly=False)
            try:
                self._pragmas(connection)
                connection.execute("BEGIN IMMEDIATE")
                for statement in _STATEMENTS:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO metadata VALUES (1, ?, ?)", (installation_id, SCHEMA_IDENTITY)
                )
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.commit()
                _schema(connection)
            except BaseException:
                connection.rollback()
                connection.close()
                raise
        except (sqlite3.Error, OSError):
            raise CatalogError(CatalogCode.STORAGE_REFUSED) from None
        self._connection = connection
        return self

    def open_existing(self) -> Self:
        _require(self._connection is None)
        _location(self.location, existing=True)
        try:
            check = self._connect(readonly=True)
            try:
                _schema(check)
            finally:
                check.close()
            connection = self._connect(readonly=False)
            try:
                _schema(connection)
                self._pragmas(connection)
            except BaseException:
                connection.close()
                raise
        except sqlite3.Error:
            raise CatalogError(CatalogCode.SCHEMA_REFUSED) from None
        self._connection = connection
        return self

    def _connect(self, *, readonly: bool) -> sqlite3.Connection:
        return sqlite3.connect(
            self.location.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
            uri=True,
            timeout=TEST_BUSY_MILLISECONDS / 1000,
            isolation_level=None,
        )

    @staticmethod
    def _pragmas(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        _require(
            connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete",
            CatalogCode.SCHEMA_REFUSED,
        )
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(f"PRAGMA busy_timeout={TEST_BUSY_MILLISECONDS}")

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _db(self) -> sqlite3.Connection:
        _require(self._connection is not None, CatalogCode.STORAGE_REFUSED)
        assert self._connection is not None
        return self._connection

    def _before_commit(self) -> None:
        """Inert transaction seam; tests may subclass to inject an exception only."""

    def reserve_synthetic(self, intent: SyntheticIntent) -> CatalogIdentity:
        _require(type(intent) is SyntheticIntent)
        # Revalidate *before* even consulting an existing idempotency key.
        intent.__post_init__()
        request = c.SubmissionRequest.parse(intent.request_bytes).to_wire()
        key = cast(str, request["idempotency_key"])
        connection = self._db()
        try:
            connection.execute("BEGIN IMMEDIATE")
            installation = _schema(connection)
            row = connection.execute(
                "SELECT app_run_id, allocation_id, fingerprint, accepted_at FROM intents "
                "WHERE operation = 'TEST_FIXED_SUBMISSION' AND idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is not None:
                _require(row[2] == intent.fingerprint, CatalogCode.IDEMPOTENCY_CONFLICT)
                identity = CatalogIdentity(installation, row[0], row[1], row[2], row[3], 1)
            else:
                _require(
                    connection.execute("SELECT COUNT(*) FROM active_slot").fetchone()[0] == 0,
                    CatalogCode.BUSY,
                )
                app_id, allocation_id = str(uuid4()), str(uuid4())
                connection.execute(
                    "INSERT INTO intents VALUES (?, ?, 'TEST_FIXED_SUBMISSION', ?, ?, ?, ?, ?, ?, 1)",
                    (
                        app_id,
                        allocation_id,
                        key,
                        intent.request_bytes,
                        intent.fingerprint,
                        intent.expected_revision,
                        intent.expected_build,
                        intent.accepted_at,
                    ),
                )
                connection.execute("INSERT INTO active_slot VALUES (1, ?)", (app_id,))
                connection.execute(
                    "INSERT INTO events VALUES (?, 1, 1, 'INTENT_RECORDED', NULL)", (app_id,)
                )
                identity = CatalogIdentity(
                    installation, app_id, allocation_id, intent.fingerprint, intent.accepted_at, 1
                )
            self._before_commit()
            connection.commit()
            return identity
        except sqlite3.OperationalError as error:
            connection.rollback()
            code = (
                CatalogCode.BUSY
                if error.sqlite_errorcode in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                else CatalogCode.STORAGE_REFUSED
            )
            raise CatalogError(code) from None
        except sqlite3.Error:
            connection.rollback()
            raise CatalogError(CatalogCode.STORAGE_REFUSED) from None
        except BaseException:
            connection.rollback()
            raise

    def record_block(self, app_run_id: str, reason: PreparatoryFailure) -> None:
        try:
            c.uuid4_text(app_run_id)
        except c.ContractError:
            raise CatalogError(CatalogCode.INVALID_INPUT) from None
        _require(type(reason) is PreparatoryFailure, CatalogCode.TRANSITION_REFUSED)
        connection = self._db()
        try:
            connection.execute("BEGIN IMMEDIATE")
            _schema(connection)
            previous = connection.execute(
                "SELECT phase, first_failure FROM events WHERE app_run_id=? ORDER BY sequence DESC",
                (app_run_id,),
            ).fetchone()
            _require(
                previous is not None and previous[0] == "INTENT_RECORDED",
                CatalogCode.TRANSITION_REFUSED,
            )
            connection.execute(
                "INSERT INTO events VALUES (?, 2, 2, 'BLOCKED', ?)", (app_run_id, reason.value)
            )
            self._before_commit()
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise CatalogError(CatalogCode.STORAGE_REFUSED) from None
        except BaseException:
            connection.rollback()
            raise

    def events(self, app_run_id: str) -> tuple[Event, ...]:
        try:
            c.uuid4_text(app_run_id)
            connection = self._db()
            _schema(connection)
            rows = connection.execute(
                "SELECT sequence, revision, phase, first_failure FROM events "
                "WHERE app_run_id=? ORDER BY sequence",
                (app_run_id,),
            ).fetchall()
        except (c.ContractError, sqlite3.Error):
            raise CatalogError(CatalogCode.STORAGE_REFUSED) from None
        return tuple(
            Event(row[0], row[1], row[2], None if row[3] is None else PreparatoryFailure(row[3]))
            for row in rows
        )
