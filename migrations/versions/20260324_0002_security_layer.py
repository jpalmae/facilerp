"""Security layer

Revision ID: 20260324_0002
Revises: 20260323_0001
Create Date: 2026-03-24 00:10:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260324_0002"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("security_groups"):
        op.create_table(
            "security_groups",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("empresa_id", sa.Integer(), nullable=False),
            sa.Column("nombre", sa.String(length=120), nullable=False),
            sa.Column("descripcion", sa.String(length=255), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "empresa_id",
                "nombre",
                name="uq_security_group_empresa_nombre",
            ),
        )
        op.create_index(
            op.f("ix_security_groups_empresa_id"),
            "security_groups",
            ["empresa_id"],
            unique=False,
        )

    if not inspector.has_table("security_group_permissions"):
        op.create_table(
            "security_group_permissions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("permission_code", sa.String(length=80), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["security_groups.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "group_id",
                "permission_code",
                name="uq_security_group_permission",
            ),
        )
        op.create_index(
            op.f("ix_security_group_permissions_group_id"),
            "security_group_permissions",
            ["group_id"],
            unique=False,
        )

    if not inspector.has_table("security_user_groups"):
        op.create_table(
            "security_user_groups",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["group_id"], ["security_groups.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "group_id", name="uq_security_user_group"),
        )
        op.create_index(
            op.f("ix_security_user_groups_group_id"),
            "security_user_groups",
            ["group_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_security_user_groups_user_id"),
            "security_user_groups",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("security_user_groups"):
        op.drop_index(op.f("ix_security_user_groups_user_id"), table_name="security_user_groups")
        op.drop_index(op.f("ix_security_user_groups_group_id"), table_name="security_user_groups")
        op.drop_table("security_user_groups")

    if inspector.has_table("security_group_permissions"):
        op.drop_index(
            op.f("ix_security_group_permissions_group_id"),
            table_name="security_group_permissions",
        )
        op.drop_table("security_group_permissions")

    if inspector.has_table("security_groups"):
        op.drop_index(op.f("ix_security_groups_empresa_id"), table_name="security_groups")
        op.drop_table("security_groups")
