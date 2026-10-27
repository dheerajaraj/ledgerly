"""Multi-tenancy: other users' rows are invisible (404, not 403)."""


def test_users_cannot_see_each_others_invoices(client, auth, other_auth, make_invoice):
    inv = make_invoice(open_link=True)
    r = client.get(f"/api/invoices/{inv['id']}", headers=other_auth)
    assert r.status_code == 404
    assert client.get("/api/invoices", headers=other_auth).json() == []


def test_users_cannot_act_on_each_others_invoices(client, auth, other_auth, make_invoice):
    inv = make_invoice()
    assert client.post(f"/api/invoices/{inv['id']}/payment-link", headers=other_auth).status_code == 404
    assert client.post(f"/api/invoices/{inv['id']}/void", headers=other_auth).status_code == 404
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "draft"


def test_users_cannot_use_each_others_clients(client, auth, other_auth):
    c = client.post("/api/clients", json={"name": "Mine", "email": "m@x.example"}, headers=auth).json()
    assert client.get("/api/clients", headers=other_auth).json() == []
    assert client.put(f"/api/clients/{c['id']}", json={"name": "Stolen", "email": "s@x.example"}, headers=other_auth).status_code == 404
    r = client.post("/api/invoices", json={"client_id": c["id"], "description": "x", "amount_cents": 100}, headers=other_auth)
    assert r.status_code == 404


def test_users_cannot_touch_each_others_expenses(client, auth, other_auth):
    exp = client.post("/api/expenses", json={"date": "2026-10-01", "description": "Mine", "amount_cents": 100}, headers=auth).json()
    assert client.get("/api/expenses", headers=other_auth).json() == []
    assert client.patch(f"/api/expenses/{exp['id']}", json={"amount_cents": 1}, headers=other_auth).status_code == 404
    assert client.delete(f"/api/expenses/{exp['id']}", headers=other_auth).status_code == 404
    assert client.get("/api/dashboard?month=2026-10", headers=other_auth).json()["summary"]["expenses_cents"] == 0
