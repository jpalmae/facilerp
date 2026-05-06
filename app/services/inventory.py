from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models import Almacen, MovimientoStock, Producto, Stock


TWOPLACES = Decimal("0.01")


class InventoryError(ValueError):
    pass


from app.constants import (
    MOV_ENTRADA,
    MOV_RECEPCION_COMPRA,
    MOV_SALIDA,
    MOV_AJUSTE_SALIDA,
)
from app.utils.tax import as_decimal, calc_totals_with_igv


def get_or_create_stock(producto_id: int, almacen_id: int) -> Stock:
    stock = (
        Stock.query.filter_by(producto_id=producto_id, almacen_id=almacen_id)
        .with_for_update()
        .first()
    )
    if stock:
        return stock

    stock = Stock(producto_id=producto_id, almacen_id=almacen_id)
    db.session.add(stock)
    db.session.flush()
    return stock


def register_stock_movement(
    *,
    empresa_id: int,
    producto: Producto,
    almacen: Almacen,
    tipo: str,
    cantidad,
    costo_unitario=Decimal("0.00"),
    fecha: date | None = None,
    referencia_tipo: str | None = None,
    referencia_id: int | None = None,
):
    qty = as_decimal(cantidad)
    unit_cost = as_decimal(costo_unitario)

    if qty <= Decimal("0.00"):
        raise InventoryError("La cantidad debe ser mayor a cero.")

    if not producto.requiere_stock:
        raise InventoryError("El producto seleccionado no maneja stock.")

    # Lock the product row to prevent concurrent cost-average corruption
    producto = (
        Producto.query.filter_by(id=producto.id)
        .with_for_update()
        .first()
    )
    stock = get_or_create_stock(producto.id, almacen.id)
    current_qty = as_decimal(stock.cantidad_disponible)
    current_avg_cost = as_decimal(producto.costo_promedio)

    if tipo in {MOV_SALIDA, MOV_AJUSTE_SALIDA} and current_qty < qty:
        raise InventoryError("El stock no puede quedar negativo.")

    if tipo in {MOV_ENTRADA, MOV_RECEPCION_COMPRA}:
        new_qty = current_qty + qty
        if new_qty > Decimal("0.00"):
            weighted_cost = ((current_qty * current_avg_cost) + (qty * unit_cost)) / new_qty
            producto.costo_promedio = weighted_cost.quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
        stock.cantidad_disponible = new_qty
    elif tipo in {MOV_SALIDA, MOV_AJUSTE_SALIDA}:
        stock.cantidad_disponible = current_qty - qty
        unit_cost = current_avg_cost
    else:
        raise InventoryError("Tipo de movimiento no soportado.")

    movement = MovimientoStock(
        empresa_id=empresa_id,
        producto_id=producto.id,
        almacen_id=almacen.id,
        tipo=tipo,
        cantidad=qty,
        costo_unitario=unit_cost,
        costo_total=(qty * unit_cost).quantize(TWOPLACES, rounding=ROUND_HALF_UP),
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        fecha=fecha or date.today(),
    )
    db.session.add_all([stock, producto, movement])
    db.session.flush()
    return movement
