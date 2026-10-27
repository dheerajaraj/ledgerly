def test_dashboard_shape_and_query_validation(client, auth):
    r = client.get("/api/dashboard?month=2026-10&months=3", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == "2026-10"
    assert [p["month"] for p in body["series"]] == ["2026-08", "2026-09", "2026-10"]
    assert body["outstanding"] == {"open_count": 0, "open_cents": 0, "overdue_count": 0, "overdue_cents": 0}
    assert set(body) == {"month", "summary", "series", "expenses_by_category", "income_by_client", "outstanding"}

    assert client.get("/api/dashboard?month=2026-1", headers=auth).status_code == 422
    assert client.get("/api/dashboard?months=25", headers=auth).status_code == 422


def test_dashboard_counts_expenses(client, auth):
    client.post("/api/expenses", json={"date": "2026-10-03", "description": "Figma", "amount_cents": 1500}, headers=auth)
    body = client.get("/api/dashboard?month=2026-10", headers=auth).json()
    assert body["summary"]["expenses_cents"] == 1500 and body["summary"]["profit_cents"] == -1500
    assert body["expenses_by_category"] == [{"category": "Software", "amount_cents": 1500}]
