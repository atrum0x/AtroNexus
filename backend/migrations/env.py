"""Alembic environment. The database comes from the app's settings (DATABASE_URL),
not from alembic.ini, so migrations always run against the same database as the app.

The app runs `upgrade head` on startup (app/migrate.py). To write a migration
after changing a model:

    uv run alembic revision --autogenerate -m "what changed"

then read the generated file and fix anything autogenerate can't know (data
moves, NOT NULL on existing rows).
"""

from logging.config import fileConfig

from alembic import context

import app.models_registry  # noqa: F401  (imports every model so autogenerate sees them)
from app.db import Base, UtcDateTime, engine, is_sqlite

config = context.config

# Only configure logging when run from the command line. When the app runs
# migrations on startup, it must keep uvicorn's logging as it is.
if config.config_file_name is not None and not config.attributes.get("from_app"):
    fileConfig(config.config_file_name)


def render_item(type_: str, obj, autogen_context):
    # Write UtcDateTime as a plain DateTime(timezone=True), so migration files
    # don't import app code that may change later.
    if type_ == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with engine.connect() as connection:
        _run(connection)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_item=render_item,
        # SQLite can't ALTER most things; batch mode copies the table instead.
        render_as_batch=is_sqlite,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
