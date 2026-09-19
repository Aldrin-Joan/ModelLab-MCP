"""Discovery MCP tools for models and datasets."""

from typing import Any

from ml_mcp.application.datasets.service import DatasetService
from ml_mcp.application.models.service import ModelService
from ml_mcp.domain.policies import Principal, Scope
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_list_models(principal: Principal) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.MODELS_READ)
    async with get_db_manager().session() as sess:
        service = ModelService(sess)
        return await service.list_models()


async def handle_get_model(model_id: str, principal: Principal) -> dict[str, Any]:
    principal.enforce_permission(Scope.MODELS_READ)
    async with get_db_manager().session() as sess:
        service = ModelService(sess)
        return await service.get_model(model_id)


async def handle_list_model_versions(model_id: str, principal: Principal) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.MODELS_READ)
    async with get_db_manager().session() as sess:
        service = ModelService(sess)
        return await service.list_model_versions(model_id)


async def handle_list_datasets(
    principal: Principal, project_id: str | None = None
) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.DATASETS_READ)
    if project_id:
        from ml_mcp.domain.policies import validate_tenant_access

        validate_tenant_access(principal, principal.tenant_id, project_id)

    async with get_db_manager().session() as sess:
        if project_id:
            from ml_mcp.domain.errors import ResourceNotFoundError
            from ml_mcp.infrastructure.postgres.repositories.projects import ProjectRepository

            proj_repo = ProjectRepository(sess)
            proj = await proj_repo.get_project(principal.tenant_id, project_id)
            if not proj:
                raise ResourceNotFoundError("Project", project_id)

        service = DatasetService(sess)
        return await service.list_datasets(principal.tenant_id, project_id)


async def handle_get_dataset(dataset_id: str, principal: Principal) -> dict[str, Any]:
    principal.enforce_permission(Scope.DATASETS_READ)
    async with get_db_manager().session() as sess:
        service = DatasetService(sess)
        return await service.get_dataset(principal.tenant_id, dataset_id)


async def handle_list_dataset_versions(
    dataset_id: str, principal: Principal
) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.DATASETS_READ)
    async with get_db_manager().session() as sess:
        from ml_mcp.infrastructure.postgres.repositories.datasets import DatasetRepository

        repo = DatasetRepository(sess)
        versions = await repo.list_versions(principal.tenant_id, dataset_id)
        return [
            {
                "version_id": v.id,
                "version": v.version,
                "row_count": v.row_count,
                "column_count": v.column_count,
                "content_hash": v.content_hash,
                "validation_status": v.validation_status,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]
