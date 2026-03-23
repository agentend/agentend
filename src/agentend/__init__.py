"""
Agentend Framework - A modular agentic framework for building AI applications.

Public API exports and version information.
"""

__version__ = "0.1.0-alpha"

from agentend.kernel.kernel import Agentend
from agentend.kernel.registry import Capability
from agentend.kernel.registry import tool
from agentend.fleet.worker import Worker, WorkerConfig
from agentend.fleet.benchmarks import BenchmarkRegistry
from agentend.connectors.base import Connector, ConnectorConfig, ConnectorRegistry
from agentend.builder.builder import CapabilityBuilder

__all__ = [
    "Agentend",
    "Capability",
    "tool",
    "Worker",
    "WorkerConfig",
    "BenchmarkRegistry",
    "Connector",
    "ConnectorConfig",
    "ConnectorRegistry",
    "CapabilityBuilder",
]
