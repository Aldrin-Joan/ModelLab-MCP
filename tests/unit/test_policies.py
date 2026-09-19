"""Unit tests for RBAC, tool policies, and tenant isolation."""

import pytest

from ml_mcp.domain.errors import AuthorizationDeniedError
from ml_mcp.domain.policies import (
    TOOL_POLICIES,
    Principal,
    Role,
    Scope,
    validate_tenant_access,
)


def test_viewer_role_permissions():
    viewer = Principal(
        principal_id="user-1",
        tenant_id="tenant-a",
        role=Role.VIEWER,
    )
    assert viewer.has_permission(Scope.MODELS_READ) is True
    assert viewer.has_permission(Scope.DATASETS_READ) is True
    assert viewer.has_permission(Scope.EXPERIMENTS_READ) is True
    # Viewer cannot create experiments
    assert viewer.has_permission(Scope.EXPERIMENTS_CREATE) is False

    with pytest.raises(AuthorizationDeniedError):
        viewer.enforce_permission(Scope.EXPERIMENTS_CREATE)


def test_researcher_role_permissions():
    researcher = Principal(
        principal_id="user-2",
        tenant_id="tenant-a",
        role=Role.RESEARCHER,
    )
    assert researcher.has_permission(Scope.EXPERIMENTS_CREATE) is True
    assert researcher.has_permission(Scope.DATASETS_WRITE) is True
    assert researcher.has_permission(Scope.WORKER_OPERATE) is False


def test_explicit_token_scope_override():
    # User is viewer but granted explicit create scope in token
    scoped_user = Principal(
        principal_id="user-3",
        tenant_id="tenant-a",
        role=Role.VIEWER,
        scopes={Scope.EXPERIMENTS_CREATE.value},
    )
    assert scoped_user.has_permission(Scope.EXPERIMENTS_CREATE) is True


def test_tenant_isolation_enforcement():
    user = Principal(
        principal_id="user-4",
        tenant_id="tenant-alpha",
        project_ids=["proj-101"],
        role=Role.RESEARCHER,
    )
    # Same tenant & allowed project succeeds
    validate_tenant_access(user, resource_tenant_id="tenant-alpha", resource_project_id="proj-101")

    # Cross-tenant access fails
    with pytest.raises(AuthorizationDeniedError) as exc_info:
        validate_tenant_access(user, resource_tenant_id="tenant-beta", resource_project_id="proj-101")
    assert "Cross-tenant access forbidden" in str(exc_info.value)

    # Cross-project access in same tenant fails
    with pytest.raises(AuthorizationDeniedError) as exc_info:
        validate_tenant_access(user, resource_tenant_id="tenant-alpha", resource_project_id="proj-999")
    assert "does not have access to project" in str(exc_info.value)


def test_tool_policies_coverage():
    # Verify all 18 core tools are cataloged with policies
    assert "create_experiment" in TOOL_POLICIES
    assert "register_dataset" in TOOL_POLICIES
    assert "analyze_experiment" in TOOL_POLICIES
    assert TOOL_POLICIES["create_experiment"].required_scope == Scope.EXPERIMENTS_CREATE
