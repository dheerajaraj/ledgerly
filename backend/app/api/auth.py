from fastapi import APIRouter, Depends

from ..schema.auth import CurrentUser, LoginIn, RegisterIn, TokenOut, UserOut
from ..services.auth_service import AuthService
from .deps import get_auth_service, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, auth: AuthService = Depends(get_auth_service)):
    return auth.register(body)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, auth: AuthService = Depends(get_auth_service)):
    return auth.login(body)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)):
    return user
