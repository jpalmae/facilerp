from __future__ import annotations

from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Almacen,
    AuditLog,
    MovimientoStock,
    PERM_INVENTORY_MANAGE,
    PERM_INVENTORY_VIEW,
    Producto,
    Stock,
)
from app.modules.inventario import bp
from app.modules.inventario.forms import MovementForm, ProductForm, WarehouseForm
from app.security import permission_required
from app.services.inventory import InventoryError, register_stock_movement
from app.utils.warehouse import allowed_warehouse_ids, warehouse_or_403, warehouse_query


def _empresa_id() -> int:
    return int(session["active_empresa_id"])





def _populate_inventory_choices(form) -> None:
    empresa_id = _empresa_id()
    form.producto_id.choices = [
        (item.id, f"{item.codigo} · {item.nombre}")
        for item in Producto.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(Producto.nombre.asc())
        .all()
    ]
    form.almacen_id.choices = [
        (item.id, item.nombre)
        for item in warehouse_query(empresa_id, active_only=True)
        .order_by(Almacen.nombre.asc())
        .all()
    ]


def _stock_status(available: Decimal, minimum: Decimal) -> str:
    if available <= Decimal("0.00"):
        return "Agotado"
    if minimum > Decimal("0.00") and available <= minimum:
        return "Bajo"
    return "Óptimo"


def _render_inventory_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    endpoint_map = {
        "productos": "inventario.products",
        "almacenes": "inventario.warehouses",
        "movimientos": "inventario.movements",
    }
    current_view_endpoint = endpoint_map[active_submodule]
    product_form = ProductForm(prefix="product")
    warehouse_form = WarehouseForm(prefix="warehouse")
    movement_form = MovementForm(prefix="move")
    _populate_inventory_choices(movement_form)

    if product_form.submit.data and product_form.validate_on_submit():
        if not current_user.has_permission(PERM_INVENTORY_MANAGE, empresa_id):
            return "", 403
        product = Producto(
            empresa_id=empresa_id,
            codigo=product_form.codigo.data.strip().upper(),
            nombre=product_form.nombre.data.strip(),
            categoria=(product_form.categoria.data or "").strip() or None,
            unidad_medida=product_form.unidad_medida.data.strip().upper(),
            tipo=product_form.tipo.data,
            precio_venta=product_form.precio_venta.data,
            stock_minimo=product_form.stock_minimo.data,
        )
        db.session.add(product)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                empresa_id=empresa_id,
                accion="inventario.producto.created",
            )
        )
        db.session.commit()
        flash("Producto creado.", "success")
        return redirect(url_for(current_view_endpoint))

    if warehouse_form.submit.data and warehouse_form.validate_on_submit():
        if not current_user.has_permission(PERM_INVENTORY_MANAGE, empresa_id):
            return "", 403
        warehouse = Almacen(
            empresa_id=empresa_id,
            nombre=warehouse_form.nombre.data.strip(),
            ubicacion=(warehouse_form.ubicacion.data or "").strip() or None,
        )
        db.session.add(warehouse)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                empresa_id=empresa_id,
                accion="inventario.almacen.created",
            )
        )
        db.session.commit()
        flash("Almacén creado.", "success")
        return redirect(url_for(current_view_endpoint))

    if movement_form.submit.data:
        if not current_user.has_permission(PERM_INVENTORY_MANAGE, empresa_id):
            return "", 403
        requested_warehouse_id = request.form.get(movement_form.almacen_id.name, type=int)
        if requested_warehouse_id is not None:
            warehouse_or_403(empresa_id, requested_warehouse_id, active_only=True)
    if movement_form.submit.data and movement_form.validate_on_submit():
        if not current_user.has_permission(PERM_INVENTORY_MANAGE, empresa_id):
            return "", 403
        producto = Producto.query.filter_by(
            id=movement_form.producto_id.data, empresa_id=empresa_id
        ).first_or_404()
        almacen = warehouse_or_403(
            empresa_id,
            movement_form.almacen_id.data,
            active_only=True,
        )
        try:
            register_stock_movement(
                empresa_id=empresa_id,
                producto=producto,
                almacen=almacen,
                tipo=movement_form.tipo.data,
                cantidad=movement_form.cantidad.data,
                costo_unitario=movement_form.costo_unitario.data or 0,
            )
        except InventoryError as exc:
            flash(str(exc), "error")
        else:
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    empresa_id=empresa_id,
                    accion=f"inventario.movimiento.{movement_form.tipo.data}",
                )
            )
            db.session.commit()
            flash("Movimiento registrado.", "success")
            return redirect(url_for(current_view_endpoint))

    search_query = (request.args.get("q") or "").strip()
    selected_status = (request.args.get("status") or "").strip() or "todos"
    selected_warehouse_id = request.args.get("warehouse", type=int)
    if selected_warehouse_id is not None:
        warehouse_or_403(empresa_id, selected_warehouse_id)

    productos = (
        Producto.query.filter_by(empresa_id=empresa_id)
        .order_by(Producto.nombre.asc())
        .all()
    )
    almacenes = warehouse_query(empresa_id).order_by(Almacen.nombre.asc()).all()
    stock_rows_query = (
        db.session.query(Stock, Producto, Almacen)
        .join(Producto, Stock.producto_id == Producto.id)
        .join(Almacen, Stock.almacen_id == Almacen.id)
        .filter(Producto.empresa_id == empresa_id)
    )
    movimientos_query = (
        db.session.query(MovimientoStock, Producto, Almacen)
        .join(Producto, MovimientoStock.producto_id == Producto.id)
        .join(Almacen, MovimientoStock.almacen_id == Almacen.id)
        .filter(MovimientoStock.empresa_id == empresa_id)
    )
    allowed_ids = allowed_warehouse_ids(empresa_id)
    if allowed_ids is not None:
        stock_rows_query = stock_rows_query.filter(Almacen.id.in_(sorted(allowed_ids)))
        movimientos_query = movimientos_query.filter(Almacen.id.in_(sorted(allowed_ids)))
    if selected_warehouse_id is not None:
        stock_rows_query = stock_rows_query.filter(Almacen.id == selected_warehouse_id)
        movimientos_query = movimientos_query.filter(Almacen.id == selected_warehouse_id)
    stock_rows = stock_rows_query.order_by(Producto.nombre.asc(), Almacen.nombre.asc()).all()
    movimientos = (
        movimientos_query.order_by(MovimientoStock.fecha.desc(), MovimientoStock.id.desc())
        .limit(10)
        .all()
    )
    stock_by_product: dict[int, dict[str, object]] = {}
    for stock, producto, almacen in stock_rows:
        record = stock_by_product.setdefault(
            producto.id,
            {
                "producto": producto,
                "disponible": Decimal("0.00"),
                "reservado": Decimal("0.00"),
                "almacenes": [],
            },
        )
        record["disponible"] += Decimal(str(stock.cantidad_disponible or 0))
        record["reservado"] += Decimal(str(stock.cantidad_reservada or 0))
        record["almacenes"].append(almacen.nombre)

    product_summaries = []
    normalized_query = search_query.lower()
    for producto in productos:
        record = stock_by_product.get(
            producto.id,
            {
                "producto": producto,
                "disponible": Decimal("0.00"),
                "reservado": Decimal("0.00"),
                "almacenes": [],
            },
        )
        status = _stock_status(
            Decimal(str(record["disponible"])),
            Decimal(str(producto.stock_minimo or 0)),
        )
        haystack = " ".join(
            [
                (producto.codigo or ""),
                (producto.nombre or ""),
                (producto.categoria or ""),
                " ".join(record["almacenes"]),
            ]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        if selected_status != "todos" and status.lower() != selected_status.lower():
            continue
        product_summaries.append(
            {
                "producto": producto,
                "disponible": record["disponible"],
                "reservado": record["reservado"],
                "status": status,
                "almacenes": record["almacenes"],
            }
        )

    filtered_movimientos = []
    for movimiento, producto, almacen in movimientos:
        haystack = " ".join(
            [producto.nombre or "", producto.codigo or "", almacen.nombre or "", movimiento.tipo or ""]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        filtered_movimientos.append((movimiento, producto, almacen))

    low_stock_count = sum(1 for item in product_summaries if item["status"] == "Bajo")
    depleted_count = sum(1 for item in product_summaries if item["status"] == "Agotado")
    inventory_value = sum(
        item["disponible"] * Decimal(str(item["producto"].costo_promedio or 0))
        for item in product_summaries
    )
    return render_template(
        "inventario/dashboard.html",
        product_form=product_form,
        warehouse_form=warehouse_form,
        movement_form=movement_form,
        productos=productos,
        almacenes=almacenes,
        stock_rows=stock_rows,
        movimientos=filtered_movimientos,
        product_summaries=product_summaries,
        search_query=search_query,
        selected_status=selected_status,
        selected_warehouse_id=selected_warehouse_id,
        inventory_value=inventory_value,
        low_stock_count=low_stock_count,
        depleted_count=depleted_count,
        can_write=current_user.has_permission(PERM_INVENTORY_MANAGE, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_INVENTORY_VIEW)
def dashboard():
    if request.method == "POST":
        if request.form.get("warehouse-submit"):
            return _render_inventory_workspace("almacenes")
        if request.form.get("move-submit"):
            return _render_inventory_workspace("movimientos")
        return _render_inventory_workspace("productos")

    empresa_id = _empresa_id()
    products = Producto.query.filter_by(empresa_id=empresa_id, activo=True).count()
    warehouses = warehouse_query(empresa_id).count()
    movements = MovimientoStock.query.filter_by(empresa_id=empresa_id).count()
    return render_template(
        "dashboard/module_hub.html",
        module_title="Inventario",
        module_heading="Inventario",
        module_badges=[
            {"label": "Operación física", "color": "blue"},
            {"label": f"{warehouses} almacenes"},
        ],
        module_stats=[
            {"label": "Productos", "value": products, "meta": "SKUs activos en la empresa."},
            {"label": "Almacenes", "value": warehouses, "meta": "Ubicaciones visibles según permisos."},
            {"label": "Movimientos", "value": movements, "meta": "Registros acumulados del módulo."},
        ],
        module_actions=[
            {"label": "Productos", "href": url_for("inventario.products"), "primary": True},
            {"label": "Movimientos", "href": url_for("inventario.movements")},
        ],
        module_children=[
            {
                "label": "Productos",
                "href": url_for("inventario.products"),
                "description": "Consulta stock, filtra SKUs y registra productos nuevos.",
            },
            {
                "label": "Almacenes",
                "href": url_for("inventario.warehouses"),
                "description": "Administra ubicaciones físicas y su alcance operativo.",
            },
            {
                "label": "Movimientos",
                "href": url_for("inventario.movements"),
                "description": "Registra ingresos, salidas y revisa el flujo reciente de stock.",
            },
        ],
    )


@bp.route("/productos", methods=["GET", "POST"])
@login_required
@permission_required(PERM_INVENTORY_VIEW)
def products():
    return _render_inventory_workspace("productos")


@bp.route("/almacenes", methods=["GET", "POST"])
@login_required
@permission_required(PERM_INVENTORY_VIEW)
def warehouses():
    return _render_inventory_workspace("almacenes")


@bp.route("/movimientos", methods=["GET", "POST"])
@login_required
@permission_required(PERM_INVENTORY_VIEW)
def movements():
    return _render_inventory_workspace("movimientos")
