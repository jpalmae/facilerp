from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models import Asiento, AsientoLinea, PeriodoContable, PlanCuenta
from app.services.inventory import as_decimal


ACCOUNT_CATALOG = {
    "1011": ("Caja", "activo"),
    "1041": ("Cuentas corrientes operativas", "activo"),
    "1212": ("Facturas por cobrar emitidas", "activo"),
    "2011": ("Mercaderías manufacturadas", "activo"),
    "40111": ("IGV - Cuenta propia", "pasivo"),
    "4212": ("Facturas por pagar emitidas", "pasivo"),
    "7011": ("Venta de mercaderías", "ingreso"),
    "6911": ("Costo de ventas", "gasto"),
    "6599": ("Gastos diversos de gestión", "gasto"),
    "7599": ("Ingresos diversos de gestión", "ingreso"),
}


class AccountingError(ValueError):
    pass


def ensure_accounting_setup(empresa_id: int) -> None:
    if PlanCuenta.query.filter_by(empresa_id=empresa_id).first():
        return

    for code, (name, kind) in ACCOUNT_CATALOG.items():
        db.session.add(
            PlanCuenta(
                empresa_id=empresa_id,
                codigo=code,
                nombre=name,
                tipo=kind,
                nivel=len(code),
                permite_movimiento=True,
            )
        )
    db.session.flush()


def get_account(empresa_id: int, codigo: str) -> PlanCuenta:
    account = PlanCuenta.query.filter_by(empresa_id=empresa_id, codigo=codigo).first()
    if not account:
        raise AccountingError(f"No existe la cuenta contable {codigo}.")
    return account


def get_or_create_period(empresa_id: int, fecha: date) -> PeriodoContable:
    period = PeriodoContable.query.filter_by(
        empresa_id=empresa_id, anio=fecha.year, mes=fecha.month
    ).first()
    if period:
        if period.estado != "abierto":
            raise AccountingError("El período contable está cerrado.")
        return period

    period = PeriodoContable(
        empresa_id=empresa_id,
        anio=fecha.year,
        mes=fecha.month,
        estado="abierto",
    )
    db.session.add(period)
    db.session.flush()
    return period


def create_journal_entry(
    *,
    empresa_id: int,
    fecha: date,
    glosa: str,
    tipo: str,
    lines: list[dict],
    created_by: str | None = None,
    referencia_tipo: str | None = None,
    referencia_id: int | None = None,
) -> Asiento:
    ensure_accounting_setup(empresa_id)
    period = get_or_create_period(empresa_id, fecha)
    total_debe = sum(as_decimal(line.get("debe", 0)) for line in lines)
    total_haber = sum(as_decimal(line.get("haber", 0)) for line in lines)
    if total_debe <= Decimal("0.00") or total_haber <= Decimal("0.00"):
        raise AccountingError("El asiento debe tener importes mayores a cero.")
    if total_debe != total_haber:
        raise AccountingError("El asiento no cuadra: debe y haber son distintos.")

    last_number = (
        db.session.query(func.max(Asiento.numero))
        .filter_by(empresa_id=empresa_id, periodo_id=period.id)
        .with_for_update()
        .scalar()
        or 0
    )

    asiento = Asiento(
        empresa_id=empresa_id,
        periodo_id=period.id,
        numero=last_number + 1,
        fecha=fecha,
        glosa=glosa,
        tipo=tipo,
        estado="registrado",
        created_by=created_by,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
    )
    db.session.add(asiento)
    db.session.flush()

    for line in lines:
        account = line.get("cuenta")
        if isinstance(account, str):
            account = get_account(empresa_id, account)
        db.session.add(
            AsientoLinea(
                asiento_id=asiento.id,
                cuenta_id=account.id,
                debe=as_decimal(line.get("debe", 0)),
                haber=as_decimal(line.get("haber", 0)),
                referencia=line.get("referencia"),
            )
        )
    db.session.flush()
    return asiento


def trial_balance(empresa_id: int) -> list[dict]:
    # Single aggregated query — avoids N+1 per account
    totals_q = (
        db.session.query(
            PlanCuenta.id.label("cuenta_id"),
            PlanCuenta.codigo,
            PlanCuenta.nombre,
            PlanCuenta.tipo,
            func.coalesce(func.sum(AsientoLinea.debe), 0).label("total_debe"),
            func.coalesce(func.sum(AsientoLinea.haber), 0).label("total_haber"),
        )
        .outerjoin(AsientoLinea, AsientoLinea.cuenta_id == PlanCuenta.id)
        .outerjoin(Asiento, Asiento.id == AsientoLinea.asiento_id)
        .filter(PlanCuenta.empresa_id == empresa_id)
        .group_by(PlanCuenta.id)
        .order_by(PlanCuenta.codigo)
        .all()
    )
    rows = []
    for row in totals_q:
        debe = as_decimal(row.total_debe)
        haber = as_decimal(row.total_haber)
        if debe == Decimal("0.00") and haber == Decimal("0.00"):
            continue
        rows.append(
            {
                "codigo": row.codigo,
                "nombre": row.nombre,
                "tipo": row.tipo,
                "debe": debe,
                "haber": haber,
                "saldo": debe - haber,
            }
        )
    return rows


def statement_snapshot(empresa_id: int) -> dict:
    rows = trial_balance(empresa_id)
    balance = defaultdict(Decimal)
    income = defaultdict(Decimal)
    for row in rows:
        saldo = row["saldo"]
        if row["tipo"] in {"activo", "pasivo"}:
            balance[row["tipo"]] += saldo
        elif row["tipo"] == "ingreso":
            income["ingresos"] += -saldo
        elif row["tipo"] == "gasto":
            income["gastos"] += saldo
    return {
        "balance": {
            "activo": balance["activo"],
            "pasivo": -balance["pasivo"],
            "patrimonio": balance["activo"] + balance["pasivo"],
        },
        "resultados": {
            "ingresos": income["ingresos"],
            "gastos": income["gastos"],
            "utilidad": income["ingresos"] - income["gastos"],
        },
    }


def account_ledger(empresa_id: int, cuenta_id: int) -> list[dict]:
    account = db.session.get(PlanCuenta, cuenta_id)
    if not account or account.empresa_id != empresa_id:
        raise AccountingError("Cuenta contable no encontrada.")
    rows = (
        db.session.query(Asiento, AsientoLinea)
        .join(AsientoLinea, Asiento.id == AsientoLinea.asiento_id)
        .filter(Asiento.empresa_id == empresa_id, AsientoLinea.cuenta_id == cuenta_id)
        .order_by(Asiento.fecha.asc(), Asiento.id.asc())
        .all()
    )
    saldo = Decimal("0.00")
    ledger = []
    for asiento, line in rows:
        saldo += as_decimal(line.debe) - as_decimal(line.haber)
        ledger.append(
            {
                "fecha": asiento.fecha,
                "asiento_numero": asiento.numero,
                "glosa": asiento.glosa,
                "debe": as_decimal(line.debe),
                "haber": as_decimal(line.haber),
                "saldo": saldo,
            }
        )
    return ledger


def list_periods(empresa_id: int) -> list[PeriodoContable]:
    return (
        PeriodoContable.query.filter_by(empresa_id=empresa_id)
        .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
        .all()
    )


def close_period(empresa_id: int, period_id: int) -> PeriodoContable:
    period = db.session.get(PeriodoContable, period_id)
    if not period or period.empresa_id != empresa_id:
        raise AccountingError("Período no encontrado.")
    if period.estado == "cerrado":
        raise AccountingError("El período ya está cerrado.")

    totals = (
        db.session.query(
            func.coalesce(func.sum(AsientoLinea.debe), 0),
            func.coalesce(func.sum(AsientoLinea.haber), 0),
        )
        .join(Asiento, Asiento.id == AsientoLinea.asiento_id)
        .filter(Asiento.empresa_id == empresa_id, Asiento.periodo_id == period.id)
        .first()
    )
    if as_decimal(totals[0]) != as_decimal(totals[1]):
        raise AccountingError("El período no puede cerrarse porque el balance no cuadra.")

    period.estado = "cerrado"
    period.fecha_cierre = date.today()
    db.session.add(period)
    db.session.flush()
    return period


def reverse_entry(
    empresa_id: int,
    asiento_id: int,
    fecha: date,
    created_by: str | None = None,
) -> Asiento:
    entry = db.session.get(Asiento, asiento_id)
    if not entry or entry.empresa_id != empresa_id:
        raise AccountingError("Asiento no encontrado.")
    if entry.estado == "revertido":
        raise AccountingError("El asiento ya fue revertido.")

    reversal = create_journal_entry(
        empresa_id=empresa_id,
        fecha=fecha,
        glosa=f"Reversión asiento {entry.numero}",
        tipo="automatico",
        created_by=created_by,
        referencia_tipo="reversion_asiento",
        referencia_id=entry.id,
        lines=[
            {
                "cuenta": line.cuenta,
                "debe": as_decimal(line.haber),
                "haber": as_decimal(line.debe),
                "referencia": f"Reversión {entry.numero}",
            }
            for line in entry.lineas
        ],
    )
    entry.estado = "revertido"
    db.session.add(entry)
    db.session.flush()
    return reversal
