"""Transactional Outbox processor dispatching experiment events to the task queue."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ml_mcp.infrastructure.postgres.repositories.outbox import OutboxRepository
from ml_mcp.infrastructure.queue.task_queue import RedisTaskQueue

logger = logging.getLogger(__name__)


class OutboxProcessor:
    """Polls transactional outbox and guarantees reliable message delivery to Redis task queue."""

    def __init__(
        self,
        session: AsyncSession,
        task_queue: RedisTaskQueue | None = None,
        max_retries: int = 5,
    ) -> None:
        self.session = session
        self.repo = OutboxRepository(session)
        self.queue = task_queue or RedisTaskQueue()
        self.max_retries = max_retries

    async def process_batch(self, limit: int = 50) -> int:
        """Process scheduled pending outbox events and dispatch them to the worker queue."""
        events = await self.repo.fetch_pending(limit=limit)
        delivered_count = 0

        for event in events:
            try:
                payload = event.payload_json
                experiment_id = payload.get("experiment_id", event.aggregate_id)
                tenant_id = payload.get("tenant_id", "system")

                # Push to Redis queue
                await self.queue.enqueue(
                    experiment_id=experiment_id,
                    tenant_id=tenant_id,
                    payload=payload,
                )

                # Mark delivered in outbox table
                await self.repo.mark_delivered(event.id)
                delivered_count += 1
                logger.info(
                    "Successfully dispatched outbox event %s for experiment %s",
                    event.id,
                    experiment_id,
                )

            except Exception as exc:
                new_retry = event.retry_count + 1
                logger.error(
                    "Failed to dispatch outbox event %s (attempt %d/%d): %s",
                    event.id,
                    new_retry,
                    self.max_retries,
                    exc,
                )
                await self.repo.mark_failed(
                    event.id, retry_count=new_retry, max_retries=self.max_retries
                )

        return delivered_count
