"""
Worker implementations for common tasks.
"""

from agentend.fleet.workers.classify import ClassifyWorker
from agentend.fleet.workers.extract import ExtractWorker
from agentend.fleet.workers.generate import GenerateWorker
from agentend.fleet.workers.verify import VerifyWorker
from agentend.fleet.workers.summarize import SummarizeWorker
from agentend.fleet.workers.tool_call import ToolCallWorker

__all__ = [
    "ClassifyWorker",
    "ExtractWorker",
    "GenerateWorker",
    "VerifyWorker",
    "SummarizeWorker",
    "ToolCallWorker",
]
