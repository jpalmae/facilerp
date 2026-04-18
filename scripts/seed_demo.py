#!/usr/bin/env python
"""Seed demo data for FacilERP — rich enough to populate charts and dashboards."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta
from decimal import Decimal
import random

from app import create_app, db
from app.models.core import Empresa
from app.models.operations import (
    Producto, Almacen, Stock, Cliente, Proveedor,
    OrdenCompra, OrdenCompraLinea, Recepcion, RecepcionLinea,
    PedidoVenta, PedidoVentaLinea, DocumentoCxC,
    MovimientoStock, MovimientoTesoreria, CuentaTesoreria,
    Asiento, AsientoLinea, PeriodoContable, PlanCuenta,
)

app = create_app()
with app.app_context():
    random.seed(42)
    today = date.today()

    # ── Clean slate ──────────────────────────────────────────
    print("🧹 Limpiando datos transaccionales...")
    tables = [
        "asiento_lineas", "asientos",
        "cobros", "documentos_cxc", "documentos_cxp", "pagos",
        "recepcion_lineas", "recepciones",
        "movimientos_stock", "movimientos_tesoreria",
        "pedido_lineas", "pedidos_venta",
        "oc_lineas", "ordenes_compra",
        "stock",
        "productos", "clientes", "proveedores",
        "almacenes", "periodos_contables",
        "plan_cuentas", "cuentas_tesoreria", "tipos_cambio",
    ]
    tbl_list = ", ".join(f'"{t}"' for t in tables)
    db.session.execute(db.text(f"TRUNCATE {tbl_list} CASCADE"))
    db.session.commit()
    print("  ✅ Tablas limpiadas")

    # ── Empresa ──────────────────────────────────────────────
    empresa = db.session.query(Empresa).first()
    assert empresa, "No hay empresa — ejecuta bootstrap primero"
    eid = empresa.id
    print(f"✅ Empresa: {empresa.razon_social} (id={eid})")

    # ── Almacenes ────────────────────────────────────────────
    alm_names = ["Almacén Principal", "Tienda", "Reserva"]
    almacenes = []
    for n in alm_names:
        a = Almacen(nombre=n, empresa_id=eid)
        db.session.add(a)
        almacenes.append(a)
    db.session.flush()
    print(f"✅ {len(almacenes)} almacenes")

    # ── Plan de cuentas ──────────────────────────────────────
    cuentas_data = [
        ("10", "Efectivo y Equivalentes", "activo"),
        ("12", "Cuentas por Cobrar", "activo"),
        ("20", "Mercaderías", "activo"),
        ("40", "Tributos por Pagar", "pasivo"),
        ("42", "Cuentas por Pagar", "pasivo"),
        ("60", "Compras", "gasto"),
        ("70", "Ventas", "ingreso"),
    ]
    cuentas = {}
    for codigo, nombre, tipo in cuentas_data:
        c = PlanCuenta(codigo=codigo, nombre=nombre, tipo=tipo, empresa_id=eid)
        db.session.add(c)
        cuentas[codigo] = c
    db.session.flush()
    print(f"✅ {len(cuentas)} cuentas contables")

    # ── Cuentas tesorería ────────────────────────────────────
    cta_banco = CuentaTesoreria(tipo="banco", nombre="BCP Operaciones", banco="BCP", numero_cuenta="193-2847293", moneda="PEN", empresa_id=eid, cuenta_contable_id=cuentas["10"].id)
    cta_caja = CuentaTesoreria(tipo="caja", nombre="Caja Principal", moneda="PEN", empresa_id=eid, cuenta_contable_id=cuentas["10"].id)
    db.session.add_all([cta_banco, cta_caja])
    db.session.flush()
    print("✅ 2 cuentas de tesorería")

    # ── Productos ────────────────────────────────────────────
    productos_data = [
        ("Laptop HP 15", "LAP-001", Decimal("2500.00"), "tecnología"),
        ("Monitor Samsung 27\"", "MON-001", Decimal("890.00"), "tecnología"),
        ("Teclado Mecánico Logitech", "TEC-001", Decimal("250.00"), "tecnología"),
        ("Mouse Inalámbrico", "MOU-001", Decimal("85.00"), "tecnología"),
        ("Impresora Epson L3250", "IMP-001", Decimal("780.00"), "tecnología"),
        ("Silla Ergonómica", "SIL-001", Decimal("650.00"), "mobiliario"),
        ("Escritorio Standing Desk", "ESC-001", Decimal("1200.00"), "mobiliario"),
        ("Auriculares Sony WH-1000", "AUR-001", Decimal("320.00"), "tecnología"),
        ("Webcam Logitech C920", "WEB-001", Decimal("180.00"), "tecnología"),
        ("SSD Kingston 480GB", "SSD-001", Decimal("120.00"), "tecnología"),
        ("RAM DDR4 16GB", "RAM-001", Decimal("95.00"), "tecnología"),
        ("Hub USB-C 7 puertos", "HUB-001", Decimal("110.00"), "tecnología"),
        ("Proyector BenQ 1080p", "PRO-001", Decimal("1800.00"), "tecnología"),
        ("Cable HDMI 2m", "CAB-001", Decimal("25.00"), "accesorios"),
        ("Pad Mouse XL", "PAD-001", Decimal("45.00"), "accesorios"),
    ]
    productos = []
    for nombre, codigo, precio, cat in productos_data:
        p = Producto(
            codigo=codigo, nombre=nombre, precio_venta=precio,
            costo_promedio=precio * Decimal("0.6"),
            categoria=cat, empresa_id=eid,
        )
        db.session.add(p)
        productos.append(p)
    db.session.flush()
    print(f"✅ {len(productos)} productos")

    # ── Stock inicial ────────────────────────────────────────
    for p in productos:
        for a in almacenes[:2]:
            qty = Decimal(random.randint(5, 50))
            s = Stock(producto_id=p.id, almacen_id=a.id, cantidad_disponible=qty)
            db.session.add(s)
    db.session.flush()
    print("✅ Stock inicial creado")

    # ── Clientes ─────────────────────────────────────────────
    clientes_data = [
        ("Carlos Mendoza", "10456789012", "empresa"),
        ("María García", "10987654321", "persona"),
        ("Tech Solutions S.A.C.", "20555666777", "empresa"),
        ("Inversiones del Sur E.I.R.L.", "20444555666", "empresa"),
        ("Pedro Huamán", "10123456789", "persona"),
        ("Ana Quispe", "10345678901", "persona"),
        ("Distribuidora Nacional S.A.", "20777888999", "empresa"),
        ("Luis Torres", "10234567890", "persona"),
        ("Comercial Andina E.I.R.L.", "20666555444", "empresa"),
        ("Sofía Romero", "10456789123", "persona"),
    ]
    clientes = []
    for nombre, doc, tipo in clientes_data:
        c = Cliente(documento=doc, razon_social=nombre, tipo_cliente=tipo, empresa_id=eid)
        db.session.add(c)
        clientes.append(c)
    db.session.flush()
    print(f"✅ {len(clientes)} clientes")

    # ── Proveedores ──────────────────────────────────────────
    proveedores_data = [
        ("Distribuidora ABC S.A.C.", "20111222333"),
        ("Tech Import E.I.R.L.", "20333444555"),
        ("Office World S.A.", "20555666777"),
        ("Insumos Globales S.A.C.", "20444777888"),
        ("Mega Suministros E.I.R.L.", "20888999000"),
    ]
    proveedores = []
    for nombre, ruc in proveedores_data:
        p = Proveedor(ruc=ruc, razon_social=nombre, empresa_id=eid)
        db.session.add(p)
        proveedores.append(p)
    db.session.flush()
    print(f"✅ {len(proveedores)} proveedores")

    # ── Periodos contables (últimos 6 meses) ────────────────
    periodos = {}
    for i in range(6):
        d = today - timedelta(days=30 * i)
        key = f"{d.year}-{d.month:02d}"
        per = PeriodoContable(anio=d.year, mes=d.month, empresa_id=eid, estado="cerrado" if i > 0 else "abierto")
        db.session.add(per)
        periodos[key] = per
    db.session.flush()
    print(f"✅ {len(periodos)} periodos contables")

    # ── Órdenes de compra (últimos 6 meses) ─────────────────
    ocs = []
    for i in range(15):
        dias_atras = random.randint(1, 180)
        fecha = today - timedelta(days=dias_atras)
        prov = random.choice(proveedores)
        estado = "recibida" if dias_atras > 30 else random.choice(["emitida", "aprobada", "recibida"])

        oc = OrdenCompra(
            proveedor_id=prov.id, empresa_id=eid,
            fecha=fecha, estado=estado,
            observaciones=f"OC-{i+1:04d}",
        )
        db.session.add(oc)
        db.session.flush()

        # 1-3 líneas por OC
        num_lineas = random.randint(1, 3)
        total = Decimal("0")
        for j in range(num_lineas):
            prod = random.choice(productos)
            qty = Decimal(random.randint(5, 30))
            precio = prod.precio_venta * Decimal("0.6")
            sub = qty * precio
            igv = sub * Decimal("0.18")
            linea = OrdenCompraLinea(
                oc_id=oc.id, producto_id=prod.id,
                cantidad=qty, precio_unitario=precio,
                subtotal=sub, igv_linea=igv,
            )
            db.session.add(linea)
            total += sub + igv

        oc.subtotal = total / Decimal("1.18")
        oc.igv = total - oc.subtotal
        oc.total = total
        ocs.append(oc)
    db.session.flush()
    print(f"✅ {len(ocs)} órdenes de compra")

    # ── Recepciones ──────────────────────────────────────────
    recepciones = []
    for oc in ocs:
        if oc.estado == "recibida":
            rec = Recepcion(
                oc_id=oc.id, almacen_id=almacenes[0].id,
                empresa_id=eid, fecha=oc.fecha + timedelta(days=random.randint(2, 7)),
            )
            db.session.add(rec)
            db.session.flush()
            # Create reception lines from OC lines
            for linea in oc.lineas:
                rl = RecepcionLinea(recepcion_id=rec.id, oc_linea_id=linea.id, producto_id=linea.producto_id, cantidad_recibida=linea.cantidad)
                db.session.add(rl)
            recepciones.append(rec)
    db.session.flush()
    print(f"✅ {len(recepciones)} recepciones")

    # ── Pedidos de venta (últimos 6 meses) ──────────────────
    pedidos = []
    for i in range(30):
        dias_atras = random.randint(1, 180)
        fecha = today - timedelta(days=dias_atras)
        cliente = random.choice(clientes)
        estado = "entregado" if dias_atras > 14 else random.choice(["confirmado", "entregado", "pendiente"])

        pv = PedidoVenta(
            cliente_id=cliente.id, empresa_id=eid,
            almacen_id=almacenes[0].id,
            fecha=fecha, estado=estado,
            observaciones=f"PV-{i+1:04d}",
        )
        db.session.add(pv)
        db.session.flush()

        num_lineas = random.randint(1, 4)
        total = Decimal("0")
        for j in range(num_lineas):
            prod = random.choice(productos)
            qty = Decimal(random.randint(1, 10))
            sub = qty * prod.precio_venta
            igv = sub * Decimal("0.18")
            linea = PedidoVentaLinea(
                pedido_id=pv.id, producto_id=prod.id,
                cantidad=qty, precio_unitario=prod.precio_venta,
                subtotal=sub, igv_linea=igv,
            )
            db.session.add(linea)
            total += sub + igv

        pv.subtotal = total / Decimal("1.18")
        pv.igv = total - pv.subtotal
        pv.total = total
        pedidos.append(pv)
    db.session.flush()
    print(f"✅ {len(pedidos)} pedidos de venta")

    # ── Documentos CxC ───────────────────────────────────────
    for pv in pedidos:
        if pv.estado == "entregado":
            pagado = random.random() < 0.6
            doc = DocumentoCxC(
                cliente_id=pv.cliente_id,
                empresa_id=eid,
                pedido_id=pv.id,
                tipo="factura",
                monto_original=pv.total,
                monto_pendiente=Decimal("0") if pagado else pv.total,
                fecha_emision=pv.fecha,
                fecha_vencimiento=pv.fecha + timedelta(days=30),
                estado="pagada" if pagado else random.choice(["pendiente", "vencida"]),
            )
            db.session.add(doc)
    db.session.flush()
    print("✅ Documentos CxC creados")

    # ── Movimientos de tesorería ─────────────────────────────
    for i in range(20):
        dias_atras = random.randint(1, 90)
        monto = Decimal(random.randint(500, 15000))
        es_ingreso = random.random() > 0.4
        mov = MovimientoTesoreria(
            empresa_id=eid,
            cuenta_id=cta_banco.id if random.random() > 0.3 else cta_caja.id,
            tipo="ingreso" if es_ingreso else "egreso",
            monto=monto,
            fecha=today - timedelta(days=dias_atras),
            glosa=f"{'Cobro' if es_ingreso else 'Pago'} #{i+1:03d}",
        )
        db.session.add(mov)
    db.session.flush()
    print("✅ 20 movimientos de tesorería")

    # ── Asientos contables ───────────────────────────────────
    for i in range(15):
        dias_atras = random.randint(1, 90)
        fecha = today - timedelta(days=dias_atras)
        periodo_key = f"{fecha.year}-{fecha.month:02d}"
        periodo = periodos.get(periodo_key)
        if not periodo:
            continue

        asiento = Asiento(
            empresa_id=eid,
            periodo_id=periodo.id,
            numero=i + 1,
            fecha=fecha,
            glosa=f"Asiento de registro {i+1}",
            tipo="manual",
            estado="registrado",
        )
        db.session.add(asiento)
        db.session.flush()

        monto = Decimal(random.randint(500, 8000))
        db.session.add(AsientoLinea(
            asiento_id=asiento.id, cuenta_id=cuentas["12"].id,
            debe=monto, haber=Decimal("0"),
        ))
        db.session.add(AsientoLinea(
            asiento_id=asiento.id, cuenta_id=cuentas["70"].id,
            debe=Decimal("0"), haber=monto,
        ))
    db.session.flush()
    print("✅ 15 asientos contables")

    # ── Commit ───────────────────────────────────────────────
    db.session.commit()
    print("")
    print("🎉 Datos semilla cargados exitosamente!")
    print(f"   Empresa: {empresa.razon_social}")
    print(f"   {len(productos)} productos | {len(clientes)} clientes | {len(proveedores)} proveedores")
    print(f"   {len(ocs)} OCs | {len(pedidos)} PVs | {len(recepciones)} recepciones")
    print(f"   {len(periodos)} periodos | 15 asientos | 20 mov. tesorería")
