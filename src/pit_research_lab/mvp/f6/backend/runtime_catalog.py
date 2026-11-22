"""B-CORE E1 synthetic test ledger, NOT an operational runtime catalog.

Only explicit test-owned SQLite operations perform I/O. No A catalog adoption,
launcher/arm/child/slot-release operation or public response constructor exists.
Unknown future-phase rows refuse; no migration or repair is attempted.
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
from typing import Self, TypeVar, cast
from uuid import uuid4

from pit_research_lab.mvp.f6 import contracts as c

from . import launch_policy as p
from . import supervisor as s
from .process_identity import boot_text, process_number

SCHEMA_VERSION = 1
APPLICATION_ID = 0x46364231
DB_CEILING = 32 * 1024 * 1024
BUSY_MILLISECONDS = 250
PURPOSE = "TEST_HELPER_ONLY"
# Verbatim reviewed E1 DDL; PRAGMA identities are installed separately.
_SCHEMA_SQL = """CREATE TABLE installation (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 installation_id TEXT NOT NULL UNIQUE,
 purpose TEXT NOT NULL CHECK(purpose IN ('TEST_HELPER_ONLY','RUNTIME_DORMANT')),
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 ddl_sha256 TEXT NOT NULL CHECK(length(ddl_sha256)=64),
 authority_sha256 TEXT NOT NULL CHECK(length(authority_sha256)=64),
 root_dev TEXT NOT NULL, root_ino TEXT NOT NULL, created_at TEXT NOT NULL
) STRICT;
CREATE TABLE owners (
 generation TEXT PRIMARY KEY,
 generation_number INTEGER NOT NULL UNIQUE CHECK(generation_number>0),
 installation_id TEXT NOT NULL REFERENCES installation(installation_id),
 boot_id TEXT NOT NULL, pid INTEGER NOT NULL CHECK(pid>1),
 start_ticks TEXT NOT NULL, pgid INTEGER NOT NULL CHECK(pgid>1), sid INTEGER NOT NULL,
 install_dev TEXT NOT NULL, install_ino TEXT NOT NULL,
 runtime_sha256 TEXT NOT NULL CHECK(length(runtime_sha256)=64),
 registration_bytes BLOB NOT NULL CHECK(length(registration_bytes) BETWEEN 1 AND 16384)
) STRICT;
CREATE TABLE runs (
 app_run_id TEXT PRIMARY KEY,
 installation_id TEXT NOT NULL REFERENCES installation(installation_id),
 operation TEXT NOT NULL CHECK(operation='FIXED_SUBMISSION'),
 idempotency_key TEXT NOT NULL,
 request_bytes BLOB NOT NULL CHECK(length(request_bytes) BETWEEN 1 AND 262144),
 fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64),
 allocation_id TEXT NOT NULL UNIQUE,
 accepted_at TEXT NOT NULL,
 admission_bytes BLOB NOT NULL CHECK(length(admission_bytes) BETWEEN 1 AND 16384),
 admission_sha256 TEXT NOT NULL CHECK(length(admission_sha256)=64),
 expectation_bytes BLOB NOT NULL CHECK(length(expectation_bytes) BETWEEN 1 AND 65536),
 expectation_sha256 TEXT NOT NULL CHECK(length(expectation_sha256)=64),
 intent_sequence INTEGER NOT NULL DEFAULT 1 CHECK(intent_sequence=1),
 UNIQUE(installation_id,operation,idempotency_key),
 FOREIGN KEY(app_run_id,intent_sequence) REFERENCES events(app_run_id,run_sequence)
   DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE events (
 revision INTEGER PRIMARY KEY CHECK(revision>0),
 app_run_id TEXT NOT NULL REFERENCES runs(app_run_id),
 run_sequence INTEGER NOT NULL CHECK(run_sequence>0),
 expected_previous_revision INTEGER NOT NULL CHECK(expected_previous_revision>=0),
 kind TEXT NOT NULL CHECK(kind IN (
  'INTENT_COMMITTED','LAUNCHER_REGISTERED','SPAWN_ARMED','CHILD_REGISTERED',
  'SPAWN_ERROR','EXIT_OBSERVED','FIRST_FAILURE','SECONDARY_FAILURE',
  'RECONCILING','QUARANTINED','QUIESCENCE_PROVEN','TERMINAL_HELD','SLOT_DISPOSED')),
 state TEXT NOT NULL CHECK(state IN (
  'INTENT_HELD','OWNER_READY','ARM_CONSUMED','CHILD_KNOWN','EXIT_HELD',
  'RECONCILING','QUARANTINED','TERMINAL_HELD','DISPOSED')),
 actor TEXT NOT NULL CHECK(actor IN ('ADMISSION','SUPERVISOR','LAUNCHER','RECOVERY')),
 generation TEXT NOT NULL REFERENCES owners(generation),
 observed_at TEXT NOT NULL, boot_id TEXT NOT NULL, monotonic_ns TEXT NOT NULL,
 facts_version INTEGER NOT NULL CHECK(facts_version=1),
 facts BLOB NOT NULL CHECK(length(facts) BETWEEN 1 AND 16384),
 previous_sha256 TEXT NOT NULL CHECK(length(previous_sha256)=64),
 event_sha256 TEXT NOT NULL UNIQUE CHECK(length(event_sha256)=64),
 UNIQUE(app_run_id,run_sequence)
) STRICT;
CREATE TABLE launchers (
 app_run_id TEXT PRIMARY KEY REFERENCES runs(app_run_id),
 launcher_id TEXT NOT NULL UNIQUE,
 generation TEXT NOT NULL REFERENCES owners(generation),
 boot_id TEXT NOT NULL, pid INTEGER NOT NULL CHECK(pid>1), start_ticks TEXT NOT NULL,
 pgid INTEGER NOT NULL CHECK(pgid>1), sid INTEGER NOT NULL,
 job_dev TEXT NOT NULL, job_ino TEXT NOT NULL,
 nonce_sha256 TEXT NOT NULL CHECK(length(nonce_sha256)=64),
 record_bytes BLOB NOT NULL CHECK(length(record_bytes) BETWEEN 1 AND 16384),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE arms (
 app_run_id TEXT PRIMARY KEY REFERENCES launchers(app_run_id),
 permission_id TEXT NOT NULL UNIQUE,
 launcher_id TEXT NOT NULL UNIQUE REFERENCES launchers(launcher_id),
 generation TEXT NOT NULL REFERENCES owners(generation),
 command_sha256 TEXT NOT NULL CHECK(length(command_sha256)=64),
 deadline_boot_id TEXT NOT NULL, arm_monotonic_ns TEXT NOT NULL,
 deadline_monotonic_ns TEXT NOT NULL,
 consumed INTEGER NOT NULL CHECK(consumed=1),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE children (
 app_run_id TEXT PRIMARY KEY REFERENCES arms(app_run_id),
 child_id TEXT NOT NULL UNIQUE,
 launcher_id TEXT NOT NULL UNIQUE REFERENCES launchers(launcher_id),
 boot_id TEXT NOT NULL, pid INTEGER NOT NULL CHECK(pid>1), start_ticks TEXT NOT NULL,
 pgid INTEGER NOT NULL CHECK(pgid>1), sid INTEGER NOT NULL,
 nonce_sha256 TEXT NOT NULL CHECK(length(nonce_sha256)=64),
 executable_sha256 TEXT NOT NULL CHECK(length(executable_sha256)=64),
 registration_bytes BLOB NOT NULL CHECK(length(registration_bytes) BETWEEN 1 AND 16384),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE waits (
 app_run_id TEXT PRIMARY KEY REFERENCES arms(app_run_id),
 launcher_id TEXT NOT NULL UNIQUE REFERENCES launchers(launcher_id),
 child_record_sha256 TEXT NOT NULL CHECK(length(child_record_sha256)=64),
 result_kind TEXT NOT NULL CHECK(result_kind IN ('EXIT','SIGNAL')),
 exit_code INTEGER, signal_number INTEGER,
 reaped INTEGER NOT NULL CHECK(reaped=1),
 record_bytes BLOB NOT NULL CHECK(length(record_bytes) BETWEEN 1 AND 16384),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED,
 CHECK((result_kind='EXIT' AND exit_code IS NOT NULL
        AND exit_code BETWEEN 0 AND 255 AND signal_number IS NULL)
    OR (result_kind='SIGNAL' AND exit_code IS NULL AND signal_number IS NOT NULL
        AND signal_number BETWEEN 1 AND 64))
) STRICT;
CREATE TABLE first_failures (
 app_run_id TEXT PRIMARY KEY REFERENCES runs(app_run_id),
 reason TEXT NOT NULL CHECK(reason IN ('LAUNCH_INTERRUPTED','CHILD_TIMEOUT',
  'CHILD_NONZERO_EXIT','SUPERVISOR_LOST','EXECUTION_OUTCOME_UNKNOWN',
  'RECOVERY_BLOCKED','STORAGE_BLOCKED','RESOURCE_LIMIT','SERVICE_NOT_READY')),
 first_observed_at TEXT NOT NULL,
 source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
 failure_bytes BLOB NOT NULL CHECK(length(failure_bytes) BETWEEN 1 AND 4096),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE quiescence (
 app_run_id TEXT PRIMARY KEY REFERENCES runs(app_run_id),
 basis TEXT NOT NULL CHECK(basis IN (
  'ORIGINAL_WAIT_NOFORK_HELPER','PREARM_ORIGINAL_OWNER_CLOSED','COLD_OWNER_ADJUDICATION')),
 proof_bytes BLOB NOT NULL CHECK(length(proof_bytes) BETWEEN 1 AND 16384),
 proof_sha256 TEXT NOT NULL CHECK(length(proof_sha256)=64),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE slot_log (
 slot_sequence INTEGER PRIMARY KEY CHECK(slot_sequence>0),
 app_run_id TEXT NOT NULL REFERENCES runs(app_run_id),
 action TEXT NOT NULL CHECK(action IN ('RESERVE','DISPOSE')),
 revision INTEGER NOT NULL UNIQUE REFERENCES events(revision) DEFERRABLE INITIALLY DEFERRED,
 UNIQUE(app_run_id,action)
) STRICT;
CREATE VIEW current_slot AS
 SELECT app_run_id FROM slot_log
 WHERE slot_sequence=(SELECT MAX(slot_sequence) FROM slot_log) AND action='RESERVE';
CREATE VIEW current_run_state AS
 SELECT e.* FROM events e WHERE run_sequence=(
  SELECT MAX(p.run_sequence) FROM events p WHERE p.app_run_id=e.app_run_id);
CREATE TRIGGER event_order BEFORE INSERT ON events BEGIN
 SELECT CASE WHEN NEW.revision != (SELECT COALESCE(MAX(revision),0)+1 FROM events)
  OR NEW.expected_previous_revision != (SELECT COALESCE(MAX(revision),0) FROM events)
  OR NEW.run_sequence != (SELECT COALESCE(MAX(run_sequence),0)+1 FROM events
                            WHERE app_run_id=NEW.app_run_id)
  THEN RAISE(ABORT,'STALE_EVENT') END;
END;
CREATE TRIGGER slot_order BEFORE INSERT ON slot_log BEGIN
 SELECT CASE WHEN NEW.slot_sequence != (SELECT COALESCE(MAX(slot_sequence),0)+1 FROM slot_log)
  OR (NEW.action='RESERVE' AND EXISTS(SELECT 1 FROM current_slot))
  OR (NEW.action='DISPOSE' AND NOT EXISTS(
      SELECT 1 FROM current_slot WHERE app_run_id=NEW.app_run_id))
  OR (NEW.action='DISPOSE' AND NOT EXISTS(
      SELECT 1 FROM quiescence WHERE app_run_id=NEW.app_run_id))
  OR (NEW.action='DISPOSE' AND NOT EXISTS(
      SELECT 1 FROM events WHERE app_run_id=NEW.app_run_id AND kind='TERMINAL_HELD'))
  THEN RAISE(ABORT,'SLOT_REFUSED') END;
END;
CREATE TRIGGER arm_owner BEFORE INSERT ON arms BEGIN
 SELECT CASE WHEN NOT EXISTS(
   SELECT 1 FROM launchers l JOIN current_slot s ON s.app_run_id=l.app_run_id
   WHERE l.app_run_id=NEW.app_run_id AND l.launcher_id=NEW.launcher_id
     AND l.generation=NEW.generation)
  OR EXISTS(SELECT 1 FROM first_failures WHERE app_run_id=NEW.app_run_id)
  OR NOT EXISTS(SELECT 1 FROM current_run_state
                WHERE app_run_id=NEW.app_run_id AND state='OWNER_READY')
  THEN RAISE(ABORT,'ARM_REFUSED') END;
END;
"""


def _statements(sql: str) -> tuple[str, ...]:
    result: list[str] = []
    current = ""
    for line in sql.splitlines(keepends=True):
        current += line
        if sqlite3.complete_statement(current):
            result.append(current.strip().removesuffix(";"))
            current = ""
    p.require(not current.strip())
    return tuple(result)


TABLE_KEYS = (
    ("installation", "singleton"),
    ("owners", "generation"),
    ("runs", "app_run_id"),
    ("events", "revision"),
    ("launchers", "app_run_id"),
    ("arms", "app_run_id"),
    ("children", "app_run_id"),
    ("waits", "app_run_id"),
    ("first_failures", "app_run_id"),
    ("quiescence", "app_run_id"),
    ("slot_log", "slot_sequence"),
)
_IMMUTABLE = tuple(
    f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
    "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_B_FACT'); END"
    for table, _ in TABLE_KEYS
    for action in ("UPDATE", "DELETE")
) + tuple(
    f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} "
    f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {key}=NEW.{key}) "
    "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_B_FACT'); END"
    for table, key in TABLE_KEYS
)
STATEMENTS = _statements(_SCHEMA_SQL) + _IMMUTABLE
SCHEMA_IDENTITY = sha256(c.canonical_json(list(STATEMENTS))).hexdigest()
OWNER_FIELDS = (
    "version record_kind installation_id generation generation_number boot_id pid start_ticks pgid sid "
    "installation_lock_dev installation_lock_ino runtime_sha256 authority_record_sha256 observed_at "
    "monotonic_ns previous_registration_sha256 closure_basis closure_evidence_sha256"
)
ADMISSION_FIELDS = (
    "version purpose authority_record_sha256 operation request_sha256 capability_revision "
    "build_sha256 policy_sha256 runtime_sha256"
)
CORE_KINDS = frozenset(("INTENT_COMMITTED", "FIRST_FAILURE", "QUARANTINED", "SECONDARY_FAILURE"))
T = TypeVar("T")


class CatalogError(p.ModelError):
    def __init__(self, code: str = "SCHEMA_REFUSED") -> None:
        p.require(
            code
            in (
                "SCHEMA_REFUSED",
                "STORAGE_BLOCKED",
                "BUSY",
                "INVALID_MODEL",
                "COMMIT_UNKNOWN",
                "TRANSITION_REFUSED",
                "IDEMPOTENCY_CONFLICT",
            )
        )
        super().__init__(code)


def _need(condition: bool, code: str = "SCHEMA_REFUSED") -> None:
    if not condition:
        raise CatalogError(code)


@dataclass(frozen=True, slots=True)
class SyntheticOwner:
    """Explicit TEST_ONLY operands, never an issued OS/deployment attestation."""

    raw: bytes

    def values(self) -> c.WireObject:
        return p.bounded_record(self.raw, OWNER_FIELDS)

    def __post_init__(self) -> None:
        obj = self.values()
        try:
            p.require(type(obj["version"]) is int and obj["version"] == 1)
            p.require(obj["record_kind"] == "OWNER_REGISTRATION")
            for key in ("installation_id", "generation"):
                c.uuid4_text(obj[key])
            p.require(obj["installation_id"] != obj["generation"])
            s.counter(obj["generation_number"])
            boot_text(obj["boot_id"])
            for key in ("pid", "pgid", "sid"):
                process_number(obj[key])
            for key in ("start_ticks", "installation_lock_ino"):
                p.decimal_text(obj[key], positive=True)
            for key in ("installation_lock_dev", "monotonic_ns"):
                p.decimal_text(obj[key])
            for key in ("runtime_sha256", "authority_record_sha256", "closure_evidence_sha256"):
                c.sha256_text(obj[key])
            p.require(obj["closure_evidence_sha256"] != s.ZERO_HASH)
            c.timestamp(obj["observed_at"])
            if obj["generation_number"] == 1:
                p.require(
                    obj["closure_basis"] == "INITIAL_EMPTY_INSTALLATION"
                    and obj["previous_registration_sha256"] is None
                )
            else:
                c.sha256_text(obj["previous_registration_sha256"])
                p.require(
                    obj["closure_basis"]
                    in ("ORIGINAL_INSTALLATION_AUTHORITY_CLOSED", "COLD_BOOT_OWNER_ADJUDICATED")
                )
        except c.ContractError:
            raise p.ModelError() from None


@dataclass(frozen=True, slots=True)
class SyntheticIntent:
    request_bytes: bytes
    admission_bytes: bytes
    expectations: p.Expectations
    accepted_at: str
    monotonic_ns: str

    def __post_init__(self) -> None:
        try:
            p.bounded_record(
                self.request_bytes,
                "schema_version kind capability_id capability_revision data_mode idempotency_key",
                262144,
            )
            request = c.SubmissionRequest.parse(self.request_bytes).to_wire()
            admission = p.bounded_record(self.admission_bytes, ADMISSION_FIELDS)
            p.require(type(admission["version"]) is int and admission["version"] == 1)
            p.require(
                admission["purpose"] == PURPOSE and admission["operation"] == "FIXED_SUBMISSION"
            )
            for key in ADMISSION_FIELDS.split()[2:]:
                if key != "operation":
                    c.sha256_text(admission[key])
            p.require(admission["request_sha256"] == sha256(self.request_bytes).hexdigest())
            p.require(admission["capability_revision"] == request["capability_revision"])
            p.require(type(self.expectations) is p.Expectations)
            self.expectations.__post_init__()
            c.timestamp(self.accepted_at)
            p.decimal_text(self.monotonic_ns)
        except c.ContractError:
            raise p.ModelError() from None


@dataclass(frozen=True, slots=True)
class SyntheticOwnerAck:
    """Unserializable test-session commit witness, NEVER a launch credential."""

    generation: str
    owner_sha256: str
    _issuer: object = field(repr=False, compare=False)

    def live_refusal(self) -> p.Refusal:
        return p.Refusal.B_CORE_AUTHORITY_ABSENT


@dataclass(frozen=True, slots=True)
class PrivateIdentity:
    installation_id: str
    app_run_id: str
    allocation_id: str
    fingerprint: str
    accepted_at: str
    original_generation: str
    intent_revision: int
    admission_bytes: bytes
    expectation_bytes: bytes


@dataclass(frozen=True, slots=True)
class TestAudit:
    installation_id: str
    owner_count: int
    run_count: int
    event_count: int
    revision: int
    active_app: str | None


@dataclass(frozen=True, slots=True)
class TestLocation:
    """Existing private directory in the specifically approved B-CORE /tmp tree."""

    root: Path
    filename: str

    def __post_init__(self) -> None:
        p.require(isinstance(self.root, Path))
        p.path_form(str(self.root))
        p.require(
            self.root.is_relative_to("/tmp")
            and any(
                re.fullmatch(r"pit-p103b-bcore\.[0-9]+\.[A-Za-z0-9]+", part) is not None
                for part in self.root.parts[2:]
            )
        )
        p.require(
            type(self.filename) is str
            and re.fullmatch(r"[a-z][a-z0-9_-]{0,40}\.sqlite3", self.filename) is not None
        )

    @property
    def path(self) -> Path:
        return self.root / self.filename


def _location(location: TestLocation, *, existing: bool) -> None:
    _need(type(location) is TestLocation, "INVALID_MODEL")
    location.__post_init__()
    try:
        for parent in (location.root, *location.root.parents):
            _need(stat.S_ISDIR(parent.lstat().st_mode), "STORAGE_BLOCKED")
        info = location.root.lstat()
        _need(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, "STORAGE_BLOCKED")
        for suffix in ("-journal", "-wal", "-shm"):
            _need(not os.path.lexists(str(location.path) + suffix), "STORAGE_BLOCKED")
        if existing:
            info = location.path.lstat()
            _need(
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_size <= DB_CEILING,
                "STORAGE_BLOCKED",
            )
        else:
            _need(not os.path.lexists(location.path), "STORAGE_BLOCKED")
    except OSError:
        raise CatalogError("STORAGE_BLOCKED") from None


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


def _event_from_row(row: sqlite3.Row) -> s.ModeledEvent:
    _need(row["facts_version"] == 1)
    return s.ModeledEvent(
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


class SyntheticCatalog:
    """Independent B data model. Constructor inert; all I/O explicitly TEST_ONLY.

    B-CORE supports intents and preparatory modeled blocks, and refuses any
    future process/quiescence/disposition data on audit. No live arm/Tx2 API.
    """

    def __init__(self, location: TestLocation) -> None:
        _need(type(location) is TestLocation, "INVALID_MODEL")
        self.location = location
        self._connection: sqlite3.Connection | None = None
        self._issuer = object()
        self._acknowledged: set[tuple[str, str]] = set()
        self._uncertain = False

    def _db(self) -> sqlite3.Connection:
        _need(self._connection is not None, "STORAGE_BLOCKED")
        assert self._connection is not None
        return self._connection

    def _connect(self, *, readonly: bool) -> sqlite3.Connection:
        db = sqlite3.connect(
            self.location.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
            uri=True,
            timeout=BUSY_MILLISECONDS / 1000,
            isolation_level=None,
        )
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA defer_foreign_keys=OFF")
            db.execute("PRAGMA recursive_triggers=ON")
            db.execute("PRAGMA synchronous=EXTRA")
            db.execute(f"PRAGMA busy_timeout={BUSY_MILLISECONDS}")
            if not readonly:
                page = db.execute("PRAGMA page_size").fetchone()[0]
                db.execute(f"PRAGMA max_page_count={DB_CEILING // page}")
            self._pragmas(db)
        except BaseException:
            db.close()
            raise
        return db

    @staticmethod
    def _pragmas(db: sqlite3.Connection) -> None:
        for name, expected in (
            ("foreign_keys", 1),
            ("defer_foreign_keys", 0),
            ("recursive_triggers", 1),
            ("synchronous", 3),
            ("journal_mode", "delete"),
            ("busy_timeout", BUSY_MILLISECONDS),
        ):
            _need(db.execute("PRAGMA " + name).fetchone()[0] == expected)

    def initialize(self, installation_id: str, authority_sha256: str, created_at: str) -> Self:
        _need(self._connection is None, "STORAGE_BLOCKED")
        c.uuid4_text(installation_id)
        c.sha256_text(authority_sha256)
        c.timestamp(created_at)
        _location(self.location, existing=False)
        try:
            fd = os.open(
                self.location.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            os.close(fd)
            db = self._connect(readonly=False)
            try:
                db.execute("BEGIN IMMEDIATE")
                for statement in STATEMENTS:
                    db.execute(statement)
                info = self.location.root.lstat()
                db.execute(
                    "INSERT INTO installation VALUES(1,?, ?,1,?,?,?,?,?)",
                    (
                        installation_id,
                        PURPOSE,
                        SCHEMA_IDENTITY,
                        authority_sha256,
                        str(info.st_dev),
                        str(info.st_ino),
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
        except (sqlite3.Error, OSError):
            raise CatalogError("STORAGE_BLOCKED") from None
        self._connection = db
        return self

    def open_existing(self) -> Self:
        _need(self._connection is None, "STORAGE_BLOCKED")
        _location(self.location, existing=True)
        try:
            check = self._connect(readonly=True)
            try:
                check.execute("BEGIN")
                self._audit(check)
            finally:
                check.rollback()
                check.close()
            db = self._connect(readonly=False)
            try:
                db.execute("BEGIN")
                self._audit(db)
                db.rollback()
            except BaseException:
                db.close()
                raise
        except (sqlite3.Error, OSError):
            raise CatalogError() from None
        self._connection = db
        return self

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        self._acknowledged.clear()

    def _audit(self, db: sqlite3.Connection) -> TestAudit:
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
            raise CatalogError() from None

    def _audit_records(self, db: sqlite3.Connection) -> TestAudit:
        self._pragmas(db)
        _need(db.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID)
        _need(db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION)
        actual = [
            r[0]
            for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY sql")
        ]
        _need(actual == sorted(STATEMENTS))
        _need([r[0] for r in db.execute("PRAGMA quick_check")] == ["ok"])
        _need(not db.execute("PRAGMA foreign_key_check").fetchall())
        rows = db.execute("SELECT * FROM installation").fetchall()
        _need(len(rows) == 1)
        install = rows[0]
        installation = c.uuid4_text(install["installation_id"])
        _need(
            install["singleton"] == 1
            and install["purpose"] == PURPOSE
            and install["schema_version"] == SCHEMA_VERSION
        )
        _need(install["ddl_sha256"] == SCHEMA_IDENTITY)
        c.sha256_text(install["authority_sha256"])
        c.timestamp(install["created_at"])
        root_info = self.location.root.lstat()
        _need(
            install["root_dev"] == str(root_info.st_dev)
            and install["root_ino"] == str(root_info.st_ino)
        )
        for table, limit in (
            ("owners", 4),
            ("runs", 4),
            ("events", 128),
            ("first_failures", 4),
            ("slot_log", 8),
        ):
            _need(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] <= limit)
        # Future E1 constraints exist, but no live/future-phase row is accepted in B-CORE.
        for table in ("launchers", "arms", "children", "waits", "quiescence"):
            _need(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0)
        owners: dict[str, c.WireObject] = {}
        predecessor: str | None = None
        for number, row in enumerate(
            db.execute("SELECT * FROM owners ORDER BY generation_number"), 1
        ):
            owner_record = SyntheticOwner(row["registration_bytes"])
            obj = owner_record.values()
            _need(tuple(row) == _owner_columns(obj, owner_record.raw))
            _need(obj["installation_id"] == installation and obj["generation_number"] == number)
            _need(obj["previous_registration_sha256"] == predecessor)
            _need(obj["authority_record_sha256"] == install["authority_sha256"])
            _need(
                datetime.fromisoformat(c.text(obj["observed_at"]))
                >= datetime.fromisoformat(install["created_at"])
            )
            owners[c.text(obj["generation"])] = obj
            predecessor = p.digest("OWNER", owner_record.raw)
        runs: dict[str, sqlite3.Row] = {}
        for row in db.execute("SELECT * FROM runs"):
            app, allocation = c.uuid4_text(row["app_run_id"]), c.uuid4_text(row["allocation_id"])
            expectation = p.Expectations(row["expectation_bytes"])
            candidate = SyntheticIntent(
                row["request_bytes"], row["admission_bytes"], expectation, row["accepted_at"], "0"
            )
            request = c.SubmissionRequest.parse(candidate.request_bytes).to_wire()
            _need(
                row["installation_id"] == installation
                and row["operation"] == "FIXED_SUBMISSION"
                and row["intent_sequence"] == 1
            )
            _need(row["idempotency_key"] == request["idempotency_key"])
            _need(row["fingerprint"] == c.submission_fingerprint(request))
            _need(row["admission_sha256"] == p.digest("INTENT", candidate.admission_bytes))
            _need(row["expectation_sha256"] == p.digest("EXPECTATION", expectation.raw))
            _need(
                expectation.values()["installation_id"] == installation
                and expectation.values()["allocation_id"] == allocation
            )
            _need(
                len({app, allocation, installation, row["idempotency_key"]}) == 4
                and app not in owners
                and allocation not in owners
            )
            runs[app] = row
        models: dict[str, s.RunModel] = {}
        firsts: dict[str, tuple[s.Failure, int, bytes]] = {}
        previous_revision, previous_hash = 0, s.ZERO_HASH
        previous_time = datetime.fromisoformat(install["created_at"])
        for row in db.execute("SELECT * FROM events ORDER BY revision"):
            event = _event_from_row(row)
            _need(event.kind in CORE_KINDS and event.event_sha256 == row["event_sha256"])
            _need(event.app_run_id in runs and event.generation in owners)
            owner = owners[event.generation]
            _need(
                event.boot_id == owner["boot_id"]
                and int(event.monotonic_ns) >= int(c.text(owner["monotonic_ns"]))
            )
            observed = datetime.fromisoformat(event.observed_at)
            _need(
                observed >= previous_time
                and observed >= datetime.fromisoformat(c.text(owner["observed_at"]))
            )
            run = runs[event.app_run_id]
            _need(observed >= datetime.fromisoformat(run["accepted_at"]))
            if event.app_run_id not in models:
                _need(event.kind == "INTENT_COMMITTED" and event.observed_at == run["accepted_at"])
                _need(
                    event.facts
                    == c.canonical_json(
                        {
                            "admission_sha256": run["admission_sha256"],
                            "expectation_sha256": run["expectation_sha256"],
                            "fingerprint": run["fingerprint"],
                            "allocation_id": run["allocation_id"],
                        }
                    )
                )
                admission = p.bounded_record(run["admission_bytes"], ADMISSION_FIELDS)
                _need(
                    admission["authority_record_sha256"] == owner["authority_record_sha256"]
                    and admission["runtime_sha256"] == owner["runtime_sha256"]
                )
                models[event.app_run_id] = s.RunModel(
                    installation, event.app_run_id, event.generation
                )
            model = s.reduce_model(
                models[event.app_run_id],
                event,
                previous_revision=previous_revision,
                previous_sha256=previous_hash,
                registered_generations=tuple(owners),
            )
            models[event.app_run_id] = model
            if event.kind == "FIRST_FAILURE":
                assert model.first_failure is not None
                _need(datetime.fromisoformat(model.first_failure.first_observed_at) <= observed)
                _need(
                    datetime.fromisoformat(model.first_failure.first_observed_at)
                    >= datetime.fromisoformat(run["accepted_at"])
                )
                firsts[event.app_run_id] = (model.first_failure, event.revision, event.facts)
            previous_revision, previous_hash, previous_time = (
                event.revision,
                event.event_sha256,
                observed,
            )
        _need(set(models) == set(runs))
        failures = db.execute("SELECT * FROM first_failures").fetchall()
        _need(len(failures) == len(firsts))
        for row in failures:
            _need(row["app_run_id"] in firsts)
            failure, revision, raw = firsts[row["app_run_id"]]
            _need(
                tuple(row)
                == (
                    row["app_run_id"],
                    failure.reason,
                    failure.first_observed_at,
                    failure.source_sha256,
                    raw,
                    revision,
                )
            )
        slots = db.execute("SELECT * FROM slot_log ORDER BY slot_sequence").fetchall()
        _need(len(slots) == len(runs) <= 1)  # No slot-disposition API in B-CORE.
        for row in slots:
            _need(row["slot_sequence"] == 1 and row["action"] == "RESERVE")
            event = db.execute(
                "SELECT * FROM events WHERE revision=?", (row["revision"],)
            ).fetchone()
            _need(
                event is not None
                and event["app_run_id"] == row["app_run_id"]
                and event["kind"] == "INTENT_COMMITTED"
            )
        return TestAudit(
            installation,
            len(owners),
            len(runs),
            previous_revision,
            previous_revision,
            slots[0]["app_run_id"] if slots else None,
        )

    def audit(self) -> TestAudit:
        _location(self.location, existing=True)
        db = self._db()
        try:
            db.execute("BEGIN")
            return self._audit(db)
        finally:
            db.rollback()

    def _test_checkpoint(self, point: str) -> None:
        """Inert exception-only seam; no runtime/config/env failpoint selector."""

    def _before_commit(self, operation: str) -> None:
        """Inert test subclass seam."""

    def _after_commit(self, operation: str) -> None:
        """Inert commit-then-raise test seam; never reissues a transaction."""

    def _write(self, operation: str, work: Callable[[sqlite3.Connection], T]) -> T:
        _need(not self._uncertain, "COMMIT_UNKNOWN")
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
        except BaseException as error:
            if committing:
                self._acknowledged.clear()
                self._uncertain = True
            try:
                db.rollback()
            except sqlite3.Error:
                self._acknowledged.clear()
                self._uncertain = True
            if committing:
                raise CatalogError("COMMIT_UNKNOWN") from None
            if isinstance(error, CatalogError):
                raise
            if isinstance(error, sqlite3.OperationalError):
                code = (
                    "BUSY"
                    if error.sqlite_errorcode in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                    else "STORAGE_BLOCKED"
                )
                raise CatalogError(code) from None
            if isinstance(error, sqlite3.Error):
                raise CatalogError("STORAGE_BLOCKED") from None
            raise

    def register_owner_for_test(self, owner: SyntheticOwner) -> SyntheticOwnerAck:
        _need(type(owner) is SyntheticOwner, "INVALID_MODEL")
        owner.__post_init__()
        obj = owner.values()

        def write(db: sqlite3.Connection) -> None:
            install = db.execute("SELECT * FROM installation").fetchone()
            _need(obj["installation_id"] == install["installation_id"], "TRANSITION_REFUSED")
            _need(
                obj["authority_record_sha256"] == install["authority_sha256"], "TRANSITION_REFUSED"
            )
            previous = db.execute(
                "SELECT * FROM owners ORDER BY generation_number DESC LIMIT 1"
            ).fetchone()
            _need(
                obj["generation_number"] == (previous["generation_number"] + 1 if previous else 1),
                "TRANSITION_REFUSED",
            )
            _need(
                obj["previous_registration_sha256"]
                == (p.digest("OWNER", previous["registration_bytes"]) if previous else None),
                "TRANSITION_REFUSED",
            )
            db.execute(
                "INSERT INTO owners VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", _owner_columns(obj, owner.raw)
            )
            self._test_checkpoint("OWNER_INSERTED")

        self._write("OWNER", write)
        generation, signature = c.text(obj["generation"]), p.digest("OWNER", owner.raw)
        self._acknowledged.add((generation, signature))
        return SyntheticOwnerAck(generation, signature, self._issuer)

    def _check_ack(self, db: sqlite3.Connection, ack: SyntheticOwnerAck | None) -> sqlite3.Row:
        _need(type(ack) is SyntheticOwnerAck, "TRANSITION_REFUSED")
        assert ack is not None
        _need(
            ack._issuer is self._issuer
            and (ack.generation, ack.owner_sha256) in self._acknowledged,
            "TRANSITION_REFUSED",
        )
        row = db.execute("SELECT * FROM owners ORDER BY generation_number DESC LIMIT 1").fetchone()
        _need(
            row is not None
            and row["generation"] == ack.generation
            and p.digest("OWNER", row["registration_bytes"]) == ack.owner_sha256,
            "TRANSITION_REFUSED",
        )
        return cast(sqlite3.Row, row)

    @staticmethod
    def _lookup(db: sqlite3.Connection, request: c.WireObject) -> PrivateIdentity | None:
        row = db.execute(
            "SELECT * FROM runs WHERE operation='FIXED_SUBMISSION' AND idempotency_key=?",
            (request["idempotency_key"],),
        ).fetchone()
        if row is None:
            return None
        _need(row["fingerprint"] == c.submission_fingerprint(request), "IDEMPOTENCY_CONFLICT")
        event = db.execute(
            "SELECT generation,revision FROM events WHERE app_run_id=? AND run_sequence=1",
            (row["app_run_id"],),
        ).fetchone()
        return PrivateIdentity(
            row["installation_id"],
            row["app_run_id"],
            row["allocation_id"],
            row["fingerprint"],
            row["accepted_at"],
            event["generation"],
            event["revision"],
            row["admission_bytes"],
            row["expectation_bytes"],
        )

    def lookup_for_test(self, request_bytes: bytes) -> PrivateIdentity | None:
        p.bounded_record(
            request_bytes,
            "schema_version kind capability_id capability_revision data_mode idempotency_key",
            262144,
        )
        request = c.SubmissionRequest.parse(request_bytes).to_wire()
        db = self._db()
        try:
            db.execute("BEGIN")
            self._audit(db)
            return self._lookup(db, request)
        finally:
            db.rollback()

    def _append_core(
        self,
        db: sqlite3.Connection,
        app: str,
        generation: str,
        kind: str,
        phase: s.Phase,
        actor: str,
        observed_at: str,
        monotonic_ns: str,
        facts: bytes,
    ) -> s.ModeledEvent:
        _need(kind in CORE_KINDS, "TRANSITION_REFUSED")
        prior = db.execute(
            "SELECT revision,event_sha256 FROM events ORDER BY revision DESC LIMIT 1"
        ).fetchone()
        sequence = db.execute(
            "SELECT COALESCE(MAX(run_sequence),0)+1 FROM events WHERE app_run_id=?", (app,)
        ).fetchone()[0]
        boot = db.execute(
            "SELECT boot_id FROM owners WHERE generation=?", (generation,)
        ).fetchone()[0]
        event = s.ModeledEvent(
            prior["revision"] + 1 if prior else 1,
            app,
            sequence,
            prior["revision"] if prior else 0,
            kind,
            phase,
            actor,
            generation,
            observed_at,
            boot,
            monotonic_ns,
            facts,
            prior["event_sha256"] if prior else s.ZERO_HASH,
        )
        db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event.revision,
                app,
                sequence,
                event.expected_previous_revision,
                kind,
                phase.value,
                actor,
                generation,
                observed_at,
                boot,
                monotonic_ns,
                1,
                facts,
                event.previous_sha256,
                event.event_sha256,
            ),
        )
        return event

    def reserve_for_test(
        self,
        intent: SyntheticIntent,
        acknowledgement: SyntheticOwnerAck | None,
        *,
        expected_capability_revision: str,
        expected_revision: int,
    ) -> PrivateIdentity:
        _need(type(intent) is SyntheticIntent, "INVALID_MODEL")
        intent.__post_init__()
        request = c.SubmissionRequest.parse(intent.request_bytes).to_wire()
        # Existing accepted identity is read BEFORE current epoch/policy/BUSY/CAS checks.
        found = self.lookup_for_test(intent.request_bytes)
        if found is not None:
            return found

        def write(db: sqlite3.Connection) -> PrivateIdentity:
            found = self._lookup(db, request)
            if found is not None:
                return found
            owner = self._check_ack(db, acknowledgement)
            _need(
                request["capability_revision"] == expected_capability_revision, "TRANSITION_REFUSED"
            )
            _need(
                db.execute("SELECT COALESCE(MAX(revision),0) FROM events").fetchone()[0]
                == expected_revision,
                "TRANSITION_REFUSED",
            )
            _need(not db.execute("SELECT * FROM current_slot").fetchall(), "BUSY")
            expectation = intent.expectations.values()
            _need(expectation["installation_id"] == owner["installation_id"], "TRANSITION_REFUSED")
            admission = p.bounded_record(intent.admission_bytes, ADMISSION_FIELDS)
            registration = SyntheticOwner(owner["registration_bytes"]).values()
            _need(
                admission["runtime_sha256"] == owner["runtime_sha256"]
                and admission["authority_record_sha256"] == registration["authority_record_sha256"],
                "TRANSITION_REFUSED",
            )
            app, fingerprint = str(uuid4()), c.submission_fingerprint(request)
            db.execute(
                "INSERT INTO runs VALUES(?,?,'FIXED_SUBMISSION',?,?,?,?,?,?,?,?,?,1)",
                (
                    app,
                    owner["installation_id"],
                    request["idempotency_key"],
                    intent.request_bytes,
                    fingerprint,
                    expectation["allocation_id"],
                    intent.accepted_at,
                    intent.admission_bytes,
                    p.digest("INTENT", intent.admission_bytes),
                    intent.expectations.raw,
                    p.digest("EXPECTATION", intent.expectations.raw),
                ),
            )
            self._test_checkpoint("RUN_INSERTED")
            event = self._append_core(
                db,
                app,
                owner["generation"],
                "INTENT_COMMITTED",
                s.Phase.INTENT_HELD,
                "ADMISSION",
                intent.accepted_at,
                intent.monotonic_ns,
                c.canonical_json(
                    {
                        "admission_sha256": p.digest("INTENT", intent.admission_bytes),
                        "expectation_sha256": p.digest("EXPECTATION", intent.expectations.raw),
                        "fingerprint": fingerprint,
                        "allocation_id": expectation["allocation_id"],
                    }
                ),
            )
            self._test_checkpoint("INTENT_INSERTED")
            db.execute("INSERT INTO slot_log VALUES(1,?,'RESERVE',?)", (app, event.revision))
            self._test_checkpoint("SLOT_INSERTED")
            result = self._lookup(db, request)
            assert result is not None
            return result

        return self._write("INTENT", write)

    def record_block_for_test(
        self,
        app_run_id: str,
        acknowledgement: SyntheticOwnerAck,
        failure: s.Failure,
        *,
        expected_revision: int,
        monotonic_ns: str,
    ) -> None:
        """Preparatory modeled cause only; never reports a child outcome or frees a slot."""
        c.uuid4_text(app_run_id)
        failure.__post_init__()
        _need(
            failure.reason
            in ("SERVICE_NOT_READY", "STORAGE_BLOCKED", "RECOVERY_BLOCKED", "LAUNCH_INTERRUPTED"),
            "TRANSITION_REFUSED",
        )
        p.decimal_text(monotonic_ns)

        def write(db: sqlite3.Connection) -> None:
            owner = self._check_ack(db, acknowledgement)
            _need(
                db.execute("SELECT COALESCE(MAX(revision),0) FROM events").fetchone()[0]
                == expected_revision,
                "TRANSITION_REFUSED",
            )
            _need(
                db.execute("SELECT * FROM runs WHERE app_run_id=?", (app_run_id,)).fetchone()
                is not None,
                "TRANSITION_REFUSED",
            )
            _need(
                db.execute(
                    "SELECT * FROM first_failures WHERE app_run_id=?", (app_run_id,)
                ).fetchone()
                is None,
                "TRANSITION_REFUSED",
            )
            prior = db.execute(
                "SELECT state FROM current_run_state WHERE app_run_id=?", (app_run_id,)
            ).fetchone()[0]
            raw = c.canonical_json(
                {
                    "reason": failure.reason,
                    "first_observed_at": failure.first_observed_at,
                    "source_sha256": failure.source_sha256,
                }
            )
            event = self._append_core(
                db,
                app_run_id,
                owner["generation"],
                "FIRST_FAILURE",
                s.Phase(prior),
                "RECOVERY",
                failure.first_observed_at,
                monotonic_ns,
                raw,
            )
            db.execute(
                "INSERT INTO first_failures VALUES(?,?,?,?,?,?)",
                (
                    app_run_id,
                    failure.reason,
                    failure.first_observed_at,
                    failure.source_sha256,
                    raw,
                    event.revision,
                ),
            )
            self._append_core(
                db,
                app_run_id,
                owner["generation"],
                "QUARANTINED",
                s.Phase.QUARANTINED,
                "RECOVERY",
                failure.first_observed_at,
                str(int(monotonic_ns) + 1),
                c.canonical_json(
                    {
                        "prior_revision": event.revision,
                        "evidence_sha256": failure.source_sha256,
                        "reason": failure.reason,
                    }
                ),
            )

        self._write("BLOCK", write)
