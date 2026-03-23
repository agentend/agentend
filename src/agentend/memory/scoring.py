"""
MemoryScorer: Composite scoring for semantic memory results.

Implements: α·similarity + β·recency_decay + γ·importance + δ·frequency
With configurable weights for different use cases.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configuration for memory scoring weights."""
    similarity: float = 0.6    # α: Semantic similarity
    recency: float = 0.2       # β: Recency decay
    importance: float = 0.1    # γ: Importance score
    frequency: float = 0.1     # δ: Access frequency

    def __post_init__(self) -> None:
        """Validate weights sum to 1.0."""
        total = self.similarity + self.recency + self.importance + self.frequency
        if abs(total - 1.0) > 0.01:
            logger.warning(
                f"Scoring weights sum to {total}, not 1.0. "
                f"Normalizing..."
            )
            # Normalize
            self.similarity /= total
            self.recency /= total
            self.importance /= total
            self.frequency /= total


class MemoryScorer:
    """
    Composite scoring for semantic memories.

    Scores combine:
    - Similarity: Cosine similarity to query (0-1)
    - Recency: Time decay (newer is better)
    - Importance: Explicit importance score (0-1)
    - Frequency: How often accessed (normalized 0-1)
    """

    def __init__(self, weights: ScoringWeights = None):
        """
        Initialize scorer.

        Args:
            weights: Scoring weights (defaults to balanced)
        """
        self.weights = weights or ScoringWeights()

    def score(
        self,
        similarity: float,
        created_at: datetime,
        importance: float = 0.5,
        frequency: int = 1,
        recency_halflife_hours: int = 168,
    ) -> float:
        """
        Compute composite score for a memory.

        Args:
            similarity: Semantic similarity (0-1)
            created_at: Creation timestamp
            importance: Importance score (0-1)
            frequency: Access frequency count
            recency_halflife_hours: Half-life for recency decay (default: 1 week)

        Returns:
            Composite score (0-1)
        """
        # Clamp similarity to [0, 1]
        similarity = max(0.0, min(1.0, similarity))

        # Compute recency decay using exponential decay
        age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
        recency = self._exponential_decay(age_hours, recency_halflife_hours)

        # Clamp importance to [0, 1]
        importance = max(0.0, min(1.0, importance))

        # Normalize frequency (assume max useful frequency is ~10)
        frequency_norm = min(frequency / 10.0, 1.0)

        # Composite score
        composite = (
            self.weights.similarity * similarity +
            self.weights.recency * recency +
            self.weights.importance * importance +
            self.weights.frequency * frequency_norm
        )

        return composite

    def rank_memories(
        self,
        memories: List[Dict[str, Any]],
        similarity_key: str = "similarity",
        created_at_key: str = "created_at",
        importance_key: str = "importance",
        frequency_key: str = "frequency",
        reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Rank and score a list of memories.

        Args:
            memories: List of memory dicts
            similarity_key: Key for similarity value
            created_at_key: Key for created_at timestamp
            importance_key: Key for importance value
            frequency_key: Key for frequency value
            reverse: Sort descending (highest first)

        Returns:
            Ranked list with 'score' field added to each memory
        """
        scored = []

        for mem in memories:
            try:
                similarity = mem.get(similarity_key, 0.5)
                created_at = mem.get(created_at_key)
                importance = mem.get(importance_key, 0.5)
                frequency = mem.get(frequency_key, 1)

                # Parse created_at if it's a string
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                elif not isinstance(created_at, datetime):
                    created_at = datetime.utcnow()

                score = self.score(
                    similarity=similarity,
                    created_at=created_at,
                    importance=importance,
                    frequency=frequency,
                )

                mem_with_score = dict(mem)
                mem_with_score["score"] = score
                scored.append(mem_with_score)

            except Exception as e:
                logger.error(f"Error scoring memory: {e}")
                mem["score"] = 0.0
                scored.append(mem)

        # Sort
        scored.sort(key=lambda x: x.get("score", 0), reverse=reverse)
        return scored

    @staticmethod
    def _exponential_decay(
        time_elapsed: float,
        halflife: float,
    ) -> float:
        """
        Exponential decay function.

        At halflife, returns 0.5. Asymptotes to 0.

        Args:
            time_elapsed: Time elapsed since creation
            halflife: Half-life period

        Returns:
            Decay value (0-1)
        """
        import math
        return math.exp(-math.log(2) * (time_elapsed / halflife))

    def get_weight_summary(self) -> Dict[str, float]:
        """Get summary of current weights."""
        return {
            "similarity": self.weights.similarity,
            "recency": self.weights.recency,
            "importance": self.weights.importance,
            "frequency": self.weights.frequency,
        }

    def set_weights(self, **kwargs) -> None:
        """
        Update scoring weights.

        Args:
            similarity: New similarity weight
            recency: New recency weight
            importance: New importance weight
            frequency: New frequency weight
        """
        if "similarity" in kwargs:
            self.weights.similarity = kwargs["similarity"]
        if "recency" in kwargs:
            self.weights.recency = kwargs["recency"]
        if "importance" in kwargs:
            self.weights.importance = kwargs["importance"]
        if "frequency" in kwargs:
            self.weights.frequency = kwargs["frequency"]

        # Renormalize
        total = (
            self.weights.similarity +
            self.weights.recency +
            self.weights.importance +
            self.weights.frequency
        )
        if abs(total - 1.0) > 0.01:
            self.weights.similarity /= total
            self.weights.recency /= total
            self.weights.importance /= total
            self.weights.frequency /= total
