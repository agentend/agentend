"""
Main Agentend kernel for intent processing and capability dispatch.
"""

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional
import logging
import asyncio
from enum import Enum

from agentend.kernel.router import IntentRouter, RoutingResult
from agentend.kernel.registry import CapabilityRegistry

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events emitted by the kernel."""

    STARTED = "started"
    ROUTING = "routing"
    CAPABILITY_SELECTED = "capability_selected"
    EXECUTING = "executing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Event emitted during kernel processing."""

    type: EventType
    """Type of event."""

    timestamp: float
    """Unix timestamp of event."""

    data: Dict[str, Any] = field(default_factory=dict)
    """Event-specific data."""

    session_id: Optional[str] = None
    """Session identifier."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for streaming."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "session_id": self.session_id,
        }


@dataclass
class RequestContext:
    """Context for processing a single user request."""

    user_id: str
    """User identifier."""

    session_id: str
    """Session identifier."""

    messages: List[Dict[str, str]] = field(default_factory=list)
    """Conversation history (role, content pairs)."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Request-level metadata."""

    memory_refs: List[str] = field(default_factory=list)
    """References to memory/knowledge stores."""

    tenant_id: Optional[str] = None
    """Multi-tenant identifier."""


@dataclass
class AgentendConfig:
    """Configuration for the Agentend kernel."""

    default_model: str = "gpt-4"
    """Default LLM model."""

    router: Optional[IntentRouter] = None
    """Custom router instance."""

    registry: Optional[CapabilityRegistry] = None
    """Custom capability registry."""

    enable_streaming: bool = True
    """Enable event streaming."""

    max_concurrent_executions: int = 5
    """Max concurrent capability executions."""


class Agentend:
    """
    Main kernel for intent-driven agent execution.

    Routes user intents to appropriate capabilities and streams
    execution progress as AG-UI events.
    """

    def __init__(self, config: Optional[AgentendConfig] = None) -> None:
        """
        Initialize the Agentend kernel.

        Args:
            config: Optional configuration. Uses defaults if None.
        """
        self.config = config or AgentendConfig()
        self.router = self.config.router or IntentRouter()
        self.registry = self.config.registry or CapabilityRegistry()
        self._execution_semaphore = asyncio.Semaphore(
            self.config.max_concurrent_executions
        )

    async def process_intent(
        self,
        intent: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Process a user intent and stream execution events.

        Classifies the intent, routes to appropriate capability,
        and streams AG-UI events during execution.

        Args:
            intent: User intent or query.
            session_id: Session identifier.
            context: Optional context dict (merged into RequestContext).

        Yields:
            AgentEvent objects as processing progresses.
        """
        import time

        context = context or {}
        request_context = RequestContext(
            user_id=context.get("user_id", "default"),
            session_id=session_id,
            messages=context.get("messages", []),
            metadata=context.get("metadata", {}),
            memory_refs=context.get("memory_refs", []),
            tenant_id=context.get("tenant_id"),
        )

        try:
            # Emit started event
            started_event = AgentEvent(
                type=EventType.STARTED,
                timestamp=time.time(),
                data={"intent": intent},
                session_id=session_id,
            )
            yield started_event

            # Emit routing event
            routing_event = AgentEvent(
                type=EventType.ROUTING,
                timestamp=time.time(),
                data={"intent": intent},
                session_id=session_id,
            )
            yield routing_event

            # Route intent to capability
            routing_result = await self.router.route(
                intent, context={"session_id": session_id}
            )

            # Emit capability selection event
            selected_event = AgentEvent(
                type=EventType.CAPABILITY_SELECTED,
                timestamp=time.time(),
                data={
                    "capability": routing_result.capability_name,
                    "confidence": routing_result.confidence,
                    "routing_method": routing_result.routing_method,
                    "metadata": routing_result.metadata,
                },
                session_id=session_id,
            )
            yield selected_event

            # Look up capability
            capability = self.registry.lookup(routing_result.capability_name)
            if not capability:
                raise ValueError(
                    f"Capability not found: {routing_result.capability_name}"
                )

            # Emit executing event
            executing_event = AgentEvent(
                type=EventType.EXECUTING,
                timestamp=time.time(),
                data={"capability": routing_result.capability_name},
                session_id=session_id,
            )
            yield executing_event

            # Execute capability with semaphore for concurrency control
            async with self._execution_semaphore:
                result = await capability.execute(request_context, intent=intent)

                # Handle streaming results
                if hasattr(result, "__aiter__"):
                    # Result is an async generator
                    async for chunk in result:
                        streaming_event = AgentEvent(
                            type=EventType.STREAMING,
                            timestamp=time.time(),
                            data={"chunk": chunk},
                            session_id=session_id,
                        )
                        yield streaming_event
                else:
                    # Regular result
                    streaming_event = AgentEvent(
                        type=EventType.STREAMING,
                        timestamp=time.time(),
                        data={"result": result},
                        session_id=session_id,
                    )
                    yield streaming_event

            # Emit completed event
            completed_event = AgentEvent(
                type=EventType.COMPLETED,
                timestamp=time.time(),
                data={"capability": routing_result.capability_name},
                session_id=session_id,
            )
            yield completed_event

        except Exception as e:
            logger.error(f"Error processing intent: {e}")
            error_event = AgentEvent(
                type=EventType.ERROR,
                timestamp=time.time(),
                data={"error": str(e), "intent": intent},
                session_id=session_id,
            )
            yield error_event
