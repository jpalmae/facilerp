from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import (
    Almacen,
    Cliente,
    Cobro,
    CuentaTesoreria,
    DocumentoCxC,
    PedidoVenta,
    Producto,
    Stock,
)


def login(client, email: str, password: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_vendedor_can_create_sale_and_generate_cxc(client, app):
    login(client, "ventas@facilerp.pe", "Ventas123!")

    with app.app_context():
        cliente = Cliente.query.filter_by(documento="20111111111").first()
        producto = Producto.query.filter_by(codigo="MSE-WL").first()
        almacen = Almacen.query.filter_by(nombre="Almacén Principal").first()
        stock = Stock.query.filter_by(producto_id=producto.id, almacen_id=almacen.id).first()
        assert cliente is not None
        assert producto is not None
        assert almacen is not None
        assert stock is not None
        before_qty = Decimal(str(stock.cantidad_disponible))

    response = client.post(
        "/ventas/",
        data={
            "sale-cliente_id": cliente.id,
            "sale-producto_id": producto.id,
            "sale-almacen_id": almacen.id,
            "sale-fecha": "2026-03-23",
            "sale-cantidad": "1",
            "sale-precio_unitario": "90",
            "sale-observaciones": "Venta vendedor",
            "sale-submit": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"CxC generada" in response.data

    with app.app_context():
        pedido = PedidoVenta.query.order_by(PedidoVenta.id.desc()).first()
        documento = DocumentoCxC.query.order_by(DocumentoCxC.id.desc()).first()
        stock = Stock.query.filter_by(producto_id=producto.id, almacen_id=almacen.id).first()
        assert pedido is not None
        assert documento is not None
        assert stock is not None
        assert Decimal(str(stock.cantidad_disponible)) == before_qty - Decimal("1.00")
        assert Decimal(str(documento.monto_pendiente)) == Decimal(str(documento.monto_original))


def test_contador_can_register_collection(client, app):
    login(client, "contador@facilerp.pe", "Contador123!")

    with app.app_context():
        documento = DocumentoCxC.query.filter(
            DocumentoCxC.monto_pendiente > 0
        ).order_by(DocumentoCxC.id.desc()).first()
        cuenta = CuentaTesoreria.query.filter_by(nombre="BCP Operaciones").first()
        assert documento is not None
        assert cuenta is not None
        pending_before = Decimal(str(documento.monto_pendiente))

    response = client.post(
        "/cxc-cxp/",
        data={
            "collect-documento_id": documento.id,
            "collect-cuenta_tesoreria_id": cuenta.id,
            "collect-fecha": "2026-03-23",
            "collect-monto": "20",
            "collect-tipo_pago": "transferencia",
            "collect-submit": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Cobro registrado." in response.data

    with app.app_context():
        documento = db.session.get(DocumentoCxC, documento.id)
        cobro = Cobro.query.order_by(Cobro.id.desc()).first()
        assert documento is not None
        assert cobro is not None
        assert Decimal(str(documento.monto_pendiente)) == pending_before - Decimal("20.00")
        assert cobro.documento_cxc_id == documento.id
