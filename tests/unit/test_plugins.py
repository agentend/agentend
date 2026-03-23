"""Tests for plugin hook system."""
import asyncio
import pytest

from agentend.plugins.hooks import HookRegistry


class TestHookRegistry:
    """Test the plugin hook system."""

    def setup_method(self):
        self.registry = HookRegistry()

    def test_register_and_emit(self):
        results = []

        async def my_hook(context):
            results.append(context["value"])

        self.registry.register("pre_llm", my_hook)
        asyncio.get_event_loop().run_until_complete(
            self.registry.emit("pre_llm", {"value": 42})
        )
        assert results == [42]

    def test_multiple_hooks_same_event(self):
        order = []

        async def first(ctx):
            order.append("first")

        async def second(ctx):
            order.append("second")

        self.registry.register("post_tool", first)
        self.registry.register("post_tool", second)
        asyncio.get_event_loop().run_until_complete(
            self.registry.emit("post_tool", {})
        )
        assert order == ["first", "second"]

    def test_emit_no_hooks_doesnt_crash(self):
        """Emitting an event with no registered hooks should be a no-op."""
        asyncio.get_event_loop().run_until_complete(
            self.registry.emit("nonexistent_event", {"data": 123})
        )

    def test_unregister_hook(self):
        results = []

        async def hook_fn(ctx):
            results.append(1)

        self.registry.register("pre_memory", hook_fn, plugin_name="test_plugin")
        self.registry.unregister("pre_memory", plugin_name="test_plugin")
        asyncio.get_event_loop().run_until_complete(
            self.registry.emit("pre_memory", {})
        )
        assert results == []
