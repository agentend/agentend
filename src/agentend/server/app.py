"""FastAPI application factory for agentend."""

from contextlib import asynccontextmanager
from typing import Optional

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
except ImportError:
    create_async_engine = None
    AsyncSession = None
    async_sessionmaker = None

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentend.config import Config
from agentend.server.routes import router
from agentend.server.middleware import setup_middleware
from agentend.observability.traces import create_tracer
from agentend.observability.metrics import MetricsCollector
from agentend.kernel.registry import CapabilityRegistry
from agentend.capabilities import SYSTEM_CAPABILITIES


async def _startup(config: Config) -> dict:
    """Initialize connections on startup. Skips unavailable services gracefully."""
    import logging
    logger = logging.getLogger(__name__)
    connections = {}

    # Initialize Redis (optional)
    try:
        if redis is not None:
            redis_client = await redis.from_url(
                config.memory.redis_url,
                encoding="utf8",
                decode_responses=True,
            )
            await redis_client.ping()
            connections["redis"] = redis_client
            logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable, using in-memory fallback: {e}")

    # Initialize PostgreSQL (optional)
    try:
        if create_async_engine is not None:
            engine = create_async_engine(config.memory.database_url)
            async_session = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            # Auto-create tables
            from agentend.persistence.models import Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            connections["engine"] = engine
            connections["session_factory"] = async_session
            logger.info("PostgreSQL connected, tables created")
    except Exception as e:
        logger.warning(f"PostgreSQL unavailable: {e}")

    # Initialize OpenTelemetry tracer (optional)
    try:
        tracer = create_tracer("agentend")
        connections["tracer"] = tracer
    except Exception:
        pass

    # Initialize metrics collector (optional)
    try:
        metrics = MetricsCollector()
        connections["metrics"] = metrics
    except Exception:
        pass

    return connections


async def _shutdown(connections: dict) -> None:
    """Clean up connections on shutdown."""
    if "engine" in connections:
        await connections["engine"].dispose()

    if "redis" in connections:
        await connections["redis"].close()


def create_app(config: Optional[Config] = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        config: Configuration object. If None, loads from environment.

    Returns:
        Configured FastAPI instance.
    """
    if config is None:
        config = Config.load()

    connections = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan context manager for startup/shutdown."""
        nonlocal connections
        connections = await _startup(config)
        app.state.config = config
        app.state.redis = connections.get("redis")
        app.state.engine = connections.get("engine")
        app.state.session_factory = connections.get("session_factory")
        app.state.tracer = connections.get("tracer")
        app.state.metrics = connections.get("metrics")

        # Register system capabilities
        registry = CapabilityRegistry()
        for cap_name, cap_instance in SYSTEM_CAPABILITIES.items():
            registry.register(cap_name, cap_instance)
        app.state.registry = registry
        yield
        await _shutdown(connections)

    app = FastAPI(
        title="agentend",
        description="Agent execution and orchestration engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=getattr(config, 'cors_origins', ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Setup custom middleware
    setup_middleware(app)

    # Include routes
    app.include_router(router)

    return app
