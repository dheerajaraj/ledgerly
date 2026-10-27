from datetime import datetime, timezone

from ...database import Base  # noqa: F401  (re-exported for the model modules)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
