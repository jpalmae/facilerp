from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Almacen,
    AuditLog,
    OrdenCompra,
    PERM_PURCHASES_MANAGE,
    PERM_PURCHASES_VIEW,
    Producto,
    Proveedor,
    Recepcion,
)
from app.modules.compras import bp
from app.modules.compras.forms import PurchaseOrderForm, ReceptionForm, SupplierForm
from app.security import permission_required
from app.services.purchases import PurchaseError, create_purchase_order, receive_purchase_order
from app.services.external import validate_ruc
from app.utils.warehouse import allowed_warehouse_ids, warehouse_or_403, warehouse_query


def _empresa_id() -> int:
    return int(session["active_empresa_id"])


def _populate_forms(order_form: PurchaseOrderForm, reception_form: ReceptionForm) -> None:
    empresa_id = _empresa_id()
    order_form.proveedor_id.choices = [
        (item.id, item.razon_social)
        for item in Proveedor.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(Proveedor.razon_social.asc())
        .all()
    ]
    order_form.producto_id.choices = [
        (item.id, f"{item.codigo} · {item.nombre}")
        for item in Producto.query.filter_by(empresa_id=empresa_id, activo=True, tipo="bien")
        .order_by(Producto.nombre.asc())
        .all()
    ]
    reception_form.oc_id.choices = [
        (item.id, f"OC-{item.id:04d} · {item.proveedor.razon_social}")
        for item in OrdenCompra.query.filter(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.estado.in_(["emitida", "parcial"]),
        )
        .order_by(OrdenCompra.id.desc())
        .all()
    ]
    reception_form.almacen_id.choices = [
        (item.id, item.nombre)
        for item in warehouse_query(empresa_id)
        .order_by(Almacen.nombre.asc())
        .all()
    ]


def _purchase_status(orden: OrdenCompra) -> str:
    estado = (orden.estado or "").lower()
    if estado in {"cerrada", "recibida"}:
        return "Recibida"
    if estado == "parcial":
        return "Parcial"
    return "Emitida"


def _render_purchase_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    endpoint_map = {
        "ordenes": "compras.orders",
        "proveedores": "compras.suppliers",
    }
    current_view_endpoint = endpoint_map[active_submodule]
    supplier_form = SupplierForm(prefix="supplier")
    order_form = PurchaseOrderForm(prefix="order")
    reception_form = ReceptionForm(prefix="receipt")
    if not order_form.fecha.data:
        order_form.fecha.data = date.today()
    if not reception_form.fecha.data:
        reception_form.fecha.data = date.today()
    _populate_forms(order_form, reception_form)

    if supplier_form.submit.data and supplier_form.validate_on_submit():
        if not current_user.has_permission(PERM_PURCHASES_MANAGE, empresa_id):
            return "", 403
        validation = validate_ruc(supplier_form.ruc.data.strip())
        if not validation.valid:
            flash(validation.message or "RUC inválido.", "error")
            return redirect(url_for(current_view_endpoint))
        supplier = Proveedor(
            empresa_id=empresa_id,
            ruc=supplier_form.ruc.data.strip(),
            razon_social=supplier_form.razon_social.data.strip(),
            condicion_pago=supplier_form.condicion_pago.data,
        )
        db.session.add(supplier)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                empresa_id=empresa_id,
                accion="compras.proveedor.created",
            )
        )
        db.session.commit()
        flash(validation.message or "Proveedor creado.", "success")
        return redirect(url_for(current_view_endpoint))

    if order_form.submit.data and order_form.validate_on_submit():
        if not current_user.has_permission(PERM_PURCHASES_MANAGE, empresa_id):
            return "", 403
        producto = Producto.query.filter_by(
            id=order_form.producto_id.data, empresa_id=empresa_id
        ).first_or_404()
        try:
            create_purchase_order(
                empresa_id=empresa_id,
                proveedor_id=order_form.proveedor_id.data,
                producto=producto,
                cantidad=order_form.cantidad.data,
                precio_unitario=order_form.precio_unitario.data,
                fecha=order_form.fecha.data,
                observaciones=order_form.observaciones.data,
            )
        except PurchaseError as exc:
            flash(str(exc), "error")
        else:
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    empresa_id=empresa_id,
                    accion="compras.oc.created",
                )
            )
            db.session.commit()
            flash("Orden de compra emitida.", "success")
            return redirect(url_for(current_view_endpoint))

    if reception_form.submit.data:
        if not current_user.has_permission(PERM_PURCHASES_MANAGE, empresa_id):
            return "", 403
        requested_warehouse_id = request.form.get(reception_form.almacen_id.name, type=int)
        if requested_warehouse_id is not None:
            warehouse_or_403(empresa_id, requested_warehouse_id)
    if reception_form.submit.data and reception_form.validate_on_submit():
        if not current_user.has_permission(PERM_PURCHASES_MANAGE, empresa_id):
            return "", 403
        orden = OrdenCompra.query.filter_by(
            id=reception_form.oc_id.data, empresa_id=empresa_id
        ).first_or_404()
        almacen = warehouse_or_403(empresa_id, reception_form.almacen_id.data)
        try:
            receive_purchase_order(
                orden=orden,
                almacen=almacen,
                cantidad_recibida=reception_form.cantidad_recibida.data,
                fecha=reception_form.fecha.data,
            )
        except PurchaseError as exc:
            flash(str(exc), "error")
        else:
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    empresa_id=empresa_id,
                    accion="compras.recepcion.created",
                )
            )
            db.session.commit()
            flash("Recepción registrada y stock actualizado.", "success")
            return redirect(url_for("compras.dashboard"))

    proveedores = (
        Proveedor.query.filter_by(empresa_id=empresa_id)
        .order_by(Proveedor.razon_social.asc())
        .all()
    )
    ordenes = (
        OrdenCompra.query.filter_by(empresa_id=empresa_id)
        .order_by(OrdenCompra.id.desc())
        .all()
    )
    recepciones_query = Recepcion.query.filter_by(empresa_id=empresa_id)
    allowed_ids = allowed_warehouse_ids(empresa_id)
    if allowed_ids is not None:
        recepciones_query = recepciones_query.filter(
            Recepcion.almacen_id.in_(sorted(allowed_ids))
        )
    recepciones = recepciones_query.order_by(Recepcion.id.desc()).limit(10).all()
    search_query = (request.args.get("q") or "").strip()
    selected_status = (request.args.get("status") or "").strip() or "todos"
    normalized_query = search_query.lower()

    order_cards = []
    for orden in ordenes:
        linea = orden.lineas[0] if orden.lineas else None
        status = _purchase_status(orden)
        haystack = " ".join(
            [
                f"OC-{orden.id:04d}",
                orden.proveedor.razon_social or "",
                linea.producto.nombre if linea else "",
                linea.producto.codigo if linea else "",
                orden.observaciones or "",
            ]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        if selected_status != "todos" and status.lower() != selected_status.lower():
            continue
        order_cards.append({"orden": orden, "linea": linea, "status": status})

    purchases_ytd = sum(
        (
            Decimal(str(card["orden"].total or 0))
            for card in order_cards
            if card["orden"].fecha.year == date.today().year
        ),
        Decimal("0.00"),
    )
    open_orders = sum(1 for card in order_cards if card["status"] != "Recibida")
    received_amount = sum(
        (
            Decimal(str(card["linea"].cantidad_recibida or 0))
            for card in order_cards
            if card["linea"] is not None
        ),
        Decimal("0.00"),
    )
    return render_template(
        "compras/dashboard.html",
        supplier_form=supplier_form,
        order_form=order_form,
        reception_form=reception_form,
        proveedores=proveedores,
        ordenes=ordenes,
        recepciones=recepciones,
        order_cards=order_cards,
        search_query=search_query,
        selected_status=selected_status,
        purchases_ytd=purchases_ytd,
        open_orders=open_orders,
        received_amount=received_amount,
        can_write=current_user.has_permission(PERM_PURCHASES_MANAGE, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_PURCHASES_VIEW)
def dashboard():
    if request.method == "POST":
        if request.form.get("supplier-submit"):
            return _render_purchase_workspace("proveedores")
        return _render_purchase_workspace("ordenes")

    empresa_id = _empresa_id()
    suppliers = Proveedor.query.filter_by(empresa_id=empresa_id, activo=True).count()
    orders = OrdenCompra.query.filter_by(empresa_id=empresa_id).count()
    receipts = Recepcion.query.filter_by(empresa_id=empresa_id).count()
    return render_template(
        "dashboard/module_hub.html",
        module_title="Compras",
        module_heading="Compras",
        module_badges=[
            {"label": "Abastecimiento", "color": "blue"},
            {"label": f"{suppliers} proveedores"},
        ],
        module_stats=[
            {"label": "Órdenes", "value": orders, "meta": "Documentos emitidos en la empresa."},
            {"label": "Proveedores", "value": suppliers, "meta": "Maestros activos para compras."},
            {"label": "Recepciones", "value": receipts, "meta": "Ingresos registrados a almacén."},
        ],
        module_actions=[
            {"label": "Órdenes", "href": url_for("compras.orders"), "primary": True},
            {"label": "Proveedores", "href": url_for("compras.suppliers")},
        ],
        module_children=[
            {
                "label": "Órdenes",
                "href": url_for("compras.orders"),
                "description": "Emite órdenes, revisa recepciones y sigue pendientes de entrega.",
            },
            {
                "label": "Proveedores",
                "href": url_for("compras.suppliers"),
                "description": "Administra la base de proveedores y condiciones de pago.",
            },
        ],
    )


@bp.route("/ordenes", methods=["GET", "POST"])
@login_required
@permission_required(PERM_PURCHASES_VIEW)
def orders():
    return _render_purchase_workspace("ordenes")


@bp.route("/proveedores", methods=["GET", "POST"])
@login_required
@permission_required(PERM_PURCHASES_VIEW)
def suppliers():
    return _render_purchase_workspace("proveedores")
