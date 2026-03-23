"""System health capability: checks PostgreSQL, Redis, Ollama connectivity."""

import logging
from typing import Any, Dict

from agentend.kernel.kernel import RequestContext

logger = logging.getLogger(__name__)


class SystemHealthCapability:
    """Checks connectivity to PostgreSQL, Redis, and Ollama.

    Returns a per-service status dict indicating whether each service
    is reachable. Does not call any LLMs.
    """

    name: str = "system.health"
    description: str = "Checks PostgreSQL, Redis, Ollama connectivity"

    async def execute(self, context: RequestContext, **kwargs: Any) -> Dict[str, Any]:
        """Check service connectivity and return status per service.

        Args:
            context: Request context with app state in metadata.

        Returns:
            Dict with service names mapped to their status.
        """
        services: Dict[str, Dict[str, Any]] = {}

        # Check PostgreSQL
        engine = context.metadata.get("engine")
        services["postgresql"] = await self._check_postgresql(engine)

        # Check Redis
        redis_client = context.metadata.get("redis")
        services["redis"] = await self._check_redis(redis_client)

        # Check Ollama
        services["ollama"] = await self._check_ollama()

        all_ok = all(s.get("status") == "ok" for s in services.values())
        return {
            "capability": "system.health",
            "healthy": all_ok,
            "services": services,
        }

    async def _check_postgresql(self, engine: Any) -> Dict[str, Any]:
        """Check PostgreSQL connectivity."""
        if engine is None:
            return {"status": "unavailable", "detail": "Engine not configured"}
        try:
            from sqlalchemy import text

            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as e:
            logger.warning(f"PostgreSQL health check failed: {e}")
            return {"status": "error", "detail": str(e)}

    async def _check_redis(self, redis_client: Any) -> Dict[str, Any]:
        """Check Redis connectivity."""
        if redis_client is None:
            return {"status": "unavailable", "detail": "Redis not configured"}
        try:
            await redis_client.ping()
            return {"status": "ok"}
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return {"status": "error", "detail": str(e)}

    async def _check_ollama(self) -> Dict[str, Any]:
        """Check Ollama connectivity."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://ollama:11434/api/tags", timeout=2.0
                )
                if response.status_code == 200:
                    return {"status": "ok"}
                return {"status": "error", "detail": f"HTTP {response.status_code}"}
        except ImportError:
            return {"status": "unavailable", "detail": "httpx not installed"}
        except Exception as e:
            return {"status": "unavailable", "detail": str(e)}
