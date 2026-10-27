from pydantic import BaseModel


class PeriodSummaryOut(BaseModel):
    start: str
    end_exclusive: str
    gross_income_cents: int
    stripe_fees_cents: int
    net_income_cents: int
    expenses_cents: int
    profit_cents: int
    payments_count: int
    expenses_count: int


class MonthPointOut(BaseModel):
    month: str
    income_cents: int
    expenses_cents: int
    net_cents: int


class CategoryTotalOut(BaseModel):
    category: str
    amount_cents: int


class ClientIncomeOut(BaseModel):
    client: str
    gross_cents: int
    payments: int
    share: float  # fraction of gross income, not money


class OutstandingOut(BaseModel):
    open_count: int
    open_cents: int
    overdue_count: int
    overdue_cents: int


class DashboardOut(BaseModel):
    month: str
    summary: PeriodSummaryOut
    series: list[MonthPointOut]
    expenses_by_category: list[CategoryTotalOut]
    income_by_client: list[ClientIncomeOut]
    outstanding: OutstandingOut
