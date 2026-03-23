"""
SemanticMemory: Tier 3, pgvector-backed semantic search memory.

Provides vector-based semantic search over memories.
Typical latency: ~100ms. Requires PostgreSQL with pgvector.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    asyncpg = None
    HAS_ASYNCPG = False

logger = logging.getLogger(__name__)


class SemanticMemory:
    """
    PostgreSQL/pgvector-backed semantic memory tier.

    Stores factual memories with vector embeddings for semantic search.
    Implements composite scoring: similarity + recency + importance + frequency.
    Latency: ~100ms. Requires PostgreSQL with pgvector extension.
    """

    def __init__(
        self,
        postgres_url: str,
        model_provider: str = "anthropic",
        model_name: str = "claude-3-haiku-20240307",
    ):
        """
        Initialize SemanticMemory.

        Args:
            postgres_url: PostgreSQL connection URL
            model_provider: Embedding model provider
            model_name: Embedding model name
        """
        self.postgres_url = postgres_url
        self.model_provider = model_provider
        self.model_name = model_name
        self.pool: Optional[Any] = None
        self._embedding_cache: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def _connect(self) -> Any:
        """Lazy connect to PostgreSQL."""
        if self.pool is None:
            if not HAS_ASYNCPG:
                raise ImportError("asyncpg is required for SemanticMemory")
            self.pool = await asyncpg.create_pool(self.postgres_url)
            await self._init_schema()
        return self.pool

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        try:
            pool = self.pool
            async with pool.acquire() as conn:
                # Create extension if not exists
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

                # Create memories table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS semantic_memories (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        text TEXT NOT NULL,
                        embedding vector(1536),
                        importance FLOAT DEFAULT 0.5,
                        frequency INT DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX (session_id),
                        INDEX (user_id)
                    )
                """)

                # Create indices for vector similarity
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS semantic_memories_embedding_idx
                    ON semantic_memories
                    USING ivfflat (embedding vector_cosine_ops)
                """)

                logger.info("Semantic memory schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text. Uses mock implementation for now.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        # Mock embedding: deterministic hash-based vector
        # In production, use actual embedding model
        hash_val = hash(text)
        embedding = [
            float((hash_val >> (i * 8)) & 0xFF) / 256.0
            for i in range(1536)
        ]
        self._embedding_cache[text] = embedding
        return embedding

    async def store(
        self,
        text: str,
        session_id: str,
        user_id: str,
        importance: float = 0.5,
    ) -> int:
        """
        Store a semantic memory.

        Args:
            text: The memory text
            session_id: Session identifier
            user_id: User identifier
            importance: Importance score (0-1)

        Returns:
            Memory ID
        """
        try:
            pool = await self._connect()
            embedding = await self._get_embedding(text)

            async with pool.acquire() as conn:
                memory_id = await conn.fetchval("""
                    INSERT INTO semantic_memories
                    (session_id, user_id, text, embedding, importance)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, session_id, user_id, text, embedding, importance)

            return memory_id
        except Exception as e:
            logger.error(f"Failed to store semantic memory: {e}")
            return -1

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search semantic memories with composite scoring.

        Uses: α·similarity + β·recency_decay + γ·importance + δ·frequency
        Defaults: α=0.6, β=0.2, γ=0.1, δ=0.1

        Args:
            query: Query text
            user_id: User identifier
            top_k: Number of results
            filters: Optional filters (e.g., {"session_id": "xyz"})

        Returns:
            List of memory results with scores
        """
        try:
            pool = await self._connect()
            embedding = await self._get_embedding(query)

            async with pool.acquire() as conn:
                # Get candidate memories
                query_sql = """
                    SELECT
                        id,
                        session_id,
                        text,
                        importance,
                        frequency,
                        created_at,
                        1 - (embedding <=> $1) as similarity
                    FROM semantic_memories
                    WHERE user_id = $2
                """

                params = [embedding, user_id]

                if filters:
                    if "session_id" in filters:
                        query_sql += " AND session_id = $3"
                        params.append(filters["session_id"])

                query_sql += " LIMIT 100"

                rows = await conn.fetch(query_sql, *params)

            # Score and sort
            scored_results = []
            now = datetime.utcnow()

            for row in rows:
                # Composite scoring
                similarity = row["similarity"]
                age_hours = (now - row["created_at"]).total_seconds() / 3600
                recency = max(0, 1 - (age_hours / 168))  # Decay over week
                importance = row["importance"]
                frequency_norm = min(row["frequency"] / 10, 1.0)

                score = (
                    0.6 * similarity +
                    0.2 * recency +
                    0.1 * importance +
                    0.1 * frequency_norm
                )

                scored_results.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "text": row["text"],
                    "score": score,
                    "similarity": similarity,
                    "importance": importance,
                    "frequency": row["frequency"],
                })

            # Sort by score and return top_k
            scored_results.sort(key=lambda x: x["score"], reverse=True)
            return scored_results[:top_k]

        except Exception as e:
            logger.error(f"Failed to search semantic memory: {e}")
            return []

    async def score(
        self,
        memory_id: int,
        alpha: float = 0.6,
        beta: float = 0.2,
        gamma: float = 0.1,
        delta: float = 0.1,
    ) -> float:
        """
        Get composite score for a memory.

        Args:
            memory_id: Memory ID
            alpha: Weight for similarity
            beta: Weight for recency
            gamma: Weight for importance
            delta: Weight for frequency

        Returns:
            Composite score
        """
        try:
            pool = await self._connect()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT importance, frequency, created_at "
                    "FROM semantic_memories WHERE id = $1",
                    memory_id,
                )

            if not row:
                return 0.0

            now = datetime.utcnow()
            age_hours = (now - row["created_at"]).total_seconds() / 3600
            recency = max(0, 1 - (age_hours / 168))

            score = (
                alpha * 0.5 +  # Assume moderate similarity
                beta * recency +
                gamma * row["importance"] +
                delta * min(row["frequency"] / 10, 1.0)
            )
            return score
        except Exception as e:
            logger.error(f"Failed to score memory: {e}")
            return 0.0

    async def update_frequency(self, memory_id: int) -> None:
        """
        Increment frequency counter for a memory.

        Args:
            memory_id: Memory ID
        """
        try:
            pool = await self._connect()
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE semantic_memories
                    SET frequency = frequency + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """, memory_id)
        except Exception as e:
            logger.error(f"Failed to update frequency: {e}")

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
