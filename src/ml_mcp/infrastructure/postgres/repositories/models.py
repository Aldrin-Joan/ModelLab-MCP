"""Repository for registered models and model versions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ml_mcp.infrastructure.postgres.models import ModelOrm, ModelVersionOrm


class ModelRepository:
    """Data access operations for the approved model catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, model_id: str) -> ModelOrm | None:
        stmt = (
            select(ModelOrm).where(ModelOrm.id == model_id).options(selectinload(ModelOrm.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_models(self) -> list[ModelOrm]:
        stmt = select(ModelOrm).options(selectinload(ModelOrm.versions)).order_by(ModelOrm.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_version(self, model_id: str, version: str) -> ModelVersionOrm | None:
        stmt = select(ModelVersionOrm).where(
            ModelVersionOrm.model_id == model_id, ModelVersionOrm.version == version
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(self, version_id: str) -> ModelVersionOrm | None:
        stmt = (
            select(ModelVersionOrm)
            .where(ModelVersionOrm.id == version_id)
            .options(selectinload(ModelVersionOrm.model))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, model_id: str) -> list[ModelVersionOrm]:
        stmt = (
            select(ModelVersionOrm)
            .where(ModelVersionOrm.model_id == model_id)
            .order_by(ModelVersionOrm.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_model(self, model: ModelOrm) -> ModelOrm:
        self.session.add(model)
        await self.session.flush()
        return model

    async def create_version(self, version: ModelVersionOrm) -> ModelVersionOrm:
        self.session.add(version)
        await self.session.flush()
        return version
