"""Experiment MCP tool handlers."""

from typing import Any

from ml_mcp.application.experiments.service import ExperimentService
from ml_mcp.domain.policies import Principal, Scope, validate_tenant_access
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_create_experiment(
    project_id: str,
    dataset_version_id: str,
    model_version_id: str,
    task_type: str,
    target_column: str,
    principal: Principal,
    feature_columns: list[str] | None = None,
    primary_metric: str = "roc_auc",
    additional_metrics: list[str] | None = None,
    hyperparameters: dict[str, Any] | None = None,
    random_seed: int = 42,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_CREATE)
    validate_tenant_access(principal, principal.tenant_id, project_id)

    async with get_db_manager().session() as sess:
        service = ExperimentService(sess)
        return await service.create_experiment(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            model_version_id=model_version_id,
            task_type=task_type,
            target_column=target_column,
            principal_id=principal.principal_id,
            feature_columns=feature_columns,
            primary_metric=primary_metric,
            additional_metrics=additional_metrics,
            hyperparameters=hyperparameters,
            random_seed=random_seed,
            idempotency_key=idempotency_key,
        )


async def handle_get_experiment(experiment_id: str, principal: Principal) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        service = ExperimentService(sess)
        return await service.get_experiment(principal.tenant_id, experiment_id)


async def handle_cancel_experiment(experiment_id: str, principal: Principal) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_CANCEL)
    async with get_db_manager().session() as sess:
        service = ExperimentService(sess)
        return await service.cancel_experiment(principal.tenant_id, experiment_id)


async def handle_list_experiments(
    principal: Principal,
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        service = ExperimentService(sess)
        return await service.list_experiments(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
        )
