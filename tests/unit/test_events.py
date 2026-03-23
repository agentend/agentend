"""Tests for AG-UI event types."""
import json
import pytest
from dataclasses import asdict

from agentend.events.types import (
    EventType,
    RunStarted,
    TextMessageContent,
    TextMessageEnd,
    ToolCallStart,
    ToolCallArgs,
    ToolCallEnd,
    RunFinished,
    RunError,
)


class TestEventTypes:
    """Test AG-UI event type definitions."""

    def test_event_type_enum(self):
        assert EventType.RUN_STARTED == "run_started"
        assert EventType.TEXT_MESSAGE_CONTENT == "text_message_content"
        assert EventType.TOOL_CALL_START == "tool_call_start"
        assert EventType.RUN_FINISHED == "run_finished"

    def test_run_started_event(self):
        event = RunStarted(run_id="run-123", user_id="u1")
        assert event.type == EventType.RUN_STARTED
        assert event.run_id == "run-123"
        d = asdict(event)
        assert d["type"] == "run_started"
        assert d["run_id"] == "run-123"

    def test_text_message_content_event(self):
        event = TextMessageContent(content="Hello ", run_id="r1")
        assert event.type == EventType.TEXT_MESSAGE_CONTENT
        assert event.content == "Hello "

    def test_tool_call_events(self):
        start = ToolCallStart(tool_name="save_invoice", tool_use_id="tc-1", run_id="r1")
        assert start.type == EventType.TOOL_CALL_START
        assert start.tool_name == "save_invoice"

        end = ToolCallEnd(run_id="r1")
        assert end.type == EventType.TOOL_CALL_END

    def test_run_error_event(self):
        event = RunError(
            run_id="run-123",
            error_type="MODEL_UNAVAILABLE",
            message="Ollama is not running",
        )
        assert event.type == EventType.RUN_ERROR
        assert "Ollama" in event.message

    def test_events_serialize_to_dict(self):
        event = RunStarted(run_id="r1", user_id="u1")
        d = asdict(event)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["type"] == "run_started"
