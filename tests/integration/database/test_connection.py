"""Real guarded PostgreSQL identity, role and reconnection evidence."""

from dataclasses import replace
from uuid import uuid4

import pytest

from pit_research_lab.infrastructure.database.config import PersistenceError
from pit_research_lab.infrastructure.database.engine import create_database_engine

pytestmark = pytest.mark.integration


def test_connection_and_reconnect(runtime):
    with runtime.connect() as connection:
        assert connection.exec_driver_sql("SELECT current_database(), current_user").one() == (
            "pitlab_test",
            "pitlab_test_app",
        )
        assert connection.exec_driver_sql("SELECT 1").scalar_one() == 2
        first = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
        connection.rollback()
        connection.invalidate()
        second = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
        assert second != first


def test_wrong_marker_rejected(db_config):
    engine = create_database_engine(replace(db_config, instance_id=str(uuid4())))
    try:
        with pytest.raises(PersistenceError, match="identity/role/privilege mismatch"):
            engine.connect()
    finally:
        engine.dispose()


def test_effective_privileges(runtime, migrator, request):
    forbidden_name = "f13_forbidden_" + uuid4().hex

    def cleanup():
        with migrator.begin() as connection:
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS public."{forbidden_name}"')

    request.addfinalizer(cleanup)
    with runtime.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT has_database_privilege(current_user,current_database(),'CREATE'), "
            "has_database_privilege(current_user,current_database(),'TEMP'), "
            "has_schema_privilege(current_user,'public','CREATE')"
        ).one() == (False, False, False)
        with pytest.raises(PersistenceError, match="SQL failed"):
            connection.exec_driver_sql(f'CREATE TABLE public."{forbidden_name}"(id integer)')
    with migrator.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT has_schema_privilege(current_user,'public','CREATE'), "
            "has_database_privilege(current_user,current_database(),'CREATE')"
        ).one() == (True, False)


def test_actual_wrong_role_rejected(db_config, monkeypatch):
    # Connect safely to the same TEST database with its migrator credential while expecting app.
    # No dev credential or dev SQL is involved.
    import pit_research_lab.infrastructure.database.engine as module

    original = module.psycopg.connect

    def wrong_role(**kwargs):
        kwargs.update(user=db_config.role("migration"), password=db_config.migrator_password)
        return original(**kwargs)

    monkeypatch.setattr(module.psycopg, "connect", wrong_role)
    engine = create_database_engine(db_config)
    try:
        with pytest.raises(PersistenceError, match="identity/role/privilege mismatch"):
            engine.connect()
    finally:
        engine.dispose()
