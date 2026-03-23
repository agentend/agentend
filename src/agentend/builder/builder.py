"""
Conversational Capability Builder.

Orchestrates building Agentend capabilities through natural language conversation.
Users describe what they want, and the builder extracts intent patterns, configures
worker slots, generates prompt templates, and produces deployable code.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class BuildStage(Enum):
    """Stages in capability building process."""
    UNDERSTAND = "understand"
    DEFINE_INTENTS = "define_intents"
    CONFIGURE_WORKERS = "configure_workers"
    DESIGN_PROMPTS = "design_prompts"
    SET_SCHEMA = "set_schema"
    ADD_EXAMPLES = "add_examples"
    REVIEW = "review"
    COMPLETE = "complete"


@dataclass
class BuilderResponse:
    """Response from processing a builder message."""
    message: str
    """What to say back to the user."""
    stage: str
    """Current building stage."""
    capability_preview: Optional[Dict[str, Any]] = None
    """Preview of what's been captured so far."""
    questions: List[str] = field(default_factory=list)
    """Follow-up questions for the user."""
    ready_to_generate: bool = False
    """Whether capability is ready to generate code."""


@dataclass
class BuilderSession:
    """Tracks an in-progress capability being built via conversation."""
    session_id: str
    """Unique session identifier."""
    name: Optional[str] = None
    """Capability name (e.g., 'ticket_classifier')."""
    description: Optional[str] = None
    """Capability description."""
    intent_patterns: List[str] = field(default_factory=list)
    """Patterns that trigger this capability (e.g., 'classify ticket', 'categorize request')."""
    worker_slots: Dict[str, str] = field(default_factory=dict)
    """Slot -> model override mapping (e.g., 'classify' -> 'gpt-4')."""
    prompt_template: Optional[str] = None
    """Jinja2-style prompt template with slots like {{ context }}, {{ instructions }}."""
    tools: List[str] = field(default_factory=list)
    """External tools/APIs this capability can call."""
    output_schema: Optional[Dict[str, Any]] = None
    """JSON schema for output validation."""
    validation_rules: List[str] = field(default_factory=list)
    """Rules for validating output (human-readable)."""
    examples: List[Dict[str, str]] = field(default_factory=list)
    """Few-shot examples as {input, output} pairs."""
    created_at: str = ""
    """ISO timestamp of session creation."""
    status: str = "drafting"
    """Status: drafting | testing | deployed."""
    current_stage: str = "understand"
    """Current building stage."""
    stage_data: Dict[str, Any] = field(default_factory=dict)
    """Temporary data for current stage."""


class CapabilityBuilder:
    """
    Builds Agentend capabilities through conversational interaction.

    Users describe what they want in natural language, and the builder:
    1. Extracts intent patterns from the description
    2. Suggests appropriate worker slots and models
    3. Generates prompt templates with Template Method slots
    4. Creates validation rules and output schemas
    5. Generates test cases
    6. Produces deployable Capability code

    Usage:
        builder = CapabilityBuilder()
        session = builder.new_session()

        result = await builder.process_message(session.session_id,
            "I need a capability that categorizes support tickets")

        result = await builder.process_message(session.session_id,
            "Urgency levels are: critical, high, medium, low")

        code = builder.generate_code(session.session_id)
        builder.deploy(session.session_id, app)
    """

    def __init__(self):
        """Initialize the capability builder."""
        self.sessions: Dict[str, BuilderSession] = {}
        self.stage_handlers = {
            BuildStage.UNDERSTAND: self._handle_understand,
            BuildStage.DEFINE_INTENTS: self._handle_define_intents,
            BuildStage.CONFIGURE_WORKERS: self._handle_configure_workers,
            BuildStage.DESIGN_PROMPTS: self._handle_design_prompts,
            BuildStage.SET_SCHEMA: self._handle_set_schema,
            BuildStage.ADD_EXAMPLES: self._handle_add_examples,
            BuildStage.REVIEW: self._handle_review,
        }

    def new_session(self) -> BuilderSession:
        """Create a new capability building session.

        Returns:
            BuilderSession with initialized defaults.
        """
        session_id = str(uuid.uuid4())
        session = BuilderSession(
            session_id=session_id,
            created_at=datetime.utcnow().isoformat(),
            current_stage=BuildStage.UNDERSTAND.value,
        )
        self.sessions[session_id] = session
        logger.info(f"Created new builder session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[BuilderSession]:
        """Retrieve a building session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            BuilderSession if found, None otherwise.
        """
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[BuilderSession]:
        """List all active building sessions.

        Returns:
            List of BuilderSession objects.
        """
        return list(self.sessions.values())

    async def process_message(
        self, session_id: str, message: str
    ) -> BuilderResponse:
        """Process a user message in the builder conversation.

        Routes to stage-specific handlers that extract structured information
        from natural language. Does NOT call an LLM; uses deterministic extraction
        and heuristics. The extracted data can be passed to LLM workers separately.

        Args:
            session_id: Session identifier.
            message: User message in natural language.

        Returns:
            BuilderResponse with next action and preview.

        Raises:
            ValueError: If session not found.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        current_stage = BuildStage(session.current_stage)
        handler = self.stage_handlers.get(current_stage)

        if handler is None:
            return BuilderResponse(
                message="Session complete. Use generate_code() to create capability.",
                stage=session.current_stage,
                ready_to_generate=True,
            )

        response = await handler(session, message)

        # Advance to next stage if this one is complete
        if response.ready_to_generate:
            session.current_stage = self._next_stage(current_stage).value
            session.stage_data.clear()

        return response

    def _next_stage(self, current: BuildStage) -> BuildStage:
        """Get the next stage in the building process.

        Args:
            current: Current BuildStage.

        Returns:
            Next BuildStage.
        """
        stages = list(BuildStage)
        idx = stages.index(current)
        if idx + 1 < len(stages):
            return stages[idx + 1]
        return BuildStage.COMPLETE

    async def _handle_understand(self, session: BuilderSession, message: str) -> BuilderResponse:
        """Handle UNDERSTAND stage: extract name and basic description.

        Args:
            session: Current builder session.
            message: User's description of what they want.

        Returns:
            BuilderResponse with extraction results.
        """
        # Extract capability name and description using simple heuristics
        words = message.lower().split()

        # Look for common patterns
        is_classifier = any(w in words for w in ["classify", "categorize", "label"])
        is_extractor = any(w in words for w in ["extract", "parse", "pull"])
        is_generator = any(w in words for w in ["generate", "create", "write"])
        is_summarizer = any(w in words for w in ["summarize", "condense", "brief"])

        capability_type = "custom"
        if is_classifier:
            capability_type = "classifier"
        elif is_extractor:
            capability_type = "extractor"
        elif is_generator:
            capability_type = "generator"
        elif is_summarizer:
            capability_type = "summarizer"

        # Extract a name from the message (first noun-like word or type-based)
        if "ticket" in words:
            session.name = f"{capability_type}_tickets"
        elif "email" in words:
            session.name = f"{capability_type}_emails"
        elif "customer" in words:
            session.name = f"{capability_type}_customers"
        else:
            session.name = f"{capability_type}_capability"

        session.description = message
        session.stage_data["raw_description"] = message

        return BuilderResponse(
            message=(
                f"Got it! You're building a {capability_type} capability called '{session.name}'. "
                f"Next, let's define the patterns that should trigger this capability. "
                f"For example, what phrases or intent patterns would users use? "
                f"(e.g., 'classify ticket', 'categorize support request')"
            ),
            stage=session.current_stage,
            capability_preview={"name": session.name, "type": capability_type},
            ready_to_generate=True,
        )

    async def _handle_define_intents(
        self, session: BuilderSession, message: str
    ) -> BuilderResponse:
        """Handle DEFINE_INTENTS stage: extract intent patterns.

        Args:
            session: Current builder session.
            message: User's list of intents/patterns.

        Returns:
            BuilderResponse with extracted patterns.
        """
        # Split by common delimiters
        patterns = [
            p.strip().strip("'\"").lower()
            for p in message.replace("\n", ",").split(",")
            if p.strip()
        ]
        patterns = [p for p in patterns if len(p) > 2]  # Filter noise

        session.intent_patterns.extend(patterns)
        session.stage_data["patterns"] = patterns

        preview = asdict(session)
        preview.pop("sessions", None)

        return BuilderResponse(
            message=(
                f"Great! I've captured {len(patterns)} intent patterns: {', '.join(patterns[:3])}... "
                f"Now let's configure worker slots. Which worker slots should this capability use? "
                f"(classify, extract, verify, summarize, generate, tool_call) "
                f"And do you want to override the default models for any slots?"
            ),
            stage=session.current_stage,
            capability_preview={"intents": session.intent_patterns},
            ready_to_generate=True,
        )

    async def _handle_configure_workers(
        self, session: BuilderSession, message: str
    ) -> BuilderResponse:
        """Handle CONFIGURE_WORKERS stage: extract slot and model preferences.

        Args:
            session: Current builder session.
            message: User's worker slot configuration.

        Returns:
            BuilderResponse with extracted configuration.
        """
        # Look for slot names and model specifications
        valid_slots = ["classify", "extract", "verify", "summarize", "generate", "tool_call"]
        message_lower = message.lower()

        # Extract explicit slot mentions
        mentioned_slots = [s for s in valid_slots if s in message_lower]
        if not mentioned_slots:
            # Default based on capability type
            if "classifier" in (session.name or "").lower():
                mentioned_slots = ["classify"]
            elif "extract" in (session.name or "").lower():
                mentioned_slots = ["extract"]
            else:
                mentioned_slots = ["classify", "extract"]

        session.stage_data["slots"] = mentioned_slots

        # Look for model overrides (e.g., "gpt-4", "claude-3", "llama")
        model_indicators = ["gpt-4", "gpt-3.5", "claude", "llama", "mistral"]
        for slot in mentioned_slots:
            for model in model_indicators:
                if model in message_lower:
                    session.worker_slots[slot] = model
                    break

        preview = {
            "name": session.name,
            "intent_patterns": session.intent_patterns,
            "worker_slots": mentioned_slots or mentioned_slots,
            "overrides": session.worker_slots,
        }

        return BuilderResponse(
            message=(
                f"Perfect! Configured worker slots: {', '.join(mentioned_slots)}. "
                f"Now let's design the prompt template. "
                f"What instructions should the worker receive? "
                f"(e.g., 'Classify the ticket urgency as critical, high, medium, or low')"
            ),
            stage=session.current_stage,
            capability_preview=preview,
            ready_to_generate=True,
        )

    async def _handle_design_prompts(
        self, session: BuilderSession, message: str
    ) -> BuilderResponse:
        """Handle DESIGN_PROMPTS stage: build the prompt template.

        Args:
            session: Current builder session.
            message: User's prompt instructions/template.

        Returns:
            BuilderResponse with generated template.
        """
        # Build a template using Template Method slots
        instruction = message.strip()
        session.prompt_template = self._generate_prompt_template(instruction, session)
        session.stage_data["instruction"] = instruction

        return BuilderResponse(
            message=(
                f"Excellent! I've created a prompt template with Template Method slots. "
                f"Now let's define the output schema. "
                f"What should the output look like? (e.g., a JSON object with 'urgency' and 'category' fields)"
            ),
            stage=session.current_stage,
            capability_preview={
                "prompt_template": session.prompt_template,
            },
            ready_to_generate=True,
        )

    async def _handle_set_schema(
        self, session: BuilderSession, message: str
    ) -> BuilderResponse:
        """Handle SET_SCHEMA stage: define output schema and validation rules.

        Args:
            session: Current builder session.
            message: User's output schema description.

        Returns:
            BuilderResponse with extracted schema.
        """
        # Extract field names and types from natural language description
        schema = self._extract_schema(message)
        session.output_schema = schema
        session.stage_data["schema_text"] = message

        # Create validation rules from schema
        for field_name in schema.get("properties", {}).keys():
            session.validation_rules.append(f"Must include '{field_name}' in output")

        return BuilderResponse(
            message=(
                f"Good! I've defined the output schema with fields: {', '.join(schema.get('properties', {}).keys())}. "
                f"Now let's add a few examples of input/output pairs to help the worker. "
                f"Give me an example input and what the output should be."
            ),
            stage=session.current_stage,
            capability_preview={
                "output_schema": session.output_schema,
                "validation_rules": session.validation_rules,
            },
            ready_to_generate=True,
        )

    async def _handle_add_examples(
        self, session: BuilderSession, message: str
    ) -> BuilderResponse:
        """Handle ADD_EXAMPLES stage: collect few-shot examples.

        Args:
            session: Current builder session.
            message: User's example input/output pair.

        Returns:
            BuilderResponse asking for more examples or moving to review.
        """
        # Try to parse input/output pairs from the message
        example = self._parse_example(message)
        if example:
            session.examples.append(example)

        if len(session.examples) < 2:
            return BuilderResponse(
                message=(
                    f"Great! I've captured {len(session.examples)} example(s). "
                    f"Please give me another input/output example, or say 'done' to move to review."
                ),
                stage=session.current_stage,
                capability_preview={"examples_count": len(session.examples)},
                ready_to_generate=False,
            )

        return BuilderResponse(
            message=(
                f"Perfect! I have {len(session.examples)} examples. "
                f"Let's review the complete specification before generating code."
            ),
            stage=session.current_stage,
            capability_preview={"examples": session.examples},
            ready_to_generate=True,
        )

    async def _handle_review(
        self, session: BuilderSession, message: str
    ) -> BuilderResponse:
        """Handle REVIEW stage: confirm specification before code generation.

        Args:
            session: Current builder session.
            message: User confirmation or feedback.

        Returns:
            BuilderResponse ready for code generation.
        """
        message_lower = message.lower()
        confirmed = any(w in message_lower for w in ["yes", "looks good", "confirmed", "ok"])

        if confirmed:
            session.status = "ready"
            return BuilderResponse(
                message=(
                    "Excellent! Your capability specification is ready. "
                    "You can now:\n"
                    "  - call generate_code() to create Python source\n"
                    "  - call generate_yaml() to create fleet.yaml additions\n"
                    "  - call deploy() to hot-deploy to a running instance"
                ),
                stage=session.current_stage,
                ready_to_generate=True,
            )
        else:
            # Allow edits
            return BuilderResponse(
                message=(
                    "No problem! What would you like to change? "
                    "You can modify: name, description, intents, prompts, schema, or examples."
                ),
                stage=session.current_stage,
                ready_to_generate=False,
            )

    def _generate_prompt_template(self, instruction: str, session: BuilderSession) -> str:
        """Generate a Jinja2-style prompt template with Template Method slots.

        Args:
            instruction: User's instruction text.
            session: Current builder session.

        Returns:
            Prompt template string with {{ slot_name }} placeholders.
        """
        template = f"""You are a {session.name or 'capability'} worker.

Your task: {instruction}

Input data:
{{{{ context }}}}

Instructions:
- Follow the rules below strictly
- Output MUST be valid JSON matching the schema
- Be concise and accurate

Rules:
{{{{ validation_rules }}}}

Examples:
{{{{ examples }}}}

Now process the input and produce output:"""

        return template

    def _extract_schema(self, description: str) -> Dict[str, Any]:
        """Extract JSON schema from natural language description.

        Args:
            description: User's description of output format.

        Returns:
            JSON Schema dict.
        """
        # Simple heuristic: look for "field: type" patterns or quoted field names
        properties = {}

        # Look for quoted strings (field names)
        import re

        # Pattern 1: quoted names
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", description)
        for field in quoted:
            if len(field) > 1:
                properties[field.lower().replace(" ", "_")] = {"type": "string"}

        # Pattern 2: common field patterns
        if "urgency" in description.lower() or "priority" in description.lower():
            properties["urgency"] = {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
            }
        if "category" in description.lower():
            properties["category"] = {"type": "string"}
        if "confidence" in description.lower():
            properties["confidence"] = {"type": "number", "minimum": 0, "maximum": 1}

        if not properties:
            properties["result"] = {"type": "string"}
            properties["confidence"] = {"type": "number"}

        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
        }

        return schema

    def _parse_example(self, message: str) -> Optional[Dict[str, str]]:
        """Parse an input/output example from user message.

        Args:
            message: User's example text.

        Returns:
            Dict with 'input' and 'output' keys, or None.
        """
        import re

        # Look for patterns like "input: ... output: ..." or "Input: ... Output: ..."
        lower_msg = message.lower()

        if "input" in lower_msg and "output" in lower_msg:
            # Match pattern: Input: "..." Output: "..."
            match = re.search(
                r'input\s*:?\s*"([^"]+)"\s+output\s*:?\s*(\{[^}]+\}|"[^"]+"|[^,\n]+)',
                message,
                re.IGNORECASE
            )
            if match:
                return {
                    "input": match.group(1).strip(),
                    "output": match.group(2).strip(),
                }

            # Alternative: match multi-line or colon-separated
            input_match = re.search(
                r"input\s*[:=]?\s*['\"]?([^'\"]*)['\"]?(?:\n|output|\s+output)",
                message,
                re.IGNORECASE
            )
            output_match = re.search(
                r"output\s*[:=]?\s*([^\n]+?)(?:\n|$)",
                message,
                re.IGNORECASE
            )

            if input_match and output_match:
                return {
                    "input": input_match.group(1).strip(),
                    "output": output_match.group(1).strip(),
                }

        # Fallback: split by newline and take first two non-empty parts
        lines = [l.strip() for l in message.split("\n") if l.strip()]
        if len(lines) >= 2:
            return {"input": lines[0], "output": lines[1]}

        return None

    def _build_extraction_prompt(self, stage: BuildStage, message: str) -> str:
        """Build a prompt for an LLM worker to help with extraction.

        This prompt can be sent to the classify or extract workers for more
        sophisticated extraction than the deterministic heuristics provide.

        Args:
            stage: Current building stage.
            message: User message to extract from.

        Returns:
            Prompt string for an LLM worker.
        """
        prompts = {
            BuildStage.UNDERSTAND: f"""Extract the capability name and description from this user request:

"{message}"

Output JSON with:
- name: short capability name (snake_case, e.g., ticket_classifier)
- type: one of [classifier, extractor, generator, summarizer, analyzer, workflow]
- description: one-sentence description
""",
            BuildStage.DEFINE_INTENTS: f"""Extract intent patterns from this message:

"{message}"

Output JSON with:
- patterns: list of intent strings the user wants to recognize
- confidence: 0-1 score for how clear the patterns are
""",
            BuildStage.CONFIGURE_WORKERS: f"""Extract worker slot configuration from this message:

"{message}"

Output JSON with:
- slots: list of [classify, extract, verify, summarize, generate, tool_call] the user mentioned
- model_overrides: dict of slot -> model_name for explicit overrides
""",
            BuildStage.SET_SCHEMA: f"""Extract output schema from this description:

"{message}"

Output JSON Schema with properties, types, and enums where relevant.
""",
        }

        return prompts.get(stage, f"Extract structured information: {message}")

    def generate_code(self, session_id: str) -> str:
        """Generate Python source code for the capability.

        Creates a complete, deployable Capability class with all extracted
        configuration baked in.

        Args:
            session_id: Session identifier.

        Returns:
            Python source code string.

        Raises:
            ValueError: If session not found or incomplete.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        if not session.name or not session.intent_patterns:
            raise ValueError("Session incomplete: missing name or intent patterns")

        # Import here to avoid circular dependency
        from agentend.builder.codegen import generate_capability_code

        return generate_capability_code(session)

    def generate_yaml(self, session_id: str) -> str:
        """Generate fleet.yaml additions for the capability.

        Args:
            session_id: Session identifier.

        Returns:
            YAML string with capability registration and slot config.

        Raises:
            ValueError: If session not found.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        from agentend.builder.codegen import generate_fleet_config

        return generate_fleet_config(session)

    async def deploy(self, session_id: str, app: Any) -> bool:
        """Hot-deploy the capability to a running Agentend instance.

        Dynamically registers the generated capability class with the app's
        capability registry so it becomes available immediately without restart.

        Args:
            session_id: Session identifier.
            app: Running Agentend instance with CapabilityRegistry.

        Returns:
            True if deployment succeeded.

        Raises:
            ValueError: If session not found.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        try:
            # Generate code and compile it
            code = self.generate_code(session_id)
            namespace: Dict[str, Any] = {}
            exec(code, namespace)

            # Find the capability class (should be named like TicketClassifier)
            capability_class = None
            for name, obj in namespace.items():
                if isinstance(obj, type) and hasattr(obj, "execute"):
                    capability_class = obj
                    break

            if capability_class is None:
                logger.error("Generated code did not produce a capability class")
                return False

            # Register with the app's capability registry
            if hasattr(app, "capabilities"):
                instance = capability_class()
                cap_name = getattr(instance, "name", session.name)
                app.capabilities[cap_name] = instance
                session.status = "deployed"
                logger.info(f"Deployed capability: {cap_name}")
                return True

            return False

        except Exception as e:
            logger.error(f"Deployment failed: {e}", exc_info=True)
            return False

    def export(self, session_id: str, path: str) -> None:
        """Save capability code to disk as a .py file.

        Args:
            session_id: Session identifier.
            path: File path to save to (e.g., '/path/to/my_capability.py').

        Raises:
            ValueError: If session not found.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        code = self.generate_code(session_id)

        from pathlib import Path

        Path(path).write_text(code)
        logger.info(f"Exported capability to: {path}")
