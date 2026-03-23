"""
Worker protocol and base implementation for executing tasks.
"""

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Protocol, Type
import logging

logger = logging.getLogger(__name__)


class Worker(Protocol):
    """Protocol defining a worker that executes tasks."""

    input_type: Type
    """Type of input the worker accepts."""

    output_type: Type
    """Type of output the worker produces."""

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> Any:
        """
        Execute the worker with given inputs.

        Args:
            context: Optional request context.
            **kwargs: Worker-specific inputs.

        Returns:
            Result of worker execution.
        """
        ...


@dataclass
class WorkerConfig:
    """Configuration for a worker."""

    model: str
    """LLM model to use (e.g., 'gpt-4', 'claude-3-opus')."""

    backend: str = "litellm"
    """Backend to use ('litellm', 'openai', 'anthropic', etc.)."""

    temperature: float = 0.7
    """Sampling temperature (0.0 to 2.0)."""

    max_tokens: Optional[int] = None
    """Maximum tokens in response."""

    fallback: Optional[str] = None
    """Fallback model if primary fails."""

    routing: Optional[Dict[str, Any]] = None
    """Routing configuration for smart routing (e.g., RouteLLM settings)."""

    routing_threshold: float = 0.5
    """Threshold for routing decisions (0.0 to 1.0)."""

    extra_params: Dict[str, Any] = field(default_factory=dict)
    """Additional model-specific parameters."""

    def override(self, **kwargs: Any) -> "WorkerConfig":
        """
        Create a new config with overrides applied.

        Args:
            **kwargs: Fields to override.

        Returns:
            New WorkerConfig with merged values.
        """
        import dataclasses

        updates = {k: v for k, v in kwargs.items() if v is not None}
        return dataclasses.replace(self, **updates)


class BaseWorker:
    """
    Base implementation of a worker using LiteLLM backend.

    Handles message formatting, model calls, streaming, and fallback logic.
    """

    def __init__(
        self,
        config: WorkerConfig,
        name: str = "base_worker",
        input_type: Type = str,
        output_type: Type = str,
    ) -> None:
        """
        Initialize the worker.

        Args:
            config: WorkerConfig with model and backend settings.
            name: Name of the worker.
            input_type: Type of input accepted.
            output_type: Type of output produced.
        """
        self.config = config
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self._backend = None

    @property
    def backend(self) -> Any:
        """Get or initialize the backend (lazy loading)."""
        if self._backend is None:
            from agentend.fleet.backends.litellm import LiteLLMBackend

            self._backend = LiteLLMBackend()
        return self._backend

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> Any:
        """
        Execute the worker with given inputs.

        Applies 3-level config override resolution:
        1. Global defaults (WorkerConfig)
        2. Per-slot context overrides
        3. Per-request kwargs

        Args:
            context: Optional request context.
            **kwargs: Worker-specific inputs and config overrides.

        Returns:
            Worker output.
        """
        # Extract config overrides from kwargs
        model = kwargs.pop("model", self.config.model)
        temperature = kwargs.pop("temperature", self.config.temperature)
        max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
        backend = kwargs.pop("backend", self.config.backend)

        # Build messages from kwargs
        messages = self._build_messages(context, **kwargs)

        # Prepare backend options
        options = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if self.config.routing:
            options["routing"] = self.config.routing
            options["routing_threshold"] = self.config.routing_threshold

        # Add extra params
        options.update(self.config.extra_params)

        try:
            # Execute with backend
            response = await self.backend.complete(messages=messages, **options)
            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Worker {self.name} execution failed: {e}")

            if self.config.fallback:
                logger.info(f"Attempting fallback model: {self.config.fallback}")
                options["model"] = self.config.fallback
                try:
                    response = await self.backend.complete(
                        messages=messages, **options
                    )
                    return self._parse_response(response)
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback model also failed: {fallback_error}"
                    )
                    raise

            raise

    async def stream(
        self,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream output from the worker.

        Yields tokens as they are produced by the backend.

        Args:
            context: Optional request context.
            **kwargs: Worker-specific inputs and config overrides.

        Yields:
            Response tokens.
        """
        # Extract config overrides
        model = kwargs.pop("model", self.config.model)
        temperature = kwargs.pop("temperature", self.config.temperature)
        max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)

        # Build messages
        messages = self._build_messages(context, **kwargs)

        # Prepare backend options
        options = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        options.update(self.config.extra_params)

        try:
            async for chunk in self.backend.stream(messages=messages, **options):
                yield chunk
        except Exception as e:
            logger.error(f"Stream failed: {e}")
            raise

    def _build_messages(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> list[Dict[str, str]]:
        """
        Build message list for the backend.

        Args:
            context: Optional request context with existing messages.
            **kwargs: Additional inputs to format into messages.

        Returns:
            List of message dicts with 'role' and 'content'.
        """
        messages = []

        # Include context messages if available
        if context and hasattr(context, "messages"):
            messages.extend(context.messages)

        # Format kwargs as user message
        if kwargs:
            content_parts = []
            for key, value in kwargs.items():
                if key not in ("model", "temperature", "max_tokens", "backend"):
                    content_parts.append(f"{key}: {value}")

            if content_parts:
                messages.append(
                    {"role": "user", "content": "\n".join(content_parts)}
                )

        return messages if messages else [{"role": "user", "content": ""}]

    def _parse_response(self, response: Any) -> Any:
        """
        Parse backend response.

        Args:
            response: Response from backend.

        Returns:
            Parsed response content.
        """
        if isinstance(response, dict):
            return response.get("content", response)
        elif isinstance(response, str):
            return response
        else:
            return response
