import os
import sys
from pathlib import Path

# Configure the app for tests before anything imports it
os.environ["DATABASE_URL"] = "sqlite:///./test_ledgerly.db"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
os.environ["ANTHROPIC_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.database import Base, engine
from app.repository import models  # noqa: F401  (registers every table)


@pytest.fixture
def fresh_db():
    """Drop and recreate every table. Autoused by tests/integration and tests/api, not tests/unit."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def pytest_sessionfinish(session, exitstatus):
    Path("test_ledgerly.db").unlink(missing_ok=True)
