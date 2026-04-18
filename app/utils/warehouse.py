"""Warehouse access control helpers — unified from compras, inventario, ventas."""

from __future__ import annotations

from flask import abort, g
from flask_login import current_user

from app.models import Almacen


def allowed_warehouse_ids(empresa_id: int) -> set[int] | None:
    """Return the set of warehouse IDs the current user can access.

    Returns ``None`` when the user has no warehouse-level restrictions
    (i.e. unrestricted access — typically admins or users without
    explicit warehouse assignments).
    """
    return current_user.allowed_warehouse_ids(empresa_id)


def warehouse_query(empresa_id: int, *, active_only: bool = True):
    """Build an ``Almacen`` query scoped to *empresa_id* and the current
    user's permitted warehouses.

    Parameters
    ----------
    empresa_id:
        Company to filter by.
    active_only:
        When *True* (the default) only active warehouses are returned.
    """
    query = Almacen.query.filter_by(empresa_id=empresa_id)
    if active_only:
        query = query.filter_by(activo=True)
    ids = allowed_warehouse_ids(empresa_id)
    if ids is not None:
        query = query.filter(Almacen.id.in_(sorted(ids)))
    return query


def warehouse_or_403(empresa_id: int, almacen_id: int, *, active_only: bool = True) -> Almacen:
    """Return the warehouse if accessible, otherwise abort with 403."""
    warehouse = warehouse_query(empresa_id, active_only=active_only).filter(
        Almacen.id == almacen_id
    ).first()
    if warehouse is None:
        abort(403)
    return warehouse
