# Ledgerly

Invoicing and cash-flow tracking for freelancers. Create an invoice, send your client a Stripe
payment link, and the payment lands on your dashboard automatically next to your expenses.
Claude categorizes expenses, writes a monthly summary, and answers questions about your money.

**Stack:** FastAPI · SQLAlchemy · SQLite/Postgres · Stripe Checkout + webhooks · Anthropic API · React (Vite) · Recharts

## How it works

```
 React (Vite :5173) ──/api──▶ FastAPI (:8000) ──▶ SQLite / Postgres
                                 │   ▲
              create Checkout ───┘   └─── webhook: checkout.session.completed
                                 ▼   │       (signature verified, idempotent)
                               Stripe ◀── client pays on hosted Checkout page
                                 
 FastAPI ──▶ Claude: categorize expenses (Haiku) · monthly summary + Q&A with tool use (Sonnet)
```

Design decisions worth calling out in interviews:

- **Webhooks are the source of truth.** An invoice is only marked paid after a signature-verified
  Stripe event, never from the browser redirect. Processed event IDs are stored so Stripe retries
  can't double-count a payment.
- **Money is integer cents everywhere.** No floats.
- **Claude never does the math.** All totals are computed in `services/analytics.py`. Claude only
  describes pre-computed numbers (summary) or picks which of our query functions to call (Q&A tool use).
  It never writes SQL.
- **Every AI feature has a fallback.** Without an API key, categorization uses keyword rules and the
  summary uses a template, so the app still runs.
- **Stripe fees are recorded** by reading the charge's balance transaction, so the dashboard shows
  gross, fees, and net separately.

## Run it locally

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in keys (see below)
python seed.py                     # optional: demo account with 6 months of data
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend
p
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with `demo@ledgerly.app` / `demo12345` (after seeding),
or create an account.

### 3. Keys (`backend/.env`)

| Variable | Where to get it |
|---|---|
| `SECRET_KEY` | Any long random string: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `STRIPE_SECRET_KEY` | Stripe Dashboard → Developers → API keys, using a **sandbox / test** key (`sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | Printed by `stripe listen` (step 4) |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

The app runs without any keys; payment links and AI features just stay switched off.

### 4. Receive Stripe webhooks locally

Install the [Stripe CLI](https://docs.stripe.com/stripe-cli), then:

```bash
stripe login
stripe listen --forward-to localhost:8000/api/webhooks/stripe \
  --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.expired
```

Copy the `whsec_…` value it prints into `STRIPE_WEBHOOK_SECRET` and restart the API.

### 5. Try the full payment loop

1. Add a client, then create an invoice for them.
2. Click **Create payment link**, then **Open**.
3. Pay with test card `4242 4242 4242 4242`, any future expiry, any CVC.
4. Within a few seconds the invoice flips to **Paid** and the dashboard updates.

## Tests

```bash
cd backend && pytest -q
```

Covers auth, per-user data isolation, webhook signature verification (with a real HMAC signature),
idempotent webhook retries, fee/net recording, CSV import, and the Claude tool-use loop (mocked).

## Project layout

```
backend/
  app/
    main.py                 FastAPI app, CORS, routers
    models.py               User, Client, Invoice, Payment, Expense, ProcessedStripeEvent
    schemas.py              Pydantic request/response models
    routers/                auth, clients, invoices, expenses, dashboard, insights, webhooks
    services/
      stripe_service.py     Customers, Checkout Sessions, fee lookup, webhook verification
      analytics.py          All money math (exact, testable)
      claude_service.py     Categorization, monthly summary, tool-use Q&A
  seed.py                   Demo data
  tests/
frontend/
  src/
    api.js                  Fetch wrapper with JWT
    pages/                  Dashboard, Invoices, Clients, Expenses, Ask, AuthPage, PayResult
    styles.css
sample-expenses.csv         Try the CSV import with this
```

## Deploying

- **Database:** set `DATABASE_URL` to Postgres (add `psycopg[binary]` to requirements). Replace
  `create_all` with Alembic migrations once the schema settles.
- **Backend:** Render, Railway, or Fly.io: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Frontend:** Vercel or Netlify. Set `VITE_API_URL` to your API origin and `FRONTEND_URL` on the
  backend to your frontend origin (used for CORS and Checkout redirects).
- **Stripe:** add a webhook endpoint in the Dashboard pointing at
  `https://your-api/api/webhooks/stripe` with the three events above, and use its signing secret.

## Ideas for after the MVP

- Email the payment link to the client (Stripe can do this if you switch to Stripe Invoices).
- Refund and dispute handling (`charge.refunded`, `charge.dispute.created`).
- Recurring retainers with Stripe Billing.
- Multi-currency support.
- Store the JWT in an httpOnly cookie instead of localStorage.
