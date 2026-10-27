from datetime import date


def test_expense_fallback_categorization_and_csv(client, auth):
    r = client.post("/api/expenses", json={"date": date.today().isoformat(), "description": "Figma subscription", "amount_cents": 1500}, headers=auth)
    assert r.json()["category"] == "Software"
    assert r.json()["category_source"] == "rule"  # no API key in tests

    csv_text = "Date,Description,Amount\n2026-10-02,Grab ride to client,-18.50\n2026-10-03,Lunch meeting,$42.00\nbad,row,x\n"
    r = client.post("/api/expenses/import-csv", files={"file": ("bank.csv", csv_text, "text/csv")}, headers=auth)
    body = r.json()
    assert body["imported"] == 2 and body["skipped_rows"] == [4]
    assert {e["category"] for e in body["expenses"]} == {"Travel", "Meals"}
    assert body["expenses"][0]["amount_cents"] == 1850


def test_csv_amounts_are_parsed_exactly(client, auth):
    """Regression: amounts went through float, so '1.005' became 100 cents instead of 101."""
    csv_text = 'date,description,amount\n2026-10-01,Fee,1.005\n2026-10-01,Laptop,"$1,042.00"\n2026-10-01,Refund,(12.34)\n'
    body = client.post("/api/expenses/import-csv", files={"file": ("b.csv", csv_text, "text/csv")}, headers=auth).json()
    assert [e["amount_cents"] for e in body["expenses"]] == [101, 104_200, 1234]


def test_csv_errors(client, auth):
    def upload(text):
        return client.post("/api/expenses/import-csv", files={"file": ("b.csv", text, "text/csv")}, headers=auth)

    assert upload("").json() == {"detail": "The file is empty."}
    missing = upload("Date,Amount\n2026-10-01,1\n")
    assert missing.status_code == 400
    assert missing.json() == {"detail": "The CSV needs these columns: date, description, amount. Missing: description."}
    too_many = upload("date,description,amount\n" + "2026-10-01,Thing,1\n" * 501)
    assert too_many.json() == {"detail": "Import up to 500 rows at a time."}


def test_manual_category_and_update(client, auth):
    exp = client.post("/api/expenses", json={"date": "2026-10-01", "description": "Uber", "amount_cents": 2500, "category": "Office"}, headers=auth).json()
    assert (exp["category"], exp["category_source"]) == ("Office", "manual")

    r = client.patch(f"/api/expenses/{exp['id']}", json={"category": "Travel", "amount_cents": 2600}, headers=auth)
    assert r.status_code == 200
    assert (r.json()["category"], r.json()["amount_cents"], r.json()["category_source"]) == ("Travel", 2600, "manual")


def test_update_rejects_nulls_and_bad_descriptions(client, auth):
    """Regression: {"category": null} used to 500, and descriptions had no length limits on update."""
    exp = client.post("/api/expenses", json={"date": "2026-10-01", "description": "Uber", "amount_cents": 2500}, headers=auth).json()
    for body in ({"category": None}, {"date": None}, {"description": ""}, {"description": "x" * 256}):
        assert client.patch(f"/api/expenses/{exp['id']}", json=body, headers=auth).status_code == 422, body


def test_list_filters_by_month_and_validates_it(client, auth):
    for on in ("2026-09-30", "2026-10-01", "2026-10-31"):
        client.post("/api/expenses", json={"date": on, "description": "Thing", "amount_cents": 100}, headers=auth)
    october = client.get("/api/expenses?month=2026-10", headers=auth).json()
    assert [e["date"] for e in october] == ["2026-10-31", "2026-10-01"]
    assert client.get("/api/expenses?month=2026-1", headers=auth).status_code == 422


def test_delete_expense(client, auth):
    exp = client.post("/api/expenses", json={"date": "2026-10-01", "description": "Thing", "amount_cents": 100}, headers=auth).json()
    assert client.delete(f"/api/expenses/{exp['id']}", headers=auth).status_code == 204
    again = client.delete(f"/api/expenses/{exp['id']}", headers=auth)
    assert again.status_code == 404 and again.json() == {"detail": "Expense not found."}


def test_categories_endpoint(client, auth):
    categories = client.get("/api/expenses/categories", headers=auth).json()
    assert categories[0] == "Software" and categories[-1] == "Other"
