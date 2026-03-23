"""
Pre-built capability templates for the builder.

Templates provide starting points for common capability patterns:
classification, extraction, generation, analysis, and workflow.
Users can start from a template and customize via conversation.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CapabilityTemplate:
    """Template for a reusable capability pattern."""

    name: str
    """Machine name of the template (e.g., 'ticket_classifier')."""

    description: str
    """Human-readable description of what this template does."""

    category: str
    """Category: classification, extraction, generation, analysis, workflow, qa."""

    intent_patterns: List[str]
    """Example intent patterns that would trigger this capability."""

    worker_slots: Dict[str, str]
    """Recommended worker slots and models (slot -> model name)."""

    prompt_template: str
    """Jinja2-style prompt template with {{ slot }} placeholders."""

    output_schema: Dict[str, Any]
    """JSON Schema for output validation."""

    examples: List[Dict[str, str]]
    """Few-shot examples as {input, output} pairs."""


# Template 1: Ticket Classification
TICKET_CLASSIFIER = CapabilityTemplate(
    name="ticket_classifier",
    description="Classify support tickets by urgency and department",
    category="classification",
    intent_patterns=[
        "classify ticket",
        "categorize support request",
        "triage ticket",
        "sort by urgency",
        "assign to department",
    ],
    worker_slots={"classify": "gpt-3.5-turbo"},
    prompt_template="""You are a support ticket classifier.

Ticket content:
{{ context }}

Your task: Classify this ticket by:
1. Urgency level: critical, high, medium, or low
2. Department: billing, technical, general, or other

Rules:
{{ validation_rules }}

Respond with JSON:
{
  "urgency": "high",
  "department": "technical",
  "confidence": 0.95,
  "reasoning": "brief explanation"
}""",
    output_schema={
        "type": "object",
        "properties": {
            "urgency": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
            },
            "department": {
                "type": "string",
                "enum": ["billing", "technical", "general", "other"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
        },
        "required": ["urgency", "department", "confidence"],
    },
    examples=[
        {
            "input": "My payment failed and I can't access my account. This is urgent!",
            "output": '{"urgency": "critical", "department": "billing", "confidence": 0.99, "reasoning": "Payment failure blocks account access"}',
        },
        {
            "input": "Can you explain the difference between plans A and B?",
            "output": '{"urgency": "low", "department": "general", "confidence": 0.87, "reasoning": "Informational question about plans"}',
        },
        {
            "input": "API keeps returning 500 errors on POST /users endpoint",
            "output": '{"urgency": "high", "department": "technical", "confidence": 0.96, "reasoning": "Service outage affecting users"}',
        },
    ],
)


# Template 2: Data Extraction
DATA_EXTRACTOR = CapabilityTemplate(
    name="data_extractor",
    description="Extract structured data from unstructured text",
    category="extraction",
    intent_patterns=[
        "extract data",
        "parse information",
        "pull fields",
        "extract entities",
        "get details from",
    ],
    worker_slots={"extract": "gpt-3.5-turbo"},
    prompt_template="""You are a data extraction specialist.

Text to process:
{{ context }}

Extract the following fields:
{{ validation_rules }}

Rules:
- Return ONLY found values, use null for missing fields
- Dates should be ISO 8601 format (YYYY-MM-DD)
- Prices should be numbers without currency symbols
- Emails and URLs should be normalized

Respond with JSON matching the schema:
{{ examples }}""",
    output_schema={
        "type": "object",
        "properties": {
            "name": {"type": ["string", "null"]},
            "email": {"type": ["string", "null"], "format": "email"},
            "phone": {"type": ["string", "null"]},
            "company": {"type": ["string", "null"]},
            "date": {"type": ["string", "null"], "format": "date"},
            "amount": {"type": ["number", "null"]},
        },
        "required": ["name", "email"],
    },
    examples=[
        {
            "input": "John Smith from Acme Corp called today (2026-03-23). He wants to discuss a $50,000 contract. His email is john@acme.com",
            "output": '{"name": "John Smith", "email": "john@acme.com", "phone": null, "company": "Acme Corp", "date": "2026-03-23", "amount": 50000}',
        },
        {
            "input": "Contact: alice.johnson@techcorp.io, works at TechCorp",
            "output": '{"name": "Alice Johnson", "email": "alice.johnson@techcorp.io", "phone": null, "company": "TechCorp", "date": null, "amount": null}',
        },
    ],
)


# Template 3: Content Generation
CONTENT_GENERATOR = CapabilityTemplate(
    name="content_generator",
    description="Generate marketing or technical content from outlines",
    category="generation",
    intent_patterns=[
        "generate content",
        "write description",
        "create copy",
        "draft email",
        "expand outline",
        "compose message",
    ],
    worker_slots={"generate": "gpt-3.5-turbo"},
    prompt_template="""You are a professional content writer.

Outline or request:
{{ context }}

Your task: Generate engaging, professional content that:
- Matches the tone and style requested
- Includes key points from the outline
- Is optimized for the target audience

Guidelines:
{{ validation_rules }}

Generate the content now:""",
    output_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "minLength": 10},
            "word_count": {"type": "integer"},
            "tone": {"type": "string", "enum": ["professional", "casual", "technical", "sales"]},
        },
        "required": ["content", "word_count"],
    },
    examples=[
        {
            "input": "Outline:\n- Product solves problem X\n- 3x faster than competitors\n- Enterprise ready\nTone: professional",
            "output": '{"content": "Introducing our revolutionary solution that cuts processing time by 66% and scales to enterprise demands. Built for teams that refuse to compromise on speed or reliability.", "word_count": 27, "tone": "professional"}',
        },
    ],
)


# Template 4: Text Summarization
SUMMARIZER = CapabilityTemplate(
    name="summarizer",
    description="Summarize long texts into concise overviews",
    category="analysis",
    intent_patterns=[
        "summarize",
        "condense",
        "create brief",
        "executive summary",
        "tl;dr",
        "key points",
    ],
    worker_slots={"summarize": "gpt-3.5-turbo"},
    prompt_template="""You are a skilled technical summarizer.

Document:
{{ context }}

Create a summary that:
- Captures key points concisely
- Preserves critical details
- Is 25-50% of original length
- Is scannable with clear structure

Rules:
{{ validation_rules }}

Respond with JSON:
{
  "summary": "...",
  "key_points": ["point1", "point2", ...],
  "word_count": N
}""",
    output_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "word_count": {"type": "integer"},
        },
        "required": ["summary", "key_points"],
    },
    examples=[
        {
            "input": "The new regulatory framework requires all companies to implement multi-factor authentication by Q4 2026. Failure to comply results in fines up to $10,000 per incident. The requirement applies to all systems handling customer data...",
            "output": '{"summary": "New regulation requires MFA implementation by Q4 2026 with fines up to $10k per incident for non-compliance on customer data systems.", "key_points": ["MFA required by Q4 2026", "Fines up to $10k per incident", "Applies to customer data systems"], "word_count": 28}',
        },
    ],
)


# Template 5: Sentiment Analysis
SENTIMENT_ANALYZER = CapabilityTemplate(
    name="sentiment_analyzer",
    description="Analyze sentiment and emotions in customer feedback",
    category="analysis",
    intent_patterns=[
        "analyze sentiment",
        "detect emotion",
        "customer satisfaction",
        "sentiment score",
        "feedback analysis",
    ],
    worker_slots={"classify": "gpt-3.5-turbo"},
    prompt_template="""You are a sentiment analysis expert.

Text to analyze:
{{ context }}

Analyze the sentiment and emotions present.

Rules:
- Sentiment: positive, negative, neutral
- Intensity: 0-10 scale
- Emotions: list detected emotions (happiness, anger, frustration, etc.)

Respond with JSON:
{
  "sentiment": "positive",
  "intensity": 8,
  "emotions": ["happiness", "enthusiasm"],
  "confidence": 0.92
}""",
    output_schema={
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "mixed"],
            },
            "intensity": {"type": "integer", "minimum": 0, "maximum": 10},
            "emotions": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["sentiment", "intensity", "confidence"],
    },
    examples=[
        {
            "input": "I absolutely love your product! It transformed how our team works and saved us countless hours.",
            "output": '{"sentiment": "positive", "intensity": 9, "emotions": ["happiness", "enthusiasm", "gratitude"], "confidence": 0.98}',
        },
        {
            "input": "The service went down for 2 hours yesterday. This is unacceptable.",
            "output": '{"sentiment": "negative", "intensity": 7, "emotions": ["anger", "frustration"], "confidence": 0.94}',
        },
    ],
)


# Template 6: Q&A Bot
QA_BOT = CapabilityTemplate(
    name="qa_bot",
    description="Answer questions based on provided knowledge base or context",
    category="qa",
    intent_patterns=[
        "answer question",
        "respond to query",
        "knowledge lookup",
        "help with",
        "how do I",
        "what is",
    ],
    worker_slots={"generate": "gpt-3.5-turbo"},
    prompt_template="""You are a helpful customer support assistant.

Knowledge Base:
{{ context }}

User Question:
{{ input }}

Respond with:
1. A direct, helpful answer
2. Confidence level (0-1) that you answered correctly
3. If uncertain, explain what additional info you'd need

Rules:
{{ validation_rules }}

Respond with JSON:
{
  "answer": "...",
  "confidence": 0.85,
  "sources": ["source1", "source2"],
  "follow_up": "suggested next question or action"
}""",
    output_schema={
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "sources": {"type": "array", "items": {"type": "string"}},
            "follow_up": {"type": ["string", "null"]},
        },
        "required": ["answer", "confidence"],
    },
    examples=[
        {
            "input": "What are your business hours?",
            "output": '{"answer": "We are open Monday-Friday 9am-6pm EST, Saturday 10am-4pm EST, and closed Sundays.", "confidence": 0.99, "sources": ["hours_page"], "follow_up": null}',
        },
    ],
)


# Template 7: Workflow Router
WORKFLOW_ROUTER = CapabilityTemplate(
    name="workflow_router",
    description="Route requests to appropriate workflows or teams",
    category="workflow",
    intent_patterns=[
        "route request",
        "handle workflow",
        "assign task",
        "escalate",
        "next step",
    ],
    worker_slots={"classify": "gpt-3.5-turbo", "verify": "gpt-3.5-turbo"},
    prompt_template="""You are a workflow routing system.

Request details:
{{ context }}

Available workflows:
{{ validation_rules }}

Determine which workflow this should route to based on:
1. Request type and urgency
2. Required expertise
3. Workflow capacity

Respond with JSON:
{
  "workflow": "name",
  "priority": "high",
  "reason": "brief explanation",
  "requires_human_review": false
}""",
    output_schema={
        "type": "object",
        "properties": {
            "workflow": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "reason": {"type": "string"},
            "requires_human_review": {"type": "boolean"},
        },
        "required": ["workflow", "priority"],
    },
    examples=[
        {
            "input": "Enterprise customer reports complete service outage affecting 10,000+ users",
            "output": '{"workflow": "critical_incident", "priority": "critical", "reason": "Service-wide outage at scale", "requires_human_review": true}',
        },
    ],
)


TEMPLATES: Dict[str, CapabilityTemplate] = {
    "ticket_classifier": TICKET_CLASSIFIER,
    "data_extractor": DATA_EXTRACTOR,
    "content_generator": CONTENT_GENERATOR,
    "summarizer": SUMMARIZER,
    "sentiment_analyzer": SENTIMENT_ANALYZER,
    "qa_bot": QA_BOT,
    "workflow_router": WORKFLOW_ROUTER,
}
