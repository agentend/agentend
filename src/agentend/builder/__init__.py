"""
Conversational Capability Builder.

Allows users to create, modify, and deploy business logic capabilities
through natural language conversation with the Agentend framework.

The builder orchestrates a multi-stage conversation to:
1. Understand what capability the user wants
2. Define intent patterns for routing
3. Configure worker slots and model preferences
4. Design the prompt template using Template Method pattern
5. Set output schema and validation rules
6. Collect few-shot examples
7. Review and confirm the specification

Once complete, the builder can:
- Generate clean, production-quality Python code
- Create fleet.yaml configuration additions
- Hot-deploy to a running Agentend instance
- Export to disk for version control

Example Usage:
    from agentend.builder import CapabilityBuilder

    builder = CapabilityBuilder()
    session = builder.new_session()

    # Describe what you want
    result = await builder.process_message(session.session_id,
        "I need a capability that classifies support tickets by urgency and department")

    # Respond to builder questions
    result = await builder.process_message(session.session_id,
        "Urgencies are: critical, high, medium, low. Departments are: billing, technical, general")

    # Generate code when ready
    code = builder.generate_code(session.session_id)
    print(code)

    # Or deploy directly
    success = await builder.deploy(session.session_id, app)

Templates:
    Users can also start from pre-built templates for common patterns:
    - ticket_classifier: Classify support tickets
    - data_extractor: Extract structured data from text
    - content_generator: Generate marketing/technical content
    - summarizer: Summarize long documents
    - sentiment_analyzer: Analyze sentiment in feedback
    - qa_bot: Answer questions from knowledge base
    - workflow_router: Route requests to workflows

No External Dependencies:
    The builder uses pure Python (dataclasses, typing, uuid, datetime, json).
    It does NOT use Jinja2 or other template engines for code generation,
    keeping the framework lean and dependency-free.
"""

from agentend.builder.builder import (
    CapabilityBuilder,
    BuilderSession,
    BuilderResponse,
    BuildStage,
)
from agentend.builder.templates import (
    CapabilityTemplate,
    TEMPLATES,
    TICKET_CLASSIFIER,
    DATA_EXTRACTOR,
    CONTENT_GENERATOR,
    SUMMARIZER,
    SENTIMENT_ANALYZER,
    QA_BOT,
    WORKFLOW_ROUTER,
)
from agentend.builder.codegen import (
    generate_capability_code,
    generate_test_code,
    generate_fleet_config,
)

__all__ = [
    # Core builder classes
    "CapabilityBuilder",
    "BuilderSession",
    "BuilderResponse",
    "BuildStage",
    # Templates
    "CapabilityTemplate",
    "TEMPLATES",
    "TICKET_CLASSIFIER",
    "DATA_EXTRACTOR",
    "CONTENT_GENERATOR",
    "SUMMARIZER",
    "SENTIMENT_ANALYZER",
    "QA_BOT",
    "WORKFLOW_ROUTER",
    # Code generation functions
    "generate_capability_code",
    "generate_test_code",
    "generate_fleet_config",
]
