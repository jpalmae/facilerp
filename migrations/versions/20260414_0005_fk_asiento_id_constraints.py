"""Add ForeignKey constraints to bare asiento_id columns

Revision ID: 20260414_0005
Revises: 20260324_0004
Create Date: 2026-04-14
"""

from alembic import op

revision = "20260414_0005"
down_revision = "20260324_0004"
branch_labels = None
depends_on = None

# Tables and columns that need FK added to asientos.id
_FK_SPECS = [
    ("movimientos_stock", "asiento_id"),
    ("cobros", "asiento_id"),
    ("documentos_cxp", "asiento_id"),
    ("pagos", "asiento_id"),
    ("movimientos_tesoreria", "asiento_id"),
]


def upgrade() -> None:
    for table, column in _FK_SPECS:
        op.create_foreign_key(
            f"fk_{table}_{column}_asientos",
            table,
            "asientos",
            [column],
            ["id"],
        )


def downgrade() -> None:
    for table, column in _FK_SPECS:
        op.drop_constraint(
            f"fk_{table}_{column}_asientos",
            table,
            type_="foreignkey",
        )
