"""
ProgressiveHydration: 4-stage memory loading pipeline.

Stage 1: Core blocks + working memory (always available, <1ms)
Stage 2: Session history (Redis, ~10ms)
Stage 3: Semantic search (pgvector, ~100ms)
Stage 4: Agent-driven retrieve_context tool
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .config import MemoryConfig, RequestContext, MemoryContext
from .working import WorkingMemory
from .session import SessionMemory
from .semantic import SemanticMemory
from .core_blocks import CoreBlocks

logger = logging.getLogger(__name__)


class ProgressiveHydration:
    """
    Progressive memory hydration across 4 stages.

    Loads memory in stages to minimize latency while maximizing available context.
    Each stage is optional and gracefully skipped if not available.
    """

    def __init__(
        self,
        core_blocks: CoreBlocks,
        working_memory: WorkingMemory,
        session_memory: Optional[SessionMemory],
        semantic_memory: Optional[SemanticMemory],
        config: MemoryConfig,
    ):
        """
        Initialize progressive hydration.

        Args:
            core_blocks: Core blocks tier
            working_memory: Working memory tier
            session_memory: Session memory tier (optional)
            semantic_memory: Semantic memory tier (optional)
            config: Memory configuration
        """
        self.core_blocks = core_blocks
        self.working_memory = working_memory
        self.session_memory = session_memory
        self.semantic_memory = semantic_memory
        self.config = config

    async def hydrate(self, request: RequestContext) -> MemoryContext:
        """
        Execute 4-stage progressive hydration.

        Args:
            request: Request context

        Returns:
            Hydrated memory context with timing information
        """
        stage_timing = {}

        # Stage 1: Core blocks + working memory (always, <1ms)
        if self.config.enable_stage1:
            start = time.time()
            core_blocks = self.core_blocks.get_blocks(sort_by_priority=True)
            working_mem = self.working_memory.get_all()
            stage_timing["stage1"] = time.time() - start
        else:
            core_blocks = []
            working_mem = {}
            stage_timing["stage1"] = 0

        # Stage 2: Session history (Redis, ~10ms)
        session_history = []
        if self.config.enable_stage2 and self.session_memory:
            start = time.time()
            try:
                session_history = await self.session_memory.get_history(
                    request.session_id
                )
            except Exception as e:
                logger.error(f"Stage 2 error: {e}")
            stage_timing["stage2"] = time.time() - start
        else:
            stage_timing["stage2"] = 0

        # Stage 3: Semantic search (pgvector, ~100ms)
        semantic_results = []
        if self.config.enable_stage3 and self.semantic_memory:
            start = time.time()
            try:
                semantic_results = await self.semantic_memory.search(
                    query=request.user_query,
                    user_id=request.user_id,
                    top_k=5,
                )
            except Exception as e:
                logger.error(f"Stage 3 error: {e}")
            stage_timing["stage3"] = time.time() - start
        else:
            stage_timing["stage3"] = 0

        # Stage 4: Agent-driven retrieve_context (handled by agent)
        stage_timing["stage4"] = 0  # Recorded when agent calls retrieve_context

        return MemoryContext(
            core_blocks=core_blocks,
            working_memory=working_mem,
            session_history=session_history,
            semantic_results=semantic_results,
            stage_timing=stage_timing,
        )

    async def hydrate_with_timeout(
        self,
        request: RequestContext,
        timeout_ms: int = 200,
    ) -> MemoryContext:
        """
        Hydrate with a timeout, gracefully degrading stages.

        If total time exceeds timeout, skip remaining stages.

        Args:
            request: Request context
            timeout_ms: Timeout in milliseconds

        Returns:
            Hydrated memory context (may be partial)
        """
        timeout_sec = timeout_ms / 1000.0

        try:
            return await asyncio.wait_for(
                self.hydrate(request),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Hydration timeout after {timeout_ms}ms")
            # Return what we have from fastest stages
            start = time.time()
            core_blocks = self.core_blocks.get_blocks(sort_by_priority=True)
            working_mem = self.working_memory.get_all()
            elapsed = time.time() - start

            return MemoryContext(
                core_blocks=core_blocks,
                working_memory=working_mem,
                session_history=[],
                semantic_results=[],
                stage_timing={
                    "stage1": elapsed,
                    "stage2": 0,
                    "stage3": 0,
                    "stage4": 0,
                },
            )

    async def retrieve_context(
        self,
        session_id: str,
        user_id: str,
        query: str,
        context_limit: int = 4000,
    ) -> str:
        """
        Build a formatted context string for agent inclusion.

        Called by agent's retrieve_context tool (Stage 4).

        Args:
            session_id: Session ID
            user_id: User ID
            query: Current query
            context_limit: Max tokens for context

        Returns:
            Formatted context string
        """
        start = time.time()
        context_parts = []

        # Add core blocks
        core_blocks_str = self.core_blocks.get_context_string(max_blocks=5)
        context_parts.append(core_blocks_str)

        # Add recent session history
        if self.session_memory:
            try:
                history = await self.session_memory.get_history(session_id)
                if history:
                    recent = history[-10:]  # Last 10 messages
                    context_parts.append(f"\nRecent History ({len(recent)} messages):")
                    for msg in recent:
                        context_parts.append(
                            f"  {msg.get('role', 'unknown')}: {msg.get('content', '')[:100]}"
                        )
            except Exception as e:
                logger.error(f"Error retrieving session history: {e}")

        # Add semantic results
        if self.semantic_memory:
            try:
                results = await self.semantic_memory.search(
                    query=query,
                    user_id=user_id,
                    top_k=3,
                )
                if results:
                    context_parts.append("\nRelevant Memories:")
                    for result in results:
                        context_parts.append(f"  - {result['text'][:100]}")
            except Exception as e:
                logger.error(f"Error searching semantic memory: {e}")

        context = "\n".join(context_parts)

        # Truncate to limit
        if len(context) > context_limit:
            context = context[:context_limit] + "\n[truncated]"

        elapsed = time.time() - start
        logger.debug(f"retrieve_context took {elapsed:.3f}s")

        return context
