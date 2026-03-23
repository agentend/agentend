"""CLI module for agentend framework."""

try:
    from .main import app
except ImportError:
    app = None

__all__ = ["app"]
