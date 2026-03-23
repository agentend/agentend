"""Budgets module for agentend framework."""

try:
    from .manager import BudgetManager
except ImportError:
    BudgetManager = None

__all__ = ["BudgetManager"]
