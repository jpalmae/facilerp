from __future__ import annotations

from datetime import date

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Asiento,
    PERM_ACCOUNTING_MANAGE,
    PERM_ACCOUNTING_VIEW,
    PlanCuenta,
)
from app.modules.contabilidad import bp
from app.modules.contabilidad.forms import ClosePeriodForm, ManualEntryForm, ReverseEntryForm
from app.security import permission_required
from app.services.accounting import (
    AccountingError,
    account_ledger,
    close_period,
    create_journal_entry,
    ensure_accounting_setup,
    list_periods,
    reverse_entry,
    statement_snapshot,
    trial_balance,
)


def _empresa_id() -> int:
    return int(session["active_empresa_id"])


def _populate_form(form: ManualEntryForm) -> None:
    empresa_id = _empresa_id()
    ensure_accounting_setup(empresa_id)
    choices = [
        (item.id, f"{item.codigo} · {item.nombre}")
        for item in PlanCuenta.query.filter_by(empresa_id=empresa_id)
        .order_by(PlanCuenta.codigo.asc())
        .all()
    ]
    form.cuenta_debe_id.choices = choices
    form.cuenta_haber_id.choices = choices


def _populate_close_form(form: ClosePeriodForm) -> None:
    form.periodo_id.choices = [
        (item.id, f"{item.mes:02d}/{item.anio} · {item.estado}")
        for item in list_periods(_empresa_id())
    ]


def _populate_reverse_form(form: ReverseEntryForm) -> None:
    form.asiento_id.choices = [
        (item.id, f"Asiento {item.numero} · {item.glosa}")
        for item in Asiento.query.filter(
            Asiento.empresa_id == _empresa_id(), Asiento.estado != "revertido"
        )
        .order_by(Asiento.id.desc())
        .limit(30)
        .all()
    ]


def _render_accounting_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    endpoint_map = {
        "asientos": "contabilidad.entries",
        "plan": "contabilidad.chart_of_accounts",
        "mayor": "contabilidad.ledger",
    }
    current_view_endpoint = endpoint_map[active_submodule]
    form = ManualEntryForm(prefix="entry")
    close_form = ClosePeriodForm(prefix="close")
    reverse_form = ReverseEntryForm(prefix="reverse")
    if not form.fecha.data:
        form.fecha.data = date.today()
    if not reverse_form.fecha.data:
        reverse_form.fecha.data = date.today()
    _populate_form(form)
    _populate_close_form(close_form)
    _populate_reverse_form(reverse_form)

    if form.submit.data and form.validate_on_submit():
        if not current_user.has_permission(PERM_ACCOUNTING_MANAGE, empresa_id):
            return "", 403
        try:
            create_journal_entry(
                empresa_id=empresa_id,
                fecha=form.fecha.data,
                glosa=form.glosa.data,
                tipo="manual",
                created_by=current_user.id,
                lines=[
                    {"cuenta": db.session.get(PlanCuenta, form.cuenta_debe_id.data), "debe": form.monto.data},
                    {"cuenta": db.session.get(PlanCuenta, form.cuenta_haber_id.data), "haber": form.monto.data},
                ],
            )
        except AccountingError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Asiento manual registrado.", "success")
            return redirect(url_for(current_view_endpoint))

    if close_form.submit.data and close_form.validate_on_submit():
        if not current_user.has_permission(PERM_ACCOUNTING_MANAGE, empresa_id):
            return "", 403
        try:
            close_period(empresa_id, close_form.periodo_id.data)
        except AccountingError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Período cerrado.", "success")
            return redirect(url_for(current_view_endpoint))

    if reverse_form.submit.data and reverse_form.validate_on_submit():
        if not current_user.has_permission(PERM_ACCOUNTING_MANAGE, empresa_id):
            return "", 403
        try:
            reverse_entry(
                empresa_id,
                reverse_form.asiento_id.data,
                reverse_form.fecha.data,
                created_by=current_user.id,
            )
        except AccountingError as exc:
            flash(str(exc), "error")
        else:
            db.session.commit()
            flash("Asiento revertido.", "success")
            return redirect(url_for(current_view_endpoint))

    entries = Asiento.query.filter_by(empresa_id=empresa_id).order_by(Asiento.id.desc()).limit(20).all()
    balances = trial_balance(empresa_id)
    snapshot = statement_snapshot(empresa_id)
    periods = list_periods(empresa_id)
    ledger_account = balances[0]["codigo"] if balances else None
    ledger_rows = []
    if ledger_account:
        account = PlanCuenta.query.filter_by(empresa_id=empresa_id, codigo=ledger_account).first()
        if account:
            ledger_rows = account_ledger(empresa_id, account.id)
    return render_template(
        "contabilidad/dashboard.html",
        form=form,
        close_form=close_form,
        reverse_form=reverse_form,
        entries=entries,
        balances=balances,
        snapshot=snapshot,
        periods=periods,
        ledger_rows=ledger_rows,
        can_write=current_user.has_permission(PERM_ACCOUNTING_MANAGE, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_ACCOUNTING_VIEW)
def dashboard():
    if request.method == "POST":
        return _render_accounting_workspace("asientos")

    empresa_id = _empresa_id()
    entries = Asiento.query.filter_by(empresa_id=empresa_id).count()
    accounts = PlanCuenta.query.filter_by(empresa_id=empresa_id).count()
    periods = len(list_periods(empresa_id))
    return render_template(
        "dashboard/module_hub.html",
        module_title="Contabilidad",
        module_heading="Contabilidad",
        module_badges=[
            {"label": "Partida doble", "color": "blue"},
            {"label": f"{periods} períodos"},
        ],
        module_stats=[
            {"label": "Asientos", "value": entries, "meta": "Registros contables emitidos."},
            {"label": "Cuentas", "value": accounts, "meta": "Plan de cuentas disponible."},
            {"label": "Períodos", "value": periods, "meta": "Períodos configurados."},
        ],
        module_actions=[
            {"label": "Asientos", "href": url_for("contabilidad.entries"), "primary": True},
            {"label": "Plan de cuentas", "href": url_for("contabilidad.chart_of_accounts")},
        ],
        module_children=[
            {
                "label": "Asientos",
                "href": url_for("contabilidad.entries"),
                "description": "Registra, cierra y revierte asientos en una vista operativa.",
            },
            {
                "label": "Plan de cuentas",
                "href": url_for("contabilidad.chart_of_accounts"),
                "description": "Consulta cuentas y balance de comprobación sin mezclar libro mayor.",
            },
            {
                "label": "Libro mayor",
                "href": url_for("contabilidad.ledger"),
                "description": "Revisa movimientos por cuenta en una pantalla analítica separada.",
            },
        ],
    )


@bp.route("/asientos", methods=["GET", "POST"])
@login_required
@permission_required(PERM_ACCOUNTING_VIEW)
def entries():
    return _render_accounting_workspace("asientos")


@bp.route("/plan-cuentas", methods=["GET"])
@login_required
@permission_required(PERM_ACCOUNTING_VIEW)
def chart_of_accounts():
    return _render_accounting_workspace("plan")


@bp.route("/libro-mayor", methods=["GET"])
@login_required
@permission_required(PERM_ACCOUNTING_VIEW)
def ledger():
    return _render_accounting_workspace("mayor")
