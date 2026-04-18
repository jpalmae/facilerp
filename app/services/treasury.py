from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from io import StringIO

from app.extensions import db
from app.models import CuentaTesoreria, DocumentoCxP, MovimientoTesoreria, Pago, TipoCambio
from app.services.external import fetch_exchange_rate
from app.services.accounting import create_journal_entry, get_account
from app.services.inventory import as_decimal


class TreasuryError(ValueError):
    pass


def create_treasury_account(
    *,
    empresa_id: int,
    tipo: str,
    nombre: str,
    banco: str | None,
    numero_cuenta: str | None,
    moneda: str,
    cuenta_contable_codigo: str,
) -> CuentaTesoreria:
    account = get_account(empresa_id, cuenta_contable_codigo)
    treasury = CuentaTesoreria(
        empresa_id=empresa_id,
        tipo=tipo,
        nombre=nombre,
        banco=banco,
        numero_cuenta=numero_cuenta,
        moneda=moneda,
        cuenta_contable_id=account.id,
    )
    db.session.add(treasury)
    db.session.flush()
    return treasury


def register_treasury_movement(
    *,
    empresa_id: int,
    treasury_account: CuentaTesoreria,
    tipo: str,
    monto,
    fecha: date,
    glosa: str,
    contra_cuenta_codigo: str,
    referencia_tipo: str | None = None,
    referencia_id: int | None = None,
    created_by: str | None = None,
) -> MovimientoTesoreria:
    amount = as_decimal(monto)
    if amount <= Decimal("0.00"):
        raise TreasuryError("El monto debe ser mayor a cero.")

    contra = get_account(empresa_id, contra_cuenta_codigo)
    treasury_ledger = treasury_account.cuenta_contable

    if tipo == "ingreso":
        lines = [
            {"cuenta": treasury_ledger, "debe": amount},
            {"cuenta": contra, "haber": amount},
        ]
        treasury_account.saldo_actual = as_decimal(treasury_account.saldo_actual) + amount
    elif tipo == "egreso":
        if as_decimal(treasury_account.saldo_actual) < amount:
            raise TreasuryError("La cuenta de tesorería no tiene saldo suficiente.")
        lines = [
            {"cuenta": contra, "debe": amount},
            {"cuenta": treasury_ledger, "haber": amount},
        ]
        treasury_account.saldo_actual = as_decimal(treasury_account.saldo_actual) - amount
    else:
        raise TreasuryError("Tipo de movimiento de tesorería no soportado.")

    entry = create_journal_entry(
        empresa_id=empresa_id,
        fecha=fecha,
        glosa=glosa,
        tipo="automatico",
        lines=lines,
        created_by=created_by,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
    )
    movement = MovimientoTesoreria(
        empresa_id=empresa_id,
        cuenta_id=treasury_account.id,
        tipo=tipo,
        monto=amount,
        fecha=fecha,
        glosa=glosa,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        asiento_id=entry.id,
    )
    db.session.add_all([treasury_account, movement])
    db.session.flush()
    return movement


def register_supplier_payment(
    *,
    empresa_id: int,
    documento: DocumentoCxP,
    treasury_account: CuentaTesoreria,
    monto,
    fecha: date,
    tipo_pago: str,
    created_by: str | None = None,
) -> Pago:
    amount = as_decimal(monto)
    pending = as_decimal(documento.monto_pendiente)
    if amount <= Decimal("0.00"):
        raise TreasuryError("El pago debe ser mayor a cero.")
    if amount > pending:
        raise TreasuryError("El pago excede el saldo pendiente.")

    movement = register_treasury_movement(
        empresa_id=empresa_id,
        treasury_account=treasury_account,
        tipo="egreso",
        monto=amount,
        fecha=fecha,
        glosa=f"Pago proveedor {documento.proveedor.razon_social}",
        contra_cuenta_codigo="4212",
        referencia_tipo="documento_cxp",
        referencia_id=documento.id,
        created_by=created_by,
    )

    documento.monto_pendiente = pending - amount
    documento.estado = "pagado" if documento.monto_pendiente == Decimal("0.00") else "parcial"
    pago = Pago(
        empresa_id=empresa_id,
        documento_cxp_id=documento.id,
        monto=amount,
        fecha=fecha,
        tipo_pago=tipo_pago,
        cuenta_tesoreria_id=treasury_account.id,
        asiento_id=movement.asiento_id,
    )
    db.session.add_all([documento, pago])
    db.session.flush()
    return pago


def transfer_between_accounts(
    *,
    empresa_id: int,
    source: CuentaTesoreria,
    destination: CuentaTesoreria,
    monto,
    fecha: date,
    created_by: str | None = None,
):
    if source.id == destination.id:
        raise TreasuryError("La transferencia requiere cuentas distintas.")
    amount = as_decimal(monto)
    if amount <= Decimal("0.00"):
        raise TreasuryError("La transferencia debe ser mayor a cero.")
    if as_decimal(source.saldo_actual) < amount:
        raise TreasuryError("La cuenta origen no tiene saldo suficiente.")

    source.saldo_actual = as_decimal(source.saldo_actual) - amount
    destination.saldo_actual = as_decimal(destination.saldo_actual) + amount

    entry = create_journal_entry(
        empresa_id=empresa_id,
        fecha=fecha,
        glosa=f"Transferencia {source.nombre} -> {destination.nombre}",
        tipo="automatico",
        created_by=created_by,
        referencia_tipo="transferencia_tesoreria",
        lines=[
            {"cuenta": destination.cuenta_contable, "debe": amount},
            {"cuenta": source.cuenta_contable, "haber": amount},
        ],
    )
    out_movement = MovimientoTesoreria(
        empresa_id=empresa_id,
        cuenta_id=source.id,
        tipo="transferencia_salida",
        monto=amount,
        fecha=fecha,
        glosa=f"Transferencia a {destination.nombre}",
        referencia_tipo="transferencia_tesoreria",
        referencia_id=entry.id,
        asiento_id=entry.id,
        conciliado=True,
    )
    in_movement = MovimientoTesoreria(
        empresa_id=empresa_id,
        cuenta_id=destination.id,
        tipo="transferencia_ingreso",
        monto=amount,
        fecha=fecha,
        glosa=f"Transferencia desde {source.nombre}",
        referencia_tipo="transferencia_tesoreria",
        referencia_id=entry.id,
        asiento_id=entry.id,
        conciliado=True,
    )
    db.session.add_all([source, destination, out_movement, in_movement])
    db.session.flush()
    return entry


def reconcile_movements_from_csv(
    *,
    empresa_id: int,
    treasury_account: CuentaTesoreria,
    csv_content: str,
) -> int:
    if not csv_content.strip():
        raise TreasuryError("El archivo CSV está vacío.")
    matched = 0
    reader = csv.DictReader(StringIO(csv_content))
    for row in reader:
        raw_amount = row.get("monto") or row.get("amount")
        raw_date = row.get("fecha") or row.get("date")
        if not raw_amount or not raw_date:
            continue
        amount = as_decimal(raw_amount.replace(",", "."))
        movement = (
            MovimientoTesoreria.query.filter_by(
                empresa_id=empresa_id,
                cuenta_id=treasury_account.id,
                conciliado=False,
            )
            .filter(MovimientoTesoreria.monto == amount, MovimientoTesoreria.fecha == date.fromisoformat(raw_date))
            .first()
        )
        if movement:
            movement.conciliado = True
            db.session.add(movement)
            matched += 1
    db.session.flush()
    return matched


def upsert_exchange_rate(empresa_id: int, target_date: date, moneda: str = "USD") -> TipoCambio:
    value = fetch_exchange_rate(target_date)
    if value is None:
        raise TreasuryError("No se pudo obtener tipo de cambio desde BCRP.")

    rate = TipoCambio.query.filter_by(
        empresa_id=empresa_id, moneda=moneda, fecha=target_date
    ).first()
    if not rate:
        rate = TipoCambio(empresa_id=empresa_id, moneda=moneda, fecha=target_date)
    rate.compra = value
    rate.venta = value
    rate.fuente = "bcrp"
    db.session.add(rate)
    db.session.flush()
    return rate
