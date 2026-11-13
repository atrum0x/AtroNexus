"""Brings the database schema up to date. The app calls upgrade() on startup.

Databases created before migrations existed (by Base.metadata.create_all) have
the tables but no alembic_version table. Those are stamped at 0001, the
migration that matches that original schema, and then upgraded normally.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db import engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
BASELINE = "0001"


def _config(connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["connection"] = connection
    config.attributes["from_app"] = True
    return config


def upgrade() -> None:
    with engine.begin() as connection:
        config = _config(connection)
        has_tables = "users" in inspect(connection).get_table_names()
        # None when alembic_version is missing or empty.
        current = MigrationContext.configure(connection).get_current_revision()
        if has_tables and current is None:
            command.stamp(config, BASELINE)
        command.upgrade(config, "head")
