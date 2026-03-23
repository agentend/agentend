"""Plugins module for agentend framework."""

from .manager import PluginManager
from .hooks import HookRegistry

__all__ = ["PluginManager", "HookRegistry"]
