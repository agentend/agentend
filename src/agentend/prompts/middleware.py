"""Prompt middleware chain for processing and augmentation."""

from typing import Optional, List
from abc import ABC, abstractmethod


class PromptMiddleware(ABC):
    """Base class for prompt processing middleware."""

    @abstractmethod
    async def process(self, prompt: str) -> str:
        """
        Process prompt and return modified version.

        Args:
            prompt: Input prompt.

        Returns:
            Processed prompt.
        """
        pass


class SafetyLayer(PromptMiddleware):
    """Safety checks and injection prevention."""

    async def process(self, prompt: str) -> str:
        """Check for safety issues."""
        from agentend.security.sanitizer import InputSanitizer

        sanitizer = InputSanitizer(allow_html=False, allow_sql=False)
        try:
            return sanitizer.sanitize(prompt)
        except ValueError:
            # If sanitization fails, return original
            # (safety layer lets legitimate prompts through)
            return prompt


class DomainLayer(PromptMiddleware):
    """Add domain-specific context and constraints."""

    def __init__(self, domain: str, context: Optional[str] = None):
        """
        Initialize domain layer.

        Args:
            domain: Domain name (e.g., "medical", "finance").
            context: Optional domain context.
        """
        self.domain = domain
        self.context = context

    async def process(self, prompt: str) -> str:
        """Add domain context."""
        domain_header = f"[Domain: {self.domain}]"

        if self.context:
            domain_header += f"\n{self.context}"

        return f"{domain_header}\n\n{prompt}"


class ContextLayer(PromptMiddleware):
    """Inject user context and metadata."""

    def __init__(self, context: dict):
        """
        Initialize context layer.

        Args:
            context: Context dictionary.
        """
        self.context = context

    async def process(self, prompt: str) -> str:
        """Add context information."""
        user_id = self.context.get("user_id")
        session_id = self.context.get("session_id")
        request_id = self.context.get("request_id")

        context_str = "[Context]\n"
        if user_id:
            context_str += f"User: {user_id}\n"
        if session_id:
            context_str += f"Session: {session_id}\n"
        if request_id:
            context_str += f"Request: {request_id}\n"

        return f"{context_str}\n{prompt}"


class FormatLayer(PromptMiddleware):
    """Ensure proper output formatting."""

    def __init__(self, output_format: str):
        """
        Initialize format layer.

        Args:
            output_format: Expected output format.
        """
        self.output_format = output_format

    async def process(self, prompt: str) -> str:
        """Add format instructions."""
        format_instruction = f"\n\nRespond in the following format:\n{self.output_format}"
        return prompt + format_instruction


class TruncationLayer(PromptMiddleware):
    """Truncate prompt to token budget."""

    def __init__(self, max_tokens: int):
        """
        Initialize truncation layer.

        Args:
            max_tokens: Maximum tokens allowed.
        """
        self.max_tokens = max_tokens

    async def process(self, prompt: str) -> str:
        """Truncate prompt if needed."""
        from agentend.prompts.truncation import PromptTruncation

        truncator = PromptTruncation(self.max_tokens)
        return truncator.truncate(prompt)


class PromptMiddlewareChain:
    """Chain of middleware for processing prompts."""

    def __init__(self):
        """Initialize middleware chain."""
        self.middlewares: List[PromptMiddleware] = []

    def add(self, middleware: PromptMiddleware) -> "PromptMiddlewareChain":
        """
        Add middleware to chain.

        Args:
            middleware: Middleware to add.

        Returns:
            Self for chaining.
        """
        self.middlewares.append(middleware)
        return self

    async def process(self, prompt: str) -> str:
        """
        Process prompt through all middleware.

        Args:
            prompt: Input prompt.

        Returns:
            Processed prompt.
        """
        result = prompt

        for middleware in self.middlewares:
            result = await middleware.process(result)

        return result

    @staticmethod
    def create_default_chain(
        domain: Optional[str] = None,
        max_tokens: int = 4000,
    ) -> "PromptMiddlewareChain":
        """
        Create default middleware chain.

        Args:
            domain: Optional domain for context.
            max_tokens: Maximum tokens.

        Returns:
            Configured chain.
        """
        chain = PromptMiddlewareChain()

        # Safety first
        chain.add(SafetyLayer())

        # Add domain context if specified
        if domain:
            chain.add(DomainLayer(domain))

        # Format instructions
        chain.add(FormatLayer("JSON\nJSON format: {\"result\": \"...\"}"))

        # Truncate to budget
        chain.add(TruncationLayer(max_tokens))

        return chain
