def test_create_list_and_update_clients(client, auth):
    r = client.post("/api/clients", json={"name": "  Zeta  ", "email": "AP@Zeta.example"}, headers=auth)
    assert r.status_code == 201
    assert (r.json()["name"], r.json()["email"]) == ("Zeta", "ap@zeta.example")
    client.post("/api/clients", json={"name": "Alpha", "email": "a@alpha.example"}, headers=auth)

    assert [c["name"] for c in client.get("/api/clients", headers=auth).json()] == ["Alpha", "Zeta"]

    updated = client.put(f"/api/clients/{r.json()['id']}", json={"name": "Zeta Ltd", "email": "ap@zeta.example"}, headers=auth)
    assert updated.status_code == 200 and updated.json()["name"] == "Zeta Ltd"


def test_update_missing_client_is_404(client, auth):
    r = client.put("/api/clients/99999", json={"name": "X", "email": "x@x.example"}, headers=auth)
    assert r.status_code == 404
    assert r.json() == {"detail": "Client not found."}
