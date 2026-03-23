"""SQL database connector for relational databases.

Provides unified access to SQL databases including PostgreSQL, MySQL, and SQLite.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agentend.connectors.base import Connector, ConnectorConfig

logger = logging.getLogger(__name__)

# Optional SQLAlchemy async support
try:
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        create_async_engine,
    )
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    AsyncEngine = None


class SQLConnector(Connector):
    """Connector for SQL databases using SQLAlchemy async.

    Supports PostgreSQL, MySQL, and SQLite through SQLAlchemy.
    Requires optional 'sqlalchemy' dependency.

    Example configuration:
        ConnectorConfig(
            name="main_db",
            connector_type="postgresql",
            connection_string="postgresql+asyncpg://user:pass@localhost/dbname"
        )
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize SQL connector.

        Args:
            config: ConnectorConfig with connection_string containing DB URL.

        Raises:
            ImportError: If SQLAlchemy is not installed.
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy is required for SQL connector. "
                "Install with: pip install sqlalchemy[asyncio]"
            )
        super().__init__(config)
        self._engine: Optional[AsyncEngine] = None

    async def connect(self) -> None:
        """Establish database connection.

        Creates async SQLAlchemy engine from connection string.

        Raises:
            ValueError: If no connection_string provided.
            ConnectionError: If connection fails.
        """
        if not self.config.connection_string:
            raise ValueError(
                f"SQL connector '{self.config.name}' requires connection_string"
            )

        try:
            # Extract SQLAlchemy options from config
            engine_kwargs = self.config.options.copy()
            if "pool_size" not in engine_kwargs:
                engine_kwargs["pool_size"] = 10
            if "max_overflow" not in engine_kwargs:
                engine_kwargs["max_overflow"] = 20
            if "echo" not in engine_kwargs:
                engine_kwargs["echo"] = False

            self._engine = create_async_engine(
                self.config.connection_string, **engine_kwargs
            )

            # Test connection
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

            self._connected = True
            logger.info(f"Connected to database: {self.config.name}")
        except Exception as e:
            logger.error(f"Failed to connect to database {self.config.name}: {e}")
            raise ConnectionError(f"Database connection failed: {e}")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._engine:
            try:
                await self._engine.dispose()
                self._connected = False
                logger.info(f"Disconnected from database: {self.config.name}")
            except Exception as e:
                logger.error(f"Error disconnecting from database: {e}")

    async def health_check(self) -> bool:
        """Check database connectivity and health.

        Returns:
            True if database is accessible, False otherwise.
        """
        if not self._connected or not self._engine:
            return False

        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False

    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute a SQL operation.

        The operation parameter is the SQL query string.
        params can be provided in kwargs for parameterized queries.

        Args:
            operation: SQL query string.
            **kwargs: Should contain 'params' dict for parameterized queries.

        Returns:
            Query result (depends on query type).

        Raises:
            RuntimeError: If not connected.
            Exception: Database operation errors.
        """
        if not self._connected or not self._engine:
            raise RuntimeError("Database connector is not connected")

        params = kwargs.get("params", {})

        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text(operation), params)
                if operation.strip().upper().startswith("SELECT"):
                    return result.fetchall()
                else:
                    return result.rowcount
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            raise

    async def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Convenience method for SELECT queries.

        Args:
            sql: SELECT query string.
            params: Parameter dictionary for parameterized query.

        Returns:
            List of result rows as dictionaries.
        """
        if not self._connected or not self._engine:
            raise RuntimeError("Database connector is not connected")

        params = params or {}

        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                # Convert Row objects to dicts
                return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise

    async def execute_raw(
        self, sql: str, params: Optional[Dict[str, Any]] = None
    ) -> int:
        """Execute INSERT/UPDATE/DELETE operations.

        Args:
            sql: DML query string (INSERT, UPDATE, DELETE).
            params: Parameter dictionary for parameterized query.

        Returns:
            Number of rows affected.
        """
        if not self._connected or not self._engine:
            raise RuntimeError("Database connector is not connected")

        params = params or {}

        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text(sql), params)
                return result.rowcount
        except Exception as e:
            logger.error(f"Raw execution error: {e}")
            raise

    async def get_tables(self) -> List[str]:
        """Get list of tables in the database.

        Returns:
            List of table names.
        """
        if not self._connected or not self._engine:
            raise RuntimeError("Database connector is not connected")

        try:
            async with self._engine.begin() as conn:
                inspector = inspect(self._engine)
                tables = inspector.get_table_names()
                return sorted(tables)
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            raise

    async def get_schema(self, table: str) -> Dict[str, Any]:
        """Get schema information for a table.

        Args:
            table: Table name.

        Returns:
            Dictionary with column information:
                {
                    "columns": [
                        {"name": "id", "type": "INTEGER", "nullable": False},
                        ...
                    ]
                }
        """
        if not self._connected or not self._engine:
            raise RuntimeError("Database connector is not connected")

        try:
            inspector = inspect(self._engine)
            columns = inspector.get_columns(table)
            return {
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col["nullable"],
                    }
                    for col in columns
                ]
            }
        except Exception as e:
            logger.error(f"Error getting schema for {table}: {e}")
            raise
