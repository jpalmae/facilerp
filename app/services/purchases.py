from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import (
    Almacen,
    DocumentoCxP,
    OrdenCompra,
    OrdenCompraLinea,
    Producto,
    Recepcion,
    RecepcionLinea,
)
from app.services.accounting import create_journal_entry
from app.services.inventory import InventoryError, as_decimal, register_stock_movement
from app.utils.tax import calc_totals_with_igv


class PurchaseError(ValueError):
    pass


def build_purchase_totals(cantidad, precio_unitario, descuento_pct=Decimal("0.00")):
    return calc_totals_with_igv(cantidad, precio_unitario, descuento_pct)


def create_purchase_order(
    *,
    empresa_id: int,
    proveedor_id: int,
    producto: Producto,
    cantidad,
    precio_unitario,
    fecha: date,
    observaciones: str | None = None,
) -> OrdenCompra:
    if not producto.requiere_stock:
        raise PurchaseError("Las órdenes de compra requieren un producto con stock.")

    subtotal, igv, total = build_purchase_totals(cantidad, precio_unitario)
    orden = OrdenCompra(
        empresa_id=empresa_id,
        proveedor_id=proveedor_id,
        fecha=fecha,
        estado="emitida",
        subtotal=subtotal,
        igv=igv,
        total=total,
        observaciones=observaciones,
    )
    db.session.add(orden)
    db.session.flush()

    linea = OrdenCompraLinea(
        oc_id=orden.id,
        producto_id=producto.id,
        cantidad=as_decimal(cantidad),
        precio_unitario=as_decimal(precio_unitario),
        subtotal=subtotal,
        igv_linea=igv,
    )
    db.session.add(linea)
    db.session.flush()
    return orden


def receive_purchase_order(
    *,
    orden: OrdenCompra,
    almacen: Almacen,
    cantidad_recibida=None,
    fecha: date | None = None,
    lineas_recibidas: list[dict] | None = None,
):
    """Receive items against a purchase order.

    Supports two calling conventions:

    * **Single-line (backward compatible):** pass ``cantidad_recibida`` to
      receive the first (or only) line of the order.
    * **Multi-line:** pass ``lineas_recibidas``, a list of dicts
      ``[{"linea_id": int, "cantidad_recibida": Decimal}, ...]``.
    """
    if not orden.lineas:
        raise PurchaseError("La orden no tiene líneas registradas.")

    fecha = fecha or date.today()

    # ── Normalise into a uniform list ────────────────────────────────
    if lineas_recibidas:
        items = []
        for rec in lineas_recibidas:
            linea = next(
                (l for l in orden.lineas if l.id == rec["linea_id"]), None
            )
            if linea is None:
                raise PurchaseError(
                    f"Línea {rec['linea_id']} no pertenece a la orden."
                )
            items.append((linea, as_decimal(rec["cantidad_recibida"])))
    elif cantidad_recibida is not None:
        items = [(orden.lineas[0], as_decimal(cantidad_recibida))]
    else:
        raise PurchaseError(
            "Indique cantidad_recibida o lineas_recibidas."
        )

    # ── Validate all quantities first ────────────────────────────────
    for linea, qty in items:
        if qty <= Decimal("0.00"):
            raise PurchaseError("La recepción debe ser mayor a cero.")
        if qty > as_decimal(linea.pendiente):
            raise PurchaseError(
                f"La cantidad recibida ({qty}) excede lo pendiente "
                f"({linea.pendiente}) en la línea del producto "
                f"{linea.producto_id}."
            )

    # ── Create the reception header ──────────────────────────────────
    recepcion = Recepcion(
        empresa_id=orden.empresa_id,
        oc_id=orden.id,
        fecha=fecha,
        almacen_id=almacen.id,
        estado="recibida",
    )
    db.session.add(recepcion)
    db.session.flush()

    # ── Process each line ────────────────────────────────────────────
    total_subtotal = Decimal("0.00")
    total_igv = Decimal("0.00")

    for linea, qty in items:
        recepcion_linea = RecepcionLinea(
            recepcion_id=recepcion.id,
            oc_linea_id=linea.id,
            producto_id=linea.producto_id,
            cantidad_recibida=qty,
        )
        db.session.add(recepcion_linea)

        linea.cantidad_recibida = as_decimal(linea.cantidad_recibida) + qty

        ratio = qty / as_decimal(linea.cantidad)
        line_sub = (as_decimal(linea.subtotal) * ratio).quantize(Decimal("0.01"))
        line_igv = (as_decimal(linea.igv_linea) * ratio).quantize(Decimal("0.01"))

        total_subtotal += line_sub
        total_igv += line_igv

        try:
            register_stock_movement(
                empresa_id=orden.empresa_id,
                producto=linea.producto,
                almacen=almacen,
                tipo="recepcion_compra",
                cantidad=qty,
                costo_unitario=linea.precio_unitario,
                fecha=fecha,
                referencia_tipo="orden_compra",
                referencia_id=orden.id,
            )
        except InventoryError as exc:
            raise PurchaseError(str(exc)) from exc

    total = total_subtotal + total_igv

    # ── Determine order status ───────────────────────────────────────
    all_received = all(
        as_decimal(l.pendiente) == Decimal("0.00") for l in orden.lineas
    )
    orden.estado = "recibida" if all_received else "parcial"

    # ── Accounting entry & CxP document ──────────────────────────────
    entry = create_journal_entry(
        empresa_id=orden.empresa_id,
        fecha=fecha,
        glosa=f"Recepción OC-{orden.id:04d} {orden.proveedor.razon_social}",
        tipo="automatico",
        referencia_tipo="recepcion_compra",
        referencia_id=recepcion.id,
        lines=[
            {"cuenta": "2011", "debe": total_subtotal},
            {"cuenta": "40111", "debe": total_igv},
            {"cuenta": "4212", "haber": total},
        ],
    )
    documento_cxp = DocumentoCxP(
        empresa_id=orden.empresa_id,
        proveedor_id=orden.proveedor_id,
        recepcion_id=recepcion.id,
        monto_original=total,
        monto_pendiente=total,
        fecha_emision=fecha,
        fecha_vencimiento=fecha,
        estado="pendiente",
        asiento_id=entry.id,
    )

    db.session.add_all([orden, recepcion, documento_cxp])
    db.session.flush()
    return recepcion
