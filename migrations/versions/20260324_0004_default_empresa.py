"""User default company

Revision ID: 20260324_0004
Revises: 20260324_0003
Create Date: 2026-03-24 19:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260324_0004"
down_revision = "20260324_0003"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        return

    columns = _column_names(inspector, "users")
    if "default_empresa_id" not in columns:
        op.add_column("users", sa.Column("default_empresa_id", sa.Integer(), nullable=True))

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "users")
    if op.f("ix_users_default_empresa_id") not in indexes:
        op.create_index(
            op.f("ix_users_default_empresa_id"),
            "users",
            ["default_empresa_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    foreign_keys = _foreign_key_names(inspector, "users")
    if "fk_users_default_empresa_id_empresas" not in foreign_keys:
        op.create_foreign_key(
            "fk_users_default_empresa_id_empresas",
            "users",
            "empresas",
            ["default_empresa_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        return

    foreign_keys = _foreign_key_names(inspector, "users")
    if "fk_users_default_empresa_id_empresas" in foreign_keys:
        op.drop_constraint(
            "fk_users_default_empresa_id_empresas",
            "users",
            type_="foreignkey",
        )

    indexes = _index_names(inspector, "users")
    if op.f("ix_users_default_empresa_id") in indexes:
        op.drop_index(op.f("ix_users_default_empresa_id"), table_name="users")

    columns = _column_names(inspector, "users")
    if "default_empresa_id" in columns:
        op.drop_column("users", "default_empresa_id")
