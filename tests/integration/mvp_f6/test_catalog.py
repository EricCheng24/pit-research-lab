"""Bounded SQLite only: no PG, process, Native verifier, server or release."""

import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from hashlib import sha256

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import catalog as cat
from pit_research_lab.mvp.f6.backend import security as sec

pytestmark = pytest.mark.integration
INSTALLATION = "00000000-0000-4000-8000-000000000001"
KEY = "00000000-0000-4000-8000-000000000002"
SECOND_KEY = "00000000-0000-4000-8000-000000000003"
NOW = "2026-11-21T00:00:00+00:00"


def intent(key=KEY, revision="a" * 64):
    request = c.SubmissionRequest.from_wire(
        dict(
            schema_version=c.VERSION,
            kind="SUBMISSION_REQUEST",
            capability_id=c.CAPABILITY_ID,
            capability_revision=revision,
            data_mode="SYNTHETIC_GOLDEN",
            idempotency_key=key,
        )
    )
    return cat.SyntheticIntent(
        request.serialize(), c.submission_fingerprint(request.to_wire()), revision, "b" * 64, NOW
    )


@pytest.fixture
def location(tmp_path, record_property):
    # pytest --basetemp MUST be external; do not create or chmod a repo path.
    assert str(tmp_path).startswith("/tmp/") and "pit-research-lab-mvp-f6" not in str(tmp_path)
    os.chmod(tmp_path, 0o700)
    value = cat.TestLocation(tmp_path, "catalog.sqlite3")
    yield value
    files = list(tmp_path.rglob("*"))
    regular = [p for p in files if p.is_file() and not p.is_symlink()]
    assert all(p.stat().st_size <= 32 * 1024 * 1024 for p in regular)
    total = sum(p.stat().st_size for p in regular)
    assert total <= 128 * 1024 * 1024
    record_property("owned_file_bytes_before_cleanup", total)
    record_property("sqlite_runtime", sqlite3.sqlite_version)
    # Everything in this isolated fixture directory is test-owned, including
    # adversarial symlinks; unlink the link itself, never its target.
    for path in sorted(files, key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            path.rmdir()
        else:
            path.unlink()
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def opened(location):
    instance = cat.TestCatalog(location).initialize(INSTALLATION)
    yield instance
    instance.close()


def snapshot(location):
    with closing(sqlite3.connect(location.path)) as db:
        return tuple(
            tuple(db.execute(f"SELECT * FROM {name} ORDER BY 1, 2"))
            for name in ("metadata", "intents", "active_slot", "events")
        )


def test_schema_init_reopen_pragmas_and_inert_constructor(location, record_property):
    unopened = cat.TestCatalog(location)
    assert not location.path.exists()
    unopened.initialize(INSTALLATION)
    db = unopened._db()
    actual = {
        key: db.execute("PRAGMA " + key).fetchone()[0]
        for key in (
            "user_version",
            "application_id",
            "foreign_keys",
            "synchronous",
            "journal_mode",
            "busy_timeout",
        )
    }
    assert actual == dict(
        user_version=1,
        application_id=cat.APPLICATION_ID,
        foreign_keys=1,
        synchronous=2,
        journal_mode="delete",
        busy_timeout=1000,
    )
    assert location.path.stat().st_mode & 0o777 == 0o600
    before = location.path.read_bytes()
    unopened.close()
    reopened = cat.TestCatalog(location).open_existing()
    try:
        assert location.path.read_bytes() == before
        assert snapshot(location)[0][0][1] == INSTALLATION
    finally:
        reopened.close()
    record_property("pragmas", repr(actual))


def test_exact_idempotency_survives_close_reopen_and_conflict_is_unchanged(opened, location):
    first = opened.reserve_synthetic(intent())
    assert first.app_run_id != first.allocation_id != first.installation_id
    before = snapshot(location)
    opened.close()
    reopened = cat.TestCatalog(location).open_existing()
    try:
        assert reopened.reserve_synthetic(intent()) == first
        assert snapshot(location) == before
        # Both fingerprints are independently closed and valid; only revision differs.
        with pytest.raises(cat.CatalogError, match="^IDEMPOTENCY_CONFLICT$"):
            reopened.reserve_synthetic(intent(revision="c" * 64))
        assert snapshot(location) == before
        with pytest.raises(cat.CatalogError, match="^BUSY$"):
            reopened.reserve_synthetic(intent(SECOND_KEY))
        assert snapshot(location) == before
    finally:
        reopened.close()


def test_invalid_operands_revalidated_before_key_lookup_and_not_consumed(opened, location):
    before = snapshot(location)
    bad = intent()
    object.__setattr__(bad, "fingerprint", "c" * 64)
    with pytest.raises(cat.CatalogError, match="^INVALID_INPUT$"):
        opened.reserve_synthetic(bad)
    assert snapshot(location) == before
    accepted = opened.reserve_synthetic(intent())
    after = snapshot(location)
    with pytest.raises(cat.CatalogError, match="^INVALID_INPUT$"):
        opened.reserve_synthetic(bad)
    assert snapshot(location) == after
    assert opened.reserve_synthetic(intent()) == accepted


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_bytes", b"{}"),
        ("request_bytes", b"not-json"),
        ("fingerprint", "c" * 64),
        ("expected_build", "secret"),
        ("expected_revision", "c" * 64),
        ("accepted_at", "invalid"),
    ],
)
def test_invalid_synthetic_intent_form_does_not_touch_catalog(opened, location, field, value):
    before = snapshot(location)
    with pytest.raises(cat.CatalogError, match="^INVALID_INPUT$"):
        replace(intent(), **{field: value})
    assert snapshot(location) == before


@pytest.mark.parametrize("table", ["intents", "active_slot", "events"])
def test_injected_insert_failure_rolls_back_all_rows(opened, location, table):
    before = snapshot(location)
    # Separate test-only SQLite seam, no production mock flag. TEMP trigger
    # aborts before the selected insert, including after earlier rows exist.
    opened._db().execute(
        f"CREATE TEMP TRIGGER injection BEFORE INSERT ON {table} "
        "BEGIN SELECT RAISE(ABORT, 'TEST_ONLY_INJECTION'); END"
    )
    with pytest.raises(cat.CatalogError, match="^STORAGE_REFUSED$"):
        opened.reserve_synthetic(intent())
    assert snapshot(location) == before
    opened._db().execute("DROP TRIGGER temp.injection")
    assert opened.reserve_synthetic(intent()).intent_revision == 1


def test_exception_immediately_before_commit_rolls_back_and_reopen_empty(location):
    class Injected(Exception):
        pass

    class FailingCatalog(cat.TestCatalog):
        def _before_commit(self):
            raise Injected("test-only")

    instance = FailingCatalog(location).initialize(INSTALLATION)
    before = snapshot(location)
    try:
        with pytest.raises(Injected, match="^test-only$"):
            instance.reserve_synthetic(intent())
        assert snapshot(location) == before
    finally:
        instance.close()
    reopened = cat.TestCatalog(location).open_existing()
    try:
        assert snapshot(location) == before
        reopened.reserve_synthetic(intent())
    finally:
        reopened.close()


def test_two_separate_connections_single_reservation_no_queue(location):
    cat.TestCatalog(location).initialize(INSTALLATION).close()
    barrier = threading.Barrier(2, timeout=2)

    def compete(key):
        instance = cat.TestCatalog(location).open_existing()
        try:
            barrier.wait()
            try:
                return instance.reserve_synthetic(intent(key))
            except cat.CatalogError as error:
                return error.code
        finally:
            instance.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compete, key) for key in (KEY, SECOND_KEY)]
        outcomes = [future.result(timeout=5) for future in futures]
    assert sum(isinstance(outcome, cat.CatalogIdentity) for outcome in outcomes) == 1
    assert outcomes.count(cat.CatalogCode.BUSY) == 1
    assert [len(rows) for rows in snapshot(location)] == [1, 1, 1, 1]


def test_sql_lock_timeout_is_bounded_closed_busy(opened, location, record_property):
    with closing(sqlite3.connect(location.path)) as holder:
        holder.execute("BEGIN IMMEDIATE")
        before = snapshot(location)
        with pytest.raises(cat.CatalogError, match="^BUSY$"):
            opened.reserve_synthetic(intent())
        assert snapshot(location) == before
        holder.rollback()
    record_property("busy_timeout_milliseconds", cat.TEST_BUSY_MILLISECONDS)
    assert cat.TEST_BUSY_MILLISECONDS <= 2000


def test_immutable_first_failure_and_ordered_events_preserve_held_slot(opened, location):
    row = opened.reserve_synthetic(intent())
    opened.record_block(row.app_run_id, cat.PreparatoryFailure.SERVICE_NOT_READY)
    events = opened.events(row.app_run_id)
    assert [(e.sequence, e.revision, e.phase) for e in events] == [
        (1, 1, "INTENT_RECORDED"),
        (2, 2, "BLOCKED"),
    ]
    assert events[1].first_failure == cat.PreparatoryFailure.SERVICE_NOT_READY
    before = snapshot(location)
    for reason in cat.PreparatoryFailure:
        with pytest.raises(cat.CatalogError, match="^TRANSITION_REFUSED$"):
            opened.record_block(row.app_run_id, reason)
    with pytest.raises(cat.CatalogError, match="^BUSY$"):
        opened.reserve_synthetic(intent(SECOND_KEY))
    assert snapshot(location) == before
    opened.close()
    reopened = cat.TestCatalog(location).open_existing()
    try:
        assert reopened.events(row.app_run_id) == events
        assert reopened.reserve_synthetic(intent()) == row
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM events",
        "UPDATE events SET revision=0",
        "UPDATE events SET sequence=1",
        "UPDATE events SET first_failure='RESOURCE_LIMIT'",
        "DELETE FROM intents",
        "UPDATE intents SET fingerprint='forged'",
        "UPDATE intents SET app_run_id='forged'",
        "UPDATE intents SET allocation_id='forged'",
        "UPDATE intents SET request_bytes=x'7b7d'",
        "DELETE FROM active_slot",
        "UPDATE active_slot SET app_run_id='forged'",
        "UPDATE metadata SET installation_id='forged'",
        "DELETE FROM metadata",
    ],
)
def test_direct_sql_identity_event_and_revision_mutation_refuses(opened, location, sql):
    row = opened.reserve_synthetic(intent())
    opened.record_block(row.app_run_id, cat.PreparatoryFailure.SERVICE_NOT_READY)
    before = snapshot(location)
    with pytest.raises(sqlite3.IntegrityError, match="^CATALOG_IMMUTABLE$"):
        opened._db().execute(sql)
    assert snapshot(location) == before


@pytest.mark.parametrize(
    "phase",
    [
        "NATIVE_RUNNING",
        "SUCCEEDED",
        "VERIFYING",
        "PASSED",
        "COMPLETE",
        "AVAILABLE",
        "ACTUAL_F3_CLI",
        "INTENT_RECORDED",
    ],
)
def test_no_native_or_release_state_can_be_forged(opened, location, phase):
    row = opened.reserve_synthetic(intent())
    before = snapshot(location)
    with pytest.raises(sqlite3.IntegrityError):
        opened._db().execute(
            "INSERT INTO events VALUES (?, 2, 2, ?, 'SERVICE_NOT_READY')", (row.app_run_id, phase)
        )
    with pytest.raises(cat.CatalogError, match="^TRANSITION_REFUSED$"):
        opened.record_block(row.app_run_id, phase)
    assert snapshot(location) == before
    for name in ("launch", "release", "complete", "native_attempt", "verify"):
        assert not hasattr(opened, name)
    with pytest.raises(sqlite3.OperationalError):
        opened._db().execute("INSERT INTO release_manifests VALUES ('forged')")


@pytest.mark.parametrize("table", ["metadata", "intents", "active_slot", "events"])
def test_insert_or_replace_cannot_bypass_immutability(opened, location, table):
    opened.reserve_synthetic(intent())
    before = snapshot(location)
    with pytest.raises(sqlite3.IntegrityError):
        opened._db().execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}")
    assert snapshot(location) == before


def test_deferred_fk_prevents_partial_intent_commit(opened, location):
    before = snapshot(location)
    db = opened._db()
    value = intent()
    db.execute("BEGIN IMMEDIATE")
    db.execute(
        "INSERT INTO intents VALUES (?, ?, 'TEST_FIXED_SUBMISSION', ?, ?, ?, ?, ?, ?, 1)",
        (
            KEY,
            SECOND_KEY,
            KEY,
            value.request_bytes,
            value.fingerprint,
            value.expected_revision,
            value.expected_build,
            value.accepted_at,
        ),
    )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        db.commit()
    db.rollback()
    assert snapshot(location) == before


def test_block_injected_exception_preserves_prior_first_failure_unknown(location):
    class FailingBlockCatalog(cat.TestCatalog):
        def _before_commit(self):
            raise RuntimeError("TEST_ONLY_BLOCK_INJECTION")

    initial = cat.TestCatalog(location).initialize(INSTALLATION)
    row = initial.reserve_synthetic(intent())
    initial.close()
    failing = FailingBlockCatalog(location).open_existing()
    before = snapshot(location)
    try:
        with pytest.raises(RuntimeError, match="^TEST_ONLY_BLOCK_INJECTION$"):
            failing.record_block(row.app_run_id, cat.PreparatoryFailure.SERVICE_NOT_READY)
        assert snapshot(location) == before
        assert failing.events(row.app_run_id)[0].first_failure is None
    finally:
        failing.close()


@pytest.mark.parametrize("sequence,revision", [(1, 2), (2, 1), (2, 3), (3, 2), (2, 0)])
def test_nonmonotonic_revision_duplicate_or_skipped_sequence_refuses(
    opened, location, sequence, revision
):
    row = opened.reserve_synthetic(intent())
    before = snapshot(location)
    with pytest.raises(sqlite3.IntegrityError):
        opened._db().execute(
            "INSERT INTO events VALUES (?, ?, ?, 'BLOCKED', 'SERVICE_NOT_READY')",
            (row.app_run_id, sequence, revision),
        )
    assert snapshot(location) == before


@pytest.mark.parametrize(
    "tamper", ["newer", "zero", "missing", "extra", "trigger", "digest", "application"]
)
def test_unknown_or_tampered_schema_refused_without_repair(location, tamper):
    cat.TestCatalog(location).initialize(INSTALLATION).close()
    with closing(sqlite3.connect(location.path)) as db:
        if tamper == "newer":
            db.execute("PRAGMA user_version=2")
        elif tamper == "zero":
            db.execute("PRAGMA user_version=0")
        elif tamper == "missing":
            db.execute("DROP TABLE events")
        elif tamper == "extra":
            db.execute("CREATE TABLE unauthorized(extra TEXT)")
        elif tamper == "trigger":
            db.execute("DROP TRIGGER events_no_delete")
        elif tamper == "application":
            db.execute("PRAGMA application_id=1")
        else:
            sql = db.execute(
                "SELECT sql FROM sqlite_master WHERE name='metadata_no_update'"
            ).fetchone()[0]
            db.execute("DROP TRIGGER metadata_no_update")
            db.execute("UPDATE metadata SET schema_identity=?", ("0" * 64,))
            db.execute(sql)
        db.commit()
    before = sha256(location.path.read_bytes()).hexdigest()
    with pytest.raises(cat.CatalogError, match="^SCHEMA_REFUSED$"):
        cat.TestCatalog(location).open_existing()
    assert sha256(location.path.read_bytes()).hexdigest() == before
    with pytest.raises(cat.CatalogError):
        cat.TestCatalog(location).initialize(INSTALLATION)
    assert sha256(location.path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("raw", [b"not a database", b"", b"SQLite format 3\x00" + b"\x00" * 100])
def test_corrupt_or_existing_empty_file_not_reinitialized(location, raw):
    location.path.write_bytes(raw)
    location.path.chmod(0o600)
    with pytest.raises(cat.CatalogError, match="^SCHEMA_REFUSED$"):
        cat.TestCatalog(location).open_existing()
    assert location.path.read_bytes() == raw
    with pytest.raises(cat.CatalogError):
        cat.TestCatalog(location).initialize(INSTALLATION)
    assert location.path.read_bytes() == raw


def test_unsafe_locations_and_file_types_refuse(location):
    with pytest.raises(cat.CatalogError):
        cat.TestLocation(location.root, "../secret.sqlite3")
    location.path.symlink_to("/nonexistent-p103a-test-only")
    with pytest.raises(cat.CatalogError):
        cat.TestCatalog(location).initialize(INSTALLATION)
    location.path.unlink()
    location.path.mkdir()
    with pytest.raises(cat.CatalogError):
        cat.TestCatalog(location).open_existing()
    location.path.rmdir()
    location.root.chmod(0o755)
    try:
        with pytest.raises(cat.CatalogError, match="^UNSAFE_TEST_LOCATION$"):
            cat.TestCatalog(location).initialize(INSTALLATION)
    finally:
        location.root.chmod(0o700)


def test_security_refusal_cannot_write_or_consume_catalog_key(opened, location):
    before = snapshot(location)
    for raw in (b"{}", b'{"x":1,"x":2}', intent().request_bytes[:-1]):
        with pytest.raises(c.ContractError):
            request = sec.parse_submission(raw, "a" * 64)
            # Unreachable: allocation only follows all pure guards.
            opened.reserve_synthetic(replace(intent(), request_bytes=request.serialize()))
        assert snapshot(location) == before
    assert opened.reserve_synthetic(intent()).intent_revision == 1


@pytest.mark.parametrize("kind", ["parent_symlink", "hardlink", "fifo", "permissive", "sidecar"])
def test_unsafe_parent_link_special_file_and_sidecar_refusal(location, kind):
    if kind == "parent_symlink":
        alias = location.root / "alias"
        alias.symlink_to(location.root, target_is_directory=True)
        value = cat.TestLocation(alias, "other.sqlite3")
        with pytest.raises(cat.CatalogError, match="^UNSAFE_TEST_LOCATION$"):
            cat.TestCatalog(value).initialize(INSTALLATION)
        assert not (location.root / "other.sqlite3").exists()
        return
    cat.TestCatalog(location).initialize(INSTALLATION).close()
    if kind == "hardlink":
        os.link(location.path, location.root / "hardlink")
    elif kind == "fifo":
        location.path.unlink()
        os.mkfifo(location.path, 0o600)
    elif kind == "permissive":
        location.path.chmod(0o644)
    else:
        sidecar = location.root / (location.filename + "-wal")
        sidecar.write_bytes(b"TEST_ONLY_AMBIGUOUS_SIDECAR")
        sidecar.chmod(0o600)
    with pytest.raises(cat.CatalogError):
        cat.TestCatalog(location).open_existing()


def test_noncanonical_or_mutable_request_bytes_refuse_before_storage(opened, location):
    before = snapshot(location)
    for raw in (bytearray(intent().request_bytes), intent().request_bytes + b"\n"):
        with pytest.raises(cat.CatalogError, match="^INVALID_INPUT$"):
            replace(intent(), request_bytes=raw)
        assert snapshot(location) == before
