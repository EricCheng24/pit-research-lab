"""Guarded PostgreSQL access and the trusted, append-only fixture writer."""

import os
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from psycopg.rows import dict_row
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from pit_research_lab.infrastructure.database.config import reject_ambient
from pit_research_lab.infrastructure.database.engine import IDENTITY_SQL

from .d1_profile import (
    Target,
    decode,
    digest,
    json_bytes,
    profile_body,
    require,
    timestamp,
)
from .d1_records import classified, counts

DB = psycopg.Connection[dict[str, Any]]
TABLES = (
    "attempt",
    "profile",
    "profile_event",
    "artifact",
    "observation",
    "issuer",
    "row_result",
    "issuer_occurrence",
    "assertion_version",
    "assertion_occurrence",
    "custody_event",
)
VIEWS = ("inventory", "values", "issuers")
ATTEMPT_LOCK = "public.f4_d1_lock_attempt()"


def table(name: str) -> sql.Identifier:
    require(
        name in TABLES + VIEWS + ("alembic_version", "observation_ordinal_seq"),
        "UNKNOWN_D1_TABLE",
    )
    return sql.Identifier("public", "f4_d1_" + name)


def tables(names: Iterable[str]) -> sql.Composed:
    return sql.SQL(", ").join(map(table, names))


def check_identity(db: DB, target: Target) -> None:
    row = db.execute(IDENTITY_SQL).fetchone()
    admin = target.role == "admin"
    migrator = target.role == "migrator"
    expected = {
        "database": target.database,
        "active_role": target.user,
        "authenticated_role": target.user,
        "major": 17,
        "marker": target.marker,
        "database_owner": target.account("admin"),
        "schema_owner": target.account("migrator"),
        "db_connect": True,
        "schema_usage": True,
        "schema_create": admin or migrator,
        "db_create": admin,
        "db_temp": admin,
        "memberships": False,
        "rolsuper": admin,
    }
    if not admin:
        expected.update(
            rolcreatedb=False,
            rolcreaterole=False,
            rolreplication=False,
            rolbypassrls=False,
        )
    if not admin and not migrator:
        expected["owns_objects"] = False
    require(
        row is not None and all(row[k] == v for k, v in expected.items()),
        "F4_DATABASE_IDENTITY_MISMATCH",
    )


def connect(target: Target) -> DB:
    reject_ambient(os.environ)
    db = psycopg.connect(
        host="127.0.0.1",
        port=target.port,
        dbname=target.database,
        user=target.user,
        password=target.password,
        connect_timeout=5,
        options="-c timezone=UTC -c statement_timeout=15000 -c lock_timeout=5000 "
        "-c search_path=pg_catalog",
        row_factory=dict_row,
    )
    try:
        check_identity(db, target)
        db.rollback()
    except BaseException:
        db.close()
        raise
    return db


def match_roles(target: Target, other: Target, role: str) -> None:
    require(
        other.role == role
        and other.marker == target.marker
        and other.port == target.port
        and other.root == target.root
        and other.password != target.password,
        "ROLE_SCOPE_MISMATCH",
    )


def provision(
    admin: Target, migrator: Target, writer: Target, reader: Target, publisher: Target
) -> None:
    require(admin.role == "admin", "ADMIN_REQUIRED")
    role_pairs = (
        (migrator, "migrator"),
        (writer, "custodian"),
        (reader, "reader"),
        (publisher, "publisher"),
    )
    for other, role_name in role_pairs:
        match_roles(admin, other, role_name)
    require(
        len(
            {
                admin.password,
                migrator.password,
                writer.password,
                reader.password,
                publisher.password,
            }
        )
        == 5,
        "ROLE_SECRET_REUSE",
    )
    with connect(admin) as db:
        for role in (writer, reader, publisher):
            exists = db.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (role.user,)
            ).fetchone()
            if exists is None:
                db.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(role.user), sql.Literal(role.password))
                )
                db.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(role.database), sql.Identifier(role.user)
                    )
                )
                db.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role.user))
                )
    # Validate each separate password and actual grant. Existing mismatch is never repaired.
    for role in (migrator, writer, reader, publisher):
        with connect(role):
            pass


def migration_target(connection: object) -> Target:
    require(
        isinstance(connection, Connection) and not connection.closed,
        "F4_VERIFIED_MIGRATOR_CONNECTION_REQUIRED",
    )
    assert isinstance(connection, Connection)
    target = connection.info.get("f4_d1_target")
    require(
        isinstance(target, Target) and target.role == "migrator",
        "F4_VERIFIED_MIGRATOR_CONNECTION_REQUIRED",
    )
    assert isinstance(target, Target)
    row = connection.exec_driver_sql(IDENTITY_SQL).mappings().one()
    require(
        row["marker"] == target.marker
        and row["database"] == target.database
        and row["active_role"] == target.user
        and row["authenticated_role"] == target.user,
        "F4_MIGRATION_BINDING_MISMATCH",
    )
    return target


def migrate(target: Target, operation: str = "upgrade") -> None:
    require(
        target.role == "migrator" and operation in {"upgrade", "current"},
        "MIGRATOR_REQUIRED",
    )
    root = Path(__file__).resolve().parents[4] / "migrations" / "f4_d1"
    require(
        (root / "versions" / "d1_001_foundation.py").is_file(),
        "CHECKOUT_MIGRATION_REQUIRED",
    )
    cfg = Config()
    cfg.set_main_option("script_location", str(root))

    # The underlying driver identity must be checked before application/Alembic SQL.
    # SQLAlchemy's dialect expects tuple rows; only the guard uses dict_row.
    def creator() -> psycopg.Connection[tuple[Any, ...]]:
        db = cast(psycopg.Connection[tuple[Any, ...]], connect(target))
        db.row_factory = psycopg.rows.tuple_row
        return db

    engine = create_engine("postgresql+psycopg://", creator=creator, hide_parameters=True)
    try:
        with engine.begin() as conn:
            conn.info["f4_d1_target"] = target
            cfg.attributes.update(connection=conn, operation=operation)
            if operation == "upgrade":
                command.upgrade(cfg, "d1_001")
            else:
                command.current(cfg)
    finally:
        engine.dispose()


def grants(db: DB, target: Target, *, available: bool) -> None:
    require(target.role == "migrator", "MIGRATOR_REQUIRED")
    user = sql.Identifier(target.account("custodian"))
    reader = sql.Identifier(target.account("reader"))
    publisher = sql.Identifier(target.account("publisher"))
    domain = sql.SQL("TYPE ") + sql.Identifier("public", "f4_d1_sha")
    members = (
        (sql.SQL("TABLE ") + tables(TABLES), sql.SQL("SELECT"), publisher),
        (domain, sql.SQL("USAGE"), publisher),
        (sql.SQL("FUNCTION " + ATTEMPT_LOCK), sql.SQL("EXECUTE"), publisher),
        (sql.SQL("TABLE ") + tables(TABLES), sql.SQL("SELECT"), user),
        (
            sql.SQL("TABLE ") + tables(n for n in TABLES if n not in {"profile", "profile_event"}),
            sql.SQL("INSERT"),
            publisher,
        ),
        (
            sql.SQL("TYPE ") + sql.Identifier("public", "f4_d1_sha"),
            sql.SQL("USAGE"),
            user,
        ),
        (sql.SQL("TABLE ") + tables(VIEWS), sql.SQL("SELECT"), reader),
        (
            sql.SQL("TYPE ") + sql.Identifier("public", "f4_d1_sha"),
            sql.SQL("USAGE"),
            reader,
        ),
    )
    for objects, permission, role in members:
        clause = sql.SQL("GRANT {} ON {} TO {}" if available else "REVOKE {} ON {} FROM {}")
        db.execute(clause.format(permission, objects, role))


def revision(db: DB) -> str | None:
    present = db.execute("SELECT to_regclass('public.f4_d1_alembic_version') AS v").fetchone()
    if present is None or present["v"] is None:
        return None
    rows = db.execute("SELECT version_num FROM public.f4_d1_alembic_version").fetchall()
    require(rows == [{"version_num": "d1_001"}], "F4_REVISION_MISMATCH")
    return "d1_001"


def lock_all(db: DB, *, restore: bool = False) -> None:
    mode = sql.SQL("ACCESS EXCLUSIVE" if restore else "SHARE")
    db.execute(sql.SQL("LOCK TABLE {} IN {} MODE").format(tables(TABLES), mode))


def set_profile(db: DB, profile: str, expires_at: datetime | None) -> None:
    body = profile_body(profile)
    key = digest("profile", body)
    encoded = json_bytes(body)
    db.execute(
        "INSERT INTO public.f4_d1_profile VALUES (%s,%s,%s) ON CONFLICT (sha) DO NOTHING",
        (key, profile, encoded),
    )
    same = db.execute("SELECT body FROM public.f4_d1_profile WHERE sha=%s", (key,)).fetchone()
    require(same is not None and same["body"] == encoded, "PROFILE_PREIMAGE_MISMATCH")
    if expires_at is not None:
        require(
            datetime.now(UTC) < expires_at <= datetime.now(UTC) + timedelta(days=2),
            "FIXTURE_AUTHORITY_WINDOW",
        )
    db.execute(
        "INSERT INTO public.f4_d1_profile_event(profile_sha,action,expires_at) VALUES (%s,%s,%s)",
        (
            key,
            "ENABLE_FIXTURE" if expires_at is not None else "REVOKE_FIXTURE",
            expires_at,
        ),
    )


def is_active(db: DB, profile: str, key: str) -> bool:
    exact = db.execute(
        """SELECT p.body, e.action, e.expires_at > clock_timestamp() AS current
           FROM public.f4_d1_profile p
           JOIN LATERAL (
               SELECT action, expires_at FROM public.f4_d1_profile_event
               WHERE profile_sha=p.sha ORDER BY recorded_at DESC LIMIT 1
           ) e ON true WHERE p.profile=%s AND p.sha=%s""",
        (profile, key),
    ).fetchone()
    return bool(
        exact
        and exact["body"] == json_bytes(profile_body(profile))
        and exact["action"] == "ENABLE_FIXTURE"
        and exact["current"]
    )


def started(db: DB, attempt: str) -> dict[str, Any] | None:
    return db.execute(
        """SELECT a.*, p.profile, o.receipt, o.receipt_sha FROM public.f4_d1_attempt a
           JOIN public.f4_d1_profile p ON p.sha=a.profile_sha
           LEFT JOIN public.f4_d1_observation o ON o.id=a.id WHERE a.id=%s""",
        (attempt,),
    ).fetchone()


def read_receipt(row: dict[str, Any]) -> dict[str, Any]:
    raw = row["receipt"]
    value = decode(raw)
    require(
        raw == json_bytes(value) and row["receipt_sha"] == digest("receipt", value),
        "RECEIPT_INTEGRITY_FAILURE",
    )
    assert isinstance(value, dict)
    return value


def begin(
    db: DB,
    attempt: str,
    profile: str,
    key: str,
    name: str,
    pin: str,
    deployment: str,
) -> tuple[dict[str, Any], bool]:
    db.execute("SELECT " + ATTEMPT_LOCK)
    require(is_active(db, profile, key), "FIXTURE_PROFILE_NOT_ACTIVE")
    fingerprint = digest("receipt", {"profile": key, "input": name, "sha": pin})
    row = started(db, attempt)
    if row is not None:
        require(row["request_sha"] == fingerprint, "ATTEMPT_REQUEST_MISMATCH")
        return row, False
    db.execute(
        """INSERT INTO public.f4_d1_attempt(id,profile_sha,request_sha,input_sha,input_name,deployment)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (attempt, key, fingerprint, pin, name, deployment),
    )
    row = started(db, attempt)
    assert row is not None
    return row, True


def issuer_bindings(db: DB) -> list[tuple[str, str, str]]:
    return [
        (r["code"], r["issuer_key"], r["name"])
        for r in db.execute(
            "SELECT DISTINCT code,issuer_key,name FROM public.f4_d1_issuer_occurrence"
        ).fetchall()
    ]


def add_result(db: DB, observation: str, artifact: str, row: dict[str, Any]) -> None:
    ordinal = row["row_no"]
    db.execute(
        "INSERT INTO public.f4_d1_row_result VALUES (%s,%s,%s,%s,%s)",
        (observation, artifact, ordinal, row["status"], row["reason"]),
    )
    if row["status"] != "ACCEPTED":
        return
    if "issuer" in row:
        i = row["issuer"]
        db.execute(
            "INSERT INTO public.f4_d1_issuer VALUES (%s) ON CONFLICT DO NOTHING",
            (i["key"],),
        )
        db.execute(
            """INSERT INTO public.f4_d1_issuer_occurrence
               (observation,row_no,issuer_key,code,name,sector,listed_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s::date)""",
            (
                observation,
                ordinal,
                i["key"],
                i["code"],
                i["name"],
                i["sector"],
                i["listed_date"],
            ),
        )
        return
    a = row["assertion"]
    b, subject = a["body"], a["body"]["subject"]
    raw = json_bytes(b)
    subject_raw = json_bytes(subject)
    db.execute(
        """INSERT INTO public.f4_d1_assertion_version
           VALUES (%s,%s,%s,%s::date,%s::date,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (version_sha) DO NOTHING""",
        (
            a["version_sha"],
            a["subject_sha"],
            a["issuer_key"],
            subject["period_start"],
            subject["period_end_exclusive"],
            subject["basis"],
            subject["currency"],
            subject["unit"],
            None if b["value"] is None else Decimal(b["value"]),
            b["state"],
            raw,
            subject_raw,
        ),
    )
    same = db.execute(
        "SELECT body,subject_body FROM public.f4_d1_assertion_version WHERE version_sha=%s",
        (a["version_sha"],),
    ).fetchone()
    require(
        same == {"body": raw, "subject_body": subject_raw},
        "ASSERTION_PREIMAGE_MISMATCH",
    )
    db.execute(
        """INSERT INTO public.f4_d1_assertion_occurrence
           (observation,row_no,field,version_sha,report_date) VALUES (%s,%s,%s,%s,%s::date)""",
        (observation, ordinal, a["field"], a["version_sha"], a["report_date"]),
    )


def projection(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for row in results:
        item = {key: row[key] for key in ("row_no", "status", "reason")}
        if row["status"] == "ACCEPTED":
            if "issuer" in row:
                item["issuer"] = row["issuer"]
            else:
                assertion = row["assertion"]
                item["assertion"] = {
                    key: assertion[key] for key in ("field", "version_sha", "report_date")
                }
        projected.append(item)
    return projected


def finish(
    db: DB,
    target: Target,
    row: dict[str, Any],
    *,
    result: str,
    reason: str | None = None,
    artifact: tuple[str, int] | None = None,
    captured: datetime | None = None,
    raw: bytes | None = None,
    recovered: bool = False,
) -> dict[str, Any]:
    db.execute("SELECT " + ATTEMPT_LOCK)
    observation = str(row["id"])
    current = started(db, observation)
    require(
        current is not None
        and current["request_sha"] == row["request_sha"]
        and current["deployment"] == target.marker,
        "ATTEMPT_REQUEST_MISMATCH",
    )
    assert current is not None
    if current["receipt"] is not None:
        return read_receipt(current)
    now = datetime.now(UTC)
    require(row["started_at"] <= now, "CLOCK_ORDER")
    results = None
    if result == "IMPORTED_UNQUALIFIED":
        require(
            is_active(db, row["profile"], row["profile_sha"]),
            "FIXTURE_PROFILE_NOT_ACTIVE",
        )
        require(
            artifact is not None
            and artifact[0] == row["input_sha"]
            and captured is not None
            and row["started_at"] <= captured <= now
            and raw is not None,
            "INVALID_FIXTURE_FINALIZATION",
        )
        assert raw is not None
        results = classified(row["profile"], raw, issuer_bindings(db))
    else:
        require(artifact is None and captured is None and raw is None, "INVALID_REFUSAL")
    key, size = artifact if artifact is not None else (None, None)
    receipt = {
        "observation": f"f4d1:observation:{observation}",
        "attempt": observation,
        "deployment": row["deployment"],
        "profile": row["profile"],
        "profile_sha": row["profile_sha"],
        "request_sha": row["request_sha"],
        "result": result,
        "reason": reason,
        "artifact": f"f4d1:artifact:sha256:{key}" if key else None,
        "byte_count": size,
        "counts": counts(results) if results is not None else None,
        "started_at": timestamp(row["started_at"]),
        "captured_at": timestamp(captured) if captured else None,
        "completed_at": timestamp(now),
        "clock_precision": "MICROSECOND",
        "clock_origin": "LOCAL_DATABASE_AND_IMPORT_PROCESS_UTC",
        "publication": "UNRESOLVED",
        "history_coverage": "UNRESOLVED",
        "method": "FIXTURE_IMPORT",
        "mode": "SYNTHETIC_ONLY",
    }
    if artifact:
        db.execute(
            "INSERT INTO public.f4_d1_artifact VALUES (%s,%s) ON CONFLICT (sha) DO NOTHING",
            artifact,
        )
    db.execute(
        """INSERT INTO public.f4_d1_observation
           (id,profile_sha,artifact_sha,size,captured_at,completed_at,result,receipt_sha,receipt,projection)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
        (
            observation,
            row["profile_sha"],
            key,
            size,
            captured,
            now,
            result,
            digest("receipt", receipt),
            json_bytes(receipt),
            json_bytes(projection(results or [])).decode("utf-8"),
        ),
    )
    if results is not None:
        assert key is not None
        for item in results:
            add_result(db, observation, key, item)
    outcome = "RECOVERED" if recovered and artifact else "PUBLISHED" if artifact else "NO_BYTES"
    db.execute(
        "INSERT INTO public.f4_d1_custody_event(id,outcome) VALUES (%s,%s)",
        (observation, outcome),
    )
    return receipt


def public_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return timestamp(value)
    if isinstance(value, date | UUID):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def inventory(db: DB) -> dict[str, Any]:
    output: dict[str, Any] = {
        "class": "UNQUALIFIED_FOUNDATION",
        "verification": "UNVERIFIED_DIAGNOSTIC",
        "mode": "SYNTHETIC_ONLY",
        "publication": "UNRESOLVED",
        "attribution": "PIT Research Lab authored fictional fixture",
    }
    for view, order in (
        ("inventory", "ordinal"),
        ("values", "observation,row_no,field"),
        ("issuers", "observation,row_no"),
    ):
        result = db.execute(
            sql.SQL("SELECT * FROM {} ORDER BY {}").format(table(view), sql.SQL(order))
        ).fetchall()
        output[view] = [{k: public_value(v) for k, v in row.items()} for row in result]
    return output
