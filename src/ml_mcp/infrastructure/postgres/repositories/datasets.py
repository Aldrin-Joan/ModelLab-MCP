"""Repository for dataset and dataset version persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ml_mcp.infrastructure.postgres.models import DatasetOrm, DatasetVersionOrm


class DatasetRepository:
    """Tenant-scoped data access for registered datasets and versions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_dataset(self, dataset: DatasetOrm) -> DatasetOrm:
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def get_dataset(self, tenant_id: str, dataset_id: str) -> DatasetOrm | None:
        stmt = (
            select(DatasetOrm)
            .where(DatasetOrm.tenant_id == tenant_id, DatasetOrm.id == dataset_id)
            .options(selectinload(DatasetOrm.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_datasets(
        self, tenant_id: str, project_id: str | None = None
    ) -> list[DatasetOrm]:
        stmt = select(DatasetOrm).where(DatasetOrm.tenant_id == tenant_id)
        if project_id:
            stmt = stmt.where(DatasetOrm.project_id == project_id)
        stmt = stmt.options(selectinload(DatasetOrm.versions)).order_by(
            DatasetOrm.created_at.desc()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_version(self, version: DatasetVersionOrm) -> DatasetVersionOrm:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_version(
        self, tenant_id: str, dataset_id: str, version: str
    ) -> DatasetVersionOrm | None:
        stmt = (
            select(DatasetVersionOrm)
            .join(DatasetOrm, DatasetVersionOrm.dataset_id == DatasetOrm.id)
            .where(
                DatasetOrm.tenant_id == tenant_id,
                DatasetVersionOrm.dataset_id == dataset_id,
                DatasetVersionOrm.version == version,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(self, tenant_id: str, version_id: str) -> DatasetVersionOrm | None:
        stmt = (
            select(DatasetVersionOrm)
            .join(DatasetOrm, DatasetVersionOrm.dataset_id == DatasetOrm.id)
            .where(
                DatasetOrm.tenant_id == tenant_id,
                DatasetVersionOrm.id == version_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, tenant_id: str, dataset_id: str) -> list[DatasetVersionOrm]:
        stmt = (
            select(DatasetVersionOrm)
            .join(DatasetOrm, DatasetVersionOrm.dataset_id == DatasetOrm.id)
            .where(
                DatasetOrm.tenant_id == tenant_id,
                DatasetVersionOrm.dataset_id == dataset_id,
            )
            .order_by(DatasetVersionOrm.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
