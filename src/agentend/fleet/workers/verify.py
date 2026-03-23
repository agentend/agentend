"""
Cross-reference verification worker for validating extracted data.
"""

from dataclasses import dataclass
from typing import Any, Optional
from agentend.fleet.worker import BaseWorker, WorkerConfig


@dataclass
class VerificationResult:
    """Result of data verification."""

    verified: bool
    """Whether data passed verification."""

    confidence: float
    """Verification confidence (0.0 to 1.0)."""

    issues: list[str] = None
    """List of detected inconsistencies or issues."""

    def __post_init__(self) -> None:
        """Initialize default issues list."""
        if self.issues is None:
            self.issues = []


class VerifyWorker(BaseWorker):
    """
    Worker for cross-reference verification.

    Takes extracted data and source material to verify consistency,
    accuracy, and logical coherence.
    """

    def __init__(self, config: Optional[WorkerConfig] = None) -> None:
        """
        Initialize the verify worker.

        Args:
            config: WorkerConfig for model selection.
        """
        if config is None:
            config = WorkerConfig(
                model="gpt-4",
                temperature=0.0,
                max_tokens=500,
            )

        super().__init__(
            config=config,
            name="verify",
            input_type=dict,
            output_type=VerificationResult,
        )

    async def execute(
        self, context: Optional[Any] = None, **kwargs: Any
    ) -> VerificationResult:
        """
        Verify extracted data against source.

        Args:
            context: Optional request context.
            **kwargs: Must include 'data' and 'source' keys.

        Returns:
            VerificationResult with verification status.
        """
        data = kwargs.get("data")
        source = kwargs.get("source", "")

        if not data or not source:
            return VerificationResult(verified=False, confidence=0.0)

        # Build verification prompt
        data_str = str(data) if not isinstance(data, str) else data

        prompt = f"""Verify that the following extracted data is accurate and consistent with the source text.

Source Text:
{source}

Extracted Data:
{data_str}

Respond with JSON format:
{{
  "verified": true/false,
  "confidence": 0.0-1.0,
  "issues": ["issue1", "issue2", ...]
}}

Be strict about accuracy and consistency."""

        response = await super().execute(context, prompt=prompt, **{
            k: v for k, v in kwargs.items() if k not in ("data", "source", "prompt")
        })

        return self._parse_verification(response)

    def _parse_verification(self, response: str) -> VerificationResult:
        """
        Parse model response into VerificationResult.

        Args:
            response: Model response (should be JSON).

        Returns:
            VerificationResult with parsed data.
        """
        try:
            import json

            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                return VerificationResult(
                    verified=data.get("verified", False),
                    confidence=float(data.get("confidence", 0.0)),
                    issues=data.get("issues", []),
                )

            return VerificationResult(verified=False, confidence=0.0)

        except Exception:
            return VerificationResult(verified=False, confidence=0.0)
