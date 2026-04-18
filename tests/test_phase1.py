from __future__ import annotations

from decimal import Decimal

from app.models import Almacen, OrdenCompra, Producto, Proveedor, Stock
from app.extensions import db


def login(client, email: str, password: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_vendedor_can_view_inventory_but_not_compras(client):
    login(client, "ventas@facilerp.pe", "Ventas123!")

    inventory_response = client.get("/inventario/")
    purchases_response = client.get("/compras/")

    assert inventory_response.status_code == 200
    assert purchases_response.status_code == 403


def test_purchase_reception_updates_stock(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    with app.app_context():
        supplier = Proveedor.query.filter_by(ruc="20601234567").first()
        producto = Producto.query.filter_by(codigo="LAP-15").first()
        almacen = Almacen.query.filter_by(nombre="Almacén Principal").first()
        assert supplier is not None
        assert producto is not None
        assert almacen is not None

    order_response = client.post(
        "/compras/",
        data={
            "order-proveedor_id": supplier.id,
            "order-producto_id": producto.id,
            "order-fecha": "2026-03-23",
            "order-cantidad": "5",
            "order-precio_unitario": "2300",
            "order-observaciones": "Reposición semanal",
            "order-submit": "1",
        },
        follow_redirects=True,
    )
    assert order_response.status_code == 200
    assert b"Orden de compra emitida." in order_response.data

    with app.app_context():
        order = OrdenCompra.query.order_by(OrdenCompra.id.desc()).first()
        assert order is not None
        existing_stock = Stock.query.filter_by(
            producto_id=producto.id, almacen_id=almacen.id
        ).first()
        before_qty = Decimal(str(existing_stock.cantidad_disponible))

    receipt_response = client.post(
        "/compras/",
        data={
            "receipt-oc_id": order.id,
            "receipt-almacen_id": almacen.id,
            "receipt-fecha": "2026-03-23",
            "receipt-cantidad_recibida": "2",
            "receipt-submit": "1",
        },
        follow_redirects=True,
    )
    assert receipt_response.status_code == 200
    assert b"Recepci" in receipt_response.data

    with app.app_context():
        stock = Stock.query.filter_by(producto_id=producto.id, almacen_id=almacen.id).first()
        order = db.session.get(OrdenCompra, order.id)
        assert stock is not None
        assert order is not None
        assert Decimal(str(stock.cantidad_disponible)) == before_qty + Decimal("2.00")
        assert order.estado == "parcial"


def test_inventory_prevents_negative_stock(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    with app.app_context():
        producto = Producto.query.filter_by(codigo="MSE-WL").first()
        almacen = Almacen.query.filter_by(nombre="Almacén Principal").first()
        stock = Stock.query.filter_by(producto_id=producto.id, almacen_id=almacen.id).first()
        assert producto is not None
        assert almacen is not None
        assert stock is not None
        before_qty = Decimal(str(stock.cantidad_disponible))

    response = client.post(
        "/inventario/",
        data={
            "move-producto_id": producto.id,
            "move-almacen_id": almacen.id,
            "move-tipo": "salida",
            "move-cantidad": str(before_qty + Decimal("1.00")),
            "move-costo_unitario": "0",
            "move-submit": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"stock no puede quedar negativo" in response.data.lower()

    with app.app_context():
        stock = Stock.query.filter_by(producto_id=producto.id, almacen_id=almacen.id).first()
        assert stock is not None
        assert Decimal(str(stock.cantidad_disponible)) == before_qty
