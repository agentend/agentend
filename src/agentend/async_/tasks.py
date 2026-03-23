"""Async task management and execution."""

from typing import Optional, Dict, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
import logging

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
except ImportError:
    AsyncSession = None
    async_sessionmaker = None

from agentend.persistence.models import Run, Session as SessionModel
from agentend.persistence.repositories import RunRepository, SessionRepository
from agentend.observability.traces import traced


logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Status of a run."""

    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AsyncTaskManager:
    """
    Manages async workflow execution, polling, and streaming.

    Handles fire-and-forget submissions, status polling, and
    WebSocket/SSE streaming for long-running tasks.
    """

    def __init__(self, session_factory):
        """
        Initialize task manager.

        Args:
            session_factory: SQLAlchemy async session factory.
        """
        if async_sessionmaker is None:
            raise ImportError("Install agentend[persistence] for SQLAlchemy support")
        self.session_factory = session_factory

    @traced("create_session")
    async def create_session(self, session: SessionModel) -> None:
        """
        Create a new session.

        Args:
            session: Session to create.
        """
        async with self.session_factory() as db:
            db.add(session)
            await db.commit()

    @traced("submit_workflow")
    async def submit_workflow(
        self,
        run_id: str,
        workflow: str,
        parameters: Dict[str, Any],
        tenant_id: str,
        user_id: str,
        priority: int = 0,
    ) -> None:
        """
        Submit an async workflow for execution.

        Args:
            run_id: Run identifier.
            workflow: Workflow name.
            parameters: Workflow parameters.
            tenant_id: Tenant identifier.
            user_id: User identifier.
            priority: Execution priority.
        """
        async with self.session_factory() as db:
            run = Run(
                id=run_id,
                tenant_id=tenant_id,
                user_id=user_id,
                workflow=workflow,
                status=RunStatus.SUBMITTED.value,
                input_params=parameters,
                priority=priority,
                created_at=datetime.utcnow(),
            )

            db.add(run)
            await db.commit()

            logger.info(
                f"Submitted workflow",
                extra={
                    "run_id": run_id,
                    "workflow": workflow,
                    "tenant_id": tenant_id,
                    "priority": priority,
                }
            )

    @traced("poll_run_status")
    async def poll_run_status(
        self,
        run_id: str,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Poll status of a run.

        Args:
            run_id: Run identifier.
            tenant_id: Tenant identifier.

        Returns:
            Run status dict or None if not found.
        """
        async with self.session_factory() as db:
            repo = RunRepository(db)
            run = await repo.get_by_id(run_id)

            if not run or run.tenant_id != tenant_id:
                return None

            return {
                "run_id": run.id,
                "status": run.status,
                "workflow": run.workflow,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "result": run.output_result,
                "error": run.error_message,
                "progress": self._calculate_progress(run),
            }

    @traced("stream_session")
    async def stream_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream events from a session.

        Args:
            session_id: Session identifier.
            tenant_id: Tenant identifier.

        Yields:
            Event dictionaries for streaming.
        """
        async with self.session_factory() as db:
            repo = SessionRepository(db)
            session = await repo.get_by_id(session_id)

            if not session or session.tenant_id != tenant_id:
                yield {
                    "type": "error",
                    "error": "Session not found",
                }
                return

            # Stream session status updates
            yield {
                "type": "session_started",
                "session_id": session_id,
                "capability": session.capability,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Simulate streaming updates (in production, would listen to task queue)
            for i in range(3):
                yield {
                    "type": "processing",
                    "message": f"Processing step {i+1}",
                    "progress": (i + 1) * 33,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            yield {
                "type": "session_completed",
                "session_id": session_id,
                "status": session.status,
                "timestamp": datetime.utcnow().isoformat(),
            }

    @traced("resume_from_checkpoint")
    async def resume_from_checkpoint(
        self,
        run_id: str,
        checkpoint_number: int,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Resume run from checkpoint.

        Args:
            run_id: Run identifier.
            checkpoint_number: Checkpoint to resume from.
            tenant_id: Tenant identifier.

        Returns:
            Checkpoint state for resumption.
        """
        async with self.session_factory() as db:
            repo = RunRepository(db)
            run = await repo.get_by_id(run_id)

            if not run or run.tenant_id != tenant_id:
                return None

            # Update run status to processing
            run.status = RunStatus.PROCESSING.value
            run.started_at = datetime.utcnow()
            await db.commit()

            # In production, would fetch actual checkpoint from CheckpointRepository
            return {
                "run_id": run_id,
                "checkpoint_number": checkpoint_number,
                "resumed_at": datetime.utcnow().isoformat(),
                "state": {},
            }

    async def update_run_status(
        self,
        run_id: str,
        tenant_id: str,
        status: RunStatus,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update run status.

        Args:
            run_id: Run identifier.
            tenant_id: Tenant identifier.
            status: New status.
            result: Optional result data.
            error: Optional error message.
        """
        async with self.session_factory() as db:
            repo = RunRepository(db)
            run = await repo.get_by_id(run_id)

            if not run or run.tenant_id != tenant_id:
                return

            run.status = status.value

            if status == RunStatus.COMPLETED:
                run.completed_at = datetime.utcnow()
                run.output_result = result

            elif status == RunStatus.FAILED:
                run.completed_at = datetime.utcnow()
                run.error_message = error

            await db.commit()

    async def list_pending_runs(self, tenant_id: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        List all pending runs.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            List of pending runs.
        """
        async with self.session_factory() as db:
            repo = RunRepository(db)
            runs = await repo.get_pending_runs(tenant_id)

            return [
                {
                    "run_id": r.id,
                    "workflow": r.workflow,
                    "status": r.status,
                    "priority": r.priority,
                    "created_at": r.created_at.isoformat(),
                }
                for r in runs
            ]

    def _calculate_progress(self, run: Run) -> int:
        """
        Calculate run progress percentage.

        Args:
            run: Run object.

        Returns:
            Progress 0-100.
        """
        if run.status == RunStatus.COMPLETED.value:
            return 100
        elif run.status == RunStatus.FAILED.value:
            return 100
        elif run.status == RunStatus.PROCESSING.value:
            return 50
        else:
            return 0
