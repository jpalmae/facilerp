from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    Almacen,
    Cliente,
    Cobro,
    CuentaTesoreria,
    DocumentoCxC,
    PedidoVenta,
    PedidoVentaLinea,
    Producto,
)
from app.services.accounting import create_journal_entry
from app.services.inventory import InventoryError, as_decimal, register_stock_movement
from app.services.purchases import build_purchase_totals
from app.services.treasury import register_treasury_movement


class SalesError(ValueError):
    pass


def create_sales_order(
    *,
    empresa_id: int,
    cliente: Cliente,
    producto: Producto,
    almacen: Almacen,
    cantidad,
    precio_unitario,
    fecha: date,
    observaciones: str | None = None,
) -> PedidoVenta:
    if not producto.requiere_stock:
        raise SalesError("La venta requiere un producto con stock.")

    subtotal, igv, total = build_purchase_totals(cantidad, precio_unitario)
    cost_amount = as_decimal(producto.costo_promedio) * as_decimal(cantidad)

    pedido = PedidoVenta(
        empresa_id=empresa_id,
        cliente_id=cliente.id,
        almacen_id=almacen.id,
        fecha=fecha,
        subtotal=subtotal,
        igv=igv,
        total=total,
        observaciones=observaciones,
    )
    db.session.add(pedido)
    db.session.flush()

    linea = PedidoVentaLinea(
        pedido_id=pedido.id,
        producto_id=producto.id,
        cantidad=as_decimal(cantidad),
        precio_unitario=as_decimal(precio_unitario),
        subtotal=subtotal,
        igv_linea=igv,
    )
    db.session.add(linea)

    try:
        register_stock_movement(
            empresa_id=empresa_id,
            producto=producto,
            almacen=almacen,
            tipo="salida",
            cantidad=cantidad,
            referencia_tipo="pedido_venta",
            referencia_id=pedido.id,
            fecha=fecha,
        )
    except InventoryError as exc:
        raise SalesError(str(exc)) from exc

    accounting_entry = create_journal_entry(
        empresa_id=empresa_id,
        fecha=fecha,
        glosa=f"Venta PV-{pedido.id:04d} {cliente.razon_social}",
        tipo="automatico",
        referencia_tipo="pedido_venta",
        referencia_id=pedido.id,
        lines=[
            {"cuenta": "1212", "debe": total},
            {"cuenta": "7011", "haber": subtotal},
            {"cuenta": "40111", "haber": igv},
            {"cuenta": "6911", "debe": cost_amount},
            {"cuenta": "2011", "haber": cost_amount},
        ],
    )
    documento = DocumentoCxC(
        empresa_id=empresa_id,
        cliente_id=cliente.id,
        pedido_id=pedido.id,
        monto_original=total,
        monto_pendiente=total,
        fecha_emision=fecha,
        fecha_vencimiento=fecha + timedelta(days=30),
        estado="pendiente",
    )
    db.session.add(documento)
    db.session.flush()
    _ = accounting_entry
    return pedido


def register_collection(
    *,
    empresa_id: int,
    documento: DocumentoCxC,
    treasury_account: CuentaTesoreria,
    monto,
    fecha: date,
    tipo_pago: str,
) -> Cobro:
    amount = as_decimal(monto)
    pending = as_decimal(documento.monto_pendiente)
    if amount <= Decimal("0.00"):
        raise SalesError("El cobro debe ser mayor a cero.")
    if amount > pending:
        raise SalesError("El cobro excede el saldo pendiente.")

    movement = register_treasury_movement(
        empresa_id=empresa_id,
        treasury_account=treasury_account,
        tipo="ingreso",
        monto=amount,
        fecha=fecha,
        glosa=f"Cobro cliente {documento.cliente.razon_social}",
        contra_cuenta_codigo="1212",
        referencia_tipo="documento_cxc",
        referencia_id=documento.id,
    )
    documento.monto_pendiente = pending - amount
    documento.estado = "pagado" if documento.monto_pendiente == Decimal("0.00") else "parcial"

    cobro = Cobro(
        empresa_id=empresa_id,
        documento_cxc_id=documento.id,
        monto=amount,
        fecha=fecha,
        tipo_pago=tipo_pago,
        asiento_id=movement.asiento_id,
    )
    db.session.add_all([documento, cobro])
    db.session.flush()
    return cobro
