"""add composite index on movimientos_stock

Revision ID: 20260501_0006
Revises: 20260414_0005
Create Date: 2025-05-01
"""

from alembic import op

revision = "20260501_0006"
down_revision = "20260414_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_movimientos_empresa_referencia",
        "movimientos_stock",
        ["empresa_id", "referencia_tipo", "referencia_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_movimientos_empresa_referencia", table_name="movimientos_stock")
