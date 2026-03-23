"""JWT token handling for authentication."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import json
import hmac
import hashlib
import base64

from pydantic import BaseModel


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    user_id: str
    tenant_id: str
    roles: list[str]
    capabilities: list[str]
    exp: int
    iat: int
    sub: str


def _base64_url_encode(data: bytes) -> str:
    """Base64 URL encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64_url_decode(data: str) -> bytes:
    """Base64 URL decode with padding restoration."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def encode_token(
    user_id: str,
    tenant_id: str,
    roles: list[str],
    capabilities: list[str],
    secret: str,
    expires_in_hours: int = 24,
) -> str:
    """
    Encode JWT token.

    Args:
        user_id: User identifier.
        tenant_id: Tenant identifier.
        roles: User roles.
        capabilities: User capabilities.
        secret: Secret key for signing.
        expires_in_hours: Token expiration time in hours.

    Returns:
        Encoded JWT token.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=expires_in_hours)

    header = {
        "alg": "HS256",
        "typ": "JWT",
    }

    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "roles": roles,
        "capabilities": capabilities,
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    # Encode header and payload
    header_encoded = _base64_url_encode(json.dumps(header).encode("utf-8"))
    payload_encoded = _base64_url_encode(json.dumps(payload).encode("utf-8"))

    # Create signature
    message = f"{header_encoded}.{payload_encoded}".encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()
    signature_encoded = _base64_url_encode(signature)

    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"


def decode_token(token: str, secret: str) -> Dict[str, Any]:
    """
    Decode JWT token without verification.

    Args:
        token: JWT token string.
        secret: Secret key for verification.

    Returns:
        Decoded payload.

    Raises:
        ValueError: If token is invalid.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_encoded, payload_encoded, signature_encoded = parts

        # Verify signature
        message = f"{header_encoded}.{payload_encoded}".encode("utf-8")
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).digest()
        expected_signature_encoded = _base64_url_encode(expected_signature)

        if not hmac.compare_digest(signature_encoded, expected_signature_encoded):
            raise ValueError("Invalid signature")

        # Decode payload
        payload_bytes = _base64_url_decode(payload_encoded)
        payload = json.loads(payload_bytes.decode("utf-8"))

        return payload

    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to decode token: {e}")


def verify_token(token: str, secret: str) -> TokenPayload:
    """
    Verify JWT token and return payload.

    Args:
        token: JWT token string.
        secret: Secret key for verification.

    Returns:
        TokenPayload with verified claims.

    Raises:
        ValueError: If token is invalid or expired.
    """
    payload = decode_token(token, secret)

    # Check expiration
    exp = payload.get("exp")
    if exp is None:
        raise ValueError("Token missing expiration")

    if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        raise ValueError("Token expired")

    # Validate required fields
    required = ["user_id", "tenant_id", "roles", "sub"]
    for field in required:
        if field not in payload:
            raise ValueError(f"Token missing required field: {field}")

    return TokenPayload(**payload)
