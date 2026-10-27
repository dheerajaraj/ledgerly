from fastapi import APIRouter, Depends, File, Query, UploadFile

from ..schema.auth import CurrentUser
from ..schema.expense import CATEGORIES, CsvImportOut, ExpenseCreate, ExpenseOut, ExpenseUpdate
from ..services.expense_service import ExpenseService
from .deps import get_current_user, get_expense_service

router = APIRouter(prefix="/api/expenses", tags=["expenses"])

MONTH_PATTERN = r"^\d{4}-\d{2}$"


@router.get("/categories", response_model=list[str])
def categories():
    return CATEGORIES


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    month: str | None = Query(default=None, pattern=MONTH_PATTERN),
    user: CurrentUser = Depends(get_current_user),
    expenses: ExpenseService = Depends(get_expense_service),
):
    return expenses.list(user.id, month)


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate,
    user: CurrentUser = Depends(get_current_user),
    expenses: ExpenseService = Depends(get_expense_service),
):
    return expenses.create(user.id, body)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    body: ExpenseUpdate,
    user: CurrentUser = Depends(get_current_user),
    expenses: ExpenseService = Depends(get_expense_service),
):
    return expenses.update(user.id, expense_id, body)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: int,
    user: CurrentUser = Depends(get_current_user),
    expenses: ExpenseService = Depends(get_expense_service),
):
    expenses.delete(user.id, expense_id)


@router.post("/import-csv", response_model=CsvImportOut)
def import_csv(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    expenses: ExpenseService = Depends(get_expense_service),
):
    """Import a CSV with columns: date, description, amount (header names are case-insensitive)."""
    return expenses.import_csv(user.id, file.file.read())
