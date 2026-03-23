"""Observability module for agentend framework."""

try:
    from .traces import create_tracer, trace_worker_call, trace_memory_lookup, trace_tool_call, traced
except ImportError:
    create_tracer = None
    trace_worker_call = None
    trace_memory_lookup = None
    trace_tool_call = None
    traced = None

try:
    from .metrics import MetricsCollector
except ImportError:
    MetricsCollector = None

__all__ = [
    "create_tracer",
    "trace_worker_call",
    "trace_memory_lookup",
    "trace_tool_call",
    "traced",
    "MetricsCollector",
]
