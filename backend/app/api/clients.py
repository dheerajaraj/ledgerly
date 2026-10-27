from fastapi import APIRouter, Depends

from ..schema.auth import CurrentUser
from ..schema.client import ClientCreate, ClientOut, ClientUpdate
from ..services.client_service import ClientService
from .deps import get_client_service, get_current_user

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
def list_clients(user: CurrentUser = Depends(get_current_user), clients: ClientService = Depends(get_client_service)):
    return clients.list(user.id)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    body: ClientCreate,
    user: CurrentUser = Depends(get_current_user),
    clients: ClientService = Depends(get_client_service),
):
    return clients.create(user.id, body)


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    body: ClientUpdate,
    user: CurrentUser = Depends(get_current_user),
    clients: ClientService = Depends(get_client_service),
):
    return clients.update(user.id, client_id, body)
