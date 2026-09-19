"""Repository for experiment artifact metadata."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ml_mcp.infrastructure.postgres.models import ArtifactOrm


class ArtifactRepository:
    """Tenant-scoped data access for persisted analytical and model artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_artifact(self, artifact: ArtifactOrm) -> ArtifactOrm:
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def list_artifacts(self, tenant_id: str, experiment_id: str) -> list[ArtifactOrm]:
        stmt = (
            select(ArtifactOrm)
            .where(ArtifactOrm.tenant_id == tenant_id, ArtifactOrm.experiment_id == experiment_id)
            .order_by(ArtifactOrm.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_artifact(self, tenant_id: str, artifact_id: str) -> ArtifactOrm | None:
        stmt = select(ArtifactOrm).where(
            ArtifactOrm.tenant_id == tenant_id, ArtifactOrm.id == artifact_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
