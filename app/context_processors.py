from __future__ import annotations

from flask import g, request, session
from flask_login import current_user

from app.extensions import db
from app.models import (
    MarcaConfig,
    PERM_ACCOUNTING_VIEW,
    PERM_BRAND_MANAGE,
    PERM_CXC_CXP_VIEW,
    PERM_INVENTORY_VIEW,
    PERM_PURCHASES_VIEW,
    PERM_REPORTS_VIEW,
    PERM_SALES_VIEW,
    PERM_SECURITY_VIEW,
    PERM_TREASURY_VIEW,
)
from app.security import get_active_empresa_id
from sqlalchemy.orm import joinedload


NAV_SECTIONS = [
    {
        "label": "Dashboard",
        "short_label": "DB",
        "icon": "dashboard",
        "endpoint": "core.dashboard",
    },
    {
        "label": "Inventario",
        "short_label": "IN",
        "icon": "inventory",
        "endpoint": "inventario.dashboard",
        "permission": PERM_INVENTORY_VIEW,
        "children": [
            {"label": "Productos", "endpoint": "inventario.products"},
            {"label": "Almacenes", "endpoint": "inventario.warehouses"},
            {"label": "Movimientos", "endpoint": "inventario.movements"},
        ],
    },
    {
        "label": "Compras",
        "short_label": "CO",
        "icon": "purchases",
        "endpoint": "compras.dashboard",
        "permission": PERM_PURCHASES_VIEW,
        "children": [
            {"label": "Órdenes", "endpoint": "compras.orders"},
            {"label": "Proveedores", "endpoint": "compras.suppliers"},
        ],
    },
    {
        "label": "Ventas",
        "short_label": "VE",
        "icon": "sales",
        "endpoint": "ventas.dashboard",
        "permission": PERM_SALES_VIEW,
        "children": [
            {"label": "Facturación", "endpoint": "ventas.invoices"},
            {"label": "Clientes", "endpoint": "ventas.clients"},
            {"label": "Notas de crédito", "endpoint": "ventas.credit_notes"},
        ],
    },
    {
        "label": "Contabilidad",
        "short_label": "CT",
        "icon": "accounting",
        "endpoint": "contabilidad.dashboard",
        "permission": PERM_ACCOUNTING_VIEW,
        "children": [
            {"label": "Asientos", "endpoint": "contabilidad.entries"},
            {"label": "Plan de cuentas", "endpoint": "contabilidad.chart_of_accounts"},
            {"label": "Libro mayor", "endpoint": "contabilidad.ledger"},
        ],
    },
    {
        "label": "Tesorería",
        "short_label": "TS",
        "icon": "treasury",
        "endpoint": "tesoreria.dashboard",
        "permission": PERM_TREASURY_VIEW,
        "children": [
            {"label": "Cajas y bancos", "endpoint": "tesoreria.accounts"},
            {"label": "Conciliación", "endpoint": "tesoreria.reconciliation"},
            {"label": "Flujo de caja", "endpoint": "tesoreria.cash_flow"},
        ],
    },
    {
        "label": "CxC / CxP",
        "short_label": "CC",
        "icon": "receivables",
        "endpoint": "cxc_cxp.dashboard",
        "permission": PERM_CXC_CXP_VIEW,
        "children": [
            {"label": "Cobros", "endpoint": "cxc_cxp.collections"},
            {"label": "Pagos", "endpoint": "cxc_cxp.payments"},
            {"label": "Antigüedad de cartera", "endpoint": "cxc_cxp.aging"},
        ],
    },
    {
        "label": "Reportes",
        "short_label": "RP",
        "icon": "reports",
        "endpoint": "reportes.dashboard",
        "permission": PERM_REPORTS_VIEW,
        "children": [
            {"label": "Ventas", "endpoint": "reportes.sales_reports"},
            {"label": "Inventario", "endpoint": "reportes.inventory_reports"},
            {"label": "Financieros", "endpoint": "reportes.financial_reports"},
        ],
    },
    {
        "label": "Seguridad",
        "short_label": "SG",
        "icon": "security",
        "endpoint": "seguridad.dashboard",
        "permission": PERM_SECURITY_VIEW,
        "children": [
            {"label": "Usuarios", "endpoint": "seguridad.users"},
            {"label": "Roles", "endpoint": "seguridad.roles"},
            {"label": "Empresas", "endpoint": "seguridad.companies"},
        ],
    },
    {
        "label": "Marca",
        "short_label": "MK",
        "icon": "brand",
        "endpoint": "marca.settings",
        "permission": PERM_BRAND_MANAGE,
        "children": [
            {"label": "Identidad", "endpoint": "marca.identity"},
            {"label": "Colores", "endpoint": "marca.colors"},
            {"label": "Plantillas", "endpoint": "marca.templates"},
        ],
    },
]


def _visible_sidebar_sections(empresa_id: int | None):
    sections = [NAV_SECTIONS[0]]
    if not current_user.is_authenticated:
        return sections

    if empresa_id is None:
        return sections

    sections = []
    for item in NAV_SECTIONS:
        permission = item.get("permission")
        if permission and not current_user.has_permission(permission, empresa_id):
            continue

        section = {key: value for key, value in item.items() if key != "children"}
        children = []
        for child in item.get("children", []):
            child_permission = child.get("permission", permission)
            if child_permission and not current_user.has_permission(child_permission, empresa_id):
                continue
            children.append(child)
        section["children"] = children
        sections.append(section)

    return sections


def _active_sidebar_section(sections: list[dict[str, object]], endpoint: str | None):
    if not endpoint:
        return None

    for section in sections:
        if endpoint == section["endpoint"]:
            return section
        if any(child["endpoint"] == endpoint for child in section.get("children", [])):
            return section

    return None


def register_context_processors(app):
    @app.context_processor
    def inject_globals():
        # Check request-level cache first
        cached = getattr(g, "_ctx_globals", None)
        if cached is not None:
            return cached

        empresa_activa = None
        marca = MarcaConfig.defaults()
        memberships = []
        sidebar_sections = [NAV_SECTIONS[0]]

        if current_user.is_authenticated:
            empresa_id = get_active_empresa_id()

            # Single query with joinedload to avoid N+1
            memberships = sorted(
                current_user.active_memberships(),
                key=lambda m: (
                    m.empresa_id != current_user.default_empresa_id,
                    m.empresa.razon_social.lower(),
                ),
            )
            if empresa_id:
                for membership in memberships:
                    if membership.empresa_id == empresa_id:
                        empresa_activa = membership.empresa
                        marca = membership.empresa.brand
                        break
            sidebar_sections = _visible_sidebar_sections(empresa_id)
        active_section = _active_sidebar_section(sidebar_sections, request.endpoint)

        result = {
            "app_name": app.config["APP_NAME"],
            "marca": marca,
            "empresa_activa": empresa_activa,
            "empresa_activa_id": session.get("active_empresa_id"),
            "empresas_disponibles": memberships,
            "sidebar_sections": sidebar_sections,
            "active_section": active_section,
            "topbar_links": active_section.get("children", []) if active_section else [],
            "current_endpoint": request.endpoint,
        }

        g._ctx_globals = result
        return result
