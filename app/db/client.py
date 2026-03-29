"""Async PostgreSQL connection pool using SQLAlchemy + asyncpg."""

import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        # Create SSL context that doesn't verify hostname (needed when
        # connecting via IP to bypass WARP DNS or through pooler)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
            connect_args={"ssl": ssl_ctx},
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def shutdown_db():
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
