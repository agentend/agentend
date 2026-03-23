"""
Tool calling / function calling worker for model-based tool selection.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import json
import logging

from agentend.fleet.worker import BaseWorker, WorkerConfig

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A single tool invocation."""

    tool_name: str
    """Name of the tool to call."""

    arguments: Dict[str, Any]
    """Arguments to pass to the tool."""

    reasoning: Optional[str] = None
    """Model's reasoning for this call."""


@dataclass
class ToolCallResult:
    """Result of tool calling."""

    calls: List[ToolCall]
    """List of tool calls made."""

    raw_response: str
    """Raw model response."""

    execution_results: Dict[str, Any] = None
    """Results from executing the tools."""

    def __post_init__(self) -> None:
        """Initialize default execution results."""
        if self.execution_results is None:
            self.execution_results = {}


class ToolCallWorker(BaseWorker):
    """
    Worker for function calling / tool use.

    Formats available tools for the model, parses tool call responses,
    and executes selected tools with proper error handling.
    """

    def __init__(
        self,
        config: Optional[WorkerConfig] = None,
        tools: Optional[Dict[str, Callable]] = None,
    ) -> None:
        """
        Initialize the tool call worker.

        Args:
            config: WorkerConfig for model selection.
            tools: Dictionary mapping tool names to callable functions.
        """
        if config is None:
            config = WorkerConfig(
                model="gpt-4",
                temperature=0.0,
                max_tokens=2000,
            )

        super().__init__(
            config=config,
            name="tool_call",
            input_type=str,
            output_type=ToolCallResult,
        )
        self.tools = tools or {}

    def register_tool(self, name: str, func: Callable) -> None:
        """
        Register a tool function.

        Args:
            name: Name of the tool.
            func: Callable to execute.
        """
        self.tools[name] = func

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> ToolCallResult:
        """
        Select and call appropriate tools.

        Args:
            context: Optional request context.
            **kwargs: Must include 'task' key. Can include 'tools' to override.

        Returns:
            ToolCallResult with calls and execution results.
        """
        task = kwargs.get("task", "")
        tools_to_use = kwargs.get("tools")

        if not task:
            return ToolCallResult(calls=[], raw_response="")

        # Use provided tools or registered ones
        available_tools = tools_to_use or self.tools

        if not available_tools:
            return ToolCallResult(
                calls=[],
                raw_response="No tools available",
            )

        # Build tool descriptions
        tool_descriptions = self._format_tools(available_tools)

        # Build prompt
        prompt = f"""You are given the following tools:

{tool_descriptions}

Task: {task}

Select which tools to call and with what arguments. Respond with JSON:
{{
  "reasoning": "explanation of approach",
  "calls": [
    {{"tool_name": "tool1", "arguments": {{"arg1": "value1"}}}},
    {{"tool_name": "tool2", "arguments": {{"arg2": "value2"}}}}
  ]
}}

Respond ONLY with valid JSON."""

        response = await super().execute(context, prompt=prompt, **{
            k: v for k, v in kwargs.items() if k not in ("task", "tools", "prompt")
        })

        # Parse tool calls from response
        calls = self._parse_tool_calls(response)

        # Execute tools
        execution_results = {}
        if kwargs.get("execute", True):
            execution_results = await self._execute_tools(calls, available_tools)

        return ToolCallResult(
            calls=calls,
            raw_response=response,
            execution_results=execution_results,
        )

    def _format_tools(self, tools: Dict[str, Callable]) -> str:
        """
        Format tools as descriptions for the model.

        Args:
            tools: Dictionary of tools.

        Returns:
            Formatted tool description string.
        """
        descriptions = []
        for name, func in tools.items():
            doc = (func.__doc__ or "").strip().split("\n")[0]
            descriptions.append(f"- {name}: {doc or 'No description'}")

        return "\n".join(descriptions)

    def _parse_tool_calls(self, response: str) -> List[ToolCall]:
        """
        Parse tool calls from model response.

        Args:
            response: Model response (should be JSON).

        Returns:
            List of ToolCall objects.
        """
        try:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start < 0 or json_end <= json_start:
                return []

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            calls = []
            for call_data in data.get("calls", []):
                call = ToolCall(
                    tool_name=call_data.get("tool_name", ""),
                    arguments=call_data.get("arguments", {}),
                    reasoning=data.get("reasoning"),
                )
                if call.tool_name:
                    calls.append(call)

            return calls

        except Exception as e:
            logger.error(f"Failed to parse tool calls: {e}")
            return []

    async def _execute_tools(
        self, calls: List[ToolCall], available_tools: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """
        Execute tool calls.

        Args:
            calls: List of tool calls to execute.
            available_tools: Dictionary of available tools.

        Returns:
            Dictionary mapping tool names to results.
        """
        results = {}

        for call in calls:
            if call.tool_name not in available_tools:
                results[call.tool_name] = {"error": "Tool not found"}
                continue

            try:
                tool = available_tools[call.tool_name]
                result = tool(**call.arguments)

                # Handle async results
                if hasattr(result, "__await__"):
                    result = await result

                results[call.tool_name] = result

            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                results[call.tool_name] = {"error": str(e)}

        return results
