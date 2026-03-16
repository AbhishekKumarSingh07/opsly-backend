from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass


def init_db() -> None:
    """Create all tables. Useful for testing with SQLite."""
    # Import all models so they are registered on Base.metadata
    from app.models import (  # noqa: F401
        user,
        site,
        dg_set,
        ticket,
        attendance,
        inventory,
        tender,
        expense,
        client,
        audit_log,
        bulk_import,
    )
    Base.metadata.create_all(bind=engine)
