"""
HITLManager: Human-in-the-Loop interrupt and approval management.

Handles:
- Pause/resume execution
- Approval/rejection of steps
- Interrupt state persistence
- Timeout handling
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Callable, Awaitable

from .workflow import Step

logger = logging.getLogger(__name__)


@dataclass
class InterruptRequest:
    """Request for human intervention."""
    step: Step
    context: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    created_at: str = ""
    timeout_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        """Set default values."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.reason:
            self.reason = f"Step '{self.step.name}' requires human approval"


@dataclass
class InterruptState:
    """State of a human approval request."""
    request: InterruptRequest
    approved: Optional[bool] = None
    feedback: str = ""
    resolved_at: Optional[str] = None
    auto_timeout: bool = False


class HITLManager:
    """
    Manages human-in-the-loop approvals and interrupts.

    Persists interrupt state for recovery and audit.
    Supports automatic timeouts and escalation.
    """

    def __init__(
        self,
        approval_callback: Optional[Callable[[InterruptRequest], Awaitable[bool]]] = None,
        persistence_backend=None,
    ):
        """
        Initialize HITLManager.

        Args:
            approval_callback: Async callback for approval requests
            persistence_backend: Optional backend for persisting state
        """
        self.approval_callback = approval_callback
        self.persistence_backend = persistence_backend
        self._pending_interrupts: Dict[str, InterruptState] = {}
        self._resolved_interrupts: Dict[str, InterruptState] = {}

    async def request_approval(
        self,
        step: Step,
        context: Dict[str, Any] = None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """
        Request human approval for a step.

        Args:
            step: Step requiring approval
            context: Context for the approval request
            timeout_seconds: Optional timeout (auto-approve on timeout)

        Returns:
            True if approved, False if rejected
        """
        context = context or {}
        interrupt_request = InterruptRequest(
            step=step,
            context=context,
            reason=f"Step '{step.name}' requires human approval",
            timeout_seconds=timeout_seconds,
        )

        logger.info(f"Requesting approval for step: {step.name}")

        # Create interrupt state
        state = InterruptState(request=interrupt_request)
        request_id = f"{step.name}:{interrupt_request.created_at}"
        self._pending_interrupts[request_id] = state

        # Persist if backend available
        if self.persistence_backend:
            await self.persistence_backend.save_interrupt(request_id, state)

        # Wait for approval
        try:
            if timeout_seconds:
                approved = await asyncio.wait_for(
                    self._wait_for_approval(request_id),
                    timeout=timeout_seconds,
                )
            else:
                approved = await self._wait_for_approval(request_id)
        except asyncio.TimeoutError:
            logger.warning(f"Approval timeout for step {step.name}, auto-approving")
            state.approved = True
            state.auto_timeout = True
            state.resolved_at = datetime.utcnow().isoformat()
            approved = True

        # Move to resolved
        if request_id in self._pending_interrupts:
            del self._pending_interrupts[request_id]
            self._resolved_interrupts[request_id] = state

        return approved

    async def _wait_for_approval(self, request_id: str) -> bool:
        """Wait for approval on a request."""
        # If callback is provided, call it
        if self.approval_callback:
            state = self._pending_interrupts.get(request_id)
            if state:
                return await self.approval_callback(state.request)

        # Otherwise, poll for approval
        while True:
            state = self._pending_interrupts.get(request_id)
            if state and state.approved is not None:
                return state.approved
            await asyncio.sleep(0.1)

    async def approve(self, request_id: str, feedback: str = "") -> None:
        """
        Approve an interrupt request.

        Args:
            request_id: Request identifier
            feedback: Optional feedback
        """
        if request_id in self._pending_interrupts:
            state = self._pending_interrupts[request_id]
            state.approved = True
            state.feedback = feedback
            state.resolved_at = datetime.utcnow().isoformat()
            logger.info(f"Approved: {request_id}")

            if self.persistence_backend:
                await self.persistence_backend.save_interrupt(request_id, state)

    async def reject(self, request_id: str, reason: str = "") -> None:
        """
        Reject an interrupt request.

        Args:
            request_id: Request identifier
            reason: Reason for rejection
        """
        if request_id in self._pending_interrupts:
            state = self._pending_interrupts[request_id]
            state.approved = False
            state.feedback = reason
            state.resolved_at = datetime.utcnow().isoformat()
            logger.info(f"Rejected: {request_id}")

            if self.persistence_backend:
                await self.persistence_backend.save_interrupt(request_id, state)

    async def pause(self) -> None:
        """Pause all execution."""
        logger.info("Pausing execution")
        # Can be implemented with a global pause flag

    async def resume(self) -> None:
        """Resume execution."""
        logger.info("Resuming execution")

    def get_pending_interrupts(self) -> Dict[str, InterruptState]:
        """Get all pending approval requests."""
        return dict(self._pending_interrupts)

    def get_resolved_interrupts(self) -> Dict[str, InterruptState]:
        """Get all resolved interrupts."""
        return dict(self._resolved_interrupts)

    def get_interrupt_status(self, request_id: str) -> Optional[str]:
        """
        Get status of an interrupt request.

        Returns:
            "pending", "approved", "rejected", or None
        """
        if request_id in self._pending_interrupts:
            return "pending"
        elif request_id in self._resolved_interrupts:
            state = self._resolved_interrupts[request_id]
            return "approved" if state.approved else "rejected"
        return None

    async def clear_resolved(self) -> None:
        """Clear resolved interrupts."""
        self._resolved_interrupts.clear()

    async def get_audit_log(self) -> list[Dict[str, Any]]:
        """Get audit log of all interrupts."""
        log = []

        for request_id, state in self._resolved_interrupts.items():
            log.append({
                "request_id": request_id,
                "step_name": state.request.step.name,
                "created_at": state.request.created_at,
                "resolved_at": state.resolved_at,
                "approved": state.approved,
                "auto_timeout": state.auto_timeout,
                "feedback": state.feedback,
            })

        return log
