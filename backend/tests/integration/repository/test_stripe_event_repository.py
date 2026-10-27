import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.repository.stripe_event_repository import StripeEventRepository


def test_stripe_event_repository_dedupes(db):
    repo = StripeEventRepository(db)
    assert not repo.exists("evt_1")
    repo.add("evt_1", "checkout.session.completed")
    db.commit()
    assert repo.exists("evt_1")


def test_duplicate_stripe_event_fails_on_commit():
    """A racing duplicate delivery must surface as IntegrityError so the service can treat it as a duplicate."""
    first, second = SessionLocal(), SessionLocal()
    try:
        assert not StripeEventRepository(second).exists("evt_race")
        StripeEventRepository(first).add("evt_race", "checkout.session.completed")
        first.commit()
        StripeEventRepository(second).add("evt_race", "checkout.session.completed")
        with pytest.raises(IntegrityError):
            second.commit()
    finally:
        second.rollback()
        first.close()
        second.close()
