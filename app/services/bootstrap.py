from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import (
    Almacen,
    Cliente,
    DocumentoCxP,
    Empresa,
    MarcaConfig,
    PERM_ACCOUNTING_MANAGE,
    PERM_ACCOUNTING_VIEW,
    PERM_CXC_CXP_MANAGE,
    PERM_CXC_CXP_VIEW,
    PERM_INVENTORY_VIEW,
    PERM_PURCHASES_MANAGE,
    PERM_PURCHASES_VIEW,
    PERM_REPORTS_VIEW,
    PERM_SALES_MANAGE,
    PERM_SALES_VIEW,
    PERM_TREASURY_MANAGE,
    PERM_TREASURY_VIEW,
    Producto,
    Proveedor,
    SecurityGroup,
    SecurityGroupPermission,
    SecurityUserGroup,
    User,
    UserEmpresaRole,
    ROLE_ADMIN,
    ROLE_CONTADOR,
    ROLE_VENDEDOR,
)
from app.services.accounting import ensure_accounting_setup
from app.services.inventory import register_stock_movement
from app.services.purchases import create_purchase_order, receive_purchase_order
from app.services.sales import create_sales_order, register_collection
from app.services.treasury import (
    create_treasury_account,
    register_supplier_payment,
    register_treasury_movement,
)


def ensure_security_demo_data() -> None:
    empresa_principal = Empresa.query.filter_by(ruc="20123456789").first()
    if empresa_principal is None:
        return

    contador = User.query.filter_by(email="contador@facilerp.pe").first()
    vendedor = User.query.filter_by(email="ventas@facilerp.pe").first()
    admin = User.query.filter_by(email="admin@facilerp.pe").first()
    if contador is None or vendedor is None or admin is None:
        return

    if admin.default_empresa_id is None:
        admin.default_empresa_id = empresa_principal.id
    if contador.default_empresa_id is None:
        contador.default_empresa_id = empresa_principal.id
    if vendedor.default_empresa_id is None:
        vendedor.default_empresa_id = empresa_principal.id

    grupo_finanzas = SecurityGroup.query.filter_by(
        empresa_id=empresa_principal.id,
        nombre="Finanzas",
    ).first()
    if grupo_finanzas is None:
        grupo_finanzas = SecurityGroup(
            empresa_id=empresa_principal.id,
            nombre="Finanzas",
            descripcion="Equipo contable y de tesorería.",
        )
        db.session.add(grupo_finanzas)
        db.session.flush()

    grupo_comercial = SecurityGroup.query.filter_by(
        empresa_id=empresa_principal.id,
        nombre="Comercial",
    ).first()
    if grupo_comercial is None:
        grupo_comercial = SecurityGroup(
            empresa_id=empresa_principal.id,
            nombre="Comercial",
            descripcion="Equipo comercial con foco en ventas y seguimiento.",
        )
        db.session.add(grupo_comercial)
        db.session.flush()

    for group, permission_code in [
        (grupo_finanzas, PERM_PURCHASES_VIEW),
        (grupo_finanzas, PERM_PURCHASES_MANAGE),
        (grupo_finanzas, PERM_CXC_CXP_VIEW),
        (grupo_finanzas, PERM_CXC_CXP_MANAGE),
        (grupo_finanzas, PERM_ACCOUNTING_VIEW),
        (grupo_finanzas, PERM_ACCOUNTING_MANAGE),
        (grupo_finanzas, PERM_TREASURY_VIEW),
        (grupo_finanzas, PERM_TREASURY_MANAGE),
        (grupo_finanzas, PERM_REPORTS_VIEW),
        (grupo_comercial, PERM_INVENTORY_VIEW),
        (grupo_comercial, PERM_SALES_VIEW),
        (grupo_comercial, PERM_SALES_MANAGE),
        (grupo_comercial, PERM_CXC_CXP_VIEW),
        (grupo_comercial, PERM_REPORTS_VIEW),
    ]:
        exists = SecurityGroupPermission.query.filter_by(
            group_id=group.id,
            permission_code=permission_code,
        ).first()
        if exists is None:
            db.session.add(
                SecurityGroupPermission(
                    group_id=group.id,
                    permission_code=permission_code,
                )
            )

    for user, group in [
        (contador, grupo_finanzas),
        (vendedor, grupo_comercial),
    ]:
        exists = SecurityUserGroup.query.filter_by(
            user_id=user.id,
            group_id=group.id,
        ).first()
        if exists is None:
            db.session.add(
                SecurityUserGroup(user_id=user.id, group_id=group.id, activo=True)
            )
        else:
            exists.activo = True


def ensure_demo_data() -> None:
    if Empresa.query.first():
        ensure_security_demo_data()
        return

    empresa_principal = Empresa(
        ruc="20123456789",
        razon_social="ContaFácil SAC",
        moneda="PEN",
        regimen_tributario="Régimen General",
    )
    empresa_secundaria = Empresa(
        ruc="20567891234",
        razon_social="Andes Retail EIRL",
        moneda="PEN",
        regimen_tributario="MYPE Tributario",
    )

    admin = User(email="admin@facilerp.pe", nombre="Ana Torres")
    admin.set_password("Admin123!")

    contador = User(email="contador@facilerp.pe", nombre="Jorge Medina")
    contador.set_password("Contador123!")

    vendedor = User(email="ventas@facilerp.pe", nombre="Carla Ruiz")
    vendedor.set_password("Ventas123!")

    db.session.add_all(
        [empresa_principal, empresa_secundaria, admin, contador, vendedor]
    )
    db.session.flush()

    db.session.add_all(
        [
            UserEmpresaRole(
                user_id=admin.id,
                empresa_id=empresa_principal.id,
                rol=ROLE_ADMIN,
            ),
            UserEmpresaRole(
                user_id=admin.id,
                empresa_id=empresa_secundaria.id,
                rol=ROLE_ADMIN,
            ),
            UserEmpresaRole(
                user_id=contador.id,
                empresa_id=empresa_principal.id,
                rol=ROLE_CONTADOR,
            ),
            UserEmpresaRole(
                user_id=vendedor.id,
                empresa_id=empresa_principal.id,
                rol=ROLE_VENDEDOR,
            ),
        ]
    )

    admin.default_empresa_id = empresa_principal.id
    contador.default_empresa_id = empresa_principal.id
    vendedor.default_empresa_id = empresa_principal.id

    db.session.add_all(
        [
            MarcaConfig(
                empresa_id=empresa_principal.id,
                nombre_sistema="ContaFácil SAC",
                color_primary="#0F766E",
                color_secondary="#16324F",
                updated_by=admin.id,
            ),
            MarcaConfig(
                empresa_id=empresa_secundaria.id,
                nombre_sistema="Andes Retail ERP",
                color_primary="#C2410C",
                color_secondary="#3F1D2E",
                updated_by=admin.id,
            ),
        ]
    )

    db.session.flush()

    grupo_finanzas = SecurityGroup(
        empresa_id=empresa_principal.id,
        nombre="Finanzas",
        descripcion="Equipo contable y de tesorería.",
    )
    grupo_comercial = SecurityGroup(
        empresa_id=empresa_principal.id,
        nombre="Comercial",
        descripcion="Equipo comercial con foco en ventas y seguimiento.",
    )
    db.session.add_all([grupo_finanzas, grupo_comercial])
    db.session.flush()
    db.session.add_all(
        [
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_PURCHASES_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_PURCHASES_MANAGE
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_CXC_CXP_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_CXC_CXP_MANAGE
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_ACCOUNTING_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_ACCOUNTING_MANAGE
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_TREASURY_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_TREASURY_MANAGE
            ),
            SecurityGroupPermission(
                group_id=grupo_finanzas.id, permission_code=PERM_REPORTS_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_comercial.id, permission_code=PERM_INVENTORY_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_comercial.id, permission_code=PERM_SALES_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_comercial.id, permission_code=PERM_SALES_MANAGE
            ),
            SecurityGroupPermission(
                group_id=grupo_comercial.id, permission_code=PERM_CXC_CXP_VIEW
            ),
            SecurityGroupPermission(
                group_id=grupo_comercial.id, permission_code=PERM_REPORTS_VIEW
            ),
        ]
    )
    db.session.add_all(
        [
            SecurityUserGroup(
                user_id=contador.id, group_id=grupo_finanzas.id, activo=True
            ),
            SecurityUserGroup(
                user_id=vendedor.id, group_id=grupo_comercial.id, activo=True
            ),
        ]
    )

    ensure_accounting_setup(empresa_principal.id)
    ensure_accounting_setup(empresa_secundaria.id)

    almacen_principal = Almacen(
        empresa_id=empresa_principal.id,
        nombre="Almacén Principal",
        ubicacion="Lima",
    )
    almacen_secundario = Almacen(
        empresa_id=empresa_principal.id,
        nombre="Showroom",
        ubicacion="Miraflores",
    )
    producto_a = Producto(
        empresa_id=empresa_principal.id,
        codigo="LAP-15",
        nombre="Laptop 15 pulgadas",
        categoria="Tecnología",
        unidad_medida="UND",
        tipo="bien",
        precio_venta=Decimal("3200.00"),
        stock_minimo=Decimal("5.00"),
    )
    producto_b = Producto(
        empresa_id=empresa_principal.id,
        codigo="MSE-WL",
        nombre="Mouse inalámbrico",
        categoria="Periféricos",
        unidad_medida="UND",
        tipo="bien",
        precio_venta=Decimal("90.00"),
        stock_minimo=Decimal("10.00"),
    )
    proveedor = Proveedor(
        empresa_id=empresa_principal.id,
        ruc="20601234567",
        razon_social="Distribuidora Lima SAC",
        condicion_pago="credito",
    )
    cliente = Cliente(
        empresa_id=empresa_principal.id,
        documento="20111111111",
        razon_social="Comercial Pacífico SAC",
        condicion_pago="credito",
    )
    db.session.add_all(
        [
            almacen_principal,
            almacen_secundario,
            producto_a,
            producto_b,
            proveedor,
            cliente,
        ]
    )
    db.session.flush()

    cuenta_banco = create_treasury_account(
        empresa_id=empresa_principal.id,
        tipo="banco",
        nombre="BCP Operaciones",
        banco="BCP",
        numero_cuenta="001-123456789-01",
        moneda="PEN",
        cuenta_contable_codigo="1041",
    )
    cuenta_caja = create_treasury_account(
        empresa_id=empresa_principal.id,
        tipo="caja",
        nombre="Caja Principal",
        banco=None,
        numero_cuenta=None,
        moneda="PEN",
        cuenta_contable_codigo="1011",
    )
    _ = cuenta_caja
    register_treasury_movement(
        empresa_id=empresa_principal.id,
        treasury_account=cuenta_banco,
        tipo="ingreso",
        monto=Decimal("5000.00"),
        fecha=date.today(),
        glosa="Saldo inicial demo",
        contra_cuenta_codigo="7599",
    )

    register_stock_movement(
        empresa_id=empresa_principal.id,
        producto=producto_b,
        almacen=almacen_principal,
        tipo="entrada",
        cantidad=Decimal("25.00"),
        costo_unitario=Decimal("45.00"),
    )
    orden = create_purchase_order(
        empresa_id=empresa_principal.id,
        proveedor_id=proveedor.id,
        producto=producto_a,
        cantidad=Decimal("8.00"),
        precio_unitario=Decimal("2100.00"),
        fecha=date.today(),
        observaciones="Primera compra demo",
    )
    recepcion = receive_purchase_order(
        orden=orden,
        almacen=almacen_principal,
        cantidad_recibida=Decimal("3.00"),
        fecha=date.today(),
    )
    venta = create_sales_order(
        empresa_id=empresa_principal.id,
        cliente=cliente,
        producto=producto_b,
        almacen=almacen_principal,
        cantidad=Decimal("2.00"),
        precio_unitario=Decimal("90.00"),
        fecha=date.today(),
        observaciones="Venta demo",
    )
    register_collection(
        empresa_id=empresa_principal.id,
        documento=venta.documentos_cxc[0],
        treasury_account=cuenta_banco,
        monto=Decimal("106.20"),
        fecha=date.today(),
        tipo_pago="transferencia",
    )
    documento_cxp = DocumentoCxP.query.filter_by(recepcion_id=recepcion.id).first()
    register_supplier_payment(
        empresa_id=empresa_principal.id,
        documento=documento_cxp,
        treasury_account=cuenta_banco,
        monto=Decimal("1000.00"),
        fecha=date.today(),
        tipo_pago="transferencia",
    )

    db.session.commit()
