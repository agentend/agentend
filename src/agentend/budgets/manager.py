"""Token budget management system."""

from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

try:
    import redis.asyncio as redis
except ImportError:
    redis = None


logger = logging.getLogger(__name__)


@dataclass
class BudgetQuota:
    """Budget quota configuration."""

    total_tokens: int
    period_seconds: int = 86400  # 24 hours
    refresh_rate: float = 1.0  # Refresh factor per period
    warning_threshold: float = 0.8  # Warn at 80%
    hard_limit: bool = True  # Block at limit


@dataclass
class BudgetUsage:
    """Current budget usage."""

    tokens_used: int = 0
    tokens_remaining: int = 0
    period_start: datetime = field(default_factory=datetime.now)
    period_end: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=1))
    exceeded: bool = False


class BudgetManager:
    """
    Token budget management for tenants, users, and capabilities.

    Provides check_budget(), track_usage(), get_remaining() operations
    with token-aware rate limiting.
    """

    def __init__(self, redis_client):
        """
        Initialize budget manager.

        Args:
            redis_client: Redis client for budget tracking.
        """
        if redis is None:
            raise ImportError("Install agentend[memory] for Redis support")
        self.redis = redis_client
        self.quotas: Dict[str, BudgetQuota] = {}

    def set_quota(
        self,
        budget_id: str,
        total_tokens: int,
        period_seconds: int = 86400,
        refresh_rate: float = 1.0,
        warning_threshold: float = 0.8,
        hard_limit: bool = True,
    ) -> None:
        """
        Set or update budget quota.

        Args:
            budget_id: Unique budget identifier (e.g., "tenant:123", "user:456").
            total_tokens: Total tokens allowed in period.
            period_seconds: Period duration in seconds.
            refresh_rate: Refresh factor per period.
            warning_threshold: Threshold for warnings.
            hard_limit: If True, block when quota exceeded.
        """
        self.quotas[budget_id] = BudgetQuota(
            total_tokens=total_tokens,
            period_seconds=period_seconds,
            refresh_rate=refresh_rate,
            warning_threshold=warning_threshold,
            hard_limit=hard_limit,
        )

    async def check_budget(
        self,
        budget_id: str,
        tokens_needed: int,
    ) -> dict[str, Any]:
        """
        Check if budget allows token consumption.

        Args:
            budget_id: Budget identifier.
            tokens_needed: Number of tokens needed.

        Returns:
            Check result with allowed, remaining, and warnings.
        """
        quota = self.quotas.get(budget_id)
        if not quota:
            return {
                "allowed": True,
                "reason": "no_quota",
                "tokens_needed": tokens_needed,
            }

        # Get current usage
        usage = await self._get_usage(budget_id, quota)

        remaining = usage.tokens_remaining
        allowed = remaining >= tokens_needed

        # Check hard limit
        if not allowed and quota.hard_limit:
            return {
                "allowed": False,
                "reason": "budget_exceeded",
                "tokens_needed": tokens_needed,
                "tokens_remaining": remaining,
                "tokens_total": quota.total_tokens,
            }

        # Check warning threshold
        warned = False
        warning_reason = None
        if remaining < quota.total_tokens * (1 - quota.warning_threshold):
            warned = True
            warning_reason = f"approaching_limit:{remaining}/{quota.total_tokens}"

        return {
            "allowed": allowed,
            "tokens_needed": tokens_needed,
            "tokens_remaining": remaining,
            "tokens_total": quota.total_tokens,
            "warned": warned,
            "warning_reason": warning_reason,
        }

    async def track_usage(
        self,
        budget_id: str,
        tokens_used: int,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Track token usage against budget.

        Args:
            budget_id: Budget identifier.
            tokens_used: Tokens consumed.
            metadata: Optional metadata to log with usage.
        """
        quota = self.quotas.get(budget_id)
        if not quota:
            return

        # Increment usage in Redis
        usage_key = f"budget:{budget_id}:usage"
        await self.redis.incrby(usage_key, tokens_used)

        # Set expiration to period length
        await self.redis.expire(usage_key, quota.period_seconds)

        # Log usage
        logger.info(
            f"Budget usage tracked",
            extra={
                "budget_id": budget_id,
                "tokens_used": tokens_used,
                "metadata": metadata,
            }
        )

    async def get_remaining(self, budget_id: str) -> int:
        """
        Get remaining tokens in budget.

        Args:
            budget_id: Budget identifier.

        Returns:
            Remaining tokens.
        """
        quota = self.quotas.get(budget_id)
        if not quota:
            return -1  # Unlimited

        usage = await self._get_usage(budget_id, quota)
        return usage.tokens_remaining

    async def reset_budget(self, budget_id: str) -> None:
        """
        Reset budget usage.

        Args:
            budget_id: Budget identifier.
        """
        usage_key = f"budget:{budget_id}:usage"
        await self.redis.delete(usage_key)

    async def get_all_budgets(self) -> dict[str, dict[str, Any]]:
        """
        Get all budget statuses.

        Returns:
            Dictionary of all budgets with current usage.
        """
        result = {}

        for budget_id, quota in self.quotas.items():
            usage = await self._get_usage(budget_id, quota)
            result[budget_id] = {
                "total_tokens": quota.total_tokens,
                "tokens_used": usage.tokens_used,
                "tokens_remaining": usage.tokens_remaining,
                "period_start": usage.period_start.isoformat(),
                "period_end": usage.period_end.isoformat(),
                "exceeded": usage.exceeded,
            }

        return result

    async def _get_usage(
        self,
        budget_id: str,
        quota: BudgetQuota,
    ) -> BudgetUsage:
        """
        Get current usage for budget.

        Args:
            budget_id: Budget identifier.
            quota: Quota configuration.

        Returns:
            Current usage.
        """
        usage_key = f"budget:{budget_id}:usage"
        tokens_used_str = await self.redis.get(usage_key)
        tokens_used = int(tokens_used_str) if tokens_used_str else 0

        tokens_remaining = quota.total_tokens - tokens_used

        return BudgetUsage(
            tokens_used=tokens_used,
            tokens_remaining=max(0, tokens_remaining),
            exceeded=tokens_remaining < 0,
        )

    def get_rate_limit_headers(self, budget_id: str, remaining: int) -> dict[str, str]:
        """
        Get rate limit headers for response.

        Args:
            budget_id: Budget identifier.
            remaining: Remaining tokens.

        Returns:
            HTTP headers for rate limiting.
        """
        quota = self.quotas.get(budget_id)
        if not quota:
            return {}

        return {
            "X-RateLimit-Limit": str(quota.total_tokens),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(quota.period_seconds),
        }
