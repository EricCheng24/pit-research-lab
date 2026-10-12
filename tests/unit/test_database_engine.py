"""Deterministic physical-connection probes; these are not PostgreSQL acceptance evidence."""

import importlib
import sqlite3

import pytest
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.pool import QueuePool
from test_database_config import config_values

from pit_research_lab.infrastructure.database.config import PersistenceError, parse_config
from pit_research_lab.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
    require_guarded_connection,
    verify_identity,
)


def identity(config, use="runtime"):
    return {
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
        **dict.fromkeys(
            [
                "db_create",
                "db_temp",
                "memberships",
                "rolsuper",
                "rolcreatedb",
                "rolcreaterole",
                "rolreplication",
                "rolbypassrls",
                "owns_objects",
            ],
            False,
        ),
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("database", "pitlab_dev"),
        ("active_role", "pitlab_test_admin"),
        ("authenticated_role", "pitlab_test_migrator"),
        ("major", 18),
        ("marker", "foreign"),
        ("database_owner", "pitlab_test_app"),
        ("schema_owner", "pitlab_test_admin"),
        ("db_connect", False),
        ("schema_usage", False),
        ("schema_create", True),
        *[
            (key, True)
            for key in (
                "db_create",
                "db_temp",
                "memberships",
                "rolsuper",
                "rolcreatedb",
                "rolcreaterole",
                "rolreplication",
                "rolbypassrls",
                "owns_objects",
            )
        ],
    ],
)
def test_identity_negatives(key, value):
    config = parse_config(config_values(), "test")
    row = identity(config)
    row[key] = value
    with pytest.raises(PersistenceError, match="mismatch"):
        verify_identity(row, config, "runtime")


def test_import_and_factory_are_lazy(monkeypatch):
    module = importlib.import_module("pit_research_lab.infrastructure.database.engine")

    def forbidden(**kwargs):
        pytest.fail("physical connection attempted by import/factory")

    monkeypatch.setattr(module.psycopg, "connect", forbidden)
    with monkeypatch.context() as import_patch:
        import_patch.setattr("sqlalchemy.create_engine", forbidden)
        importlib.reload(module)  # Import must construct no Engine as well as open no connection.
    importlib.reload(module)
    engine = module.create_database_engine(parse_config(config_values(), "test"))
    assert engine.pool.size() == 2
    assert engine.pool._max_overflow == 0
    assert engine.pool.timeout() == 5
    assert not engine.echo and engine.hide_parameters
    assert module.create_session_factory(engine).kw["bind"] is engine
    engine.dispose()


def test_verified_creator_pool_reuse_and_invalidation(monkeypatch):
    module = importlib.import_module("pit_research_lab.infrastructure.database.engine")
    config = parse_config(config_values(), "test")
    created = []
    probes = []
    wrong_marker = [False]

    class GuardCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            assert sql == module.IDENTITY_SQL
            probes.append(sql)

        def fetchone(self):
            row = identity(config)
            if wrong_marker[0]:
                row["marker"] = "wrong"
            return row

    class Physical:
        def __init__(self):
            self.db = sqlite3.connect(":memory:")
            self.closed = False

        def cursor(self, *, row_factory=None):
            return GuardCursor() if row_factory else self.db.cursor()

        def close(self):
            self.closed = True
            self.db.close()

        def __getattr__(self, name):
            return getattr(self.db, name)

    def connect(**kwargs):
        assert kwargs["connect_timeout"] == 5
        assert kwargs["port"] == 55433
        physical = Physical()
        created.append(physical)
        return physical

    def harness(url, **kwargs):
        return sqlalchemy_create_engine("sqlite://", poolclass=QueuePool, **kwargs)

    monkeypatch.setattr(module.psycopg, "connect", connect)
    monkeypatch.setattr(module, "create_engine", harness)
    engine = module.create_database_engine(config)
    try:
        with engine.connect() as connection:
            assert len(probes) == 1
            assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
        with engine.connect() as connection:
            assert len(probes) == 1  # Reused live physical connection is not re-probed.
            connection.invalidate()
            assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
            assert len(probes) == 2
            connection.rollback()
            connection.invalidate()
            wrong_marker[0] = True
            with pytest.raises(PersistenceError, match="mismatch"):
                connection.exec_driver_sql("SELECT 1")
            assert len(probes) == 3
            assert created[-1].closed
    finally:
        engine.dispose()
    assert all(raw.closed for raw in created)


def test_connect_errors_do_not_expose_driver_chain(monkeypatch):
    module = importlib.import_module("pit_research_lab.infrastructure.database.engine")

    def fail(**kwargs):
        raise RuntimeError("secret-password-bearing-driver-error")

    monkeypatch.setattr(module.psycopg, "connect", fail)
    engine = create_database_engine(parse_config(config_values(), "test"))
    try:
        with pytest.raises(PersistenceError) as caught:
            engine.connect()
        assert "secret" not in str(caught.value)
        assert caught.value.__suppress_context__
    finally:
        engine.dispose()


def test_no_unguarded_session_or_migration_connection():
    config = parse_config(config_values(), "test")
    engine = sqlalchemy_create_engine("sqlite://")
    try:
        with pytest.raises(PersistenceError):
            create_session_factory(engine)
        with engine.connect() as connection, pytest.raises(PersistenceError):
            require_guarded_connection(connection, config, "migration")
    finally:
        engine.dispose()
