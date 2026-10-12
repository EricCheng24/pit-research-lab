"""Selected-test fixtures only. One local file lock serializes use of this test database."""

import fcntl
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table

from pit_research_lab.infrastructure.database.config import load_config
from pit_research_lab.infrastructure.database.engine import (
    create_database_engine,
    require_guarded_connection,
)


@pytest.fixture(scope="session")
def db_config():
    root = Path(__file__).resolve().parents[3]
    config = load_config("test", root)
    with (root / ".env.test.local").open("rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            pytest.fail(
                "Test database already in use; integration runs must be serial.", pytrace=False
            )
        yield config


@pytest.fixture
def runtime(db_config):
    engine = create_database_engine(db_config)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def migrator(db_config):
    engine = create_database_engine(db_config, "migration")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def scratch(request, migrator, db_config):
    table = Table(
        f"f13_probe_{uuid4().hex}",
        MetaData(),
        Column("id", Integer, primary_key=True),
        schema="public",
    )

    def cleanup():
        with migrator.begin() as connection:
            require_guarded_connection(connection, db_config, "migration")
            table.drop(connection, checkfirst=True)

    # Register exact cleanup before allocation/grant, including partial setup failures.
    request.addfinalizer(cleanup)
    with migrator.begin() as connection:
        require_guarded_connection(connection, db_config, "migration")
        table.create(connection)
        connection.exec_driver_sql(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."{table.name}" '
            f'TO "{db_config.role("runtime")}"'
        )
    return table
