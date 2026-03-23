"""
AG-UI event types for streaming agent execution.

All events are dataclasses with JSON serialization support.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class EventType(str, Enum):
    """Enumeration of all event types."""
    RUN_STARTED = "run_started"
    TEXT_MESSAGE_START = "text_message_start"
    TEXT_MESSAGE_CONTENT = "text_message_content"
    TEXT_MESSAGE_END = "text_message_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_END = "tool_call_end"
    STATE_SNAPSHOT = "state_snapshot"
    STATE_DELTA = "state_delta"
    THINKING_STEP = "thinking_step"
    INTERRUPT = "interrupt"
    RUN_FINISHED = "run_finished"
    RUN_ERROR = "run_error"


@dataclass
class AgentEvent:
    """Base class for all agent events."""
    type: EventType
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: Optional[str] = None

    def to_json(self) -> str:
        """Serialize event to JSON."""
        data = asdict(self)
        data["type"] = self.type.value
        return json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        data = asdict(self)
        data["type"] = self.type.value
        return data


@dataclass
class RunStarted(AgentEvent):
    """Emitted when a run starts."""
    type: EventType = field(default=EventType.RUN_STARTED, init=False)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    input: str = ""


@dataclass
class TextMessageStart(AgentEvent):
    """Emitted when agent starts generating text output."""
    type: EventType = field(default=EventType.TEXT_MESSAGE_START, init=False)
    content_type: str = "text"


@dataclass
class TextMessageContent(AgentEvent):
    """Emitted when agent generates text content."""
    type: EventType = field(default=EventType.TEXT_MESSAGE_CONTENT, init=False)
    content: str = ""
    delta: bool = False  # True if this is a delta/chunk


@dataclass
class TextMessageEnd(AgentEvent):
    """Emitted when agent finishes generating text output."""
    type: EventType = field(default=EventType.TEXT_MESSAGE_END, init=False)
    stop_reason: str = "end_turn"


@dataclass
class ToolCallStart(AgentEvent):
    """Emitted when agent calls a tool."""
    type: EventType = field(default=EventType.TOOL_CALL_START, init=False)
    tool_name: str = ""
    tool_use_id: str = ""


@dataclass
class ToolCallArgs(AgentEvent):
    """Emitted when tool arguments are being streamed."""
    type: EventType = field(default=EventType.TOOL_CALL_ARGS, init=False)
    tool_use_id: str = ""
    args: str = ""
    delta: bool = False  # True if this is a delta


@dataclass
class ToolCallEnd(AgentEvent):
    """Emitted when tool call completes with result."""
    type: EventType = field(default=EventType.TOOL_CALL_END, init=False)
    tool_name: str = ""
    tool_use_id: str = ""
    result: Any = None
    is_error: bool = False


@dataclass
class StateSnapshot(AgentEvent):
    """Emitted with full state snapshot."""
    type: EventType = field(default=EventType.STATE_SNAPSHOT, init=False)
    state: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateDelta(AgentEvent):
    """Emitted with incremental state changes."""
    type: EventType = field(default=EventType.STATE_DELTA, init=False)
    path: str = ""  # JSON path to changed value
    value: Any = None
    operation: str = "set"  # set, delete, append, etc


@dataclass
class ThinkingStep(AgentEvent):
    """Emitted with agent's internal reasoning."""
    type: EventType = field(default=EventType.THINKING_STEP, init=False)
    content: str = ""
    thinking_type: str = "planning"  # planning, reasoning, reflection


@dataclass
class Interrupt(AgentEvent):
    """Emitted when agent pauses for human approval."""
    type: EventType = field(default=EventType.INTERRUPT, init=False)
    reason: str = ""
    action_required: str = "approve"  # approve, select, input
    options: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunFinished(AgentEvent):
    """Emitted when run completes successfully."""
    type: EventType = field(default=EventType.RUN_FINISHED, init=False)
    result: Any = None
    stop_reason: str = "end_turn"
    messages_sent: int = 0
    tools_used: List[str] = field(default_factory=list)


@dataclass
class RunError(AgentEvent):
    """Emitted when run encounters an error."""
    type: EventType = field(default=EventType.RUN_ERROR, init=False)
    error_type: str = ""
    message: str = ""
    traceback: Optional[str] = None
    recoverable: bool = False
