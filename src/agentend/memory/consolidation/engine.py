"""
ConsolidationEngine: Abstract protocol for memory consolidation engines.

Consolidation engines are responsible for extracting, classifying, and storing
memories from conversations using LLM-based analysis.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal


class ConsolidationEngine(ABC):
    """
    Abstract base for memory consolidation engines.

    Consolidation engines analyze conversations and extract/update long-term memories.
    They classify each memory as: ADD, UPDATE, DELETE, or NOOP.
    """

    @abstractmethod
    async def consolidate(
        self,
        messages: List[Dict[str, Any]],
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Consolidate memories from conversation messages.

        Analyzes the messages, extracts facts/insights, and updates long-term memory.
        Returns summary of changes made.

        Args:
            messages: List of conversation messages with 'role' and 'content'
            user_id: User identifier for scoping memories

        Returns:
            Dictionary with:
            - added: List of newly added memories
            - updated: List of updated memories
            - deleted: List of deleted memories
            - noop: Number of messages that resulted in no action
        """
        pass

    @abstractmethod
    async def add(
        self,
        memory_text: str,
        user_id: str,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Add a new memory.

        Args:
            memory_text: Text of the memory
            user_id: User identifier
            metadata: Optional metadata

        Returns:
            Memory ID
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search memories.

        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results

        Returns:
            List of matching memories
        """
        pass

    @abstractmethod
    async def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all memories for a user.

        Args:
            user_id: User identifier

        Returns:
            List of all memories
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory.

        Args:
            memory_id: Memory ID
            user_id: User identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def update(
        self,
        memory_id: str,
        memory_text: str,
        user_id: str,
    ) -> bool:
        """
        Update an existing memory.

        Args:
            memory_id: Memory ID
            memory_text: New memory text
            user_id: User identifier

        Returns:
            True if updated, False if not found
        """
        pass
