"""Execution context and principal resolution for MCP tool invocations."""

from contextvars import ContextVar
import logging
from ml_mcp.domain.errors import AuthenticationRequiredError
from ml_mcp.domain.policies import Principal, Role
from ml_mcp.server.middleware import LOCAL_STDIO_PRINCIPAL

logger = logging.getLogger(__name__)

_current_principal_var: ContextVar[Principal | None] = ContextVar("current_principal_var", default=None)


def set_current_principal(principal: Principal | None) -> None:
    """Set the active principal in context."""
    _current_principal_var.set(principal)


def get_current_principal() -> Principal:
    """Resolve active principal from context, HTTP request headers, or default local boundary.

    Resolution order:
    1. Explicit Principal set in ContextVar (e.g. from middleware, worker, or test context).
    2. HTTP request Authorization header (if running within an active HTTP request).
    3. Default LOCAL_STDIO_PRINCIPAL (if running via STDIO transport or local CLI).
    """
    p = _current_principal_var.get()
    if p is not None:
        return p

    # Check for active HTTP request in FastMCP context
    try:
        from fastmcp.server.dependencies import get_http_request
        req = get_http_request()
    except RuntimeError:
        req = None

    if req is not None:
        auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            from ml_mcp.config import get_settings
            if not get_settings().auth.enabled:
                return LOCAL_STDIO_PRINCIPAL
            raise AuthenticationRequiredError("Missing or invalid Bearer token in Authorization header")

        token = auth_header.split(" ", 1)[1].strip()
        from ml_mcp.server.auth import get_token_validator
        validator = get_token_validator()
        return validator.validate_token(token)

    return LOCAL_STDIO_PRINCIPAL
