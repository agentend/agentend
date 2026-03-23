"""
ContextBus: Orchestrator for all memory tiers with progressive hydration.

Coordinates working memory, session memory, semantic memory, and core blocks.
Implements graceful degradation when Redis or PostgreSQL are unavailable.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .config import MemoryConfig, RequestContext, MemoryContext
from .working import WorkingMemory
from .session import SessionMemory
from .semantic import SemanticMemory
from .core_blocks import CoreBlocks
from .hydration import ProgressiveHydration
from .consolidation.engine import ConsolidationEngine
from .consolidation.mem0 import Mem0Engine
from .consolidation.builtin import BuiltinEngine

logger = logging.getLogger(__name__)


class ContextBus:
    """
    Orchestrator for all memory tiers with progressive hydration.

    Implements a 4-stage hydration pipeline:
    1. Core blocks + working memory (always available)
    2. Session memory (Redis-backed)
    3. Semantic memory (pgvector search)
    4. Agent-driven retrieve_context tool

    Provides graceful degradation if Redis/PostgreSQL are unavailable.
    """

    def __init__(self, config: MemoryConfig):
        """
        Initialize ContextBus with configuration.

        Args:
            config: Memory configuration
        """
        self.config = config
        self.working_memory = WorkingMemory()

        # Initialize optional tiers with graceful degradation
        self.session_memory: Optional[SessionMemory] = None
        self.semantic_memory: Optional[SemanticMemory] = None
        self.core_blocks = CoreBlocks()

        self._init_session_memory()
        self._init_semantic_memory()

        # Initialize consolidation engine
        self.consolidation_engine = self._init_consolidation_engine()

        # Progressive hydration
        self.hydration = ProgressiveHydration(
            core_blocks=self.core_blocks,
            working_memory=self.working_memory,
            session_memory=self.session_memory,
            semantic_memory=self.semantic_memory,
            config=config,
        )

    def _init_session_memory(self) -> None:
        """Initialize session memory with graceful degradation."""
        if not self.config.redis_url:
            logger.warning("Redis URL not provided, session memory disabled")
            return

        try:
            self.session_memory = SessionMemory(redis_url=self.config.redis_url)
        except Exception as e:
            logger.error(f"Failed to initialize session memory: {e}")
            self.session_memory = None

    def _init_semantic_memory(self) -> None:
        """Initialize semantic memory with graceful degradation."""
        if not self.config.postgres_url:
            logger.warning("PostgreSQL URL not provided, semantic memory disabled")
            return

        try:
            self.semantic_memory = SemanticMemory(
                postgres_url=self.config.postgres_url,
                model_provider=self.config.model_provider,
                model_name=self.config.model_name,
            )
        except Exception as e:
            logger.error(f"Failed to initialize semantic memory: {e}")
            self.semantic_memory = None

    def _init_consolidation_engine(self) -> ConsolidationEngine:
        """Initialize consolidation engine based on config."""
        if self.config.consolidation_engine == "mem0" and self.config.mem0_api_key:
            return Mem0Engine(api_key=self.config.mem0_api_key)
        else:
            return BuiltinEngine(
                model_provider=self.config.model_provider,
                model_name=self.config.model_name,
            )

    async def hydrate(self, request: RequestContext) -> MemoryContext:
        """
        Progressive hydration: load memory in 4 stages.

        Stage 1: Core blocks + working memory (always available, <1ms)
        Stage 2: Session history (Redis, ~10ms)
        Stage 3: Semantic search (pgvector, ~100ms)
        Stage 4: Agent-driven retrieve_context tool (agent calls)

        Args:
            request: Request context with session_id, user_id, user_query

        Returns:
            MemoryContext with hydrated memory across all tiers
        """
        return await self.hydration.hydrate(request)

    async def store(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        user_id: str,
    ) -> None:
        """
        Post-request storage: persist messages to appropriate tiers.

        Args:
            session_id: Session identifier
            messages: List of messages from the request
            user_id: User identifier
        """
        # Store in working memory (always succeeds)
        for msg in messages:
            key = f"{session_id}:{msg.get('role', 'unknown')}"
            self.working_memory.set(key, msg)

        # Store in session memory (graceful degradation)
        if self.session_memory:
            try:
                await self.session_memory.append(session_id, messages)
            except Exception as e:
                logger.error(f"Failed to store in session memory: {e}")

        # Store in semantic memory (graceful degradation)
        if self.semantic_memory:
            try:
                for msg in messages:
                    if msg.get("role") == "assistant":
                        await self.semantic_memory.store(
                            text=msg.get("content", ""),
                            session_id=session_id,
                            user_id=user_id,
                        )
            except Exception as e:
                logger.error(f"Failed to store in semantic memory: {e}")

    async def extract_and_consolidate(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        user_id: str,
    ) -> None:
        """
        Trigger consolidation engine to extract and store memories.

        Args:
            session_id: Session identifier
            messages: Messages from the conversation
            user_id: User identifier
        """
        try:
            await self.consolidation_engine.consolidate(messages, user_id)
        except Exception as e:
            logger.error(f"Failed to consolidate memories: {e}")

    async def close(self) -> None:
        """Clean up resources."""
        if self.session_memory:
            await self.session_memory.close()
        if self.semantic_memory:
            await self.semantic_memory.close()
