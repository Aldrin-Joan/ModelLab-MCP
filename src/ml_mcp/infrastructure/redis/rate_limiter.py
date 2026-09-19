"""Sliding window distributed rate limiter using Redis sorted sets."""

import time
from collections import defaultdict
from dataclasses import dataclass

from redis.asyncio import Redis

from ml_mcp.infrastructure.redis.client import RedisManager, get_redis_manager


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch_seconds: float
    retry_after_seconds: float


class SlidingWindowRateLimiter:
    """Sliding-window rate limiter ensuring strict enforcement across all tool tiers."""

    def __init__(self, redis_manager: RedisManager | None = None) -> None:
        self.redis_mgr = redis_manager or get_redis_manager()
        # In-memory fallback for testing or when Redis is unavailable
        self._local_history: dict[str, list[float]] = defaultdict(list)

    async def check_rate_limit(
        self,
        identifier: str,
        category: str,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """Check and record a rate limit hit for a given identifier (e.g. principal_id:tool_name).

        Returns:
            RateLimitResult with allowed status, remaining tokens, and reset epoch.
        """
        key = f"ratelimit:{category}:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        try:
            client: Redis = self.redis_mgr.client
            pipe = client.pipeline()
            # 1. Remove timestamps outside the sliding window
            pipe.zremrangebyscore(key, 0, window_start)
            # 2. Count current hits within window
            pipe.zcard(key)
            # 3. Add current timestamp tentatively (will rollback if over limit)
            member = f"{now}:{time.time_ns()}"
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds * 2)

            results = await pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                # Remove the added hit since it was throttled
                await client.zrem(key, member)
                # Oldest element timestamp determines reset
                oldest = await client.zrange(key, 0, 0, withscores=True)
                reset_time = oldest[0][1] + window_seconds if oldest else now + window_seconds
                retry_after = max(0.0, reset_time - now)

                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_epoch_seconds=reset_time,
                    retry_after_seconds=retry_after,
                )

            remaining = max(0, limit - (current_count + 1))
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_epoch_seconds=now + window_seconds,
                retry_after_seconds=0.0,
            )

        except Exception:
            # In-memory fallback if Redis is offline/unconfigured in testing
            history = self._local_history[key]
            # Prune expired
            valid = [ts for ts in history if ts > window_start]
            self._local_history[key] = valid

            if len(valid) >= limit:
                reset_time = valid[0] + window_seconds
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_epoch_seconds=reset_time,
                    retry_after_seconds=max(0.0, reset_time - now),
                )

            valid.append(now)
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - len(valid),
                reset_epoch_seconds=now + window_seconds,
                retry_after_seconds=0.0,
            )
