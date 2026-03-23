"""Middleware stack for agentend server."""

import time
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)


class TenantExtractionMiddleware(BaseHTTPMiddleware):
    """Extract tenant ID from JWT token in request."""

    async def dispatch(self, request: Request, call_next):
        """Extract tenant and attach to request state."""
        from agentend.auth.jwt import decode_token

        token = None
        if "authorization" in request.headers:
            auth_header = request.headers["authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        tenant_id = None
        user_id = None

        if token:
            try:
                payload = decode_token(token)
                tenant_id = payload.get("tenant_id")
                user_id = payload.get("user_id")
            except Exception as e:
                logger.debug(f"Failed to decode token: {e}")

        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""

    async def dispatch(self, request: Request, call_next):
        """Log request and response."""
        request.state.request_id = str(uuid4())
        request.state.start_time = time.time()

        logger.info(
            f"[{request.state.request_id}] {request.method} {request.url.path}",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client,
            }
        )

        response = await call_next(request)

        duration = time.time() - request.state.start_time
        logger.info(
            f"[{request.state.request_id}] {response.status_code} completed in {duration:.2f}s",
            extra={
                "request_id": request.state.request_id,
                "status_code": response.status_code,
                "duration_seconds": duration,
            }
        )

        response.headers["X-Request-ID"] = request.state.request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses."""

    async def dispatch(self, request: Request, call_next):
        """Add security headers."""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


def setup_middleware(app: FastAPI) -> None:
    """Setup middleware stack in order."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantExtractionMiddleware)
