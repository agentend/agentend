"""
Configuration dataclasses for memory system.

Separated to avoid circular imports.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class MemoryConfig:
    """Configuration for memory system."""
    redis_url: Optional[str] = None
    postgres_url: Optional[str] = None
    model_provider: str = "anthropic"
    model_name: str = "claude-3-haiku-20240307"
    consolidation_engine: str = "mem0"  # "mem0" or "builtin"
    mem0_api_key: Optional[str] = None

    # Hydration stages
    enable_stage1: bool = True  # Core blocks + working
    enable_stage2: bool = True  # Session memory
    enable_stage3: bool = True  # Semantic search
    enable_stage4: bool = True  # Agent-driven retrieve_context


@dataclass
class RequestContext:
    """Context of an incoming request."""
    session_id: str
    user_id: str
    user_query: str
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class MemoryContext:
    """Hydrated memory context for a request."""
    core_blocks: list[Dict[str, Any]]
    working_memory: Dict[str, Any]
    session_history: list[Dict[str, Any]]
    semantic_results: list[Dict[str, Any]]
    stage_timing: Dict[str, float]  # Timing of each hydration stage
