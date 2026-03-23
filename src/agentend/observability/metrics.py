"""Metrics collection and export."""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import os

try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
except ImportError:
    metrics = None
    MeterProvider = None
    PeriodicExportingMetricReader = None
    OTLPMetricExporter = None


logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""

    timestamp: datetime = field(default_factory=datetime.now)
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkerMetrics:
    """Metrics for a worker."""

    worker_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    call_count: int = 0
    error_count: int = 0


class MetricsCollector:
    """
    Collects and exports metrics to OpenTelemetry.

    Tracks tokens_in, tokens_out, cost, latency per worker/capability/tenant.
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.capability_metrics: Dict[str, Dict[str, Any]] = {}
        self.tenant_metrics: Dict[str, Dict[str, Any]] = {}
        self._setup_otel()

    def _setup_otel(self) -> None:
        """Setup OpenTelemetry metrics export."""
        if metrics is None:
            logger.warning("OpenTelemetry not installed. Metrics will not be exported.")
            self.meter = None
            return

        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        try:
            # Create OTLP metric exporter
            otlp_exporter = OTLPMetricExporter(
                endpoint=otlp_endpoint,
                insecure=True,
            )

            # Create metric reader
            metric_reader = PeriodicExportingMetricReader(otlp_exporter, interval_millis=60000)

            # Create meter provider
            meter_provider = MeterProvider(metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)

            self.meter = metrics.get_meter(__name__)

            # Create instruments
            self.tokens_in_counter = self.meter.create_counter(
                "agentend.tokens_in",
                description="Tokens processed as input",
            )

            self.tokens_out_counter = self.meter.create_counter(
                "agentend.tokens_out",
                description="Tokens generated as output",
            )

            self.cost_counter = self.meter.create_counter(
                "agentend.cost",
                description="Total cost in USD",
            )

            self.latency_histogram = self.meter.create_histogram(
                "agentend.latency_ms",
                description="Request latency in milliseconds",
            )

            logger.info("OpenTelemetry metrics initialized")

        except Exception as e:
            logger.warning(f"Failed to setup OpenTelemetry metrics: {e}")
            self.meter = None

    def track_worker_call(
        self,
        worker_id: str,
        capability: str,
        tokens_in: int,
        tokens_out: int,
        cost: float = 0.0,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """
        Track worker call metrics.

        Args:
            worker_id: Worker identifier.
            capability: Capability executed.
            tokens_in: Input tokens.
            tokens_out: Output tokens.
            cost: Cost of call.
            latency_ms: Latency in milliseconds.
            success: Whether call succeeded.
        """
        # Update worker metrics
        if worker_id not in self.worker_metrics:
            self.worker_metrics[worker_id] = WorkerMetrics(worker_id=worker_id)

        metrics_obj = self.worker_metrics[worker_id]
        metrics_obj.tokens_in += tokens_in
        metrics_obj.tokens_out += tokens_out
        metrics_obj.cost += cost
        metrics_obj.latency_ms = latency_ms
        metrics_obj.call_count += 1
        if not success:
            metrics_obj.error_count += 1

        # Update capability metrics
        if capability not in self.capability_metrics:
            self.capability_metrics[capability] = {
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "call_count": 0,
                "error_count": 0,
            }

        cap_metrics = self.capability_metrics[capability]
        cap_metrics["tokens_in"] += tokens_in
        cap_metrics["tokens_out"] += tokens_out
        cap_metrics["cost"] += cost
        cap_metrics["call_count"] += 1
        if not success:
            cap_metrics["error_count"] += 1

        # Export to OpenTelemetry if available
        if self.meter:
            labels = {
                "worker_id": worker_id,
                "capability": capability,
                "status": "success" if success else "error",
            }

            self.tokens_in_counter.add(tokens_in, attributes=labels)
            self.tokens_out_counter.add(tokens_out, attributes=labels)
            self.cost_counter.add(cost, attributes=labels)
            self.latency_histogram.record(latency_ms, attributes=labels)

    def track_tenant_usage(
        self,
        tenant_id: str,
        tokens: int,
        cost: float = 0.0,
    ) -> None:
        """
        Track tenant-level usage.

        Args:
            tenant_id: Tenant identifier.
            tokens: Tokens used.
            cost: Cost incurred.
        """
        if tenant_id not in self.tenant_metrics:
            self.tenant_metrics[tenant_id] = {
                "tokens": 0,
                "cost": 0.0,
                "call_count": 0,
            }

        self.tenant_metrics[tenant_id]["tokens"] += tokens
        self.tenant_metrics[tenant_id]["cost"] += cost
        self.tenant_metrics[tenant_id]["call_count"] += 1

    def get_worker_metrics(self, worker_id: str) -> Optional[WorkerMetrics]:
        """
        Get metrics for a worker.

        Args:
            worker_id: Worker identifier.

        Returns:
            WorkerMetrics or None.
        """
        return self.worker_metrics.get(worker_id)

    def get_capability_metrics(self, capability: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a capability.

        Args:
            capability: Capability name.

        Returns:
            Metrics dictionary or None.
        """
        return self.capability_metrics.get(capability)

    def get_tenant_metrics(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a tenant.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            Metrics dictionary or None.
        """
        return self.tenant_metrics.get(tenant_id)

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.

        Returns:
            Dictionary with all metrics.
        """
        return {
            "workers": self.worker_metrics,
            "capabilities": self.capability_metrics,
            "tenants": self.tenant_metrics,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.worker_metrics.clear()
        self.capability_metrics.clear()
        self.tenant_metrics.clear()
