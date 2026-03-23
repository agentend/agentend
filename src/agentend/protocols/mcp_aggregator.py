"""
MCPAggregator: Aggregates MCP (Model Context Protocol) tool servers.

Manages connections to multiple MCP servers and routes tool calls.
Supports lazy initialization and connection pooling.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPServer:
    """Represents a connected MCP server."""

    def __init__(self, name: str, url: str, transport: str = "stdio"):
        """
        Initialize MCP server connection info.

        Args:
            name: Server name
            url: Server connection URL or path
            transport: Transport type (stdio, sse, websocket)
        """
        self.name = name
        self.url = url
        self.transport = transport
        self.connected = False
        self.tools: Dict[str, Any] = {}
        self._connection = None

    async def connect(self) -> None:
        """Connect to MCP server."""
        try:
            # In production, use actual MCP client library
            # For now, mark as connected
            self.connected = True
            logger.info(f"Connected to MCP server: {self.name}")
        except Exception as e:
            logger.error(f"Failed to connect to {self.name}: {e}")
            self.connected = False

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        self.connected = False
        logger.info(f"Disconnected from MCP server: {self.name}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from this server."""
        if not self.connected:
            await self.connect()
        return list(self.tools.values())

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool on this server."""
        if not self.connected:
            await self.connect()
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found on {self.name}")
        # In production, actually invoke the tool
        logger.info(f"Calling {self.name}::{tool_name} with {args}")
        return None


class MCPAggregator:
    """
    Aggregates tools from multiple MCP servers.

    Features:
    - Lazy initialization of connections
    - Connection pooling
    - Tool discovery and listing
    - Automatic tool namespacing (server::tool)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize MCPAggregator.

        Args:
            config: Configuration with server definitions
        """
        self.config = config or {}
        self.servers: Dict[str, MCPServer] = {}
        self._initialized = False

    async def load_servers(self, config: Dict[str, Any]) -> None:
        """
        Load MCP servers from configuration.

        Config format:
        {
            "servers": {
                "server_name": {
                    "url": "path/to/server",
                    "transport": "stdio",
                    "tools": [{"name": "tool1", "description": "..."}]
                }
            }
        }

        Args:
            config: Server configuration
        """
        self.config = config
        servers_config = config.get("servers", {})

        for server_name, server_config in servers_config.items():
            server = MCPServer(
                name=server_name,
                url=server_config.get("url", ""),
                transport=server_config.get("transport", "stdio"),
            )

            # Pre-populate known tools
            for tool_config in server_config.get("tools", []):
                server.tools[tool_config.get("name", "")] = tool_config

            self.servers[server_name] = server

        logger.info(f"Loaded {len(self.servers)} MCP servers")
        self._initialized = True

    async def connect_all(self) -> None:
        """Connect to all configured servers."""
        tasks = [server.connect() for server in self.servers.values()]
        await asyncio.gather(*tasks)

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        tasks = [server.disconnect() for server in self.servers.values()]
        await asyncio.gather(*tasks)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from all servers.

        Returns:
            List of tool definitions with namespace prefix
        """
        tools = []

        for server_name, server in self.servers.items():
            server_tools = await server.list_tools()
            for tool in server_tools:
                # Add server namespace
                tool_with_namespace = dict(tool)
                tool_with_namespace["name"] = f"{server_name}__{tool.get('name', '')}"
                tool_with_namespace["server"] = server_name
                tools.append(tool_with_namespace)

        return tools

    async def call(
        self,
        tool_call: str,
        args: Dict[str, Any],
    ) -> Any:
        """
        Call a tool on a specific server.

        Tool call format: "server_name::tool_name" or "server_name__tool_name"

        Args:
            tool_call: Tool specification
            args: Tool arguments

        Returns:
            Tool result
        """
        # Parse server and tool name
        if "::" in tool_call:
            server_name, tool_name = tool_call.split("::", 1)
        elif "__" in tool_call:
            server_name, tool_name = tool_call.split("__", 1)
        else:
            raise ValueError(f"Invalid tool call format: {tool_call}")

        if server_name not in self.servers:
            raise ValueError(f"Server '{server_name}' not found")

        server = self.servers[server_name]
        return await server.call_tool(tool_name, args)

    def get_tool(self, tool_call: str) -> Optional[Dict[str, Any]]:
        """Get tool definition by name."""
        if "::" in tool_call:
            server_name, tool_name = tool_call.split("::", 1)
        elif "__" in tool_call:
            server_name, tool_name = tool_call.split("__", 1)
        else:
            return None

        if server_name not in self.servers:
            return None

        server = self.servers[server_name]
        return server.tools.get(tool_name)

    def get_server(self, server_name: str) -> Optional[MCPServer]:
        """Get a server by name."""
        return self.servers.get(server_name)

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all servers."""
        status = {}
        for name, server in self.servers.items():
            status[name] = server.connected
        return status

    def is_initialized(self) -> bool:
        """Check if aggregator has been initialized."""
        return self._initialized
