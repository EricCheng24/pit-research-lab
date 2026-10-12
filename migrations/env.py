"""Independent explicit migration entry point; same guarded connection owns all work."""

from pathlib import Path

from alembic import context
from sqlalchemy import MetaData

from pit_research_lab.infrastructure.database.config import (
    PersistenceError,
    load_config,
    select_target,
)
from pit_research_lab.infrastructure.database.engine import (
    create_database_engine,
    require_guarded_connection,
)


def run_migrations() -> None:
    settings = context.config
    args = context.get_x_argument()
    if len(args) != 1 or args[0] not in ("target=dev", "target=test"):
        raise PersistenceError("Alembic requires exactly -x target=dev|test.")
    target = select_target(args[0].partition("=")[2])
    operation = settings.attributes.get("operation")
    if settings.cmd_opts is not None and getattr(settings.cmd_opts, "cmd", None):
        operation = settings.cmd_opts.cmd[0].__name__
    if operation not in ("upgrade", "current", "downgrade"):
        raise PersistenceError("Only deliberate upgrade/current and test downgrade are supported.")
    if target == "dev" and operation == "downgrade":
        raise PersistenceError("Dev downgrade/reset is excluded; dev storage retained.")
    if context.is_offline_mode() or settings.get_main_option("sqlalchemy.url"):
        raise PersistenceError("Offline SQL and URL overrides are unsupported.")
    root = Path(__file__).resolve().parents[1]
    config = load_config(target, root)

    def migrate(connection):
        require_guarded_connection(connection, config, "migration")
        print(
            f"Alembic verified target={target}, database={config.database}, role={config.role('migration')}."
        )
        context.configure(
            connection=connection,
            target_metadata=MetaData(),
            version_table_schema="public",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    existing = settings.attributes.get("connection")
    if existing is not None:
        migrate(existing)
    else:
        engine = create_database_engine(config, "migration")
        try:
            with engine.connect() as connection:
                migrate(connection)
        finally:
            engine.dispose()


try:
    run_migrations()
except PersistenceError as error:
    # SystemExit prevents Python/Alembic from displaying driver chains or configuration locals.
    raise SystemExit(str(error)) from None
