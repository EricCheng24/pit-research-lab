"""Five bounded SQLite-only scenarios; no process, service or native execution."""

import json
import os
import sqlite3
import stat
from dataclasses import asdict, replace
from hashlib import sha256
from time import monotonic

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import launch_policy as p
from pit_research_lab.mvp.f6.backend import runtime_catalog as r
from pit_research_lab.mvp.f6.backend import supervisor as s

pytestmark = pytest.mark.integration
INSTALL = "40000000-0000-4000-8000-000000000001"
BOOT = "40000000-0000-4000-8000-000000000002"
KEY = "40000000-0000-4000-8000-000000000003"
ALLOC = "40000000-0000-4000-8000-000000000004"
TIME = "2026-11-21T00:00:00+00:00"
LATER = "2026-11-21T00:00:01+00:00"
SHA = "a" * 64


def owner(number=1, previous=None, **changes):
    obj = {
        "version": 1,
        "record_kind": "OWNER_REGISTRATION",
        "installation_id": INSTALL,
        "generation": f"50000000-0000-4000-8000-{number:012d}",
        "generation_number": number,
        "boot_id": BOOT,
        "pid": 8123,
        "start_ticks": "500",
        "pgid": 8123,
        "sid": 8123,
        "installation_lock_dev": "9",
        "installation_lock_ino": "17",
        "runtime_sha256": SHA,
        "authority_record_sha256": SHA,
        "observed_at": TIME,
        "monotonic_ns": "10",
        "previous_registration_sha256": p.digest("OWNER", previous.raw) if previous else None,
        "closure_basis": "ORIGINAL_INSTALLATION_AUTHORITY_CLOSED"
        if previous
        else "INITIAL_EMPTY_INSTALLATION",
        "closure_evidence_sha256": SHA,
    }
    obj.update(changes)
    return r.SyntheticOwner(c.canonical_json(obj))


def intent(**request_changes):
    request = {
        "schema_version": c.VERSION,
        "kind": "SUBMISSION_REQUEST",
        "capability_id": c.CAPABILITY_ID,
        "capability_revision": SHA,
        "data_mode": "SYNTHETIC_GOLDEN",
        "idempotency_key": KEY,
    }
    request.update(request_changes)
    raw = c.canonical_json(request)
    admission = {
        "version": 1,
        "purpose": r.PURPOSE,
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
        "allocation_id": ALLOC,
        **{key: SHA for key in p.EXPECTATION_FIELDS.split()[3:]},
    }
    return r.SyntheticIntent(
        raw, c.canonical_json(admission), p.Expectations(c.canonical_json(expectation)), TIME, "20"
    )


class FaultCatalog(r.SyntheticCatalog):
    checkpoint = ""
    before = ""
    after = ""
    sampled_bytes = 0

    def _test_checkpoint(self, point):
        size = sum(path.lstat().st_size for path in self.location.root.iterdir())
        assert size <= 256 * 1024 * 1024
        self.sampled_bytes = max(self.sampled_bytes, size)
        if point == self.checkpoint:
            raise RuntimeError("injected transaction checkpoint")

    def _before_commit(self, operation):
        if operation == self.before:
            raise RuntimeError("injected before commit")

    def _after_commit(self, operation):
        if operation == self.after:
            raise RuntimeError("injected lost commit ACK")


@pytest.fixture
def catalogs(tmp_path, record_property):
    """At most four private catalogs, no thread/child. Delete only owned leaves."""
    assert tmp_path.is_relative_to("/tmp")
    assert all(stat.S_ISDIR(parent.lstat().st_mode) for parent in (tmp_path, *tmp_path.parents))
    parent_info = tmp_path.lstat()
    assert parent_info.st_uid == os.getuid()
    private_root = tmp_path / "pit-p103b-bcore.1.integration"
    private_root.mkdir(mode=0o700)  # Existing or linked leaves must refuse, never be adopted.
    root_info = private_root.lstat()
    assert private_root.parent == tmp_path
    assert stat.S_ISDIR(root_info.st_mode) and root_info.st_uid == os.getuid()
    assert stat.S_IMODE(root_info.st_mode) == 0o700
    record_property("private_root", str(private_root))
    record_property(
        "private_root_identity",
        json.dumps(
            {
                "dev": root_info.st_dev,
                "ino": root_info.st_ino,
                "uid": root_info.st_uid,
                "mode": stat.S_IMODE(root_info.st_mode),
            }
        ),
    )
    objects = []

    def create():
        assert len(objects) < 4
        location = r.TestLocation(private_root, f"catalog{len(objects)}.sqlite3")
        catalog = FaultCatalog(location).initialize(INSTALL, SHA, TIME)
        objects.append(catalog)
        return catalog

    try:
        yield create
    finally:
        cleanup_complete = False
        try:
            for catalog in objects:
                catalog.close()
            parent_now = tmp_path.lstat()
            assert (parent_now.st_dev, parent_now.st_ino) == (
                parent_info.st_dev,
                parent_info.st_ino,
            )
            assert stat.S_ISDIR(parent_now.st_mode) and parent_now.st_uid == os.getuid()
            current = private_root.lstat()
            assert (current.st_dev, current.st_ino) == (root_info.st_dev, root_info.st_ino)
            assert stat.S_ISDIR(current.st_mode) and current.st_uid == os.getuid()
            assert stat.S_IMODE(current.st_mode) == 0o700
            leaves = [(path, path.lstat()) for path in private_root.iterdir()]
            size = sum(info.st_size for _, info in leaves)
            record_property("owned_final_bytes", size)
            record_property(
                "sampled_transaction_bytes", max((obj.sampled_bytes for obj in objects), default=0)
            )
            record_property("owned_inventory", json.dumps([(p.name, i.st_size) for p, i in leaves]))
            record_property(
                "owned_file_modes",
                json.dumps([(p.name, stat.S_IMODE(i.st_mode)) for p, i in leaves]),
            )
            assert size <= 256 * 1024 * 1024
            expected_names = {f"catalog{i}.sqlite3" for i in range(len(objects))}
            # Validate the entire inventory before deleting any leaf. Sidecars,
            # symlinks and unknown files are retained as failed-cleanup evidence.
            for path, info in leaves:
                assert path.name in expected_names
                assert info.st_uid == os.getuid() and stat.S_ISREG(info.st_mode)
                assert info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
                assert info.st_size <= r.DB_CEILING
            for path, info in leaves:
                assert path.lstat() == info
                path.unlink()
            remaining = len(tuple(private_root.iterdir()))
            record_property("owned_cleanup_remaining", remaining)
            assert remaining == 0
            private_root.rmdir()
            assert not os.path.lexists(private_root)
            cleanup_complete = True
        finally:
            record_property("private_root_removed", cleanup_complete)


def reserve(catalog, ack, candidate=None, revision=0):
    return catalog.reserve_for_test(
        candidate or intent(), ack, expected_capability_revision=SHA, expected_revision=revision
    )


def counts(catalog):
    db = catalog._db()
    return tuple(
        db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        for table in ("owners", "runs", "events", "slot_log", "arms")
    )


def test_tx0_tx1_real_foreign_keys_owner_only_reopen_and_atomic_unit(catalogs, record_property):
    catalog = catalogs()
    db = catalog._db()
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.execute("PRAGMA defer_foreign_keys").fetchone()[0] == 0
    # Direct SQL negative: create the deferred run, then a first event whose
    # required owner is absent. The real immediate owner FK must reject it.
    candidate = intent()
    app = "60000000-0000-4000-8000-000000000001"
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "INSERT INTO runs VALUES(?,?,'FIXED_SUBMISSION',?,?,?,?,?,?,?,?,?,1)",
            (
                app,
                INSTALL,
                KEY,
                candidate.request_bytes,
                c.submission_fingerprint(
                    c.SubmissionRequest.parse(candidate.request_bytes).to_wire()
                ),
                ALLOC,
                TIME,
                candidate.admission_bytes,
                p.digest("INTENT", candidate.admission_bytes),
                candidate.expectations.raw,
                p.digest("EXPECTATION", candidate.expectations.raw),
            ),
        )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed") as error:
            db.execute(
                "INSERT INTO events VALUES(1,?,1,0,'INTENT_COMMITTED','INTENT_HELD','ADMISSION',?,?,?,'20',1,?,?,?)",
                (
                    app,
                    owner().values()["generation"],
                    TIME,
                    BOOT,
                    c.canonical_json(
                        {
                            "admission_sha256": SHA,
                            "expectation_sha256": SHA,
                            "fingerprint": SHA,
                            "allocation_id": ALLOC,
                        }
                    ),
                    s.ZERO_HASH,
                    SHA,
                ),
            )
        record_property("missing_owner_sql_trace", str(error.value))
    finally:
        db.rollback()
    assert counts(catalog) == (0, 0, 0, 0, 0)
    with pytest.raises(r.CatalogError, match="TRANSITION_REFUSED"):
        reserve(catalog, None)
    first = owner()
    old_ack = catalog.register_owner_for_test(first)
    assert counts(catalog) == (1, 0, 0, 0, 0)
    catalog.close()
    catalog.open_existing()
    assert catalog.audit().revision == 0 and counts(catalog) == (1, 0, 0, 0, 0)
    with pytest.raises(r.CatalogError, match="TRANSITION_REFUSED"):
        reserve(catalog, old_ack)
    ack = catalog.register_owner_for_test(owner(2, first))
    result = reserve(catalog, ack)
    assert counts(catalog) == (2, 1, 1, 1, 0)
    assert result.original_generation == ack.generation and result.intent_revision == 1
    with pytest.raises(r.CatalogError, match="TRANSITION_REFUSED"):
        catalog._append_core(
            catalog._db(),
            result.app_run_id,
            ack.generation,
            "SPAWN_ARMED",
            s.Phase.ARM_CONSUMED,
            "LAUNCHER",
            TIME,
            "30",
            b"{}",
        )
    assert counts(catalog) == (2, 1, 1, 1, 0)
    assert catalog._db().execute("PRAGMA foreign_key_check").fetchall() == []
    assert all(
        catalog._db().execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
        for table in ("launchers", "arms", "children", "waits", "quiescence")
    )
    record_property("fk_check", "[]")
    record_property("tx0_tx1_audit", json.dumps(asdict(catalog.audit())))
    catalog.close()
    assert catalog.open_existing().lookup_for_test(candidate.request_bytes) == result


def test_atomic_faults_and_definite_vs_unknown_commit_ack(catalogs, record_property):
    catalog = catalogs()
    ack = catalog.register_owner_for_test(owner())
    for point in ("RUN_INSERTED", "INTENT_INSERTED", "SLOT_INSERTED"):
        catalog.checkpoint = point
        with pytest.raises(RuntimeError, match="injected"):
            reserve(catalog, ack)
        assert counts(catalog) == (1, 0, 0, 0, 0)
        assert catalog.lookup_for_test(intent().request_bytes) is None
        assert catalog._db().execute("PRAGMA foreign_key_check").fetchall() == []
    catalog.checkpoint = ""
    catalog.before = "INTENT"
    with pytest.raises(RuntimeError, match="before commit"):
        reserve(catalog, ack)
    assert counts(catalog) == (1, 0, 0, 0, 0)
    catalog.before = ""
    assert reserve(catalog, ack).intent_revision == 1

    unknown_owner = catalogs()
    unknown_owner.after = "OWNER"
    with pytest.raises(r.CatalogError, match="COMMIT_UNKNOWN"):
        unknown_owner.register_owner_for_test(owner())
    assert counts(unknown_owner) == (1, 0, 0, 0, 0)
    with pytest.raises(r.CatalogError, match="COMMIT_UNKNOWN"):
        unknown_owner.register_owner_for_test(owner(2, owner()))

    unknown_intent = catalogs()
    ack = unknown_intent.register_owner_for_test(owner())
    unknown_intent.after = "INTENT"
    with pytest.raises(r.CatalogError, match="COMMIT_UNKNOWN"):
        reserve(unknown_intent, ack)
    assert counts(unknown_intent) == (1, 1, 1, 1, 0)
    original = unknown_intent.lookup_for_test(intent().request_bytes)
    assert reserve(unknown_intent, None) == original  # Identity-only readback.
    with pytest.raises(r.CatalogError, match="COMMIT_UNKNOWN"):
        reserve(unknown_intent, ack, intent(idempotency_key="40000000-0000-4000-8000-000000000006"))
    assert counts(unknown_intent) == (1, 1, 1, 1, 0)

    before_owner = catalogs()
    before_owner.before = "OWNER"
    with pytest.raises(RuntimeError, match="before commit"):
        before_owner.register_owner_for_test(owner())
    assert counts(before_owner) == (0, 0, 0, 0, 0)
    record_property(
        "fault_points",
        "RUN_INSERTED INTENT_INSERTED SLOT_INSERTED PRECOMMIT_OWNER PRECOMMIT_INTENT POSTCOMMIT_OWNER POSTCOMMIT_INTENT",
    )


def test_accepted_key_precedes_drift_busy_and_owner_fencing(catalogs):
    catalog = catalogs()
    first = owner()
    for bad in (
        owner(installation_id="40000000-0000-4000-8000-000000000009"),
        owner(authority_record_sha256="b" * 64),
    ):
        with pytest.raises(r.CatalogError):
            catalog.register_owner_for_test(bad)
    ack = catalog.register_owner_for_test(first)
    for forged in (
        replace(ack, _issuer=object()),
        replace(ack, generation=INSTALL),
        replace(ack, owner_sha256="b" * 64),
    ):
        with pytest.raises(r.CatalogError):
            reserve(catalog, forged)
    for candidate in (
        replace(intent(), monotonic_ns="1"),
        replace(intent(), accepted_at="2026-11-20T00:00:00+00:00"),
    ):
        with pytest.raises(r.CatalogError):
            reserve(catalog, ack, candidate)
    accepted = reserve(catalog, ack)
    failure = s.Failure("RECOVERY_BLOCKED", LATER, SHA)
    catalog.record_block_for_test(
        accepted.app_run_id, ack, failure, expected_revision=1, monotonic_ns="30"
    )
    before_failure = tuple(catalog._db().execute("SELECT * FROM first_failures").fetchone())
    with pytest.raises(r.CatalogError):
        catalog.record_block_for_test(
            accepted.app_run_id,
            ack,
            s.Failure("STORAGE_BLOCKED", LATER, "b" * 64),
            expected_revision=3,
            monotonic_ns="40",
        )
    assert tuple(catalog._db().execute("SELECT * FROM first_failures").fetchone()) == before_failure
    for bad in (owner(2, first, previous_registration_sha256="b" * 64), owner(3, first)):
        with pytest.raises(r.CatalogError):
            catalog.register_owner_for_test(bad)
    second = catalog.register_owner_for_test(
        owner(2, first, boot_id="40000000-0000-4000-8000-000000000008")
    )
    db = catalog._db()
    before = (db.total_changes, catalog.location.path.read_bytes(), counts(catalog))
    changed_expectation = replace(
        intent(),
        expectations=p.Expectations(
            intent().expectations.raw.replace(b'"a' + b"a" * 63, b'"b' + b"b" * 63)
        ),
    )
    for current in (intent(), changed_expectation):
        assert (
            catalog.reserve_for_test(
                current, None, expected_capability_revision="b" * 64, expected_revision=999
            )
            == accepted
        )
    assert (db.total_changes, catalog.location.path.read_bytes(), counts(catalog)) == before
    with pytest.raises(r.CatalogError, match="IDEMPOTENCY_CONFLICT"):
        reserve(catalog, second, intent(capability_revision="b" * 64))
    fresh = intent(idempotency_key="40000000-0000-4000-8000-000000000006")
    with pytest.raises(r.CatalogError, match="TRANSITION_REFUSED"):
        reserve(catalog, ack, fresh, revision=3)
    with pytest.raises(r.CatalogError, match="BUSY"):
        reserve(catalog, second, fresh, revision=3)
    assert catalog.lookup_for_test(fresh.request_bytes) is None
    assert db.total_changes == before[0] and counts(catalog) == (2, 1, 3, 1, 0)
    assert second.live_refusal() is p.Refusal.B_CORE_AUTHORITY_ABSENT


def test_immutable_ledger_replace_order_hash_and_closed_record_tamper(catalogs):
    catalog = catalogs()
    ack = catalog.register_owner_for_test(owner())
    accepted = reserve(catalog, ack)
    db = catalog._db()
    for table in ("installation", "owners", "runs", "events", "slot_log"):
        for sql in (
            f"UPDATE {table} SET rowid=rowid",
            f"DELETE FROM {table}",
            f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_B_FACT"):
                db.execute(sql)
    # Alternate UNIQUE collision, not merely same primary key.
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_B_FACT"):
        db.execute(
            "INSERT OR REPLACE INTO owners SELECT ?,generation_number,installation_id,boot_id,pid,start_ticks,pgid,sid,install_dev,install_ino,runtime_sha256,registration_bytes FROM owners",
            ("50000000-0000-4000-8000-000000000009",),
        )
    for revision, sequence, prior in ((3, 2, 1), (2, 3, 1), (2, 2, 0)):
        with pytest.raises(sqlite3.IntegrityError, match="STALE_EVENT"):
            db.execute(
                "INSERT INTO events SELECT ?,app_run_id,?,?,kind,state,actor,generation,observed_at,boot_id,monotonic_ns,facts_version,facts,previous_sha256,? FROM events WHERE revision=1",
                (revision, sequence, prior, "b" * 64),
            )
    for column, value in (
        ("event_sha256", "b" * 64),
        ("previous_sha256", "b" * 64),
        ("actor", "LAUNCHER"),
        ("generation", INSTALL),
        ("facts", b'{"fabricated":true}'),
    ):
        db.execute("BEGIN IMMEDIATE")
        db.execute("DROP TRIGGER events_no_update")
        if column == "generation":
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
                db.execute(f"UPDATE events SET {column}=?", (value,))
            db.rollback()
            continue
        db.execute(f"UPDATE events SET {column}=?", (value,))
        db.execute(
            next(sql for sql in r.STATEMENTS if sql.startswith("CREATE TRIGGER events_no_update "))
        )
        with pytest.raises(r.CatalogError):
            catalog._audit(db)
        db.rollback()
        assert catalog.audit().revision == 1
    # A fabricated registration JSON / column disagreement cannot be self-pinned.
    db.execute("BEGIN IMMEDIATE")
    db.execute("DROP TRIGGER owners_no_update")
    db.execute("UPDATE owners SET boot_id=?", ("40000000-0000-4000-8000-000000000009",))
    db.execute(
        next(sql for sql in r.STATEMENTS if sql.startswith("CREATE TRIGGER owners_no_update "))
    )
    with pytest.raises(r.CatalogError):
        catalog._audit(db)
    db.rollback()
    assert catalog.lookup_for_test(intent().request_bytes) == accepted
    assert counts(catalog) == (1, 1, 1, 1, 0)


def test_unknown_storage_schema_bounded_contention_and_no_repair(catalogs, record_property):
    catalog = catalogs()
    db = catalog._db()
    for sql in (
        "CREATE TABLE unapproved(x)",
        "CREATE INDEX unapproved ON owners(pid)",
        "DROP TRIGGER event_order",
        "DROP TABLE children",
        "PRAGMA application_id=7",
        "PRAGMA user_version=99",
    ):
        db.execute("BEGIN IMMEDIATE")
        db.execute(sql)
        with pytest.raises(r.CatalogError):
            catalog._audit(db)
        db.rollback()
    blocker = sqlite3.connect(catalog.location.path, timeout=0.25, isolation_level=None)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        start = monotonic()
        with pytest.raises(r.CatalogError, match="BUSY"):
            catalog.register_owner_for_test(owner())
        elapsed = monotonic() - start
        assert elapsed < 1.5
        record_property("busy_elapsed_seconds", elapsed)
    finally:
        blocker.rollback()
        blocker.close()
    assert counts(catalog) == (0, 0, 0, 0, 0)
    # Persistent drift survives refusal byte-for-byte; no auto-migration/repair.
    db.execute("PRAGMA user_version=99")
    catalog.close()
    before = catalog.location.path.read_bytes()
    with pytest.raises(r.CatalogError):
        catalog.open_existing()
    assert catalog.location.path.read_bytes() == before
    # A second explicitly test-owned file is deliberately corrupt.
    corrupt = catalogs()
    corrupt.close()
    corrupt.location.path.write_bytes(b"not an sqlite database")
    before = corrupt.location.path.read_bytes()
    with pytest.raises(r.CatalogError):
        corrupt.open_existing()
    assert corrupt.location.path.read_bytes() == before
    # Reject unsafe modes/links without ever opening their targets.
    unsafe = catalogs()
    unsafe.close()
    unsafe.location.path.chmod(0o644)
    with pytest.raises(r.CatalogError, match="STORAGE_BLOCKED"):
        unsafe.open_existing()
    unsafe.location.path.chmod(0o600)
    alias = unsafe.location.root / "catalog_alias.sqlite3"
    alias.symlink_to(unsafe.location.path.name)
    try:
        with pytest.raises(r.CatalogError, match="STORAGE_BLOCKED"):
            r.SyntheticCatalog(r.TestLocation(unsafe.location.root, alias.name)).open_existing()
    finally:
        assert alias.is_symlink()
        alias.unlink()
    # Adversarial storage fixture: bypass FKs only to manufacture an orphan in
    # a test-owned corrupt database. Every catalog connection still enables FKs.
    orphan = catalogs()
    orphan_db = orphan._db()
    orphan_db.execute("PRAGMA foreign_keys=OFF")
    orphan_db.execute(
        "INSERT INTO owners VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "50000000-0000-4000-8000-000000000001",
            1,
            KEY,
            BOOT,
            8123,
            "500",
            8123,
            8123,
            "9",
            "17",
            SHA,
            owner().raw,
        ),
    )
    orphan.close()
    with pytest.raises(r.CatalogError):
        orphan.open_existing()
