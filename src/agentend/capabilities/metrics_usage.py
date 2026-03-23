"""Metrics usage capability: returns token counts, cost, and latency stats."""

from typing import Any, Dict

from agentend.kernel.kernel import RequestContext


class MetricsUsageCapability:
    """Returns token counts, cost, and latency statistics.

    Reads from the MetricsCollector stored on app state and returns
    per-worker, per-capability, and per-tenant aggregated metrics.
    """

    name: str = "metrics.usage"
    description: str = "Returns token counts, cost, latency stats"

    async def execute(self, context: RequestContext, **kwargs: Any) -> Dict[str, Any]:
        """Return usage metrics.

        Args:
            context: Request context with app state in metadata.

        Returns:
            Dict with worker, capability, and tenant metrics.
        """
        metrics_collector = context.metadata.get("metrics")
        if metrics_collector is None:
            return {
                "capability": "metrics.usage",
                "error": "MetricsCollector not available",
                "workers": {},
                "capabilities": {},
                "tenants": {},
            }

        all_metrics = metrics_collector.get_all_metrics()

        # Serialize worker metrics (they are WorkerMetrics dataclass instances)
        workers = {}
        for worker_id, wm in all_metrics.get("workers", {}).items():
            workers[worker_id] = {
                "tokens_in": wm.tokens_in,
                "tokens_out": wm.tokens_out,
                "cost": wm.cost,
                "latency_ms": wm.latency_ms,
                "call_count": wm.call_count,
                "error_count": wm.error_count,
            }

        # Capability and tenant metrics are already plain dicts
        capabilities = dict(all_metrics.get("capabilities", {}))
        tenants = dict(all_metrics.get("tenants", {}))

        # If tenant_id is set, include tenant-specific view
        tenant_id = context.tenant_id
        tenant_summary = None
        if tenant_id:
            tenant_summary = metrics_collector.get_tenant_metrics(tenant_id)

        return {
            "capability": "metrics.usage",
            "workers": workers,
            "capabilities": capabilities,
            "tenants": tenants,
            "current_tenant": tenant_summary,
        }
