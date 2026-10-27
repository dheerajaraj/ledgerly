"""Populate a demo account with six months of realistic data.

Run:  python seed.py
Then sign in with  demo@ledgerly.app / demo12345

Seeded payments are written straight to the database (no Stripe calls), so the dashboard
has history to show. New invoices you create in the app go through real Stripe Checkout.
"""
import random
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.repository.models import CategorySource, Client, Expense, Invoice, InvoiceStatus, Payment, User
from app.utils.dates import month_bounds, month_key, shift_month
from app.utils.security import hash_password

EMAIL, PASSWORD = "demo@ledgerly.app", "demo12345"

CLIENTS = [
    ("Northwind Studio", "billing@northwind.example"),
    ("Kestrel Health", "ap@kestrel.example"),
    ("Juniper & Co", "finance@juniper.example"),
    ("Orbital Coffee", "owner@orbital.example"),
]

WORK = ["Website redesign", "Brand guidelines", "Landing page build", "Monthly retainer", "App UI audit", "Pitch deck design"]

EXPENSES = [
    ("Figma Professional subscription", 1500, "Software"),
    ("Notion Plus", 1000, "Software"),
    ("Adobe Creative Cloud", 5999, "Software"),
    ("Coworking day pass", 3500, "Office"),
    ("Client lunch", 6420, "Meals"),
    ("Grab to client office", 1850, "Travel"),
    ("Fibre broadband", 4990, "Utilities"),
    ("Mobile plan", 3000, "Utilities"),
    ("LinkedIn ads", 12000, "Marketing"),
    ("Accountant quarterly review", 25000, "Professional services"),
    ("Udemy course: motion design", 1999, "Education"),
    ("Coffee with prospect", 1240, "Meals"),
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    random.seed(7)

    existing = db.scalar(select(User).where(User.email == EMAIL))
    if existing:
        db.query(Expense).filter(Expense.user_id == existing.id).delete()
        db.query(Payment).filter(Payment.user_id == existing.id).delete()
        db.query(Invoice).filter(Invoice.user_id == existing.id).delete()
        db.delete(existing)  # cascades to clients
        db.commit()

    user = User(email=EMAIL, name="Demo Freelancer", hashed_password=hash_password(PASSWORD))
    db.add(user)
    db.flush()
    clients = [Client(user_id=user.id, name=n, email=e) for n, e in CLIENTS]
    db.add_all(clients)
    db.flush()

    this_month = month_key(date.today())
    for back in range(5, -1, -1):
        m = shift_month(this_month, -back)
        start, end = month_bounds(m)
        last_day = min(end - timedelta(days=1), date.today())
        span = max((last_day - start).days, 1)

        # 2-4 paid invoices a month, weighted toward one big client (a realistic concentration risk)
        for _ in range(random.randint(2, 4)):
            client = random.choices(clients, weights=[5, 2, 2, 1])[0]
            amount = random.choice([80000, 120000, 150000, 240000, 320000])
            paid_day = start + timedelta(days=random.randint(0, span))
            fee = round(amount * 0.029) + 30
            inv = Invoice(
                user_id=user.id, client_id=client.id, description=random.choice(WORK),
                amount_cents=amount, currency="usd", status=InvoiceStatus.PAID,
                due_date=paid_day + timedelta(days=7), paid_at=datetime.combine(paid_day, datetime.min.time()),
                created_at=datetime.combine(paid_day - timedelta(days=10), datetime.min.time()),
            )
            db.add(inv)
            db.flush()
            db.add(Payment(user_id=user.id, invoice_id=inv.id, gross_cents=amount, fee_cents=fee,
                           net_cents=amount - fee, currency="usd", paid_at=inv.paid_at))

        for desc, cents, cat in EXPENSES:
            if random.random() < 0.75:
                d = start + timedelta(days=random.randint(0, span))
                jitter = cents if cat == "Software" else round(cents * random.uniform(0.7, 1.4))
                db.add(Expense(user_id=user.id, date=d, description=desc, amount_cents=jitter,
                               category=cat, category_source=CategorySource.MANUAL))

    # A couple of open invoices, one overdue, so the dashboard has something to chase
    db.add(Invoice(user_id=user.id, client_id=clients[1].id, description="Patient portal wireframes",
                   amount_cents=180000, currency="usd", status=InvoiceStatus.OPEN,
                   due_date=date.today() - timedelta(days=5)))
    db.add(Invoice(user_id=user.id, client_id=clients[2].id, description="Q4 campaign assets",
                   amount_cents=95000, currency="usd", status=InvoiceStatus.DRAFT,
                   due_date=date.today() + timedelta(days=14)))
    db.commit()
    db.close()
    print(f"Seeded demo account: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    run()
