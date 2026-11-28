"""Only the supplied, already verified F4 migrator connection may run DDL."""

from alembic import context

from pit_research_lab.mvp.f4.d1_profile import Refusal
from pit_research_lab.mvp.f4.d1_store import migration_target

settings = context.config
connection = settings.attributes.get("connection")
if context.is_offline_mode() or settings.get_main_option("sqlalchemy.url"):
    raise Refusal("F4_OFFLINE_MIGRATION_OR_URL_REFUSED")
if settings.attributes.get("operation") not in {"upgrade", "current"}:
    raise Refusal("F4_MIGRATION_COMMAND_REFUSED")
migration_target(connection)
context.configure(
    connection=connection,
    version_table="f4_d1_alembic_version",
    version_table_schema="public",
    transactional_ddl=True,
)
with context.begin_transaction():
    context.run_migrations()
