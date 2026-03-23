"""OpenTelemetry tracing integration."""

from typing import Optional, Any, Callable
from functools import wraps
import logging
import os

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
except ImportError:
    trace = None
    TracerProvider = None
    BatchSpanProcessor = None
    OTLPSpanExporter = None
    FastAPIInstrumentor = None
    SQLAlchemyInstrumentor = None
    RedisInstrumentor = None


logger = logging.getLogger(__name__)


def create_tracer(service_name: str):
    """
    Create OpenTelemetry tracer.

    Args:
        service_name: Name of service for tracing.

    Returns:
        Configured Tracer instance.
    """
    if trace is None:
        logger.warning("OpenTelemetry not installed. Tracing disabled.")
        return None

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    try:
        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,
        )

        # Create tracer provider
        trace_provider = TracerProvider()
        trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(trace_provider)

        # Auto-instrument libraries
        try:
            if FastAPIInstrumentor:
                FastAPIInstrumentor().instrument()
            if SQLAlchemyInstrumentor:
                SQLAlchemyInstrumentor().instrument()
            if RedisInstrumentor:
                RedisInstrumentor().instrument()
        except Exception as e:
            logger.warning(f"Failed to auto-instrument libraries: {e}")

    except Exception as e:
        logger.warning(f"Failed to setup OTLP tracing: {e}. Using no-op tracer.")
        trace_provider = TracerProvider()
        trace.set_tracer_provider(trace_provider)

    return trace.get_tracer(service_name)


async def trace_worker_call(
    tracer,
    worker_id: str,
    capability: str,
    input_data: Any,
) -> Any:
    """
    Trace worker execution.

    Args:
        tracer: Tracer instance.
        worker_id: Worker identifier.
        capability: Capability being executed.
        input_data: Input to worker.

    Returns:
        Span context for worker call.
    """
    if tracer is None:
        raise ImportError("Install agentend[observability] for OpenTelemetry support")
    with tracer.start_as_current_span("worker_call") as span:
        span.set_attribute("worker_id", worker_id)
        span.set_attribute("capability", capability)
        span.set_attribute("input_size", len(str(input_data)))
        return span


async def trace_memory_lookup(
    tracer,
    memory_type: str,
    query: str,
) -> Any:
    """
    Trace memory lookup operation.

    Args:
        tracer: Tracer instance.
        memory_type: Type of memory (facts, graph, etc).
        query: Memory query.

    Returns:
        Span context for memory lookup.
    """
    if tracer is None:
        raise ImportError("Install agentend[observability] for OpenTelemetry support")
    with tracer.start_as_current_span("memory_lookup") as span:
        span.set_attribute("memory_type", memory_type)
        span.set_attribute("query_length", len(query))
        return span


async def trace_tool_call(
    tracer,
    tool_name: str,
    arguments: dict,
) -> Any:
    """
    Trace tool execution.

    Args:
        tracer: Tracer instance.
        tool_name: Name of tool.
        arguments: Tool arguments.

    Returns:
        Span context for tool call.
    """
    if tracer is None:
        raise ImportError("Install agentend[observability] for OpenTelemetry support")
    with tracer.start_as_current_span("tool_call") as span:
        span.set_attribute("tool_name", tool_name)
        span.set_attribute("arg_count", len(arguments))
        span.set_attribute("arg_keys", ",".join(arguments.keys()))
        return span


def traced(operation_name: str) -> Callable:
    """
    Decorator for automatic tracing. No-op when OpenTelemetry is not installed.

    Args:
        operation_name: Name of operation for tracing.

    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        if trace is None:
            return func

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span(operation_name) as span:
                span.set_attribute("function", func.__name__)
                span.set_attribute("args_count", len(args))
                span.set_attribute("kwargs_keys", ",".join(kwargs.keys()))

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error_type", type(e).__name__)
                    span.set_attribute("error_message", str(e))
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span(operation_name) as span:
                span.set_attribute("function", func.__name__)
                span.set_attribute("args_count", len(args))
                span.set_attribute("kwargs_keys", ",".join(kwargs.keys()))

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error_type", type(e).__name__)
                    span.set_attribute("error_message", str(e))
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
