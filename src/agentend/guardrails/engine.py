"""Guardrails engine for input moderation and output validation."""

from enum import Enum
from typing import Optional, Any, Callable
from dataclasses import dataclass

from agentend.security.sanitizer import InputSanitizer
from agentend.security.output_validator import OutputValidator


class GuardrailAction(str, Enum):
    """Actions to take when guardrails are violated."""

    BLOCK = "block"
    WARN = "warn"
    ALLOW = "allow"
    QUARANTINE = "quarantine"


@dataclass
class GuardrailRule:
    """Single guardrail rule."""

    name: str
    description: str
    check: Callable[[str], bool]
    action: GuardrailAction
    priority: int


class GuardrailsEngine:
    """
    Guardrails engine for input moderation, LLM execution, and output validation.

    Configurable rules with tool call validation before execution.
    """

    def __init__(self):
        """Initialize guardrails engine."""
        self.input_rules: list[GuardrailRule] = []
        self.output_rules: list[GuardrailRule] = []
        self.tool_rules: list[GuardrailRule] = []
        self.sanitizer = InputSanitizer()
        self.output_validator = OutputValidator()

    def add_input_rule(
        self,
        name: str,
        description: str,
        check: Callable[[str], bool],
        action: GuardrailAction = GuardrailAction.BLOCK,
        priority: int = 0,
    ) -> None:
        """
        Add input moderation rule.

        Args:
            name: Rule name.
            description: Rule description.
            check: Function that returns True if rule violated.
            action: Action to take on violation.
            priority: Rule priority (higher = checked first).
        """
        rule = GuardrailRule(name, description, check, action, priority)
        self.input_rules.append(rule)
        self.input_rules.sort(key=lambda r: r.priority, reverse=True)

    def add_output_rule(
        self,
        name: str,
        description: str,
        check: Callable[[str], bool],
        action: GuardrailAction = GuardrailAction.BLOCK,
        priority: int = 0,
    ) -> None:
        """
        Add output validation rule.

        Args:
            name: Rule name.
            description: Rule description.
            check: Function that returns True if rule violated.
            action: Action to take on violation.
            priority: Rule priority (higher = checked first).
        """
        rule = GuardrailRule(name, description, check, action, priority)
        self.output_rules.append(rule)
        self.output_rules.sort(key=lambda r: r.priority, reverse=True)

    def add_tool_rule(
        self,
        name: str,
        description: str,
        check: Callable[[str, dict], bool],
        action: GuardrailAction = GuardrailAction.BLOCK,
        priority: int = 0,
    ) -> None:
        """
        Add tool call validation rule.

        Args:
            name: Rule name.
            description: Rule description.
            check: Function that returns True if rule violated (receives tool_name, args).
            action: Action to take on violation.
            priority: Rule priority (higher = checked first).
        """
        rule = GuardrailRule(name, description, check, action, priority)
        self.tool_rules.append(rule)
        self.tool_rules.sort(key=lambda r: r.priority, reverse=True)

    async def check_input(self, text: str) -> dict[str, Any]:
        """
        Check input against all input rules.

        Args:
            text: Input text to check.

        Returns:
            Result dict with violations and recommended action.
        """
        result = {
            "passed": True,
            "violations": [],
            "action": GuardrailAction.ALLOW,
            "blocked": False,
        }

        for rule in self.input_rules:
            try:
                if rule.check(text):
                    result["passed"] = False
                    result["violations"].append({
                        "rule": rule.name,
                        "description": rule.description,
                        "action": rule.action,
                    })

                    if rule.action == GuardrailAction.BLOCK:
                        result["action"] = GuardrailAction.BLOCK
                        result["blocked"] = True
                        break
            except Exception as e:
                result["violations"].append({
                    "rule": rule.name,
                    "error": str(e),
                    "action": GuardrailAction.WARN,
                })

        return result

    async def check_output(self, text: str) -> dict[str, Any]:
        """
        Check LLM output against all output rules.

        Args:
            text: Output text to check.

        Returns:
            Result dict with violations and recommended action.
        """
        result = {
            "passed": True,
            "violations": [],
            "action": GuardrailAction.ALLOW,
            "blocked": False,
            "sanitized": text,
        }

        for rule in self.output_rules:
            try:
                if rule.check(text):
                    result["passed"] = False
                    result["violations"].append({
                        "rule": rule.name,
                        "description": rule.description,
                        "action": rule.action,
                    })

                    if rule.action == GuardrailAction.BLOCK:
                        result["action"] = GuardrailAction.BLOCK
                        result["blocked"] = True
                        break
            except Exception as e:
                result["violations"].append({
                    "rule": rule.name,
                    "error": str(e),
                    "action": GuardrailAction.WARN,
                })

        # Sanitize output if violations found
        if not result["passed"]:
            result["sanitized"] = self.output_validator.sanitize_output(text)

        return result

    async def check_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate tool call before execution.

        Args:
            tool_name: Name of tool to call.
            arguments: Tool arguments.

        Returns:
            Validation result.
        """
        result = {
            "passed": True,
            "violations": [],
            "action": GuardrailAction.ALLOW,
            "allowed": True,
        }

        # First validate against tool rules
        for rule in self.tool_rules:
            try:
                if rule.check(tool_name, arguments):
                    result["passed"] = False
                    result["violations"].append({
                        "rule": rule.name,
                        "description": rule.description,
                        "action": rule.action,
                    })

                    if rule.action == GuardrailAction.BLOCK:
                        result["action"] = GuardrailAction.BLOCK
                        result["allowed"] = False
                        break
            except Exception as e:
                result["violations"].append({
                    "rule": rule.name,
                    "error": str(e),
                    "action": GuardrailAction.WARN,
                })

        # Validate tool call structure
        try:
            self.output_validator.validate_tool_call(tool_name, arguments)
        except ValueError as e:
            result["passed"] = False
            result["violations"].append({
                "rule": "tool_structure_validation",
                "description": str(e),
                "action": GuardrailAction.BLOCK,
            })
            result["allowed"] = False

        return result

    def set_default_rules(self) -> None:
        """Configure default safety rules."""
        # Input rules
        self.add_input_rule(
            "injection_detection",
            "Detect SQL/command injection patterns",
            lambda text: any(
                pattern in text.lower()
                for pattern in ["union select", "drop table", "exec(", "eval("]
            ),
            GuardrailAction.BLOCK,
            priority=100,
        )

        self.add_input_rule(
            "length_limit",
            "Enforce maximum input length",
            lambda text: len(text) > 100000,
            GuardrailAction.BLOCK,
            priority=90,
        )

        # Output rules
        self.add_output_rule(
            "prompt_leakage",
            "Detect system prompt leakage",
            lambda text: "<|system_prompt|>" in text or "system prompt:" in text.lower(),
            GuardrailAction.BLOCK,
            priority=100,
        )

        self.add_output_rule(
            "xss_detection",
            "Detect XSS patterns in output",
            lambda text: "<script" in text.lower() or "javascript:" in text.lower(),
            GuardrailAction.WARN,
            priority=90,
        )

        # Tool rules
        self.add_tool_rule(
            "dangerous_commands",
            "Block dangerous system commands",
            lambda tool, args: tool in ["exec", "eval", "system", "shell"] and args,
            GuardrailAction.BLOCK,
            priority=100,
        )
