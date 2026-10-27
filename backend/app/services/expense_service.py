import csv
import io

from sqlalchemy.orm import Session

from ..repository.expense_repository import ExpenseRepository
from ..repository.models import CategorySource, Expense
from ..schema.expense import CsvImportOut, ExpenseCreate, ExpenseOut, ExpenseUpdate
from ..utils.dates import month_bounds, parse_flexible_date
from ..utils.money import parse_amount_to_cents
from .categorization import CategorizationService
from .exceptions import BadInputError, NotFoundError

MAX_CSV_ROWS = 500
CSV_COLUMNS = {"date", "description", "amount"}


class ExpenseService:
    def __init__(self, db: Session, expenses: ExpenseRepository, categorizer: CategorizationService):
        self.db = db
        self.expenses = expenses
        self.categorizer = categorizer

    def _get_owned(self, user_id: int, expense_id: int) -> Expense:
        expense = self.expenses.get_for_user(user_id, expense_id)
        if not expense:
            raise NotFoundError("Expense not found.")
        return expense

    def list(self, user_id: int, month: str | None = None) -> list[Expense]:
        start, end = month_bounds(month) if month else (None, None)
        return self.expenses.list_for_user(user_id, start, end)

    def create(self, user_id: int, data: ExpenseCreate) -> Expense:
        if data.category:
            category, source = data.category, CategorySource.MANUAL
        else:
            [(category, source)] = self.categorizer.categorize([data.description])
        expense = self.expenses.add(Expense(
            user_id=user_id,
            date=data.date,
            description=data.description,
            amount_cents=data.amount_cents,
            category=category,
            category_source=source,
        ))
        self.db.commit()
        return expense

    def update(self, user_id: int, expense_id: int, data: ExpenseUpdate) -> Expense:
        expense = self._get_owned(user_id, expense_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(expense, field, value)
        if "category" in changes:
            expense.category_source = CategorySource.MANUAL
        self.db.commit()
        return expense

    def delete(self, user_id: int, expense_id: int) -> None:
        self.expenses.delete(self._get_owned(user_id, expense_id))
        self.db.commit()

    def import_csv(self, user_id: int, raw: bytes) -> CsvImportOut:
        """Import a CSV with columns: date, description, amount (header names are case-insensitive)."""
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
        if not reader.fieldnames:
            raise BadInputError("The file is empty.")
        columns = {name.strip().lower(): name for name in reader.fieldnames}
        missing = CSV_COLUMNS - set(columns)
        if missing:
            raise BadInputError(f"The CSV needs these columns: date, description, amount. Missing: {', '.join(sorted(missing))}.")

        rows, skipped = [], []
        for line_no, row in enumerate(reader, start=2):
            if len(rows) >= MAX_CSV_ROWS:
                raise BadInputError(f"Import up to {MAX_CSV_ROWS} rows at a time.")
            try:
                description = (row[columns["description"]] or "").strip()
                amount = parse_amount_to_cents(row[columns["amount"]] or "")
                if not description or amount <= 0:
                    raise ValueError("blank")
                rows.append((parse_flexible_date(row[columns["date"]] or ""), description[:255], amount))
            except (ValueError, KeyError):
                skipped.append(line_no)

        categorized = self.categorizer.categorize([description for _, description, _ in rows])
        created = self.expenses.add_all([
            Expense(user_id=user_id, date=on, description=description, amount_cents=amount, category=category, category_source=source)
            for (on, description, amount), (category, source) in zip(rows, categorized)
        ])
        self.db.commit()
        return CsvImportOut(imported=len(created), skipped_rows=skipped, expenses=[ExpenseOut.model_validate(e) for e in created])
