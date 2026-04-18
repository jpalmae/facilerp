from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text
from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    DocumentoCxC,
    OrdenCompra,
    PERM_ACCOUNTING_VIEW,
    PERM_CXC_CXP_VIEW,
    PERM_INVENTORY_VIEW,
    PERM_PURCHASES_VIEW,
    PERM_REPORTS_VIEW,
    PERM_SALES_VIEW,
    PERM_SECURITY_VIEW,
    PERM_TREASURY_VIEW,
    PedidoVenta,
    Producto,
    ROLE_ADMIN,
    ROLE_CONTADOR,
    ROLE_LABELS,
    ROLE_LECTURA,
    ROLE_VENDEDOR,
    Stock,
)
from app.modules.core import bp


MODULES = {
    "inventario": {
        "title": "Inventario",
        "description": "Catálogo de productos, stock, kardex y reposición.",
        "endpoint": "inventario.dashboard",
        "permission": PERM_INVENTORY_VIEW,
    },
    "compras": {
        "title": "Compras",
        "description": "Órdenes, recepciones y registro de facturas de compra.",
        "endpoint": "compras.dashboard",
        "permission": PERM_PURCHASES_VIEW,
    },
    "ventas": {
        "title": "Ventas",
        "description": "Pedidos, ingresos manuales y listas de precios.",
        "endpoint": "ventas.dashboard",
        "permission": PERM_SALES_VIEW,
    },
    "contabilidad": {
        "title": "Contabilidad",
        "description": "PCGE, asientos, libro diario y reportes financieros.",
        "endpoint": "contabilidad.dashboard",
        "permission": PERM_ACCOUNTING_VIEW,
    },
    "tesoreria": {
        "title": "Tesorería",
        "description": "Caja, bancos, conciliación y tipos de cambio.",
        "endpoint": "tesoreria.dashboard",
        "permission": PERM_TREASURY_VIEW,
    },
    "cxc-cxp": {
        "title": "CxC / CxP",
        "description": "Cobros, pagos y antigüedad de cartera/deudas.",
        "endpoint": "cxc_cxp.dashboard",
        "permission": PERM_CXC_CXP_VIEW,
    },
    "reportes": {
        "title": "Reportes",
        "description": "Balance, P&L, flujo de caja, PDF y Excel.",
        "endpoint": "reportes.dashboard",
        "permission": PERM_REPORTS_VIEW,
    },
    "seguridad": {
        "title": "Seguridad",
        "description": "Usuarios, grupos y permisos por empresa.",
        "endpoint": "seguridad.dashboard",
        "permission": PERM_SECURITY_VIEW,
    },
}

MONTH_LABELS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _currency(value: Decimal | int | float) -> str:
    amount = _to_decimal(value)
    return f"S/ {amount:,.2f}"


def _percentage_change(current: Decimal, previous: Decimal) -> tuple[str, str]:
    current_value = _to_decimal(current)
    previous_value = _to_decimal(previous)
    if previous_value == 0:
        if current_value == 0:
            return ("0.0%", "stable")
        return ("100.0%", "up")
    change = ((current_value - previous_value) / previous_value) * Decimal("100")
    trend = "up" if change >= 0 else "down"
    return (f"{abs(change):.1f}%", trend)


def _chart_series(points: list[Decimal]) -> tuple[list[dict[str, object]], str]:
    if not points:
        points = [Decimal("0.00")] * 12
    peak = max(points)
    if peak <= 0:
        peak = Decimal("1.00")
    rows: list[dict[str, object]] = []
    for index, raw_value in enumerate(points):
        x = round(index * (100 / max(len(points) - 1, 1)), 2)
        y = round(100 - (float(raw_value / peak) * 100), 2)
        rows.append(
            {
                "label": MONTH_LABELS[index],
                "value": raw_value,
                "display": _currency(raw_value),
                "x": x,
                "y": y,
            }
        )
    polyline = " ".join(f"{row['x']},{row['y']}" for row in rows)
    return rows, polyline


def _bar_series(values: dict[str, Decimal]) -> list[dict[str, object]]:
    if not values:
        return []
    ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)[:5]
    peak = max(amount for _, amount in ranked) or Decimal("1.00")
    return [
        {
            "label": label,
            "value": amount,
            "display": _currency(amount),
            "width": max(12, round(float(amount / peak) * 100, 2)),
        }
        for label, amount in ranked
    ]


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("core.dashboard"))
    return redirect(url_for("auth.login"))


@bp.get("/dashboard")
@login_required
def dashboard():
    memberships = current_user.memberships
    active_empresa_id = session.get("active_empresa_id")
    active_role = current_user.role_for_empresa(active_empresa_id)
    visible_modules = {
        slug: module
        for slug, module in MODULES.items()
        if current_user.has_permission(module["permission"], active_empresa_id)
    }
    today = date.today()
    year_start = date(today.year, 1, 1)
    month_start = date(today.year, today.month, 1)
    if today.month == 1:
        previous_month_start = date(today.year - 1, 12, 1)
        previous_month_end = date(today.year - 1, 12, 31)
    else:
        previous_month_start = date(today.year, today.month - 1, 1)
        previous_month_end = date.fromordinal(month_start.toordinal() - 1)

    sales_orders = (
        PedidoVenta.query.filter(
            PedidoVenta.empresa_id == active_empresa_id,
            PedidoVenta.fecha >= year_start,
            PedidoVenta.fecha <= today,
        )
        .order_by(PedidoVenta.fecha.asc(), PedidoVenta.id.asc())
        .all()
    )
    purchase_orders = (
        OrdenCompra.query.filter(
            OrdenCompra.empresa_id == active_empresa_id,
            OrdenCompra.fecha >= year_start,
            OrdenCompra.fecha <= today,
        )
        .order_by(OrdenCompra.fecha.asc(), OrdenCompra.id.asc())
        .all()
    )
    receivables = DocumentoCxC.query.filter_by(empresa_id=active_empresa_id).all()
    stock_rows = (
        db.session.query(Stock, Producto)
        .join(Producto, Stock.producto_id == Producto.id)
        .filter(Producto.empresa_id == active_empresa_id)
        .all()
    )

    sales_ytd = sum((_to_decimal(order.total) for order in sales_orders), Decimal("0.00"))
    purchases_ytd = sum(
        (_to_decimal(order.total) for order in purchase_orders),
        Decimal("0.00"),
    )
    current_month_sales = sum(
        (_to_decimal(order.total) for order in sales_orders if order.fecha >= month_start),
        Decimal("0.00"),
    )
    previous_month_sales = sum(
        (
            _to_decimal(order.total)
            for order in sales_orders
            if previous_month_start <= order.fecha <= previous_month_end
        ),
        Decimal("0.00"),
    )
    current_month_purchases = sum(
        (_to_decimal(order.total) for order in purchase_orders if order.fecha >= month_start),
        Decimal("0.00"),
    )
    previous_month_purchases = sum(
        (
            _to_decimal(order.total)
            for order in purchase_orders
            if previous_month_start <= order.fecha <= previous_month_end
        ),
        Decimal("0.00"),
    )
    pending_receivables = sum(
        (_to_decimal(document.monto_pendiente) for document in receivables),
        Decimal("0.00"),
    )
    overdue_receivables = sum(
        1
        for document in receivables
        if _to_decimal(document.monto_pendiente) > 0 and document.fecha_vencimiento < today
    )
    stock_value = Decimal("0.00")
    risky_products: set[int] = set()
    catalog_products: set[int] = set()
    monthly_sales = [Decimal("0.00")] * 12
    monthly_purchases = [Decimal("0.00")] * 12
    category_distribution: dict[str, Decimal] = {}

    for order in sales_orders:
        monthly_sales[order.fecha.month - 1] += _to_decimal(order.total)
        for line in order.lineas:
            category = (line.producto.categoria or "Sin categoría").strip() or "Sin categoría"
            category_distribution.setdefault(category, Decimal("0.00"))
            category_distribution[category] += _to_decimal(line.subtotal) + _to_decimal(line.igv_linea)

    for order in purchase_orders:
        monthly_purchases[order.fecha.month - 1] += _to_decimal(order.total)

    for stock, product in stock_rows:
        catalog_products.add(product.id)
        available = _to_decimal(stock.cantidad_disponible)
        stock_value += available * _to_decimal(product.costo_promedio)
        if available <= _to_decimal(product.stock_minimo):
            risky_products.add(product.id)

    sales_delta, sales_trend = _percentage_change(current_month_sales, previous_month_sales)
    purchases_delta, purchases_trend = _percentage_change(
        current_month_purchases, previous_month_purchases
    )
    risk_ratio = (
        (Decimal(len(risky_products)) / Decimal(len(catalog_products))) * Decimal("100")
        if catalog_products
        else Decimal("0.00")
    )
    collections_ratio = (
        (Decimal(overdue_receivables) / Decimal(len(receivables))) * Decimal("100")
        if receivables
        else Decimal("0.00")
    )
    sales_points, sales_polyline = _chart_series(monthly_sales)
    purchase_points, purchase_polyline = _chart_series(monthly_purchases)

    kpis = [
        {
            "label": "Ventas YTD",
            "value": _currency(sales_ytd),
            "delta": sales_delta,
            "trend": sales_trend,
            "meta": "vs mes anterior",
        },
        {
            "label": "Compras YTD",
            "value": _currency(purchases_ytd),
            "delta": purchases_delta,
            "trend": purchases_trend,
            "meta": "vs mes anterior",
        },
        {
            "label": "CxC pendiente",
            "value": _currency(pending_receivables),
            "delta": f"{collections_ratio:.1f}%",
            "trend": "down" if overdue_receivables else "up",
            "meta": "documentos vencidos",
        },
        {
            "label": "Stock valorizado",
            "value": _currency(stock_value),
            "delta": f"{risk_ratio:.1f}%",
            "trend": "down" if risky_products else "up",
            "meta": "catálogo bajo mínimo",
        },
    ]
    activity_overview = [
        {"label": "Empresas disponibles", "value": len(memberships)},
        {"label": "Módulos activos", "value": len(visible_modules)},
        {"label": "Rol activo", "value": ROLE_LABELS.get(active_role, active_role or "Sin rol")},
    ]
    quick_actions = [
        {
            "title": module["title"],
            "description": module["description"],
            "href": url_for(module["endpoint"]),
        }
        for module in visible_modules.values()
    ]

    # Recent activity: last 10 orders (sales + purchases combined)
    recent_orders: list[dict] = []
    for order in sales_orders[-5:]:
        recent_orders.append({
            "reference": f"PV-{order.id:04d}",
            "type": "Pedido de venta",
            "amount": _currency(_to_decimal(order.total)),
            "status": "Completado" if _to_decimal(order.total) > 0 else "Pendiente",
            "date": order.fecha.strftime("%d/%m/%Y"),
        })
    for order in purchase_orders[-5:]:
        recent_orders.append({
            "reference": f"OC-{order.id:04d}",
            "type": "Orden de compra",
            "amount": _currency(_to_decimal(order.total)),
            "status": "Completado" if order.estado == "recibida" else "Pendiente",
            "date": order.fecha.strftime("%d/%m/%Y"),
        })
    recent_orders.sort(key=lambda x: x["date"], reverse=True)
    recent_orders = recent_orders[:10]

    return render_template(
        "dashboard/index.html",
        active_role=active_role,
        activity_overview=activity_overview,
        kpis=kpis,
        quick_actions=quick_actions,
        recent_orders=recent_orders,
        sales_points=sales_points,
        sales_polyline=sales_polyline,
        purchase_points=purchase_points,
        purchase_polyline=purchase_polyline,
        category_bars=_bar_series(category_distribution),
        dashboard_year=today.year,
    )


@bp.post("/switch-company")
@login_required
def switch_company():
    empresa_id = request.form.get("empresa_id", type=int)
    if not current_user.can_access_empresa(empresa_id):
        abort(403)

    session["active_empresa_id"] = empresa_id
    flash("Empresa activa actualizada.", "success")
    next_url = request.form.get("next") or url_for("core.dashboard")
    # Protección contra Open Redirect: solo permitir rutas relativas
    parsed = urlparse(next_url)
    if parsed.netloc or parsed.scheme:
        next_url = url_for("core.dashboard")
    return redirect(next_url)


@bp.get("/modulos/<slug>")
@login_required
def module_placeholder(slug: str):
    module = MODULES.get(slug)
    if not module:
        abort(404)
    if not current_user.has_permission(module["permission"], session.get("active_empresa_id")):
        abort(403)
    if module["endpoint"] != "core.module_placeholder":
        return redirect(url_for(module["endpoint"]))
    allowed_roles = {
        "inventario": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_VENDEDOR, ROLE_LECTURA},
        "compras": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_LECTURA},
        "ventas": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_VENDEDOR, ROLE_LECTURA},
        "contabilidad": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_LECTURA},
        "tesoreria": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_LECTURA},
        "cxc-cxp": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_VENDEDOR, ROLE_LECTURA},
        "reportes": {ROLE_ADMIN, ROLE_CONTADOR, ROLE_VENDEDOR, ROLE_LECTURA},
    }
    active_role = current_user.role_for_empresa(session.get("active_empresa_id"))
    if active_role not in allowed_roles[slug]:
        abort(403)
    return render_template(
        "dashboard/module_placeholder.html",
        module=module,
        slug=slug,
    )


@bp.get("/uploads/brand/<path:filename>")
@login_required
def serve_brand_upload(filename):
    """Serve brand uploads from the protected UPLOAD_ROOT directory.
    
    Unlike static files, this endpoint requires authentication so that
    uploaded logos/favicons are not publicly accessible by URL.
    """
    upload_root = Path(current_app.config["UPLOAD_ROOT"])
    # Sanitize: ensure no path traversal
    safe_path = (upload_root / filename).resolve()
    if not str(safe_path).startswith(str(upload_root.resolve())):
        abort(404)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(upload_root, filename)


@bp.get("/healthz")
def healthcheck():
    return {"status": "ok", "service": "facilerp"}


@bp.get("/readyz")
def readiness():
    try:
        db.session.execute(text("SELECT 1"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        abort(503)
    return {"status": "ready", "database": "ok"}
