"""Root pytest fixtures ensuring test isolation and hermetic teardown."""

import os
from collections.abc import AsyncGenerator

import pytest

from ml_mcp.config import get_settings
from ml_mcp.infrastructure.object_storage import s3
from ml_mcp.infrastructure.postgres import session
from ml_mcp.infrastructure.redis import client
from ml_mcp.server.context import set_current_principal


@pytest.fixture(autouse=True)
def hermetic_environment():
    """Ensure testing environment configuration and reset LRU cache."""
    old_env = os.environ.get("APP_ENV")
    os.environ["APP_ENV"] = "testing"
    get_settings.cache_clear()
    yield
    if old_env is not None:
        os.environ["APP_ENV"] = old_env
    else:
        os.environ.pop("APP_ENV", None)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def hermetic_storage():
    """Reset S3 in-memory store before and after each test."""
    if s3._storage_service is not None:
        s3._storage_service._memory_store.clear()
        s3._storage_service = None
    yield
    if s3._storage_service is not None:
        s3._storage_service._memory_store.clear()
        s3._storage_service = None


@pytest.fixture(autouse=True)
def hermetic_principal_context():
    """Ensure contextvars do not leak principals across tests."""
    set_current_principal(None)
    yield
    set_current_principal(None)


@pytest.fixture(autouse=True)
async def hermetic_database() -> AsyncGenerator[None]:
    """Dispose database connection pool and reset singleton after each test."""
    yield
    db_mgr = session.get_db_manager()
    await db_mgr.close()
    session._db_manager = None


@pytest.fixture(autouse=True)
async def hermetic_redis() -> AsyncGenerator[None]:
    """Close Redis client pool and reset singleton before and after each test."""
    if client._redis_manager is not None:
        try:
            await client._redis_manager.client.flushdb()
        except (RuntimeError, Exception):
            pass
    yield
    if client._redis_manager is not None:
        try:
            await client._redis_manager.client.flushdb()
            await client._redis_manager.close()
        except (RuntimeError, Exception):
            pass
        finally:
            client._redis_manager = None


@pytest.fixture(autouse=True)
def hermetic_middleware():
    """Reset security pipeline singleton and rate limiter state after each test."""
    yield
    from ml_mcp.server import middleware

    middleware._security_pipeline = None
