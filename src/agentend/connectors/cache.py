"""Cache connectors for data caching and memoization.

Provides connectors for in-memory caching and Redis-backed distributed caching.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from agentend.connectors.base import Connector, ConnectorConfig

logger = logging.getLogger(__name__)

# Optional Redis dependency
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class CacheConnector(Connector):
    """Abstract base connector for cache systems.

    Provides common interface for key-value caching with TTL support.
    """

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value, or None if not found or expired.
        """
        pass

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Set a value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds. None means no expiration.
        """
        pass

    async def delete(self, key: str) -> None:
        """Delete a value from cache.

        Args:
            key: Cache key to delete.
        """
        pass

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache.

        Args:
            key: Cache key.

        Returns:
            True if key exists, False otherwise.
        """
        pass


class InMemoryCacheConnector(CacheConnector):
    """In-memory cache connector using a simple dictionary.

    Zero external dependencies, suitable for single-process applications.
    Not suitable for distributed systems (use RedisCacheConnector instead).

    Configuration:
        ConnectorConfig(
            name="cache",
            connector_type="memory_cache"
        )
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize in-memory cache connector."""
        super().__init__(config)
        self._cache: Dict[str, tuple[Any, Optional[float]]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Initialize in-memory cache."""
        self._cache.clear()
        self._connected = True
        logger.info("In-memory cache connector initialized")

    async def disconnect(self) -> None:
        """Cleanup in-memory cache."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self._cache.clear()
        self._connected = False

    async def health_check(self) -> bool:
        """In-memory cache is always available."""
        return True

    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute cache operation.

        Operations:
            - get: Get value (requires 'key')
            - set: Set value (requires 'key', 'value', optional 'ttl')
            - delete: Delete key (requires 'key')
            - exists: Check existence (requires 'key')
            - clear: Clear all keys
        """
        if operation == "get":
            return await self.get(kwargs.get("key"))
        elif operation == "set":
            await self.set(
                kwargs.get("key"),
                kwargs.get("value"),
                kwargs.get("ttl"),
            )
            return True
        elif operation == "delete":
            await self.delete(kwargs.get("key"))
            return True
        elif operation == "exists":
            return await self.exists(kwargs.get("key"))
        elif operation == "clear":
            self._cache.clear()
            return True
        else:
            raise ValueError(f"Unknown cache operation: {operation}")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self._cache:
            return None

        value, expiration = self._cache[key]

        # Check expiration
        if expiration is not None and time.time() > expiration:
            del self._cache[key]
            return None

        return value

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Set value in cache."""
        expiration = None
        if ttl is not None:
            expiration = time.time() + ttl

        self._cache[key] = (value, expiration)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if key not in self._cache:
            return False

        value, expiration = self._cache[key]

        # Check expiration
        if expiration is not None and time.time() > expiration:
            del self._cache[key]
            return False

        return True


def _make_redis_stub() -> type:
    """Create a stub RedisCacheConnector for when redis is not installed."""
    class RedisCacheConnector(CacheConnector):
        """Stub: Redis cache connector.

        Requires optional 'redis' dependency.
        Install with: pip install redis
        """

        async def connect(self) -> None:
            raise ImportError(
                "Redis caching requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise ImportError(
                "Redis caching requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def get(self, key: str) -> Optional[Any]:
            raise ImportError(
                "Redis caching requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def set(
            self, key: str, value: Any, ttl: Optional[int] = None
        ) -> None:
            raise ImportError(
                "Redis caching requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def delete(self, key: str) -> None:
            raise ImportError(
                "Redis caching requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def exists(self, key: str) -> bool:
            raise ImportError(
                "Redis caching requires the 'redis' package. "
                "Install with: pip install redis"
            )

    return RedisCacheConnector


if REDIS_AVAILABLE:

    class RedisCacheConnector(CacheConnector):
        """Redis cache connector for distributed caching.

        Uses Redis for high-performance, distributed caching across
        multiple processes and machines.

        Configuration:
            ConnectorConfig(
                name="redis_cache",
                connector_type="redis_cache",
                connection_string="redis://localhost:6379/0"
            )
        """

        def __init__(self, config: ConnectorConfig):
            """Initialize Redis cache connector."""
            super().__init__(config)
            self._client: Optional[redis.Redis] = None

        async def connect(self) -> None:
            """Connect to Redis."""
            if not self.config.connection_string:
                raise ValueError(
                    "Redis cache connector requires connection_string"
                )

            try:
                self._client = await redis.from_url(
                    self.config.connection_string,
                    decode_responses=True,
                )
                # Test connection
                await self._client.ping()
                self._connected = True
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise ConnectionError(f"Redis connection failed: {e}")

        async def disconnect(self) -> None:
            """Disconnect from Redis."""
            if self._client:
                try:
                    await self._client.close()
                except Exception as e:
                    logger.error(f"Error closing Redis connection: {e}")
            self._connected = False

        async def health_check(self) -> bool:
            """Check Redis connectivity."""
            if not self._client:
                return False

            try:
                await self._client.ping()
                return True
            except Exception:
                return False

        async def execute(self, operation: str, **kwargs) -> Any:
            """Execute cache operation.

            Operations:
                - get: Get value (requires 'key')
                - set: Set value (requires 'key', 'value', optional 'ttl')
                - delete: Delete key (requires 'key')
                - exists: Check existence (requires 'key')
                - clear: Clear all keys
            """
            if not self._connected or not self._client:
                raise RuntimeError("Redis cache is not connected")

            if operation == "get":
                return await self.get(kwargs.get("key"))
            elif operation == "set":
                await self.set(
                    kwargs.get("key"),
                    kwargs.get("value"),
                    kwargs.get("ttl"),
                )
                return True
            elif operation == "delete":
                await self.delete(kwargs.get("key"))
                return True
            elif operation == "exists":
                return await self.exists(kwargs.get("key"))
            elif operation == "clear":
                await self._client.flushdb()
                return True
            else:
                raise ValueError(f"Unknown cache operation: {operation}")

        async def get(self, key: str) -> Optional[Any]:
            """Get value from Redis."""
            if not self._client:
                return None

            try:
                value = await self._client.get(key)
                return value
            except Exception as e:
                logger.error(f"Error getting cache key {key}: {e}")
                return None

        async def set(
            self, key: str, value: Any, ttl: Optional[int] = None
        ) -> None:
            """Set value in Redis."""
            if not self._client:
                raise RuntimeError("Redis cache is not connected")

            try:
                await self._client.set(key, value, ex=ttl)
            except Exception as e:
                logger.error(f"Error setting cache key {key}: {e}")
                raise

        async def delete(self, key: str) -> None:
            """Delete key from Redis."""
            if not self._client:
                return

            try:
                await self._client.delete(key)
            except Exception as e:
                logger.error(f"Error deleting cache key {key}: {e}")

        async def exists(self, key: str) -> bool:
            """Check if key exists in Redis."""
            if not self._client:
                return False

            try:
                result = await self._client.exists(key)
                return result > 0
            except Exception:
                return False

else:
    RedisCacheConnector = _make_redis_stub()
