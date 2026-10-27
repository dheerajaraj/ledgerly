---
paths:
  - "backend/**/*.py"
---

# Backend Architecture Rules

These rules define the target structure for the FastAPI backend in `backend/app/`. New code must follow them. When touching existing code that doesn't follow them yet, move it toward this layout instead of adding to the old one.

## Folder layout

```
backend/
├── app/
│   ├── main.py              # App factory: wires routers, middleware, startup. No business logic.
│   ├── config.py            # Settings (pydantic-settings). The only place env vars are read.
│   ├── database.py          # Engine, SessionLocal, Base, get_db session dependency
│   ├── api/                 # HTTP entry point: routers/controllers
│   │   ├── deps.py          # FastAPI dependencies (current user, db session, services)
│   │   ├── auth.py
│   │   ├── invoices.py
│   │   └── ...
│   ├── schema/              # Pydantic models for data entering or leaving the API
│   │   ├── invoice.py
│   │   └── ...
│   ├── services/            # Business rules, use cases, transaction coordination
│   │   ├── factory.py       # builds services with their repositories and integration clients
│   │   ├── exceptions.py    # domain exceptions (NotFoundError, InvalidStatusTransition, ...)
│   │   ├── invoice_service.py
│   │   ├── analytics.py
│   │   └── ...
│   ├── repository/          # Database queries and persistence
│   │   ├── models/          # SQLAlchemy ORM models (one file per aggregate)
│   │   │   ├── invoice.py
│   │   │   └── ...
│   │   ├── invoice_repository.py
│   │   └── ...
│   ├── integrations/        # Third-party providers, one sub-folder per provider
│   │   ├── stripe/
│   │   │   ├── client.py
│   │   │   └── webhooks.py  # signature verification, event parsing
│   │   └── anthropic/
│   │       └── client.py
│   ├── middleware/          # Cross-cutting request/response logic
│   │   ├── request_id.py
│   │   ├── logging.py
│   │   └── error_handlers.py
│   └── utils/               # Generic, app-agnostic helpers
│       ├── money.py
│       ├── dates.py
│       └── security.py      # password hashing, JWT encode/decode
└── tests/
    ├── conftest.py          # Shared fixtures (env setup, db, client)
    ├── unit/
    ├── integration/
    └── api/
```

## Dependency direction

Dependencies point one way: **api → services → repository / integrations**. `schema` and `utils` can be imported from most layers. No layer may import from a layer above it, and circular imports between modules are not allowed.

| Layer          | May import                                                                      | Must NOT import                                                   |
|----------------|---------------------------------------------------------------------------------|-------------------------------------------------------------------|
| `api`          | `services`, `schema`, `utils`, `api/deps` (only `api/deps.py` imports `database`) | `repository` (incl. `models`), `integrations`                     |
| `services`     | `repository`, `repository/models`, `integrations`, `schema`, `utils`, `config`  | `api`, `middleware`, `fastapi` (`HTTPException`, `Request`, etc.) |
| `repository`   | `repository/models`, `database`, `utils`                                        | `services`, `api`, `integrations`, `schema`                       |
| `integrations` | `utils`, `config`                                                               | `services`, `repository`, `api`, `schema`                         |
| `schema`       | `utils`                                                                         | `services`, `repository`, `api`, `integrations`                   |
| `middleware`   | `utils`, `config`, `services` exceptions                                        | `repository`, `integrations`                                      |
| `utils`        | stdlib and third-party libraries only                                           | anything in `app/`                                                |

If you need to break one of these rules, the code is probably in the wrong layer. Move it rather than adding the import.

---

## `api/`: routers and controllers

**Responsibility:** The HTTP entry point. Each module defines an `APIRouter` for one resource, maps HTTP requests to service calls, and maps results back to HTTP responses.

**Best practices:**
- **Keep endpoints thin.** A handler should do three things: take validated input (a schema), call one service method, and return a response schema. If a handler has branching business logic, loops over data, or more than a few lines, move that logic into a service.
- Every route lives under `/api/...`.
- Declare `response_model` on every endpoint so output is always filtered through a schema. Never return ORM objects without a response schema.
- Map service exceptions to HTTP status codes, either in the handler or (preferably) through the handlers in `middleware/error_handlers.py`. A row owned by another user returns **404, not 403**.
- Inject services and the DB session with FastAPI `Depends`. Don't instantiate clients or open sessions inside a handler.
- `api/deps.py` gets services from `services/factory.py` (e.g. `factory.build_invoice_service(db)`), so the api layer never imports repositories or integration clients.
- `api/deps.get_current_user` returns a `schema.auth.CurrentUser`, not the ORM `User`. Pass `user.id` to services; never trust a `user_id` from the request body or query.
- Don't call `db.commit()`, write queries, or call Stripe or Anthropic from this layer.

## `schema/`: API contracts (Pydantic)

**Responsibility:** Define what data enters and leaves the API layer. Schemas are the public contract of the API.

**Best practices:**
- Use Pydantic v2. Use separate models per direction and purpose: `InvoiceCreate`, `InvoiceUpdate`, `InvoiceOut`. Don't reuse one model for input and output.
- Set `model_config = ConfigDict(extra="forbid")` on input schemas so unknown fields are rejected. Set `from_attributes=True` on output schemas that are built from ORM objects.
- Validate declaratively with `Field(...)` constraints (`gt`, `ge`, `max_length`, `pattern`), `EmailStr`, enums, and `field_validator` / `model_validator`. Validation that needs the database (e.g. "client exists and belongs to user") belongs in services, not schemas.
- Never expose internal or sensitive fields (password hashes, Stripe secrets, other users' IDs) in output schemas.
- Keep schemas free of behavior. Apart from validators and simple computed fields, they hold no business logic.
- Group by resource: one module per resource (`schema/invoice.py`, `schema/client.py`).

## `services/`: business logic and use cases

**Responsibility:** Business rules, use cases, and transaction coordination. This is where the app decides what should happen.

**Best practices:**
- Use one service per use-case area (e.g. `InvoiceService`, `ExpenseService`, `InsightsService`, `PaymentService`). Its public methods are use cases (`create_payment_link`, `mark_paid_from_webhook`, `void_invoice`).
- **Services own the transaction boundary.** A use case that touches several repositories commits once at the end, or rolls back on failure. Repositories never commit.
- Enforce domain invariants here:
  - Invoice status transitions (`draft → open → paid | expired`; any non-paid → `void`; paid can't be voided). Put the allowed transitions in one place and check them before every status change.
  - Only the Stripe webhook use case marks an invoice `paid`.
  - Webhook idempotency: record the event ID and apply the change in the same transaction.
  - All money math happens in integer cents.
- Always scope by user: every service method that reads or writes tenant data takes `user_id` and passes it to the repository.
- Raise **domain exceptions** (e.g. `NotFoundError`, `InvalidStatusTransition`, `IntegrationUnavailable`) defined in `services/exceptions.py`. Never raise `HTTPException` or import FastAPI here.
- Call third-party providers only through `integrations/`, and own the fallback decision. When an integration is disabled or fails, the service uses the non-AI or non-Stripe fallback (keyword categorization, template summary) and records the source (`category_source`, `generated_by`).
- **Claude never does math.** Totals and aggregates come from `services/analytics.py`. The service that runs the Q&A tool loop does tool dispatch (tool name → analytics function). The Anthropic integration only sends and receives messages.
- Services should be easy to unit test: take repositories and integration clients as constructor or function arguments instead of importing module-level singletons.
- Wire new services in `services/factory.py` (a `build_<name>_service(db)` function) and expose them through `api/deps.py`. Integration clients come from the `stripe_client()` / `claude_client()` providers there, which tests replace.
- A deliberate early commit is OK when a third-party side effect has already happened and must not be lost (e.g. saving a new Stripe customer ID before creating the checkout session). Comment why.

## `repository/`: persistence

**Responsibility:** Database queries and persistence logic. This is the only layer that knows about SQLAlchemy sessions and queries.

**Best practices:**
- Use one repository per aggregate (`InvoiceRepository`, `ClientRepository`, `ExpenseRepository`). Methods are named after the data they fetch or store (`get_for_user`, `list_by_status`, `add`, `get_by_checkout_session_id`).
- **Every query on tenant data filters by `user_id`.** Return `None` (or raise `NotFoundError`) when a row doesn't belong to the user, so the user can't tell whether it exists.
- Don't call `commit()` here. Use `add` / `flush` and leave committing to the service.
- No business rules. Repositories don't decide whether a status change is allowed. They only persist what the service decides.
- Avoid N+1 queries. Use `selectinload` / `joinedload` when callers need relationships, and do aggregation in SQL where practical.
- Return ORM models or plain values. Don't return Pydantic schemas.
- Never build SQL by string concatenation. Use the SQLAlchemy expression API or bound parameters.

### `repository/models/`: ORM models

- SQLAlchemy declarative models only, one module per aggregate, re-exported from `repository/models/__init__.py` so `Base.metadata` sees every table.
- Every tenant-owned model has an indexed, non-null `user_id` foreign key.
- Status fields use Python `Enum`s defined next to the model (e.g. `InvoiceStatus`).
- Models hold columns, relationships, and constraints (unique, check, indexes). They don't hold business methods that call out to other layers.

## `integrations/`: third-party providers

**Responsibility:** Talk to external service providers. Each provider gets its own sub-folder (`integrations/stripe/`, `integrations/anthropic/`), and logic specific to that provider stays inside it.

**Best practices:**
- **Wrap the vendor SDK.** Expose a small, app-shaped interface (`create_checkout_session(...)`, `get_fee_cents(...)`, `verify_webhook(...)`, `complete(messages, tools)`) so the rest of the app never imports `stripe` or `anthropic` directly.
- Return plain data (dataclasses, typed dicts, or primitive values), not raw SDK objects, so callers don't depend on vendor types.
- Translate vendor exceptions into integration-level exceptions (e.g. `StripeError`, `ClaudeUnavailable`). Document which methods are guaranteed never to raise (e.g. `get_fee_cents` returns 0 on failure).
- Read API keys and model names from `config.get_settings()`. Expose `enabled` checks (`stripe_enabled`, `claude_enabled`). **Never hard-code secrets.**
- No database access and no business rules. An integration doesn't know what an invoice status is. It only does what the service asks it to do.
- Set explicit timeouts. Add retries only for idempotent calls, and pass idempotency keys to Stripe for create operations.
- Keep each client easy to mock: one client object per provider, injected into services, so tests can replace it.

## `middleware/`: cross-cutting concerns

**Responsibility:** Logic that applies to every request (or a broad class of requests), independent of any one resource.

**Typical contents:**
- Request ID / correlation ID generation and propagation into logs.
- Structured request/response logging and timing. Never log secrets, tokens, full card or payment data, or request bodies with PII.
- Global exception handlers that map domain and integration exceptions to consistent JSON error responses and status codes (`NotFoundError → 404`, `InvalidStatusTransition → 409`, validation → 422, unexpected → 500 without leaking stack traces).
- CORS, security headers, and rate limiting.

**Best practices:**
- Middleware must not contain business logic or query the database.
- Keep auth that depends on the route (who the current user is) in `api/deps.py` as a dependency, not in global middleware, so public routes (webhooks, `/pay/*` results, login) stay explicit.
- Register all middleware in `main.py` in one place, in a deliberate order (request ID first, so later middleware can use it).
- Middleware must be cheap and non-blocking. Use async-safe code and no external calls.

## `utils/`: generic helpers

**Responsibility:** Small, pure, reusable functions that any layer can use.

**Best practices:**
- Utilities must be **app-agnostic**: no imports from `app/` modules, no database access, no knowledge of invoices, users, or providers. If a helper needs domain knowledge, it belongs in a service.
- Prefer pure functions with no side effects or global state.
- Group by topic (`money.py` for cents formatting/parsing, `dates.py` for month ranges and timezone handling, `security.py` for hashing and JWT helpers). Avoid a catch-all `helpers.py`.
- Every utility has unit tests.

---

## `tests/`

Tests mirror the source layout inside each category. Shared fixtures go in `tests/conftest.py`. Fixtures for one category go in that folder's `conftest.py`.

### `tests/unit/`
- Test a single unit in isolation: services, utils, schema validators.
- Replace repositories and integration clients with fakes or mocks. Unit tests don't touch a real database or the network.
- Cover business rules thoroughly: every allowed and forbidden status transition, fallback paths when Claude or Stripe is disabled or fails, and cents arithmetic edge cases.
- Must be fast. The full unit suite should run in seconds.

### `tests/integration/`
- Test a layer against its real dependency: repositories against a real SQLite test database, and services wired to real repositories.
- Test integration clients against mocked HTTP or monkeypatched SDK calls. Never call live Stripe or Anthropic APIs from the test suite.
- Verify tenant isolation at the repository level (queries never return another user's rows) and transaction behavior (rollback on failure, webhook dedupe).
- Recreate the database for each test so tests never depend on each other.

### `tests/api/`
- End-to-end through FastAPI's `TestClient`: HTTP request → router → service → repository → test DB, with external providers mocked.
- Assert status codes, response schemas, and error shapes, including 401 for missing auth, 404 for another user's resources, 422 for invalid input, and 409 for illegal state transitions.
- Test webhooks with real HMAC signatures, including invalid signature, duplicate event, and unknown invoice.

### General testing rules
- Every new piece of logic ships with tests in the right category.
- Name tests for the behavior they check: `test_void_paid_invoice_is_rejected`, not `test_void_2`.
- Set env vars before importing the app (see `tests/conftest.py`) so no real keys or production database are ever used.
