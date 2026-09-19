"""Unit tests for centralized settings."""

import os
from unittest.mock import patch

from ml_mcp.config.settings import Settings


def test_default_settings():
    settings = Settings()
    assert settings.app.name == "ml-mcp"
    assert settings.mcp.protocol_version == "2026-07-28"
    assert settings.auth.enabled is True
    assert "RS256" in settings.auth.algorithms
    assert settings.rate_limit.read_per_minute == 120
    assert settings.security.max_request_body_bytes == 10 * 1024 * 1024


def test_env_override():
    with patch.dict(
        os.environ,
        {
            "APP_NAME": "custom-mcp",
            "MCP_PORT": "9000",
            "RATE_LIMIT_READ_PER_MINUTE": "300",
        },
    ):
        # Direct instantiation reads updated env
        settings = Settings()
        assert settings.app.name == "custom-mcp"
        assert settings.mcp.port == 9000
        assert settings.rate_limit.read_per_minute == 300


def test_secret_masking():
    settings = Settings()
    secret_str = str(settings.app.secret_key)
    # The actual secret value should not appear in raw str() or repr()
    assert "insecure-dev-secret-key" not in secret_str
    assert settings.app.secret_key.get_secret_value().startswith("insecure-dev-secret-key")
