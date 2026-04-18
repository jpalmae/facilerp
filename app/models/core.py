from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from flask import g
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import ExpirableMixin


ROLE_ADMIN = "admin"
ROLE_CONTADOR = "contador"
ROLE_VENDEDOR = "vendedor"
ROLE_LECTURA = "lectura"

ROLE_LABELS = {
    ROLE_ADMIN: "Administrador",
    ROLE_CONTADOR: "Contador",
    ROLE_VENDEDOR: "Vendedor",
    ROLE_LECTURA: "Solo lectura",
}

PERM_SECURITY_VIEW = "security.view"
PERM_SECURITY_MANAGE_USERS = "security.users.manage"
PERM_SECURITY_MANAGE_GROUPS = "security.groups.manage"
PERM_BRAND_MANAGE = "brand.manage"
PERM_INVENTORY_VIEW = "inventory.view"
PERM_INVENTORY_MANAGE = "inventory.manage"
PERM_PURCHASES_VIEW = "purchases.view"
PERM_PURCHASES_MANAGE = "purchases.manage"
PERM_SALES_VIEW = "sales.view"
PERM_SALES_MANAGE = "sales.manage"
PERM_CXC_CXP_VIEW = "cxc_cxp.view"
PERM_CXC_CXP_MANAGE = "cxc_cxp.manage"
PERM_ACCOUNTING_VIEW = "accounting.view"
PERM_ACCOUNTING_MANAGE = "accounting.manage"
PERM_TREASURY_VIEW = "treasury.view"
PERM_TREASURY_MANAGE = "treasury.manage"
PERM_REPORTS_VIEW = "reports.view"

PERMISSION_LABELS = {
    PERM_SECURITY_VIEW: "Ver seguridad",
    PERM_SECURITY_MANAGE_USERS: "Gestionar usuarios",
    PERM_SECURITY_MANAGE_GROUPS: "Gestionar grupos y permisos",
    PERM_BRAND_MANAGE: "Gestionar marca",
    PERM_INVENTORY_VIEW: "Ver inventario",
    PERM_INVENTORY_MANAGE: "Gestionar inventario",
    PERM_PURCHASES_VIEW: "Ver compras",
    PERM_PURCHASES_MANAGE: "Gestionar compras",
    PERM_SALES_VIEW: "Ver ventas",
    PERM_SALES_MANAGE: "Gestionar ventas",
    PERM_CXC_CXP_VIEW: "Ver CxC / CxP",
    PERM_CXC_CXP_MANAGE: "Gestionar cobros y pagos",
    PERM_ACCOUNTING_VIEW: "Ver contabilidad",
    PERM_ACCOUNTING_MANAGE: "Gestionar contabilidad",
    PERM_TREASURY_VIEW: "Ver tesorería",
    PERM_TREASURY_MANAGE: "Gestionar tesorería",
    PERM_REPORTS_VIEW: "Ver reportes",
}

PERMISSION_GROUPS = (
    (
        "Seguridad",
        (
            PERM_SECURITY_VIEW,
            PERM_SECURITY_MANAGE_USERS,
            PERM_SECURITY_MANAGE_GROUPS,
        ),
    ),
    ("Configuración", (PERM_BRAND_MANAGE,)),
    ("Inventario", (PERM_INVENTORY_VIEW, PERM_INVENTORY_MANAGE)),
    ("Compras", (PERM_PURCHASES_VIEW, PERM_PURCHASES_MANAGE)),
    ("Ventas", (PERM_SALES_VIEW, PERM_SALES_MANAGE)),
    ("CxC / CxP", (PERM_CXC_CXP_VIEW, PERM_CXC_CXP_MANAGE)),
    ("Contabilidad", (PERM_ACCOUNTING_VIEW, PERM_ACCOUNTING_MANAGE)),
    ("Tesorería", (PERM_TREASURY_VIEW, PERM_TREASURY_MANAGE)),
    ("Reportes", (PERM_REPORTS_VIEW,)),
)

ROLE_PERMISSION_MAP = {
    ROLE_ADMIN: set(PERMISSION_LABELS),
    ROLE_CONTADOR: {
        PERM_INVENTORY_VIEW,
        PERM_PURCHASES_VIEW,
        PERM_PURCHASES_MANAGE,
        PERM_SALES_VIEW,
        PERM_CXC_CXP_VIEW,
        PERM_CXC_CXP_MANAGE,
        PERM_ACCOUNTING_VIEW,
        PERM_ACCOUNTING_MANAGE,
        PERM_TREASURY_VIEW,
        PERM_TREASURY_MANAGE,
        PERM_REPORTS_VIEW,
    },
    ROLE_VENDEDOR: {
        PERM_INVENTORY_VIEW,
        PERM_SALES_VIEW,
        PERM_SALES_MANAGE,
        PERM_CXC_CXP_VIEW,
        PERM_REPORTS_VIEW,
    },
    ROLE_LECTURA: {
        PERM_INVENTORY_VIEW,
        PERM_PURCHASES_VIEW,
        PERM_SALES_VIEW,
        PERM_CXC_CXP_VIEW,
        PERM_ACCOUNTING_VIEW,
        PERM_TREASURY_VIEW,
        PERM_REPORTS_VIEW,
    },
}


def permissions_for_role(role: str | None) -> set[str]:
    return set(ROLE_PERMISSION_MAP.get(role, set()))


@dataclass
class DefaultBrand:
    nombre_sistema: str = "FacilERP"
    logo_url: str = "/static/img/defaults/facilerp-logo.svg"
    favicon_url: str = "/static/img/defaults/facilerp-favicon.svg"
    color_primary: str = "#2563EB"
    color_secondary: str = "#1E3A5F"


class TimestampMixin:
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(160), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    default_empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=True,
        index=True,
    )

    memberships = db.relationship(
        "UserEmpresaRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    group_assignments = db.relationship(
        "SecurityUserGroup",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    warehouse_assignments = db.relationship(
        "SecurityWarehouseAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(
            password, method="pbkdf2:sha256", salt_length=16
        )

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        return str(self.id)

    def role_for_empresa(self, empresa_id: int | None) -> str | None:
        # Request-level cache to avoid repeated lookups
        cache = getattr(g, "_role_cache", None)
        if cache is None:
            cache = {}
            g._role_cache = cache
        if empresa_id in cache:
            return cache[empresa_id]

        membership = self.membership_for_empresa(empresa_id)
        role = membership.rol if membership else None
        cache[empresa_id] = role
        return role

    def active_memberships(self) -> list["UserEmpresaRole"]:
        return [
            membership
            for membership in self.memberships
            if membership.is_currently_active()
            and membership.empresa is not None
            and membership.empresa.activa
        ]

    def membership_for_empresa(self, empresa_id: int | None) -> "UserEmpresaRole | None":
        if empresa_id is None:
            return None
        for membership in self.memberships:
            if (
                membership.empresa_id == empresa_id
                and membership.is_currently_active()
                and membership.empresa is not None
                and membership.empresa.activa
            ):
                return membership
        return None

    def empresas_activas(self) -> list["Empresa"]:
        return [membership.empresa for membership in self.active_memberships()]

    def preferred_empresa(self) -> "Empresa | None":
        if self.default_empresa_id:
            membership = self.membership_for_empresa(self.default_empresa_id)
            if membership is not None:
                return membership.empresa
        memberships = self.active_memberships()
        if memberships:
            return memberships[0].empresa
        return None

    def can_access_empresa(self, empresa_id: int | None) -> bool:
        return self.role_for_empresa(empresa_id) is not None

    def groups_for_empresa(self, empresa_id: int | None) -> list["SecurityGroup"]:
        if empresa_id is None:
            return []
        groups: list[SecurityGroup] = []
        for assignment in self.group_assignments:
            group = assignment.group
            if (
                assignment.is_currently_active()
                and group is not None
                and group.activo
                and group.empresa_id == empresa_id
            ):
                groups.append(group)
        return groups

    def warehouse_access_records(
        self, empresa_id: int | None
    ) -> list["SecurityWarehouseAccess"]:
        if empresa_id is None:
            return []
        return [
            assignment
            for assignment in self.warehouse_assignments
            if assignment.empresa_id == empresa_id and assignment.is_currently_active()
        ]

    def allowed_warehouse_ids(self, empresa_id: int | None) -> set[int] | None:
        """Return allowed warehouse IDs for the user.

        Returns:
            ``None``  – no warehouse-level restrictions (admin, or warehouse
                        access control is not enabled for this user)
            ``set()`` – explicitly restricted: user has assignments but none
                        are currently active
            ``{ids}`` – explicit access to listed warehouses
        """
        if empresa_id is None:
            return set()
        if self.role_for_empresa(empresa_id) == ROLE_ADMIN:
            return None
        assignments = self.warehouse_access_records(empresa_id)
        if not assignments:
            return None
        active_ids = {a.almacen_id for a in assignments if a.is_currently_active()}
        return active_ids  # may be empty set if all expired

    def permissions_for_empresa(self, empresa_id: int | None) -> set[str]:
        """Return the set of permission codes the user holds in *empresa_id*."""
        # Request-level cache to avoid repeated DB queries
        cache = getattr(g, "_perm_cache", None)
        if cache is None:
            cache = {}
            g._perm_cache = cache
        if empresa_id in cache:
            return cache[empresa_id]

        permissions = permissions_for_role(self.role_for_empresa(empresa_id))
        for group in self.groups_for_empresa(empresa_id):
            permissions.update(group.permission_codes)
        cache[empresa_id] = permissions
        return permissions

    def has_permission(self, permission_code: str, empresa_id: int | None) -> bool:
        return permission_code in self.permissions_for_empresa(empresa_id)


class Empresa(TimestampMixin, db.Model):
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    ruc = db.Column(db.String(11), unique=True, nullable=False)
    razon_social = db.Column(db.String(255), nullable=False)
    moneda = db.Column(db.String(3), nullable=False, default="PEN")
    regimen_tributario = db.Column(db.String(120), nullable=False, default="General")
    activa = db.Column(db.Boolean, default=True, nullable=False)

    marca = db.relationship(
        "MarcaConfig",
        back_populates="empresa",
        uselist=False,
        cascade="all, delete-orphan",
    )
    user_roles = db.relationship(
        "UserEmpresaRole",
        back_populates="empresa",
        cascade="all, delete-orphan",
    )
    security_groups = db.relationship(
        "SecurityGroup",
        back_populates="empresa",
        cascade="all, delete-orphan",
    )

    @property
    def brand(self) -> "MarcaConfig | DefaultBrand":
        return self.marca or MarcaConfig.defaults()


class UserEmpresaRole(ExpirableMixin, TimestampMixin, db.Model):
    __tablename__ = "user_empresa_roles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    rol = db.Column(db.String(40), nullable=False)

    user = db.relationship("User", back_populates="memberships")
    empresa = db.relationship("Empresa", back_populates="user_roles")

    __table_args__ = (
        db.UniqueConstraint("user_id", "empresa_id", name="uq_user_empresa_role"),
    )

    @property
    def rol_label(self) -> str:
        return ROLE_LABELS.get(self.rol, self.rol.title())


class SecurityGroup(TimestampMixin, db.Model):
    __tablename__ = "security_groups"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    nombre = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    empresa = db.relationship("Empresa", back_populates="security_groups")
    permissions = db.relationship(
        "SecurityGroupPermission",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    assignments = db.relationship(
        "SecurityUserGroup",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "nombre", name="uq_security_group_empresa_nombre"),
    )

    @property
    def permission_codes(self) -> set[str]:
        return {
            item.permission_code
            for item in self.permissions
            if item.permission_code in PERMISSION_LABELS
        }


class SecurityGroupPermission(db.Model):
    __tablename__ = "security_group_permissions"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(
        db.Integer, db.ForeignKey("security_groups.id"), nullable=False, index=True
    )
    permission_code = db.Column(db.String(80), nullable=False)

    group = db.relationship("SecurityGroup", back_populates="permissions")

    __table_args__ = (
        db.UniqueConstraint(
            "group_id",
            "permission_code",
            name="uq_security_group_permission",
        ),
    )


class SecurityUserGroup(ExpirableMixin, TimestampMixin, db.Model):
    __tablename__ = "security_user_groups"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    group_id = db.Column(
        db.Integer, db.ForeignKey("security_groups.id"), nullable=False, index=True
    )

    user = db.relationship("User", back_populates="group_assignments")
    group = db.relationship("SecurityGroup", back_populates="assignments")

    __table_args__ = (
        db.UniqueConstraint("user_id", "group_id", name="uq_security_user_group"),
    )

    @property
    def empresa_id(self) -> int | None:
        return self.group.empresa_id if self.group else None


class SecurityWarehouseAccess(ExpirableMixin, TimestampMixin, db.Model):
    __tablename__ = "security_warehouse_access"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    almacen_id = db.Column(db.Integer, db.ForeignKey("almacenes.id"), nullable=False, index=True)

    user = db.relationship("User", back_populates="warehouse_assignments")

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "empresa_id",
            "almacen_id",
            name="uq_security_warehouse_access",
        ),
    )


class MarcaConfig(TimestampMixin, db.Model):
    __tablename__ = "empresa_marca"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    nombre_sistema = db.Column(db.String(120), nullable=False, default="FacilERP")
    logo_url = db.Column(
        db.String(255),
        nullable=False,
        default="/static/img/defaults/facilerp-logo.svg",
    )
    favicon_url = db.Column(
        db.String(255),
        nullable=False,
        default="/static/img/defaults/facilerp-favicon.svg",
    )
    color_primary = db.Column(db.String(7), nullable=False, default="#2563EB")
    color_secondary = db.Column(db.String(7), nullable=False, default="#1E3A5F")
    updated_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    empresa = db.relationship("Empresa", back_populates="marca")

    @classmethod
    def defaults(cls) -> DefaultBrand:
        return DefaultBrand()

    def reset_defaults(self) -> None:
        defaults = self.defaults()
        self.nombre_sistema = defaults.nombre_sistema
        self.logo_url = defaults.logo_url
        self.favicon_url = defaults.favicon_url
        self.color_primary = defaults.color_primary
        self.color_secondary = defaults.color_secondary


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=True,
        index=True,
    )
    accion = db.Column(db.String(255), nullable=False)
    detalle = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
