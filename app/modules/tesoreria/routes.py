from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    CuentaTesoreria,
    MovimientoTesoreria,
    PERM_TREASURY_MANAGE,
    PERM_TREASURY_VIEW,
    PlanCuenta,
    TipoCambio,
)
from app.modules.tesoreria import bp
from app.modules.tesoreria.forms import ExchangeRateForm, ReconcileForm, TransferForm, TreasuryAccountForm, TreasuryMovementForm
from app.security import permission_required
from app.services.accounting import ensure_accounting_setup
from app.services.reporting import cash_flow_summary
from app.services.treasury import (
    TreasuryError,
    create_treasury_account,
    reconcile_movements_from_csv,
    register_treasury_movement,
    transfer_between_accounts,
    upsert_exchange_rate,
)


def _empresa_id() -> int:
    return int(session["active_empresa_id"])


def _populate_forms(account_form: TreasuryAccountForm, movement_form: TreasuryMovementForm, transfer_form: TransferForm, reconcile_form: ReconcileForm) -> None:
    empresa_id = _empresa_id()
    ensure_accounting_setup(empresa_id)
    account_choices = [
        (item.codigo, f"{item.codigo} · {item.nombre}")
        for item in PlanCuenta.query.filter_by(empresa_id=empresa_id)
        .order_by(PlanCuenta.codigo.asc())
        .all()
    ]
    movement_form.cuenta_id.choices = [
        (item.id, item.nombre)
        for item in CuentaTesoreria.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(CuentaTesoreria.nombre.asc())
        .all()
    ]
    treasury_choices = movement_form.cuenta_id.choices
    transfer_form.cuenta_origen_id.choices = treasury_choices
    transfer_form.cuenta_destino_id.choices = treasury_choices
    reconcile_form.cuenta_id.choices = treasury_choices
    account_form.cuenta_contable_codigo.choices = account_choices
    movement_form.contra_cuenta_codigo.choices = account_choices


def _render_treasury_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    endpoint_map = {
        "cuentas": "tesoreria.accounts",
        "conciliacion": "tesoreria.reconciliation",
        "flujo": "tesoreria.cash_flow",
    }
    current_view_endpoint = endpoint_map[active_submodule]
    account_form = TreasuryAccountForm(prefix="cash")
    movement_form = TreasuryMovementForm(prefix="move")
    transfer_form = TransferForm(prefix="transfer")
    reconcile_form = ReconcileForm(prefix="reconcile")
    fx_form = ExchangeRateForm(prefix="fx")
    if not movement_form.fecha.data:
        movement_form.fecha.data = date.today()
    if not transfer_form.fecha.data:
        transfer_form.fecha.data = date.today()
    if not fx_form.fecha.data:
        fx_form.fecha.data = date.today()
    _populate_forms(account_form, movement_form, transfer_form, reconcile_form)

    if account_form.submit.data and account_form.validate_on_submit():
        if not current_user.has_permission(PERM_TREASURY_MANAGE, empresa_id):
            return "", 403
        create_treasury_account(
            empresa_id=empresa_id,
            tipo=account_form.tipo.data,
            nombre=account_form.nombre.data,
            banco=account_form.banco.data,
            numero_cuenta=account_form.numero_cuenta.data,
            moneda=account_form.moneda.data,
            cuenta_contable_codigo=account_form.cuenta_contable_codigo.data,
        )
        db.session.commit()
        flash("Cuenta de tesorería creada.", "success")
        return redirect(url_for(current_view_endpoint))

    if movement_form.submit.data and movement_form.validate_on_submit():
        if not current_user.has_permission(PERM_TREASURY_MANAGE, empresa_id):
            return "", 403
        treasury = db.session.get(CuentaTesoreria, movement_form.cuenta_id.data)
        try:
            register_treasury_movement(
                empresa_id=empresa_id,
                treasury_account=treasury,
                tipo=movement_form.tipo.data,
                monto=movement_form.monto.data,
                fecha=movement_form.fecha.data,
                glosa=movement_form.glosa.data,
                contra_cuenta_codigo=movement_form.contra_cuenta_codigo.data,
                created_by=current_user.id,
            )
        except TreasuryError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Movimiento de tesorería registrado.", "success")
            return redirect(url_for(current_view_endpoint))

    if transfer_form.submit.data and transfer_form.validate_on_submit():
        if not current_user.has_permission(PERM_TREASURY_MANAGE, empresa_id):
            return "", 403
        try:
            transfer_between_accounts(
                empresa_id=empresa_id,
                source=db.session.get(CuentaTesoreria, transfer_form.cuenta_origen_id.data),
                destination=db.session.get(CuentaTesoreria, transfer_form.cuenta_destino_id.data),
                monto=transfer_form.monto.data,
                fecha=transfer_form.fecha.data,
                created_by=current_user.id,
            )
        except TreasuryError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Transferencia registrada.", "success")
            return redirect(url_for(current_view_endpoint))

    if reconcile_form.submit.data and reconcile_form.validate_on_submit():
        if not current_user.has_permission(PERM_TREASURY_MANAGE, empresa_id):
            return "", 403
        file_storage = reconcile_form.csv_file.data
        content = file_storage.stream.read().decode("utf-8") if file_storage else ""
        try:
            matched = reconcile_movements_from_csv(
                empresa_id=empresa_id,
                treasury_account=db.session.get(CuentaTesoreria, reconcile_form.cuenta_id.data),
                csv_content=content,
            )
        except TreasuryError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash(f"Conciliación completada. Movimientos conciliados: {matched}.", "success")
            return redirect(url_for(current_view_endpoint))

    if fx_form.submit.data and fx_form.validate_on_submit():
        if not current_user.has_permission(PERM_TREASURY_MANAGE, empresa_id):
            return "", 403
        try:
            upsert_exchange_rate(empresa_id, fx_form.fecha.data)
        except TreasuryError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Tipo de cambio actualizado desde BCRP.", "success")
            return redirect(url_for(current_view_endpoint))

    accounts = CuentaTesoreria.query.filter_by(empresa_id=empresa_id).order_by(CuentaTesoreria.nombre.asc()).all()
    movements = MovimientoTesoreria.query.filter_by(empresa_id=empresa_id).order_by(MovimientoTesoreria.id.desc()).limit(20).all()
    exchange_rates = TipoCambio.query.filter_by(empresa_id=empresa_id).order_by(TipoCambio.fecha.desc()).limit(10).all()
    cash_flow = cash_flow_summary(empresa_id)
    treasury_balance = sum((Decimal(str(account.saldo_actual or 0)) for account in accounts), Decimal("0.00"))
    reconciled_count = sum(1 for movement in movements if movement.conciliado)
    return render_template(
        "tesoreria/dashboard.html",
        account_form=account_form,
        movement_form=movement_form,
        transfer_form=transfer_form,
        reconcile_form=reconcile_form,
        fx_form=fx_form,
        accounts=accounts,
        movements=movements,
        exchange_rates=exchange_rates,
        cash_flow=cash_flow,
        treasury_balance=treasury_balance,
        reconciled_count=reconciled_count,
        can_write=current_user.has_permission(PERM_TREASURY_MANAGE, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_TREASURY_VIEW)
def dashboard():
    if request.method == "POST":
        if request.form.get("reconcile-submit") or request.form.get("fx-submit"):
            return _render_treasury_workspace("conciliacion")
        if request.form.get("move-submit"):
            return _render_treasury_workspace("flujo")
        return _render_treasury_workspace("cuentas")

    empresa_id = _empresa_id()
    accounts = CuentaTesoreria.query.filter_by(empresa_id=empresa_id).count()
    movements = MovimientoTesoreria.query.filter_by(empresa_id=empresa_id).count()
    fx = TipoCambio.query.filter_by(empresa_id=empresa_id).count()
    return render_template(
        "dashboard/module_hub.html",
        module_title="Tesorería",
        module_heading="Tesorería",
        module_badges=[
            {"label": "Liquidez", "color": "blue"},
            {"label": f"{accounts} cuentas"},
        ],
        module_stats=[
            {"label": "Cuentas", "value": accounts, "meta": "Cajas y bancos visibles."},
            {"label": "Movimientos", "value": movements, "meta": "Actividad acumulada de tesorería."},
            {"label": "Tipo cambio", "value": fx, "meta": "Registros BCRP almacenados."},
        ],
        module_actions=[
            {"label": "Cajas y bancos", "href": url_for("tesoreria.accounts"), "primary": True},
            {"label": "Conciliación", "href": url_for("tesoreria.reconciliation")},
        ],
        module_children=[
            {
                "label": "Cajas y bancos",
                "href": url_for("tesoreria.accounts"),
                "description": "Administra cuentas, movimientos manuales y transferencias internas.",
            },
            {
                "label": "Conciliación",
                "href": url_for("tesoreria.reconciliation"),
                "description": "Concilia extractos, revisa actividad y actualiza tipo de cambio.",
            },
            {
                "label": "Flujo de caja",
                "href": url_for("tesoreria.cash_flow"),
                "description": "Analiza entradas, salidas y posición neta en una vista de liquidez.",
            },
        ],
    )


@bp.route("/cajas-bancos", methods=["GET", "POST"])
@login_required
@permission_required(PERM_TREASURY_VIEW)
def accounts():
    return _render_treasury_workspace("cuentas")


@bp.route("/conciliacion", methods=["GET", "POST"])
@login_required
@permission_required(PERM_TREASURY_VIEW)
def reconciliation():
    return _render_treasury_workspace("conciliacion")


@bp.route("/flujo-caja", methods=["GET", "POST"])
@login_required
@permission_required(PERM_TREASURY_VIEW)
def cash_flow():
    return _render_treasury_workspace("flujo")
