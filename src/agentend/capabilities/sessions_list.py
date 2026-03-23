"""Sessions list capability: returns recent sessions for current tenant."""

import logging
from typing import Any, Dict

from agentend.kernel.kernel import RequestContext

logger = logging.getLogger(__name__)


class SessionsListCapability:
    """Returns recent sessions for the current tenant.

    Queries the persistence layer for sessions belonging to the
    authenticated tenant and returns summary information.
    """

    name: str = "sessions.list"
    description: str = "Returns recent sessions for current tenant"

    async def execute(self, context: RequestContext, **kwargs: Any) -> Dict[str, Any]:
        """Return recent sessions for the current tenant.

        Args:
            context: Request context with tenant_id and app state in metadata.

        Returns:
            Dict with list of recent sessions.
        """
        session_factory = context.metadata.get("session_factory")
        tenant_id = context.tenant_id

        if session_factory is None:
            return {
                "capability": "sessions.list",
                "error": "Database not available",
                "sessions": [],
            }

        if not tenant_id:
            return {
                "capability": "sessions.list",
                "error": "No tenant_id in context",
                "sessions": [],
            }

        try:
            from agentend.persistence.repositories import SessionRepository

            async with session_factory() as db_session:
                repo = SessionRepository(db_session)
                sessions = await repo.get_by_status(tenant_id, "created", limit=50)
                # Also get active sessions
                active = await repo.get_by_status(tenant_id, "active", limit=50)
                all_sessions = list(sessions) + list(active)

                session_list = []
                for s in all_sessions:
                    session_list.append({
                        "id": s.id,
                        "user_id": s.user_id,
                        "capability": s.capability,
                        "status": s.status,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    })

                return {
                    "capability": "sessions.list",
                    "tenant_id": tenant_id,
                    "count": len(session_list),
                    "sessions": session_list,
                }
        except ImportError:
            return {
                "capability": "sessions.list",
                "error": "SQLAlchemy not installed",
                "sessions": [],
            }
        except Exception as e:
            logger.warning(f"Failed to list sessions: {e}")
            return {
                "capability": "sessions.list",
                "error": str(e),
                "sessions": [],
            }
