from __future__ import annotations

from io import BytesIO

from flask import render_template, send_file, session, url_for
from flask_login import login_required

from app.models import Asiento, PERM_REPORTS_VIEW
from app.modules.reportes import bp
from app.security import permission_required
from app.services.accounting import statement_snapshot, trial_balance
from app.services.reporting import (
    aging_summary,
    build_financial_excel,
    build_financial_pdf,
    build_ple_txt,
    cash_flow_summary,
)


def _render_reports_workspace(active_submodule: str):
    empresa_id = int(session["active_empresa_id"])
    snapshot = statement_snapshot(empresa_id)
    balances = trial_balance(empresa_id)
    entries = (
        Asiento.query.filter_by(empresa_id=empresa_id)
        .order_by(Asiento.id.desc())
        .limit(15)
        .all()
    )
    return render_template(
        "reportes/dashboard.html",
        snapshot=snapshot,
        balances=balances,
        entries=entries,
        aging=aging_summary(empresa_id),
        cash_flow=cash_flow_summary(empresa_id),
        active_submodule=active_submodule,
    )


@bp.get("/")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def dashboard():
    empresa_id = int(session["active_empresa_id"])
    balances = trial_balance(empresa_id)
    return render_template(
        "dashboard/module_hub.html",
        module_title="Reportes",
        module_heading="Reportes",
        module_badges=[
            {"label": "Exportables", "color": "blue"},
            {"label": f"{len(balances)} cuentas"},
        ],
        module_stats=[
            {"label": "PDF", "value": "1", "meta": "Salida financiera disponible."},
            {"label": "Excel", "value": "1", "meta": "Exportable operativo disponible."},
            {"label": "PLE", "value": "1", "meta": "Archivo de libro mayor disponible."},
        ],
        module_actions=[
            {"label": "Financieros", "href": url_for("reportes.financial_reports"), "primary": True},
            {"label": "Ventas", "href": url_for("reportes.sales_reports")},
        ],
        module_children=[
            {
                "label": "Ventas",
                "href": url_for("reportes.sales_reports"),
                "description": "Lee aging y señales comerciales desde una vista enfocada en cobranza.",
            },
            {
                "label": "Inventario",
                "href": url_for("reportes.inventory_reports"),
                "description": "Consulta rotación operativa y liquidez ligada al stock y tesorería.",
            },
            {
                "label": "Financieros",
                "href": url_for("reportes.financial_reports"),
                "description": "Balance, resultados y exportaciones en una pantalla propia.",
            },
        ],
    )


@bp.get("/ventas")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def sales_reports():
    return _render_reports_workspace("ventas")


@bp.get("/inventario")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def inventory_reports():
    return _render_reports_workspace("inventario")


@bp.get("/financieros")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def financial_reports():
    return _render_reports_workspace("financieros")


@bp.get("/export/excel")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def export_excel():
    empresa_id = int(session["active_empresa_id"])
    workbook = build_financial_excel(empresa_id)
    return send_file(
        workbook,
        as_attachment=True,
        download_name="facilerp-reportes.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/export/pdf")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def export_pdf():
    empresa_id = int(session["active_empresa_id"])
    payload, mimetype = build_financial_pdf(empresa_id)
    download_name = "facilerp-reportes.pdf" if mimetype == "application/pdf" else "facilerp-reportes.html"
    return send_file(
        BytesIO(payload),
        as_attachment=True,
        download_name=download_name,
        mimetype=mimetype,
    )


@bp.get("/export/ple")
@login_required
@permission_required(PERM_REPORTS_VIEW)
def export_ple():
    empresa_id = int(session["active_empresa_id"])
    payload = build_ple_txt(empresa_id)
    return send_file(
        payload,
        as_attachment=True,
        download_name="facilerp-libro-mayor.txt",
        mimetype="text/plain; charset=utf-8",
    )
