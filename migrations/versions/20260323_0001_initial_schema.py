"""Initial schema

Revision ID: 20260323_0001
Revises: None
Create Date: 2026-03-23 22:30:00
"""

from __future__ import annotations

import os

from alembic import op

from app import create_app
from app.extensions import db

os.environ["CREATE_DB_ON_START"] = "false"

revision = "20260323_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    app = create_app("production")
    with app.app_context():
        bind = op.get_bind()
        db.metadata.create_all(bind=bind)


def downgrade() -> None:
    app = create_app("production")
    with app.app_context():
        bind = op.get_bind()
        db.metadata.drop_all(bind=bind)
