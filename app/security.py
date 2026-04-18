from __future__ import annotations

from functools import wraps

from flask import abort, current_app, g, request, session
from flask_login import current_user


def get_active_empresa_id() -> int | None:
    """Resolve the active empresa_id from the session.

    If the stored value is invalid, falls back to the user's preferred
    empresa and persists it in the session.
    """
    empresa_id = session.get("active_empresa_id")
    if empresa_id and current_user.is_authenticated and current_user.can_access_empresa(
        empresa_id
    ):
        return empresa_id
    if current_user.is_authenticated:
        empresa = current_user.preferred_empresa()
        if empresa is not None:
            empresa_id = empresa.id
            session["active_empresa_id"] = empresa_id
            return empresa_id
    return None


def role_required(*allowed_roles: str):
    """Decorator that checks the user has one of the required roles."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            # Reuse g.active_role set by before_request; recalc only if missing
            role = g.get("active_role")
            if role is None:
                empresa_id = g.get("active_empresa_id") or get_active_empresa_id()
                role = current_user.role_for_empresa(empresa_id)
            if role not in allowed_roles:
                current_app.logger.warning(
                    "role_required DENIED user=%s role=%s required=%s path=%s",
                    current_user.id, role, allowed_roles, request.path,
                )
                abort(403)
            g.active_role = role
            return view(*args, **kwargs)
        return wrapped_view
    return decorator


def permission_required(*required_permissions: str):
    """Decorator that checks the user has ALL of the required permissions."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            empresa_id = g.get("active_empresa_id") or get_active_empresa_id()
            missing = [
                permission
                for permission in required_permissions
                if not current_user.has_permission(permission, empresa_id)
            ]
            if missing:
                current_app.logger.warning(
                    "permission_required DENIED user=%s missing=%s path=%s",
                    current_user.id, missing, request.path,
                )
                abort(403)
            # Cache permissions in g for the rest of the request
            g.active_permissions = current_user.permissions_for_empresa(empresa_id)
            return view(*args, **kwargs)
        return wrapped_view
    return decorator
