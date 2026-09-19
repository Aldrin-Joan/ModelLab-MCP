"""Role-Based Access Control (RBAC) and permission scope evaluation."""

from enum import StrEnum

from pydantic import BaseModel, Field

from ml_mcp.domain.errors import AuthorizationDeniedError


class Role(StrEnum):
    """Supported principal roles in ModelLab."""

    VIEWER = "viewer"
    RESEARCHER = "researcher"
    OPERATOR = "operator"
    ADMIN = "admin"


class Scope(StrEnum):
    """Granular permission scopes for ML control plane operations."""

    PROJECTS_READ = "ml:projects:read"
    PROJECTS_WRITE = "ml:projects:write"
    MODELS_READ = "ml:models:read"
    DATASETS_READ = "ml:datasets:read"
    DATASETS_WRITE = "ml:datasets:write"
    EXPERIMENTS_READ = "ml:experiments:read"
    EXPERIMENTS_CREATE = "ml:experiments:create"
    EXPERIMENTS_CANCEL = "ml:experiments:cancel"
    ANALYSIS_CREATE = "ml:analysis:create"
    ARTIFACTS_READ = "ml:artifacts:read"
    WORKER_OPERATE = "ml:worker:operate"
    EXPERIMENT_OVERRIDE = "ml:experiment:override"
    ADMIN = "ml:admin"


# Standard role permissions matrix per Architecture.md section 7
ROLE_PERMISSIONS: dict[Role, set[Scope]] = {
    Role.VIEWER: {
        Scope.PROJECTS_READ,
        Scope.MODELS_READ,
        Scope.DATASETS_READ,
        Scope.EXPERIMENTS_READ,
        Scope.ARTIFACTS_READ,
    },
    Role.RESEARCHER: {
        Scope.PROJECTS_READ,
        Scope.PROJECTS_WRITE,
        Scope.MODELS_READ,
        Scope.DATASETS_READ,
        Scope.DATASETS_WRITE,
        Scope.EXPERIMENTS_READ,
        Scope.EXPERIMENTS_CREATE,
        Scope.EXPERIMENTS_CANCEL,
        Scope.ANALYSIS_CREATE,
        Scope.ARTIFACTS_READ,
    },
    Role.OPERATOR: {
        Scope.PROJECTS_READ,
        Scope.PROJECTS_WRITE,
        Scope.MODELS_READ,
        Scope.DATASETS_READ,
        Scope.DATASETS_WRITE,
        Scope.EXPERIMENTS_READ,
        Scope.EXPERIMENTS_CREATE,
        Scope.EXPERIMENTS_CANCEL,
        Scope.ANALYSIS_CREATE,
        Scope.ARTIFACTS_READ,
        Scope.WORKER_OPERATE,
        Scope.EXPERIMENT_OVERRIDE,
    },
    Role.ADMIN: set(Scope),
}


class Principal(BaseModel):
    """Authenticated caller identity."""

    principal_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    project_ids: list[str] = Field(
        default_factory=list,
        description="List of authorized project IDs, empty allows all tenant projects",
    )
    role: Role = Role.VIEWER
    scopes: set[str] = Field(
        default_factory=set, description="Explicit scopes granted via token claims"
    )

    def has_permission(self, required_scope: Scope) -> bool:
        """Evaluate if the principal holds the required permission via role and scope intersection.

        Enforces strict OAuth 2.1 scope attenuation:
        1. The requested scope MUST be allowed by the principal's role.
        2. If explicit token scopes are present, the requested scope MUST also be granted
           by the token (or covered by a wildcard '*').
        """
        role_allowed = ROLE_PERMISSIONS.get(self.role, set())
        if required_scope not in role_allowed:
            return False

        # If no explicit token scopes are set, the principal has full role permissions
        if not self.scopes:
            return True

        # If explicit scopes are set, evaluate scope intersection
        scope_vals = {s.value if isinstance(s, Scope) else s for s in self.scopes}
        req_val = required_scope.value
        req_short = req_val.removeprefix("ml:")

        return (
            "*" in self.scopes
            or "admin" in scope_vals
            or Scope.ADMIN.value in scope_vals
            or Scope.ADMIN in self.scopes
            or req_val in scope_vals
            or req_short in scope_vals
        )

    def enforce_permission(self, required_scope: Scope) -> None:
        """Enforce permission, raising AuthorizationDeniedError if missing."""
        if not self.has_permission(required_scope):
            raise AuthorizationDeniedError(
                f"Principal '{self.principal_id}' lacks required permission scope '{required_scope.value}'",
                details={"required_scope": required_scope.value, "role": self.role.value},
            )
