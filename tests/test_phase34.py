from __future__ import annotations

from io import BytesIO
from decimal import Decimal

from app.extensions import db
from app.models import (
    Asiento,
    CuentaTesoreria,
    DocumentoCxP,
    MovimientoTesoreria,
    Pago,
    PeriodoContable,
    PlanCuenta,
)


def login(client, email: str, password: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_operations_generate_journal_entries(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    with app.app_context():
        entries = Asiento.query.all()
        ventas = [item for item in entries if item.referencia_tipo == "pedido_venta"]
        compras = [item for item in entries if item.referencia_tipo == "recepcion_compra"]
        assert ventas
        assert compras


def test_contador_can_post_manual_entry(client, app):
    login(client, "contador@facilerp.pe", "Contador123!")

    with app.app_context():
        debe = PlanCuenta.query.filter_by(codigo="1011").first()
        haber = PlanCuenta.query.filter_by(codigo="7599").first()
        assert debe is not None
        assert haber is not None

    response = client.post(
        "/contabilidad/",
        data={
            "entry-fecha": "2026-03-23",
            "entry-glosa": "Ajuste de caja",
            "entry-cuenta_debe_id": debe.id,
            "entry-cuenta_haber_id": haber.id,
            "entry-monto": "50",
            "entry-submit": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Asiento manual registrado." in response.data


def test_supplier_payment_registers_treasury_movement(client, app):
    login(client, "contador@facilerp.pe", "Contador123!")

    with app.app_context():
        documento = DocumentoCxP.query.filter(DocumentoCxP.monto_pendiente > 0).first()
        cuenta = CuentaTesoreria.query.filter_by(nombre="BCP Operaciones").first()
        assert documento is not None
        assert cuenta is not None
        before_pending = Decimal(str(documento.monto_pendiente))

    response = client.post(
        "/cxc-cxp/",
        data={
            "pay-documento_id": documento.id,
            "pay-cuenta_tesoreria_id": cuenta.id,
            "pay-fecha": "2026-03-23",
            "pay-monto": "100",
            "pay-tipo_pago": "transferencia",
            "pay-submit": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Pago registrado." in response.data

    with app.app_context():
        documento = db.session.get(DocumentoCxP, documento.id)
        pago = Pago.query.order_by(Pago.id.desc()).first()
        movimiento = MovimientoTesoreria.query.order_by(MovimientoTesoreria.id.desc()).first()
        assert documento is not None
        assert pago is not None
        assert movimiento is not None
        assert Decimal(str(documento.monto_pendiente)) == before_pending - Decimal("100.00")
        assert movimiento.tipo == "egreso"


def test_reverse_entry_and_close_period(client, app):
    login(client, "contador@facilerp.pe", "Contador123!")

    with app.app_context():
        debe = PlanCuenta.query.filter_by(codigo="1011").first()
        haber = PlanCuenta.query.filter_by(codigo="7599").first()
        assert debe is not None
        assert haber is not None

    create_response = client.post(
        "/contabilidad/",
        data={
            "entry-fecha": "2026-03-23",
            "entry-glosa": "Ajuste reversible",
            "entry-cuenta_debe_id": debe.id,
            "entry-cuenta_haber_id": haber.id,
            "entry-monto": "70",
            "entry-submit": "1",
        },
        follow_redirects=True,
    )

    assert create_response.status_code == 200

    with app.app_context():
        entry = Asiento.query.filter_by(glosa="Ajuste reversible").order_by(Asiento.id.desc()).first()
        period = PeriodoContable.query.filter_by(anio=2026, mes=3).first()
        assert entry is not None
        assert period is not None

    reverse_response = client.post(
        "/contabilidad/",
        data={
            "reverse-asiento_id": entry.id,
            "reverse-fecha": "2026-03-23",
            "reverse-submit": "1",
        },
        follow_redirects=True,
    )

    assert reverse_response.status_code == 200
    assert b"Asiento revertido." in reverse_response.data

    close_response = client.post(
        "/contabilidad/",
        data={
            "close-periodo_id": period.id,
            "close-submit": "1",
        },
        follow_redirects=True,
    )

    assert close_response.status_code == 200
    assert b"Per\xc3\xadodo cerrado." in close_response.data

    with app.app_context():
        entry = db.session.get(Asiento, entry.id)
        period = db.session.get(PeriodoContable, period.id)
        reversal = (
            Asiento.query.filter_by(referencia_tipo="reversion_asiento", referencia_id=entry.id)
            .order_by(Asiento.id.desc())
            .first()
        )
        assert entry is not None
        assert period is not None
        assert reversal is not None
        assert entry.estado == "revertido"
        assert period.estado == "cerrado"


def test_transfer_and_csv_reconcile(client, app):
    login(client, "contador@facilerp.pe", "Contador123!")

    with app.app_context():
        banco = CuentaTesoreria.query.filter_by(nombre="BCP Operaciones").first()
        caja = CuentaTesoreria.query.filter_by(nombre="Caja Principal").first()
        assert banco is not None
        assert caja is not None
        banco_saldo = Decimal(str(banco.saldo_actual))
        caja_saldo = Decimal(str(caja.saldo_actual))

    transfer_response = client.post(
        "/tesoreria/",
        data={
            "transfer-cuenta_origen_id": banco.id,
            "transfer-cuenta_destino_id": caja.id,
            "transfer-fecha": "2026-03-23",
            "transfer-monto": "50",
            "transfer-glosa": "Transferencia de prueba",
            "transfer-submit": "1",
        },
        follow_redirects=True,
    )

    assert transfer_response.status_code == 200
    assert b"Transferencia registrada." in transfer_response.data

    movement_response = client.post(
        "/tesoreria/",
        data={
            "move-cuenta_id": banco.id,
            "move-tipo": "ingreso",
            "move-fecha": "2026-03-23",
            "move-monto": "123.45",
            "move-glosa": "Deposito conciliable",
            "move-contra_cuenta_codigo": "7599",
            "move-submit": "1",
        },
        follow_redirects=True,
    )

    assert movement_response.status_code == 200
    assert b"Movimiento de tesorer\xc3\xada registrado." in movement_response.data

    reconcile_response = client.post(
        "/tesoreria/",
        data={
            "reconcile-cuenta_id": banco.id,
            "reconcile-csv_file": (BytesIO(b"fecha,monto\n2026-03-23,123.45\n"), "extracto.csv"),
            "reconcile-submit": "1",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert reconcile_response.status_code == 200
    assert b"Conciliaci\xc3\xb3n completada." in reconcile_response.data

    with app.app_context():
        banco = db.session.get(CuentaTesoreria, banco.id)
        caja = db.session.get(CuentaTesoreria, caja.id)
        conciliado = MovimientoTesoreria.query.filter_by(glosa="Deposito conciliable").first()
        transfer_out = MovimientoTesoreria.query.filter_by(tipo="transferencia_salida").first()
        transfer_in = MovimientoTesoreria.query.filter_by(tipo="transferencia_ingreso").first()
        assert banco is not None
        assert caja is not None
        assert conciliado is not None
        assert transfer_out is not None
        assert transfer_in is not None
        assert Decimal(str(banco.saldo_actual)) == banco_saldo + Decimal("73.45")
        assert Decimal(str(caja.saldo_actual)) == caja_saldo + Decimal("50.00")
        assert conciliado.conciliado is True
