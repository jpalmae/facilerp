"""Tax and totals calculation — extracted from purchases/sales."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")


def as_decimal(value) -> Decimal:
    """Convert *value* to a ``Decimal`` quantized to 2 decimal places."""
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calc_totals_with_igv(
    cantidad,
    precio_unitario,
    descuento_pct: Decimal = Decimal("0.00"),
    igv_rate: Decimal = Decimal("0.18"),
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate subtotal, IGV and total for a line item.

    Returns ``(subtotal, igv, total)`` — all quantized to 2 decimal places.

    Parameters
    ----------
    cantidad:
        Quantity (will be converted to Decimal).
    precio_unitario:
        Unit price (will be converted to Decimal).
    descuento_pct:
        Discount percentage (0–100). Defaults to 0.
    igv_rate:
        IGV rate as a decimal fraction (e.g. 0.18 for 18%). Defaults to 0.18.
    """
    qty = as_decimal(cantidad)
    unit_price = as_decimal(precio_unitario)
    discount = as_decimal(descuento_pct)

    gross = qty * unit_price
    discounted = gross * (Decimal("1.00") - (discount / Decimal("100.00")))
    subtotal = discounted.quantize(TWOPLACES)
    igv = (subtotal * igv_rate).quantize(TWOPLACES)
    total = subtotal + igv
    return subtotal, igv, total
