"""App factory: wires routers, middleware and startup. No business logic."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import auth, clients, dashboard, expenses, health, insights, invoices, webhooks
from .config import get_settings
from .database import Base, engine
from .middleware import configure_logging, register_error_handlers, register_middleware
from .repository import models  # noqa: F401  (registers every table on Base.metadata)

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # For an MVP we create tables on startup. Switch to Alembic migrations once the schema settles.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Ledgerly API", version="0.1.0", lifespan=lifespan)
register_middleware(app, settings)
register_error_handlers(app)

for module in (auth, clients, invoices, expenses, dashboard, insights, webhooks, health):
    app.include_router(module.router)
