"""Durable task queue implementation backed by Redis list/streams with local queue fallback."""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

from ml_mcp.config import Settings, get_settings
from ml_mcp.infrastructure.postgres.base import generate_uuid7
from ml_mcp.infrastructure.redis.client import RedisManager, get_redis_manager

logger = logging.getLogger(__name__)


@dataclass
class TaskMessage:
    """Message payload transmitted from Outbox processor to isolated ML worker."""

    task_id: str
    experiment_id: str
    tenant_id: str
    payload: dict[str, Any]
    created_at: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data_str: str) -> "TaskMessage":
        data = json.loads(data_str)
        return cls(**data)


class RedisTaskQueue:
    """Reliable Redis-backed queue for orchestrating ML worker tasks."""

    def __init__(
        self,
        redis_manager: RedisManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.redis_mgr = redis_manager or get_redis_manager()
        self.queue_name = self.settings.redis.task_queue_name
        # In-memory queue fallback for isolated testing
        self._local_queue: asyncio.Queue[TaskMessage] = asyncio.Queue()

    async def enqueue(
        self,
        experiment_id: str,
        tenant_id: str,
        payload: dict[str, Any],
    ) -> str:
        """Enqueue an experiment task for execution. Returns task_id."""
        task_id = generate_uuid7()
        message = TaskMessage(
            task_id=task_id,
            experiment_id=experiment_id,
            tenant_id=tenant_id,
            payload=payload,
            created_at=time.time(),
        )

        try:
            client = self.redis_mgr.client
            await client.rpush(self.queue_name, message.to_json())
            logger.info("Enqueued task %s for experiment %s in Redis", task_id, experiment_id)
        except Exception as exc:
            logger.warning("Redis unavailable, enqueuing to in-memory queue fallback: %s", exc)
            await self._local_queue.put(message)

        return task_id

    async def dequeue(self, timeout_seconds: int = 5) -> TaskMessage | None:
        """Pop the next available task from the queue with timeout."""
        try:
            client = self.redis_mgr.client
            result = await client.blpop(self.queue_name, timeout=timeout_seconds)
            if result:
                _, data_str = result
                return TaskMessage.from_json(data_str)
            return None
        except Exception:
            # Fallback to local queue
            try:
                return await asyncio.wait_for(self._local_queue.get(), timeout=timeout_seconds)
            except TimeoutError:
                return None

    async def get_queue_depth(self) -> int:
        """Return total count of waiting tasks in the queue."""
        try:
            client = self.redis_mgr.client
            return await client.llen(self.queue_name)
        except Exception:
            return self._local_queue.qsize()
