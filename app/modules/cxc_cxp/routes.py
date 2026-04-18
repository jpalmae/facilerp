from __future__ import annotations

from datetime import date

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Cobro,
    CuentaTesoreria,
    DocumentoCxC,
    DocumentoCxP,
    Pago,
    PERM_CXC_CXP_MANAGE,
    PERM_CXC_CXP_VIEW,
)
from app.modules.cxc_cxp import bp
from app.modules.cxc_cxp.forms import CollectionForm, PaymentForm
from app.security import permission_required
from app.services.reporting import aging_summary, cash_flow_summary
from app.services.sales import SalesError, register_collection
from app.services.treasury import TreasuryError, register_supplier_payment
from app.utils.document import document_status


def _empresa_id() -> int:
    return int(session["active_empresa_id"])





def _populate_form(form: CollectionForm) -> None:
    empresa_id = _empresa_id()
    form.documento_id.choices = [
        (
            item.id,
            f"CxC-{item.id:04d} · {item.cliente.razon_social} · saldo S/ {item.monto_pendiente}",
        )
        for item in DocumentoCxC.query.filter(
            DocumentoCxC.empresa_id == empresa_id,
            DocumentoCxC.estado.in_(["pendiente", "parcial"]),
        )
        .order_by(DocumentoCxC.id.desc())
        .all()
    ]
    form.cuenta_tesoreria_id.choices = [
        (item.id, item.nombre)
        for item in CuentaTesoreria.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(CuentaTesoreria.nombre.asc())
        .all()
    ]


def _populate_payment_form(form: PaymentForm) -> None:
    empresa_id = _empresa_id()
    form.documento_id.choices = [
        (
            item.id,
            f"CxP-{item.id:04d} · {item.proveedor.razon_social} · saldo S/ {item.monto_pendiente}",
        )
        for item in DocumentoCxP.query.filter(
            DocumentoCxP.empresa_id == empresa_id,
            DocumentoCxP.estado.in_(["pendiente", "parcial"]),
        )
        .order_by(DocumentoCxP.id.desc())
        .all()
    ]
    form.cuenta_tesoreria_id.choices = [
        (item.id, item.nombre)
        for item in CuentaTesoreria.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(CuentaTesoreria.nombre.asc())
        .all()
    ]


def _render_portfolio_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    endpoint_map = {
        "cobros": "cxc_cxp.collections",
        "pagos": "cxc_cxp.payments",
        "aging": "cxc_cxp.aging",
    }
    current_view_endpoint = endpoint_map[active_submodule]
    form = CollectionForm(prefix="collect")
    payment_form = PaymentForm(prefix="pay")
    if not form.fecha.data:
        form.fecha.data = date.today()
    if not payment_form.fecha.data:
        payment_form.fecha.data = date.today()
    _populate_form(form)
    _populate_payment_form(payment_form)

    if form.submit.data and form.validate_on_submit():
        if not current_user.has_permission(PERM_CXC_CXP_MANAGE, empresa_id):
            return "", 403
        documento = DocumentoCxC.query.filter_by(
            id=form.documento_id.data, empresa_id=empresa_id
        ).first_or_404()
        cuenta = CuentaTesoreria.query.filter_by(
            id=form.cuenta_tesoreria_id.data, empresa_id=empresa_id
        ).first_or_404()
        try:
            register_collection(
                empresa_id=empresa_id,
                documento=documento,
                treasury_account=cuenta,
                monto=form.monto.data,
                fecha=form.fecha.data,
                tipo_pago=form.tipo_pago.data,
            )
        except SalesError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Cobro registrado.", "success")
            return redirect(url_for(current_view_endpoint))

    if payment_form.submit.data and payment_form.validate_on_submit():
        if not current_user.has_permission(PERM_CXC_CXP_MANAGE, empresa_id):
            return "", 403
        documento = DocumentoCxP.query.filter_by(
            id=payment_form.documento_id.data, empresa_id=empresa_id
        ).first_or_404()
        cuenta = CuentaTesoreria.query.filter_by(
            id=payment_form.cuenta_tesoreria_id.data, empresa_id=empresa_id
        ).first_or_404()
        try:
            register_supplier_payment(
                empresa_id=empresa_id,
                documento=documento,
                treasury_account=cuenta,
                monto=payment_form.monto.data,
                fecha=payment_form.fecha.data,
                tipo_pago=payment_form.tipo_pago.data,
            )
        except TreasuryError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Pago registrado.", "success")
            return redirect(url_for(current_view_endpoint))

    documentos = (
        DocumentoCxC.query.filter_by(empresa_id=empresa_id)
        .order_by(DocumentoCxC.id.desc())
        .all()
    )
    documentos_cxp = (
        DocumentoCxP.query.filter_by(empresa_id=empresa_id)
        .order_by(DocumentoCxP.id.desc())
        .all()
    )
    cobros = (
        Cobro.query.filter_by(empresa_id=empresa_id).order_by(Cobro.id.desc()).limit(10).all()
    )
    pagos = Pago.query.filter_by(empresa_id=empresa_id).order_by(Pago.id.desc()).limit(10).all()
    aging = aging_summary(empresa_id)
    cash_flow = cash_flow_summary(empresa_id)
    cxc_cards = [{"documento": item, "status": document_status(item)} for item in documentos]
    cxp_cards = [{"documento": item, "status": document_status(item)} for item in documentos_cxp]
    return render_template(
        "cxc_cxp/dashboard.html",
        form=form,
        payment_form=payment_form,
        documentos=documentos,
        documentos_cxp=documentos_cxp,
        cxc_cards=cxc_cards,
        cxp_cards=cxp_cards,
        cobros=cobros,
        pagos=pagos,
        aging=aging,
        cash_flow=cash_flow,
        can_write=current_user.has_permission(PERM_CXC_CXP_MANAGE, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_CXC_CXP_VIEW)
def dashboard():
    if request.method == "POST":
        if request.form.get("pay-submit"):
            return _render_portfolio_workspace("pagos")
        return _render_portfolio_workspace("cobros")

    empresa_id = _empresa_id()
    pending_cxc = DocumentoCxC.query.filter_by(empresa_id=empresa_id).count()
    pending_cxp = DocumentoCxP.query.filter_by(empresa_id=empresa_id).count()
    movement_count = Cobro.query.filter_by(empresa_id=empresa_id).count() + Pago.query.filter_by(
        empresa_id=empresa_id
    ).count()
    return render_template(
        "dashboard/module_hub.html",
        module_title="CxC / CxP",
        module_heading="Cuentas por Cobrar y Pagar",
        module_badges=[
            {"label": "Liquidez", "color": "blue"},
            {"label": f"{pending_cxc} CxC · {pending_cxp} CxP"},
        ],
        module_stats=[
            {"label": "CxC", "value": pending_cxc, "meta": "Documentos por cobrar visibles."},
            {"label": "CxP", "value": pending_cxp, "meta": "Documentos por pagar visibles."},
            {"label": "Movimientos", "value": movement_count, "meta": "Cobros y pagos registrados."},
        ],
        module_actions=[
            {"label": "Cobros", "href": url_for("cxc_cxp.collections"), "primary": True},
            {"label": "Pagos", "href": url_for("cxc_cxp.payments")},
        ],
        module_children=[
            {
                "label": "Cobros",
                "href": url_for("cxc_cxp.collections"),
                "description": "Gestiona cartera por cobrar y registra ingresos contra documentos.",
            },
            {
                "label": "Pagos",
                "href": url_for("cxc_cxp.payments"),
                "description": "Programa y ejecuta egresos contra proveedores y obligaciones.",
            },
            {
                "label": "Antigüedad de cartera",
                "href": url_for("cxc_cxp.aging"),
                "description": "Analiza vencimientos por tramo y posición neta de liquidez.",
            },
        ],
    )


@bp.route("/cobros", methods=["GET", "POST"])
@login_required
@permission_required(PERM_CXC_CXP_VIEW)
def collections():
    return _render_portfolio_workspace("cobros")


@bp.route("/pagos", methods=["GET", "POST"])
@login_required
@permission_required(PERM_CXC_CXP_VIEW)
def payments():
    return _render_portfolio_workspace("pagos")


@bp.get("/aging")
@login_required
@permission_required(PERM_CXC_CXP_VIEW)
def aging():
    return _render_portfolio_workspace("aging")
