"""Worker daemon dequeuing and executing ML experiment tasks from Redis."""

import asyncio
import logging
import signal
import sys
from typing import Any

from ml_mcp.infrastructure.object_storage.s3 import S3StorageService, get_storage_service
from ml_mcp.infrastructure.postgres.session import DatabaseManager, get_db_manager
from ml_mcp.infrastructure.queue.task_queue import RedisTaskQueue
from ml_mcp.infrastructure.telemetry.logging import configure_logging
from ml_mcp.workers.runner import WorkerRunner

logger = logging.getLogger(__name__)


class WorkerDaemon:
    """Asynchronous background worker daemon executing experiment tasks from Redis."""

    def __init__(
        self,
        task_queue: RedisTaskQueue | None = None,
        storage_service: S3StorageService | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.queue = task_queue or RedisTaskQueue()
        self.storage = storage_service or get_storage_service()
        self.db_mgr = db_manager or get_db_manager()
        self._stop_event = asyncio.Event()
        self._running = False

    def stop(self, *args: Any) -> None:
        """Signal the daemon loop to terminate gracefully."""
        logger.info("Shutdown signal received; initiating graceful termination of worker daemon...")
        self._stop_event.set()

    async def run(self) -> None:
        """Run continuous dequeue-execute loop until stopped."""
        self._running = True
        logger.info("Worker daemon started, polling for experiment tasks...")

        while not self._stop_event.is_set():
            try:
                task_message = await self.queue.dequeue(timeout_seconds=2)
                if task_message is None:
                    continue

                logger.info(
                    "Dequeued task %s for experiment %s (tenant %s)",
                    task_message.task_id,
                    task_message.experiment_id,
                    task_message.tenant_id,
                )

                async with self.db_mgr.session() as session:
                    runner = WorkerRunner(session=session, storage_service=self.storage)
                    try:
                        result = await runner.execute_experiment(
                            experiment_id=task_message.experiment_id,
                            tenant_id=task_message.tenant_id,
                        )
                        logger.info(
                            "Task %s succeeded for experiment %s: %s",
                            task_message.task_id,
                            task_message.experiment_id,
                            result.get("status"),
                        )
                    except Exception as exc:
                        logger.error(
                            "Task %s failed for experiment %s: %s",
                            task_message.task_id,
                            task_message.experiment_id,
                            exc,
                        )

            except asyncio.CancelledError:
                logger.info("Worker daemon cancelled")
                break
            except Exception as exc:
                logger.error("Unexpected error in worker daemon polling loop: %s", exc)
                # Brief sleep on unexpected error to prevent rapid spinning
                await asyncio.sleep(1)

        self._running = False
        logger.info("Worker daemon stopped cleanly.")


def _register_signals(daemon: WorkerDaemon) -> None:
    """Attach graceful shutdown handlers for SIGINT and SIGTERM."""
    loop = asyncio.get_running_loop()
    signals = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        signals.append(signal.SIGTERM)

    for sig in signals:
        try:
            loop.add_signal_handler(sig, daemon.stop)
        except (NotImplementedError, AttributeError):
            # Fallback for platforms without loop.add_signal_handler (e.g. Windows)
            signal.signal(sig, lambda s, f: daemon.stop())


async def main() -> None:
    """Daemon CLI entrypoint."""
    configure_logging()
    daemon = WorkerDaemon()
    _register_signals(daemon)
    await daemon.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
