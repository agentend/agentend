"""Abstract base connector system for infrastructure access.

Provides the foundation for connecting to databases, caches, message queues,
logging platforms, and other backend services.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConnectorConfig:
    """Configuration for a connector instance.

    Attributes:
        name: Unique identifier for this connector instance.
        connector_type: Type of connector (e.g., 'sql', 'redis_cache', 'stdout_log').
        connection_string: Optional connection string for the backend service.
        options: Additional configuration options specific to the connector type.
        enabled: Whether this connector should be active.
    """
    name: str
    connector_type: str
    connection_string: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class Connector(ABC):
    """Abstract base class for all connectors.

    Connectors provide unified access to various infrastructure services.
    Subclasses must implement connect/disconnect and execute methods.
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize connector with configuration.

        Args:
            config: ConnectorConfig instance with connection parameters.
        """
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connector is currently connected.

        Returns:
            True if connected to the backend service.
        """
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the backend service.

        Should set self._connected = True on successful connection.
        Raises:
            ConnectionError: If connection fails.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the backend service.

        Should set self._connected = False after disconnecting.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend service is healthy and accessible.

        Returns:
            True if service is healthy, False otherwise.
        """
        pass

    @abstractmethod
    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute an operation on the backend service.

        The operation parameter and kwargs are connector-specific.
        For SQL connectors, operation is the SQL query.
        For caches, operation might be 'get', 'set', 'delete'.

        Args:
            operation: The operation to perform.
            **kwargs: Operation-specific parameters.

        Returns:
            Result of the operation (type depends on operation).
        """
        pass

    async def __aenter__(self) -> Connector:
        """Async context manager entry.

        Automatically connects when entering the context.
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit.

        Automatically disconnects when exiting the context.
        """
        await self.disconnect()

    def metadata(self) -> Dict[str, Any]:
        """Get metadata about this connector.

        Returns:
            Dictionary with connector information:
                - name: Connector name
                - type: Connector type
                - connected: Current connection status
                - options: Configuration options
        """
        return {
            "name": self.config.name,
            "type": self.config.connector_type,
            "connected": self.is_connected,
            "options": self.config.options,
        }


class ConnectorRegistry:
    """Registry for managing connector types and instances.

    Handles registration of connector classes, creation of instances,
    and lifecycle management of active connectors.
    """

    def __init__(self):
        """Initialize the connector registry."""
        self._connector_types: Dict[str, type] = {}
        self._active_connectors: Dict[str, Connector] = {}

    def register(self, type_name: str, connector_cls: type) -> type:
        """Register a connector class by type name.

        Can be used as a decorator or called directly.

        Args:
            type_name: The connector type identifier (e.g., 'sql', 'redis_cache').
            connector_cls: The connector class to register.

        Returns:
            The connector class (for decorator use).

        Example:
            @registry.register('sql')
            class SQLConnector(Connector):
                pass
        """
        if type_name in self._connector_types:
            logger.warning(
                f"Overwriting existing connector registration for type '{type_name}'"
            )
        self._connector_types[type_name] = connector_cls
        logger.debug(f"Registered connector type: {type_name}")
        return connector_cls

    def create(self, config: ConnectorConfig) -> Connector:
        """Create a connector instance from a configuration.

        Args:
            config: ConnectorConfig instance.

        Returns:
            Instantiated connector.

        Raises:
            ValueError: If connector type is not registered.
        """
        if config.connector_type not in self._connector_types:
            available = ", ".join(self._connector_types.keys())
            raise ValueError(
                f"Unknown connector type '{config.connector_type}'. "
                f"Available types: {available}"
            )

        connector_cls = self._connector_types[config.connector_type]
        connector = connector_cls(config)

        # Store as active connector if named
        if config.name:
            self._active_connectors[config.name] = connector
            logger.debug(f"Created connector: {config.name} ({config.connector_type})")

        return connector

    def list_available(self) -> list[str]:
        """Get list of registered connector types.

        Returns:
            List of available connector type identifiers.
        """
        return sorted(self._connector_types.keys())

    def get(self, name: str) -> Optional[Connector]:
        """Get an active connector by name.

        Args:
            name: The connector name.

        Returns:
            The connector instance, or None if not found.
        """
        return self._active_connectors.get(name)

    def get_all(self) -> Dict[str, Connector]:
        """Get all active connectors.

        Returns:
            Dictionary mapping connector names to instances.
        """
        return dict(self._active_connectors)

    async def close_all(self) -> None:
        """Close all active connectors.

        Used during shutdown to cleanly disconnect all services.
        """
        for name, connector in self._active_connectors.items():
            try:
                if connector.is_connected:
                    await connector.disconnect()
                    logger.debug(f"Disconnected: {name}")
            except Exception as e:
                logger.error(f"Error disconnecting {name}: {e}")

        self._active_connectors.clear()
