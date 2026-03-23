"""
BuiltinEngine: Lightweight memory consolidation without Mem0AI.

Provides a fallback implementation for memory extraction using
basic LLM prompting without external dependencies.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BuiltinEngine:
    """
    Lightweight memory consolidation engine without Mem0 dependency.

    Uses simple LLM-based extraction with basic memory storage.
    Suitable for small to medium workloads and development.
    """

    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-3-haiku-20240307",
    ):
        """
        Initialize BuiltinEngine.

        Args:
            model_provider: LLM provider (anthropic, openai, etc)
            model_name: Model name
        """
        self.model_provider = model_provider
        self.model_name = model_name
        self._memories: Dict[str, List[Dict[str, Any]]] = {}
        self._memory_counter: Dict[str, int] = {}

    async def _extract_memories(
        self,
        conversation_text: str,
    ) -> List[str]:
        """
        Extract key facts from conversation using heuristics.

        In a real implementation, this would call an LLM.
        For now, uses simple pattern matching.

        Args:
            conversation_text: Conversation text

        Returns:
            List of extracted facts
        """
        facts = []

        # Simple heuristic: look for "remember", "fact", "about" mentions
        lines = conversation_text.split("\n")
        for line in lines:
            line_lower = line.lower()
            if any(trigger in line_lower for trigger in ["remember", "fact", "about", "my name is", "i'm ", "i am "]):
                facts.append(line.strip())

        # In production, call Claude/GPT for actual extraction
        # response = await anthropic.messages.create(
        #     model=self.model_name,
        #     messages=[{
        #         "role": "user",
        #         "content": f"Extract key facts about the user from this conversation:\n\n{conversation_text}"
        #     }]
        # )
        # facts = parse_facts_from_response(response)

        return facts

    async def consolidate(
        self,
        messages: List[Dict[str, Any]],
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Consolidate memories from messages.

        Args:
            messages: Conversation messages
            user_id: User identifier

        Returns:
            Consolidation summary
        """
        try:
            # Format conversation
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
                for msg in messages
            ])

            # Extract memories
            extracted_facts = await self._extract_memories(conversation_text)

            # Initialize user's memory list if needed
            if user_id not in self._memories:
                self._memories[user_id] = []
                self._memory_counter[user_id] = 0

            # Add facts as memories
            added = 0
            for fact in extracted_facts:
                memory_id = f"{user_id}:{self._memory_counter[user_id]}"
                self._memories[user_id].append({
                    "id": memory_id,
                    "text": fact,
                    "created_at": datetime.utcnow().isoformat(),
                    "importance": 0.5,
                })
                self._memory_counter[user_id] += 1
                added += 1

            return {
                "added": added,
                "updated": 0,
                "deleted": 0,
                "noop": max(0, len(messages) - added),
            }
        except Exception as e:
            logger.error(f"Failed to consolidate: {e}")
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
        Add a new memory.

        Args:
            memory_text: Memory text
            user_id: User identifier
            metadata: Optional metadata

        Returns:
            Memory ID
        """
        if user_id not in self._memories:
            self._memories[user_id] = []
            self._memory_counter[user_id] = 0

        memory_id = f"{user_id}:{self._memory_counter[user_id]}"
        self._memories[user_id].append({
            "id": memory_id,
            "text": memory_text,
            "created_at": datetime.utcnow().isoformat(),
            "importance": metadata.get("importance", 0.5) if metadata else 0.5,
            "metadata": metadata or {},
        })
        self._memory_counter[user_id] += 1
        return memory_id

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search memories by simple text matching.

        Args:
            query: Search query
            user_id: User identifier
            limit: Max results

        Returns:
            List of matching memories
        """
        if user_id not in self._memories:
            return []

        query_lower = query.lower()
        results = [
            mem for mem in self._memories[user_id]
            if query_lower in mem["text"].lower()
        ]
        return results[:limit]

    async def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all memories for a user.

        Args:
            user_id: User identifier

        Returns:
            List of all memories
        """
        return self._memories.get(user_id, [])

    async def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory.

        Args:
            memory_id: Memory ID
            user_id: User identifier

        Returns:
            True if deleted
        """
        if user_id not in self._memories:
            return False

        original_length = len(self._memories[user_id])
        self._memories[user_id] = [
            m for m in self._memories[user_id]
            if m["id"] != memory_id
        ]
        return len(self._memories[user_id]) < original_length

    async def update(
        self,
        memory_id: str,
        memory_text: str,
        user_id: str,
    ) -> bool:
        """
        Update a memory.

        Args:
            memory_id: Memory ID
            memory_text: New text
            user_id: User identifier

        Returns:
            True if updated
        """
        if user_id not in self._memories:
            return False

        for mem in self._memories[user_id]:
            if mem["id"] == memory_id:
                mem["text"] = memory_text
                mem["updated_at"] = datetime.utcnow().isoformat()
                return True

        return False
