"""
Capability registry for managing and discovering framework capabilities.
"""

from typing import Any, Callable, Dict, List, Optional, Protocol
from functools import wraps
import inspect


class Capability(Protocol):
    """Protocol defining a capability that can be executed by the kernel."""

    name: str
    """Unique identifier for this capability."""

    description: str
    """Human-readable description of what this capability does."""

    async def execute(
        self, context: "RequestContext", *args: Any, **kwargs: Any
    ) -> Any:
        """
        Execute the capability.

        Args:
            context: RequestContext with messages, metadata, and session info.
            *args: Positional arguments passed to the capability.
            **kwargs: Keyword arguments passed to the capability.

        Returns:
            Result of capability execution.
        """
        ...


def tool(name: str, description: str = "") -> Callable:
    """
    Decorator to register a function as a tool/capability.

    Args:
        name: Unique identifier for the tool.
        description: Human-readable description.

    Returns:
        Decorator function.

    Example:
        @tool("translate", "Translate text to target language")
        async def translate_tool(context, text: str, target_lang: str):
            return translated_text
    """

    def decorator(func: Callable) -> Callable:
        func._is_tool = True
        func._tool_name = name
        func._tool_description = description or func.__doc__ or ""
        return func

    return decorator


class CapabilityRegistry:
    """
    Registry for managing capabilities and tools.

    Supports registration, lookup, and listing of capabilities
    that can be executed by the kernel.
    """

    def __init__(self) -> None:
        """Initialize the capability registry."""
        self._capabilities: Dict[str, Capability] = {}
        self._tool_functions: Dict[str, Callable] = {}

    def register(self, name: str, capability: Capability) -> None:
        """
        Register a capability in the registry.

        Args:
            name: Unique identifier for the capability.
            capability: The capability object or class implementing Capability protocol.

        Raises:
            ValueError: If a capability with this name already exists.
        """
        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' already registered")

        self._capabilities[name] = capability

    def register_tool(self, func: Callable) -> Callable:
        """
        Register a function as a tool capability.

        Args:
            func: Function decorated with @tool.

        Returns:
            The original function.

        Raises:
            ValueError: If function is not decorated with @tool or name exists.
        """
        if not hasattr(func, "_is_tool"):
            raise ValueError(f"Function {func.__name__} not decorated with @tool")

        tool_name = func._tool_name
        if tool_name in self._tool_functions:
            raise ValueError(f"Tool '{tool_name}' already registered")

        self._tool_functions[tool_name] = func
        return func

    def lookup(self, name: str) -> Optional[Capability]:
        """
        Look up a capability by name.

        Args:
            name: Unique identifier of the capability.

        Returns:
            The capability if found, None otherwise.
        """
        return self._capabilities.get(name)

    def lookup_tool(self, name: str) -> Optional[Callable]:
        """
        Look up a tool function by name.

        Args:
            name: Unique identifier of the tool.

        Returns:
            The tool function if found, None otherwise.
        """
        return self._tool_functions.get(name)

    def list_capabilities(self) -> List[Dict[str, str]]:
        """
        List all registered capabilities.

        Returns:
            List of dicts with 'name' and 'description' keys.
        """
        result = []
        for name, cap in self._capabilities.items():
            desc = getattr(cap, "description", "")
            result.append({"name": name, "description": desc})

        for name, func in self._tool_functions.items():
            desc = getattr(func, "_tool_description", "")
            result.append({"name": name, "description": desc})

        return result

    def list_tool_functions(self) -> Dict[str, Callable]:
        """
        Get all registered tool functions.

        Returns:
            Dictionary mapping tool names to functions.
        """
        return self._tool_functions.copy()

    def get_tool_signature(self, tool_name: str) -> Optional[inspect.Signature]:
        """
        Get the signature of a registered tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            The function signature if found, None otherwise.
        """
        func = self._tool_functions.get(tool_name)
        if func:
            return inspect.signature(func)
        return None
