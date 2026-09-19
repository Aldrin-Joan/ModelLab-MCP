"""Sliding window distributed rate limiter using Redis sorted sets and atomic Lua script."""

import time
from collections import defaultdict
from dataclasses import dataclass

from redis.asyncio import Redis

from ml_mcp.infrastructure.redis.client import RedisManager, get_redis_manager

LUA_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

local window_start = now - window_seconds

-- 1. Remove entries older than window_start
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- 2. Count existing entries
local current_count = redis.call('ZCARD', key)

if current_count < limit then
    -- Allowed: add entry and update TTL
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window_seconds * 2))
    local remaining = limit - (current_count + 1)
    return {1, limit, remaining, tostring(now + window_seconds), "0.0"}
else
    -- Denied: find oldest entry to determine reset time
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_time = now + window_seconds
    if oldest and #oldest >= 2 then
        reset_time = tonumber(oldest[2]) + window_seconds
    end
    local retry_after = reset_time - now
    if retry_after < 0 then
        retry_after = 0
    end
    return {0, limit, 0, tostring(reset_time), tostring(retry_after)}
end
"""


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch_seconds: float
    retry_after_seconds: float


class SlidingWindowRateLimiter:
    """Sliding-window rate limiter ensuring atomic Lua script execution across all tool tiers."""

    def __init__(self, redis_manager: RedisManager | None = None) -> None:
        self.redis_mgr = redis_manager or get_redis_manager()
        # In-memory fallback for testing or when Redis is unavailable
        self._local_history: dict[str, list[float]] = defaultdict(list)

    async def check_rate_limit(
        self,
        identifier: str,
        category: str = "default",
        limit: int = 60,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """Check and record a rate limit hit atomically using Redis Lua script.

        Returns:
            RateLimitResult with allowed status, remaining tokens, and reset epoch.
        """
        key = f"ratelimit:{category}:{identifier}"
        now = time.time()
        member = f"{now}:{time.time_ns()}"
        window_start = now - window_seconds

        try:
            client: Redis = self.redis_mgr.client
            result = await client.eval(
                LUA_RATE_LIMIT_SCRIPT,
                1,
                key,
                str(now),
                str(window_seconds),
                str(limit),
                member,
            )
            allowed = bool(result[0])
            limit_val = int(result[1])
            remaining_val = int(result[2])
            reset_epoch = float(result[3])
            retry_after = float(result[4])
            return RateLimitResult(
                allowed=allowed,
                limit=limit_val,
                remaining=remaining_val,
                reset_epoch_seconds=reset_epoch,
                retry_after_seconds=retry_after,
            )

        except Exception:
            # In-memory fallback if Redis is offline/unconfigured in testing
            history = self._local_history[key]
            valid = [ts for ts in history if ts > window_start]
            self._local_history[key] = valid

            if len(valid) >= limit:
                reset_time = valid[0] + window_seconds if valid else now + window_seconds
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
                remaining=max(0, limit - len(valid)),
                reset_epoch_seconds=now + window_seconds,
                retry_after_seconds=0.0,
            )
