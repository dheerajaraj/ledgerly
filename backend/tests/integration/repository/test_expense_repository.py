from datetime import date

from app.repository.expense_repository import ExpenseRepository


def test_expense_repository_is_scoped_filtered_and_sorted(db, make):
    owner, other = make.user("a@example.com"), make.user("b@example.com")
    early = make.expense(owner, on=date(2026, 10, 1))
    late = make.expense(owner, on=date(2026, 10, 20))
    make.expense(owner, on=date(2026, 11, 1))
    foreign = make.expense(other, on=date(2026, 10, 5))
    repo = ExpenseRepository(db)

    assert [e.id for e in repo.list_for_user(owner.id, date(2026, 10, 1), date(2026, 11, 1))] == [late.id, early.id]
    assert {e.id for e in repo.list_for_period(owner.id, date(2026, 10, 1), date(2026, 11, 1))} == {early.id, late.id}
    assert len(repo.list_for_user(owner.id)) == 3
    assert repo.get_for_user(owner.id, foreign.id) is None


def test_delete_removes_expense(db, make):
    owner = make.user()
    expense = make.expense(owner)
    repo = ExpenseRepository(db)
    repo.delete(expense)
    assert repo.get_for_user(owner.id, expense.id) is None
