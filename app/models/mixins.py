"""Reusable SQLAlchemy mixins for the FacilERP models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

import sqlalchemy as sa


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
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
