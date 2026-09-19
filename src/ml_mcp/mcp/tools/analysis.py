"""Analysis MCP tool handlers."""

from typing import Any
from ml_mcp.application.analysis.service import AnalysisService
from ml_mcp.domain.policies import Principal, Scope
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_analyze_experiment(
    experiment_id: str,
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ANALYSIS_CREATE)
    async with get_db_manager().session() as sess:
        service = AnalysisService(sess)
        return await service.analyze_experiment(principal.tenant_id, experiment_id)


async def handle_analyze_model_errors(
    experiment_id: str,
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ANALYSIS_CREATE)
    async with get_db_manager().session() as sess:
        service = AnalysisService(sess)
        return await service.analyze_model_errors(principal.tenant_id, experiment_id)


async def handle_check_experiment_validity(
    experiment_id: str,
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.ANALYSIS_CREATE)
    async with get_db_manager().session() as sess:
        service = AnalysisService(sess)
        return await service.check_experiment_validity(principal.tenant_id, experiment_id)
