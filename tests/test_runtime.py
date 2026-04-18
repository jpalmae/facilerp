from __future__ import annotations


def test_health_and_ready_endpoints(client):
    health_response = client.get("/healthz")
    ready_response = client.get("/readyz")

    assert health_response.status_code == 200
    assert health_response.json["status"] == "ok"
    assert ready_response.status_code == 200
    assert ready_response.json["status"] == "ready"


def test_security_headers_are_present(client):
    response = client.get("/healthz")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["X-Request-ID"]
    assert "Content-Security-Policy" in response.headers
