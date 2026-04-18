from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Almacen,
    AuditLog,
    Cliente,
    DocumentoCxC,
    PERM_SALES_MANAGE,
    PERM_SALES_VIEW,
    PedidoVenta,
    Producto,
)
from app.modules.ventas import bp
from app.modules.ventas.forms import ClientForm, SalesOrderForm
from app.security import permission_required
from app.services.external import validate_ruc, validate_ruc_format
from app.utils.document import document_status
from app.utils.warehouse import allowed_warehouse_ids, warehouse_or_403, warehouse_query
from app.services.sales import SalesError, create_sales_order


def _empresa_id() -> int:
    return int(session["active_empresa_id"])

def _populate_sales_form(form: SalesOrderForm) -> None:
    empresa_id = _empresa_id()
    form.cliente_id.choices = [
        (item.id, item.razon_social)
        for item in Cliente.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(Cliente.razon_social.asc())
        .all()
    ]
    form.producto_id.choices = [
        (item.id, f"{item.codigo} · {item.nombre}")
        for item in Producto.query.filter_by(empresa_id=empresa_id, activo=True, tipo="bien")
        .order_by(Producto.nombre.asc())
        .all()
    ]
    form.almacen_id.choices = [
        (item.id, item.nombre)
        for item in warehouse_query(empresa_id)
        .order_by(Almacen.nombre.asc())
        .all()
    ]

def _render_sales_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    endpoint_map = {
        "facturacion": "ventas.invoices",
        "clientes": "ventas.clients",
        "creditos": "ventas.credit_notes",
    }
    current_view_endpoint = endpoint_map[active_submodule]
    client_form = ClientForm(prefix="client")
    order_form = SalesOrderForm(prefix="sale")
    if not order_form.fecha.data:
        order_form.fecha.data = date.today()
    _populate_sales_form(order_form)

    if client_form.submit.data and client_form.validate_on_submit():
        if not current_user.has_permission(PERM_SALES_MANAGE, empresa_id):
            return "", 403
        document = client_form.documento.data.strip()
        if len(document) == 11 and validate_ruc_format(document):
            validation = validate_ruc(document)
            if not validation.valid:
                flash(validation.message or "RUC inválido.", "error")
                return redirect(url_for("ventas.dashboard"))
        client = Cliente(
            empresa_id=empresa_id,
            documento=document,
            razon_social=client_form.razon_social.data.strip(),
            condicion_pago=client_form.condicion_pago.data,
        )
        db.session.add(client)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                empresa_id=empresa_id,
                accion="ventas.cliente.created",
            )
        )
        db.session.commit()
        flash("Cliente creado.", "success")
        return redirect(url_for(current_view_endpoint))

    if order_form.submit.data:
        if not current_user.has_permission(PERM_SALES_MANAGE, empresa_id):
            return "", 403
        requested_warehouse_id = request.form.get(order_form.almacen_id.name, type=int)
        if requested_warehouse_id is not None:
            warehouse_or_403(empresa_id, requested_warehouse_id)
    if order_form.submit.data and order_form.validate_on_submit():
        if not current_user.has_permission(PERM_SALES_MANAGE, empresa_id):
            return "", 403
        cliente = Cliente.query.filter_by(
            id=order_form.cliente_id.data, empresa_id=empresa_id
        ).first_or_404()
        producto = Producto.query.filter_by(
            id=order_form.producto_id.data, empresa_id=empresa_id
        ).first_or_404()
        almacen = warehouse_or_403(empresa_id, order_form.almacen_id.data)
        try:
            create_sales_order(
                empresa_id=empresa_id,
                cliente=cliente,
                producto=producto,
                almacen=almacen,
                cantidad=order_form.cantidad.data,
                precio_unitario=order_form.precio_unitario.data,
                fecha=order_form.fecha.data,
                observaciones=order_form.observaciones.data,
            )
        except SalesError as exc:
            flash(str(exc), "error")
        else:
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    empresa_id=empresa_id,
                    accion="ventas.pedido.created",
                )
            )
            db.session.commit()
            flash("Venta registrada, stock descontado y CxC generada.", "success")
            return redirect(url_for(current_view_endpoint))

    clientes = (
        Cliente.query.filter_by(empresa_id=empresa_id)
        .order_by(Cliente.razon_social.asc())
        .all()
    )
    pedidos_query = PedidoVenta.query.filter_by(empresa_id=empresa_id)
    documentos_query = DocumentoCxC.query.filter_by(empresa_id=empresa_id)
    allowed_ids = allowed_warehouse_ids(empresa_id)
    if allowed_ids is not None:
        pedidos_query = pedidos_query.filter(PedidoVenta.almacen_id.in_(sorted(allowed_ids)))
        documentos_query = documentos_query.join(PedidoVenta).filter(
            PedidoVenta.almacen_id.in_(sorted(allowed_ids))
        )
    pedidos = pedidos_query.order_by(PedidoVenta.id.desc()).all()
    documentos = documentos_query.order_by(DocumentoCxC.id.desc()).limit(8).all()
    search_query = (request.args.get("q") or "").strip()
    selected_status = (request.args.get("status") or "").strip() or "todos"
    normalized_query = search_query.lower()

    document_cards = []
    for pedido in pedidos:
        documento = pedido.documentos_cxc[0] if pedido.documentos_cxc else None
        display_status = document_status(documento) if documento else pedido.estado.capitalize()
        haystack_parts = [
            f"FV-{pedido.id:04d}",
            pedido.cliente.razon_social or "",
            pedido.almacen.nombre or "",
            pedido.observaciones or "",
        ]
        for line in pedido.lineas:
            haystack_parts.extend(
                [line.producto.nombre or "", line.producto.codigo or "", line.producto.categoria or ""]
            )
        haystack = " ".join(haystack_parts).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        if selected_status != "todos" and display_status.lower() != selected_status.lower():
            continue
        document_cards.append(
            {
                "pedido": pedido,
                "documento": documento,
                "status": display_status,
            }
        )

    sales_ytd = sum(
        (
            Decimal(str(card["pedido"].total or 0))
            for card in document_cards
            if card["pedido"].fecha.year == date.today().year
        ),
        Decimal("0.00"),
    )
    overdue_count = sum(1 for card in document_cards if card["status"] == "Vencida")
    pending_amount = sum(
        (
            Decimal(str(card["documento"].monto_pendiente or 0))
            for card in document_cards
            if card["documento"] is not None
        ),
        Decimal("0.00"),
    )
    document_summaries = [
        {
            "documento": documento,
            "status": document_status(documento),
        }
        for documento in documentos
    ]
    return render_template(
        "ventas/dashboard.html",
        client_form=client_form,
        order_form=order_form,
        clientes=clientes,
        pedidos=pedidos,
        documentos=documentos,
        document_cards=document_cards,
        document_summaries=document_summaries,
        search_query=search_query,
        selected_status=selected_status,
        sales_ytd=sales_ytd,
        overdue_count=overdue_count,
        pending_amount=pending_amount,
        can_write=current_user.has_permission(PERM_SALES_MANAGE, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SALES_VIEW)
def dashboard():
    if request.method == "POST":
        if request.form.get("client-submit"):
            return _render_sales_workspace("clientes")
        return _render_sales_workspace("facturacion")

    empresa_id = _empresa_id()
    clients = Cliente.query.filter_by(empresa_id=empresa_id, activo=True).count()
    orders = PedidoVenta.query.filter_by(empresa_id=empresa_id).count()
    documents = DocumentoCxC.query.filter_by(empresa_id=empresa_id).count()
    return render_template(
        "dashboard/module_hub.html",
        module_title="Ventas",
        module_heading="Ventas",
        module_badges=[
            {"label": "Ingresos", "color": "blue"},
            {"label": f"{clients} clientes"},
        ],
        module_stats=[
            {"label": "Facturas", "value": documents, "meta": "Documentos CxC visibles."},
            {"label": "Pedidos", "value": orders, "meta": "Ventas registradas en la empresa."},
            {"label": "Clientes", "value": clients, "meta": "Maestro comercial activo."},
        ],
        module_actions=[
            {"label": "Facturación", "href": url_for("ventas.invoices"), "primary": True},
            {"label": "Clientes", "href": url_for("ventas.clients")},
        ],
        module_children=[
            {
                "label": "Facturación",
                "href": url_for("ventas.invoices"),
                "description": "Consulta documentos, estados de cobranza y registra nuevas ventas.",
            },
            {
                "label": "Clientes",
                "href": url_for("ventas.clients"),
                "description": "Mantén la base comercial y condiciones de pago en una pantalla dedicada.",
            },
            {
                "label": "Notas de crédito",
                "href": url_for("ventas.credit_notes"),
                "description": "Entrada reservada para devoluciones y ajustes comerciales por documento.",
            },
        ],
    )


@bp.route("/facturacion", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SALES_VIEW)
def invoices():
    return _render_sales_workspace("facturacion")


@bp.route("/clientes", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SALES_VIEW)
def clients():
    return _render_sales_workspace("clientes")


@bp.route("/notas-credito", methods=["GET"])
@login_required
@permission_required(PERM_SALES_VIEW)
def credit_notes():
    return _render_sales_workspace("creditos")
