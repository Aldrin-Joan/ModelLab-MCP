"""MCP Resources exposing system metadata and catalog information."""

import json
from typing import Any
from ml_mcp.application.models.service import ModelService
from ml_mcp.domain.policies import Principal, Role
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def read_models_resource() -> str:
    """Read full catalog of approved models (modellab://models)."""
    async with get_db_manager().session() as sess:
        service = ModelService(sess)
        models = await service.list_models()
        return json.dumps(models, indent=2)


async def read_model_details_resource(model_id: str) -> str:
    """Read detailed specification of a model (modellab://models/{model_id})."""
    async with get_db_manager().session() as sess:
        service = ModelService(sess)
        details = await service.get_model(model_id)
        return json.dumps(details, indent=2)


async def read_experiment_metrics_resource(experiment_id: str, tenant_id: str = "default-tenant") -> str:
    """Read metrics for an experiment (modellab://experiments/{experiment_id}/metrics)."""
    async with get_db_manager().session() as sess:
        from ml_mcp.infrastructure.postgres.repositories.metrics import MetricRepository
        repo = MetricRepository(sess)
        metrics = await repo.get_metrics(tenant_id, experiment_id)
        payload = {m.metric_name: m.metric_value for m in metrics}
        return json.dumps(payload, indent=2)
