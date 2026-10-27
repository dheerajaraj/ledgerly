from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Client


class ClientRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: int) -> list[Client]:
        return list(self.db.scalars(select(Client).where(Client.user_id == user_id).order_by(Client.name)))

    def get_for_user(self, user_id: int, client_id: int) -> Client | None:
        return self.db.scalar(select(Client).where(Client.id == client_id, Client.user_id == user_id))

    def add(self, client: Client) -> Client:
        self.db.add(client)
        self.db.flush()
        return client
