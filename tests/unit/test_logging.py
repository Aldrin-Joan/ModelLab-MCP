"""Unit tests for JSON structured logging."""

import json
import logging

from ml_mcp.infrastructure.telemetry.logging import (
    JSONFormatter,
    clear_request_context,
    set_request_context,
)


def test_json_formatter():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    set_request_context(
        request_id="req-123",
        trace_id="tr-456",
        tenant_id="tenant-alpha",
        principal_id="user-001",
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test message"
    assert parsed["request_id"] == "req-123"
    assert parsed["trace_id"] == "tr-456"
    assert parsed["tenant_id"] == "tenant-alpha"
    assert parsed["principal_id"] == "user-001"
    assert "timestamp" in parsed

    clear_request_context()


def test_sensitive_field_redaction():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="auth_logger",
        level=logging.INFO,
        pathname="auth.py",
        lineno=20,
        msg="User login",
        args=(),
        exc_info=None,
    )
    record.auth_token = "super-secret-jwt-token"
    record.user_password = "plain-text-password"
    record.safe_field = "visible-info"

    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    extras = parsed.get("extra", {})

    assert extras.get("auth_token") == "***REDACTED***"
    assert extras.get("user_password") == "***REDACTED***"
    assert extras.get("safe_field") == "visible-info"
