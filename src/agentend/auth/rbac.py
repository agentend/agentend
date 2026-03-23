"""Role-based access control (RBAC) system."""

from enum import Enum
from typing import Callable, Optional
from functools import wraps

from fastapi import Depends, HTTPException, status

from agentend.auth.middleware import get_current_user
from agentend.auth.jwt import TokenPayload


class CapabilityPermission(str, Enum):
    """Capability-based permissions."""

    EXECUTE = "execute"
    MANAGE_AGENTS = "manage_agents"
    MANAGE_FLEET = "manage_fleet"
    MANAGE_WORKERS = "manage_workers"
    VIEW_METRICS = "view_metrics"
    MANAGE_USERS = "manage_users"
    MANAGE_TENANTS = "manage_tenants"
    ADMIN = "admin"


class Role(str, Enum):
    """User roles with capability mappings."""

    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    SERVICE = "service"


# Role to capability mappings
ROLE_PERMISSIONS = {
    Role.ADMIN: [
        CapabilityPermission.ADMIN,
        CapabilityPermission.EXECUTE,
        CapabilityPermission.MANAGE_AGENTS,
        CapabilityPermission.MANAGE_FLEET,
        CapabilityPermission.MANAGE_WORKERS,
        CapabilityPermission.VIEW_METRICS,
        CapabilityPermission.MANAGE_USERS,
        CapabilityPermission.MANAGE_TENANTS,
    ],
    Role.MANAGER: [
        CapabilityPermission.EXECUTE,
        CapabilityPermission.MANAGE_AGENTS,
        CapabilityPermission.MANAGE_FLEET,
        CapabilityPermission.VIEW_METRICS,
    ],
    Role.USER: [
        CapabilityPermission.EXECUTE,
    ],
    Role.SERVICE: [
        CapabilityPermission.EXECUTE,
        CapabilityPermission.VIEW_METRICS,
    ],
}


def require_capability(capability: CapabilityPermission) -> Callable:
    """
    Decorator to require a specific capability.

    Args:
        capability: Required capability.

    Returns:
        Decorator function.

    Example:
        @app.post("/manage")
        @require_capability(CapabilityPermission.MANAGE_AGENTS)
        async def manage_agents(current_user: TokenPayload = Depends(get_current_user)):
            ...
    """

    async def check_capability(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        """Check if user has capability."""
        if capability in current_user.capabilities:
            return current_user

        # Check role-based permissions
        user_roles = [Role(r) for r in current_user.roles if r in [r.value for r in Role]]
        for role in user_roles:
            if capability in ROLE_PERMISSIONS.get(role, []):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required capability: {capability}",
        )

    return Depends(check_capability)


def require_role(role: Role) -> Callable:
    """
    Decorator to require a specific role.

    Args:
        role: Required role.

    Returns:
        Decorator function.

    Example:
        @app.post("/admin")
        @require_role(Role.ADMIN)
        async def admin_endpoint(current_user: TokenPayload = Depends(get_current_user)):
            ...
    """

    async def check_role(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        """Check if user has role."""
        if role.value in current_user.roles:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required role: {role}",
        )

    return Depends(check_role)


def check_tenant_access(user: TokenPayload, tenant_id: str) -> bool:
    """
    Check if user has access to tenant.

    Args:
        user: Current user.
        tenant_id: Tenant to access.

    Returns:
        True if user can access tenant.
    """
    if Role.ADMIN.value in user.roles:
        return True

    return user.tenant_id == tenant_id
