"""
Workflow and Step dataclasses for DAG-based orchestration.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable
from enum import Enum


class InterruptPolicy(str, Enum):
    """Interrupt policy for a step."""
    NEVER = "never"           # Never interrupt
    ON_FAILURE = "on_failure" # Interrupt only on failure
    ON_TOOL_CALL = "on_tool_call"  # Interrupt on any tool call
    ALWAYS = "always"         # Always interrupt before execution


@dataclass
class RetryConfig:
    """Retry configuration for a step."""
    max_retries: int = 0
    backoff_factor: float = 1.0
    backoff_max: float = 60.0
    retry_on: List[str] = field(default_factory=lambda: ["timeout", "transient_error"])


@dataclass
class Step:
    """
    Definition of a workflow step.

    A step is a unit of work that can be executed independently.
    Steps are executed based on dependency order.
    """
    name: str
    worker: Callable[[Dict[str, Any]], Awaitable[Any]]
    input: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    interrupt_policy: InterruptPolicy = InterruptPolicy.NEVER
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    timeout_seconds: Optional[float] = None
    description: str = ""

    def __post_init__(self) -> None:
        """Validate step configuration."""
        if not self.name:
            raise ValueError("Step name cannot be empty")
        if not self.worker:
            raise ValueError("Step worker cannot be None")


@dataclass
class Workflow:
    """
    Definition of a DAG-based workflow.

    A workflow consists of multiple steps with dependencies.
    Steps are executed in order respecting dependencies.
    Parallel execution is possible for independent steps.
    """
    name: str
    steps: List[Step] = field(default_factory=list)
    supervisor_model: Optional[str] = None
    parallel_enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate workflow configuration."""
        if not self.name:
            raise ValueError("Workflow name cannot be empty")

        # Validate step names are unique
        names = [step.name for step in self.steps]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate step names in workflow")

        # Validate dependencies exist
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in names:
                    raise ValueError(f"Step '{step.name}' depends on non-existent step '{dep}'")

        # Validate no circular dependencies
        self._validate_no_cycles()

    def _validate_no_cycles(self) -> None:
        """Validate workflow has no circular dependencies."""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            step = next((s for s in self.steps if s.name == node), None)
            if not step:
                return False

            for dep in step.depends_on:
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for step in self.steps:
            if step.name not in visited:
                if dfs(step.name):
                    raise ValueError(f"Circular dependency detected in workflow '{self.name}'")

    def get_step(self, name: str) -> Optional[Step]:
        """Get a step by name."""
        return next((s for s in self.steps if s.name == name), None)

    def get_topological_order(self) -> List[str]:
        """Get step names in topological order."""
        in_degree = {step.name: len(step.depends_on) for step in self.steps}
        queue = [step.name for step in self.steps if step.depends_on == []]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            # Find steps that depend on this one
            for step in self.steps:
                if node in step.depends_on:
                    in_degree[step.name] -= 1
                    if in_degree[step.name] == 0:
                        queue.append(step.name)

        return order

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get steps grouped by execution level (can execute in parallel).

        Returns:
            List of lists, where inner lists contain steps that can run in parallel
        """
        if not self.parallel_enabled:
            return [[step.name] for step in self.steps]

        levels = {}
        step_by_name = {step.name: step for step in self.steps}

        for step in self.steps:
            if not step.depends_on:
                levels[step.name] = 0
            else:
                max_dep_level = max(levels.get(dep, 0) for dep in step.depends_on)
                levels[step.name] = max_dep_level + 1

        # Group by level
        groups = {}
        for step_name, level in levels.items():
            if level not in groups:
                groups[level] = []
            groups[level].append(step_name)

        return [groups[level] for level in sorted(groups.keys())]
