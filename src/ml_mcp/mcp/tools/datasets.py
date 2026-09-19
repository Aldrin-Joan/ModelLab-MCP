"""Dataset MCP tool handlers."""

import base64
from typing import Any

from ml_mcp.application.datasets.service import DatasetService
from ml_mcp.domain.policies import Principal, Scope, validate_tenant_access
from ml_mcp.infrastructure.postgres.session import get_db_manager


async def handle_register_dataset(
    project_id: str,
    name: str,
    description: str,
    format: str,
    data_base64: str,
    principal: Principal,
    version: str = "1.0",
) -> dict[str, Any]:
    principal.enforce_permission(Scope.DATASETS_WRITE)
    validate_tenant_access(principal, principal.tenant_id, project_id)

    raw_bytes = base64.b64decode(data_base64)
    async with get_db_manager().session() as sess:
        service = DatasetService(sess)
        return await service.register_dataset(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            data_format=format,
            raw_bytes=raw_bytes,
            version=version,
        )


async def handle_validate_dataset(
    format: str,
    data_base64: str,
    principal: Principal,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.DATASETS_READ)
    raw_bytes = base64.b64decode(data_base64)
    async with get_db_manager().session() as sess:
        service = DatasetService(sess)
        return await service.validate_only(raw_bytes, format)


async def handle_inspect_dataset(
    dataset_id: str,
    principal: Principal,
    version: str = "1.0",
    sample_rows: int = 5,
) -> dict[str, Any]:
    principal.enforce_permission(Scope.DATASETS_READ)
    async with get_db_manager().session() as sess:
        service = DatasetService(sess)
        return await service.inspect_dataset(
            tenant_id=principal.tenant_id,
            dataset_id=dataset_id,
            version=version,
            sample_rows=sample_rows,
        )
