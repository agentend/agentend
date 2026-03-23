"""
Text summarization worker with configurable length.
"""

from dataclasses import dataclass
from typing import Any, Optional
from agentend.fleet.worker import BaseWorker, WorkerConfig


@dataclass
class SummaryResult:
    """Result of text summarization."""

    summary: str
    """Generated summary text."""

    original_length: int
    """Length of original text."""

    summary_length: int
    """Length of summary."""

    compression_ratio: float
    """Ratio of original to summary length."""


class SummarizeWorker(BaseWorker):
    """
    Worker for text summarization.

    Supports configurable summary length and style (bullet points, prose, etc.).
    """

    def __init__(
        self,
        config: Optional[WorkerConfig] = None,
        summary_style: str = "prose",
    ) -> None:
        """
        Initialize the summarize worker.

        Args:
            config: WorkerConfig for model selection.
            summary_style: Style of summary ('prose', 'bullets', 'key_points').
        """
        if config is None:
            config = WorkerConfig(
                model="gpt-4",
                temperature=0.5,
                max_tokens=500,
            )

        super().__init__(
            config=config,
            name="summarize",
            input_type=str,
            output_type=SummaryResult,
        )
        self.summary_style = summary_style

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> SummaryResult:
        """
        Summarize text.

        Args:
            context: Optional request context.
            **kwargs: Must include 'text' key. Can include 'length' (short/medium/long).

        Returns:
            SummaryResult with summary and metrics.
        """
        text = kwargs.get("text", "")
        length = kwargs.get("length", "medium")

        if not text:
            return SummaryResult(
                summary="",
                original_length=0,
                summary_length=0,
                compression_ratio=0.0,
            )

        # Map length to token count
        length_map = {
            "short": "50-100 words",
            "medium": "150-250 words",
            "long": "400-600 words",
        }
        target_length = length_map.get(length, "150-250 words")

        # Build summarization prompt
        style_instructions = {
            "prose": "Write as a coherent paragraph.",
            "bullets": "Format as bullet points.",
            "key_points": "List the key points in order of importance.",
        }
        style = style_instructions.get(self.summary_style, "Write as a coherent paragraph.")

        prompt = f"""Summarize the following text in {target_length}. {style}

Text:
{text}

Summary:"""

        response = await super().execute(context, prompt=prompt, **{
            k: v for k, v in kwargs.items() if k not in ("text", "length", "prompt")
        })

        summary = response.strip() if isinstance(response, str) else str(response)
        original_len = len(text.split())
        summary_len = len(summary.split())

        compression = (
            original_len / summary_len if summary_len > 0 else 0.0
        )

        return SummaryResult(
            summary=summary,
            original_length=original_len,
            summary_length=summary_len,
            compression_ratio=compression,
        )
