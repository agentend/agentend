"""Plugin hook registry and execution system."""

from typing import Dict, List, Callable, Any
import logging
import asyncio


logger = logging.getLogger(__name__)


class HookRegistry:
    """
    Registry for plugin hooks.

    Supports registering callbacks for hook points:
    pre_llm, post_llm, pre_tool, post_tool, pre_memory, post_memory
    """

    # Valid hook points
    VALID_HOOKS = {
        "pre_llm": "Before LLM execution",
        "post_llm": "After LLM execution",
        "pre_tool": "Before tool call",
        "post_tool": "After tool call",
        "pre_memory": "Before memory access",
        "post_memory": "After memory access",
        "pre_request": "Before request handling",
        "post_request": "After request handling",
    }

    def __init__(self):
        """Initialize hook registry."""
        self.hooks: Dict[str, List[tuple]] = {
            hook: [] for hook in self.VALID_HOOKS.keys()
        }

    def register(
        self,
        hook_name: str,
        callback: Callable,
        plugin_name: str = "unknown",
        priority: int = 0,
    ) -> None:
        """
        Register a callback for a hook.

        Args:
            hook_name: Name of hook (e.g., "pre_llm").
            callback: Callable to execute.
            plugin_name: Name of plugin registering hook.
            priority: Priority (higher = executed first).

        Raises:
            ValueError: If invalid hook name.
        """
        if hook_name not in self.VALID_HOOKS:
            raise ValueError(f"Invalid hook: {hook_name}")

        self.hooks[hook_name].append((callback, plugin_name, priority))

        # Sort by priority
        self.hooks[hook_name].sort(key=lambda x: x[2], reverse=True)

        logger.debug(f"Registered {plugin_name} for {hook_name}")

    def unregister(
        self,
        hook_name: str,
        plugin_name: str,
    ) -> None:
        """
        Unregister callbacks from a plugin.

        Args:
            hook_name: Name of hook.
            plugin_name: Name of plugin.
        """
        if hook_name not in self.VALID_HOOKS:
            return

        self.hooks[hook_name] = [
            (cb, pn, pr) for cb, pn, pr in self.hooks[hook_name]
            if pn != plugin_name
        ]

    async def emit(
        self,
        hook_name: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Emit a hook and execute all registered callbacks.

        Args:
            hook_name: Name of hook to emit.
            context: Context dictionary to pass to callbacks.

        Returns:
            Modified context after hook execution.
        """
        if hook_name not in self.VALID_HOOKS:
            logger.warning(f"Unknown hook: {hook_name}")
            return context

        callbacks = self.hooks.get(hook_name, [])

        if not callbacks:
            return context

        logger.debug(f"Emitting hook: {hook_name} ({len(callbacks)} callbacks)")

        for callback, plugin_name, priority in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    result = await callback(context)
                else:
                    result = callback(context)

                # Allow callbacks to modify context
                if isinstance(result, dict):
                    context.update(result)

            except Exception as e:
                logger.error(
                    f"Error in hook {hook_name} ({plugin_name}): {e}",
                    exc_info=True,
                )
                # Continue to next callback on error
                continue

        return context

    def get_hooks(self, hook_name: str) -> List[tuple]:
        """
        Get all callbacks for a hook.

        Args:
            hook_name: Name of hook.

        Returns:
            List of (callback, plugin_name, priority) tuples.
        """
        if hook_name not in self.VALID_HOOKS:
            return []

        return self.hooks.get(hook_name, [])

    def list_hooks(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all registered hooks.

        Returns:
            Dictionary of hooks with registered callbacks.
        """
        result = {}

        for hook_name, callbacks in self.hooks.items():
            result[hook_name] = [
                {
                    "plugin": plugin_name,
                    "priority": priority,
                    "callable": callback.__name__,
                }
                for callback, plugin_name, priority in callbacks
            ]

        return result
