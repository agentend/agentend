"""
CoreBlocks: Tier 4, Letta-style pinned memory blocks.

Always loaded into context. Pinned facts that should never be forgotten.
In-process storage, no database required. Typical latency: <1ms.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CoreBlocks:
    """
    Letta-style pinned memory blocks.

    Always loaded into agent context. Used for critical information
    that should never be forgotten (user facts, system constraints, etc).
    In-process storage. Latency: <1ms.
    """

    def __init__(self):
        """Initialize core blocks storage."""
        self._blocks: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, str] = {}  # name -> id mapping

    def insert(
        self,
        name: str,
        content: str,
        block_type: str = "fact",
        priority: int = 0,
    ) -> str:
        """
        Insert a new core block.

        Args:
            name: Human-readable block name (must be unique)
            content: Block content
            block_type: Type of block (fact, constraint, instruction, context)
            priority: Priority for ordering in context (higher = more important)

        Returns:
            Block ID (same as name)

        Raises:
            ValueError: If block name already exists
        """
        if name in self._index:
            raise ValueError(f"Core block '{name}' already exists")

        block_id = name
        self._blocks[block_id] = {
            "id": block_id,
            "name": name,
            "content": content,
            "type": block_type,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._index[name] = block_id
        logger.info(f"Inserted core block: {name}")
        return block_id

    def replace(self, name: str, content: str, block_type: Optional[str] = None) -> str:
        """
        Replace an existing core block.

        Args:
            name: Block name
            content: New content
            block_type: Optional new block type

        Returns:
            Block ID

        Raises:
            ValueError: If block doesn't exist
        """
        if name not in self._index:
            raise ValueError(f"Core block '{name}' not found")

        block_id = self._index[name]
        block = self._blocks[block_id]
        block["content"] = content
        block["updated_at"] = datetime.utcnow().isoformat()
        if block_type:
            block["type"] = block_type

        logger.info(f"Replaced core block: {name}")
        return block_id

    def get_block(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a single core block by name.

        Args:
            name: Block name

        Returns:
            Block data or None if not found
        """
        block_id = self._index.get(name)
        if block_id:
            return dict(self._blocks[block_id])
        return None

    def get_blocks(
        self,
        block_type: Optional[str] = None,
        sort_by_priority: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get all core blocks, optionally filtered by type.

        Args:
            block_type: Optional filter by block type
            sort_by_priority: Whether to sort by priority (descending)

        Returns:
            List of blocks
        """
        blocks = list(self._blocks.values())

        if block_type:
            blocks = [b for b in blocks if b["type"] == block_type]

        if sort_by_priority:
            blocks.sort(key=lambda x: x["priority"], reverse=True)

        return blocks

    def delete(self, name: str) -> bool:
        """
        Delete a core block.

        Args:
            name: Block name

        Returns:
            True if deleted, False if not found
        """
        if name not in self._index:
            return False

        block_id = self._index.pop(name)
        del self._blocks[block_id]
        logger.info(f"Deleted core block: {name}")
        return True

    def exists(self, name: str) -> bool:
        """
        Check if a core block exists.

        Args:
            name: Block name

        Returns:
            True if block exists
        """
        return name in self._index

    def rethink(
        self,
        name: str,
        new_content: str,
        reason: str = "",
    ) -> str:
        """
        Update a core block with reasoning.

        Letta-style "rethinking" - update with context about why.

        Args:
            name: Block name
            new_content: New content
            reason: Reason for the rethink

        Returns:
            Block ID

        Raises:
            ValueError: If block doesn't exist
        """
        if name not in self._index:
            raise ValueError(f"Core block '{name}' not found")

        block_id = self._index[name]
        block = self._blocks[block_id]

        # Store previous content
        if "history" not in block:
            block["history"] = []

        block["history"].append({
            "content": block["content"],
            "reason": reason,
            "timestamp": block["updated_at"],
        })

        block["content"] = new_content
        block["updated_at"] = datetime.utcnow().isoformat()

        logger.info(f"Rethought core block: {name}")
        return block_id

    def get_context_string(self, max_blocks: int = 10) -> str:
        """
        Generate a formatted string for context inclusion.

        Args:
            max_blocks: Maximum blocks to include

        Returns:
            Formatted string for context
        """
        blocks = self.get_blocks(sort_by_priority=True)[:max_blocks]

        if not blocks:
            return "No core blocks."

        lines = ["Core Blocks:"]
        for block in blocks:
            lines.append(f"\n{block['name']} ({block['type']}):")
            lines.append(f"  {block['content']}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all core blocks."""
        self._blocks.clear()
        self._index.clear()
        logger.info("Cleared all core blocks")

    def get_size(self) -> int:
        """Get number of core blocks."""
        return len(self._blocks)

    def get_names(self) -> List[str]:
        """Get all block names."""
        return list(self._index.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about core blocks."""
        blocks = self.get_blocks()
        type_counts = {}
        for block in blocks:
            block_type = block["type"]
            type_counts[block_type] = type_counts.get(block_type, 0) + 1

        return {
            "total_blocks": len(blocks),
            "type_counts": type_counts,
            "avg_priority": (
                sum(b["priority"] for b in blocks) / len(blocks)
                if blocks else 0
            ),
        }
