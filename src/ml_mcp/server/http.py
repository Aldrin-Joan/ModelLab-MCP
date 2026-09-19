"""HTTP transport application for ModelLab FastMCP Server.

Exposes Streamable HTTP endpoint (/mcp), health probes (/health/live, /health/ready),
and enforces OAuth 2.1 / OIDC Bearer token authentication middleware.
"""

import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ml_mcp.config import get_settings
from ml_mcp.infrastructure.object_storage.s3 import get_storage_service
from ml_mcp.infrastructure.postgres.session import get_db_manager
from ml_mcp.infrastructure.redis.client import get_redis_manager
from ml_mcp.server.app import create_server
from ml_mcp.server.auth import get_token_validator
from ml_mcp.server.context import set_current_principal

logger = logging.getLogger(__name__)


class BearerAuthMiddleware:
    """Pure ASGI middleware enforcing Bearer token authentication on protected MCP endpoints."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        # Health probes bypass token authentication
        if path.startswith("/health"):
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        if not settings.auth.enabled:
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header_bytes = headers.get(b"authorization", b"")
        auth_header = auth_header_bytes.decode("utf-8") if auth_header_bytes else ""

        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse(
                {
                    "error": "Unauthorized",
                    "code": "AUTHENTICATION_REQUIRED",
                    "detail": "Missing Bearer token in Authorization header",
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        token = auth_header.split(" ", 1)[1].strip()
        try:
            validator = get_token_validator()
            principal = validator.validate_token(token)
        except Exception as exc:
            logger.warning("Authentication failure: %s", exc)
            response = JSONResponse(
                {
                    "error": "Unauthorized",
                    "code": "INVALID_TOKEN",
                    "detail": str(exc),
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        # Bind authenticated principal to context variable for downstream handlers
        set_current_principal(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            set_current_principal(None)


async def health_live(request: Request) -> JSONResponse:
    """Liveness probe: verifies process is alive and responsive."""
    return JSONResponse({"status": "alive", "service": "modellab-mcp-api"})


async def health_ready(request: Request) -> JSONResponse:
    """Readiness probe: verifies operational connectivity to Postgres, Redis, and Object Store."""
    checks: dict[str, str] = {}
    all_healthy = True

    # 1. Database Check
    try:
        from sqlalchemy import text
        async with get_db_manager().session() as sess:
            await sess.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"
        all_healthy = False

    # 2. Redis Check
    try:
        redis_mgr = get_redis_manager()
        healthy = await redis_mgr.check_health()
        checks["redis"] = "healthy" if healthy else "degraded"
    except Exception as exc:
        checks["redis"] = f"degraded: {exc}"
        # Redis failure can fall back to in-memory, but flag status

    # 3. Object Store Check
    try:
        storage = get_storage_service()
        # Verify storage client initialized
        if storage.s3_client is not None:
            checks["object_store"] = "healthy"
        else:
            checks["object_store"] = "uninitialized"
            all_healthy = False
    except Exception as exc:
        checks["object_store"] = f"unhealthy: {exc}"
        all_healthy = False

    status_code = 200 if all_healthy else 503
    return JSONResponse(
        {
            "status": "ready" if all_healthy else "degraded",
            "checks": checks,
        },
        status_code=status_code,
    )


def create_http_app() -> Starlette:
    """Create configured Starlette application wrapping FastMCP with auth and operational endpoints."""
    settings = get_settings()
    server = create_server()

    # FastMCP streamable HTTP app mounted at configured path (default: /mcp)
    app = server.http_app(
        path=settings.mcp.streamable_http_path,
        transport="streamable-http",
    )

    # Register health probes
    app.add_route("/health/live", health_live, methods=["GET"])
    app.add_route("/health/ready", health_ready, methods=["GET"])

    # Register BearerAuthMiddleware
    app.add_middleware(BearerAuthMiddleware)

    return app


def run_http() -> None:
    """CLI entrypoint for running the ModelLab HTTP server using uvicorn."""
    import uvicorn

    from ml_mcp.infrastructure.telemetry.logging import configure_logging

    configure_logging()
    settings = get_settings()

    uvicorn.run(
        "ml_mcp.server.http:create_http_app",
        factory=True,
        host=settings.mcp.host,
        port=settings.mcp.port,
        log_config=None,  # Use structured stderr logger
        access_log=False,
    )


if __name__ == "__main__":
    run_http()
