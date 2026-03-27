"""
Database layer for RuView API Gateway.

- SQLite 기본 (aiosqlite)
- DATABASE_URL env var로 PostgreSQL 전환 가능
  PostgreSQL: postgresql+asyncpg://user:pass@host/db
  SQLite:     sqlite+aiosqlite:///./ruview.db  (기본값)
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ── Base ────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Engine / session factory (lazy-init) ────────────────────────────────────
_engine = None
_async_session_factory = None


def _build_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ruview.db")
    # plain postgresql:// → postgresql+asyncpg://
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    # plain postgres:// (Heroku style)
    elif raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


def get_engine():
    global _engine
    if _engine is None:
        url = _build_url()
        is_sqlite = "sqlite" in url
        kwargs = dict(echo=os.getenv("DB_ECHO", "0") == "1", future=True)
        if not is_sqlite:
            kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
            kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
            kwargs["pool_pre_ping"] = True
        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 또는 직접 호출용 세션 컨텍스트 매니저."""
    factory = get_session_factory()
    session: AsyncSession = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """앱 시작 시 테이블 생성 (존재하면 skip)."""
    from database.models import Base as ModelBase  # noqa: F401 — import to register models
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(ModelBase.metadata.create_all)


async def close_db() -> None:
    """앱 종료 시 엔진 dispose."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


__all__ = [
    "Base",
    "get_engine",
    "get_session_factory",
    "get_db",
    "init_db",
    "close_db",
]
