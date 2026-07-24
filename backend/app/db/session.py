from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 — ensures models are registered on Base before create_all

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Day-1 approach: create tables directly from the models.
    TODO (later day): replace with Alembic migrations once the schema
    stabilizes past the prototyping phase — auto-create is fine for now
    but doesn't give us versioned, reviewable migrations.
    """
    Base.metadata.create_all(bind=engine)
