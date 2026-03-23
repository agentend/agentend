"""Logging platform connectors for centralized log management.

Provides connectors for shipping logs to various platforms including
stdout, files, Datadog, and Elasticsearch.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentend.connectors.base import Connector, ConnectorConfig

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from datadog import initialize, api as datadog_api
    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False

try:
    from elasticsearch import Elasticsearch as ES
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False


class LogConnector(Connector):
    """Abstract base connector for logging platforms.

    Provides common interface for shipping logs to various backends.
    """

    async def log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a message with metadata.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            message: Log message.
            metadata: Additional metadata to include in log.
        """
        pass

    async def query_logs(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query logs by filter criteria.

        Args:
            filter: Filter dictionary with query parameters.

        Returns:
            List of log entries matching the filter.
        """
        return []


class StdoutLogConnector(LogConnector):
    """Log connector that writes to stdout.

    Simple, zero-dependency logging to standard output.
    Useful for development and debugging.

    Configuration:
        ConnectorConfig(
            name="logs",
            connector_type="stdout_log"
        )
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize stdout log connector."""
        super().__init__(config)
        self._py_logger = logging.getLogger(f"agentend.connectors.stdout_log")

    async def connect(self) -> None:
        """Establish stdout logging."""
        self._connected = True
        logger.info("Stdout log connector initialized")

    async def disconnect(self) -> None:
        """Close stdout logging."""
        self._connected = False

    async def health_check(self) -> bool:
        """Stdout logging is always available."""
        return True

    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute logging operation.

        Operations:
            - log: Log a message (requires level, message, metadata in kwargs)
            - query: Query logs (not supported for stdout)
        """
        if operation == "log":
            level = kwargs.get("level", "INFO").upper()
            message = kwargs.get("message", "")
            metadata = kwargs.get("metadata", {})

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": level,
                "message": message,
            }
            if metadata:
                log_entry["metadata"] = metadata

            # Use appropriate logging level
            log_method = getattr(
                self._py_logger, level.lower(), self._py_logger.info
            )
            log_method(json.dumps(log_entry))
            return log_entry
        elif operation == "query":
            logger.warning("Stdout log connector does not support querying")
            return []
        else:
            raise ValueError(f"Unknown logging operation: {operation}")

    async def log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a message to stdout."""
        await self.execute("log", level=level, message=message, metadata=metadata)


class FileLogConnector(LogConnector):
    """Log connector that writes to a file.

    Logs to a local file in JSON format.
    Useful for persistent local logging.

    Configuration:
        ConnectorConfig(
            name="file_logs",
            connector_type="file_log",
            options={"path": "/var/log/agentend.log"}
        )
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize file log connector."""
        super().__init__(config)
        self._log_path: Optional[Path] = None
        self._log_file = None

    async def connect(self) -> None:
        """Open log file for writing."""
        try:
            log_path = self.config.options.get("path", "agentend.log")
            self._log_path = Path(log_path)

            # Ensure parent directory exists
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

            # Open file in append mode
            self._log_file = open(self._log_path, "a", encoding="utf-8")
            self._connected = True
            logger.info(f"File log connector initialized: {self._log_path}")
        except Exception as e:
            logger.error(f"Failed to open log file: {e}")
            raise ConnectionError(f"Cannot open log file: {e}")

    async def disconnect(self) -> None:
        """Close log file."""
        if self._log_file:
            try:
                self._log_file.close()
                self._connected = False
            except Exception as e:
                logger.error(f"Error closing log file: {e}")

    async def health_check(self) -> bool:
        """Check if log file is writable."""
        if not self._log_path:
            return False
        try:
            # Try to write and flush
            if self._log_file and not self._log_file.closed:
                self._log_file.flush()
                return True
        except Exception:
            pass
        return False

    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute logging operation.

        Operations:
            - log: Write message to file
            - query: Query logs from file
        """
        if operation == "log":
            level = kwargs.get("level", "INFO").upper()
            message = kwargs.get("message", "")
            metadata = kwargs.get("metadata", {})

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": level,
                "message": message,
            }
            if metadata:
                log_entry["metadata"] = metadata

            try:
                if self._log_file and not self._log_file.closed:
                    self._log_file.write(json.dumps(log_entry) + "\n")
                    self._log_file.flush()
                return log_entry
            except Exception as e:
                logger.error(f"Error writing to log file: {e}")
                raise
        elif operation == "query":
            # Simple file-based query - load all logs and filter
            return await self._query_file()
        else:
            raise ValueError(f"Unknown logging operation: {operation}")

    async def _query_file(self) -> List[Dict[str, Any]]:
        """Query logs from file."""
        if not self._log_path or not self._log_path.exists():
            return []

        logs = []
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.error(f"Error reading log file: {e}")

        return logs

    async def log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a message to file."""
        await self.execute("log", level=level, message=message, metadata=metadata)

    async def query_logs(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query logs from file with filtering."""
        all_logs = await self._query_file()

        # Simple filter implementation
        filtered = all_logs
        if "level" in filter:
            level = filter["level"].upper()
            filtered = [log for log in filtered if log.get("level") == level]

        return filtered


def _make_datadog_stub() -> type:
    """Create a stub DatadogLogConnector for when datadog is not installed."""
    class DatadogLogConnector(LogConnector):
        """Stub: Datadog logging connector.

        Requires optional 'datadog' dependency.
        Install with: pip install datadog
        """

        async def connect(self) -> None:
            raise ImportError(
                "Datadog logging requires the 'datadog' package. "
                "Install with: pip install datadog"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise ImportError(
                "Datadog logging requires the 'datadog' package. "
                "Install with: pip install datadog"
            )

    return DatadogLogConnector


def _make_elasticsearch_stub() -> type:
    """Create a stub ElasticsearchLogConnector for when elasticsearch is not installed."""
    class ElasticsearchLogConnector(LogConnector):
        """Stub: Elasticsearch logging connector.

        Requires optional 'elasticsearch' dependency.
        Install with: pip install elasticsearch
        """

        async def connect(self) -> None:
            raise ImportError(
                "Elasticsearch logging requires the 'elasticsearch' package. "
                "Install with: pip install elasticsearch"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise ImportError(
                "Elasticsearch logging requires the 'elasticsearch' package. "
                "Install with: pip install elasticsearch"
            )

    return ElasticsearchLogConnector


# Create actual or stub connectors based on availability
if DATADOG_AVAILABLE:
    class DatadogLogConnector(LogConnector):
        """Datadog logging connector.

        Ships logs to Datadog for centralized monitoring and analysis.

        Configuration:
            ConnectorConfig(
                name="datadog",
                connector_type="datadog_log",
                options={
                    "api_key": "${DATADOG_API_KEY}",
                    "site": "datadoghq.com"
                }
            )
        """

        def __init__(self, config: ConnectorConfig):
            super().__init__(config)
            self._client = None

        async def connect(self) -> None:
            api_key = self.config.options.get("api_key")
            if not api_key:
                raise ValueError("Datadog connector requires 'api_key' in options")

            try:
                initialize(
                    api_key=api_key,
                    app_key=self.config.options.get("app_key"),
                )
                self._connected = True
                logger.info("Connected to Datadog")
            except Exception as e:
                logger.error(f"Failed to connect to Datadog: {e}")
                raise ConnectionError(f"Datadog connection failed: {e}")

        async def disconnect(self) -> None:
            self._connected = False

        async def health_check(self) -> bool:
            try:
                # Quick API check
                datadog_api.Comment.get_all()
                return True
            except Exception:
                return False

        async def execute(self, operation: str, **kwargs) -> Any:
            if operation == "log":
                level = kwargs.get("level", "INFO")
                message = kwargs.get("message", "")
                metadata = kwargs.get("metadata", {})

                tags = [f"level:{level.lower()}"]
                if metadata:
                    for key, value in metadata.items():
                        tags.append(f"{key}:{value}")

                datadog_api.Event.create(
                    title=self.config.name,
                    text=message,
                    tags=tags,
                    alert_type="info",
                )
                return {"status": "sent"}
            else:
                raise ValueError(f"Unknown operation: {operation}")

        async def log(
            self,
            level: str,
            message: str,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> None:
            await self.execute("log", level=level, message=message, metadata=metadata)

else:
    DatadogLogConnector = _make_datadog_stub()


if ELASTICSEARCH_AVAILABLE:
    class ElasticsearchLogConnector(LogConnector):
        """Elasticsearch logging connector.

        Indexes logs in Elasticsearch for powerful searching and analysis.

        Configuration:
            ConnectorConfig(
                name="elastic",
                connector_type="elasticsearch_log",
                connection_string="http://localhost:9200",
                options={"index": "agentend-logs"}
            )
        """

        def __init__(self, config: ConnectorConfig):
            super().__init__(config)
            self._client: Optional[ES] = None

        async def connect(self) -> None:
            if not self.config.connection_string:
                raise ValueError(
                    "Elasticsearch connector requires connection_string"
                )

            try:
                self._client = ES([self.config.connection_string])
                # Test connection
                self._client.info()
                self._connected = True
                logger.info("Connected to Elasticsearch")
            except Exception as e:
                logger.error(f"Failed to connect to Elasticsearch: {e}")
                raise ConnectionError(f"Elasticsearch connection failed: {e}")

        async def disconnect(self) -> None:
            if self._client:
                self._client.close()
            self._connected = False

        async def health_check(self) -> bool:
            if not self._client:
                return False
            try:
                self._client.info()
                return True
            except Exception:
                return False

        async def execute(self, operation: str, **kwargs) -> Any:
            if operation == "log":
                level = kwargs.get("level", "INFO")
                message = kwargs.get("message", "")
                metadata = kwargs.get("metadata", {})

                index = self.config.options.get("index", "agentend-logs")
                doc = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": level,
                    "message": message,
                }
                if metadata:
                    doc["metadata"] = metadata

                result = self._client.index(index=index, body=doc)
                return result
            else:
                raise ValueError(f"Unknown operation: {operation}")

        async def log(
            self,
            level: str,
            message: str,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> None:
            await self.execute("log", level=level, message=message, metadata=metadata)

else:
    ElasticsearchLogConnector = _make_elasticsearch_stub()
