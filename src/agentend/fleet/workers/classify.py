"""
Intent classification worker using small, efficient models.
"""

from dataclasses import dataclass
from typing import Any, Optional
from agentend.fleet.worker import BaseWorker, WorkerConfig


@dataclass
class ClassificationResult:
    """Result of intent classification."""

    label: str
    """The classified intent label."""

    confidence: float
    """Confidence score (0.0 to 1.0)."""

    scores: dict[str, float] = None
    """Per-label confidence scores if available."""

    def __post_init__(self) -> None:
        """Initialize default scores."""
        if self.scores is None:
            self.scores = {self.label: self.confidence}


class ClassifyWorker(BaseWorker):
    """
    Worker for intent classification.

    Uses small, fast models (e.g., distilbert, fasttext) to classify
    user intents into predefined categories with confidence scores.
    """

    def __init__(
        self,
        config: Optional[WorkerConfig] = None,
        categories: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize the classify worker.

        Args:
            config: WorkerConfig. Defaults to a small, fast model.
            categories: Optional list of intent categories to classify into.
        """
        if config is None:
            config = WorkerConfig(
                model="gpt-3.5-turbo",
                temperature=0.0,
                max_tokens=50,
            )

        super().__init__(
            config=config,
            name="classify",
            input_type=str,
            output_type=ClassificationResult,
        )
        self.categories = categories or [
            "search",
            "generate",
            "analyze",
            "extract",
            "summarize",
            "other",
        ]

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> ClassificationResult:
        """
        Classify the intent.

        Args:
            context: Optional request context.
            **kwargs: Must include 'intent' key with the text to classify.

        Returns:
            ClassificationResult with label and confidence.
        """
        intent = kwargs.get("intent", "")
        if not intent:
            return ClassificationResult(label="other", confidence=0.0)

        # Build classification prompt
        categories_str = ", ".join(self.categories)
        prompt = f"""Classify the following intent into one of these categories: {categories_str}

Intent: {intent}

Respond with ONLY the category name and a confidence score (0-100) in format: "CATEGORY: CONFIDENCE"
Example: "search: 95"
"""

        response = await super().execute(
            context, prompt=prompt, **{
                k: v
                for k, v in kwargs.items()
                if k not in ("intent", "prompt")
            }
        )

        return self._parse_classification(response)

    def _parse_classification(self, response: str) -> ClassificationResult:
        """
        Parse model response into ClassificationResult.

        Args:
            response: Model response string.

        Returns:
            Parsed ClassificationResult.
        """
        try:
            # Try to parse "CATEGORY: CONFIDENCE" format
            if ":" in response:
                parts = response.split(":")
                label = parts[0].strip().lower()
                confidence_str = parts[1].strip().rstrip("%").strip()
                confidence = float(confidence_str) / 100.0
            else:
                # Fallback: treat response as category
                label = response.strip().lower()
                confidence = 0.8

            # Validate category
            if label not in [c.lower() for c in self.categories]:
                label = "other"
                confidence = 0.5

            return ClassificationResult(
                label=label,
                confidence=min(confidence, 1.0),
                scores={label: confidence},
            )

        except (ValueError, IndexError):
            return ClassificationResult(label="other", confidence=0.0)
