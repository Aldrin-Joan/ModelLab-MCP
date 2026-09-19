"""Integration test for DatabaseManager and session lifecycle."""

import pytest
from sqlalchemy import text

import ml_mcp.infrastructure.postgres.models  # noqa: F401
from ml_mcp.infrastructure.postgres.base import Base
from ml_mcp.infrastructure.postgres.session import DatabaseManager


@pytest.mark.asyncio
async def test_database_manager_lifecycle():
    db_mgr = DatabaseManager()
    db_mgr.initialize(custom_url="sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared&uri=true")

    # Verify health check succeeds
    is_healthy = await db_mgr.check_health()
    assert is_healthy is True

    # Initialize schema in memory
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Test transactional session commit
    async with db_mgr.session() as sess:
        await sess.execute(
            text("INSERT INTO tenants (id, name, created_at, updated_at) VALUES ('t-1', 'Acme Corp', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
        )

    # Verify query in new session
    async with db_mgr.session() as sess:
        result = await sess.execute(text("SELECT name FROM tenants WHERE id = 't-1'"))
        assert result.scalar() == "Acme Corp"

    # Test rollback on exception
    with pytest.raises(ValueError):
        async with db_mgr.session() as sess:
            await sess.execute(
                text("INSERT INTO tenants (id, name, created_at, updated_at) VALUES ('t-2', 'Beta LLC', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
            )
            raise ValueError("Intentional abort")

    # Verify t-2 was rolled back
    async with db_mgr.session() as sess:
        result = await sess.execute(text("SELECT name FROM tenants WHERE id = 't-2'"))
        assert result.scalar() is None

    await db_mgr.close()
