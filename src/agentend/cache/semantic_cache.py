"""Semantic caching with dual-layer (Redis + pgvector)."""

from typing import Optional, Any, List
import json
import hashlib

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    AsyncSession = None


class SemanticCache:
    """
    Dual-layer semantic cache: L1 exact hash (Redis), L2 embedding similarity (pgvector).

    Provides get(), set(), invalidate() operations with per-worker cache policies.
    """

    def __init__(
        self,
        redis_client,
        db_session,
        default_ttl: int = 3600,
        similarity_threshold: float = 0.95,
    ):
        """
        Initialize semantic cache.

        Args:
            redis_client: Redis client for L1 cache.
            db_session: SQLAlchemy async session for L2 (pgvector).
            default_ttl: Default time-to-live in seconds.
            similarity_threshold: Threshold for semantic similarity match (0-1).
        """
        if redis is None:
            raise ImportError("Install agentend[memory] for Redis support")
        if AsyncSession is None:
            raise ImportError("Install agentend[persistence] for SQLAlchemy support")
        self.redis = redis_client
        self.db = db_session
        self.default_ttl = default_ttl
        self.similarity_threshold = similarity_threshold

    async def get(
        self,
        key: str,
        embedding: Optional[List[float]] = None,
        worker_id: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Get value from cache with L1 (exact) and L2 (semantic) lookup.

        Args:
            key: Cache key.
            embedding: Optional embedding for semantic search.
            worker_id: Worker ID for worker-specific cache policies.

        Returns:
            Cached value or None.
        """
        # Check if this worker skips cache
        if worker_id and await self._should_skip_cache(worker_id):
            return None

        # L1: Try exact hash lookup in Redis
        cache_key = self._make_key(key)
        value = await self.redis.get(cache_key)
        if value:
            return json.loads(value)

        # L2: Try semantic lookup if embedding provided
        if embedding and len(embedding) > 0:
            semantic_result = await self._semantic_lookup(embedding, key)
            if semantic_result:
                return semantic_result

        return None

    async def set(
        self,
        key: str,
        value: Any,
        embedding: Optional[List[float]] = None,
        ttl: Optional[int] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        """
        Set value in cache with L1 and optional L2 storage.

        Args:
            key: Cache key.
            value: Value to cache.
            embedding: Optional embedding for semantic search.
            ttl: Time-to-live in seconds (uses default if None).
            worker_id: Worker ID for worker-specific policies.
        """
        if worker_id and await self._should_skip_cache(worker_id):
            return

        ttl = ttl or self.default_ttl
        cache_key = self._make_key(key)

        # L1: Store in Redis
        await self.redis.setex(
            cache_key,
            ttl,
            json.dumps(value),
        )

        # L2: Store with embedding if provided
        if embedding and len(embedding) > 0:
            await self._store_semantic(key, value, embedding, worker_id)

    async def invalidate(
        self,
        key: Optional[str] = None,
        pattern: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate.
            pattern: Pattern to match keys (e.g., "user:123:*").
            worker_id: Worker-specific invalidation.

        Returns:
            Number of keys invalidated.
        """
        count = 0

        if key:
            cache_key = self._make_key(key)
            count += await self.redis.delete(cache_key)
            await self._delete_semantic(key)

        elif pattern:
            pattern_key = self._make_key(pattern)
            keys = await self.redis.keys(pattern_key)
            if keys:
                count += await self.redis.delete(*keys)

        return count

    async def _should_skip_cache(self, worker_id: str) -> bool:
        """Check if worker has cache skip policy."""
        # Placeholder: Check worker config
        # In production, query worker_configs table
        skip_cache_workers = {"streaming-worker", "realtime-worker"}
        return worker_id in skip_cache_workers

    async def _semantic_lookup(
        self,
        embedding: List[float],
        namespace: str,
    ) -> Optional[Any]:
        """
        Lookup similar vectors using pgvector.

        Args:
            embedding: Query embedding.
            namespace: Cache namespace/type.

        Returns:
            Cached value from similar embedding or None.
        """
        # Placeholder: This would query pgvector
        # Example SQL: SELECT value FROM semantic_cache
        #             WHERE namespace = ?
        #             ORDER BY embedding <-> %s LIMIT 1
        # WHERE similarity > threshold
        return None

    async def _store_semantic(
        self,
        key: str,
        value: Any,
        embedding: List[float],
        worker_id: Optional[str] = None,
    ) -> None:
        """Store value with embedding for semantic search."""
        # Placeholder: Store to semantic_cache table with pgvector
        pass

    async def _delete_semantic(self, key: str) -> None:
        """Delete semantic cache entry."""
        # Placeholder: Delete from semantic_cache table
        pass

    def _make_key(self, key: str) -> str:
        """Make Redis key with prefix."""
        return f"cache:{key}"

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "l1_backend": "redis",
            "l2_backend": "pgvector",
            "default_ttl": self.default_ttl,
            "similarity_threshold": self.similarity_threshold,
        }
