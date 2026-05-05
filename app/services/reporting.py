from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

from flask import current_app, render_template
from openpyxl import Workbook

from app.models import DocumentoCxC, DocumentoCxP, MovimientoTesoreria
from app.services.accounting import statement_snapshot, trial_balance
from app.services.inventory import as_decimal


def aging_summary(empresa_id: int) -> dict:
    today = date.today()

    def bucketize(items):
        buckets = {
            "current": Decimal("0.00"),
            "1_30": Decimal("0.00"),
            "31_60": Decimal("0.00"),
            "61_90": Decimal("0.00"),
            "90_plus": Decimal("0.00"),
        }
        total = Decimal("0.00")
        for item in items:
            pending = as_decimal(item.monto_pendiente)
            total += pending
            diff = (today - item.fecha_vencimiento).days
            if diff <= 0:
                buckets["current"] += pending
            elif diff <= 30:
                buckets["1_30"] += pending
            elif diff <= 60:
                buckets["31_60"] += pending
            elif diff <= 90:
                buckets["61_90"] += pending
            else:
                buckets["90_plus"] += pending
        buckets["total"] = total
        return buckets

    cxc_buckets = bucketize(DocumentoCxC.query.filter_by(empresa_id=empresa_id).all())
    cxp_buckets = bucketize(DocumentoCxP.query.filter_by(empresa_id=empresa_id).all())
    return {"cxc": cxc_buckets, "cxp": cxp_buckets, "neto": cxc_buckets["total"] - cxp_buckets["total"]}


def cash_flow_summary(empresa_id: int) -> dict:
    ingresos = as_decimal(
        sum(
            item.monto
            for item in MovimientoTesoreria.query.filter_by(
                empresa_id=empresa_id, tipo="ingreso"
            )
        )
    )
    egresos = as_decimal(
        sum(
            item.monto
            for item in MovimientoTesoreria.query.filter_by(
                empresa_id=empresa_id, tipo="egreso"
            )
        )
    )
    return {"ingresos": ingresos, "egresos": egresos, "neto": ingresos - egresos}


def build_financial_excel(empresa_id: int) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Balance"
    sheet.append(["Codigo", "Cuenta", "Debe", "Haber", "Saldo"])
    for row in trial_balance(empresa_id):
        sheet.append(
            [
                row["codigo"],
                row["nombre"],
                float(row["debe"]),
                float(row["haber"]),
                float(row["saldo"]),
            ]
        )

    snapshot = statement_snapshot(empresa_id)
    summary = workbook.create_sheet("Resumen")
    summary.append(["Concepto", "Monto"])
    summary.append(["Activo", float(snapshot["balance"]["activo"])])
    summary.append(["Pasivo", float(snapshot["balance"]["pasivo"])])
    summary.append(["Utilidad", float(snapshot["resultados"]["utilidad"])])
    aging = aging_summary(empresa_id)
    summary.append(["CxC Total", float(aging["cxc"]["total"])])
    summary.append(["CxP Total", float(aging["cxp"]["total"])])
    summary.append(["Flujo Neto", float(cash_flow_summary(empresa_id)["neto"])])
    summary.append(["Posicion Neta", float(aging["neto"])])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def build_ple_txt(empresa_id: int) -> BytesIO:
    output = BytesIO()
    lines = []
    for row in trial_balance(empresa_id):
        lines.append(
            f"{row['codigo']}|{row['nombre']}|{row['debe']:.2f}|{row['haber']:.2f}|{row['saldo']:.2f}"
        )
    output.write("\n".join(lines).encode("utf-8"))
    output.seek(0)
    return output


def build_financial_pdf(empresa_id: int) -> tuple[bytes, str]:
    """Return (payload_bytes, mimetype).

    Generates a proper PDF when WeasyPrint is available.
    Falls back to a downloadable HTML file with a clear warning if not.
    """
    html = render_template(
        "reportes/pdf_financial.html",
        snapshot=statement_snapshot(empresa_id),
        balances=trial_balance(empresa_id),
        aging=aging_summary(empresa_id),
        cash_flow=cash_flow_summary(empresa_id),
    )
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html, base_url=str(current_app.root_path)).write_pdf()
        return pdf_bytes, "application/pdf"
    except ImportError:
        current_app.logger.warning(
            "WeasyPrint no está instalado — el reporte se exportará como HTML. "
            "Instale weasyprint para generar PDFs reales."
        )
        return html.encode("utf-8"), "text/html; charset=utf-8"
    except Exception:
        current_app.logger.exception("Error generando PDF con WeasyPrint — exportando HTML como fallback.")
        return html.encode("utf-8"), "text/html; charset=utf-8"
