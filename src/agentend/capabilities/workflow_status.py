"""Workflow status capability: returns workflow runs list or detail."""

import logging
from typing import Any, Dict

from agentend.kernel.kernel import RequestContext

logger = logging.getLogger(__name__)


class WorkflowStatusCapability:
    """Returns workflow runs list or detail for a specific run.

    Queries the persistence layer for workflow runs belonging to the
    current tenant. If a run_id is provided in the intent kwargs,
    returns detail for that specific run.
    """

    name: str = "workflow.status"
    description: str = "Returns workflow runs list or detail for a specific run"

    async def execute(self, context: RequestContext, **kwargs: Any) -> Dict[str, Any]:
        """Return workflow run status.

        Args:
            context: Request context with tenant_id and app state in metadata.
            **kwargs: Optional run_id for single-run detail.

        Returns:
            Dict with run list or single run detail.
        """
        session_factory = context.metadata.get("session_factory")
        tenant_id = context.tenant_id
        run_id = kwargs.get("run_id")

        if session_factory is None:
            return {
                "capability": "workflow.status",
                "error": "Database not available",
                "runs": [],
            }

        if not tenant_id:
            return {
                "capability": "workflow.status",
                "error": "No tenant_id in context",
                "runs": [],
            }

        try:
            from agentend.persistence.repositories import RunRepository

            async with session_factory() as db_session:
                repo = RunRepository(db_session)

                if run_id:
                    run = await repo.get_by_id(run_id)
                    if run is None or run.tenant_id != tenant_id:
                        return {
                            "capability": "workflow.status",
                            "error": f"Run {run_id} not found",
                        }
                    return {
                        "capability": "workflow.status",
                        "run": {
                            "id": run.id,
                            "workflow": run.workflow,
                            "status": run.status,
                            "input_params": run.input_params,
                            "output_result": run.output_result,
                            "error_message": run.error_message,
                            "priority": run.priority,
                            "created_at": run.created_at.isoformat() if run.created_at else None,
                            "started_at": run.started_at.isoformat() if run.started_at else None,
                            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                        },
                    }

                # List recent runs for tenant
                user_id = context.user_id
                runs = await repo.get_by_tenant_user(tenant_id, user_id, limit=50)
                run_list = []
                for r in runs:
                    run_list.append({
                        "id": r.id,
                        "workflow": r.workflow,
                        "status": r.status,
                        "priority": r.priority,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    })

                return {
                    "capability": "workflow.status",
                    "tenant_id": tenant_id,
                    "count": len(run_list),
                    "runs": run_list,
                }
        except ImportError:
            return {
                "capability": "workflow.status",
                "error": "SQLAlchemy not installed",
                "runs": [],
            }
        except Exception as e:
            logger.warning(f"Failed to get workflow status: {e}")
            return {
                "capability": "workflow.status",
                "error": str(e),
                "runs": [],
            }
