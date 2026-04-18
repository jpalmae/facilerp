from __future__ import annotations

from app.models import Empresa


def login(client):
    return client.post(
        "/auth/login",
        data={"email": "admin@facilerp.pe", "password": "Admin123!"},
        follow_redirects=True,
    )


def test_brand_update_changes_name(client, app):
    login(client)

    response = client.post(
        "/configuracion/marca/",
        data={
            "nombre_sistema": "Mi ERP Peru",
            "color_primary": "#123456",
            "color_secondary": "#654321",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Identidad visual actualizada." in response.data

    with app.app_context():
        empresa = Empresa.query.filter_by(ruc="20123456789").first()
        assert empresa is not None
        assert empresa.brand.nombre_sistema == "Mi ERP Peru"
        assert empresa.brand.color_primary == "#123456"


def test_brand_reset_restores_defaults(client, app):
    login(client)
    client.post(
        "/configuracion/marca/",
        data={
            "nombre_sistema": "Temporal",
            "color_primary": "#123456",
            "color_secondary": "#654321",
        },
        follow_redirects=True,
    )

    response = client.post("/configuracion/marca/reset", follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        empresa = Empresa.query.filter_by(ruc="20123456789").first()
        assert empresa is not None
        assert empresa.brand.nombre_sistema == "FacilERP"
        assert empresa.brand.color_primary == "#2563EB"
