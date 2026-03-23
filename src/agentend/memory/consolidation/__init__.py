"""
Consolidation module for memory extraction and storage.

Exports:
- ConsolidationEngine: Protocol/interface for consolidation engines
- Mem0Engine: Integration with Mem0AI
- BuiltinEngine: Lightweight fallback implementation
"""

from .engine import ConsolidationEngine
from .mem0 import Mem0Engine
from .builtin import BuiltinEngine

__all__ = ["ConsolidationEngine", "Mem0Engine", "BuiltinEngine"]
