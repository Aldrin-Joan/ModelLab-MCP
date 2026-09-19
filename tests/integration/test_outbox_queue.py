"""Integration tests for OutboxProcessor and RedisTaskQueue."""

import pytest

from ml_mcp.infrastructure.postgres.base import Base, generate_uuid7
from ml_mcp.infrastructure.postgres.models import OutboxEventOrm
from ml_mcp.infrastructure.postgres.session import DatabaseManager
from ml_mcp.infrastructure.queue.outbox_processor import OutboxProcessor
from ml_mcp.infrastructure.queue.task_queue import RedisTaskQueue


@pytest.fixture
async def db():
    db_mgr = DatabaseManager()
    db_mgr.initialize(
        custom_url="sqlite+aiosqlite:///file:outboxdb?mode=memory&cache=shared&uri=true"
    )
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_mgr
    await db_mgr.close()


@pytest.mark.asyncio
async def test_outbox_dispatch_to_queue(db: DatabaseManager):
    exp_id = generate_uuid7()
    outbox_id = generate_uuid7()

    # 1. Insert pending outbox event
    async with db.session() as sess:
        event = OutboxEventOrm(
            id=outbox_id,
            event_type="EXPERIMENT_SUBMITTED",
            aggregate_type="EXPERIMENT",
            aggregate_id=exp_id,
            payload_json={"experiment_id": exp_id, "tenant_id": "tenant-test", "model": "xgboost"},
            status="PENDING",
        )
        sess.add(event)

    queue = RedisTaskQueue()
    queue.queue_name = f"test:tasks:{exp_id}"
    while await queue.dequeue(timeout_seconds=0.01) is not None:
        pass

    # 2. Process outbox batch
    async with db.session() as sess:
        processor = OutboxProcessor(session=sess, task_queue=queue)
        delivered_count = await processor.process_batch()
        assert delivered_count == 1

    # 3. Verify event is now marked DELIVERED in DB
    async with db.session() as sess:
        from ml_mcp.infrastructure.postgres.repositories.outbox import OutboxRepository

        repo = OutboxRepository(sess)
        pending = await repo.fetch_pending()
        assert len(pending) == 0

    # 4. Dequeue message from task queue
    msg = await queue.dequeue(timeout_seconds=2)
    assert msg is not None
    assert msg.experiment_id == exp_id
    assert msg.payload["model"] == "xgboost"


@pytest.mark.asyncio
async def test_outbox_retry_on_queue_failure(db: DatabaseManager):
    """Verify that queue failure increments retry_count and marks outbox event for retry."""
    from unittest.mock import AsyncMock

    from ml_mcp.infrastructure.postgres.repositories.outbox import OutboxRepository

    exp_id = generate_uuid7()
    outbox_id = generate_uuid7()

    async with db.session() as sess:
        event = OutboxEventOrm(
            id=outbox_id,
            event_type="EXPERIMENT_SUBMITTED",
            aggregate_type="EXPERIMENT",
            aggregate_id=exp_id,
            payload_json={"experiment_id": exp_id, "tenant_id": "tenant-test"},
            status="PENDING",
            retry_count=0,
        )
        sess.add(event)

    failing_queue = RedisTaskQueue()
    failing_queue.enqueue = AsyncMock(side_effect=RuntimeError("Simulated Redis outage"))

    async with db.session() as sess:
        processor = OutboxProcessor(session=sess, task_queue=failing_queue, max_retries=3)
        delivered_count = await processor.process_batch()
        assert delivered_count == 0

    async with db.session() as sess:
        repo = OutboxRepository(sess)
        events = await repo.fetch_pending()
        assert len(events) == 1
        assert events[0].retry_count == 1
        assert events[0].status == "PENDING"


@pytest.mark.asyncio
async def test_outbox_dead_letter_on_max_retries(db: DatabaseManager):
    """Verify that exceeding max_retries marks outbox event as FAILED / DEAD_LETTER."""
    from unittest.mock import AsyncMock

    from ml_mcp.infrastructure.postgres.repositories.outbox import OutboxRepository

    exp_id = generate_uuid7()
    outbox_id = generate_uuid7()

    async with db.session() as sess:
        event = OutboxEventOrm(
            id=outbox_id,
            event_type="EXPERIMENT_SUBMITTED",
            aggregate_type="EXPERIMENT",
            aggregate_id=exp_id,
            payload_json={"experiment_id": exp_id, "tenant_id": "tenant-test"},
            status="PENDING",
            retry_count=2,  # Already at attempt 2 of 3
        )
        sess.add(event)

    failing_queue = RedisTaskQueue()
    failing_queue.enqueue = AsyncMock(side_effect=RuntimeError("Permanent queue failure"))

    async with db.session() as sess:
        processor = OutboxProcessor(session=sess, task_queue=failing_queue, max_retries=3)
        delivered_count = await processor.process_batch()
        assert delivered_count == 0

    async with db.session() as sess:
        repo = OutboxRepository(sess)
        pending = await repo.fetch_pending()
        assert len(pending) == 0  # No longer pending; moved to FAILED/DEAD_LETTER
