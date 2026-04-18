from __future__ import annotations

from datetime import date, datetime, time, timezone

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Almacen,
    AuditLog,
    Empresa,
    MarcaConfig,
    PERMISSION_GROUPS,
    PERMISSION_LABELS,
    PERM_SECURITY_MANAGE_GROUPS,
    PERM_SECURITY_MANAGE_USERS,
    PERM_SECURITY_VIEW,
    ROLE_ADMIN,
    ROLE_LABELS,
    SecurityGroup,
    SecurityGroupPermission,
    SecurityUserGroup,
    SecurityWarehouseAccess,
    User,
    UserEmpresaRole,
)
from app.modules.seguridad import bp
from app.modules.seguridad.forms import SecurityCompanyForm, SecurityGroupForm, SecurityUserForm
from app.security import permission_required
from app.services.accounting import ensure_accounting_setup


def _empresa_id() -> int:
    return int(session["active_empresa_id"])


def _role_choices() -> list[tuple[str, str]]:
    return [(code, label) for code, label in ROLE_LABELS.items()]


def _permission_choices() -> list[tuple[str, str]]:
    return [(code, label) for code, label in PERMISSION_LABELS.items()]


def _permission_catalog() -> list[dict[str, object]]:
    return [
        {
            "title": title,
            "permissions": [
                {"code": code, "label": PERMISSION_LABELS[code]} for code in permissions
            ],
        }
        for title, permissions in PERMISSION_GROUPS
    ]


def _active_admin_count(empresa_id: int) -> int:
    memberships = UserEmpresaRole.query.filter_by(
        empresa_id=empresa_id,
        rol=ROLE_ADMIN,
    ).all()
    return sum(1 for membership in memberships if membership.is_currently_active())


def _manageable_company_memberships() -> list[UserEmpresaRole]:
    return [
        membership
        for membership in current_user.memberships
        if membership.is_currently_active() and membership.empresa is not None
    ]


def _membership_or_404(user_id: str, empresa_id: int) -> UserEmpresaRole:
    membership = UserEmpresaRole.query.filter_by(
        user_id=user_id,
        empresa_id=empresa_id,
    ).first()
    if membership is None:
        abort(404)
    return membership


def _group_or_404(group_id: int, empresa_id: int) -> SecurityGroup:
    group = SecurityGroup.query.filter_by(id=group_id, empresa_id=empresa_id).first()
    if group is None:
        abort(404)
    return group


def _parse_expiration(raw_value: str | None) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    parsed = date.fromisoformat(value)
    return datetime.combine(parsed, time(23, 59, 59), tzinfo=timezone.utc)


def _audit(action: str, empresa_id: int, detail: str | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            empresa_id=empresa_id,
            accion=action,
            detalle=detail,
            ip=request.remote_addr,
        )
    )


def _render_dashboard(
    empresa_id: int,
    user_form: SecurityUserForm,
    group_form: SecurityGroupForm,
    company_form: SecurityCompanyForm,
    *,
    active_submodule: str,
):
    memberships = (
        UserEmpresaRole.query.filter_by(empresa_id=empresa_id)
        .order_by(UserEmpresaRole.activo.desc(), UserEmpresaRole.created_at.asc())
        .all()
    )
    groups = (
        SecurityGroup.query.filter_by(empresa_id=empresa_id)
        .order_by(SecurityGroup.activo.desc(), SecurityGroup.nombre.asc())
        .all()
    )
    warehouses = (
        Almacen.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(Almacen.nombre.asc())
        .all()
    )
    active_groups = [group for group in groups if group.activo]

    user_rows = []
    for membership in memberships:
        user = membership.user
        assigned_groups = user.groups_for_empresa(empresa_id)
        assigned_warehouses = user.allowed_warehouse_ids(empresa_id)
        effective_codes = sorted(user.permissions_for_empresa(empresa_id))
        user_rows.append(
            {
                "membership": membership,
                "user": user,
                "assigned_groups": assigned_groups,
                "assigned_group_ids": {group.id for group in assigned_groups},
                "assigned_warehouse_ids": assigned_warehouses or set(),
                "warehouse_scope_enabled": assigned_warehouses is not None,
                "effective_permissions": [
                    {"code": code, "label": PERMISSION_LABELS[code]} for code in effective_codes
                ],
            }
        )

    group_rows = []
    for group in groups:
        member_count = sum(
            1
            for assignment in group.assignments
            if assignment.is_currently_active()
            and assignment.user.membership_for_empresa(empresa_id)
        )
        group_rows.append(
            {
                "group": group,
                "member_count": member_count,
                "permission_codes": group.permission_codes,
                "permission_labels": [
                    PERMISSION_LABELS[code] for code in sorted(group.permission_codes)
                ],
            }
        )

    company_rows = []
    for membership in sorted(
        _manageable_company_memberships(),
        key=lambda item: (item.empresa.razon_social.lower(), item.empresa_id),
    ):
        empresa = membership.empresa
        company_rows.append(
            {
                "empresa": empresa,
                "membership": membership,
                "user_count": UserEmpresaRole.query.filter_by(empresa_id=empresa.id).count(),
                "group_count": SecurityGroup.query.filter_by(empresa_id=empresa.id).count(),
                "is_current": empresa.id == empresa_id,
                "is_default": current_user.default_empresa_id == empresa.id,
            }
        )

    return render_template(
        "seguridad/dashboard.html",
        user_form=user_form,
        group_form=group_form,
        company_form=company_form,
        user_rows=user_rows,
        group_rows=group_rows,
        company_rows=company_rows,
        active_groups=active_groups,
        warehouses=warehouses,
        permission_catalog=_permission_catalog(),
        role_choices=_role_choices(),
        can_manage_users=current_user.has_permission(PERM_SECURITY_MANAGE_USERS, empresa_id),
        can_manage_groups=current_user.has_permission(PERM_SECURITY_MANAGE_GROUPS, empresa_id),
        active_submodule=active_submodule,
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SECURITY_VIEW)
def dashboard():
    if request.method == "POST":
        if request.form.get("group-submit"):
            return _render_security_workspace("roles")
        return _render_security_workspace("usuarios")

    empresa_id = _empresa_id()
    memberships = UserEmpresaRole.query.filter_by(empresa_id=empresa_id).count()
    groups = SecurityGroup.query.filter_by(empresa_id=empresa_id).count()
    warehouses = Almacen.query.filter_by(empresa_id=empresa_id, activo=True).count()
    companies = len(current_user.active_memberships())
    return render_template(
        "dashboard/module_hub.html",
        module_title="Seguridad",
        module_heading="Seguridad",
        module_badges=[
            {"label": "Gobierno de acceso", "color": "blue"},
            {"label": f"{memberships} usuarios"},
        ],
        module_stats=[
            {"label": "Usuarios", "value": memberships, "meta": "Accesos asociados a la empresa."},
            {"label": "Grupos", "value": groups, "meta": "Equipos con permisos efectivos."},
            {"label": "Almacenes", "value": warehouses, "meta": "Ubicaciones disponibles para alcance."},
            {"label": "Empresas", "value": companies, "meta": "Razones sociales vinculadas a tu usuario."},
        ],
        module_actions=[
            {"label": "Usuarios", "href": url_for("seguridad.users"), "primary": True},
            {"label": "Roles", "href": url_for("seguridad.roles")},
            {"label": "Empresas", "href": url_for("seguridad.companies")},
        ],
        module_children=[
            {
                "label": "Usuarios",
                "href": url_for("seguridad.users"),
                "description": "Administra accesos, vigencias, grupos y alcance por almacén.",
            },
            {
                "label": "Roles",
                "href": url_for("seguridad.roles"),
                "description": "Define grupos, permisos y la estructura de acceso de la empresa.",
            },
            {
                "label": "Empresas",
                "href": url_for("seguridad.companies"),
                "description": "Crea empresas nuevas, ajusta sus datos base y define tu empresa predeterminada.",
            },
        ],
    )


def _render_security_workspace(active_submodule: str):
    empresa_id = _empresa_id()
    user_form = SecurityUserForm(prefix="user")
    group_form = SecurityGroupForm(prefix="group")
    company_form = SecurityCompanyForm(prefix="company")
    user_form.rol.choices = _role_choices()
    group_form.permisos.choices = _permission_choices()

    if request.method == "POST":
        if user_form.submit.data:
            if not current_user.has_permission(PERM_SECURITY_MANAGE_USERS, empresa_id):
                abort(403)
            if user_form.validate_on_submit():
                return _create_or_attach_user(user_form, group_form, company_form, empresa_id)
        elif group_form.submit.data:
            if not current_user.has_permission(PERM_SECURITY_MANAGE_GROUPS, empresa_id):
                abort(403)
            if group_form.validate_on_submit():
                return _create_group(user_form, group_form, company_form, empresa_id)
        elif company_form.submit.data:
            if not current_user.has_permission(PERM_SECURITY_MANAGE_USERS, empresa_id):
                abort(403)
            if company_form.validate_on_submit():
                return _create_company(user_form, group_form, company_form, empresa_id)

    return _render_dashboard(
        empresa_id,
        user_form,
        group_form,
        company_form,
        active_submodule=active_submodule,
    )


@bp.route("/usuarios", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SECURITY_VIEW)
def users():
    return _render_security_workspace("usuarios")


@bp.route("/roles", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SECURITY_VIEW)
def roles():
    return _render_security_workspace("roles")


@bp.route("/empresas", methods=["GET", "POST"])
@login_required
@permission_required(PERM_SECURITY_VIEW)
def companies():
    return _render_security_workspace("empresas")


def _create_or_attach_user(
    user_form: SecurityUserForm,
    group_form: SecurityGroupForm,
    company_form: SecurityCompanyForm,
    empresa_id: int,
):
    nombre = (user_form.nombre.data or "").strip()
    email = (user_form.email.data or "").strip().lower()
    password = user_form.password.data or ""

    user = User.query.filter_by(email=email).first()
    created = False
    if user is None:
        if not password:
            user_form.password.errors.append(
                "La contraseña inicial es obligatoria para usuarios nuevos."
            )
            return _render_dashboard(
                empresa_id,
                user_form,
                group_form,
                company_form,
                active_submodule="usuarios",
            )
        user = User(email=email, nombre=nombre, activo=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        created = True
    else:
        membership = UserEmpresaRole.query.filter_by(
            user_id=user.id,
            empresa_id=empresa_id,
        ).first()
        if membership is not None:
            user_form.email.errors.append("Ese usuario ya pertenece a la empresa activa.")
            return _render_dashboard(
                empresa_id,
                user_form,
                group_form,
                company_form,
                active_submodule="usuarios",
            )
        if password:
            user.set_password(password)
        user.nombre = nombre
        user.activo = True

    db.session.add(
        UserEmpresaRole(
            user_id=user.id,
            empresa_id=empresa_id,
            rol=user_form.rol.data,
            activo=True,
        )
    )
    _audit(
        "seguridad.usuario.created" if created else "seguridad.usuario.linked",
        empresa_id,
        detail=f"{email} · rol {ROLE_LABELS[user_form.rol.data]}",
    )
    db.session.commit()
    flash("Usuario guardado en la empresa activa.", "success")
    return redirect(url_for("seguridad.users"))


def _create_group(
    user_form: SecurityUserForm,
    group_form: SecurityGroupForm,
    company_form: SecurityCompanyForm,
    empresa_id: int,
):
    nombre = (group_form.nombre.data or "").strip()
    exists = SecurityGroup.query.filter_by(empresa_id=empresa_id, nombre=nombre).first()
    if exists is not None:
        group_form.nombre.errors.append("Ya existe un grupo con ese nombre en la empresa activa.")
        return _render_dashboard(
            empresa_id,
            user_form,
            group_form,
            company_form,
            active_submodule="roles",
        )

    group = SecurityGroup(
        empresa_id=empresa_id,
        nombre=nombre,
        descripcion=(group_form.descripcion.data or "").strip() or None,
        activo=True,
    )
    db.session.add(group)
    db.session.flush()
    for code in group_form.permisos.data:
        if code in PERMISSION_LABELS:
            db.session.add(SecurityGroupPermission(group_id=group.id, permission_code=code))
    _audit(
        "seguridad.grupo.created",
        empresa_id,
        detail=f"{nombre} · {len(group_form.permisos.data)} permiso(s)",
    )
    db.session.commit()
    flash("Grupo guardado.", "success")
    return redirect(url_for("seguridad.roles"))


def _create_company(
    user_form: SecurityUserForm,
    group_form: SecurityGroupForm,
    company_form: SecurityCompanyForm,
    empresa_id: int,
):
    del empresa_id
    ruc = (company_form.ruc.data or "").strip()
    razon_social = (company_form.razon_social.data or "").strip()
    regimen_tributario = (company_form.regimen_tributario.data or "").strip()
    if len(ruc) != 11 or not ruc.isdigit():
        company_form.ruc.errors.append("El RUC debe tener 11 dígitos.")
        return _render_dashboard(
            _empresa_id(),
            user_form,
            group_form,
            company_form,
            active_submodule="empresas",
        )
    if Empresa.query.filter_by(ruc=ruc).first() is not None:
        company_form.ruc.errors.append("Ya existe una empresa registrada con ese RUC.")
        return _render_dashboard(
            _empresa_id(),
            user_form,
            group_form,
            company_form,
            active_submodule="empresas",
        )

    empresa = Empresa(
        ruc=ruc,
        razon_social=razon_social,
        moneda=company_form.moneda.data,
        regimen_tributario=regimen_tributario,
        activa=True,
    )
    db.session.add(empresa)
    db.session.flush()
    db.session.add(
        UserEmpresaRole(
            user_id=current_user.id,
            empresa_id=empresa.id,
            rol=ROLE_ADMIN,
            activo=True,
        )
    )
    db.session.add(
        MarcaConfig(
            empresa_id=empresa.id,
            nombre_sistema=razon_social,
            updated_by=current_user.id,
        )
    )
    ensure_accounting_setup(empresa.id)
    if current_user.default_empresa_id is None:
        current_user.default_empresa_id = empresa.id
    _audit(
        "seguridad.empresa.created",
        _empresa_id(),
        detail=f"{razon_social} · {ruc}",
    )
    db.session.commit()
    flash("Empresa creada y vinculada a tu usuario administrador.", "success")
    return redirect(url_for("seguridad.companies"))


@bp.post("/usuarios/<user_id>/rol")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def update_user_role(user_id: str):
    empresa_id = _empresa_id()
    membership = _membership_or_404(user_id, empresa_id)
    new_role = request.form.get("rol", "").strip()
    if new_role not in ROLE_LABELS:
        flash("Rol inválido.", "error")
        return redirect(url_for("seguridad.users"))
    if (
        membership.rol == ROLE_ADMIN
        and new_role != ROLE_ADMIN
        and membership.activo
        and _active_admin_count(empresa_id) <= 1
    ):
        flash("La empresa debe conservar al menos un administrador activo.", "error")
        return redirect(url_for("seguridad.users"))

    membership.rol = new_role
    _audit(
        "seguridad.usuario.role_updated",
        empresa_id,
        detail=f"{membership.user.email} · {ROLE_LABELS[new_role]}",
    )
    db.session.commit()
    flash("Rol actualizado.", "success")
    return redirect(url_for("seguridad.users"))


@bp.post("/usuarios/<user_id>/expiracion")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def update_user_expiration(user_id: str):
    empresa_id = _empresa_id()
    membership = _membership_or_404(user_id, empresa_id)
    expires_at = _parse_expiration(request.form.get("expires_at"))
    will_disable_admin = (
        membership.rol == ROLE_ADMIN
        and membership.is_currently_active()
        and expires_at is not None
        and expires_at < datetime.now(timezone.utc)
        and _active_admin_count(empresa_id) <= 1
    )
    if will_disable_admin:
        flash("La empresa debe conservar al menos un administrador activo.", "error")
        return redirect(url_for("seguridad.users"))
    membership.expires_at = expires_at
    _audit(
        "seguridad.usuario.expiration_updated",
        empresa_id,
        detail=f"{membership.user.email} · vence {membership.expires_at.isoformat() if membership.expires_at else 'sin vencimiento'}",
    )
    db.session.commit()
    flash("Vencimiento del acceso actualizado.", "success")
    return redirect(url_for("seguridad.users"))


@bp.post("/usuarios/<user_id>/estado")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def toggle_user_membership(user_id: str):
    empresa_id = _empresa_id()
    membership = _membership_or_404(user_id, empresa_id)
    if membership.rol == ROLE_ADMIN and membership.activo and _active_admin_count(empresa_id) <= 1:
        flash("La empresa debe conservar al menos un administrador activo.", "error")
        return redirect(url_for("seguridad.users"))

    membership.activo = not membership.activo
    _audit(
        "seguridad.usuario.state_updated",
        empresa_id,
        detail=f"{membership.user.email} · {'activo' if membership.activo else 'inactivo'}",
    )
    db.session.commit()
    flash("Estado del usuario actualizado.", "success")
    return redirect(url_for("seguridad.users"))


@bp.post("/usuarios/<user_id>/password")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def update_user_password(user_id: str):
    empresa_id = _empresa_id()
    membership = _membership_or_404(user_id, empresa_id)
    password = (request.form.get("password") or "").strip()
    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("seguridad.users"))

    membership.user.set_password(password)
    _audit("seguridad.usuario.password_updated", empresa_id, detail=membership.user.email)
    db.session.commit()
    flash("Contraseña actualizada.", "success")
    return redirect(url_for("seguridad.users"))


@bp.post("/usuarios/<user_id>/grupos")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def update_user_groups(user_id: str):
    empresa_id = _empresa_id()
    membership = _membership_or_404(user_id, empresa_id)
    selected_ids = {
        int(group_id)
        for group_id in request.form.getlist("group_ids")
        if group_id.isdigit()
    }
    groups = SecurityGroup.query.filter_by(empresa_id=empresa_id).all()
    assignment_map = {
        assignment.group_id: assignment for assignment in membership.user.group_assignments
    }
    for group in groups:
        assignment = assignment_map.get(group.id)
        if group.id in selected_ids and group.activo:
            if assignment is None:
                db.session.add(
                    SecurityUserGroup(
                        user_id=membership.user_id,
                        group_id=group.id,
                        activo=True,
                    )
                )
            else:
                assignment.activo = True
        elif assignment is not None:
            assignment.activo = False

    _audit(
        "seguridad.usuario.groups_updated",
        empresa_id,
        detail=f"{membership.user.email} · {len(selected_ids)} grupo(s)",
    )
    db.session.commit()
    flash("Grupos actualizados.", "success")
    return redirect(url_for("seguridad.roles"))


@bp.post("/usuarios/<user_id>/almacenes")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def update_user_warehouses(user_id: str):
    empresa_id = _empresa_id()
    membership = _membership_or_404(user_id, empresa_id)
    selected_ids = {
        int(warehouse_id)
        for warehouse_id in request.form.getlist("almacen_ids")
        if warehouse_id.isdigit()
    }
    warehouses = Almacen.query.filter_by(empresa_id=empresa_id, activo=True).all()
    assignment_map = {
        assignment.almacen_id: assignment
        for assignment in membership.user.warehouse_assignments
        if assignment.empresa_id == empresa_id
    }
    for warehouse in warehouses:
        assignment = assignment_map.get(warehouse.id)
        if warehouse.id in selected_ids:
            if assignment is None:
                db.session.add(
                    SecurityWarehouseAccess(
                        user_id=membership.user_id,
                        empresa_id=empresa_id,
                        almacen_id=warehouse.id,
                        activo=True,
                    )
                )
            else:
                assignment.activo = True
        elif assignment is not None:
            assignment.activo = False

    _audit(
        "seguridad.usuario.warehouses_updated",
        empresa_id,
        detail=f"{membership.user.email} · {len(selected_ids)} almacén(es)",
    )
    db.session.commit()
    flash("Alcance por almacén actualizado.", "success")
    return redirect(url_for("seguridad.roles"))


@bp.post("/grupos/<int:group_id>/estado")
@login_required
@permission_required(PERM_SECURITY_MANAGE_GROUPS)
def toggle_group(group_id: int):
    empresa_id = _empresa_id()
    group = _group_or_404(group_id, empresa_id)
    group.activo = not group.activo
    _audit(
        "seguridad.grupo.state_updated",
        empresa_id,
        detail=f"{group.nombre} · {'activo' if group.activo else 'inactivo'}",
    )
    db.session.commit()
    flash("Estado del grupo actualizado.", "success")
    return redirect(url_for("seguridad.roles"))


@bp.post("/grupos/<int:group_id>/permisos")
@login_required
@permission_required(PERM_SECURITY_MANAGE_GROUPS)
def update_group(group_id: int):
    empresa_id = _empresa_id()
    group = _group_or_404(group_id, empresa_id)
    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip() or None
    permission_codes = {
        code for code in request.form.getlist("permission_codes") if code in PERMISSION_LABELS
    }

    if not nombre:
        flash("El grupo debe tener un nombre.", "error")
        return redirect(url_for("seguridad.roles"))

    duplicate = (
        SecurityGroup.query.filter(
            SecurityGroup.empresa_id == empresa_id,
            SecurityGroup.nombre == nombre,
            SecurityGroup.id != group.id,
        ).first()
    )
    if duplicate is not None:
        flash("Ya existe otro grupo con ese nombre.", "error")
        return redirect(url_for("seguridad.roles"))

    group.nombre = nombre
    group.descripcion = descripcion
    group.permissions.clear()
    for code in sorted(permission_codes):
        group.permissions.append(SecurityGroupPermission(permission_code=code))

    _audit(
        "seguridad.grupo.permissions_updated",
        empresa_id,
        detail=f"{group.nombre} · {len(permission_codes)} permiso(s)",
    )
    db.session.commit()
    flash("Grupo actualizado.", "success")
    return redirect(url_for("seguridad.roles"))


def _company_membership_or_403(company_id: int) -> UserEmpresaRole:
    membership = UserEmpresaRole.query.filter_by(
        user_id=current_user.id,
        empresa_id=company_id,
    ).first()
    if membership is None or membership.rol != ROLE_ADMIN or not membership.is_currently_active():
        abort(403)
    return membership


@bp.post("/empresas/<int:company_id>/actualizar")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def update_company(company_id: int):
    _company_membership_or_403(company_id)
    empresa = Empresa.query.get_or_404(company_id)
    old_razon_social = empresa.razon_social
    old_brand_name = empresa.marca.nombre_sistema if empresa.marca is not None else None
    ruc = (request.form.get("ruc") or "").strip()
    razon_social = (request.form.get("razon_social") or "").strip()
    moneda = (request.form.get("moneda") or "").strip() or empresa.moneda
    regimen_tributario = (request.form.get("regimen_tributario") or "").strip()

    if len(ruc) != 11 or not ruc.isdigit():
        flash("El RUC debe tener 11 dígitos.", "error")
        return redirect(url_for("seguridad.companies"))
    if not razon_social or not regimen_tributario:
        flash("Completa razón social y régimen tributario.", "error")
        return redirect(url_for("seguridad.companies"))

    duplicate = Empresa.query.filter(Empresa.ruc == ruc, Empresa.id != company_id).first()
    if duplicate is not None:
        flash("Ya existe otra empresa con ese RUC.", "error")
        return redirect(url_for("seguridad.companies"))

    empresa.ruc = ruc
    empresa.razon_social = razon_social
    empresa.moneda = moneda
    empresa.regimen_tributario = regimen_tributario
    if empresa.marca is not None and old_brand_name == old_razon_social:
        empresa.marca.nombre_sistema = razon_social
    _audit("seguridad.empresa.updated", _empresa_id(), detail=f"{empresa.razon_social} · {empresa.ruc}")
    db.session.commit()
    flash("Empresa actualizada.", "success")
    return redirect(url_for("seguridad.companies"))


@bp.post("/empresas/<int:company_id>/predeterminada")
@login_required
@permission_required(PERM_SECURITY_VIEW)
def set_default_company(company_id: int):
    if not current_user.can_access_empresa(company_id):
        abort(403)
    current_user.default_empresa_id = company_id
    db.session.commit()
    flash("Empresa predeterminada actualizada.", "success")
    return redirect(url_for("seguridad.companies"))


@bp.post("/empresas/<int:company_id>/estado")
@login_required
@permission_required(PERM_SECURITY_MANAGE_USERS)
def toggle_company(company_id: int):
    _company_membership_or_403(company_id)
    empresa = Empresa.query.get_or_404(company_id)
    active_memberships = [
        membership
        for membership in current_user.active_memberships()
        if membership.empresa_id != company_id
    ]
    if empresa.activa and not active_memberships:
        flash("Tu usuario debe conservar al menos una empresa activa.", "error")
        return redirect(url_for("seguridad.companies"))

    empresa.activa = not empresa.activa
    if not empresa.activa:
        if session.get("active_empresa_id") == empresa.id:
            session["active_empresa_id"] = active_memberships[0].empresa_id if active_memberships else None
        if current_user.default_empresa_id == empresa.id:
            current_user.default_empresa_id = active_memberships[0].empresa_id if active_memberships else None
    _audit(
        "seguridad.empresa.state_updated",
        _empresa_id(),
        detail=f"{empresa.razon_social} · {'activa' if empresa.activa else 'inactiva'}",
    )
    db.session.commit()
    flash("Estado de la empresa actualizado.", "success")
    return redirect(url_for("seguridad.companies"))
