"""Result and artifact MCP tool handlers."""

from typing import Any

from ml_mcp.application.artifacts.service import ArtifactService
from ml_mcp.domain.policies import Principal, Scope
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_get_experiment_metrics(
    experiment_id: str,
    principal: Principal,
    split: str | None = None,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        service = ArtifactService(sess)
        return await service.get_metrics(principal.tenant_id, experiment_id, split)


async def handle_get_experiment_predictions(
    experiment_id: str,
    principal: Principal,
    limit: int = 5,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ARTIFACTS_READ)
    async with get_db_manager().session() as sess:
        service = ArtifactService(sess)
        return await service.get_predictions(principal.tenant_id, experiment_id, limit)


async def handle_list_experiment_artifacts(
    experiment_id: str,
    principal: Principal,
) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.ARTIFACTS_READ)
    async with get_db_manager().session() as sess:
        service = ArtifactService(sess)
        return await service.list_artifacts(principal.tenant_id, experiment_id)


async def handle_read_experiment_artifact(
    artifact_id: str,
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ARTIFACTS_READ)
    async with get_db_manager().session() as sess:
        service = ArtifactService(sess)
        return await service.get_artifact(principal.tenant_id, artifact_id)


async def handle_compare_experiments(
    experiment_ids: list[str],
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        service = ArtifactService(sess)
        return await service.compare_experiments(principal.tenant_id, experiment_ids)
