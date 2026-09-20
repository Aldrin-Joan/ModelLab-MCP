"""Artifact and results application service managing metrics, predictions, and model artifacts."""

import contextlib
import io
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from ml_mcp.domain.errors import ResourceNotFoundError
from ml_mcp.infrastructure.object_storage.s3 import S3StorageService, get_storage_service
from ml_mcp.infrastructure.postgres.repositories.artifacts import ArtifactRepository
from ml_mcp.infrastructure.postgres.repositories.experiments import ExperimentRepository
from ml_mcp.infrastructure.postgres.repositories.metrics import MetricRepository


class ArtifactService:
    """Encapsulates querying of experiment results, metrics, prediction samples, and stored artifacts."""

    def __init__(
        self,
        session: AsyncSession,
        storage_service: S3StorageService | None = None,
    ) -> None:
        self.session = session
        self.storage = storage_service or get_storage_service()
        self.exp_repo = ExperimentRepository(session)
        self.metric_repo = MetricRepository(session)
        self.artifact_repo = ArtifactRepository(session)

    async def get_metrics(
        self,
        tenant_id: str,
        experiment_id: str,
        split: str | None = None,
    ) -> dict[str, Any]:
        """Fetch metrics for an experiment with tenant isolation and anti-enumeration enforcement."""
        exp = await self.exp_repo.get_experiment(tenant_id, experiment_id)
        if not exp:
            raise ResourceNotFoundError("Experiment", experiment_id)

        metrics = await self.metric_repo.get_metrics(tenant_id, experiment_id, split)

        formatted: dict[str, Any] = {}
        for m in metrics:
            key = f"{m.split}_{m.metric_name}" if not split else m.metric_name
            formatted[key] = m.metric_value

        return {
            "experiment_id": experiment_id,
            "split": split or "all",
            "metrics": formatted,
        }

    async def get_predictions(
        self,
        tenant_id: str,
        experiment_id: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Fetch sample predictions and generate presigned download URL with tenant verification."""
        exp = await self.exp_repo.get_experiment(tenant_id, experiment_id)
        if not exp:
            raise ResourceNotFoundError("Experiment", experiment_id)

        key = self.storage.get_experiment_artifact_key(
            tenant_id, experiment_id, "predictions", "predictions.parquet"
        )

        download_url = self.storage.generate_presigned_get_url(key, expires_in=900)

        sample_preview = []
        with contextlib.suppress(Exception):
            data = self.storage.get_object(key)
            df = pd.read_parquet(io.BytesIO(data))
            sample_preview = df.head(limit).to_dict(orient="records")

        return {
            "experiment_id": experiment_id,
            "sample_preview": sample_preview,
            "download_url": download_url,
            "expires_in_seconds": 900,
        }

    async def list_artifacts(
        self,
        tenant_id: str,
        experiment_id: str,
    ) -> list[dict[str, Any]]:
        """List stored artifacts for an experiment after tenant ownership check."""
        exp = await self.exp_repo.get_experiment(tenant_id, experiment_id)
        if not exp:
            raise ResourceNotFoundError("Experiment", experiment_id)

        artifacts = await self.artifact_repo.list_artifacts(tenant_id, experiment_id)
        return [
            {
                "artifact_id": a.id,
                "artifact_type": a.artifact_type,
                "size_bytes": a.size_bytes,
                "content_hash": a.content_hash,
                "created_at": a.created_at.isoformat(),
            }
            for a in artifacts
        ]

    async def get_artifact(
        self,
        tenant_id: str,
        artifact_id: str,
    ) -> dict[str, Any]:
        """Fetch artifact metadata and presigned URL by artifact ID."""
        art = await self.artifact_repo.get_artifact(tenant_id, artifact_id)
        if not art:
            raise ResourceNotFoundError("Artifact", artifact_id)

        prefix = f"s3://{self.storage.bucket_name}/"
        key = (
            art.storage_uri[len(prefix) :]
            if art.storage_uri.startswith(prefix)
            else art.storage_uri
        )
        download_url = self.storage.generate_presigned_get_url(key, expires_in=900)

        return {
            "artifact_id": art.id,
            "artifact_type": art.artifact_type,
            "size_bytes": art.size_bytes,
            "content_hash": art.content_hash,
            "download_url": download_url,
            "metadata": art.metadata_json,
        }

    async def compare_experiments(
        self,
        tenant_id: str,
        experiment_ids: list[str],
    ) -> dict[str, Any]:
        """Compare validation metrics across experiments ensuring caller owns every experiment."""
        for exp_id in experiment_ids:
            exp = await self.exp_repo.get_experiment(tenant_id, exp_id)
            if not exp:
                raise ResourceNotFoundError("Experiment", exp_id)

        comparison = await self.metric_repo.compare_metrics(tenant_id, experiment_ids)
        return {
            "compared_experiment_ids": experiment_ids,
            "validation_metrics_by_experiment": comparison,
        }
