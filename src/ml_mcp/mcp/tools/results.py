"""Result and artifact MCP tool handlers."""

import io
from typing import Any

import pandas as pd

from ml_mcp.domain.errors import ResourceNotFoundError
from ml_mcp.domain.policies import Principal, Scope
from ml_mcp.infrastructure.object_storage.s3 import get_storage_service
from ml_mcp.infrastructure.postgres.repositories.artifacts import ArtifactRepository
from ml_mcp.infrastructure.postgres.repositories.metrics import MetricRepository
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_get_experiment_metrics(
    experiment_id: str,
    principal: Principal,
    split: str | None = None,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        repo = MetricRepository(sess)
        metrics = await repo.get_metrics(principal.tenant_id, experiment_id, split)

        formatted: dict[str, Any] = {}
        for m in metrics:
            key = f"{m.split}_{m.metric_name}" if not split else m.metric_name
            formatted[key] = m.metric_value

        return {
            "experiment_id": experiment_id,
            "split": split or "all",
            "metrics": formatted,
        }


async def handle_get_experiment_predictions(
    experiment_id: str,
    principal: Principal,
    limit: int = 5,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ARTIFACTS_READ)
    storage = get_storage_service()
    key = storage.get_experiment_artifact_key(principal.tenant_id, experiment_id, "predictions", "predictions.parquet")

    # Generate presigned URL for secure download
    download_url = storage.generate_presigned_get_url(key, expires_in=900)

    # Fetch head rows for immediate preview
    sample_preview = []
    try:
        data = storage.get_object(key)
        df = pd.read_parquet(io.BytesIO(data))
        sample_preview = df.head(limit).to_dict(orient="records")
    except Exception:
        pass

    return {
        "experiment_id": experiment_id,
        "sample_preview": sample_preview,
        "download_url": download_url,
        "expires_in_seconds": 900,
    }


async def handle_list_experiment_artifacts(
    experiment_id: str,
    principal: Principal,
) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.ARTIFACTS_READ)
    async with get_db_manager().session() as sess:
        repo = ArtifactRepository(sess)
        artifacts = await repo.list_artifacts(principal.tenant_id, experiment_id)
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


async def handle_read_experiment_artifact(
    artifact_id: str,
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ARTIFACTS_READ)
    async with get_db_manager().session() as sess:
        repo = ArtifactRepository(sess)
        art = await repo.get_artifact(principal.tenant_id, artifact_id)
        if not art:
            raise ResourceNotFoundError("Artifact", artifact_id)

        storage = get_storage_service()
        # Parse key from s3://bucket/key
        key = art.storage_uri.replace(f"s3://{storage.bucket_name}/", "")
        download_url = storage.generate_presigned_get_url(key, expires_in=900)

        return {
            "artifact_id": art.id,
            "artifact_type": art.artifact_type,
            "size_bytes": art.size_bytes,
            "content_hash": art.content_hash,
            "download_url": download_url,
            "metadata": art.metadata_json,
        }


async def handle_compare_experiments(
    experiment_ids: list[str],
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        repo = MetricRepository(sess)
        comparison = await repo.compare_metrics(principal.tenant_id, experiment_ids)
        return {
            "compared_experiment_ids": experiment_ids,
            "validation_metrics_by_experiment": comparison,
        }
