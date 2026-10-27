from fastapi.testclient import TestClient

from app.main import app
from app.services import factory


def test_health(client, stripe, claude):
    assert client.get("/api/health").json() == {"ok": True, "stripe_configured": True, "claude_configured": False}


def test_every_response_has_a_request_id(client):
    first = client.get("/api/health").headers["X-Request-ID"]
    second = client.get("/api/auth/me").headers["X-Request-ID"]  # error responses too
    assert first and second and first != second


def test_valid_incoming_request_id_is_reused_and_invalid_one_replaced(client):
    assert client.get("/api/health", headers={"X-Request-ID": "proxy-abc.123"}).headers["X-Request-ID"] == "proxy-abc.123"
    replaced = client.get("/api/health", headers={"X-Request-ID": "bad id\n"}).headers["X-Request-ID"]
    assert replaced != "bad id\n" and len(replaced) == 32


def test_unhandled_errors_return_json_without_internals(auth, monkeypatch):
    def broken(db):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(factory, "build_client_service", broken)
    r = TestClient(app, raise_server_exceptions=False).get("/api/clients", headers=auth)
    assert r.status_code == 500
    assert r.json() == {"detail": "Something went wrong. Please try again."}
    assert "secret" not in r.text


def test_cors_allows_frontend_origin(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
