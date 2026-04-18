from __future__ import annotations

from datetime import date, timedelta

from app.models import (
    Almacen,
    AuditLog,
    Cliente,
    Empresa,
    PERM_SALES_MANAGE,
    Producto,
    SecurityGroup,
    User,
    UserEmpresaRole,
)


def login(client, email: str, password: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_only_admin_can_access_security_dashboard(client):
    login(client, "contador@facilerp.pe", "Contador123!")

    forbidden = client.get("/seguridad/")
    assert forbidden.status_code == 403

    client.post("/auth/logout", follow_redirects=True)
    login(client, "admin@facilerp.pe", "Admin123!")
    allowed = client.get("/seguridad/")
    assert allowed.status_code == 200
    assert b"Seguridad" in allowed.data


def test_group_permissions_extend_user_capabilities(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    create_group = client.post(
        "/seguridad/",
        data={
            "group-nombre": "Supervisores de venta",
            "group-descripcion": "Permisos extra para ventas.",
            "group-permisos": ["sales.view", "sales.manage"],
            "group-submit": "1",
        },
        follow_redirects=True,
    )
    assert create_group.status_code == 200
    assert b"Grupo guardado." in create_group.data

    create_user = client.post(
        "/seguridad/",
        data={
            "user-nombre": "Luis Supervisor",
            "user-email": "supervisor@facilerp.pe",
            "user-password": "Supervisor123!",
            "user-rol": "lectura",
            "user-submit": "1",
        },
        follow_redirects=True,
    )
    assert create_user.status_code == 200
    assert b"Usuario guardado" in create_user.data

    with app.app_context():
        empresa = Empresa.query.filter_by(ruc="20123456789").first()
        user = User.query.filter_by(email="supervisor@facilerp.pe").first()
        group = SecurityGroup.query.filter_by(nombre="Supervisores de venta").first()
        cliente = Cliente.query.filter_by(documento="20111111111").first()
        almacen = Almacen.query.order_by(Almacen.id.asc()).first()
        producto = Producto.query.filter_by(codigo="MSE-WL").first()

        assert empresa is not None
        assert user is not None
        assert group is not None
        assert cliente is not None
        assert producto is not None
        assert almacen is not None

        user_id = user.id
        group_id = group.id
        cliente_id = cliente.id
        producto_id = producto.id
        almacen_id = almacen.id

    assign_group = client.post(
        f"/seguridad/usuarios/{user_id}/grupos",
        data={"group_ids": [str(group_id)]},
        follow_redirects=True,
    )
    assert assign_group.status_code == 200
    assert b"Grupos actualizados." in assign_group.data

    with app.app_context():
        user = User.query.filter_by(email="supervisor@facilerp.pe").first()
        empresa = Empresa.query.filter_by(ruc="20123456789").first()
        assert user is not None
        assert empresa is not None
        assert user.has_permission(PERM_SALES_MANAGE, empresa.id)

    client.post("/auth/logout", follow_redirects=True)
    login(client, "supervisor@facilerp.pe", "Supervisor123!")

    response = client.post(
        "/ventas/facturacion",
        data={
            "sale-cliente_id": cliente_id,
            "sale-producto_id": producto_id,
            "sale-almacen_id": almacen_id,
            "sale-fecha": "2026-03-23",
            "sale-cantidad": "1",
            "sale-precio_unitario": "90",
            "sale-observaciones": "Venta con permiso por grupo",
            "sale-submit": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"CxC generada" in response.data


def test_company_management_creates_company_and_persists_default_selection(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    workspace = client.get("/seguridad/empresas")
    assert workspace.status_code == 200
    assert b"Portafolio multiempresa" in workspace.data

    create_company = client.post(
        "/seguridad/empresas",
        data={
            "company-ruc": "20999888777",
            "company-razon_social": "Pacific Edge SAC",
            "company-moneda": "USD",
            "company-regimen_tributario": "Régimen General",
            "company-submit": "1",
        },
        follow_redirects=True,
    )
    assert create_company.status_code == 200
    assert b"Empresa creada y vinculada" in create_company.data

    with app.app_context():
        company = Empresa.query.filter_by(ruc="20999888777").first()
        admin = User.query.filter_by(email="admin@facilerp.pe").first()
        membership = (
            UserEmpresaRole.query.filter_by(user_id=admin.id, empresa_id=company.id).first()
            if admin and company
            else None
        )
        assert company is not None
        assert admin is not None
        assert membership is not None
        assert membership.rol == "admin"
        company_id = company.id

    set_default = client.post(
        f"/seguridad/empresas/{company_id}/predeterminada",
        follow_redirects=True,
    )
    assert set_default.status_code == 200
    assert b"Empresa predeterminada actualizada." in set_default.data

    client.post("/auth/logout", follow_redirects=True)
    login(client, "admin@facilerp.pe", "Admin123!")
    with client.session_transaction() as session_state:
        assert session_state["active_empresa_id"] == company_id


def test_user_expiration_blocks_future_login(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    with app.app_context():
        empresa = Empresa.query.filter_by(ruc="20123456789").first()
        membership = (
            UserEmpresaRole.query.join(User)
            .filter(
                User.email == "contador@facilerp.pe",
                UserEmpresaRole.empresa_id == empresa.id,
            )
            .first()
        )
        assert empresa is not None
        assert membership is not None
        user_id = membership.user_id

    expired_on = (date.today() - timedelta(days=1)).isoformat()
    update = client.post(
        f"/seguridad/usuarios/{user_id}/expiracion",
        data={"expires_at": expired_on},
        follow_redirects=True,
    )
    assert update.status_code == 200
    assert b"Vencimiento del acceso actualizado." in update.data

    with app.app_context():
        membership = (
            UserEmpresaRole.query.join(User)
            .filter(
                User.email == "contador@facilerp.pe",
                UserEmpresaRole.empresa_id == empresa.id,
            )
            .first()
        )
        assert membership is not None
        assert not membership.is_currently_active()

    client.post("/auth/logout", follow_redirects=True)
    denied_login = login(client, "contador@facilerp.pe", "Contador123!")

    assert denied_login.status_code == 200
    assert b"inactivo o vencido" in denied_login.data


def test_warehouse_scope_limits_sales_operations_and_stores_audit_detail(client, app):
    login(client, "admin@facilerp.pe", "Admin123!")

    create_group = client.post(
        "/seguridad/",
        data={
            "group-nombre": "Ventas por almacen",
            "group-descripcion": "Ventas con alcance restringido.",
            "group-permisos": ["sales.view", "sales.manage"],
            "group-submit": "1",
        },
        follow_redirects=True,
    )
    assert create_group.status_code == 200

    create_user = client.post(
        "/seguridad/",
        data={
            "user-nombre": "Paula Bodega",
            "user-email": "bodega@facilerp.pe",
            "user-password": "Bodega123!",
            "user-rol": "lectura",
            "user-submit": "1",
        },
        follow_redirects=True,
    )
    assert create_user.status_code == 200

    create_warehouse = client.post(
        "/inventario/",
        data={
            "warehouse-nombre": "Almacen Secundario",
            "warehouse-ubicacion": "Sucursal norte",
            "warehouse-submit": "1",
        },
        follow_redirects=True,
    )
    assert create_warehouse.status_code == 200
    assert b"Almac" in create_warehouse.data

    with app.app_context():
        empresa = Empresa.query.filter_by(ruc="20123456789").first()
        user = User.query.filter_by(email="bodega@facilerp.pe").first()
        group = SecurityGroup.query.filter_by(nombre="Ventas por almacen").first()
        cliente = Cliente.query.filter_by(documento="20111111111").first()
        producto = Producto.query.filter_by(codigo="MSE-WL").first()
        almacen_principal = Almacen.query.order_by(Almacen.id.asc()).first()
        almacen_secundario = Almacen.query.filter_by(nombre="Almacen Secundario").first()

        assert empresa is not None
        assert user is not None
        assert group is not None
        assert cliente is not None
        assert producto is not None
        assert almacen_principal is not None
        assert almacen_secundario is not None

        user_id = user.id
        group_id = group.id
        cliente_id = cliente.id
        producto_id = producto.id
        almacen_principal_id = almacen_principal.id
        almacen_secundario_id = almacen_secundario.id

    assign_group = client.post(
        f"/seguridad/usuarios/{user_id}/grupos",
        data={"group_ids": [str(group_id)]},
        follow_redirects=True,
    )
    assert assign_group.status_code == 200

    restrict_warehouses = client.post(
        f"/seguridad/usuarios/{user_id}/almacenes",
        data={"almacen_ids": [str(almacen_principal_id)]},
        follow_redirects=True,
    )
    assert restrict_warehouses.status_code == 200
    assert b"Alcance por almac" in restrict_warehouses.data

    with app.app_context():
        user = User.query.filter_by(email="bodega@facilerp.pe").first()
        audit = (
            AuditLog.query.filter_by(accion="seguridad.usuario.warehouses_updated")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert user is not None
        assert empresa is not None
        assert user.allowed_warehouse_ids(empresa.id) == {almacen_principal_id}
        assert audit is not None
        assert audit.detalle is not None
        assert "bodega@facilerp.pe" in audit.detalle

    client.post("/auth/logout", follow_redirects=True)
    login(client, "bodega@facilerp.pe", "Bodega123!")

    sales_page = client.get("/ventas/facturacion")
    assert sales_page.status_code == 200
    assert b"Facturaci" in sales_page.data

    allowed_sale = client.post(
        "/ventas/facturacion",
        data={
            "sale-cliente_id": cliente_id,
            "sale-producto_id": producto_id,
            "sale-almacen_id": almacen_principal_id,
            "sale-fecha": "2026-03-23",
            "sale-cantidad": "1",
            "sale-precio_unitario": "95",
            "sale-observaciones": "Venta restringida al almacen principal",
            "sale-submit": "1",
        },
        follow_redirects=True,
    )
    assert allowed_sale.status_code == 200
    assert b"CxC generada" in allowed_sale.data

    denied_sale = client.post(
        "/ventas/facturacion",
        data={
            "sale-cliente_id": cliente_id,
            "sale-producto_id": producto_id,
            "sale-almacen_id": almacen_secundario_id,
            "sale-fecha": "2026-03-23",
            "sale-cantidad": "1",
            "sale-precio_unitario": "95",
            "sale-observaciones": "Debe fallar por almacen fuera de alcance",
            "sale-submit": "1",
        },
    )
    assert denied_sale.status_code == 403
