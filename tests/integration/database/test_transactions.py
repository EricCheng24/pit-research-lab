"""Tiny fixtures prove caller-owned transactions on distinct backend connections."""

import pytest
from sqlalchemy import insert, select

from pit_research_lab.infrastructure.database.engine import create_session_factory

pytestmark = pytest.mark.integration


def test_commit_visibility_and_uncommitted_isolation(runtime, scratch):
    with runtime.connect() as writer, runtime.connect() as reader:
        assert (
            writer.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
            != reader.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
        )
        writer.rollback()
        reader.rollback()
        transaction = writer.begin()
        writer.execute(insert(scratch).values(id=1))
        assert reader.execute(select(scratch)).all() == []
        reader.rollback()  # Fresh transaction/read snapshot after commit.
        transaction.commit()
        assert reader.execute(select(scratch.c.id)).scalars().all() == [1]


def test_session_atomic_rollback_and_commit(runtime, scratch):
    sessions = create_session_factory(runtime)
    with pytest.raises(RuntimeError, match="injected"):
        with sessions.begin() as session:
            session.execute(insert(scratch).values(id=1))
            session.execute(insert(scratch).values(id=2))
            raise RuntimeError("injected")
    with runtime.connect() as reader:
        assert reader.execute(select(scratch)).all() == []
    with sessions.begin() as session:
        session.execute(insert(scratch).values(id=3))
    with runtime.connect() as reader:
        assert reader.execute(select(scratch.c.id)).scalars().all() == [3]
