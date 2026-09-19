"""Project MCP tool handlers."""

from typing import Any

from ml_mcp.application.projects.service import ProjectService
from ml_mcp.domain.policies import Principal, Scope
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_create_project(
    name: str,
    principal: Principal,
    description: str = "",
) -> dict[str, Any]:
    """Handle create_project tool call."""
    principal.enforce_permission(Scope.PROJECTS_WRITE)
    async with get_db_manager().session() as sess:
        service = ProjectService(sess)
        return await service.create_project(
            tenant_id=principal.tenant_id,
            name=name,
            description=description,
        )


async def handle_list_projects(
    principal: Principal,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Handle list_projects tool call."""
    principal.enforce_permission(Scope.PROJECTS_READ)
    async with get_db_manager().session() as sess:
        service = ProjectService(sess)
        return await service.list_projects(
            tenant_id=principal.tenant_id,
            limit=limit,
            offset=offset,
        )
