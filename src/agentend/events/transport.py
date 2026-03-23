"""
Transport layer for AG-UI events.

Supports SSE and WebSocket transports.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional

from .types import AgentEvent

logger = logging.getLogger(__name__)


class EventTransport(ABC):
    """Abstract base for event transports."""

    @abstractmethod
    async def send(self, event: AgentEvent) -> None:
        """Send an event."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport."""
        pass


class SSETransport(EventTransport):
    """
    Server-Sent Events transport.

    Sends events as SSE messages over HTTP.
    Requires sse-starlette or similar.
    """

    def __init__(self, send_callable: Callable[[str], Awaitable[None]]):
        """
        Initialize SSE transport.

        Args:
            send_callable: Async callable that sends SSE data
        """
        self.send_callable = send_callable

    async def send(self, event: AgentEvent) -> None:
        """Send event via SSE."""
        try:
            event_json = event.to_json()
            message = f"data: {event_json}\n\n"
            await self.send_callable(message)
        except Exception as e:
            logger.error(f"Failed to send SSE event: {e}")

    async def close(self) -> None:
        """Close SSE transport."""
        pass


class WebSocketTransport(EventTransport):
    """
    WebSocket transport for bidirectional communication.

    Sends events as JSON messages over WebSocket.
    """

    def __init__(self, websocket):
        """
        Initialize WebSocket transport.

        Args:
            websocket: FastAPI WebSocket or similar
        """
        self.websocket = websocket

    async def send(self, event: AgentEvent) -> None:
        """Send event via WebSocket."""
        try:
            event_dict = event.to_dict()
            await self.websocket.send_json(event_dict)
        except Exception as e:
            logger.error(f"Failed to send WebSocket event: {e}")

    async def close(self) -> None:
        """Close WebSocket connection."""
        try:
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")


class FileTransport(EventTransport):
    """
    File-based transport for testing/debugging.

    Writes events to a JSON Lines file.
    """

    def __init__(self, filepath: str):
        """
        Initialize file transport.

        Args:
            filepath: Path to write events to
        """
        self.filepath = filepath
        self.file = open(filepath, "a", encoding="utf-8")

    async def send(self, event: AgentEvent) -> None:
        """Write event to file."""
        try:
            event_json = event.to_json()
            self.file.write(event_json + "\n")
            self.file.flush()
        except Exception as e:
            logger.error(f"Failed to write event to file: {e}")

    async def close(self) -> None:
        """Close file."""
        try:
            self.file.close()
        except Exception as e:
            logger.error(f"Error closing file: {e}")


class MultiTransport(EventTransport):
    """
    Multiplex events to multiple transports.

    Useful for sending to both logging and client simultaneously.
    """

    def __init__(self, transports: list[EventTransport]):
        """
        Initialize multi-transport.

        Args:
            transports: List of transports to send to
        """
        self.transports = transports

    async def send(self, event: AgentEvent) -> None:
        """Send event to all transports."""
        for transport in self.transports:
            try:
                await transport.send(event)
            except Exception as e:
                logger.error(f"Transport {transport} failed: {e}")

    async def close(self) -> None:
        """Close all transports."""
        for transport in self.transports:
            try:
                await transport.close()
            except Exception as e:
                logger.error(f"Error closing transport: {e}")


class LoggingTransport(EventTransport):
    """
    Logging-based transport for debugging.

    Logs all events at debug level.
    """

    async def send(self, event: AgentEvent) -> None:
        """Log event."""
        logger.debug(f"Event: {event.type.value} - {event.to_dict()}")

    async def close(self) -> None:
        """No-op for logging transport."""
        pass
