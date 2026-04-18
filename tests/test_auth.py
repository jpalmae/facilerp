from __future__ import annotations


def login(client, email: str, password: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_admin_login_shows_dashboard(client):
    response = login(client, "admin@facilerp.pe", "Admin123!")

    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Accesos directos" in response.data


def test_vendedor_cannot_access_brand_settings(client):
    login(client, "ventas@facilerp.pe", "Ventas123!")

    response = client.get("/configuracion/marca/")

    assert response.status_code == 403


def test_inventory_placeholder_redirects_to_real_module(client):
    login(client, "admin@facilerp.pe", "Admin123!")

    response = client.get("/modulos/inventario", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/inventario/")


def test_authenticated_layout_exposes_sidebar_toggle(client):
    response = login(client, "admin@facilerp.pe", "Admin123!")

    assert response.status_code == 200
    assert b"data-sidebar-toggle" in response.data
    assert b"app.js" in response.data


def test_dashboard_hides_delivery_language(client):
    response = login(client, "admin@facilerp.pe", "Admin123!")

    assert response.status_code == 200
    assert b"Fase" not in response.data
    assert b"Roadmap" not in response.data
    assert b"base product" not in response.data


def test_login_hides_demo_implementation_language(client):
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert b"Rol demo" not in response.data
    assert b"Credenciales demo" not in response.data
    assert b"white-label" not in response.data


def test_logout_invalidates_session_and_disables_cache(client):
    response = login(client, "admin@facilerp.pe", "Admin123!")

    assert response.status_code == 200
    assert response.headers["Cache-Control"].startswith("no-store")

    logout_response = client.post("/auth/logout", follow_redirects=True)

    assert logout_response.status_code == 200
    assert b"Sesi\xc3\xb3n cerrada." in logout_response.data
    assert b"Accede a tu espacio de trabajo" in logout_response.data

    protected = client.get("/dashboard", follow_redirects=False)

    assert protected.status_code == 302
    assert protected.headers["Location"].startswith("/auth/login")
