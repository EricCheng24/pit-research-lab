"""C01–C05: supplied SQLite fixtures, never physical-helper installations."""

import os
import sqlite3
import stat
import subprocess
from hashlib import sha256
from time import monotonic

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import launch_policy as p
from pit_research_lab.mvp.f6.backend import os_ownership as o
from pit_research_lab.mvp.f6.backend import os_runtime_catalog as r
from pit_research_lab.mvp.f6.backend import runtime_catalog as core
from pit_research_lab.mvp.f6.backend import supervisor as s
from pit_research_lab.mvp.f6.backend.child_launcher import hold_unregistered_observation

pytestmark = pytest.mark.integration
IDS = tuple(f"81000000-0000-4000-8000-{n:012d}" for n in range(1, 10))
INSTALL, KEY, ALLOCATION, GEN, LAUNCHER, PERMISSION, CHILD, BOOT, OTHER = IDS
SHA = "a" * 64
TIME = "2026-11-22T00:00:00+00:00"


def owner():
    return c.canonical_json(
        {
            "version": 1,
            "record_kind": "OWNER_REGISTRATION",
            "installation_id": INSTALL,
            "generation": GEN,
            "generation_number": 1,
            "boot_id": BOOT,
            "pid": 4000,
            "start_ticks": "100",
            "pgid": 4000,
            "sid": 4000,
            "installation_lock_dev": "8",
            "installation_lock_ino": "9",
            "runtime_sha256": SHA,
            "authority_record_sha256": SHA,
            "observed_at": TIME,
            "monotonic_ns": "10",
            "previous_registration_sha256": None,
            "closure_basis": "INITIAL_EMPTY_INSTALLATION",
            "closure_evidence_sha256": SHA,
        }
    )


def intent(**changes):
    request = {
        "schema_version": c.VERSION,
        "kind": "SUBMISSION_REQUEST",
        "capability_id": c.CAPABILITY_ID,
        "capability_revision": SHA,
        "data_mode": "SYNTHETIC_GOLDEN",
        "idempotency_key": KEY,
    }
    request.update(changes)
    raw = c.canonical_json(request)
    admission = {
        "version": 1,
        "purpose": "TEST_HELPER_ONLY",
        "authority_record_sha256": SHA,
        "operation": "FIXED_SUBMISSION",
        "request_sha256": sha256(raw).hexdigest(),
        "capability_revision": request["capability_revision"],
        "build_sha256": SHA,
        "policy_sha256": SHA,
        "runtime_sha256": SHA,
    }
    expectation = {
        "version": 1,
        "installation_id": INSTALL,
        "allocation_id": ALLOCATION,
        **{key: SHA for key in p.EXPECTATION_FIELDS.split()[3:]},
    }
    return core.SyntheticIntent(
        raw, c.canonical_json(admission), p.Expectations(c.canonical_json(expectation)), TIME, "20"
    )


def records(catalog, app, code=0, signal=None):
    launcher = {
        "version": 1,
        "installation_id": INSTALL,
        "app_run_id": app,
        "launcher_id": LAUNCHER,
        "generation": GEN,
        "boot_id": BOOT,
        "pid": 4001,
        "start_ticks": "101",
        "pgid": 4001,
        "sid": 4001,
        "installation_lock_dev": "8",
        "installation_lock_ino": "9",
        "job_lock_dev": "8",
        "job_lock_ino": "10",
        "channel_nonce_sha256": "b" * 64,
        "executable_sha256": "c" * 64,
    }
    arm = {
        "app_run_id": app,
        "permission_id": PERMISSION,
        "launcher_id": LAUNCHER,
        "generation": GEN,
        "command_sha256": SHA,
        "deadline_boot_id": BOOT,
        "arm_monotonic_ns": "40",
        "deadline_monotonic_ns": "2000000",
        "consumed": 1,
    }
    child = {
        "version": 1,
        "installation_id": INSTALL,
        "app_run_id": app,
        "permission_id": PERMISSION,
        "launcher_id": LAUNCHER,
        "generation": GEN,
        "boot_id": BOOT,
        "pid": 4002,
        "start_ticks": "102",
        "pgid": 4002,
        "sid": 4002,
        "nonce_sha256": "d" * 64,
        "executable_sha256": "c" * 64,
        "command_sha256": SHA,
        "popen_exec_ack": True,
        "handshake_kind": "HELPER_CHALLENGE_RESPONSE",
        "observed_at": TIME,
    }
    wait = {
        "version": 1,
        "installation_id": INSTALL,
        "app_run_id": app,
        "permission_id": PERMISSION,
        "launcher_id": LAUNCHER,
        "generation": GEN,
        "child_record_sha256": p.digest("CHILD", c.canonical_json(child)),
        "boot_id": BOOT,
        "wait_kind": "EXIT" if signal is None else "SIGNAL",
        "exit_code": code,
        "signal_number": signal,
        "reaped_at": TIME,
        "monotonic_ns": "60",
        "resource_observations_sha256": "e" * 64,
    }
    proof = {
        "version": 1,
        "app_run_id": app,
        "basis": "ORIGINAL_WAIT_NOFORK_HELPER",
        "original_launcher_record_sha256": p.digest("LAUNCHER", c.canonical_json(launcher)),
        "wait_record_sha256": p.digest("WAIT", c.canonical_json(wait)),
        "child_contract_sha256": SHA,
        "process_inventory_sha256": "e" * 64,
        "lease_disposition_sha256": "f" * 64,
        "owner_adjudication_sha256": None,
        "observed_boot_id": BOOT,
        "observed_at": TIME,
    }
    return {
        kind: c.canonical_json(obj)
        for kind, obj in (
            ("LAUNCHER", launcher),
            ("ARM", arm),
            ("CHILD", child),
            ("WAIT", wait),
            ("QUIESCENCE", proof),
        )
    }


class FaultCatalog(r.OsHelperCatalog):
    before = ""
    after = ""
    checkpoint = ""

    def _before_commit(self, operation):
        if operation == self.before:
            raise RuntimeError("injected before commit")

    def _after_commit(self, operation):
        if operation == self.after:
            raise RuntimeError("injected lost commit acknowledgement")

    def _checkpoint(self, point):
        if point == self.checkpoint:
            raise RuntimeError("injected precommit checkpoint")


@pytest.fixture(autouse=True)
def no_physical_calls(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("FORBIDDEN")
        raise AssertionError("SQL fixture reached a physical operation")

    for module, name in (
        (o.fcntl, "flock"),
        (o.fcntl, "fcntl"),
        (o.socket, "socket"),
        (o.socket, "socketpair"),
        (o.os, "pidfd_open"),
        (o.os, "kill"),
        (o.os, "killpg"),
        (o.signal, "pidfd_send_signal"),
        (subprocess, "Popen"),
        (subprocess, "run"),
    ):
        monkeypatch.setattr(module, name, forbidden, raising=False)
    yield
    assert calls == []


@pytest.fixture
def catalogs(tmp_path, record_property):
    assert tmp_path.is_relative_to("/tmp")
    objects, roots = [], []
    started = monotonic()

    def create():
        assert len(objects) < 2
        root = tmp_path / f"pit-p103b-bcore.1000.recorded{len(objects)}"
        root.mkdir(mode=0o700)
        roots.append((root, root.lstat()))
        catalog = FaultCatalog(r.RecordedLocation(root, "catalog.sqlite3"))
        catalog.initialize_recorded(INSTALL, SHA, TIME)
        objects.append(catalog)
        return catalog

    try:
        yield create
    finally:
        total = 0
        for catalog in objects:
            catalog.close()
        for root, original in roots:
            now = root.lstat()
            assert (now.st_dev, now.st_ino, now.st_uid) == (
                original.st_dev,
                original.st_ino,
                os.getuid(),
            )
            assert stat.S_ISDIR(now.st_mode) and stat.S_IMODE(now.st_mode) == 0o700
            leaves = [(path, path.lstat()) for path in root.iterdir()]
            assert {path.name for path, _ in leaves} == {"catalog.sqlite3"}
            for path, info in leaves:
                assert (
                    stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                )
                assert stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= r.DB_LIMIT
                total += info.st_size
                assert path.lstat() == info
                path.unlink()
            root.rmdir()
        assert total <= 16 * 1024 * 1024
        record_property("recorded_only_final_bytes", total)
        record_property("recorded_only_elapsed_seconds", monotonic() - started)
        record_property("physical_roles_started", 0)


def admit(catalog):
    ack = catalog.register_owner_recorded(owner())
    return catalog.admit_recorded(
        intent(), ack, expected_revision=0, expected_capability_revision=SHA
    ).app_run_id


def append(catalog, kind, data, mono):
    catalog.append_recorded(
        kind,
        data[kind],
        expected_revision=catalog.audit_recorded().revision,
        observed_at=TIME,
        monotonic_ns=str(mono),
        child_id=CHILD if kind == "CHILD" else None,
    )


def through_child(catalog, code=0):
    app = admit(catalog)
    data = records(catalog, app, code)
    for kind, mono in (("LAUNCHER", 30), ("ARM", 40), ("CHILD", 50)):
        append(catalog, kind, data, mono)
    return app, data


def test_schema_and_profile_separation(catalogs):
    catalog, missing = catalogs(), catalogs()
    db = catalog._db()
    assert r.STATEMENTS is core.STATEMENTS and r.SCHEMA_IDENTITY == core.SCHEMA_IDENTITY
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.execute("PRAGMA defer_foreign_keys").fetchone()[0] == 0
    with pytest.raises(r.CatalogRefusal):
        catalog.admit_recorded(
            intent(), None, expected_revision=0, expected_capability_revision=SHA
        )
    ack = catalog.register_owner_recorded(owner())
    assert catalog.audit_recorded().revision == 0
    assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
    app = catalog.admit_recorded(
        intent(), ack, expected_revision=0, expected_capability_revision=SHA
    ).app_run_id
    negative = missing._db()
    negative.execute("BEGIN IMMEDIATE")
    try:
        run = tuple(db.execute("SELECT * FROM runs").fetchone())
        negative.execute("INSERT INTO runs VALUES(" + ",".join("?" for _ in run) + ")", run)
        item = tuple(db.execute("SELECT * FROM events").fetchone())
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            negative.execute("INSERT INTO events VALUES(" + ",".join("?" for _ in item) + ")", item)
    finally:
        negative.rollback()
    assert missing.audit_recorded().revision == 0
    append(catalog, "LAUNCHER", records(catalog, app), 30)
    old = core.SyntheticCatalog(core.TestLocation(catalog.location.root, catalog.location.filename))
    with pytest.raises(core.CatalogError):
        old.open_existing()
    assert catalog.audit_recorded().evidence_class == "RECORDED_ONLY"
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(o.PhysicalNotAuthorized):
        catalog.activate_physical(ack)


def test_launcher_arm_transaction_uniqueness(catalogs):
    catalog = catalogs()
    app = admit(catalog)
    data = records(catalog, app)
    append(catalog, "LAUNCHER", data, 30)
    db = catalog._db()
    db.execute("BEGIN IMMEDIATE")
    try:
        arm = r.record("ARM", data["ARM"])
        catalog._event(
            db,
            app,
            "SPAWN_ARMED",
            s.Phase.ARM_CONSUMED,
            "LAUNCHER",
            {
                k: arm[k]
                for k in ("permission_id", "launcher_id", "command_sha256", "deadline_monotonic_ns")
            },
            2,
            TIME,
            "40",
        )
        with pytest.raises(sqlite3.IntegrityError, match="ARM_REFUSED"):
            values = r._columns("ARM", arm, 3, None)
            db.execute("INSERT INTO arms VALUES(" + ",".join("?" for _ in values) + ")", values)
    finally:
        db.rollback()
    assert catalog.audit_recorded().revision == 2
    blocker = sqlite3.connect(catalog.location.path, isolation_level=None, timeout=0.25)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            append(catalog, "ARM", data, 40)
    finally:
        blocker.rollback()
        blocker.close()
    append(catalog, "ARM", data, 40)
    before = catalog.location.path.read_bytes()
    with pytest.raises(sqlite3.IntegrityError):
        append(catalog, "ARM", data, 40)
    assert catalog.location.path.read_bytes() == before
    assert db.execute("SELECT consumed FROM arms").fetchone()[0] == 1
    assert catalog.audit_recorded().revision == 3


def test_child_wait_and_first_failure_consistency(catalogs):
    zero, nonzero = catalogs(), catalogs()
    app0, data0 = through_child(zero)
    append(zero, "WAIT", data0, 60)
    before = zero.location.path.read_bytes()
    with pytest.raises(r.CatalogRefusal):
        zero.failure_recorded(
            app0,
            s.Failure("CHILD_NONZERO_EXIT", TIME, SHA),
            expected_revision=5,
            observed_at=TIME,
            monotonic_ns="70",
        )
    assert zero.location.path.read_bytes() == before
    with pytest.raises(sqlite3.IntegrityError):
        append(zero, "WAIT", records(zero, app0, 7), 60)
    assert zero.location.path.read_bytes() == before
    app7, data7 = through_child(nonzero, 7)
    signal = records(nonzero, app7, None, 15)
    db = nonzero._db()
    db.execute("BEGIN IMMEDIATE")
    try:
        obj = r.record("WAIT", signal["WAIT"])
        values = r._columns("WAIT", obj, 5, None)
        db.execute("INSERT INTO waits VALUES(" + ",".join("?" for _ in values) + ")", values)
        nonzero._event(
            db,
            app7,
            "EXIT_OBSERVED",
            s.Phase.EXIT_HELD,
            "LAUNCHER",
            {
                "wait_record_sha256": p.digest("WAIT", signal["WAIT"]),
                "result_kind": "SIGNAL",
                "exit_code": None,
                "signal_number": 15,
            },
            4,
            TIME,
            "60",
        )
        assert nonzero._audit(db).models[0].wait_outcome.signal_number == 15
    finally:
        db.rollback()
    append(nonzero, "WAIT", data7, 60)
    nonzero.failure_recorded(
        app7,
        s.Failure("CHILD_NONZERO_EXIT", TIME, SHA),
        expected_revision=5,
        observed_at=TIME,
        monotonic_ns="70",
    )
    failure = tuple(db.execute("SELECT * FROM first_failures").fetchone())
    with pytest.raises(sqlite3.IntegrityError):
        nonzero.failure_recorded(
            app7,
            s.Failure("STORAGE_BLOCKED", TIME, "b" * 64),
            expected_revision=6,
            observed_at=TIME,
            monotonic_ns="80",
        )
    assert tuple(db.execute("SELECT * FROM first_failures").fetchone()) == failure
    append(nonzero, "QUIESCENCE", data7, 80)
    nonzero.terminal_recorded(
        app7, "FAILED_KNOWN", SHA, expected_revision=7, observed_at=TIME, monotonic_ns="90"
    )
    assert nonzero.audit_recorded().active_run == app7
    assert nonzero.audit_recorded().models[0].first_failure.reason == "CHILD_NONZERO_EXIT"


def test_commit_ack_and_reopen_are_readonly(catalogs):
    owner_unknown, catalog = catalogs(), catalogs()
    owner_unknown.before = "OWNER"
    with pytest.raises(RuntimeError):
        owner_unknown.register_owner_recorded(owner())
    assert owner_unknown.audit_recorded().revision == 0
    assert owner_unknown._db().execute("SELECT COUNT(*) FROM owners").fetchone()[0] == 0
    owner_unknown.before, owner_unknown.after = "", "OWNER"
    with pytest.raises(r.CatalogRefusal, match="COMMIT_UNKNOWN"):
        owner_unknown.register_owner_recorded(owner())
    assert owner_unknown._db().execute("SELECT COUNT(*) FROM owners").fetchone()[0] == 1
    with pytest.raises(r.CatalogRefusal, match="COMMIT_UNKNOWN"):
        owner_unknown.register_owner_recorded(owner())
    ack = catalog.register_owner_recorded(owner())
    for checkpoint in ("RUN_INSERTED", "SLOT_INSERTED"):
        catalog.checkpoint = checkpoint
        with pytest.raises(RuntimeError):
            catalog.admit_recorded(
                intent(), ack, expected_revision=0, expected_capability_revision=SHA
            )
        assert catalog.lookup_recorded(intent().request_bytes) is None
        assert catalog.audit_recorded().revision == 0
    catalog.checkpoint = ""
    identity = catalog.admit_recorded(
        intent(), ack, expected_revision=0, expected_capability_revision=SHA
    )
    data = records(catalog, identity.app_run_id)
    append(catalog, "LAUNCHER", data, 30)
    catalog.after = "ARM"
    with pytest.raises(r.CatalogRefusal, match="COMMIT_UNKNOWN"):
        append(catalog, "ARM", data, 40)
    assert catalog.audit_recorded().revision == 3
    assert (
        catalog.admit_recorded(
            intent(), None, expected_revision=999, expected_capability_revision="b" * 64
        )
        == identity
    )
    with pytest.raises(r.CatalogRefusal, match="COMMIT_UNKNOWN"):
        append(catalog, "ARM", data, 40)
    with pytest.raises(r.CatalogRefusal, match="IDEMPOTENCY_CONFLICT"):
        catalog.lookup_recorded(intent(capability_revision="b" * 64).request_bytes)
    catalog.close()
    assert catalog.open_recorded().lookup_recorded(intent().request_bytes) == identity
    with pytest.raises(r.CatalogRefusal):
        append(catalog, "CHILD", data, 50)
    with pytest.raises(o.PhysicalNotAuthorized):
        catalog.activate_physical(catalog.audit_recorded())


def test_full_audit_tamper_and_slot_retention(catalogs):
    catalog, gap = catalogs(), catalogs()
    app, data = through_child(catalog)
    append(catalog, "WAIT", data, 60)
    append(catalog, "QUIESCENCE", data, 80)
    catalog.terminal_recorded(
        app, "HELPER_EXIT_ZERO_HELD", SHA, expected_revision=6, observed_at=TIME, monotonic_ns="90"
    )
    db = catalog._db()
    assert catalog.audit_recorded().active_run == app
    for table in (
        "installation",
        "owners",
        "runs",
        "events",
        "launchers",
        "arms",
        "children",
        "waits",
        "quiescence",
        "slot_log",
    ):
        for statement in (
            f"UPDATE {table} SET rowid=rowid",
            f"DELETE FROM {table}",
            f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(statement)
    for statement in ("CREATE TABLE extra(x)", "DROP TRIGGER arm_owner", "PRAGMA user_version=99"):
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(statement)
            with pytest.raises(r.CatalogRefusal):
                catalog._audit(db)
        finally:
            db.rollback()
    for table, column, value in (
        ("launchers", "record_bytes", data["LAUNCHER"].replace(b'"pid":4001', b'"pid":4003')),
        ("arms", "command_sha256", "f" * 64),
        ("children", "executable_sha256", "f" * 64),
        ("waits", "exit_code", 7),
        ("quiescence", "proof_sha256", "f" * 64),
        ("events", "previous_sha256", "f" * 64),
    ):
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(f"DROP TRIGGER {table}_no_update")
            db.execute(f"UPDATE {table} SET {column}=?", (value,))
            db.execute(
                next(
                    sql
                    for sql in r.STATEMENTS
                    if sql.startswith(f"CREATE TRIGGER {table}_no_update ")
                )
            )
            with pytest.raises(r.CatalogRefusal):
                catalog._audit(db)
        finally:
            db.rollback()
    db.execute("BEGIN IMMEDIATE")
    try:
        catalog._event(
            db,
            app,
            "SLOT_DISPOSED",
            s.Phase.DISPOSED,
            "SUPERVISOR",
            {
                "quiescence_sha256": p.digest("QUIESCENCE", data["QUIESCENCE"]),
                "terminal_revision": 7,
                "lease_disposition_sha256": "f" * 64,
            },
            7,
            TIME,
            "100",
        )
        db.execute("INSERT INTO slot_log VALUES(2,?,'DISPOSE',8)", (app,))
        with pytest.raises(r.CatalogRefusal):
            catalog._audit(db)
    finally:
        db.rollback()
    gap_app = admit(gap)
    gap_data = records(gap, gap_app)
    append(gap, "LAUNCHER", gap_data, 30)
    append(gap, "ARM", gap_data, 40)
    before = gap.location.path.read_bytes()
    for kind, mono in (("WAIT", 60), ("QUIESCENCE", 80)):
        with pytest.raises(r.CatalogRefusal):
            append(gap, kind, gap_data, mono)
    assert gap.location.path.read_bytes() == before
    assert all(
        gap._db().execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
        for table in ("children", "waits", "quiescence")
    )
    assert gap.audit_recorded().active_run == gap_app
    evidence = hold_unregistered_observation(b"supplied raw wait: no registered child")
    assert evidence.disposition == "REGISTRATION_GAP_UNKNOWN_HELD"
    gap.quarantine_recorded(
        gap_app,
        evidence.observation_sha256,
        expected_revision=3,
        observed_at=TIME,
        monotonic_ns="100",
    )
    assert gap.audit_recorded().models[0].phase is s.Phase.QUARANTINED
    assert gap.audit_recorded().models[0].first_failure is None
