from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models.mixins import TimestampMixin


class Producto(TimestampMixin, db.Model):
    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    codigo = db.Column(db.String(50), nullable=False)
    nombre = db.Column(db.String(255), nullable=False)
    categoria = db.Column(db.String(120), nullable=True)
    unidad_medida = db.Column(db.String(20), nullable=False, default="UND")
    tipo = db.Column(db.String(20), nullable=False, default="bien")
    costo_promedio = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    precio_venta = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    stock_minimo = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    activo = db.Column(db.Boolean, nullable=False, default=True)

    stock_items = db.relationship(
        "Stock",
        back_populates="producto",
        passive_deletes=True,
    )
    movimientos = db.relationship(
        "MovimientoStock",
        back_populates="producto",
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "codigo", name="uq_producto_empresa_codigo"),
    )

    @property
    def requiere_stock(self) -> bool:
        return self.tipo == "bien"


class Almacen(TimestampMixin, db.Model):
    __tablename__ = "almacenes"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    nombre = db.Column(db.String(120), nullable=False)
    ubicacion = db.Column(db.String(255), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    stock_items = db.relationship(
        "Stock",
        back_populates="almacen",
        passive_deletes=True,
    )
    movimientos = db.relationship(
        "MovimientoStock",
        back_populates="almacen",
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "nombre", name="uq_almacen_empresa_nombre"),
    )


class Stock(TimestampMixin, db.Model):
    __tablename__ = "stock"

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(
        db.Integer, db.ForeignKey("productos.id"), nullable=False, index=True
    )
    almacen_id = db.Column(
        db.Integer, db.ForeignKey("almacenes.id"), nullable=False, index=True
    )
    cantidad_disponible = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    cantidad_reservada = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    producto = db.relationship("Producto", back_populates="stock_items")
    almacen = db.relationship("Almacen", back_populates="stock_items")

    __table_args__ = (
        db.UniqueConstraint("producto_id", "almacen_id", name="uq_stock_producto_almacen"),
    )


class MovimientoStock(TimestampMixin, db.Model):
    __tablename__ = "movimientos_stock"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    producto_id = db.Column(
        db.Integer, db.ForeignKey("productos.id"), nullable=False, index=True
    )
    almacen_id = db.Column(
        db.Integer, db.ForeignKey("almacenes.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(20), nullable=False)
    cantidad = db.Column(db.Numeric(12, 2), nullable=False)
    costo_unitario = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    costo_total = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    referencia_tipo = db.Column(db.String(50), nullable=True)
    referencia_id = db.Column(db.Integer, nullable=True)
    asiento_id = db.Column(db.Integer, db.ForeignKey("asientos.id"), nullable=True)
    fecha = db.Column(db.Date, nullable=False)

    producto = db.relationship("Producto", back_populates="movimientos")
    almacen = db.relationship("Almacen", back_populates="movimientos")


class Proveedor(TimestampMixin, db.Model):
    __tablename__ = "proveedores"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    ruc = db.Column(db.String(11), nullable=False)
    razon_social = db.Column(db.String(255), nullable=False)
    tipo_proveedor = db.Column(db.String(60), nullable=False, default="general")
    condicion_pago = db.Column(db.String(60), nullable=False, default="contado")
    cuenta_detraccion = db.Column(db.String(60), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    ordenes = db.relationship(
        "OrdenCompra",
        back_populates="proveedor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "ruc", name="uq_proveedor_empresa_ruc"),
    )


class Cliente(TimestampMixin, db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    documento = db.Column(db.String(11), nullable=False)
    razon_social = db.Column(db.String(255), nullable=False)
    tipo_cliente = db.Column(db.String(40), nullable=False, default="empresa")
    condicion_pago = db.Column(db.String(60), nullable=False, default="credito")
    activo = db.Column(db.Boolean, nullable=False, default=True)

    pedidos = db.relationship(
        "PedidoVenta",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )
    documentos_cxc = db.relationship(
        "DocumentoCxC",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "documento", name="uq_cliente_empresa_documento"),
    )


class OrdenCompra(TimestampMixin, db.Model):
    __tablename__ = "ordenes_compra"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    proveedor_id = db.Column(
        db.Integer, db.ForeignKey("proveedores.id"), nullable=False, index=True
    )
    fecha = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="emitida")
    moneda = db.Column(db.String(3), nullable=False, default="PEN")
    tipo_cambio = db.Column(db.Numeric(10, 3), nullable=False, default=Decimal("1.000"))
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    igv = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    observaciones = db.Column(db.Text, nullable=True)

    proveedor = db.relationship("Proveedor", back_populates="ordenes")
    lineas = db.relationship(
        "OrdenCompraLinea",
        back_populates="orden",
        cascade="all, delete-orphan",
    )
    recepciones = db.relationship(
        "Recepcion",
        back_populates="orden",
        cascade="all, delete-orphan",
    )

    @property
    def total_recibido(self) -> Decimal:
        recibido = Decimal("0.00")
        for linea in self.lineas:
            recibido += linea.cantidad_recibida or Decimal("0.00")
        return recibido


class OrdenCompraLinea(TimestampMixin, db.Model):
    __tablename__ = "oc_lineas"

    id = db.Column(db.Integer, primary_key=True)
    oc_id = db.Column(
        db.Integer, db.ForeignKey("ordenes_compra.id"), nullable=False, index=True
    )
    producto_id = db.Column(
        db.Integer, db.ForeignKey("productos.id"), nullable=False, index=True
    )
    cantidad = db.Column(db.Numeric(12, 2), nullable=False)
    cantidad_recibida = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    descuento_pct = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    igv_linea = db.Column(db.Numeric(12, 2), nullable=False)

    orden = db.relationship("OrdenCompra", back_populates="lineas")
    producto = db.relationship("Producto")
    recepciones = db.relationship(
        "RecepcionLinea",
        back_populates="oc_linea",
        cascade="all, delete-orphan",
    )

    @property
    def pendiente(self) -> Decimal:
        return (self.cantidad or Decimal("0.00")) - (
            self.cantidad_recibida or Decimal("0.00")
        )


class Recepcion(TimestampMixin, db.Model):
    __tablename__ = "recepciones"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    oc_id = db.Column(
        db.Integer, db.ForeignKey("ordenes_compra.id"), nullable=False, index=True
    )
    fecha = db.Column(db.Date, nullable=False)
    almacen_id = db.Column(
        db.Integer, db.ForeignKey("almacenes.id"), nullable=False, index=True
    )
    estado = db.Column(db.String(30), nullable=False, default="recibida")

    orden = db.relationship("OrdenCompra", back_populates="recepciones")
    almacen = db.relationship("Almacen")
    lineas = db.relationship(
        "RecepcionLinea",
        back_populates="recepcion",
        cascade="all, delete-orphan",
    )


class RecepcionLinea(TimestampMixin, db.Model):
    __tablename__ = "recepcion_lineas"

    id = db.Column(db.Integer, primary_key=True)
    recepcion_id = db.Column(
        db.Integer, db.ForeignKey("recepciones.id"), nullable=False, index=True
    )
    oc_linea_id = db.Column(
        db.Integer, db.ForeignKey("oc_lineas.id"), nullable=False, index=True
    )
    producto_id = db.Column(
        db.Integer, db.ForeignKey("productos.id"), nullable=False, index=True
    )
    cantidad_recibida = db.Column(db.Numeric(12, 2), nullable=False)
    lote = db.Column(db.String(60), nullable=True)
    fecha_vencimiento = db.Column(db.Date, nullable=True)

    recepcion = db.relationship("Recepcion", back_populates="lineas")
    oc_linea = db.relationship("OrdenCompraLinea", back_populates="recepciones")
    producto = db.relationship("Producto")


class PedidoVenta(TimestampMixin, db.Model):
    __tablename__ = "pedidos_venta"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    cliente_id = db.Column(
        db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True
    )
    almacen_id = db.Column(
        db.Integer, db.ForeignKey("almacenes.id"), nullable=False, index=True
    )
    fecha = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="confirmado")
    moneda = db.Column(db.String(3), nullable=False, default="PEN")
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    igv = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    observaciones = db.Column(db.Text, nullable=True)

    cliente = db.relationship("Cliente", back_populates="pedidos")
    almacen = db.relationship("Almacen")
    lineas = db.relationship(
        "PedidoVentaLinea",
        back_populates="pedido",
        cascade="all, delete-orphan",
    )
    documentos_cxc = db.relationship(
        "DocumentoCxC",
        back_populates="pedido",
        cascade="all, delete-orphan",
    )


class PedidoVentaLinea(TimestampMixin, db.Model):
    __tablename__ = "pedido_lineas"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer, db.ForeignKey("pedidos_venta.id"), nullable=False, index=True
    )
    producto_id = db.Column(
        db.Integer, db.ForeignKey("productos.id"), nullable=False, index=True
    )
    cantidad = db.Column(db.Numeric(12, 2), nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    descuento_pct = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    igv_linea = db.Column(db.Numeric(12, 2), nullable=False)

    pedido = db.relationship("PedidoVenta", back_populates="lineas")
    producto = db.relationship("Producto")


class DocumentoCxC(TimestampMixin, db.Model):
    __tablename__ = "documentos_cxc"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    cliente_id = db.Column(
        db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True
    )
    pedido_id = db.Column(
        db.Integer, db.ForeignKey("pedidos_venta.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(30), nullable=False, default="pedido")
    monto_original = db.Column(db.Numeric(12, 2), nullable=False)
    monto_pendiente = db.Column(db.Numeric(12, 2), nullable=False)
    fecha_emision = db.Column(db.Date, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="pendiente")

    cliente = db.relationship("Cliente", back_populates="documentos_cxc")
    pedido = db.relationship("PedidoVenta", back_populates="documentos_cxc")
    cobros = db.relationship(
        "Cobro",
        back_populates="documento",
        cascade="all, delete-orphan",
    )


class Cobro(TimestampMixin, db.Model):
    __tablename__ = "cobros"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    documento_cxc_id = db.Column(
        db.Integer, db.ForeignKey("documentos_cxc.id"), nullable=False, index=True
    )
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    tipo_pago = db.Column(db.String(30), nullable=False, default="transferencia")
    asiento_id = db.Column(db.Integer, db.ForeignKey("asientos.id"), nullable=True)

    documento = db.relationship("DocumentoCxC", back_populates="cobros")


class DocumentoCxP(TimestampMixin, db.Model):
    __tablename__ = "documentos_cxp"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    proveedor_id = db.Column(
        db.Integer, db.ForeignKey("proveedores.id"), nullable=False, index=True
    )
    recepcion_id = db.Column(
        db.Integer, db.ForeignKey("recepciones.id"), nullable=False, index=True
    )
    monto_original = db.Column(db.Numeric(12, 2), nullable=False)
    monto_pendiente = db.Column(db.Numeric(12, 2), nullable=False)
    fecha_emision = db.Column(db.Date, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="pendiente")
    asiento_id = db.Column(db.Integer, db.ForeignKey("asientos.id"), nullable=True)

    proveedor = db.relationship("Proveedor")
    recepcion = db.relationship("Recepcion")
    pagos = db.relationship(
        "Pago",
        back_populates="documento",
        cascade="all, delete-orphan",
    )


class Pago(TimestampMixin, db.Model):
    __tablename__ = "pagos"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    documento_cxp_id = db.Column(
        db.Integer, db.ForeignKey("documentos_cxp.id"), nullable=False, index=True
    )
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    tipo_pago = db.Column(db.String(30), nullable=False, default="transferencia")
    cuenta_tesoreria_id = db.Column(
        db.Integer, db.ForeignKey("cuentas_tesoreria.id"), nullable=True, index=True
    )
    asiento_id = db.Column(db.Integer, db.ForeignKey("asientos.id"), nullable=True)

    documento = db.relationship("DocumentoCxP", back_populates="pagos")
    cuenta_tesoreria = db.relationship("CuentaTesoreria")


class PlanCuenta(TimestampMixin, db.Model):
    __tablename__ = "plan_cuentas"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    codigo = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    nivel = db.Column(db.Integer, nullable=False, default=1)
    cuenta_padre_id = db.Column(
        db.Integer, db.ForeignKey("plan_cuentas.id"), nullable=True, index=True
    )
    permite_movimiento = db.Column(db.Boolean, nullable=False, default=True)

    cuenta_padre = db.relationship("PlanCuenta", remote_side=[id])
    lineas = db.relationship("AsientoLinea", back_populates="cuenta")

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "codigo", name="uq_plan_cuenta_empresa_codigo"),
    )


class PeriodoContable(TimestampMixin, db.Model):
    __tablename__ = "periodos_contables"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="abierto")
    fecha_cierre = db.Column(db.Date, nullable=True)

    asientos = db.relationship(
        "Asiento",
        back_populates="periodo",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "anio", "mes", name="uq_periodo_empresa_anio_mes"),
    )


class Asiento(TimestampMixin, db.Model):
    __tablename__ = "asientos"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    periodo_id = db.Column(
        db.Integer, db.ForeignKey("periodos_contables.id"), nullable=False, index=True
    )
    numero = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    glosa = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default="manual")
    estado = db.Column(db.String(20), nullable=False, default="registrado")
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    referencia_tipo = db.Column(db.String(50), nullable=True)
    referencia_id = db.Column(db.Integer, nullable=True)

    periodo = db.relationship("PeriodoContable", back_populates="asientos")
    lineas = db.relationship(
        "AsientoLinea",
        back_populates="asiento",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "periodo_id", "numero", name="uq_asiento_periodo_numero"),
    )


class AsientoLinea(TimestampMixin, db.Model):
    __tablename__ = "asiento_lineas"

    id = db.Column(db.Integer, primary_key=True)
    asiento_id = db.Column(
        db.Integer, db.ForeignKey("asientos.id"), nullable=False, index=True
    )
    cuenta_id = db.Column(
        db.Integer, db.ForeignKey("plan_cuentas.id"), nullable=False, index=True
    )
    debe = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    haber = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    referencia = db.Column(db.String(255), nullable=True)
    centro_costo = db.Column(db.String(120), nullable=True)

    asiento = db.relationship("Asiento", back_populates="lineas")
    cuenta = db.relationship("PlanCuenta", back_populates="lineas")


class CuentaTesoreria(TimestampMixin, db.Model):
    __tablename__ = "cuentas_tesoreria"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(20), nullable=False, default="banco")
    nombre = db.Column(db.String(120), nullable=False)
    banco = db.Column(db.String(120), nullable=True)
    numero_cuenta = db.Column(db.String(60), nullable=True)
    moneda = db.Column(db.String(3), nullable=False, default="PEN")
    saldo_actual = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    cuenta_contable_id = db.Column(
        db.Integer, db.ForeignKey("plan_cuentas.id"), nullable=False, index=True
    )
    activo = db.Column(db.Boolean, nullable=False, default=True)

    cuenta_contable = db.relationship("PlanCuenta")
    movimientos = db.relationship(
        "MovimientoTesoreria",
        back_populates="cuenta",
        cascade="all, delete-orphan",
    )


class MovimientoTesoreria(TimestampMixin, db.Model):
    __tablename__ = "movimientos_tesoreria"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    cuenta_id = db.Column(
        db.Integer, db.ForeignKey("cuentas_tesoreria.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(20), nullable=False)
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    glosa = db.Column(db.String(255), nullable=False)
    referencia_tipo = db.Column(db.String(50), nullable=True)
    referencia_id = db.Column(db.Integer, nullable=True)
    conciliado = db.Column(db.Boolean, nullable=False, default=False)
    asiento_id = db.Column(db.Integer, db.ForeignKey("asientos.id"), nullable=True)

    cuenta = db.relationship("CuentaTesoreria", back_populates="movimientos")


class TipoCambio(TimestampMixin, db.Model):
    __tablename__ = "tipos_cambio"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True
    )
    moneda = db.Column(db.String(3), nullable=False, default="USD")
    fecha = db.Column(db.Date, nullable=False)
    compra = db.Column(db.Numeric(10, 3), nullable=False)
    venta = db.Column(db.Numeric(10, 3), nullable=False)
    fuente = db.Column(db.String(60), nullable=False, default="manual")

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "moneda", "fecha", name="uq_tipo_cambio_empresa_fecha"),
    )
