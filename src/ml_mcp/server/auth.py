"""Authentication and JWT validation adhering to OAuth 2.1 / OIDC standards."""

import datetime
import logging
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError, PyJWTError

from ml_mcp.config import Settings, get_settings
from ml_mcp.domain.errors import AuthenticationRequiredError
from ml_mcp.domain.policies import Principal, Role

logger = logging.getLogger(__name__)


class TokenValidator:
    """Validates incoming OAuth 2.1 / OIDC Bearer JWTs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate_token(self, token: str) -> Principal:
        """Validate signature, claims, and issuer bindings on a JWT string.

        Raises:
            AuthenticationRequiredError: on expired, malformed, or unauthorized tokens.
        """
        if not token:
            raise AuthenticationRequiredError("Missing bearer token")

        # 1. Inspect unverified header to guard against algorithm confusion/none attacks
        try:
            unverified_header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise AuthenticationRequiredError("Malformed JWT header") from exc

        alg = unverified_header.get("alg")
        if not alg or alg.lower() == "none" or alg not in self.settings.auth.algorithms:
            logger.warning("Rejected token with disallowed algorithm: %s", alg)
            raise AuthenticationRequiredError(f"Token algorithm '{alg}' is not permitted")

        # 2. Select verification key
        key: str = (
            self.settings.auth.public_key_pem
            if alg.startswith("RS") and self.settings.auth.public_key_pem
            else self.settings.auth.secret_key.get_secret_value()
        )

        # 3. Verify signature and claims
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=[alg],
                issuer=self.settings.auth.issuer,
                audience=self.settings.auth.audience,
                options={
                    "require": ["exp", "iss", "aud", "sub"],
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationRequiredError("Bearer token has expired") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationRequiredError("Invalid token issuer") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationRequiredError("Invalid token audience") from exc
        except InvalidTokenError as exc:
            raise AuthenticationRequiredError(f"Invalid authentication token: {exc}") from exc

        # 4. Map claims to Principal
        principal_id = payload["sub"]
        tenant_id = payload.get("tenant_id") or payload.get("tid", "default-tenant")
        project_ids = payload.get("project_ids") or payload.get("projects", [])
        role_str = payload.get("role", "viewer").lower()
        role = Role(role_str) if role_str in Role else Role.VIEWER

        # Scopes can be space-delimited string or list
        raw_scopes = payload.get("scope") or payload.get("scopes", "")
        if isinstance(raw_scopes, str):
            scopes = set(raw_scopes.split()) if raw_scopes else set()
        else:
            scopes = set(raw_scopes)

        return Principal(
            principal_id=principal_id,
            tenant_id=tenant_id,
            project_ids=project_ids,
            role=role,
            scopes=scopes,
        )

    def create_access_token(
        self,
        principal_id: str,
        tenant_id: str,
        role: Role = Role.RESEARCHER,
        scopes: list[str] | None = None,
        project_ids: list[str] | None = None,
        expires_in_minutes: int = 60,
    ) -> str:
        """Helper to generate signed JWT for development, testing, and internal callers."""
        now = datetime.datetime.now(datetime.UTC)
        payload = {
            "iss": self.settings.auth.issuer,
            "aud": self.settings.auth.audience,
            "sub": principal_id,
            "tenant_id": tenant_id,
            "role": role.value,
            "scope": " ".join(scopes or []),
            "project_ids": project_ids or [],
            "iat": now,
            "nbf": now,
            "exp": now + datetime.timedelta(minutes=expires_in_minutes),
        }
        return jwt.encode(
            payload,
            key=self.settings.auth.secret_key.get_secret_value(),
            algorithm="HS256",
        )


_token_validator: TokenValidator | None = None


def get_token_validator() -> TokenValidator:
    global _token_validator
    if _token_validator is None:
        _token_validator = TokenValidator()
    return _token_validator
