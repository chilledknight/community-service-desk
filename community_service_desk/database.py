"""Database connection and session lifecycle."""

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from community_service_desk.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base for Community Service Desk."""

    pass


def get_engine(database_url: str | None = None):
    settings = get_settings()
    url = database_url or settings.database_url

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        echo=settings.debug,
        future=True,
    )

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables(target_engine=None):
    """Create all defined tables (useful for test harnesses or initial bootstrap)."""
    target = target_engine or engine
    Base.metadata.create_all(bind=target)
