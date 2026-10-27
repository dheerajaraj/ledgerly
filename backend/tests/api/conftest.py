import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import factory
from tests.helpers import FakeClaude, FakeStripe, sign


@pytest.fixture(autouse=True)
def _fresh_db(fresh_db):
    yield


@pytest.fixture(autouse=True)
def stripe(monkeypatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(factory, "stripe_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def claude(monkeypatch) -> FakeClaude:
    """Disabled by default, like the test env (no ANTHROPIC_API_KEY). Set .enabled and .replies to use it."""
    fake = FakeClaude(enabled=False)
    monkeypatch.setattr(factory, "claude_client", lambda: fake)
    return fake


@pytest.fixture
def client():
    return TestClient(app)


def register(client, email: str) -> dict:
    r = client.post("/api/auth/register", json={"email": email, "password": "password123", "name": "A"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register(client, "a@example.com")


@pytest.fixture
def other_auth(client):
    return register(client, "z@example.com")


@pytest.fixture
def make_invoice(client, auth):
    def _make(amount_cents=150_000, headers=None, open_link=False) -> dict:
        headers = headers or auth
        c = client.post("/api/clients", json={"name": "Northwind", "email": "pay@northwind.example"}, headers=headers).json()
        inv = client.post("/api/invoices", json={"client_id": c["id"], "description": "Website", "amount_cents": amount_cents}, headers=headers)
        assert inv.status_code == 201, inv.text
        if not open_link:
            return inv.json()
        r = client.post(f"/api/invoices/{inv.json()['id']}/payment-link", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "open"
        return r.json()

    return _make


@pytest.fixture
def post_webhook(client):
    def _post(payload: str, secret: str | None = None):
        signature = sign(payload) if secret is None else sign(payload, secret)
        return client.post("/api/webhooks/stripe", content=payload, headers={"Stripe-Signature": signature})

    return _post
