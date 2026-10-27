from datetime import date

import pytest

from app.repository.models import CategorySource, Expense
from app.schema.expense import ExpenseCreate, ExpenseUpdate
from app.services.exceptions import BadInputError, NotFoundError
from app.services.expense_service import ExpenseService
from tests.helpers import FakeSession
from tests.unit.services.fakes import FakeExpenses

USER, OTHER = 1, 2


class FakeCategorizer:
    def __init__(self):
        self.calls: list[list[str]] = []

    def categorize(self, descriptions):
        self.calls.append(descriptions)
        return [("Travel", CategorySource.AI) for _ in descriptions]


@pytest.fixture
def svc():
    return ExpenseService(FakeSession(), FakeExpenses(), FakeCategorizer())


def test_create_with_manual_category_skips_categorizer(svc):
    expense = svc.create(USER, ExpenseCreate(date=date(2026, 10, 1), description="Desk", amount_cents=100, category="Office"))
    assert (expense.category, expense.category_source) == ("Office", "manual")
    assert svc.categorizer.calls == [] and svc.db.commits == 1


def test_create_without_category_uses_categorizer(svc):
    expense = svc.create(USER, ExpenseCreate(date=date(2026, 10, 1), description="Uber", amount_cents=100))
    assert (expense.category, expense.category_source) == ("Travel", "ai")
    assert svc.categorizer.calls == [["Uber"]]


def test_update_changes_only_sent_fields_and_marks_category_manual(svc):
    expense = svc.expenses.add(Expense(user_id=USER, date=date(2026, 10, 1), description="Uber", amount_cents=100,
                                       category="Travel", category_source=CategorySource.AI))
    svc.update(USER, expense.id, ExpenseUpdate(amount_cents=250))
    assert (expense.amount_cents, expense.category_source) == (250, "ai")
    svc.update(USER, expense.id, ExpenseUpdate(category="Meals"))
    assert (expense.category, expense.category_source, expense.description) == ("Meals", "manual", "Uber")


def test_other_users_expense_is_not_found(svc):
    expense = svc.expenses.add(Expense(user_id=USER, date=date(2026, 10, 1), description="x", amount_cents=1, category="Other"))
    with pytest.raises(NotFoundError, match="Expense not found."):
        svc.update(OTHER, expense.id, ExpenseUpdate(amount_cents=2))
    with pytest.raises(NotFoundError):
        svc.delete(OTHER, expense.id)
    svc.delete(USER, expense.id)
    assert svc.expenses.rows == {}


def test_list_filters_by_month(svc):
    for on in (date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 31)):
        svc.expenses.add(Expense(user_id=USER, date=on, description="x", amount_cents=1, category="Other"))
    assert [e.date for e in svc.list(USER, "2026-10")] == [date(2026, 10, 31), date(2026, 10, 1)]
    assert len(svc.list(USER)) == 3


def test_import_csv_parses_rows_and_reports_skipped_lines(svc):
    raw = (
        "﻿Date , DESCRIPTION,Amount\n"
        "2026-10-02,Grab ride,-18.50\n"
        "03/10/2026,Laptop,\"$1,042.00\"\n"
        "bad,row,x\n"
        "2026-10-04,,5\n"
        "2026-10-05,Zero,0\n"
        f"2026-10-06,{'x' * 300},1\n"
    ).encode()
    out = svc.import_csv(USER, raw)
    assert out.imported == 3 and out.skipped_rows == [4, 5, 6]
    assert [(e.date, e.amount_cents) for e in out.expenses] == [
        (date(2026, 10, 2), 1_850), (date(2026, 10, 3), 104_200), (date(2026, 10, 6), 100),
    ]
    assert len(out.expenses[2].description) == 255
    assert svc.categorizer.calls == [["Grab ride", "Laptop", "x" * 255]]
    assert svc.db.commits == 1


@pytest.mark.parametrize(
    "raw, message",
    [
        (b"", "The file is empty."),
        (b"date,amount\n2026-10-01,1\n", "The CSV needs these columns: date, description, amount. Missing: description."),
        (b"date,description,amount\n" + b"2026-10-01,x,1\n" * 501, "Import up to 500 rows at a time."),
    ],
)
def test_import_csv_errors(svc, raw, message):
    with pytest.raises(BadInputError) as exc:
        svc.import_csv(USER, raw)
    assert exc.value.message == message
    assert svc.db.commits == 0
