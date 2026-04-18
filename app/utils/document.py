"""Document status helpers — unified from cxc_cxp and ventas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


def document_status(documento) -> str:
    """Return a human-readable status label for a CxC/CxP document.

    Parameters
    ----------
    documento:
        Any object with ``monto_pendiente``, ``estado`` and
        ``fecha_vencimiento`` attributes.
    """
    pending = Decimal(str(documento.monto_pendiente or 0))
    if pending <= Decimal("0.00") or (documento.estado or "").lower() == "pagado":
        return "Pagada"
    if documento.fecha_vencimiento < date.today():
        return "Vencida"
    if (documento.estado or "").lower() == "parcial":
        return "Parcial"
    return "Pendiente"
