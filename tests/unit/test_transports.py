"""Unit tests for ModelLab HTTP and STDIO transports, auth middleware, and health endpoints."""

import pytest
from starlette.testclient import TestClient
from ml_mcp.config import get_settings
from ml_mcp.domain.policies import Principal, Role
from ml_mcp.infrastructure.postgres.base import Base
from ml_mcp.infrastructure.postgres.session import DatabaseManager, get_db_manager
from ml_mcp.server.auth import get_token_validator
from ml_mcp.server.http import create_http_app


@pytest.fixture(autouse=True)
async def setup_db():
    db_mgr = get_db_manager()
    db_mgr.initialize(custom_url="sqlite+aiosqlite:///file:transport_db?mode=memory&cache=shared&uri=true")
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await db_mgr.close()


def test_health_live_endpoint():
    """Verify unauthenticated GET /health/live returns HTTP 200 alive."""
    app = create_http_app()
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "modellab-mcp-api"


def test_health_ready_endpoint():
    """Verify GET /health/ready returns service readiness checks."""
    app = create_http_app()
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "checks" in data
        assert "database" in data["checks"]


def test_protected_endpoint_requires_auth():
    """Verify request to /mcp without Authorization header returns HTTP 401."""
    app = create_http_app()
    with TestClient(app) as client:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert data["code"] == "AUTHENTICATION_REQUIRED"


def test_protected_endpoint_rejects_invalid_token():
    """Verify request with invalid Bearer token returns HTTP 401."""
    app = create_http_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert data["code"] == "INVALID_TOKEN"


def test_protected_endpoint_accepts_valid_token():
    """Verify request with valid Bearer token passes auth middleware."""
    validator = get_token_validator()
    token = validator.create_access_token(
        principal_id="user-http-test",
        tenant_id="tenant-alpha",
        role=Role.RESEARCHER,
        scopes=["models:read", "datasets:read", "experiments:read"],
    )

    app = create_http_app()
    with TestClient(app) as client:
        # Request passes through BearerAuthMiddleware
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Auth middleware succeeded; status will be either 200 or FastMCP response, but definitely not 401
        assert response.status_code != 401


def test_stdio_launcher_import():
    """Verify STDIO launcher is importable and has entrypoint."""
    from ml_mcp.server.stdio import run_stdio, run_stdio_server
    assert callable(run_stdio)
    assert callable(run_stdio_server)
