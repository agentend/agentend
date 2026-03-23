"""Server module for agentend framework."""

try:
    from .app import create_app
except ImportError:
    create_app = None

try:
    from .routes import router
except ImportError:
    router = None

try:
    from .middleware import setup_middleware
except ImportError:
    setup_middleware = None

__all__ = ["create_app", "router", "setup_middleware"]
