"""Tenant isolation and project boundary enforcement."""

from ml_mcp.domain.errors import AuthorizationDeniedError
from ml_mcp.domain.policies.rbac import Principal, Role


def validate_tenant_access(
    principal: Principal,
    resource_tenant_id: str,
    resource_project_id: str | None = None,
) -> None:
    """Validate that the authenticated principal is authorized to access resources belonging to a given tenant and project.

    Raises:
        AuthorizationDeniedError: if cross-tenant or unauthorized cross-project access is detected.
    """
    if principal.role == Role.ADMIN:
        return

    # Tenant boundary enforcement: strictly forbidden to touch another tenant's data
    if principal.tenant_id != resource_tenant_id:
        raise AuthorizationDeniedError(
            f"Cross-tenant access forbidden: principal belongs to '{principal.tenant_id}', resource belongs to '{resource_tenant_id}'",
            details={
                "principal_tenant": principal.tenant_id,
                "resource_tenant": resource_tenant_id,
            },
        )

    # Project boundary enforcement: if principal has restricted project_ids, check membership
    if resource_project_id is not None and principal.project_ids:
        if resource_project_id not in principal.project_ids:
            raise AuthorizationDeniedError(
                f"Principal '{principal.principal_id}' does not have access to project '{resource_project_id}'",
                details={
                    "allowed_projects": principal.project_ids,
                    "requested_project": resource_project_id,
                },
            )
