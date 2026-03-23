"""Built-in system capabilities for backend introspection.

These capabilities return data via STATE_SNAPSHOT events through POST /intent,
allowing the frontend console to introspect the backend without new REST endpoints.
"""

from agentend.capabilities.fleet_status import FleetStatusCapability
from agentend.capabilities.system_health import SystemHealthCapability
from agentend.capabilities.memory_inspect import MemoryInspectCapability
from agentend.capabilities.metrics_usage import MetricsUsageCapability
from agentend.capabilities.sessions_list import SessionsListCapability
from agentend.capabilities.workflow_status import WorkflowStatusCapability

SYSTEM_CAPABILITIES = {
    "fleet.status": FleetStatusCapability(),
    "system.health": SystemHealthCapability(),
    "memory.inspect": MemoryInspectCapability(),
    "metrics.usage": MetricsUsageCapability(),
    "sessions.list": SessionsListCapability(),
    "workflow.status": WorkflowStatusCapability(),
}

__all__ = [
    "FleetStatusCapability",
    "SystemHealthCapability",
    "MemoryInspectCapability",
    "MetricsUsageCapability",
    "SessionsListCapability",
    "WorkflowStatusCapability",
    "SYSTEM_CAPABILITIES",
]
