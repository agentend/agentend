"""
EventStream: High-level API for emitting AG-UI events.

Provides convenient methods for emitting all event types.
Transport-agnostic (SSE, WebSocket, etc).
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable

from .types import (
    AgentEvent,
    RunStarted,
    TextMessageStart,
    TextMessageContent,
    TextMessageEnd,
    ToolCallStart,
    ToolCallArgs,
    ToolCallEnd,
    StateSnapshot,
    StateDelta,
    ThinkingStep,
    Interrupt,
    RunFinished,
    RunError,
)

logger = logging.getLogger(__name__)


class EventStream:
    """
    High-level API for emitting AG-UI events.

    Handles event serialization and transport dispatch.
    Transport is pluggable (SSE, WebSocket, etc).
    """

    def __init__(
        self,
        transport: Optional[Callable[[AgentEvent], Awaitable[None]]] = None,
        run_id: Optional[str] = None,
    ):
        """
        Initialize EventStream.

        Args:
            transport: Async callable that sends events
            run_id: Optional run ID for all events
        """
        self.transport = transport
        self.run_id = run_id
        self._event_count = 0

    async def emit(self, event: AgentEvent) -> None:
        """
        Emit an event.

        Args:
            event: The event to emit
        """
        if self.run_id and not event.run_id:
            event.run_id = self.run_id

        self._event_count += 1
        logger.debug(f"Event {self._event_count}: {event.type.value}")

        if self.transport:
            try:
                await self.transport(event)
            except Exception as e:
                logger.error(f"Failed to send event: {e}")

    async def run_started(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        input: str = "",
    ) -> None:
        """Emit run start event."""
        event = RunStarted(
            run_id=self.run_id,
            user_id=user_id,
            session_id=session_id,
            input=input,
        )
        await self.emit(event)

    async def text_message_start(self) -> None:
        """Emit text message start."""
        event = TextMessageStart(run_id=self.run_id)
        await self.emit(event)

    async def text(self, content: str, delta: bool = True) -> None:
        """
        Emit text content.

        Args:
            content: Text content
            delta: Whether this is a delta chunk
        """
        event = TextMessageContent(
            run_id=self.run_id,
            content=content,
            delta=delta,
        )
        await self.emit(event)

    async def text_message_end(self, stop_reason: str = "end_turn") -> None:
        """Emit text message end."""
        event = TextMessageEnd(
            run_id=self.run_id,
            stop_reason=stop_reason,
        )
        await self.emit(event)

    async def tool_call_start(self, tool_name: str, tool_use_id: str = "") -> None:
        """
        Emit tool call start.

        Args:
            tool_name: Name of the tool
            tool_use_id: Unique ID for this tool use
        """
        event = ToolCallStart(
            run_id=self.run_id,
            tool_name=tool_name,
            tool_use_id=tool_use_id,
        )
        await self.emit(event)

    async def tool_call_args(
        self,
        tool_use_id: str,
        args: str,
        delta: bool = True,
    ) -> None:
        """
        Emit tool arguments.

        Args:
            tool_use_id: Tool use ID
            args: Arguments JSON string or delta
            delta: Whether this is a delta
        """
        event = ToolCallArgs(
            run_id=self.run_id,
            tool_use_id=tool_use_id,
            args=args,
            delta=delta,
        )
        await self.emit(event)

    async def tool_call_end(
        self,
        tool_name: str,
        tool_use_id: str,
        result: Any = None,
        is_error: bool = False,
    ) -> None:
        """
        Emit tool call end with result.

        Args:
            tool_name: Tool name
            tool_use_id: Tool use ID
            result: Tool result
            is_error: Whether result is an error
        """
        event = ToolCallEnd(
            run_id=self.run_id,
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            result=result,
            is_error=is_error,
        )
        await self.emit(event)

    async def state_snapshot(
        self,
        state: Dict[str, Any],
        memory: Dict[str, Any] = None,
    ) -> None:
        """
        Emit full state snapshot.

        Args:
            state: Full state dict
            memory: Optional memory context
        """
        event = StateSnapshot(
            run_id=self.run_id,
            state=state,
            memory=memory or {},
        )
        await self.emit(event)

    async def state_delta(
        self,
        path: str,
        value: Any,
        operation: str = "set",
    ) -> None:
        """
        Emit state delta.

        Args:
            path: JSON path to changed value
            value: New value
            operation: Operation type (set, delete, append)
        """
        event = StateDelta(
            run_id=self.run_id,
            path=path,
            value=value,
            operation=operation,
        )
        await self.emit(event)

    async def thinking(
        self,
        content: str,
        thinking_type: str = "planning",
    ) -> None:
        """
        Emit thinking step.

        Args:
            content: Thinking content
            thinking_type: Type of thinking (planning, reasoning, reflection)
        """
        event = ThinkingStep(
            run_id=self.run_id,
            content=content,
            thinking_type=thinking_type,
        )
        await self.emit(event)

    async def interrupt(
        self,
        reason: str,
        action_required: str = "approve",
        options: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> None:
        """
        Emit interrupt request for human approval.

        Args:
            reason: Why execution is paused
            action_required: Type of action needed
            options: Optional list of choices
            context: Optional context for the interrupt
        """
        event = Interrupt(
            run_id=self.run_id,
            reason=reason,
            action_required=action_required,
            options=options or [],
            context=context or {},
        )
        await self.emit(event)

    async def finish(
        self,
        result: Any = None,
        stop_reason: str = "end_turn",
        messages_sent: int = 0,
        tools_used: List[str] = None,
    ) -> None:
        """
        Emit run finish event.

        Args:
            result: Final result
            stop_reason: Reason for stopping
            messages_sent: Number of messages sent
            tools_used: List of tools used
        """
        event = RunFinished(
            run_id=self.run_id,
            result=result,
            stop_reason=stop_reason,
            messages_sent=messages_sent,
            tools_used=tools_used or [],
        )
        await self.emit(event)

    async def error(
        self,
        message: str,
        error_type: str = "runtime_error",
        traceback: Optional[str] = None,
        recoverable: bool = False,
    ) -> None:
        """
        Emit run error event.

        Args:
            message: Error message
            error_type: Type of error
            traceback: Optional traceback
            recoverable: Whether error is recoverable
        """
        event = RunError(
            run_id=self.run_id,
            error_type=error_type,
            message=message,
            traceback=traceback,
            recoverable=recoverable,
        )
        await self.emit(event)

    def get_event_count(self) -> int:
        """Get number of events emitted."""
        return self._event_count
