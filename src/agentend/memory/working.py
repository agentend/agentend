"""
WorkingMemory: Tier 1, in-process dictionary-backed memory.

Provides fast, in-memory storage for the current session.
Typical latency: <1ms. Not persistent across restarts.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkingMemory:
    """
    In-process, dictionary-backed memory tier.

    Stores transient data for the current session with sub-millisecond latency.
    All operations are synchronous. Data is lost on restart.
    """

    def __init__(self):
        """Initialize working memory with empty store."""
        self._store: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value by key.

        Args:
            key: The key to retrieve
            default: Default value if key not found

        Returns:
            The stored value or default
        """
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Store a value by key.

        Args:
            key: The key to store under
            value: The value to store
        """
        self._store[key] = value

    def get_all(self) -> Dict[str, Any]:
        """
        Retrieve all stored values.

        Returns:
            Dictionary of all key-value pairs
        """
        return dict(self._store)

    def delete(self, key: str) -> bool:
        """
        Delete a value by key.

        Args:
            key: The key to delete

        Returns:
            True if key existed and was deleted, False otherwise
        """
        if key in self._store:
            del self._store[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """
        Check if a key exists.

        Args:
            key: The key to check

        Returns:
            True if key exists, False otherwise
        """
        return key in self._store

    def clear(self) -> None:
        """Clear all stored values."""
        self._store.clear()

    def get_keys(self) -> List[str]:
        """
        Get all stored keys.

        Returns:
            List of all keys
        """
        return list(self._store.keys())

    def get_size(self) -> int:
        """
        Get the number of stored items.

        Returns:
            Number of key-value pairs
        """
        return len(self._store)

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update multiple values at once.

        Args:
            data: Dictionary of key-value pairs to store
        """
        self._store.update(data)

    def get_with_prefix(self, prefix: str) -> Dict[str, Any]:
        """
        Get all values for keys with a given prefix.

        Args:
            prefix: The prefix to search for

        Returns:
            Dictionary of matching key-value pairs
        """
        return {k: v for k, v in self._store.items() if k.startswith(prefix)}

    def delete_with_prefix(self, prefix: str) -> int:
        """
        Delete all values for keys with a given prefix.

        Args:
            prefix: The prefix to search for

        Returns:
            Number of keys deleted
        """
        keys_to_delete = [k for k in self._store.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._store[key]
        return len(keys_to_delete)
