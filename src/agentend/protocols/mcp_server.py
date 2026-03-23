"""
MCPServerAdapter: Exposes agentend agent capabilities as MCP tools.

Allows other agents/applications to call agentend agent functions
via the Model Context Protocol.
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class ToolDefinition:
    """Definition of an exposed tool."""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        input_schema: Dict[str, Any],
    ):
        """
        Initialize tool definition.

        Args:
            name: Tool name
            description: Human-readable description
            handler: Async function to handle tool calls
            input_schema: JSON schema for input parameters
        """
        self.name = name
        self.description = description
        self.handler = handler
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPServerAdapter:
    """
    Exposes agentend capabilities as MCP tools.

    Allows peer agents to call this agent's capabilities
    via the Model Context Protocol.
    """

    def __init__(self, agent_name: str = "agentend"):
        """
        Initialize MCP server adapter.

        Args:
            agent_name: Name of the agent
        """
        self.agent_name = agent_name
        self.tools: Dict[str, ToolDefinition] = {}
        self._registered_handlers: Dict[str, Callable] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        input_schema: Dict[str, Any],
    ) -> None:
        """
        Register a tool to be exposed via MCP.

        Args:
            name: Tool name
            description: Tool description
            handler: Async handler function
            input_schema: JSON schema for inputs
        """
        tool = ToolDefinition(
            name=name,
            description=description,
            handler=handler,
            input_schema=input_schema,
        )
        self.tools[name] = tool
        self._registered_handlers[name] = handler
        logger.info(f"Registered MCP tool: {name}")

    async def auto_register(self, agent) -> None:
        """
        Auto-register common agent capabilities as MCP tools.

        Args:
            agent: Agent instance with standard methods
        """
        # Register retrieve_context tool
        if hasattr(agent, "retrieve_context"):
            self.register_tool(
                name="retrieve_context",
                description="Retrieve relevant context from memory",
                handler=agent.retrieve_context,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Context query"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": ["query"],
                },
            )

        # Register store_memory tool
        if hasattr(agent, "store_memory"):
            self.register_tool(
                name="store_memory",
                description="Store a memory or fact",
                handler=agent.store_memory,
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "importance": {"type": "number", "description": "Importance 0-1"},
                    },
                    "required": ["content"],
                },
            )

        logger.info(f"Auto-registered {len(self.tools)} MCP tools")

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Handle a tool call from another agent.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        handler = self._registered_handlers[tool_name]

        try:
            result = await handler(**arguments)
            return result
        except Exception as e:
            logger.error(f"Tool call failed: {tool_name}: {e}")
            raise

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all exposed tools in MCP format.

        Returns:
            List of tool definitions
        """
        return [tool.to_dict() for tool in self.tools.values()]

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self.tools.get(tool_name)

    def get_agent_json(self) -> Dict[str, Any]:
        """
        Get agent metadata for /.well-known/agent.json.

        Returns:
            Agent JSON object
        """
        return {
            "name": self.agent_name,
            "description": f"AgentEnd-based agent: {self.agent_name}",
            "tools": self.list_tools(),
        }

    async def handle_mcp_request(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle an MCP request (for reference).

        Args:
            request: MCP request object

        Returns:
            MCP response object
        """
        method = request.get("method", "")

        if method == "tools/list":
            return {"tools": self.list_tools()}

        elif method == "tools/call":
            tool_name = request.get("params", {}).get("name", "")
            arguments = request.get("params", {}).get("arguments", {})
            try:
                result = await self.handle_tool_call(tool_name, arguments)
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}

        else:
            return {"error": f"Unknown method: {method}"}

    def clear_tools(self) -> None:
        """Clear all registered tools."""
        self.tools.clear()
        self._registered_handlers.clear()
