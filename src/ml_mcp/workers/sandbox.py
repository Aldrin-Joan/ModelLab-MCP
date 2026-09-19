"""Worker sandboxing and resource boundary enforcement."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar
from ml_mcp.domain.errors import ResourceLimitExceededError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class WorkerSandbox:
    """Safeguards worker execution with wall-clock timeouts and error containment."""

    def __init__(self, timeout_seconds: int = 1800, max_memory_mb: int = 4096) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb

    async def execute(
        self,
        coro_fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute async function wrapped with wall-clock timeout."""
        try:
            return await asyncio.wait_for(coro_fn(*args, **kwargs), timeout=self.timeout_seconds)
        except (asyncio.TimeoutError, TimeoutError) as exc:
            logger.error("Worker execution timed out after %d seconds", self.timeout_seconds)
            raise ResourceLimitExceededError("execution_time", f"{self.timeout_seconds}s", "timeout") from exc
