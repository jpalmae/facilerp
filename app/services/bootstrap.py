from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.constants import MOV_ENTRADA
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


# ── Phase 1: Companies & branding ────────────────────────────────────────


def _ensure_empresas() -> dict[str, Empresa]:
    """Create demo companies. Returns dict keyed by RUC."""
    existing: dict[str, Empresa] = {
        e.ruc: e for e in Empresa.query.filter(
            Empresa.ruc.in_(["20123456789", "20567891234"])
        ).all()
    }
    if "20123456789" not in existing:
        existing["20123456789"] = Empresa(
            ruc="20123456789",
            razon_social="ContaFácil SAC",
            moneda="PEN",
            regimen_tributario="Régimen General",
        )
        db.session.add(existing["20123456789"])

    if "20567891234" not in existing:
        existing["20567891234"] = Empresa(
            ruc="20567891234",
            razon_social="Andes Retail EIRL",
            moneda="PEN",
            regimen_tributario="MYPE Tributario",
        )
        db.session.add(existing["20567891234"])

    db.session.flush()
    return existing


def _ensure_marca(empresas: dict[str, Empresa]) -> None:
    """Create brand configs for demo companies."""
    admin = User.query.filter_by(email="admin@facilerp.pe").first()
    updated_by = admin.id if admin else None

    configs = [
        ("20123456789", "ContaFácil SAC", "#0F766E", "#16324F"),
        ("20567891234", "Andes Retail ERP", "#C2410C", "#3F1D2E"),
    ]
    for ruc, nombre, primary, secondary in configs:
        empresa = empresas.get(ruc)
        if empresa is None:
            continue
        exists = MarcaConfig.query.filter_by(empresa_id=empresa.id).first()
        if exists is None:
            db.session.add(
                MarcaConfig(
                    empresa_id=empresa.id,
                    nombre_sistema=nombre,
                    color_primary=primary,
                    color_secondary=secondary,
                    updated_by=updated_by,
                )
            )
    db.session.flush()


# ── Phase 2: Users & roles ───────────────────────────────────────────────


def _ensure_users() -> dict[str, User]:
    """Create demo users. Returns dict keyed by email."""
    emails = ["admin@facilerp.pe", "contador@facilerp.pe", "ventas@facilerp.pe"]
    existing: dict[str, User] = {
        u.email: u for u in User.query.filter(User.email.in_(emails)).all()
    }

    specs = [
        ("admin@facilerp.pe", "Ana Torres", "Admin123!"),
        ("contador@facilerp.pe", "Jorge Medina", "Contador123!"),
        ("ventas@facilerp.pe", "Carla Ruiz", "Ventas123!"),
    ]
    for email, nombre, password in specs:
        if email not in existing:
            user = User(email=email, nombre=nombre)
            user.set_password(password)
            db.session.add(user)
            existing[email] = user

    db.session.flush()
    return existing


def _ensure_user_roles(
    users: dict[str, User], empresas: dict[str, Empresa]
) -> None:
    """Assign roles to demo users in demo companies."""
    principal = empresas.get("20123456789")
    secundaria = empresas.get("20567891234")
    if principal is None:
        return

    specs = [
        ("admin@facilerp.pe", principal.id, ROLE_ADMIN),
        ("admin@facilerp.pe", secundaria.id, ROLE_ADMIN) if secundaria else None,
        ("contador@facilerp.pe", principal.id, ROLE_CONTADOR),
        ("ventas@facilerp.pe", principal.id, ROLE_VENDEDOR),
    ]

    for spec in specs:
        if spec is None:
            continue
        email, empresa_id, rol = spec
        user = users.get(email)
        if user is None:
            continue
        exists = UserEmpresaRole.query.filter_by(
            user_id=user.id, empresa_id=empresa_id, rol=rol
        ).first()
        if exists is None:
            db.session.add(
                UserEmpresaRole(user_id=user.id, empresa_id=empresa_id, rol=rol)
            )
        # Set default empresa
        if user.default_empresa_id is None:
            user.default_empresa_id = principal.id

    db.session.flush()


# ── Phase 3: Security groups ─────────────────────────────────────────────


def _ensure_security_groups(empresas: dict[str, Empresa], users: dict[str, User]) -> None:
    """Create security groups with permissions and assign users."""
    principal = empresas.get("20123456789")
    if principal is None:
        return

    # Groups
    groups_spec = {
        "Finanzas": "Equipo contable y de tesorería.",
        "Comercial": "Equipo comercial con foco en ventas y seguimiento.",
    }
    groups: dict[str, SecurityGroup] = {}
    for nombre, descripcion in groups_spec.items():
        group = SecurityGroup.query.filter_by(
            empresa_id=principal.id, nombre=nombre
        ).first()
        if group is None:
            group = SecurityGroup(
                empresa_id=principal.id,
                nombre=nombre,
                descripcion=descripcion,
            )
            db.session.add(group)
            db.session.flush()
        groups[nombre] = group

    # Permissions per group
    perm_map = {
        "Finanzas": [
            PERM_PURCHASES_VIEW, PERM_PURCHASES_MANAGE,
            PERM_CXC_CXP_VIEW, PERM_CXC_CXP_MANAGE,
            PERM_ACCOUNTING_VIEW, PERM_ACCOUNTING_MANAGE,
            PERM_TREASURY_VIEW, PERM_TREASURY_MANAGE,
            PERM_REPORTS_VIEW,
        ],
        "Comercial": [
            PERM_INVENTORY_VIEW,
            PERM_SALES_VIEW, PERM_SALES_MANAGE,
            PERM_CXC_CXP_VIEW,
            PERM_REPORTS_VIEW,
        ],
    }
    for nombre, codes in perm_map.items():
        group = groups[nombre]
        for code in codes:
            exists = SecurityGroupPermission.query.filter_by(
                group_id=group.id, permission_code=code
            ).first()
            if exists is None:
                db.session.add(
                    SecurityGroupPermission(group_id=group.id, permission_code=code)
                )

    # User assignments
    assignments = [
        ("contador@facilerp.pe", "Finanzas"),
        ("ventas@facilerp.pe", "Comercial"),
    ]
    for email, group_name in assignments:
        user = users.get(email)
        group = groups.get(group_name)
        if user is None or group is None:
            continue
        exists = SecurityUserGroup.query.filter_by(
            user_id=user.id, group_id=group.id
        ).first()
        if exists is None:
            db.session.add(
                SecurityUserGroup(user_id=user.id, group_id=group.id, activo=True)
            )
        else:
            exists.activo = True

    db.session.flush()


# ── Phase 4: Accounting setup ────────────────────────────────────────────


def _ensure_accounting(empresas: dict[str, Empresa]) -> None:
    """Ensure accounting plan is set up for all demo companies."""
    for empresa in empresas.values():
        ensure_accounting_setup(empresa.id)


# ── Phase 5: Master data (warehouses, products, contacts) ────────────────


def _ensure_master_data(
    empresas: dict[str, Empresa]
) -> dict[str, object]:
    """Create warehouses, products, supplier, and customer.
    Returns a dict with created entities."""
    principal = empresas.get("20123456789")
    if principal is None:
        return {}

    result: dict[str, object] = {}

    # Warehouses
    for nombre, ubicacion in [("Almacén Principal", "Lima"), ("Showroom", "Miraflores")]:
        wh = Almacen.query.filter_by(
            empresa_id=principal.id, nombre=nombre
        ).first()
        if wh is None:
            wh = Almacen(empresa_id=principal.id, nombre=nombre, ubicacion=ubicacion)
            db.session.add(wh)
        result[nombre] = wh

    # Products
    products_spec = [
        ("LAP-15", "Laptop 15 pulgadas", "Tecnología", Decimal("3200.00"), Decimal("5.00")),
        ("MSE-WL", "Mouse inalámbrico", "Periféricos", Decimal("90.00"), Decimal("10.00")),
    ]
    for codigo, nombre, cat, precio, stock_min in products_spec:
        prod = Producto.query.filter_by(
            empresa_id=principal.id, codigo=codigo
        ).first()
        if prod is None:
            prod = Producto(
                empresa_id=principal.id,
                codigo=codigo,
                nombre=nombre,
                categoria=cat,
                unidad_medida="UND",
                tipo="bien",
                precio_venta=precio,
                stock_minimo=stock_min,
            )
            db.session.add(prod)
        result[codigo] = prod

    # Supplier
    prov = Proveedor.query.filter_by(
        empresa_id=principal.id, ruc="20601234567"
    ).first()
    if prov is None:
        prov = Proveedor(
            empresa_id=principal.id,
            ruc="20601234567",
            razon_social="Distribuidora Lima SAC",
            condicion_pago="credito",
        )
        db.session.add(prov)
    result["proveedor"] = prov

    # Customer
    cli = Cliente.query.filter_by(
        empresa_id=principal.id, documento="20111111111"
    ).first()
    if cli is None:
        cli = Cliente(
            empresa_id=principal.id,
            documento="20111111111",
            razon_social="Comercial Pacífico SAC",
            condicion_pago="credito",
        )
        db.session.add(cli)
    result["cliente"] = cli

    db.session.flush()
    return result


# ── Phase 6: Treasury accounts ───────────────────────────────────────────


def _ensure_treasury(empresas: dict[str, Empresa]) -> dict[str, object]:
    """Create demo treasury accounts and seed with initial balance."""
    principal = empresas.get("20123456789")
    if principal is None:
        return {}

    from app.models import CuentaTesoreria

    result: dict[str, object] = {}

    # Bank account
    cuenta_banco = CuentaTesoreria.query.filter_by(
        empresa_id=principal.id, nombre="BCP Operaciones"
    ).first()
    if cuenta_banco is None:
        cuenta_banco = create_treasury_account(
            empresa_id=principal.id,
            tipo="banco",
            nombre="BCP Operaciones",
            banco="BCP",
            numero_cuenta="001-123456789-01",
            moneda="PEN",
            cuenta_contable_codigo="1041",
        )
    result["banco"] = cuenta_banco

    # Cash account
    cuenta_caja = CuentaTesoreria.query.filter_by(
        empresa_id=principal.id, nombre="Caja Principal"
    ).first()
    if cuenta_caja is None:
        cuenta_caja = create_treasury_account(
            empresa_id=principal.id,
            tipo="caja",
            nombre="Caja Principal",
            banco=None,
            numero_cuenta=None,
            moneda="PEN",
            cuenta_contable_codigo="1011",
        )
    result["caja"] = cuenta_caja

    # Seed initial balance if account is at zero
    if cuenta_banco.saldo_actual == 0:
        register_treasury_movement(
            empresa_id=principal.id,
            treasury_account=cuenta_banco,
            tipo="ingreso",
            monto=Decimal("5000.00"),
            fecha=date.today(),
            glosa="Saldo inicial demo",
            contra_cuenta_codigo="7599",
        )

    return result


# ── Phase 7: Sample transactions ─────────────────────────────────────────


def _ensure_sample_transactions(
    empresas: dict[str, Empresa],
    master: dict[str, object],
    treasury: dict[str, object],
) -> None:
    """Create sample purchase, sale, and payment transactions."""
    principal = empresas.get("20123456789")
    if principal is None:
        return

    almacen = master.get("Almacén Principal")
    producto_a = master.get("LAP-15")
    producto_b = master.get("MSE-WL")
    proveedor = master.get("proveedor")
    cliente = master.get("cliente")
    cuenta_banco = treasury.get("banco")

    if not all([almacen, producto_a, producto_b, proveedor, cliente, cuenta_banco]):
        return

    # Check if sample transactions already exist (by observation text)
    from app.models import MovimientoStock

    existing = MovimientoStock.query.filter_by(
        empresa_id=principal.id, referencia_tipo="orden_compra"
    ).first()
    if existing is not None:
        return  # Transactions already seeded

    # Initial stock entry
    register_stock_movement(
        empresa_id=principal.id,
        producto=producto_b,
        almacen=almacen,
        tipo=MOV_ENTRADA,
        cantidad=Decimal("25.00"),
        costo_unitario=Decimal("45.00"),
    )

    # Purchase order
    orden = create_purchase_order(
        empresa_id=principal.id,
        proveedor_id=proveedor.id,
        producto=producto_a,
        cantidad=Decimal("8.00"),
        precio_unitario=Decimal("2100.00"),
        fecha=date.today(),
        observaciones="Primera compra demo",
    )
    recepcion = receive_purchase_order(
        orden=orden,
        almacen=almacen,
        cantidad_recibida=Decimal("3.00"),
        fecha=date.today(),
    )

    # Sales order
    venta = create_sales_order(
        empresa_id=principal.id,
        cliente=cliente,
        producto=producto_b,
        almacen=almacen,
        cantidad=Decimal("2.00"),
        precio_unitario=Decimal("90.00"),
        fecha=date.today(),
        observaciones="Venta demo",
    )

    # Collection
    register_collection(
        empresa_id=principal.id,
        documento=venta.documentos_cxc[0],
        treasury_account=cuenta_banco,
        monto=Decimal("106.20"),
        fecha=date.today(),
        tipo_pago="transferencia",
    )

    # Supplier payment
    documento_cxp = DocumentoCxP.query.filter_by(recepcion_id=recepcion.id).first()
    register_supplier_payment(
        empresa_id=principal.id,
        documento=documento_cxp,
        treasury_account=cuenta_banco,
        monto=Decimal("1000.00"),
        fecha=date.today(),
        tipo_pago="transferencia",
    )


# ── Public API ───────────────────────────────────────────────────────────


def ensure_security_demo_data() -> None:
    """Ensure security groups exist for the main demo company (idempotent)."""
    empresa_principal = Empresa.query.filter_by(ruc="20123456789").first()
    if empresa_principal is None:
        return

    users = _ensure_users()
    _ensure_security_groups({"20123456789": empresa_principal}, users)


def ensure_demo_data() -> None:
    """Seed the database with demo data (fully idempotent)."""
    empresas = _ensure_empresas()
    users = _ensure_users()
    _ensure_marca(empresas)
    _ensure_user_roles(users, empresas)
    _ensure_security_groups(empresas, users)
    _ensure_accounting(empresas)
    master = _ensure_master_data(empresas)
    treasury = _ensure_treasury(empresas)
    _ensure_sample_transactions(empresas, master, treasury)

    db.session.commit()
