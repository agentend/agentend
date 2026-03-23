"""Tests for working memory (Tier 1)."""
import pytest

from agentend.memory.working import WorkingMemory


class TestWorkingMemory:
    """Test the in-process working memory dict."""

    def test_get_set(self):
        mem = WorkingMemory()
        mem.set("key1", "value1")
        assert mem.get("key1") == "value1"

    def test_get_missing_returns_default(self):
        mem = WorkingMemory()
        assert mem.get("missing") is None
        assert mem.get("missing", "default") == "default"

    def test_delete(self):
        mem = WorkingMemory()
        mem.set("key1", "value1")
        mem.delete("key1")
        assert mem.get("key1") is None

    def test_clear(self):
        mem = WorkingMemory()
        mem.set("a", 1)
        mem.set("b", 2)
        mem.clear()
        assert mem.get("a") is None
        assert mem.get("b") is None

    def test_get_all(self):
        mem = WorkingMemory()
        mem.set("x", 10)
        mem.set("y", 20)
        all_data = mem.get_all()
        assert all_data == {"x": 10, "y": 20}

    def test_isolation_between_instances(self):
        mem1 = WorkingMemory()
        mem2 = WorkingMemory()
        mem1.set("shared", "from_mem1")
        assert mem2.get("shared") is None
