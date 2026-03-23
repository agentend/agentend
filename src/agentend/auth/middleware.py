"""Authentication middleware and FastAPI dependencies."""

from typing import Optional
import os

from fastapi import Depends, HTTPException, status, Request

from agentend.auth.jwt import TokenPayload, verify_token


async def get_current_user(request: Request) -> TokenPayload:
    """
    FastAPI dependency to extract and verify current user.

    Args:
        request: FastAPI request object.

    Returns:
        TokenPayload with user information.

    Raises:
        HTTPException: If authentication fails.
    """
    # Try JWT token first
    auth_header = request.headers.get("authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            secret = os.getenv("JWT_SECRET", "dev-secret")
            payload = verify_token(token, secret)
            return payload
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Try API key fallback
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Validate API key (implementation depends on storage)
        user_id = _validate_api_key(api_key)
        if user_id:
            return TokenPayload(
                user_id=user_id,
                tenant_id=request.state.tenant_id or "default",
                roles=["user"],
                capabilities=["execute"],
                exp=0,
                iat=0,
                sub=user_id,
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _validate_api_key(api_key: str) -> Optional[str]:
    """
    Validate API key against stored keys.

    Args:
        api_key: API key to validate.

    Returns:
        User ID if valid, None otherwise.
    """
    # Placeholder: In production, check against database
    # For now, simple validation against environment variable
    valid_keys = os.getenv("VALID_API_KEYS", "").split(",")
    if api_key in valid_keys:
        return f"user_from_{api_key[:8]}"
    return None


class AuthMiddleware:
    """Middleware for automatic authentication."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        """Attach user to request state if available."""
        try:
            request.state.user = await get_current_user(request)
        except HTTPException:
            # Not all endpoints require auth; let routes handle it
            request.state.user = None

        response = await call_next(request)
        return response
