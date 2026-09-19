"""Repository for immutable audit log records."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ml_mcp.infrastructure.postgres.models import AuditEventOrm


class AuditRepository:
    """Append-only audit trail repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(self, event: AuditEventOrm) -> AuditEventOrm:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventOrm]:
        stmt = (
            select(AuditEventOrm)
            .where(AuditEventOrm.tenant_id == tenant_id)
            .order_by(AuditEventOrm.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
