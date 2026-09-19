"""Experiment MCP tool handlers."""

from typing import Any

from ml_mcp.domain.errors import (
    ExperimentNotCancellableError,
    ResourceNotFoundError,
)
from ml_mcp.domain.policies import Principal, Scope, validate_tenant_access
from ml_mcp.domain.value_objects import (
    EvaluationConfig,
    ExperimentSpec,
    TaskType,
)
from ml_mcp.infrastructure.postgres.base import generate_uuid7
from ml_mcp.infrastructure.postgres.models import ExperimentOrm, OutboxEventOrm
from ml_mcp.infrastructure.postgres.repositories.experiments import ExperimentRepository
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

    spec = ExperimentSpec(
        tenant_id=principal.tenant_id,
        project_id=project_id,
        dataset_version_id=dataset_version_id,
        model_version_id=model_version_id,
        task_type=TaskType(task_type),
        target_column=target_column,
        feature_columns=feature_columns,
        evaluation_config=EvaluationConfig(
            primary_metric=primary_metric,
            additional_metrics=additional_metrics or [],
        ),
        hyperparameters=hyperparameters or {},
        random_seed=random_seed,
        idempotency_key=idempotency_key,
        created_by=principal.principal_id,
    )

    async with get_db_manager().session() as sess:
        repo = ExperimentRepository(sess)

        # Idempotency check
        if idempotency_key:
            existing = await repo.get_by_idempotency_key(principal.tenant_id, project_id, idempotency_key)
            if existing:
                return {
                    "experiment_id": existing.id,
                    "status": existing.status,
                    "idempotent_replay": True,
                    "created_at": existing.created_at.isoformat(),
                }

        experiment_id = generate_uuid7()
        exp_orm = ExperimentOrm(
            id=experiment_id,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            model_version_id=model_version_id,
            spec_json=spec.model_dump(),
            status="QUEUED",
            idempotency_key=idempotency_key,
            created_by=principal.principal_id,
        )

        outbox_event = OutboxEventOrm(
            id=generate_uuid7(),
            event_type="EXPERIMENT_SUBMITTED",
            aggregate_type="EXPERIMENT",
            aggregate_id=experiment_id,
            payload_json={
                "experiment_id": experiment_id,
                "tenant_id": principal.tenant_id,
                "project_id": project_id,
            },
        )

        await repo.create_experiment(exp_orm, initial_outbox_event=outbox_event)

        return {
            "experiment_id": experiment_id,
            "status": "QUEUED",
            "idempotent_replay": False,
            "task_type": task_type,
            "target_column": target_column,
            "created_at": exp_orm.created_at.isoformat(),
        }


async def handle_get_experiment(experiment_id: str, principal: Principal) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        repo = ExperimentRepository(sess)
        exp = await repo.get_experiment(principal.tenant_id, experiment_id)
        if not exp:
            raise ResourceNotFoundError("Experiment", experiment_id)

        latest_run = exp.runs[0] if exp.runs else None
        return {
            "experiment_id": exp.id,
            "project_id": exp.project_id,
            "status": exp.status,
            "spec": exp.spec_json,
            "runs_count": len(exp.runs),
            "latest_run_status": latest_run.status if latest_run else None,
            "metrics_count": len(exp.metrics),
            "artifacts_count": len(exp.artifacts),
            "created_at": exp.created_at.isoformat(),
            "updated_at": exp.updated_at.isoformat(),
        }


async def handle_cancel_experiment(experiment_id: str, principal: Principal) -> dict[str, Any]:
    principal.enforce_permission(Scope.EXPERIMENTS_CANCEL)
    async with get_db_manager().session() as sess:
        repo = ExperimentRepository(sess)
        exp = await repo.get_experiment(principal.tenant_id, experiment_id)
        if not exp:
            raise ResourceNotFoundError("Experiment", experiment_id)

        if exp.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            raise ExperimentNotCancellableError(experiment_id, exp.status)

        await repo.update_status(principal.tenant_id, experiment_id, "CANCELLED")
        return {
            "experiment_id": experiment_id,
            "status": "CANCELLED",
            "message": f"Experiment {experiment_id} successfully cancelled.",
        }


async def handle_list_experiments(
    principal: Principal,
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    principal.enforce_permission(Scope.EXPERIMENTS_READ)
    async with get_db_manager().session() as sess:
        repo = ExperimentRepository(sess)
        experiments = await repo.list_experiments(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [
            {
                "experiment_id": e.id,
                "project_id": e.project_id,
                "status": e.status,
                "primary_metric": e.spec_json.get("evaluation_config", {}).get("primary_metric"),
                "created_at": e.created_at.isoformat(),
            }
            for e in experiments
        ]
