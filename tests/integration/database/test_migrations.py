"""Repeatable serial lifecycle: restore the acceptable starting state (base or head)."""

from argparse import Namespace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

pytestmark = pytest.mark.integration
HEAD = "f13_empty_baseline"


def test_repeatable_empty_baseline(migrator):
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.cmd_opts = Namespace(x=["target=test"])
    assert ScriptDirectory.from_config(config).get_heads() == [HEAD]
    with migrator.connect() as connection:
        config.attributes["connection"] = connection

        def state():
            result = MigrationContext.configure(connection).get_current_heads()
            connection.commit()
            return result

        def invoke(operation, revision=None):
            config.attributes["operation"] = operation
            if revision is None:
                getattr(command, operation)(config)
            else:
                getattr(command, operation)(config, revision)

        starting = state()
        assert starting in ((), (HEAD,)), "Unexpected revision; no migration lifecycle attempted"
        tables_before = set(
            connection.exec_driver_sql(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            ).scalars()
        )
        connection.commit()
        try:
            invoke("upgrade", "head")
            assert state() == (HEAD,)
            invoke("current")
            invoke("downgrade", "base")
            assert state() == ()
            tables_after = set(
                connection.exec_driver_sql(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                ).scalars()
            )
            connection.commit()
            assert tables_after - tables_before <= {"alembic_version"}
            assert not tables_before - tables_after
        finally:
            connection.rollback()
            try:
                current = state()
            except Exception:
                pytest.fail(
                    "Migration revision state unavailable; retain storage and inspect target=test current.",
                    pytrace=False,
                )
            if current not in ((), (HEAD,)):
                pytest.fail(
                    f"Migration recovery refused: actual heads={current!r}; retain test storage.",
                    pytrace=False,
                )
            try:
                invoke("upgrade", "head") if starting else invoke("downgrade", "base")
                assert state() == starting
            except (Exception, SystemExit):
                connection.rollback()
                try:
                    remaining = repr(state())
                except Exception:
                    remaining = "UNAVAILABLE"
                pytest.fail(
                    f"Migration recovery failed; actual heads={remaining}; retain test storage.",
                    pytrace=False,
                )
