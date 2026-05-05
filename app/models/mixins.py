"""Reusable SQLAlchemy mixins for the FacilERP models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from flask import g

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns.

    Uses Flask-SQLAlchemy ``db.Column`` so it integrates cleanly with
    the rest of the codebase and keeps behaviour consistent (Python-side
    defaults with timezone-aware datetimes).
    """

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ExpirableMixin:
    """Shared logic for models with ``activo`` + ``expires_at`` fields.

    Provides ``is_currently_active()`` used by ``SecurityMembership``,
    ``SecurityGroupMembership`` and ``SecurityWarehouseAccess``.
    """

    activo = sa.Column(sa.Boolean, default=True, nullable=False)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True, default=None)

    def is_currently_active(self, at: Optional[datetime] = None) -> bool:
        """Check whether the record is active and not expired.

        Parameters
        ----------
        at:
            Reference timestamp. Defaults to ``datetime.now(timezone.utc)``.
        """
        if not self.activo:
            return False
        if self.expires_at is None:
            return True
        reference = at or datetime.now(timezone.utc)
        expiration = self.expires_at
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return expiration >= reference
