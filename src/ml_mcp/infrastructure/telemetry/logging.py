"""Structured JSON logging strictly directed to sys.stderr to preserve STDIO transport."""

import contextvars
import datetime
import json
import logging
import sys
from typing import Any

# Context variables for correlation
ctx_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_request_id", default=None
)
ctx_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_trace_id", default=None
)
ctx_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_tenant_id", default=None
)
ctx_principal_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_principal_id", default=None
)


def set_request_context(
    request_id: str | None = None,
    trace_id: str | None = None,
    tenant_id: str | None = None,
    principal_id: str | None = None,
) -> None:
    """Set request-scoped telemetry and correlation IDs."""
    if request_id is not None:
        ctx_request_id.set(request_id)
    if trace_id is not None:
        ctx_trace_id.set(trace_id)
    if tenant_id is not None:
        ctx_tenant_id.set(tenant_id)
    if principal_id is not None:
        ctx_principal_id.set(principal_id)


def clear_request_context() -> None:
    """Reset all correlation IDs in current context."""
    ctx_request_id.set(None)
    ctx_trace_id.set(None)
    ctx_tenant_id.set(None)
    ctx_principal_id.set(None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter producing structured log entries for centralized log ingestion."""

    _SENSITIVE_KEYS = {
        "password",
        "secret",
        "token",
        "authorization",
        "key",
        "api_key",
        "access_token",
        "secret_key",
    }

    def _sanitize(self, val: Any) -> Any:
        if isinstance(val, dict):
            return {
                k: ("***REDACTED***" if any(s in k.lower() for s in self._SENSITIVE_KEYS) else self._sanitize(v))
                for k, v in val.items()
            }
        if isinstance(val, (list, tuple)):
            return [self._sanitize(item) for item in val]
        return val

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": ctx_request_id.get(),
            "trace_id": ctx_trace_id.get(),
            "tenant_id": ctx_tenant_id.get(),
            "principal_id": ctx_principal_id.get(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields attached to the log record
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
        }
        extras = {
            k: ("***REDACTED***" if any(s in k.lower() for s in self._SENSITIVE_KEYS) else self._sanitize(v))
            for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extras:
            payload["extra"] = extras

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger to use JSON formatting directed exclusively to stderr."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove any existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Output strictly to sys.stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(stderr_handler)

    # Ensure critical third-party loggers do not write raw stdout
    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastmcp"):
        l = logging.getLogger(noisy)
        l.handlers = []
        l.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance by name."""
    return logging.getLogger(name)
