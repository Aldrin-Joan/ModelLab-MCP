"""Repository for evaluation metrics recording and cross-experiment comparison."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ml_mcp.infrastructure.postgres.models import ExperimentOrm, MetricOrm


class MetricRepository:
    """Tenant-scoped data access for experiment evaluation metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_metrics(self, metrics: list[MetricOrm]) -> list[MetricOrm]:
        self.session.add_all(metrics)
        await self.session.flush()
        return metrics

    async def get_metrics(
        self,
        tenant_id: str,
        experiment_id: str,
        split: str | None = None,
    ) -> list[MetricOrm]:
        stmt = (
            select(MetricOrm)
            .join(ExperimentOrm, MetricOrm.experiment_id == ExperimentOrm.id)
            .where(ExperimentOrm.tenant_id == tenant_id, MetricOrm.experiment_id == experiment_id)
        )
        if split:
            stmt = stmt.where(MetricOrm.split == split)
        stmt = stmt.order_by(MetricOrm.metric_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def compare_metrics(
        self,
        tenant_id: str,
        experiment_ids: list[str],
    ) -> dict[str, dict[str, float]]:
        """Return {experiment_id: {metric_name: metric_value}} across authorized experiments."""
        if not experiment_ids:
            return {}

        stmt = (
            select(MetricOrm)
            .join(ExperimentOrm, MetricOrm.experiment_id == ExperimentOrm.id)
            .where(
                ExperimentOrm.tenant_id == tenant_id,
                MetricOrm.experiment_id.in_(experiment_ids),
                MetricOrm.split == "validation",
            )
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        comparison: dict[str, dict[str, float]] = {eid: {} for eid in experiment_ids}
        for row in rows:
            comparison[row.experiment_id][row.metric_name] = row.metric_value
        return comparison
