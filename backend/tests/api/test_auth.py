def test_auth_required(client):
    r = client.get("/api/clients")
    assert r.status_code == 401
    assert r.json() == {"detail": "Sign in to continue."}


def test_invalid_token_is_rejected(client):
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_register_login_me(client):
    client.post("/api/auth/register", json={"email": "b@example.com", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "B@example.com", "password": "password123"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "b@example.com"
    bad = client.post("/api/auth/login", json={"email": "b@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401
    assert bad.json() == {"detail": "Email or password is incorrect."}


def test_register_rejects_duplicate_email_case_insensitively(client, auth):
    r = client.post("/api/auth/register", json={"email": "A@Example.com", "password": "password123"})
    assert r.status_code == 409
    assert r.json() == {"detail": "An account with this email already exists. Sign in instead."}


def test_register_validates_input(client):
    assert client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"}).status_code == 422
    r = client.post("/api/auth/register", json={"email": "x@example.com", "password": "password123", "is_admin": True})
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "extra_forbidden"
