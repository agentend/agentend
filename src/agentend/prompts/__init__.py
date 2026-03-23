"""Prompts module for agentend framework."""

from .slots import BaseCapability
from .middleware import PromptMiddleware
from .truncation import PromptTruncation

__all__ = [
    "BaseCapability",
    "PromptMiddleware",
    "PromptTruncation",
]
