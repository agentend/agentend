"""
Intent routing using classification and semantic similarity.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of intent routing decision."""

    capability_name: str
    """Name of the capability to route to."""

    confidence: float
    """Confidence score (0.0 to 1.0) of the routing decision."""

    metadata: Dict[str, Any]
    """Additional metadata about the routing decision."""

    routing_method: str = "classifier"
    """Method used for routing: 'classifier' or 'semantic'."""


class IntentRouter:
    """
    Routes user intents to appropriate capabilities.

    Uses a classify worker for intent classification, with fallback to
    embedding-based semantic similarity if classification fails.
    """

    def __init__(
        self,
        classify_worker: Optional[Any] = None,
        embedding_model: Optional[Any] = None,
        fallback_capability: str = "generate",
    ) -> None:
        """
        Initialize the intent router.

        Args:
            classify_worker: Worker that performs intent classification.
            embedding_model: Model for semantic similarity (fallback).
            fallback_capability: Default capability if routing fails.
        """
        self.classify_worker = classify_worker
        self.embedding_model = embedding_model
        self.fallback_capability = fallback_capability
        self._capability_intents: Dict[str, List[str]] = {}

    def register_capability_intents(
        self, capability_name: str, intents: List[str]
    ) -> None:
        """
        Register intent keywords for a capability.

        Args:
            capability_name: Name of the capability.
            intents: List of intent keywords or patterns.
        """
        self._capability_intents[capability_name] = intents

    async def route(
        self, intent: str, context: Optional[Dict[str, Any]] = None
    ) -> RoutingResult:
        """
        Route an intent to a capability.

        First attempts classification. If that fails or confidence is low,
        falls back to semantic similarity matching.

        Args:
            intent: User intent or query string.
            context: Optional context dictionary.

        Returns:
            RoutingResult with capability name and confidence score.
        """
        context = context or {}

        # Try classification first
        if self.classify_worker:
            try:
                classification = await self.classify_worker.execute(
                    None, intent=intent
                )
                if classification and hasattr(classification, "label"):
                    return RoutingResult(
                        capability_name=classification.label,
                        confidence=getattr(classification, "confidence", 0.8),
                        metadata={
                            "classifier_output": classification,
                            "intent": intent,
                        },
                        routing_method="classifier",
                    )
            except Exception as e:
                logger.warning(f"Classification failed, using fallback: {e}")

        # Fallback to semantic similarity
        if self.embedding_model:
            try:
                result = await self._semantic_route(intent)
                return result
            except Exception as e:
                logger.warning(f"Semantic routing failed: {e}")

        # Final fallback
        logger.warning(f"Routing to default capability: {self.fallback_capability}")
        return RoutingResult(
            capability_name=self.fallback_capability,
            confidence=0.5,
            metadata={"reason": "fallback", "intent": intent},
            routing_method="fallback",
        )

    async def _semantic_route(self, intent: str) -> RoutingResult:
        """
        Route using semantic similarity to registered intent keywords.

        Args:
            intent: User intent string.

        Returns:
            RoutingResult with highest confidence match.
        """
        if not self._capability_intents:
            return RoutingResult(
                capability_name=self.fallback_capability,
                confidence=0.5,
                metadata={"reason": "no_registered_intents"},
            )

        try:
            # Get embedding for intent
            intent_embedding = await self.embedding_model.embed(intent)

            best_capability = self.fallback_capability
            best_score = 0.0

            # Compare against all registered capability intents
            for cap_name, intent_keywords in self._capability_intents.items():
                for keyword in intent_keywords:
                    try:
                        keyword_embedding = await self.embedding_model.embed(
                            keyword
                        )
                        score = self._cosine_similarity(
                            intent_embedding, keyword_embedding
                        )
                        if score > best_score:
                            best_score = score
                            best_capability = cap_name
                    except Exception:
                        continue

            return RoutingResult(
                capability_name=best_capability,
                confidence=min(best_score, 1.0),
                metadata={"semantic_score": best_score},
                routing_method="semantic",
            )

        except Exception as e:
            logger.error(f"Semantic routing error: {e}")
            return RoutingResult(
                capability_name=self.fallback_capability,
                confidence=0.5,
                metadata={"error": str(e)},
                routing_method="fallback",
            )

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector.
            vec2: Second vector.

        Returns:
            Cosine similarity score (0 to 1).
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)
