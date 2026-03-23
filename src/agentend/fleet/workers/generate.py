"""
General text generation worker with streaming support.
"""

from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional
from agentend.fleet.worker import BaseWorker, WorkerConfig


@dataclass
class GenerationResult:
    """Result of text generation."""

    content: str
    """Generated text content."""

    model: str
    """Model used for generation."""

    tokens: Optional[int] = None
    """Number of tokens in completion."""


class GenerateWorker(BaseWorker):
    """
    Worker for general text generation.

    Supports both regular and streaming generation for flexible
    output handling in agent pipelines.
    """

    def __init__(self, config: Optional[WorkerConfig] = None) -> None:
        """
        Initialize the generate worker.

        Args:
            config: WorkerConfig for model selection.
        """
        if config is None:
            config = WorkerConfig(
                model="gpt-4",
                temperature=0.7,
                max_tokens=2000,
            )

        super().__init__(
            config=config,
            name="generate",
            input_type=str,
            output_type=GenerationResult,
        )

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> GenerationResult:
        """
        Generate text.

        Args:
            context: Optional request context.
            **kwargs: Can include 'prompt' or 'intent' key with generation request.

        Returns:
            GenerationResult with generated content.
        """
        prompt = kwargs.get("prompt") or kwargs.get("intent", "")
        if not prompt:
            return GenerationResult(content="", model=self.config.model)

        response = await super().execute(context, prompt=prompt, **{
            k: v for k, v in kwargs.items() if k not in ("prompt", "intent")
        })

        return GenerationResult(
            content=response,
            model=self.config.model,
        )

    async def stream(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        Stream generated text token by token.

        Args:
            context: Optional request context.
            **kwargs: Can include 'prompt' or 'intent' key.

        Yields:
            Generated tokens as they are produced.
        """
        prompt = kwargs.get("prompt") or kwargs.get("intent", "")
        if not prompt:
            return

        async for token in super().stream(context, prompt=prompt, **{
            k: v for k, v in kwargs.items() if k not in ("prompt", "intent")
        }):
            yield token
