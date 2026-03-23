"""
SessionMemory: Tier 2, Redis-backed session memory.

Provides distributed, TTL-based storage across sessions.
Typical latency: ~10ms. Requires Redis connection.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    import aioredis
    from aioredis import Redis
except ImportError:
    aioredis = None
    Redis = None

logger = logging.getLogger(__name__)


class SessionMemory:
    """
    Redis-backed session memory tier.

    Stores session history with TTL-based expiration.
    Supports compaction and efficient queries.
    Latency: ~10ms. Requires Redis connection.
    """

    DEFAULT_TTL_SECONDS = 86400 * 7  # 7 days

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        """
        Initialize SessionMemory.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            ttl_seconds: TTL for stored data
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.redis: Optional[Redis] = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> Redis:
        """Lazy connect to Redis."""
        if self.redis is None:
            if aioredis is None:
                raise ImportError("aioredis is required for SessionMemory")
            self.redis = await aioredis.from_url(self.redis_url)
        return self.redis

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve full message history for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of messages in the session
        """
        try:
            redis = await self._connect()
            key = f"session:{session_id}:history"
            data = await redis.get(key)
            if data:
                return json.loads(data)
            return []
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    async def append(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        Append messages to session history.

        Args:
            session_id: The session identifier
            messages: Messages to append
        """
        try:
            redis = await self._connect()
            key = f"session:{session_id}:history"

            # Get existing history
            existing = await self.get_history(session_id)
            existing.extend(messages)

            # Store updated history with TTL
            await redis.setex(
                key,
                self.ttl_seconds,
                json.dumps(existing),
            )

            # Update last_updated timestamp
            await redis.setex(
                f"session:{session_id}:updated_at",
                self.ttl_seconds,
                datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Failed to append to session history: {e}")

    async def compact(self, session_id: str, keep_recent: int = 100) -> None:
        """
        Compact session history by keeping only recent messages.

        Args:
            session_id: The session identifier
            keep_recent: Number of recent messages to keep
        """
        try:
            history = await self.get_history(session_id)
            if len(history) > keep_recent:
                compacted = history[-keep_recent:]
                redis = await self._connect()
                key = f"session:{session_id}:history"
                await redis.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(compacted),
                )
                logger.info(
                    f"Compacted session {session_id}: "
                    f"{len(history)} -> {len(compacted)} messages"
                )
        except Exception as e:
            logger.error(f"Failed to compact session history: {e}")

    async def delete_session(self, session_id: str) -> None:
        """
        Delete a session and all its data.

        Args:
            session_id: The session identifier
        """
        try:
            redis = await self._connect()
            keys = [
                f"session:{session_id}:history",
                f"session:{session_id}:updated_at",
                f"session:{session_id}:metadata",
            ]
            await redis.delete(*keys)
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")

    async def set_metadata(self, session_id: str, metadata: Dict[str, Any]) -> None:
        """
        Store session metadata.

        Args:
            session_id: The session identifier
            metadata: Metadata to store
        """
        try:
            redis = await self._connect()
            key = f"session:{session_id}:metadata"
            await redis.setex(
                key,
                self.ttl_seconds,
                json.dumps(metadata),
            )
        except Exception as e:
            logger.error(f"Failed to set session metadata: {e}")

    async def get_metadata(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve session metadata.

        Args:
            session_id: The session identifier

        Returns:
            Session metadata
        """
        try:
            redis = await self._connect()
            key = f"session:{session_id}:metadata"
            data = await redis.get(key)
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            logger.error(f"Failed to get session metadata: {e}")
            return {}

    async def get_last_updated(self, session_id: str) -> Optional[datetime]:
        """
        Get the last update timestamp for a session.

        Args:
            session_id: The session identifier

        Returns:
            Last update timestamp or None
        """
        try:
            redis = await self._connect()
            key = f"session:{session_id}:updated_at"
            data = await redis.get(key)
            if data:
                return datetime.fromisoformat(data.decode() if isinstance(data, bytes) else data)
            return None
        except Exception as e:
            logger.error(f"Failed to get last updated: {e}")
            return None

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self.redis = None
