"""Lazy factories: verify once before exposing each new physical connection."""

import os
from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DatabaseConfig, PersistenceError, Use, reject_ambient

IDENTITY_SQL = """
SELECT current_database() AS database, current_user AS active_role,
       session_user AS authenticated_role,
       current_setting('server_version_num')::integer / 10000 AS major,
       pg_catalog.shobj_description(d.oid, 'pg_database') AS marker,
       pg_catalog.pg_get_userbyid(d.datdba) AS database_owner,
       pg_catalog.pg_get_userbyid(n.nspowner) AS schema_owner,
       r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls,
       EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = r.oid) AS memberships,
       has_database_privilege(current_user, d.oid, 'CONNECT') AS db_connect,
       has_database_privilege(current_user, d.oid, 'CREATE') AS db_create,
       has_database_privilege(current_user, d.oid, 'TEMP') AS db_temp,
       has_schema_privilege(current_user, n.oid, 'USAGE') AS schema_usage,
       has_schema_privilege(current_user, n.oid, 'CREATE') AS schema_create,
       EXISTS (SELECT 1 FROM pg_catalog.pg_class WHERE relowner = r.oid) AS owns_objects
FROM pg_catalog.pg_database d, pg_catalog.pg_roles r, pg_catalog.pg_namespace n
WHERE d.datname = current_database() AND r.rolname = session_user AND n.nspname = 'public'
"""


def verify_identity(row: Mapping[str, Any] | None, config: DatabaseConfig, use: Use) -> None:
    expected = {
        "database": config.database,
        "active_role": config.role(use),
        "authenticated_role": config.role(use),
        "major": 17,
        "marker": config.marker,
        "database_owner": f"pitlab_{config.target}_admin",
        "schema_owner": config.role("migration"),
        "db_connect": True,
        "schema_usage": True,
        "schema_create": use == "migration",
        "db_create": False,
        "db_temp": False,
        "memberships": False,
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolreplication": False,
        "rolbypassrls": False,
    }
    if use == "runtime":
        expected["owns_objects"] = False
    if row is None or any(row.get(key) != value for key, value in expected.items()):
        raise PersistenceError(
            f"{config.target} database identity/role/privilege mismatch; stop and inspect configuration."
        )


def _connect_verified(config: DatabaseConfig, use: Use) -> psycopg.Connection[tuple[Any, ...]]:
    raw: psycopg.Connection[tuple[Any, ...]] | None = None
    try:
        url = config.runtime_url if use == "runtime" else config.migration_url
        raw = psycopg.connect(
            host="127.0.0.1",
            port=config.port,
            dbname=config.database,
            user=config.role(use),
            password=str(url.password),
            connect_timeout=5,
            options="-c statement_timeout=10000 -c lock_timeout=5000",
        )
        with raw.cursor(row_factory=dict_row) as cursor:
            cursor.execute(IDENTITY_SQL)
            verify_identity(cursor.fetchone(), config, use)
        raw.rollback()
        return raw
    except Exception as error:
        if raw is not None:
            raw.close()
        if isinstance(error, PersistenceError):
            raise
        state = getattr(error, "sqlstate", None)
        detail = (
            "authentication rejected"
            if state in ("28P01", "28000")
            else "connection/verification unavailable"
        )
        raise PersistenceError(
            f"{config.target} database {detail}; check selected config and explicitly start that DB."
        ) from None


def create_database_engine(config: DatabaseConfig, use: Use = "runtime") -> Engine:
    """Construct without connecting; every creator invocation verifies its physical connection."""
    reject_ambient(os.environ)
    config.role(use)
    engine = create_engine(
        config.runtime_url if use == "runtime" else config.migration_url,
        creator=lambda: _connect_verified(config, use),
        pool_size=2,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=False,
        echo=False,
        hide_parameters=True,
    )
    # Engine-local metadata only; direct Alembic rejects unguarded or wrong-use connections.
    engine.__dict__["_pitlab_policy"] = config, use

    @event.listens_for(engine, "handle_error")
    def redact_sql_error(context: Any) -> None:
        if isinstance(context.original_exception, PersistenceError):
            raise context.original_exception from None
        raise PersistenceError(
            "Database SQL failed; transaction must roll back (details redacted)."
        ) from None

    return engine


def require_guarded_connection(connection: Connection, config: DatabaseConfig, use: Use) -> None:
    if getattr(connection.engine, "_pitlab_policy", None) != (config, use) or connection.closed:
        raise PersistenceError(
            "Operation requires the active guarded connection for this target/role."
        )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    if getattr(engine, "_pitlab_policy", None) is None:
        raise PersistenceError("Sessions require an official guarded Engine.")
    return sessionmaker(bind=engine, expire_on_commit=False)


def probe_database(config: DatabaseConfig) -> None:
    engine = create_database_engine(config)
    try:
        with engine.connect() as connection:
            if connection.exec_driver_sql("SELECT 1").scalar_one() != 1:
                raise PersistenceError("SQL readiness probe failed.")
    finally:
        engine.dispose()
