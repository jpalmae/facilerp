from __future__ import annotations


def login(client, email: str, password: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_report_exports_work(client):
    login(client, "admin@facilerp.pe", "Admin123!")

    dashboard_response = client.get("/reportes/")
    pdf_response = client.get("/reportes/export/pdf")
    xlsx_response = client.get("/reportes/export/excel")
    ple_response = client.get("/reportes/export/ple")

    assert dashboard_response.status_code == 200
    assert b"Accesos por funci" in dashboard_response.data
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert xlsx_response.status_code == 200
    assert (
        xlsx_response.mimetype
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert ple_response.status_code == 200
    assert ple_response.mimetype == "text/plain"
    assert b"1041|Cuentas corrientes operativas" in ple_response.data
