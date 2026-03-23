"""
Memory module for agentend framework.

Exports:
- ContextBus: Orchestrator for all memory tiers with progressive hydration
- MemoryTier: Enum for different memory tier types
"""

from enum import Enum
from .bus import ContextBus

__all__ = ["ContextBus", "MemoryTier"]


class MemoryTier(Enum):
    """Enumeration of memory tiers in the hierarchy."""
    WORKING = "working"
    SESSION = "session"
    SEMANTIC = "semantic"
    CORE_BLOCKS = "core_blocks"
