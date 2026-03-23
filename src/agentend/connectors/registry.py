"""Module-level connector registry singleton.

Provides global access to registered connectors and manages their lifecycle.
"""
from __future__ import annotations

import logging

from agentend.connectors.base import Connector, ConnectorRegistry

logger = logging.getLogger(__name__)

# Create global registry instance
registry = ConnectorRegistry()


def _register_builtin_connectors() -> None:
    """Register all built-in connectors.

    Called on module import to populate the registry with default connectors.
    """
    # Database connectors
    try:
        from agentend.connectors.database import SQLConnector

        registry.register("sql", SQLConnector)
        registry.register("postgresql", SQLConnector)
        registry.register("postgres", SQLConnector)
        registry.register("mysql", SQLConnector)
        registry.register("sqlite", SQLConnector)
    except Exception as e:
        logger.warning(f"Failed to register SQL connector: {e}")

    # Logging connectors
    try:
        from agentend.connectors.logging import (
            StdoutLogConnector,
            FileLogConnector,
            DatadogLogConnector,
            ElasticsearchLogConnector,
        )

        registry.register("stdout_log", StdoutLogConnector)
        registry.register("file_log", FileLogConnector)
        registry.register("datadog_log", DatadogLogConnector)
        registry.register("elasticsearch_log", ElasticsearchLogConnector)
    except Exception as e:
        logger.warning(f"Failed to register logging connectors: {e}")

    # Cache connectors
    try:
        from agentend.connectors.cache import (
            InMemoryCacheConnector,
            RedisCacheConnector,
        )

        registry.register("memory_cache", InMemoryCacheConnector)
        registry.register("in_memory_cache", InMemoryCacheConnector)
        registry.register("redis_cache", RedisCacheConnector)
    except Exception as e:
        logger.warning(f"Failed to register cache connectors: {e}")

    # Queue connectors
    try:
        from agentend.connectors.queue import (
            InMemoryQueueConnector,
            RedisQueueConnector,
            RabbitMQConnector,
            KafkaConnector,
        )

        registry.register("memory_queue", InMemoryQueueConnector)
        registry.register("in_memory_queue", InMemoryQueueConnector)
        registry.register("redis_queue", RedisQueueConnector)
        registry.register("rabbitmq", RabbitMQConnector)
        registry.register("kafka", KafkaConnector)
    except Exception as e:
        logger.warning(f"Failed to register queue connectors: {e}")


def get_connector(name: str) -> Connector | None:
    """Get an active connector by name.

    Args:
        name: Connector name.

    Returns:
        The connector instance, or None if not found.
    """
    return registry.get(name)


# Auto-register built-in connectors on module import
_register_builtin_connectors()
