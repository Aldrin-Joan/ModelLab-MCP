"""Unit tests for OAuth 2.1 / OIDC Bearer JWT TokenValidator."""

import jwt
import pytest

from ml_mcp.domain.errors import AuthenticationRequiredError
from ml_mcp.domain.policies import Role, Scope
from ml_mcp.server.auth import TokenValidator


def test_valid_token_issuance_and_validation():
    validator = TokenValidator()
    token = validator.create_access_token(
        principal_id="researcher-01",
        tenant_id="tenant-alpha",
        role=Role.RESEARCHER,
        scopes=[Scope.EXPERIMENTS_CREATE.value, Scope.DATASETS_WRITE.value],
        project_ids=["proj-100"],
    )

    principal = validator.validate_token(token)
    assert principal.principal_id == "researcher-01"
    assert principal.tenant_id == "tenant-alpha"
    assert principal.role == Role.RESEARCHER
    assert Scope.EXPERIMENTS_CREATE in principal.scopes or Scope.EXPERIMENTS_CREATE.value in principal.scopes
    assert principal.project_ids == ["proj-100"]


def test_expired_token_rejected():
    validator = TokenValidator()
    # Create expired token (-1 minute)
    token = validator.create_access_token(
        principal_id="user-exp",
        tenant_id="tenant-alpha",
        expires_in_minutes=-5,
    )
    with pytest.raises(AuthenticationRequiredError) as exc:
        validator.validate_token(token)
    assert "expired" in str(exc.value)


def test_wrong_issuer_rejected():
    validator = TokenValidator()
    # Forge token with illegitimate issuer
    payload = {
        "iss": "https://attacker.evil.com",
        "aud": validator.settings.auth.audience,
        "sub": "user-evil",
        "exp": 9999999999,
    }
    forged = jwt.encode(payload, key=validator.settings.auth.secret_key.get_secret_value(), algorithm="HS256")

    with pytest.raises(AuthenticationRequiredError) as exc:
        validator.validate_token(forged)
    assert "issuer" in str(exc.value)


def test_none_algorithm_attack_rejected():
    validator = TokenValidator()
    # Attempt "none" algorithm bypass
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "iss": validator.settings.auth.issuer,
        "aud": validator.settings.auth.audience,
        "sub": "admin",
        "exp": 9999999999,
    }
    # Hand-craft unsigned token
    import base64
    import json
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    none_token = f"{h_b64}.{p_b64}."

    with pytest.raises(AuthenticationRequiredError) as exc:
        validator.validate_token(none_token)
    assert "not permitted" in str(exc.value)
