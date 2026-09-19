"""Repository for Outbox event lifecycle management."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ml_mcp.infrastructure.postgres.base import utc_now
from ml_mcp.infrastructure.postgres.models import OutboxEventOrm


class OutboxRepository:
    """Operations for polling and updating transactional outbox events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch_pending(self, limit: int = 50) -> list[OutboxEventOrm]:
        """Fetch pending outbox events scheduled for delivery."""
        stmt = (
            select(OutboxEventOrm)
            .where(
                OutboxEventOrm.status == "PENDING",
                OutboxEventOrm.scheduled_at <= utc_now(),
            )
            .order_by(OutboxEventOrm.scheduled_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_delivered(self, event_id: str) -> bool:
        stmt = (
            update(OutboxEventOrm)
            .where(OutboxEventOrm.id == event_id)
            .values(status="DELIVERED", processed_at=utc_now())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def mark_failed(self, event_id: str, retry_count: int, max_retries: int = 5) -> bool:
        new_status = "FAILED" if retry_count >= max_retries else "PENDING"
        stmt = (
            update(OutboxEventOrm)
            .where(OutboxEventOrm.id == event_id)
            .values(status=new_status, retry_count=retry_count)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
