from fastapi import APIRouter, Depends

from ..schema.system import HealthOut
from ..services.system_service import SystemService
from .deps import get_system_service

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(system: SystemService = Depends(get_system_service)):
    return system.status()
