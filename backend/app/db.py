from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

settings = get_settings()


def normalize_database_url(url: str) -> str:
    """Accepts the plain postgres:// URLs that hosting platforms hand out.

    SQLAlchemy needs the driver in the scheme, so point them at psycopg (v3).
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


database_url = normalize_database_url(settings.database_url)
is_sqlite = database_url.startswith("sqlite")

engine = create_engine(
    database_url,
    connect_args=(
        {"check_same_thread": False}
        if is_sqlite
        # psycopg prepares statements it sees often. Through a transaction
        # pooler (Neon's "-pooler" host is PgBouncer) the next query can land
        # on a connection where that statement doesn't exist, so turn it off.
        else {"prepare_threshold": None}
    ),
    # Managed Postgres (and Neon when it scales to zero) drops idle
    # connections; check one before reusing it.
    pool_pre_ping=not is_sqlite,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UtcDateTime(TypeDecorator[datetime]):
    """Stores UTC and always returns timezone-aware values.

    SQLite drops the zone, so without this the API would send times like
    "2026-11-13T09:00:00" that browsers read as local time.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
