"""Infrastructure connectors for Agentend.

Provides unified access to databases, logging platforms, caches,
message queues, and other backend infrastructure.

Example usage:
    from agentend.connectors import registry, ConnectorConfig

    # Create a database connector
    config = ConnectorConfig(
        name="main_db",
        connector_type="postgresql",
        connection_string="postgresql://user:pass@localhost/dbname"
    )
    connector = registry.create(config)

    # Use it with async context manager
    async with connector:
        result = await connector.execute("SELECT * FROM users")
        print(result)
"""

from agentend.connectors.base import Connector, ConnectorConfig, ConnectorRegistry
from agentend.connectors.registry import registry, get_connector

__all__ = [
    "Connector",
    "ConnectorConfig",
    "ConnectorRegistry",
    "registry",
    "get_connector",
]
