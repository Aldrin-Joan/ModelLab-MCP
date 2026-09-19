"""Integration test for SlidingWindowRateLimiter."""

import pytest

from ml_mcp.infrastructure.redis.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    from ml_mcp.infrastructure.redis.client import get_redis_manager

    await get_redis_manager().client.flushdb()

    limiter = SlidingWindowRateLimiter()
    # Test 3 requests with limit 5
    for i in range(3):
        res = await limiter.check_rate_limit(
            identifier="test-user-1",
            category="read",
            limit=5,
            window_seconds=60,
        )
        assert res.allowed is True
        assert res.remaining == 5 - (i + 1)


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    from ml_mcp.infrastructure.redis.client import get_redis_manager

    await get_redis_manager().client.flushdb()

    limiter = SlidingWindowRateLimiter()
    # Hit limit 3
    for _ in range(3):
        res = await limiter.check_rate_limit(
            identifier="test-user-blocked",
            category="experiment",
            limit=3,
            window_seconds=60,
        )
        assert res.allowed is True

    # 4th request must be blocked
    blocked = await limiter.check_rate_limit(
        identifier="test-user-blocked",
        category="experiment",
        limit=3,
        window_seconds=60,
    )
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after_seconds > 0.0
