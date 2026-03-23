"""
A2AClient: Delegates tasks to peer agents via Agent-to-Agent protocol.

Allows one agent to request another agent to perform tasks.
Handles A2A task lifecycle and result aggregation.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class A2ATask:
    """Task to be delegated to another agent."""
    id: str
    peer_agent_url: str
    task_description: str
    context: Dict[str, Any]
    timeout_seconds: int = 300


@dataclass
class A2AResult:
    """Result from an A2A task."""
    task_id: str
    status: str  # "pending", "success", "failed", "timeout"
    result: Any = None
    error: Optional[str] = None
    response_time_seconds: float = 0.0


class A2AClient:
    """
    Client for Agent-to-Agent communication.

    Delegates tasks to peer agents and aggregates results.
    """

    def __init__(self, http_client=None):
        """
        Initialize A2A client.

        Args:
            http_client: Optional async HTTP client (aiohttp.ClientSession)
        """
        self.http_client = http_client
        self._pending_tasks: Dict[str, A2ATask] = {}
        self._results: Dict[str, A2AResult] = {}

    async def delegate(
        self,
        peer_url: str,
        task: str,
        context: Dict[str, Any] = None,
        timeout_seconds: int = 300,
    ) -> A2AResult:
        """
        Delegate a task to a peer agent.

        Args:
            peer_url: URL of peer agent (base URL, without /a2a endpoint)
            task: Task description or instruction
            context: Context to pass to peer agent
            timeout_seconds: Task timeout

        Returns:
            A2AResult with status and outcome
        """
        import uuid
        import time

        task_id = str(uuid.uuid4())
        context = context or {}

        # Create task
        a2a_task = A2ATask(
            id=task_id,
            peer_agent_url=peer_url,
            task_description=task,
            context=context,
            timeout_seconds=timeout_seconds,
        )

        self._pending_tasks[task_id] = a2a_task
        logger.info(f"Delegating task {task_id} to {peer_url}")

        start_time = time.time()

        try:
            # Send task to peer agent
            result = await self._invoke_peer_agent(a2a_task)
            elapsed = time.time() - start_time

            # Store result
            a2a_result = A2AResult(
                task_id=task_id,
                status="success",
                result=result,
                response_time_seconds=elapsed,
            )
            self._results[task_id] = a2a_result

            return a2a_result

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"Task {task_id} timed out after {timeout_seconds}s")

            a2a_result = A2AResult(
                task_id=task_id,
                status="timeout",
                error=f"Timeout after {timeout_seconds}s",
                response_time_seconds=elapsed,
            )
            self._results[task_id] = a2a_result

            return a2a_result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Task {task_id} failed: {e}")

            a2a_result = A2AResult(
                task_id=task_id,
                status="failed",
                error=str(e),
                response_time_seconds=elapsed,
            )
            self._results[task_id] = a2a_result

            return a2a_result

        finally:
            # Clean up pending
            if task_id in self._pending_tasks:
                del self._pending_tasks[task_id]

    async def _invoke_peer_agent(self, task: A2ATask) -> Any:
        """
        Invoke a task on the peer agent.

        Args:
            task: A2A task

        Returns:
            Result from peer agent
        """
        # Build request payload
        payload = {
            "task_id": task.id,
            "task": task.task_description,
            "context": task.context,
        }

        # Determine endpoint
        endpoint = f"{task.peer_agent_url.rstrip('/')}/a2a/invoke"

        logger.debug(f"Invoking {endpoint} with task {task.id}")

        # Make HTTP request
        if self.http_client is None:
            # Use a simple mock for now
            logger.debug(f"Mock invoke to {endpoint}")
            return {"status": "success", "data": f"Completed: {task.task_description}"}

        try:
            # In production, use actual HTTP client
            # response = await self.http_client.post(
            #     endpoint,
            #     json=payload,
            #     timeout=task.timeout_seconds,
            # )
            # return await response.json()

            # For now, return mock response
            return {"status": "success", "data": f"Completed: {task.task_description}"}

        except Exception as e:
            logger.error(f"Failed to invoke peer agent: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Optional[str]:
        """
        Get status of a delegated task.

        Args:
            task_id: Task ID

        Returns:
            Status string or None if not found
        """
        if task_id in self._pending_tasks:
            return "pending"
        elif task_id in self._results:
            return self._results[task_id].status
        return None

    async def get_result(self, task_id: str) -> Optional[A2AResult]:
        """
        Get result of a completed task.

        Args:
            task_id: Task ID

        Returns:
            A2AResult or None if not found
        """
        return self._results.get(task_id)

    async def delegate_batch(
        self,
        peer_url: str,
        tasks: List[Dict[str, Any]],
        parallel: bool = True,
    ) -> List[A2AResult]:
        """
        Delegate multiple tasks to the same peer.

        Args:
            peer_url: Peer agent URL
            tasks: List of task descriptions or dicts with task and context
            parallel: Whether to run in parallel

        Returns:
            List of results
        """
        task_objects = []

        for task_spec in tasks:
            if isinstance(task_spec, str):
                task_description = task_spec
                context = {}
            else:
                task_description = task_spec.get("task", "")
                context = task_spec.get("context", {})

            task_objects.append((task_description, context))

        if parallel:
            # Run in parallel
            results = await asyncio.gather(*[
                self.delegate(peer_url, task_desc, context)
                for task_desc, context in task_objects
            ])
        else:
            # Run sequentially
            results = []
            for task_desc, context in task_objects:
                result = await self.delegate(peer_url, task_desc, context)
                results.append(result)

        return results

    def get_pending_tasks(self) -> List[A2ATask]:
        """Get all pending tasks."""
        return list(self._pending_tasks.values())

    def get_completed_results(self) -> List[A2AResult]:
        """Get all completed results."""
        return list(self._results.values())

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        results = list(self._results.values())
        successful = [r for r in results if r.status == "success"]
        failed = [r for r in results if r.status == "failed"]
        timeout = [r for r in results if r.status == "timeout"]

        avg_response_time = (
            sum(r.response_time_seconds for r in results) / len(results)
            if results else 0
        )

        return {
            "pending_tasks": len(self._pending_tasks),
            "completed_tasks": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "timeout": len(timeout),
            "average_response_time_seconds": avg_response_time,
        }

    async def clear_results(self) -> None:
        """Clear all stored results."""
        self._results.clear()
