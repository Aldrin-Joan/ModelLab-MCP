"""Repository for experiments, runs, and transactional outbox emission."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ml_mcp.infrastructure.postgres.base import utc_now
from ml_mcp.infrastructure.postgres.models import (
    ExperimentOrm,
    ExperimentRunOrm,
    ModelVersionOrm,
    OutboxEventOrm,
)


class ExperimentRepository:
    """Tenant-scoped data access for experiments and execution runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_experiment(
        self,
        experiment: ExperimentOrm,
        initial_outbox_event: OutboxEventOrm | None = None,
    ) -> ExperimentOrm:
        """Create experiment and optional transactional outbox event atomically."""
        self.session.add(experiment)
        if initial_outbox_event:
            self.session.add(initial_outbox_event)
        await self.session.flush()
        return experiment

    async def get_by_idempotency_key(
        self,
        tenant_id: str,
        project_id: str,
        idempotency_key: str,
    ) -> ExperimentOrm | None:
        stmt = (
            select(ExperimentOrm)
            .where(
                ExperimentOrm.tenant_id == tenant_id,
                ExperimentOrm.project_id == project_id,
                ExperimentOrm.idempotency_key == idempotency_key,
            )
            .options(selectinload(ExperimentOrm.runs))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_experiment(self, tenant_id: str, experiment_id: str) -> ExperimentOrm | None:
        stmt = (
            select(ExperimentOrm)
            .where(ExperimentOrm.tenant_id == tenant_id, ExperimentOrm.id == experiment_id)
            .options(
                selectinload(ExperimentOrm.runs),
                selectinload(ExperimentOrm.metrics),
                selectinload(ExperimentOrm.artifacts),
                selectinload(ExperimentOrm.analysis),
                selectinload(ExperimentOrm.model_version).selectinload(ModelVersionOrm.model),
                selectinload(ExperimentOrm.dataset_version),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_experiments(
        self,
        tenant_id: str,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExperimentOrm]:
        stmt = select(ExperimentOrm).where(ExperimentOrm.tenant_id == tenant_id)
        if project_id:
            stmt = stmt.where(ExperimentOrm.project_id == project_id)
        if status:
            stmt = stmt.where(ExperimentOrm.status == status)
        stmt = (
            stmt.options(selectinload(ExperimentOrm.runs))
            .order_by(ExperimentOrm.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, tenant_id: str, experiment_id: str, new_status: str) -> bool:
        stmt = (
            update(ExperimentOrm)
            .where(ExperimentOrm.tenant_id == tenant_id, ExperimentOrm.id == experiment_id)
            .values(status=new_status, updated_at=utc_now())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def create_run(self, run: ExperimentRunOrm) -> ExperimentRunOrm:
        self.session.add(run)
        await self.session.flush()
        return run

    async def update_run(
        self,
        run_id: str,
        status: str,
        duration_seconds: float | None = None,
        failure_reason: str | None = None,
        end_time: bool = False,
    ) -> bool:
        values: dict[str, Any] = {"status": status}
        if duration_seconds is not None:
            values["duration_seconds"] = duration_seconds
        if failure_reason is not None:
            values["failure_reason"] = failure_reason
        if end_time:
            values["end_time"] = utc_now()

        stmt = update(ExperimentRunOrm).where(ExperimentRunOrm.id == run_id).values(**values)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_latest_run(self, experiment_id: str) -> ExperimentRunOrm | None:
        stmt = (
            select(ExperimentRunOrm)
            .where(ExperimentRunOrm.experiment_id == experiment_id)
            .order_by(ExperimentRunOrm.run_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
