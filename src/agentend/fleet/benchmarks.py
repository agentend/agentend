"""
Model benchmark registry for the Agentend framework.

This module provides benchmark data for LLM models and maps worker slots
to recommended models based on performance, cost, and latency characteristics.

The registry is backed by March 2026 benchmark data and supports multiple
selection strategies (primary, budget, local, fallback).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Data version for tracking when benchmarks were last updated
DATA_VERSION = "2026-03"


@dataclass
class ModelBenchmark:
    """
    Benchmark data for a specific LLM model.

    Captures performance metrics, costs, latency, and capabilities
    for use in model selection and optimization decisions.
    """

    model_id: str
    """Unique model identifier (e.g., 'claude-opus-4-6')."""

    provider: str
    """Model provider (e.g., 'Anthropic', 'OpenAI', 'Google', 'Meta', 'Alibaba', 'Zhipu')."""

    cost_per_1k_input: float
    """Cost per 1,000 input tokens (in USD)."""

    cost_per_1k_output: float
    """Cost per 1,000 output tokens (in USD)."""

    latency_p50_ms: int
    """Median latency in milliseconds (p50)."""

    context_window: int
    """Maximum context window size in tokens."""

    scores: Dict[str, float] = field(default_factory=dict)
    """
    Benchmark scores mapped by name.

    Common benchmark names:
    - chatbot_arena_elo: LMSys Chatbot Arena Elo rating
    - classification_acc: Classification accuracy
    - json_accuracy: JSON output accuracy for structured extraction
    - swe_bench: Software engineering benchmark score
    - gpqa: Graduate-level Google-Proof Q&A
    - gpqa_diamond: Diamond subset of GPQA
    - facts_score: Fact-checking accuracy
    - arena_elo: General Chatbot Arena Elo rating
    - humaneval: Code generation benchmark (HumanEval pass@1)
    - tool_use_acc: Tool/function calling accuracy
    - function_call_success: Function call success rate
    - summarization_quality: Summarization quality score
    """

    strengths: List[str] = field(default_factory=list)
    """Key strengths of this model (e.g., ['fast', 'cheap', 'accurate classification'])."""

    updated: str = "2026-03-01"
    """ISO 8601 date when benchmark data was last updated."""

    def cost_per_1k_tokens(self, input_ratio: float = 0.5) -> float:
        """
        Estimate average cost per 1,000 tokens assuming a mix of input/output.

        Args:
            input_ratio: Proportion of tokens that are input (0.0 to 1.0).
                         Default 0.5 assumes equal input/output.

        Returns:
            Estimated cost per 1,000 tokens.
        """
        return (
            self.cost_per_1k_input * input_ratio
            + self.cost_per_1k_output * (1 - input_ratio)
        )

    def __str__(self) -> str:
        """Return human-readable benchmark summary."""
        score_str = ", ".join(f"{k}={v:.1f}" for k, v in self.scores.items())
        return (
            f"{self.model_id} ({self.provider}) "
            f"[scores: {score_str}, cost: ${self.cost_per_1k_input:.2f}/$"
            f"{self.cost_per_1k_output:.2f}, latency: {self.latency_p50_ms}ms]"
        )


@dataclass
class SlotRecommendation:
    """
    Model recommendations for a specific worker slot.

    Provides primary, fallback, budget, and local deployment options
    for a worker slot like 'classify', 'extract', 'verify', etc.
    """

    slot: str
    """Worker slot name (e.g., 'classify', 'extract', 'verify', 'summarize', 'generate', 'tool_call')."""

    primary: ModelBenchmark
    """Recommended primary model for this slot."""

    fallbacks: List[ModelBenchmark] = field(default_factory=list)
    """List of fallback models if primary is unavailable or fails."""

    budget_pick: ModelBenchmark = None  # type: ignore
    """Most cost-effective model option for this slot."""

    local_pick: Optional[ModelBenchmark] = None
    """Self-hosted/local model option if available."""

    def __post_init__(self) -> None:
        """Validate recommendation has required components."""
        if not self.slot:
            raise ValueError("Slot name cannot be empty")
        if not self.primary:
            raise ValueError(f"Primary model required for slot '{self.slot}'")
        if not self.budget_pick:
            raise ValueError(f"Budget pick required for slot '{self.slot}'")

    def __str__(self) -> str:
        """Return human-readable recommendation summary."""
        result = f"Slot '{self.slot}':\n"
        result += f"  Primary: {self.primary.model_id}\n"
        if self.fallbacks:
            result += f"  Fallbacks: {', '.join(m.model_id for m in self.fallbacks)}\n"
        result += f"  Budget: {self.budget_pick.model_id}\n"
        if self.local_pick:
            result += f"  Local: {self.local_pick.model_id}\n"
        return result


class BenchmarkRegistry:
    """
    Registry of model benchmarks and slot recommendations.

    Provides lookup, comparison, and application of benchmark data
    to fleet configurations. Backed by March 2026 benchmark research.
    """

    # Benchmark data populated from March 2026 research
    BENCHMARKS: Dict[str, ModelBenchmark] = {}

    def __init__(self) -> None:
        """Initialize the registry with benchmark data."""
        if not self.BENCHMARKS:
            self._populate_benchmarks()
        self._recommendations: Dict[str, SlotRecommendation] = {}
        self._populate_recommendations()

    def _populate_benchmarks(self) -> None:
        """Populate BENCHMARKS with March 2026 model data."""
        # Anthropic models
        self.BENCHMARKS["claude-haiku-4-5"] = ModelBenchmark(
            model_id="claude-haiku-4-5",
            provider="Anthropic",
            cost_per_1k_input=0.80 / 1000,
            cost_per_1k_output=4.00 / 1000,
            latency_p50_ms=180,
            context_window=200_000,
            scores={
                "chatbot_arena_elo": 1290,
                "classification_acc": 92.1,
            },
            strengths=["fast", "cheap", "excellent at classification"],
            updated="2026-03-01",
        )

        self.BENCHMARKS["claude-sonnet-4-6"] = ModelBenchmark(
            model_id="claude-sonnet-4-6",
            provider="Anthropic",
            cost_per_1k_input=3.00 / 1000,
            cost_per_1k_output=15.00 / 1000,
            latency_p50_ms=600,
            context_window=200_000,
            scores={
                "swe_bench": 72.7,
                "json_accuracy": 96.2,
                "gpqa": 84.0,
                "arena_elo": 1390,
                "summarization_quality": 94.1,
                "tool_use_acc": 96.8,
                "function_call_success": 97.2,
            },
            strengths=[
                "excellent extraction",
                "best-in-class tool use",
                "high-quality summarization",
            ],
            updated="2026-03-01",
        )

        self.BENCHMARKS["claude-opus-4-6"] = ModelBenchmark(
            model_id="claude-opus-4-6",
            provider="Anthropic",
            cost_per_1k_input=15.00 / 1000,
            cost_per_1k_output=75.00 / 1000,
            latency_p50_ms=2000,
            context_window=200_000,
            scores={
                "facts_score": 67.2,
                "gpqa_diamond": 83.8,
                "swe_bench": 80.8,
                "arena_elo": 1410,
                "humaneval": 92.0,
            },
            strengths=["best verification", "best generation", "highest reasoning power"],
            updated="2026-03-01",
        )

        # OpenAI models
        self.BENCHMARKS["gpt-4o-mini"] = ModelBenchmark(
            model_id="gpt-4o-mini",
            provider="OpenAI",
            cost_per_1k_input=0.15 / 1000,
            cost_per_1k_output=0.60 / 1000,
            latency_p50_ms=150,
            context_window=128_000,
            scores={
                "chatbot_arena_elo": 1272,
                "classification_acc": 90.5,
            },
            strengths=["very fast", "very cheap", "good at classification"],
            updated="2026-03-01",
        )

        self.BENCHMARKS["gpt-4o"] = ModelBenchmark(
            model_id="gpt-4o",
            provider="OpenAI",
            cost_per_1k_input=2.50 / 1000,
            cost_per_1k_output=10.00 / 1000,
            latency_p50_ms=500,
            context_window=128_000,
            scores={
                "swe_bench": 69.1,
                "json_accuracy": 94.8,
                "tool_use_acc": 95.1,
            },
            strengths=["good extraction", "reliable tool use", "good fallback option"],
            updated="2026-03-01",
        )

        # Google models
        self.BENCHMARKS["gemini-2.0-flash"] = ModelBenchmark(
            model_id="gemini-2.0-flash",
            provider="Google",
            cost_per_1k_input=0.10 / 1000,
            cost_per_1k_output=0.40 / 1000,
            latency_p50_ms=120,
            context_window=1_000_000,
            scores={
                "chatbot_arena_elo": 1354,
                "classification_acc": 91.0,
                "summarization_quality": 89.5,
                "tool_use_acc": 92.3,
            },
            strengths=["extremely fast", "very cheap", "huge context window"],
            updated="2026-03-01",
        )

        self.BENCHMARKS["gemini-2.5-flash"] = ModelBenchmark(
            model_id="gemini-2.5-flash",
            provider="Google",
            cost_per_1k_input=0.15 / 1000,
            cost_per_1k_output=0.60 / 1000,
            latency_p50_ms=300,
            context_window=1_000_000,
            scores={
                "json_accuracy": 93.1,
                "facts_score": 58.3,
                "humaneval": 85.3,
                "tool_use_acc": 92.3,
            },
            strengths=["fast", "cheap", "good for extraction", "large context"],
            updated="2026-03-01",
        )

        self.BENCHMARKS["gemini-3-pro"] = ModelBenchmark(
            model_id="gemini-3-pro",
            provider="Google",
            cost_per_1k_input=5.00 / 1000,
            cost_per_1k_output=20.00 / 1000,
            latency_p50_ms=1500,
            context_window=2_000_000,
            scores={
                "facts_score": 68.8,
                "gpqa_diamond": 82.1,
            },
            strengths=["good verification", "excellent fact-checking"],
            updated="2026-03-01",
        )

        # Alibaba models
        self.BENCHMARKS["qwen2.5-7b"] = ModelBenchmark(
            model_id="qwen2.5-7b",
            provider="Alibaba",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_p50_ms=200,
            context_window=32_000,
            scores={
                "classification_acc": 87.3,
            },
            strengths=["free self-hosted", "reasonable classification"],
            updated="2026-03-01",
        )

        self.BENCHMARKS["qwen2.5-72b"] = ModelBenchmark(
            model_id="qwen2.5-72b",
            provider="Alibaba",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_p50_ms=800,
            context_window=131_072,
            scores={
                "json_accuracy": 91.5,
            },
            strengths=["free self-hosted", "good extraction capability"],
            updated="2026-03-01",
        )

        self.BENCHMARKS["qwen2.5-coder-32b"] = ModelBenchmark(
            model_id="qwen2.5-coder-32b",
            provider="Alibaba",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_p50_ms=600,
            context_window=131_072,
            scores={
                "humaneval": 88.1,
            },
            strengths=["free self-hosted", "excellent code generation"],
            updated="2026-03-01",
        )

        # Meta models
        self.BENCHMARKS["llama-4-maverick"] = ModelBenchmark(
            model_id="llama-4-maverick",
            provider="Meta",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_p50_ms=500,
            context_window=131_072,
            scores={
                "facts_score": 52.1,
                "tool_use_acc": 88.7,
            },
            strengths=["free open-source", "decent tool use"],
            updated="2026-03-01",
        )

        # Microsoft models
        self.BENCHMARKS["phi-4-14b"] = ModelBenchmark(
            model_id="phi-4-14b",
            provider="Microsoft",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_p50_ms=400,
            context_window=131_072,
            scores={
                "summarization_quality": 85.2,
            },
            strengths=["free open-source", "lightweight", "good summarization"],
            updated="2026-03-01",
        )

        # Zhipu models
        self.BENCHMARKS["glm-4.7"] = ModelBenchmark(
            model_id="glm-4.7",
            provider="Zhipu",
            cost_per_1k_input=2.00 / 1000,
            cost_per_1k_output=8.00 / 1000,
            latency_p50_ms=800,
            context_window=128_000,
            scores={
                "humaneval": 94.2,
                "arena_elo": 1445,
                "swe_bench": 76.5,
            },
            strengths=["excellent code generation", "high arena ranking"],
            updated="2026-03-01",
        )

    def _populate_recommendations(self) -> None:
        """Populate recommendations for each slot based on benchmark data."""
        # Classify slot: needs fast, cheap, good at classification
        self._recommendations["classify"] = SlotRecommendation(
            slot="classify",
            primary=self.BENCHMARKS["claude-haiku-4-5"],
            fallbacks=[self.BENCHMARKS["gpt-4o-mini"]],
            budget_pick=self.BENCHMARKS["gemini-2.0-flash"],
            local_pick=self.BENCHMARKS["qwen2.5-7b"],
        )

        # Extract slot: structured data extraction, JSON output
        self._recommendations["extract"] = SlotRecommendation(
            slot="extract",
            primary=self.BENCHMARKS["claude-sonnet-4-6"],
            fallbacks=[self.BENCHMARKS["gpt-4o"]],
            budget_pick=self.BENCHMARKS["gemini-2.5-flash"],
            local_pick=self.BENCHMARKS["qwen2.5-72b"],
        )

        # Verify slot: fact-checking, validation
        self._recommendations["verify"] = SlotRecommendation(
            slot="verify",
            primary=self.BENCHMARKS["claude-opus-4-6"],
            fallbacks=[self.BENCHMARKS["gemini-3-pro"]],
            budget_pick=self.BENCHMARKS["gemini-2.5-flash"],
            local_pick=self.BENCHMARKS["llama-4-maverick"],
        )

        # Summarize slot: content condensation
        self._recommendations["summarize"] = SlotRecommendation(
            slot="summarize",
            primary=self.BENCHMARKS["claude-sonnet-4-6"],
            fallbacks=[self.BENCHMARKS["gpt-4o"]],
            budget_pick=self.BENCHMARKS["gemini-2.0-flash"],
            local_pick=self.BENCHMARKS["phi-4-14b"],
        )

        # Generate slot: content/code generation
        self._recommendations["generate"] = SlotRecommendation(
            slot="generate",
            primary=self.BENCHMARKS["claude-opus-4-6"],
            fallbacks=[self.BENCHMARKS["glm-4.7"]],
            budget_pick=self.BENCHMARKS["gemini-2.5-flash"],
            local_pick=self.BENCHMARKS["qwen2.5-coder-32b"],
        )

        # Tool call slot: function/tool calling
        self._recommendations["tool_call"] = SlotRecommendation(
            slot="tool_call",
            primary=self.BENCHMARKS["claude-sonnet-4-6"],
            fallbacks=[self.BENCHMARKS["gpt-4o"]],
            budget_pick=self.BENCHMARKS["gemini-2.5-flash"],
            local_pick=self.BENCHMARKS["llama-4-maverick"],
        )

    def get_recommendation(self, slot: str) -> SlotRecommendation:
        """
        Get model recommendations for a specific worker slot.

        Args:
            slot: Worker slot name ('classify', 'extract', 'verify', 'summarize', 'generate', 'tool_call').

        Returns:
            SlotRecommendation with primary, fallback, budget, and local options.

        Raises:
            ValueError: If slot is not recognized.
        """
        if slot not in self._recommendations:
            raise ValueError(
                f"Unknown slot '{slot}'. Valid slots: {', '.join(self.list_slots())}"
            )
        return self._recommendations[slot]

    def get_model_for_slot(self, slot: str, strategy: str = "primary") -> str:
        """
        Get a specific model ID for a slot using a selection strategy.

        Args:
            slot: Worker slot name.
            strategy: Selection strategy ('primary', 'fallback', 'budget', or 'local').
                     Default is 'primary'.

        Returns:
            Model ID string (e.g., 'claude-opus-4-6').

        Raises:
            ValueError: If slot is unknown or strategy is invalid.
        """
        rec = self.get_recommendation(slot)

        if strategy == "primary":
            return rec.primary.model_id
        elif strategy == "budget":
            return rec.budget_pick.model_id
        elif strategy == "local":
            if rec.local_pick is None:
                raise ValueError(f"No local option available for slot '{slot}'")
            return rec.local_pick.model_id
        elif strategy == "fallback":
            if not rec.fallbacks:
                raise ValueError(f"No fallback models available for slot '{slot}'")
            return rec.fallbacks[0].model_id
        else:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Valid: 'primary', 'fallback', 'budget', 'local'"
            )

    def apply_to_fleet_config(self, fleet_config: Dict[str, Any], strategy: str = "primary") -> Dict[str, Any]:
        """
        Apply benchmark recommendations to a fleet configuration.

        Takes a fleet YAML configuration dict and updates model fields
        for known slots based on benchmark recommendations.

        Args:
            fleet_config: Fleet configuration dict (typically loaded from YAML).
            strategy: Selection strategy for model picking ('primary', 'budget', 'local').
                     Default is 'primary'.

        Returns:
            Updated fleet_config with recommended models applied to worker slots.

        Example:
            >>> config = {'workers': {'classify': {'model': 'gpt-4'}, 'extract': {}}}
            >>> updated = registry.apply_to_fleet_config(config, strategy='budget')
            >>> updated['workers']['classify']['model']  # Returns budget model for classify
        """
        import copy

        updated_config = copy.deepcopy(fleet_config)

        # Ensure workers dict exists
        if "workers" not in updated_config:
            updated_config["workers"] = {}

        # Apply recommendations for each known slot
        for slot in self.list_slots():
            if slot not in updated_config["workers"]:
                updated_config["workers"][slot] = {}

            try:
                model = self.get_model_for_slot(slot, strategy)
                updated_config["workers"][slot]["model"] = model
                logger.info(f"Applied {strategy} model '{model}' to slot '{slot}'")
            except ValueError as e:
                logger.warning(f"Could not apply model to slot '{slot}': {e}")

        return updated_config

    def list_slots(self) -> List[str]:
        """
        List all available worker slots.

        Returns:
            List of slot names in canonical order.
        """
        return [
            "classify",
            "extract",
            "verify",
            "summarize",
            "generate",
            "tool_call",
        ]

    def get_benchmark(self, model_id: str) -> Optional[ModelBenchmark]:
        """
        Look up benchmark data for a specific model.

        Args:
            model_id: Model identifier (e.g., 'claude-opus-4-6').

        Returns:
            ModelBenchmark if found, None otherwise.
        """
        return self.BENCHMARKS.get(model_id)

    def compare_models(self, model_ids: List[str]) -> List[ModelBenchmark]:
        """
        Get benchmark data for multiple models for comparison.

        Useful for cost-benefit analysis, model selection, etc.

        Args:
            model_ids: List of model identifiers to compare.

        Returns:
            List of ModelBenchmark objects in requested order.
                Missing models are silently skipped.

        Example:
            >>> registry.compare_models(['claude-opus-4-6', 'gpt-4o'])
            [ModelBenchmark(...), ModelBenchmark(...)]
        """
        results = []
        for model_id in model_ids:
            benchmark = self.get_benchmark(model_id)
            if benchmark:
                results.append(benchmark)
            else:
                logger.warning(f"Model '{model_id}' not found in benchmarks")
        return results


# Module-level singleton registry instance
registry = BenchmarkRegistry()
