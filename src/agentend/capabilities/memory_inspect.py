"""Memory inspect capability: returns memory tier contents for current session."""

import logging
from typing import Any, Dict

from agentend.kernel.kernel import RequestContext

logger = logging.getLogger(__name__)


class MemoryInspectCapability:
    """Returns memory tier contents for the current session.

    Inspects working memory (in-process dict), session memory (Redis),
    and reports availability of semantic and consolidation tiers.
    """

    name: str = "memory.inspect"
    description: str = "Returns memory tier contents for current session"

    async def execute(self, context: RequestContext, **kwargs: Any) -> Dict[str, Any]:
        """Inspect memory tiers for the current session.

        Args:
            context: Request context with session_id and app state in metadata.

        Returns:
            Dict with memory tier contents.
        """
        session_id = context.session_id
        tiers: Dict[str, Any] = {}

        # Tier 1: Working memory
        context_bus = context.metadata.get("context_bus")
        if context_bus is not None:
            working = context_bus.working_memory
            session_keys = working.get_with_prefix(f"{session_id}:")
            tiers["working"] = {
                "total_keys": working.get_size(),
                "session_keys": len(session_keys),
                "entries": session_keys,
            }
        else:
            tiers["working"] = {"status": "unavailable", "detail": "ContextBus not initialized"}

        # Tier 2: Session memory (Redis)
        if context_bus is not None and context_bus.session_memory is not None:
            try:
                history = await context_bus.session_memory.get_history(session_id)
                metadata = await context_bus.session_memory.get_metadata(session_id)
                tiers["session"] = {
                    "message_count": len(history),
                    "messages": history[-10:],  # Last 10 messages
                    "metadata": metadata,
                }
            except Exception as e:
                logger.warning(f"Failed to inspect session memory: {e}")
                tiers["session"] = {"status": "error", "detail": str(e)}
        else:
            tiers["session"] = {"status": "unavailable", "detail": "Redis not connected"}

        # Tier 3: Semantic memory
        if context_bus is not None and context_bus.semantic_memory is not None:
            tiers["semantic"] = {"status": "available"}
        else:
            tiers["semantic"] = {"status": "unavailable"}

        # Tier 4: Core blocks
        if context_bus is not None:
            tiers["core_blocks"] = {"status": "available"}
        else:
            tiers["core_blocks"] = {"status": "unavailable"}

        # Tier 5: Consolidation
        if context_bus is not None and context_bus.consolidation_engine is not None:
            engine_type = type(context_bus.consolidation_engine).__name__
            tiers["consolidation"] = {"status": "available", "engine": engine_type}
        else:
            tiers["consolidation"] = {"status": "unavailable"}

        return {
            "capability": "memory.inspect",
            "session_id": session_id,
            "tiers": tiers,
        }
