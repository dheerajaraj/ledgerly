from sqlalchemy.orm import Session

from ..repository.client_repository import ClientRepository
from ..repository.models import Client
from ..schema.client import ClientCreate, ClientUpdate
from .exceptions import NotFoundError


class ClientService:
    def __init__(self, db: Session, clients: ClientRepository):
        self.db = db
        self.clients = clients

    def list(self, user_id: int) -> list[Client]:
        return self.clients.list_for_user(user_id)

    def create(self, user_id: int, data: ClientCreate) -> Client:
        client = self.clients.add(Client(user_id=user_id, name=data.name, email=data.email))
        self.db.commit()
        return client

    def update(self, user_id: int, client_id: int, data: ClientUpdate) -> Client:
        client = self.clients.get_for_user(user_id, client_id)
        if not client:
            raise NotFoundError("Client not found.")
        client.name, client.email = data.name, data.email
        self.db.commit()
        return client
