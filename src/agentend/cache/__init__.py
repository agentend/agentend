"""Cache module for agentend framework."""

try:
    from .semantic_cache import SemanticCache
except ImportError:
    SemanticCache = None

__all__ = ["SemanticCache"]
