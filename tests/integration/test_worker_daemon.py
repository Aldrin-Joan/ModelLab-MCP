"""Integration tests for WorkerDaemon lifecycle and task processing."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.session import DatabaseManager
from ml_mcp.infrastructure.queue.task_queue import RedisTaskQueue
from ml_mcp.workers.daemon import WorkerDaemon


@pytest.fixture
async def db():
    db_mgr = DatabaseManager()
    db_mgr.initialize(
        custom_url="sqlite+aiosqlite:///file:daemon_test_db?mode=memory&cache=shared&uri=true"
    )
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_mgr
    await db_mgr.close()


@pytest.mark.asyncio
async def test_daemon_handles_empty_queue_and_stops():
    """Verify daemon polls empty queue with timeout and stops cleanly on stop()."""
    queue = RedisTaskQueue()
    daemon = WorkerDaemon(task_queue=queue)

    daemon_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.1)

    assert daemon._running is True
    daemon.stop()

    await asyncio.wait_for(daemon_task, timeout=3.0)
    assert daemon._running is False


@pytest.mark.asyncio
async def test_daemon_dequeues_and_executes(db: DatabaseManager):
    """Verify daemon dequeues a message and invokes WorkerRunner.execute_experiment."""
    queue = RedisTaskQueue()
    daemon = WorkerDaemon(task_queue=queue, db_manager=db)

    exp_id = generate_uuid7()
    tenant_id = generate_uuid7()

    # Enqueue a task
    await queue.enqueue(
        experiment_id=exp_id,
        tenant_id=tenant_id,
        payload={"experiment_id": exp_id, "tenant_id": tenant_id},
    )

    # Mock WorkerRunner to verify execution without needing full ML run
    with patch("ml_mcp.workers.daemon.WorkerRunner") as MockRunner:
        mock_instance = MockRunner.return_value
        mock_instance.execute_experiment = AsyncMock(return_value={"status": "SUCCEEDED"})

        daemon_task = asyncio.create_task(daemon.run())

        # Wait for task to be processed
        for _ in range(20):
            if mock_instance.execute_experiment.called:
                break
            await asyncio.sleep(0.1)

        daemon.stop()
        await asyncio.wait_for(daemon_task, timeout=3.0)

        mock_instance.execute_experiment.assert_called_once_with(
            experiment_id=exp_id,
            tenant_id=tenant_id,
        )


@pytest.mark.asyncio
async def test_daemon_isolated_task_failure(db: DatabaseManager):
    """Verify exception during a task does not crash the daemon polling loop."""
    queue = RedisTaskQueue()
    daemon = WorkerDaemon(task_queue=queue, db_manager=db)

    exp_id_1 = generate_uuid7()
    exp_id_2 = generate_uuid7()
    tenant_id = generate_uuid7()

    await queue.enqueue(
        experiment_id=exp_id_1,
        tenant_id=tenant_id,
        payload={"experiment_id": exp_id_1, "tenant_id": tenant_id},
    )
    await queue.enqueue(
        experiment_id=exp_id_2,
        tenant_id=tenant_id,
        payload={"experiment_id": exp_id_2, "tenant_id": tenant_id},
    )

    with patch("ml_mcp.workers.daemon.WorkerRunner") as MockRunner:
        mock_instance = MockRunner.return_value
        # First call fails, second call succeeds
        mock_instance.execute_experiment = AsyncMock(
            side_effect=[ValueError("Simulated worker error"), {"status": "SUCCEEDED"}]
        )

        daemon_task = asyncio.create_task(daemon.run())

        # Wait for both tasks to be processed
        for _ in range(30):
            if mock_instance.execute_experiment.call_count >= 2:
                break
            await asyncio.sleep(0.1)

        daemon.stop()
        await asyncio.wait_for(daemon_task, timeout=3.0)

        assert mock_instance.execute_experiment.call_count == 2
