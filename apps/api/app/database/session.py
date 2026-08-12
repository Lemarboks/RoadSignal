from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings


@lru_cache
def engine():
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 5},
    )


@lru_cache
def session_factory():
    return sessionmaker(bind=engine(), expire_on_commit=False, autoflush=False)


def database_session() -> Generator[Session, None, None]:
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


def database_ready() -> bool:
    if settings.storage_backend != "mysql":
        return False
    try:
        with engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
