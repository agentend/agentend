"""
Structured data extraction worker using Instructor + Pydantic.
"""

from dataclasses import dataclass
from typing import Any, Optional, Type
from agentend.fleet.worker import BaseWorker, WorkerConfig


@dataclass
class ExtractionResult:
    """Result of structured data extraction."""

    data: dict[str, Any]
    """Extracted structured data."""

    model: str
    """Model used for extraction."""

    prompt_tokens: Optional[int] = None
    """Number of input tokens."""

    completion_tokens: Optional[int] = None
    """Number of output tokens."""


class ExtractWorker(BaseWorker):
    """
    Worker for structured data extraction.

    Uses Instructor library with Pydantic models to guarantee
    structured, valid output from language models.
    """

    def __init__(
        self,
        config: Optional[WorkerConfig] = None,
        output_schema: Optional[Type] = None,
    ) -> None:
        """
        Initialize the extract worker.

        Args:
            config: WorkerConfig for model selection.
            output_schema: Pydantic model class for output validation.
        """
        if config is None:
            config = WorkerConfig(
                model="gpt-4",
                temperature=0.0,
                max_tokens=2000,
            )

        super().__init__(
            config=config,
            name="extract",
            input_type=str,
            output_type=ExtractionResult,
        )
        self.output_schema = output_schema

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> ExtractionResult:
        """
        Extract structured data from text.

        Args:
            context: Optional request context.
            **kwargs: Must include 'text' key with content to extract from.

        Returns:
            ExtractionResult with validated structured data.
        """
        text = kwargs.get("text", "")
        if not text:
            return ExtractionResult(data={}, model=self.config.model)

        # Build extraction prompt
        schema_desc = "structured data"
        if self.output_schema:
            schema_desc = self.output_schema.__name__

        prompt = f"""Extract structured {schema_desc} from the following text:

Text:
{text}

Return valid JSON that matches the required schema."""

        response = await super().execute(
            context, prompt=prompt, **{
                k: v for k, v in kwargs.items() if k not in ("text", "prompt")
            }
        )

        return self._parse_extraction(response)

    def _parse_extraction(self, response: str) -> ExtractionResult:
        """
        Parse model response into ExtractionResult.

        Args:
            response: Model response (should be JSON).

        Returns:
            ExtractionResult with parsed data.
        """
        try:
            import json

            # Try to extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                # Validate against schema if provided
                if self.output_schema:
                    try:
                        validated = self.output_schema(**data)
                        data = validated.dict() if hasattr(validated, "dict") else vars(validated)
                    except Exception:
                        pass

                return ExtractionResult(
                    data=data,
                    model=self.config.model,
                )

            return ExtractionResult(data={}, model=self.config.model)

        except Exception:
            return ExtractionResult(data={}, model=self.config.model)
