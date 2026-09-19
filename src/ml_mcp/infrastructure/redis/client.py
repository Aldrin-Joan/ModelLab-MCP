"""Async Redis connection management."""

import logging
from redis.asyncio import ConnectionPool, Redis
from ml_mcp.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Manages Redis connection pool and async client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None

    def initialize(self, custom_url: str | None = None) -> None:
        redis_url = custom_url or self.settings.redis.url
        self._pool = ConnectionPool.from_url(
            redis_url,
            max_connections=self.settings.redis.max_connections,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=1.0,
        )
        self._client = Redis(connection_pool=self._pool)
        logger.info("Redis client initialized")

    @property
    def client(self) -> Redis:
        if self._client is None:
            self.initialize()
        assert self._client is not None
        return self._client

    async def check_health(self) -> bool:
        """Ping Redis server to assert availability."""
        try:
            return await self.client.ping() is True
        except Exception as exc:
            logger.error("Redis healthcheck failed: %s", exc)
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
        if self._pool is not None:
            await self._pool.disconnect()
        self._client = None
        self._pool = None
        logger.info("Redis connection closed")


_redis_manager: RedisManager | None = None


def get_redis_manager() -> RedisManager:
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager
