"""Tenant isolation and project boundary enforcement."""

from ml_mcp.domain.errors import AuthorizationDeniedError, ResourceNotFoundError
from ml_mcp.domain.policies.rbac import Principal


def validate_tenant_access(
    principal: Principal,
    resource_tenant_id: str,
    resource_project_id: str | None = None,
) -> None:
    """Validate that the authenticated principal is authorized to access resources belonging to a given tenant and project.

    Raises:
        ResourceNotFoundError: if cross-tenant access is detected (anti-enumeration: 404 with 0 foreign tenant leaks).
        AuthorizationDeniedError: if unauthorized cross-project access within the same tenant is detected.
    """
    # Tenant boundary enforcement: cross-tenant access returns 404 with zero foreign tenant leakage
    if principal.tenant_id != resource_tenant_id:
        raise ResourceNotFoundError("Resource", resource_project_id or "requested")

    # Project boundary enforcement: if principal has restricted project_ids, check membership
    if (
        resource_project_id is not None
        and principal.project_ids
        and resource_project_id not in principal.project_ids
    ):
        raise AuthorizationDeniedError(
            f"Principal '{principal.principal_id}' does not have access to project '{resource_project_id}'",
            details={
                "allowed_projects": principal.project_ids,
                "requested_project": resource_project_id,
            },
        )
