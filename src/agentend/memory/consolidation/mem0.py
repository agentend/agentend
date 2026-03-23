"""
Mem0Engine: Integration with Mem0AI for memory consolidation.

Wraps the mem0ai SDK to provide production-grade memory management.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from mem0 import MemoryClient
except ImportError:
    MemoryClient = None


class Mem0Engine:
    """
    Mem0AI-based consolidation engine.

    Uses the Mem0AI SDK to provide intelligent memory extraction,
    update detection, and storage with composite scoring.
    """

    def __init__(self, api_key: str):
        """
        Initialize Mem0Engine.

        Args:
            api_key: Mem0AI API key
        """
        if MemoryClient is None:
            raise ImportError("mem0-ai SDK is required for Mem0Engine")

        self.api_key = api_key
        self.client = MemoryClient(api_key=api_key)

    async def consolidate(
        self,
        messages: List[Dict[str, Any]],
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Consolidate memories from messages using Mem0.

        Sends messages to Mem0 API, which classifies each as:
        ADD, UPDATE, DELETE, or NOOP.

        Args:
            messages: List of conversation messages
            user_id: User identifier

        Returns:
            Consolidation summary with added/updated/deleted/noop counts
        """
        try:
            # Format messages for Mem0
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
                for msg in messages
            ])

            # Add to Mem0 - API will handle classification
            result = self.client.add(
                data=conversation_text,
                user_id=user_id,
                metadata={"source": "agentend_consolidation"},
            )

            return {
                "added": 1 if result else 0,
                "updated": 0,
                "deleted": 0,
                "noop": 0,
                "mem0_response": result,
            }
        except Exception as e:
            logger.error(f"Failed to consolidate with Mem0: {e}")
            return {
                "added": 0,
                "updated": 0,
                "deleted": 0,
                "noop": len(messages),
                "error": str(e),
            }

    async def add(
        self,
        memory_text: str,
        user_id: str,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Add a new memory via Mem0.

        Args:
            memory_text: Memory text
            user_id: User identifier
            metadata: Optional metadata

        Returns:
            Memory ID from Mem0
        """
        try:
            result = self.client.add(
                data=memory_text,
                user_id=user_id,
                metadata=metadata or {},
            )
            return result.get("id", "") if isinstance(result, dict) else str(result)
        except Exception as e:
            logger.error(f"Failed to add memory to Mem0: {e}")
            return ""

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search memories in Mem0.

        Args:
            query: Search query
            user_id: User identifier
            limit: Max results

        Returns:
            List of matching memories
        """
        try:
            results = self.client.search(
                query=query,
                user_id=user_id,
                limit=limit,
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.error(f"Failed to search memories in Mem0: {e}")
            return []

    async def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all memories for a user from Mem0.

        Args:
            user_id: User identifier

        Returns:
            List of all memories
        """
        try:
            results = self.client.get_all(user_id=user_id)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.error(f"Failed to get all memories from Mem0: {e}")
            return []

    async def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory from Mem0.

        Args:
            memory_id: Memory ID
            user_id: User identifier

        Returns:
            True if deleted
        """
        try:
            self.client.delete(memory_id=memory_id, user_id=user_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory from Mem0: {e}")
            return False

    async def update(
        self,
        memory_id: str,
        memory_text: str,
        user_id: str,
    ) -> bool:
        """
        Update a memory in Mem0.

        Args:
            memory_id: Memory ID
            memory_text: New text
            user_id: User identifier

        Returns:
            True if updated
        """
        try:
            self.client.update(
                memory_id=memory_id,
                data=memory_text,
                user_id=user_id,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update memory in Mem0: {e}")
            return False
