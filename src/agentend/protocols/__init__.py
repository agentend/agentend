"""
Protocols module for external service integrations.

Exports:
- MCPAggregator: Aggregates MCP tool servers
- MCPServerAdapter: Exposes agentend as MCP server
- AgentCardGenerator: Generates Agent.json for A2A
- A2AClient: Delegates tasks to peer agents
"""

from .mcp_aggregator import MCPAggregator
from .mcp_server import MCPServerAdapter
from .a2a_card import AgentCardGenerator
from .a2a_client import A2AClient

__all__ = [
    "MCPAggregator",
    "MCPServerAdapter",
    "AgentCardGenerator",
    "A2AClient",
]
