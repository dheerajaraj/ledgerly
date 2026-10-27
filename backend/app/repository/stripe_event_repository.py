from sqlalchemy.orm import Session

from .models import ProcessedStripeEvent


class StripeEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def exists(self, event_id: str) -> bool:
        return self.db.get(ProcessedStripeEvent, event_id) is not None

    def add(self, event_id: str, event_type: str) -> None:
        """Record an event as processed. Not flushed here: a racing duplicate surfaces as an
        IntegrityError on the caller's commit, so the event ID and the invoice change commit together."""
        self.db.add(ProcessedStripeEvent(id=event_id, type=event_type))
