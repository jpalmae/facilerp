"""Security scope and expiration

Revision ID: 20260324_0003
Revises: 20260324_0002
Create Date: 2026-03-24 01:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260324_0003"
down_revision = "20260324_0002"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("user_empresa_roles"):
        columns = _column_names(inspector, "user_empresa_roles")
        if "expires_at" not in columns:
            op.add_column(
                "user_empresa_roles",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )

    if inspector.has_table("security_user_groups"):
        columns = _column_names(inspector, "security_user_groups")
        if "expires_at" not in columns:
            op.add_column(
                "security_user_groups",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )

    if inspector.has_table("audit_log"):
        columns = _column_names(inspector, "audit_log")
        if "detalle" not in columns:
            op.add_column("audit_log", sa.Column("detalle", sa.Text(), nullable=True))

    if not inspector.has_table("security_warehouse_access"):
        op.create_table(
            "security_warehouse_access",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("empresa_id", sa.Integer(), nullable=False),
            sa.Column("almacen_id", sa.Integer(), nullable=False),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"]),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "empresa_id",
                "almacen_id",
                name="uq_security_warehouse_access",
            ),
        )
        op.create_index(
            op.f("ix_security_warehouse_access_almacen_id"),
            "security_warehouse_access",
            ["almacen_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_security_warehouse_access_empresa_id"),
            "security_warehouse_access",
            ["empresa_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_security_warehouse_access_user_id"),
            "security_warehouse_access",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("security_warehouse_access"):
        indexes = _index_names(inspector, "security_warehouse_access")
        if op.f("ix_security_warehouse_access_user_id") in indexes:
            op.drop_index(
                op.f("ix_security_warehouse_access_user_id"),
                table_name="security_warehouse_access",
            )
        if op.f("ix_security_warehouse_access_empresa_id") in indexes:
            op.drop_index(
                op.f("ix_security_warehouse_access_empresa_id"),
                table_name="security_warehouse_access",
            )
        if op.f("ix_security_warehouse_access_almacen_id") in indexes:
            op.drop_index(
                op.f("ix_security_warehouse_access_almacen_id"),
                table_name="security_warehouse_access",
            )
        op.drop_table("security_warehouse_access")

    if inspector.has_table("audit_log"):
        columns = _column_names(inspector, "audit_log")
        if "detalle" in columns:
            op.drop_column("audit_log", "detalle")

    if inspector.has_table("security_user_groups"):
        columns = _column_names(inspector, "security_user_groups")
        if "expires_at" in columns:
            op.drop_column("security_user_groups", "expires_at")

    if inspector.has_table("user_empresa_roles"):
        columns = _column_names(inspector, "user_empresa_roles")
        if "expires_at" in columns:
            op.drop_column("user_empresa_roles", "expires_at")
