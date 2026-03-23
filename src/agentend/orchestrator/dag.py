"""
DAGExecutor: Executes workflow steps respecting dependencies.

Handles:
- Topological ordering
- Parallel execution of independent steps
- Checkpointing after each step
- Retry logic on failure
- Human-in-the-loop interrupts
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .workflow import Workflow, Step, InterruptPolicy

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of step execution."""
    step_name: str
    status: str  # "success", "failed", "interrupted", "skipped"
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    retries: int = 0


@dataclass
class WorkflowCheckpoint:
    """Checkpoint for workflow execution."""
    workflow_name: str
    executed_steps: Dict[str, StepResult]
    current_step: Optional[str] = None
    timestamp: str = ""


class DAGExecutor:
    """
    Executes workflows as directed acyclic graphs.

    Features:
    - Respects dependency order
    - Parallel execution of independent steps
    - Checkpoint at each step
    - Retry logic on failure
    - Human-in-the-loop interrupt support
    """

    def __init__(self, hitl_manager=None):
        """
        Initialize DAGExecutor.

        Args:
            hitl_manager: Optional HITL manager for interrupts
        """
        self.hitl_manager = hitl_manager
        self.checkpoints: Dict[str, WorkflowCheckpoint] = {}

    async def execute(
        self,
        workflow: Workflow,
        execution_id: str = "",
        resume_from: Optional[str] = None,
    ) -> Dict[str, StepResult]:
        """
        Execute a workflow, respecting dependencies.

        Args:
            workflow: Workflow to execute
            execution_id: Unique execution identifier
            resume_from: Optional step name to resume from

        Returns:
            Dictionary mapping step names to results
        """
        if not execution_id:
            execution_id = f"{workflow.name}:{int(time.time())}"

        logger.info(f"Starting workflow execution: {execution_id}")
        results: Dict[str, StepResult] = {}

        # Get parallel groups
        groups = workflow.get_parallel_groups()

        # Filter groups if resuming
        if resume_from:
            resume_index = None
            for idx, group in enumerate(groups):
                if resume_from in group:
                    resume_index = idx
                    break

            if resume_index is not None:
                groups = groups[resume_index:]
            else:
                logger.warning(f"Resume point '{resume_from}' not found")

        # Execute each group (parallel within, serial between)
        for group in groups:
            tasks = []
            for step_name in group:
                step = workflow.get_step(step_name)
                if not step:
                    continue

                # Check if dependencies are met
                if all(dep in results for dep in step.depends_on):
                    task = self._execute_step(
                        step,
                        workflow,
                        results,
                        execution_id,
                    )
                    tasks.append(task)

            # Execute group in parallel
            if tasks:
                group_results = await asyncio.gather(*tasks, return_exceptions=True)
                for step_name, result in zip(group, group_results):
                    if isinstance(result, StepResult):
                        results[step_name] = result
                    else:
                        logger.error(f"Step {step_name} raised exception: {result}")
                        results[step_name] = StepResult(
                            step_name=step_name,
                            status="failed",
                            error=str(result),
                        )

            # Checkpoint after group
            self._save_checkpoint(workflow, execution_id, results)

        logger.info(f"Workflow execution completed: {execution_id}")
        return results

    async def _execute_step(
        self,
        step: Step,
        workflow: Workflow,
        previous_results: Dict[str, StepResult],
        execution_id: str,
    ) -> StepResult:
        """
        Execute a single step with retry logic.

        Args:
            step: Step to execute
            workflow: Parent workflow
            previous_results: Results from previous steps
            execution_id: Execution ID

        Returns:
            Step result
        """
        logger.info(f"Executing step: {step.name}")
        start_time = time.time()

        # Handle interrupts
        if step.interrupt_policy != InterruptPolicy.NEVER and self.hitl_manager:
            approval = await self.hitl_manager.request_approval(
                step=step,
                context={"previous_results": previous_results},
            )
            if not approval:
                logger.info(f"Step {step.name} rejected by human")
                return StepResult(
                    step_name=step.name,
                    status="interrupted",
                    duration_seconds=time.time() - start_time,
                )

        # Build input with previous results
        step_input = dict(step.input)
        for dep in step.depends_on:
            if dep in previous_results:
                step_input[f"{dep}_result"] = previous_results[dep].output

        # Execute with retry
        retries = 0
        last_error = None

        while retries <= step.retry_config.max_retries:
            try:
                # Execute with timeout
                if step.timeout_seconds:
                    output = await asyncio.wait_for(
                        step.worker(step_input),
                        timeout=step.timeout_seconds,
                    )
                else:
                    output = await step.worker(step_input)

                duration = time.time() - start_time
                logger.info(f"Step {step.name} completed in {duration:.2f}s")

                return StepResult(
                    step_name=step.name,
                    status="success",
                    output=output,
                    duration_seconds=duration,
                    retries=retries,
                )

            except asyncio.TimeoutError as e:
                last_error = f"Timeout after {step.timeout_seconds}s"
                if "timeout" not in step.retry_config.retry_on:
                    raise
            except Exception as e:
                last_error = str(e)
                # Check if we should retry
                if "transient_error" not in step.retry_config.retry_on:
                    raise

            # Retry with backoff
            if retries < step.retry_config.max_retries:
                retries += 1
                backoff = min(
                    step.retry_config.backoff_factor ** retries,
                    step.retry_config.backoff_max,
                )
                logger.warning(
                    f"Step {step.name} failed (attempt {retries}), "
                    f"retrying in {backoff:.1f}s: {last_error}"
                )
                await asyncio.sleep(backoff)
            else:
                break

        # All retries exhausted
        duration = time.time() - start_time
        logger.error(f"Step {step.name} failed after {retries} retries: {last_error}")

        return StepResult(
            step_name=step.name,
            status="failed",
            error=last_error,
            duration_seconds=duration,
            retries=retries,
        )

    def _save_checkpoint(
        self,
        workflow: Workflow,
        execution_id: str,
        results: Dict[str, StepResult],
    ) -> None:
        """Save execution checkpoint."""
        from datetime import datetime

        checkpoint = WorkflowCheckpoint(
            workflow_name=workflow.name,
            executed_steps=results,
            timestamp=datetime.utcnow().isoformat(),
        )
        self.checkpoints[execution_id] = checkpoint
        logger.debug(f"Checkpoint saved: {execution_id}")

    def get_checkpoint(self, execution_id: str) -> Optional[WorkflowCheckpoint]:
        """Retrieve a checkpoint."""
        return self.checkpoints.get(execution_id)

    def get_execution_status(
        self,
        results: Dict[str, StepResult],
    ) -> str:
        """
        Get overall execution status.

        Args:
            results: Step results

        Returns:
            "success", "partial_success", or "failed"
        """
        if not results:
            return "failed"

        failed = [r for r in results.values() if r.status == "failed"]
        interrupted = [r for r in results.values() if r.status == "interrupted"]

        if not failed and not interrupted:
            return "success"
        elif failed:
            return "failed"
        else:
            return "partial_success"

    def get_execution_summary(
        self,
        results: Dict[str, StepResult],
    ) -> Dict[str, Any]:
        """Get summary of execution."""
        total_duration = sum(r.duration_seconds for r in results.values())
        failed_count = sum(1 for r in results.values() if r.status == "failed")
        success_count = sum(1 for r in results.values() if r.status == "success")

        return {
            "status": self.get_execution_status(results),
            "total_steps": len(results),
            "successful": success_count,
            "failed": failed_count,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": total_duration / len(results) if results else 0,
        }
