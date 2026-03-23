"""
AgentCardGenerator: Generates Agent.json for Agent-to-Agent (A2A) protocol.

Automatically generates /.well-known/agent.json metadata about the agent's
capabilities, allowing other agents to discover and invoke it.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentCardGenerator:
    """
    Generates Agent.json metadata for Agent-to-Agent discovery.

    Follows the emerging A2A protocol for agent discoverability and invocation.
    """

    def __init__(
        self,
        agent_name: str,
        agent_description: str = "",
        version: str = "1.0.0",
    ):
        """
        Initialize card generator.

        Args:
            agent_name: Name of the agent
            agent_description: Description of agent capabilities
            version: API version
        """
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.version = version
        self.tools: List[Dict[str, Any]] = []
        self.capabilities: List[str] = []
        self.models: List[str] = []

    def add_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a tool capability.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON schema for inputs
            output_schema: JSON schema for outputs (optional)
        """
        tool = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }
        if output_schema:
            tool["outputSchema"] = output_schema

        self.tools.append(tool)
        logger.debug(f"Added tool: {name}")

    def add_capability(self, capability: str) -> None:
        """
        Add a capability string.

        Args:
            capability: Capability identifier (e.g., "memory_management")
        """
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def add_model(self, model_name: str) -> None:
        """
        Add a supported model.

        Args:
            model_name: Model identifier
        """
        if model_name not in self.models:
            self.models.append(model_name)

    def generate(self) -> Dict[str, Any]:
        """
        Generate the agent.json card.

        Returns:
            Agent metadata dictionary
        """
        card = {
            "apiVersion": self.version,
            "name": self.agent_name,
            "description": self.agent_description,
            "type": "agent",
            "capabilities": self.capabilities,
        }

        if self.tools:
            card["tools"] = self.tools

        if self.models:
            card["models"] = self.models

        return card

    def generate_json(self, pretty: bool = True) -> str:
        """
        Generate JSON string of agent card.

        Args:
            pretty: Whether to pretty-print JSON

        Returns:
            JSON string
        """
        card = self.generate()
        if pretty:
            return json.dumps(card, indent=2)
        else:
            return json.dumps(card)

    def to_fastapi_response(self):
        """
        Generate a FastAPI JSONResponse for /.well-known/agent.json.

        Returns:
            FastAPI JSONResponse object
        """
        try:
            from fastapi.responses import JSONResponse
            return JSONResponse(content=self.generate())
        except ImportError:
            logger.warning("FastAPI not installed, returning dict instead")
            return self.generate()

    @staticmethod
    def from_mcp_server(mcp_server) -> "AgentCardGenerator":
        """
        Create a card generator from an MCP server.

        Args:
            mcp_server: MCPServerAdapter instance

        Returns:
            AgentCardGenerator with tools from MCP server
        """
        generator = AgentCardGenerator(
            agent_name=mcp_server.agent_name,
            agent_description=f"Agent: {mcp_server.agent_name}",
        )

        for tool_def in mcp_server.list_tools():
            generator.add_tool(
                name=tool_def.get("name", ""),
                description=tool_def.get("description", ""),
                input_schema=tool_def.get("inputSchema", {}),
            )

        return generator

    @staticmethod
    def from_registry(registry: Dict[str, Any]) -> "AgentCardGenerator":
        """
        Create a card generator from an agent registry/manifest.

        Args:
            registry: Agent registry with tools and capabilities

        Returns:
            AgentCardGenerator from registry
        """
        generator = AgentCardGenerator(
            agent_name=registry.get("name", "agent"),
            agent_description=registry.get("description", ""),
            version=registry.get("version", "1.0.0"),
        )

        # Add tools from registry
        for tool in registry.get("tools", []):
            generator.add_tool(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("input_schema", {}),
                output_schema=tool.get("output_schema"),
            )

        # Add capabilities
        for capability in registry.get("capabilities", []):
            generator.add_capability(capability)

        # Add models
        for model in registry.get("models", []):
            generator.add_model(model)

        return generator

    def get_tool_names(self) -> List[str]:
        """Get names of all tools."""
        return [tool["name"] for tool in self.tools]

    def get_capabilities_summary(self) -> Dict[str, Any]:
        """Get summary of capabilities."""
        return {
            "total_tools": len(self.tools),
            "tool_names": self.get_tool_names(),
            "capabilities": self.capabilities,
            "supported_models": self.models,
        }
