"""Security, authorization, and rate-limiting middleware pipeline."""

import logging
from typing import Any
from ml_mcp.domain.errors import DomainError, ResourceLimitExceededError
from ml_mcp.domain.policies import (
    TOOL_POLICIES,
    Principal,
    Role,
)
from ml_mcp.infrastructure.postgres.models import AuditEventOrm
from ml_mcp.infrastructure.postgres.repositories.audit import AuditRepository
from ml_mcp.infrastructure.postgres.session import get_db_manager
from ml_mcp.infrastructure.redis.rate_limiter import SlidingWindowRateLimiter
from ml_mcp.infrastructure.telemetry.logging import (
    clear_request_context,
    set_request_context,
)
from ml_mcp.infrastructure.telemetry.otel import get_instruments

logger = logging.getLogger(__name__)


# Default local principal for STDIO operations (trusted local process boundary)
LOCAL_STDIO_PRINCIPAL = Principal(
    principal_id="local-user",
    tenant_id="default-tenant",
    role=Role.ADMIN,
)


class SecurityPipeline:
    """Orchestrates authentication, scope checks, rate limiting, and audit logging for tool executions."""

    def __init__(self, rate_limiter: SlidingWindowRateLimiter | None = None) -> None:
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()

    async def pre_tool_call(
        self,
        tool_name: str,
        principal: Principal,
        request_id: str | None = None,
    ) -> None:
        """Enforce rate limits, scopes, and set request context."""
        policy = TOOL_POLICIES.get(tool_name)
        if not policy:
            return

        # 1. Telemetry context
        set_request_context(
            request_id=request_id,
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
        )

        # 2. Scope enforcement
        principal.enforce_permission(policy.required_scope)

        # 3. Rate limiting enforcement
        limits_map = {
            "read": 120,
            "metadata": 60,
            "experiment": 10,
            "analysis": 20,
        }
        limit = limits_map.get(policy.rate_limit_category, 60)
        res = await self.rate_limiter.check_rate_limit(
            identifier=f"{principal.tenant_id}:{principal.principal_id}",
            category=policy.rate_limit_category,
            limit=limit,
        )
        if not res.allowed:
            get_instruments().rate_limit_denials_total.add(1)
            raise ResourceLimitExceededError(
                f"Rate limit exceeded for tool category '{policy.rate_limit_category}'",
                limit=limit,
                current=limit + 1,
            )

    async def post_tool_call(
        self,
        tool_name: str,
        principal: Principal,
        result: Any,
        success: bool = True,
        error_code: str | None = None,
    ) -> None:
        """Emit audit log entry if required by policy and clear telemetry context."""
        policy = TOOL_POLICIES.get(tool_name)
        if policy and policy.requires_audit:
            try:
                async with get_db_manager().session() as sess:
                    audit_repo = AuditRepository(sess)
                    await audit_repo.record_event(
                        AuditEventOrm(
                            principal_id=principal.principal_id,
                            tenant_id=principal.tenant_id,
                            action=f"TOOL_{tool_name.upper()}",
                            resource_type="tool",
                            resource_id=tool_name,
                            result="SUCCESS" if success else "ERROR",
                            reason_code=error_code,
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to record audit event for %s: %s", tool_name, exc)

        clear_request_context()


_pipeline: SecurityPipeline | None = None


def get_security_pipeline() -> SecurityPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = SecurityPipeline()
    return _pipeline
