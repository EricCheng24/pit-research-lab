"""Actual F4 PostgreSQL tests. The guarded Owner WSL runner selects every target."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import psycopg
import pytest

from pit_research_lab.mvp.f4 import d1, d1_backup, d1_store
from pit_research_lab.mvp.f4.d1_custody import blob_path
from pit_research_lab.mvp.f4.d1_profile import (
    AUDIENCE,
    ISSUER,
    REVENUE,
    Refusal,
    decode,
    digest,
    json_bytes,
    load_target,
    private_read,
    sha,
)

pytestmark = pytest.mark.integration
CONTROL = "F4_D1_INTEGRATION"
ISSUER_FILE = "issuer_fixture.csv"
REVENUE_FILE = "revenue_fixture.csv"
LOCK = "SELECT public.f4_d1_lock_attempt()"
RAW_LOCK = "LOCK TABLE public.f4_d1_attempt IN SHARE ROW EXCLUSIVE MODE"
TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
    "MAINTAIN",
)


def interrupted(stop):
    def callback(point):
        if point == stop:
            raise InterruptedError(stop)

    return callback


def runtime_catalog(maintainer, *, open_grants):
    roles = ("reader", "custodian", "publisher", "migrator", "admin")
    with d1_store.connect(maintainer) as db:
        assert db.execute(
            "SELECT pg_get_userbyid(proowner) AS owner, prosecdef AS definer,"
            " proconfig AS config, pronargs AS nargs FROM pg_proc"
            " WHERE oid='public.f4_d1_lock_attempt()'::regprocedure"
        ).fetchone() == {
            "owner": maintainer.user,
            "definer": True,
            "config": ["search_path=pg_catalog"],
            "nargs": 0,
        }
        for role in roles:
            account = maintainer.account(role)
            elevated = role in {"admin", "migrator"}
            for name in d1_store.TABLES + d1_store.VIEWS + ("alembic_version",):
                for privilege in TABLE_PRIVILEGES:
                    expected = (
                        elevated
                        or open_grants
                        and (
                            privilege == "SELECT"
                            and (
                                role in {"publisher", "custodian"}
                                and name in d1_store.TABLES
                                or role == "reader"
                                and name in d1_store.VIEWS
                            )
                            or privilege == "INSERT"
                            and role == "publisher"
                            and name in d1_store.TABLES
                            and name not in {"profile", "profile_event"}
                        )
                    )
                    assert db.execute(
                        "SELECT has_table_privilege(%s,%s,%s) AS allowed",
                        (account, f"public.f4_d1_{name}", privilege),
                    ).fetchone() == {"allowed": expected}, (role, name, privilege)
            assert db.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE') AS helper,"
                " has_type_privilege(%s,'public.f4_d1_sha','USAGE') AS domain,"
                " has_sequence_privilege(%s,'public.f4_d1_observation_ordinal_seq',"
                " 'USAGE, SELECT, UPDATE') AS sequence",
                (account, d1_store.ATTEMPT_LOCK, account, account),
            ).fetchone() == {
                "helper": elevated or open_grants and role == "publisher",
                "domain": elevated or open_grants,
                "sequence": elevated,
            }, role


def test_f4_d1_foundation():
    control = os.environ.get(CONTROL)
    assert control, "explicit verified Owner WSL F4 integration descriptor required"
    details = decode(private_read(Path(control), 8192))
    assert set(details) == {
        "integration",
        "independent",
        "container",
        "app_auth",
        "restoration",
        "restore_container",
    }
    root = Path(details["integration"])
    reader = load_target(root / "reader.json")
    maintainer = load_target(root / "migrator.json")
    admin = load_target(root / "admin.json")
    writer = load_target(root / "custodian.json")
    publisher = load_target(root / "publisher.json")
    other = load_target(Path(details["independent"]) / "reader.json")
    assert maintainer.target == "test" and other.marker != maintainer.marker
    assert other.port != maintainer.port and other.root != maintainer.root

    def ingest(profile=REVENUE, filename=REVENUE_FILE, config=writer, attempt=None, **opts):
        return d1.import_fixture(
            config,
            profile,
            attempt or str(uuid4()),
            filename,
            publisher=publisher,
            **opts,
        )

    # The Owner initialized this dedicated instance once. Exercise repeat guarded migration.
    d1.init(admin, maintainer, writer, reader, publisher, restore_only=False)
    runtime_catalog(maintainer, open_grants=True)
    with d1_store.connect(maintainer) as db:
        assert d1_store.revision(db) == "d1_001"
        assert db.execute("SELECT to_regclass('public.alembic_version') AS v").fetchone() == {
            "v": None
        }
    with (
        pytest.raises(Refusal, match="F4_DATABASE_IDENTITY_MISMATCH"),
        d1_store.connect(replace(maintainer, instance=str(uuid4()))),
    ):
        pytest.fail("wrong deployment accepted")

    first = ingest(ISSUER, ISSUER_FILE)
    assert first["counts"] == {"total": 3, "accepted": 2, "rejected": 0, "excluded": 1}
    repeated = ingest(attempt=str(uuid4()))
    replay = ingest(attempt=repeated["attempt"])
    assert repeated == replay and repeated["publication"] == "UNRESOLVED"
    assert repeated["started_at"] <= repeated["captured_at"] <= repeated["completed_at"]
    duplicate = ingest()
    assert duplicate["artifact"] == repeated["artifact"]
    assert duplicate["observation"] != repeated["observation"]
    with pytest.raises(Refusal, match="ATTEMPT_REQUEST_MISMATCH"):
        ingest(ISSUER, ISSUER_FILE, attempt=repeated["attempt"])
    initial = d1.inspect(reader)["values"]
    separate = d1.inspect(other)["values"]
    assert {r["version_sha"] for r in initial} == {r["version_sha"] for r in separate}
    assert {r["subject_sha"] for r in initial} == {r["subject_sha"] for r in separate}

    data = private_read(writer.root / "inputs" / REVENUE_FILE, 8 * 1024 * 1024)
    changed_name = "changed.csv"
    changed_data = data.replace(b",0,2025-02-09", b",42,2025-02-09", 1)
    location = writer.root / "inputs" / changed_name
    with location.open("xb") as output:
        output.write(changed_data)
    location.chmod(0o600)
    changed_writer = replace(
        writer,
        inputs=writer.inputs
        | {
            f"{REVENUE}/{changed_name}": sha(changed_data),
        },
    )
    alt = ingest(filename=changed_name, config=changed_writer)
    reverted = ingest()
    sequences = []
    for observation in (repeated, alt, reverted):
        values = [
            r
            for r in d1.inspect(reader)["values"]
            if r["observation"] == observation["attempt"] and r["row_no"] == 1
        ]
        assert len(values) == 1
        sequences.append(values[0]["version_sha"])
    assert sequences[0] == sequences[2] != sequences[1]

    for breakpoint, expected in (
        ("after_intent", "INTERRUPTED"),
        ("after_publish", "IMPORTED_UNQUALIFIED"),
        ("before_commit", "IMPORTED_UNQUALIFIED"),
        ("after_commit", "IMPORTED_UNQUALIFIED"),
    ):
        attempt = str(uuid4())
        with pytest.raises(InterruptedError, match=breakpoint):
            ingest(attempt=attempt, checkpoint=interrupted(breakpoint))
        with d1_store.connect(maintainer) as db:
            row = d1_store.started(db, attempt)
            assert row is not None
            assert (row["receipt"] is not None) == (breakpoint == "after_commit")
            children = db.execute(
                "SELECT COUNT(*) AS n FROM public.f4_d1_row_result WHERE observation=%s",
                (attempt,),
            ).fetchone()
            assert children == {"n": 4 if breakpoint == "after_commit" else 0}
        terminal = d1.recover(writer, attempt, publisher=publisher)
        assert terminal["result"] == expected
        assert d1.recover(writer, attempt, publisher=publisher) == terminal

    attempt = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as threads:
        tasks = [threads.submit(ingest, attempt=attempt) for _ in range(2)]
        assert tasks[0].result(timeout=10) == tasks[1].result(timeout=10)
    with pytest.raises(Refusal, match="EXPORT_AUDIENCE_NOT_GRANTED"):
        d1.export(reader, "PUBLIC", "denied")
    assert d1.export(reader, AUDIENCE, "approved-fixture-export")["rows"] > 0
    with d1_store.connect(maintainer) as db:
        saved = db.execute(
            "SELECT artifact_sha,size FROM public.f4_d1_observation WHERE id=%s",
            (repeated["attempt"],),
        ).fetchone()
        assert saved is not None
    path = blob_path(writer.root, saved["artifact_sha"])
    original = private_read(path, 8 * 1024 * 1024)
    try:
        path.write_bytes(b"x" * len(original))
        with pytest.raises(Refusal, match="ARTIFACT_INTEGRITY_FAILURE"):
            d1.recover(writer, repeated["attempt"], publisher=publisher)
    finally:
        path.write_bytes(original)
    assert d1.recover(writer, repeated["attempt"], publisher=publisher) == repeated
    with d1_store.connect(reader) as db:
        for query in (
            "SELECT * FROM public.f4_d1_artifact",
            "INSERT INTO public.f4_d1_issuer VALUES ('FIC-ILLEGAL')",
            LOCK,
            RAW_LOCK,
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(query)
    app_secret = private_read(Path(details["app_auth"]), 1024).decode().strip()
    with psycopg.connect(
        host="127.0.0.1",
        port=writer.port,
        dbname=writer.database,
        user="pitlab_test_app",
        password=app_secret,
        connect_timeout=5,
    ) as app:
        bound = app.execute(
            "SELECT shobj_description(oid,'pg_database') FROM pg_database "
            "WHERE datname=current_database()"
        ).fetchone()
        assert bound == (writer.marker,)
        for query in (
            "INSERT INTO public.f4_d1_attempt DEFAULT VALUES",
            "UPDATE public.f4_d1_observation SET result='INTERRUPTED'",
            "INSERT INTO public.f4_d1_assertion_occurrence DEFAULT VALUES",
            LOCK,
            RAW_LOCK,
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), app.transaction():
                app.execute(query)
    with d1_store.connect(writer) as db:
        for query in (LOCK, RAW_LOCK):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(query)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("INSERT INTO public.f4_d1_profile_event DEFAULT VALUES")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("UPDATE public.f4_d1_observation SET result='INTERRUPTED'")
        for query, params in (
            ("INSERT INTO public.f4_d1_attempt DEFAULT VALUES", ()),
            (
                "INSERT INTO public.f4_d1_assertion_occurrence"
                " (observation,row_no,field,version_sha,report_date) VALUES (%s,1,'amount',%s,%s)",
                (first["attempt"], sequences[0], "2025-02-09"),
            ),
            (
                "INSERT INTO public.f4_d1_issuer_occurrence"
                " (observation,row_no,issuer_key,code,name,sector,listed_date)"
                " SELECT %s,1,issuer_key,code,name,sector,listed_date"
                " FROM public.f4_d1_issuer_occurrence WHERE observation=%s AND row_no=1",
                (repeated["attempt"], first["attempt"]),
            ),
            (
                "INSERT INTO public.f4_d1_assertion_occurrence"
                " (observation,row_no,field,version_sha,report_date) VALUES (%s,1,'amount',%s,%s)",
                (repeated["attempt"], sequences[1], "2025-02-09"),
            ),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(query, params)
    verified = d1.verify(maintainer)
    with d1_store.connect(publisher) as db:
        for query in (
            RAW_LOCK,
            "DELETE FROM public.f4_d1_attempt",
            "TRUNCATE public.f4_d1_attempt",
            "INSERT INTO public.f4_d1_profile_event DEFAULT VALUES",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(query)
        with pytest.raises(psycopg.errors.UndefinedFunction), db.transaction():
            db.execute("SELECT public.f4_d1_lock_attempt('public.f4_d1_issuer')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("SELECT public.f4_d1_check_completion()")
        for obs, row, version, reason in (
            (first["attempt"], 1, sequences[0], "D1 child profile mismatch"),
            (repeated["attempt"], 1, sequences[1], "D1 child projection mismatch"),
            (repeated["attempt"], 4, sequences[0], "D1 child projection mismatch"),
        ):
            with (
                pytest.raises(psycopg.errors.CheckViolation, match=reason),
                db.transaction(),
            ):
                db.execute(
                    "INSERT INTO public.f4_d1_assertion_occurrence"
                    " (observation,row_no,field,version_sha,report_date) VALUES (%s,%s,'amount',%s,%s)",
                    (obs, row, version, "2025-02-09"),
                )
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="D1 child profile mismatch"),
            db.transaction(),
        ):
            db.execute(
                "INSERT INTO public.f4_d1_issuer_occurrence"
                " (observation,row_no,issuer_key,code,name,sector,listed_date)"
                " SELECT %s,1,issuer_key,code,name,sector,listed_date"
                " FROM public.f4_d1_issuer_occurrence WHERE observation=%s AND row_no=1",
                (repeated["attempt"], first["attempt"]),
            )
        for bad_receipt in (False, True):
            omitted = str(uuid4())
            with (
                pytest.raises(
                    psycopg.errors.CheckViolation,
                    match="D1 receipt binding mismatch"
                    if bad_receipt
                    else "D1 incomplete sealed observation",
                ),
                db.transaction(),
            ):
                db.execute(
                    "INSERT INTO public.f4_d1_attempt"
                    " (id,profile_sha,request_sha,input_sha,input_name,started_at,deployment)"
                    " SELECT %s,profile_sha,request_sha,input_sha,input_name,started_at,deployment"
                    " FROM public.f4_d1_attempt WHERE id=%s",
                    (omitted, repeated["attempt"]),
                )
                receipt = repeated | {
                    "attempt": omitted,
                    "observation": f"f4d1:observation:{omitted}",
                }
                if bad_receipt:
                    receipt["request_sha"] = "e" * 64
                db.execute(
                    "INSERT INTO public.f4_d1_observation"
                    " (id,profile_sha,artifact_sha,size,captured_at,completed_at,result,"
                    " receipt_sha,receipt,projection)"
                    " SELECT %s,profile_sha,artifact_sha,size,captured_at,completed_at,result,"
                    " %s,%s,projection FROM public.f4_d1_observation WHERE id=%s",
                    (omitted, digest("receipt", receipt), json_bytes(receipt), repeated["attempt"]),
                )
                db.execute(
                    "INSERT INTO public.f4_d1_custody_event (id,outcome) VALUES (%s,'PUBLISHED')",
                    (omitted,),
                )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
            db.execute(
                "INSERT INTO public.f4_d1_row_result SELECT * FROM public.f4_d1_row_result "
                "WHERE observation=%s AND row_no=1",
                (repeated["attempt"],),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute(
                "UPDATE public.f4_d1_assertion_version SET amount=1 WHERE version_sha=%s",
                (sequences[0],),
            )
    reconciled = d1.verify(maintainer)
    assert {k: v for k, v in reconciled.items() if k != "sequence"} == {
        k: v for k, v in verified.items() if k != "sequence"
    }

    # Use a trusted, rollback-only migrator adversary. Both digests and row counts remain valid.
    with d1_store.connect(maintainer) as db:
        with pytest.raises(Refusal, match="ARTIFACT_ASSERTION_OCCURRENCE_MISMATCH"):
            with db.transaction():
                db.execute(
                    "UPDATE public.f4_d1_assertion_occurrence SET version_sha=%s"
                    " WHERE observation=%s AND row_no=1",
                    (sequences[1], repeated["attempt"]),
                )
                assert db.execute(
                    "SELECT count(*) AS n FROM public.f4_d1_assertion_occurrence"
                ).fetchone() == {"n": verified["tables"]["assertion_occurrence"]["count"]}
                d1_backup.state(db, writer.root)
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(
                "UPDATE public.f4_d1_assertion_version SET amount=1 WHERE version_sha=%s",
                (sequences[0],),
            )
    reconciled = d1.verify(maintainer)
    assert {k: v for k, v in reconciled.items() if k != "sequence"} == {
        k: v for k, v in verified.items() if k != "sequence"
    }

    # Configure a past fixture window under the trusted test migrator.
    with d1_store.connect(maintainer) as db:
        db.execute(
            "INSERT INTO public.f4_d1_profile_event VALUES "
            "(%s,statement_timestamp()-interval '2 microseconds','ENABLE_FIXTURE',"
            "statement_timestamp()-interval '1 microsecond')",
            (writer.profiles[REVENUE],),
        )
    with pytest.raises(Refusal, match="FIXTURE_PROFILE_NOT_ACTIVE"):
        ingest()
    assert not d1.inspect(reader)["values"]

    # Revoke, check the exact profile refuses, then explicitly re-enable the fixture event.
    d1.init(admin, maintainer, writer, reader, publisher, restore_only=False, revoke=REVENUE)
    with pytest.raises(Refusal, match="FIXTURE_PROFILE_NOT_ACTIVE"):
        ingest()
    assert not d1.inspect(reader)["values"]
    d1.init(
        admin,
        maintainer,
        writer,
        reader,
        publisher,
        restore_only=False,
        profiles_until=datetime.now(UTC) + timedelta(hours=1),
    )
    before = d1.verify(maintainer)
    arrived = Event()
    later_attempt = str(uuid4())
    later_name = "snapshot-contender.csv"
    later_data = changed_data.replace(b",42,2025-02-09", b",43,2025-02-09", 1)
    later_path = writer.root / "inputs" / later_name
    with later_path.open("xb") as output:
        output.write(later_data)
    later_path.chmod(0o600)
    later_writer = replace(
        writer, inputs=writer.inputs | {f"{REVENUE}/{later_name}": sha(later_data)}
    )
    # Hold the Publisher helper's lock in one real session. A second Publisher
    # must time out in begin(), before it can record the competing intent.
    database_arrived = Event()

    def try_begin():
        with d1_store.connect(publisher) as db:
            db.execute("SET LOCAL lock_timeout='150ms'")
            database_arrived.set()
            with pytest.raises(psycopg.errors.LockNotAvailable) as blocked:
                d1_store.begin(
                    db,
                    later_attempt,
                    REVENUE,
                    writer.profiles[REVENUE],
                    later_name,
                    sha(later_data),
                    writer.marker,
                )
            assert blocked.value.sqlstate == "55P03"
            assert "f4_d1_lock_attempt" in (blocked.value.diag.context or "")
            db.rollback()

    with ThreadPoolExecutor(max_workers=1) as threads:
        with d1_store.connect(publisher) as holder:
            holder.execute(LOCK)
            explicit_locks = holder.execute(
                "SELECT relation::regclass::text AS relation, mode FROM pg_locks"
                " WHERE pid=pg_backend_pid() AND mode='ShareRowExclusiveLock' AND granted"
            ).fetchall()
            assert explicit_locks == [
                {"relation": "public.f4_d1_attempt", "mode": "ShareRowExclusiveLock"}
            ]
            competing = threads.submit(try_begin)
            assert database_arrived.wait(5)
            competing.result(timeout=5)
    assert d1.verify(maintainer) == before

    with ThreadPoolExecutor(max_workers=1) as threads:

        def contention():
            # Actual trusted credential, independent of the OS custody lock.
            with d1_store.connect(publisher) as direct:
                direct.execute("SET LOCAL lock_timeout='150ms'")
                with (
                    pytest.raises(psycopg.errors.LockNotAvailable),
                    direct.transaction(),
                ):
                    direct.execute("INSERT INTO public.f4_d1_issuer VALUES ('FIC-BLOCKED')")
                with (
                    pytest.raises(psycopg.errors.LockNotAvailable, match="lock timeout"),
                    direct.transaction(),
                ):
                    direct.execute(LOCK)
                assert d1_store.is_active(direct, REVENUE, writer.profiles[REVENUE])
            result = threads.submit(
                ingest,
                filename=later_name,
                config=later_writer,
                attempt=later_attempt,
                lock_budget=0,
                on_contention=arrived.set,
            )
            assert arrived.wait(5), "writer did not reach the contested custody lock"
            with pytest.raises(Refusal, match="^CUSTODY_LOCK_TIMEOUT$"):
                result.result(timeout=5)

        bundle = d1_backup.backup(
            maintainer,
            details["container"],
            "concurrent-fixture-backup",
            on_snapshot=contention,
        )
    backup_path = writer.root / "concurrent-fixture-backup"
    assert bundle["state"] == before
    assert d1_backup.check_bundle(backup_path)[0] == bundle
    assert d1.verify(maintainer) == before
    followup = ingest(filename=later_name, config=later_writer, attempt=later_attempt)
    assert followup["result"] == "IMPORTED_UNQUALIFIED"
    assert ingest(filename=later_name, config=later_writer, attempt=later_attempt) == followup
    after = d1.verify(maintainer)
    assert set(after["bindings"]) == set(before["bindings"]) | {later_attempt}
    assert all(after["bindings"][key] == value for key, value in before["bindings"].items())
    assert set(after["artifacts"]) == set(before["artifacts"]) | {sha(later_data)}
    binding = after["bindings"][later_attempt]
    assert followup["attempt"] == later_attempt
    assert followup["observation"] == f"f4d1:observation:{later_attempt}"
    assert followup["artifact"] == f"f4d1:artifact:sha256:{sha(later_data)}"
    assert binding["receipt"] == digest("receipt", followup)
    assert binding["artifact"] == sha(later_data)
    with d1_store.connect(publisher) as db:
        saved_attempt = d1_store.started(db, later_attempt)
        assert saved_attempt is not None and d1_store.read_receipt(saved_attempt) == followup
        assert saved_attempt["input_sha"] == sha(later_data)
        assert saved_attempt["request_sha"] == followup["request_sha"]
    for name in ("attempt", "observation", "artifact", "custody_event"):
        assert after["tables"][name]["count"] == before["tables"][name]["count"] + 1
    destination = load_target(Path(details["restoration"]) / "migrator.json")
    restore_publisher = load_target(destination.root.parent / "publisher.json")
    runtime_catalog(destination, open_grants=False)
    with d1_store.connect(restore_publisher) as db:
        for query in (LOCK, RAW_LOCK, "SELECT * FROM public.f4_d1_attempt"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(query)
    restored = d1_backup.restore(destination, details["restore_container"], backup_path)
    assert restored["state"] == before == d1.verify(destination)
    assert later_attempt not in restored["state"]["bindings"]
    runtime_catalog(destination, open_grants=True)
    with d1_store.connect(restore_publisher) as db:
        db.execute(LOCK)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute(RAW_LOCK)
