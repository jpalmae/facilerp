from __future__ import annotations

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AuditLog, MarcaConfig, PERM_BRAND_MANAGE
from app.modules.marca import bp
from app.modules.marca.forms import BrandForm
from app.security import permission_required
from app.services.storage import get_brand_storage, validate_image_upload


def get_or_create_brand(empresa_id: int) -> MarcaConfig:
    brand = MarcaConfig.query.filter_by(empresa_id=empresa_id).first()
    if brand:
        return brand

    defaults = MarcaConfig.defaults()
    brand = MarcaConfig(
        empresa_id=empresa_id,
        nombre_sistema=defaults.nombre_sistema,
        logo_url=defaults.logo_url,
        favicon_url=defaults.favicon_url,
        color_primary=defaults.color_primary,
        color_secondary=defaults.color_secondary,
        updated_by=current_user.id,
    )
    db.session.add(brand)
    db.session.flush()
    return brand


def _render_brand_workspace(active_submodule: str):
    empresa_id = session["active_empresa_id"]
    brand = get_or_create_brand(empresa_id)
    form = BrandForm(obj=brand)
    endpoint_map = {
        "identidad": "marca.identity",
        "colores": "marca.colors",
        "plantillas": "marca.templates",
    }
    current_view_endpoint = endpoint_map[active_submodule]

    if form.validate_on_submit():
        brand.nombre_sistema = form.nombre_sistema.data.strip()
        brand.color_primary = form.color_primary.data.upper()
        brand.color_secondary = form.color_secondary.data.upper()
        brand.updated_by = current_user.id

        storage = get_brand_storage()
        logo = form.logo.data
        if logo and getattr(logo, "filename", ""):
            try:
                validate_image_upload(logo, "logo")
            except ValueError as exc:
                form.logo.errors.append(str(exc))
                return (
                    render_template(
                        "marca/settings.html",
                        form=form,
                        brand=brand,
                        active_submodule=active_submodule,
                    ),
                    400,
                )
            brand.logo_url = storage.save(logo, empresa_id, "logo")

        favicon = form.favicon.data
        if favicon and getattr(favicon, "filename", ""):
            try:
                validate_image_upload(favicon, "favicon")
            except ValueError as exc:
                form.favicon.errors.append(str(exc))
                return (
                    render_template(
                        "marca/settings.html",
                        form=form,
                        brand=brand,
                        active_submodule=active_submodule,
                    ),
                    400,
                )
            brand.favicon_url = storage.save(favicon, empresa_id, "favicon")

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                empresa_id=empresa_id,
                accion="marca.updated",
                ip=request.remote_addr,
            )
        )
        db.session.commit()
        flash("Identidad visual actualizada.", "success")
        return redirect(url_for(current_view_endpoint))

    return render_template(
        "marca/settings.html",
        form=form,
        brand=brand,
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_BRAND_MANAGE)
def settings():
    if request.method == "POST":
        return _render_brand_workspace("identidad")

    empresa_id = session["active_empresa_id"]
    brand = get_or_create_brand(empresa_id)
    return render_template(
        "dashboard/module_hub.html",
        module_title="Marca",
        module_heading="Marca",
        module_badges=[
            {"label": "White label", "color": "blue"},
            {"label": brand.nombre_sistema},
        ],
        module_stats=[
            {"label": "Sistema", "value": brand.nombre_sistema, "meta": "Nombre visible actual."},
            {"label": "Primario", "value": brand.color_primary, "meta": "Color principal activo."},
            {"label": "Secundario", "value": brand.color_secondary, "meta": "Color secundario activo."},
        ],
        module_actions=[
            {"label": "Identidad", "href": url_for("marca.identity"), "primary": True},
            {"label": "Colores", "href": url_for("marca.colors")},
        ],
        module_children=[
            {
                "label": "Identidad",
                "href": url_for("marca.identity"),
                "description": "Edita nombre del sistema, logo y favicon desde una vista dedicada.",
            },
            {
                "label": "Colores",
                "href": url_for("marca.colors"),
                "description": "Ajusta paleta principal y secundaria con vista previa inmediata.",
            },
            {
                "label": "Plantillas",
                "href": url_for("marca.templates"),
                "description": "Reserva el espacio para futuras plantillas de documentos y branding extendido.",
            },
        ],
    )


@bp.route("/identidad", methods=["GET", "POST"])
@login_required
@permission_required(PERM_BRAND_MANAGE)
def identity():
    return _render_brand_workspace("identidad")


@bp.route("/colores", methods=["GET", "POST"])
@login_required
@permission_required(PERM_BRAND_MANAGE)
def colors():
    return _render_brand_workspace("colores")


@bp.route("/plantillas", methods=["GET", "POST"])
@login_required
@permission_required(PERM_BRAND_MANAGE)
def templates():
    return _render_brand_workspace("plantillas")


@bp.post("/reset")
@login_required
@permission_required(PERM_BRAND_MANAGE)
def reset():
    empresa_id = session["active_empresa_id"]
    brand = get_or_create_brand(empresa_id)
    brand.reset_defaults()
    brand.updated_by = current_user.id
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            empresa_id=empresa_id,
            accion="marca.reset",
            ip=request.remote_addr,
        )
    )
    db.session.commit()
    flash("Se restauró la marca por defecto.", "success")
    return redirect(url_for("marca.identity"))
