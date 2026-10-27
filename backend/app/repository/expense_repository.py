from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Expense


class ExpenseRepository:
    def __init__(self, db: Session):
        self.db = db

    def _in_period(self, user_id: int, start: date | None, end: date | None):
        query = select(Expense).where(Expense.user_id == user_id)
        if start:
            query = query.where(Expense.date >= start)
        if end:
            query = query.where(Expense.date < end)
        return query

    def list_for_user(self, user_id: int, start: date | None = None, end: date | None = None) -> list[Expense]:
        """Newest first, for display."""
        query = self._in_period(user_id, start, end).order_by(Expense.date.desc(), Expense.id.desc())
        return list(self.db.scalars(query))

    def list_for_period(self, user_id: int, start: date | None = None, end: date | None = None) -> list[Expense]:
        """Unordered, for analytics."""
        return list(self.db.scalars(self._in_period(user_id, start, end)))

    def get_for_user(self, user_id: int, expense_id: int) -> Expense | None:
        return self.db.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id))

    def add(self, expense: Expense) -> Expense:
        self.db.add(expense)
        self.db.flush()
        return expense

    def add_all(self, expenses: list[Expense]) -> list[Expense]:
        self.db.add_all(expenses)
        self.db.flush()
        return expenses

    def delete(self, expense: Expense) -> None:
        self.db.delete(expense)
        self.db.flush()
