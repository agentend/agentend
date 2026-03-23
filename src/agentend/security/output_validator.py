"""Output validation for PALADIN Layer 3."""

import re
import json
from typing import Optional, Any


class OutputValidator:
    """
    Validates LLM outputs before tool execution.

    Implements PALADIN Layer 3: checks for leaked system prompts,
    injection in outputs, and validates output structure.
    """

    # Patterns that indicate system prompt leakage
    PROMPT_LEAKAGE_PATTERNS = [
        r"(?i)(system prompt|secret.*?prompt|hidden.*?instruction|backdoor|jailbreak)",
        r"(?i)(you are.*?to.*?ignore.*?previous)",
        r"(?i)(disregard.*?instruction|forget.*?instruction|new instruction)",
        r"<\|system_prompt\|>",
        r"<\|developer_instructions\|>",
    ]

    # Patterns that indicate injection attempts in output
    INJECTION_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"(?i)javascript:",
        r"\$\{.*?\}",
        r"\{\{.*?\}\}",
        r"(?i)exec\s*\(",
        r"(?i)eval\s*\(",
    ]

    def __init__(self, strict: bool = True, allow_json: bool = True):
        """
        Initialize validator.

        Args:
            strict: If True, reject any suspicious patterns.
            allow_json: If True, validate JSON-formatted outputs.
        """
        self.strict = strict
        self.allow_json = allow_json

    def validate(self, output: str) -> bool:
        """
        Validate LLM output.

        Args:
            output: Output to validate.

        Returns:
            True if output is valid.

        Raises:
            ValueError: If validation fails and strict mode enabled.
        """
        issues = []

        # Check for prompt leakage
        leakage = self._check_prompt_leakage(output)
        if leakage:
            issues.append(f"Prompt leakage detected: {leakage}")

        # Check for injection patterns
        injections = self._check_injections(output)
        if injections:
            issues.append(f"Injection patterns detected: {injections}")

        # Try to parse as JSON if applicable
        if self.allow_json:
            try:
                json.loads(output)
            except json.JSONDecodeError:
                # Not JSON, which is fine
                pass

        if issues:
            if self.strict:
                raise ValueError("; ".join(issues))
            return False

        return True

    def validate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """
        Validate tool call before execution.

        Args:
            tool_name: Name of tool to call.
            arguments: Arguments to pass to tool.

        Returns:
            True if safe to execute.

        Raises:
            ValueError: If validation fails and strict mode enabled.
        """
        issues = []

        # Check tool name
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", tool_name):
            issues.append(f"Invalid tool name: {tool_name}")

        # Check arguments for injection
        for key, value in arguments.items():
            if isinstance(value, str):
                if self._check_injections(value):
                    issues.append(f"Injection in argument {key}")

        if issues:
            if self.strict:
                raise ValueError("; ".join(issues))
            return False

        return True

    def _check_prompt_leakage(self, text: str) -> Optional[str]:
        """
        Check for system prompt leakage patterns.

        Args:
            text: Text to check.

        Returns:
            Matched pattern or None.
        """
        for pattern in self.PROMPT_LEAKAGE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _check_injections(self, text: str) -> Optional[str]:
        """
        Check for injection patterns.

        Args:
            text: Text to check.

        Returns:
            Matched pattern or None.
        """
        for pattern in self.INJECTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def extract_json_from_output(self, output: str) -> Optional[dict[str, Any]]:
        """
        Safely extract JSON from LLM output.

        Args:
            output: Output text containing JSON.

        Returns:
            Parsed JSON object or None if not found/invalid.
        """
        # Try direct parse
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in markdown code blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find first complete JSON object
        for i, char in enumerate(output):
            if char == "{":
                try:
                    # Find matching closing brace
                    depth = 0
                    for j in range(i, len(output)):
                        if output[j] == "{":
                            depth += 1
                        elif output[j] == "}":
                            depth -= 1
                            if depth == 0:
                                return json.loads(output[i:j+1])
                except json.JSONDecodeError:
                    pass

        return None

    def sanitize_output(self, output: str) -> str:
        """
        Remove suspicious patterns from output.

        Args:
            output: Output to sanitize.

        Returns:
            Sanitized output.
        """
        result = output

        # Remove injection patterns
        for pattern in self.INJECTION_PATTERNS:
            result = re.sub(pattern, "", result)

        return result
