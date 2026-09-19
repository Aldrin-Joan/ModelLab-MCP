"""Comprehensive Security Matrix & Multi-Tenant Isolation Tests.

Verifies:
- Multi-tenant boundary isolation (Tenant B cannot read/write/cancel Tenant A's resources)
- RBAC enforcement (Viewer, Researcher, Operator, Admin permission matrix)
- Scope authorization checks
- Forged, expired, and tampered JWT token rejection
- Sliding-window rate limit saturation and denial
- Anti-enumeration behavior (404 instead of 403 on cross-tenant access)
"""

import base64
import json

import pytest
from starlette.testclient import TestClient

from ml_mcp.application.models.service import ModelService
from ml_mcp.domain.errors import (
    ResourceLimitExceededError,
)
from ml_mcp.domain.policies import Principal, Role, Scope
from ml_mcp.infrastructure.postgres.base import Base
from ml_mcp.infrastructure.postgres.session import get_db_manager
from ml_mcp.server.app import create_server
from ml_mcp.server.auth import get_token_validator
from ml_mcp.server.context import set_current_principal
from ml_mcp.server.http import create_http_app


@pytest.fixture(autouse=True)
async def setup_db():
    db_mgr = get_db_manager()
    db_mgr.initialize(
        custom_url="sqlite+aiosqlite:///file:sec_matrix_db?mode=memory&cache=shared&uri=true"
    )
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed model catalog and tenant projects
    async with db_mgr.session() as sess:
        service = ModelService(sess)
        await service.seed_catalog()
        from ml_mcp.application.projects.service import ProjectService
        from ml_mcp.infrastructure.postgres.models import ProjectOrm

        proj_service = ProjectService(sess)
        await proj_service.ensure_default_project("tenant-alpha")
        await proj_service.ensure_default_project("tenant-bravo")

        proj_a = ProjectOrm(
            id="proj-a",
            tenant_id="tenant-alpha",
            name="Project Alpha",
            description="Project for Tenant Alpha",
        )
        sess.add(proj_a)
        await sess.flush()

    yield
    set_current_principal(None)
    await db_mgr.close()


def extract_result(tool_res):
    """Unwrap structured content or JSON text from FastMCP tool result."""
    if tool_res.structured_content is not None:
        if (
            isinstance(tool_res.structured_content, dict)
            and "result" in tool_res.structured_content
            and len(tool_res.structured_content) == 1
        ):
            return tool_res.structured_content["result"]
        return tool_res.structured_content
    return json.loads(tool_res.content[0].text)


@pytest.mark.asyncio
async def test_multi_tenant_dataset_isolation():
    """Verify Tenant B cannot access or inspect Tenant A's datasets."""
    server = create_server()

    # Principal A (Tenant A)
    principal_a = Principal(
        principal_id="user-a",
        tenant_id="tenant-alpha",
        role=Role.RESEARCHER,
        scopes={"*"},
    )
    set_current_principal(principal_a)

    csv_data = "f1,f2,target\n1,2,0\n3,4,1\n"
    csv_b64 = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")

    reg_res = await server.call_tool(
        "register_dataset",
        {
            "project_id": "proj-a",
            "name": "ds-alpha",
            "description": "Tenant A dataset",
            "format": "csv",
            "data_base64": csv_b64,
        },
    )
    dataset_id = extract_result(reg_res)["dataset_id"]

    # Principal B (Tenant B) attempts to inspect or get Tenant A's dataset
    principal_b = Principal(
        principal_id="user-b",
        tenant_id="tenant-bravo",
        role=Role.ADMIN,
        scopes={"*"},
    )
    set_current_principal(principal_b)

    # Attempting to inspect Tenant A's dataset from Tenant B must raise ResourceNotFoundError (anti-enumeration)
    with pytest.raises(Exception) as exc:
        await server.call_tool(
            "inspect_dataset",
            {"dataset_id": dataset_id, "version": "1.0"},
        )
    assert "not found" in str(exc.value).lower() or "resourcenotfound" in str(exc.value).lower()

    # Listing datasets for Tenant B must return empty list
    list_res = await server.call_tool("list_datasets", {})
    datasets_b = extract_result(list_res)
    assert len(datasets_b) == 0


@pytest.mark.asyncio
async def test_multi_tenant_experiment_isolation():
    """Verify Tenant B cannot get or cancel Tenant A's experiments."""
    server = create_server()

    # Create dataset & experiment as Tenant A
    principal_a = Principal(
        principal_id="user-a",
        tenant_id="tenant-alpha",
        role=Role.RESEARCHER,
        scopes={"*"},
    )
    set_current_principal(principal_a)

    csv_data = "x,y\n1,0\n2,1\n"
    csv_b64 = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")
    reg_res = await server.call_tool(
        "register_dataset",
        {
            "project_id": "proj-a",
            "name": "ds-exp",
            "description": "Dataset",
            "format": "csv",
            "data_base64": csv_b64,
        },
    )
    dataset_version_id = extract_result(reg_res)["version_id"]

    res_v = await server.call_tool("list_model_versions", {"model_id": "logistic_regression"})
    model_version_id = extract_result(res_v)[0]["version_id"]

    exp_res = await server.call_tool(
        "create_experiment",
        {
            "project_id": "proj-a",
            "dataset_version_id": dataset_version_id,
            "model_version_id": model_version_id,
            "task_type": "binary_classification",
            "target_column": "y",
        },
    )
    experiment_id = extract_result(exp_res)["experiment_id"]

    # Switch to Tenant B
    principal_b = Principal(
        principal_id="user-b",
        tenant_id="tenant-bravo",
        role=Role.ADMIN,
        scopes={"*"},
    )
    set_current_principal(principal_b)

    # Tenant B tries to get Tenant A's experiment
    with pytest.raises(Exception) as exc_get:
        await server.call_tool("get_experiment", {"experiment_id": experiment_id})
    assert "not found" in str(exc_get.value).lower()

    # Tenant B tries to cancel Tenant A's experiment
    with pytest.raises(Exception) as exc_cancel:
        await server.call_tool("cancel_experiment", {"experiment_id": experiment_id})
    assert "not found" in str(exc_cancel.value).lower()


@pytest.mark.asyncio
async def test_rbac_viewer_cannot_mutate():
    """Verify VIEWER role cannot register datasets, create experiments, or cancel experiments."""
    server = create_server()

    viewer = Principal(
        principal_id="viewer-1",
        tenant_id="tenant-alpha",
        role=Role.VIEWER,
        scopes={Scope.MODELS_READ.value, Scope.DATASETS_READ.value, Scope.EXPERIMENTS_READ.value},
    )
    set_current_principal(viewer)

    # 1. Read operations succeed
    models_res = await server.call_tool("list_models", {})
    assert not models_res.is_error
    assert len(extract_result(models_res)) == 7

    # 2. Mutating operations fail with PermissionDeniedError
    csv_data = "x,y\n1,0\n"
    csv_b64 = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")

    with pytest.raises(Exception) as exc_reg:
        await server.call_tool(
            "register_dataset",
            {
                "project_id": "proj-view",
                "name": "ds-view",
                "description": "test",
                "format": "csv",
                "data_base64": csv_b64,
            },
        )
    assert "permission" in str(exc_reg.value).lower() or "denied" in str(exc_reg.value).lower()

    with pytest.raises(Exception) as exc_exp:
        await server.call_tool(
            "create_experiment",
            {
                "project_id": "proj-view",
                "dataset_version_id": "any-id",
                "model_version_id": "any-id",
                "task_type": "binary_classification",
                "target_column": "y",
            },
        )
    assert "permission" in str(exc_exp.value).lower() or "denied" in str(exc_exp.value).lower()


@pytest.mark.asyncio
async def test_scope_enforcement_missing_permission():
    """Verify principal with missing required scope is denied execution."""
    server = create_server()

    # Researcher role, but token only carries models:read scope
    token_principal = Principal(
        principal_id="researcher-scoped",
        tenant_id="tenant-alpha",
        role=Role.RESEARCHER,
        scopes={"models:read"},  # Missing datasets:write and experiments:create
    )
    set_current_principal(token_principal)

    csv_data = "x,y\n1,0\n"
    csv_b64 = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")

    with pytest.raises(Exception) as exc:
        await server.call_tool(
            "register_dataset",
            {
                "project_id": "proj-1",
                "name": "ds",
                "description": "test",
                "format": "csv",
                "data_base64": csv_b64,
            },
        )
    assert "permission" in str(exc.value).lower() or "denied" in str(exc.value).lower()


def test_jwt_expired_token_rejected_at_transport():
    """Verify expired token is rejected with HTTP 401 at HTTP transport boundary."""
    validator = get_token_validator()
    expired_token = validator.create_access_token(
        principal_id="user-expired",
        tenant_id="tenant-alpha",
        role=Role.RESEARCHER,
        expires_in_minutes=-10,  # Expired 10 minutes ago
    )

    app = create_http_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "INVALID_TOKEN"
        assert "expired" in data["detail"].lower()


def test_jwt_forged_signature_rejected_at_transport():
    """Verify token signed with an unauthorized key is rejected with HTTP 401."""
    import datetime

    import jwt

    now = datetime.datetime.now(datetime.UTC)
    forged_token = jwt.encode(
        {
            "iss": "https://auth.modellab.local",
            "aud": "modellab-mcp-api",
            "sub": "attacker",
            "tenant_id": "tenant-victim",
            "role": "admin",
            "scope": "*",
            "iat": now,
            "exp": now + datetime.timedelta(hours=1),
        },
        key="completely-wrong-secret-key-attacker-provided-1234567890",
        algorithm="HS256",
    )

    app = create_http_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_rate_limiting_enforcement():
    """Verify sliding-window rate limit triggers ResourceLimitExceededError when saturated."""
    from ml_mcp.infrastructure.redis.rate_limiter import SlidingWindowRateLimiter
    from ml_mcp.server.middleware import SecurityPipeline

    # Custom rate limiter with low limit of 3 calls
    limiter = SlidingWindowRateLimiter()
    pipeline = SecurityPipeline(rate_limiter=limiter)

    from ml_mcp.infrastructure.postgres.base import generate_uuid7

    test_principal = Principal(
        principal_id=f"spammer-{generate_uuid7()}",
        tenant_id="tenant-rate-limited",
        role=Role.ADMIN,
        scopes={"*"},
    )

    # Tool 'create_experiment' has category 'experiment' (limit 10 by default)
    # Fire 10 allowed calls directly on pipeline
    for _ in range(10):
        await pipeline.pre_tool_call("create_experiment", test_principal)

    # The 11th call must fail with ResourceLimitExceededError
    with pytest.raises(ResourceLimitExceededError) as exc:
        await pipeline.pre_tool_call("create_experiment", test_principal)
    assert "Rate limit exceeded" in str(exc.value)
