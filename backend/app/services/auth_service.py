from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..repository.models import User
from ..repository.user_repository import UserRepository
from ..schema.auth import CurrentUser, LoginIn, RegisterIn, TokenOut, UserOut
from ..utils.security import create_access_token, decode_access_token, hash_password, verify_password
from .exceptions import ConflictError, InvalidCredentials, NotAuthenticated

EMAIL_TAKEN = "An account with this email already exists. Sign in instead."


class AuthService:
    def __init__(self, db: Session, users: UserRepository, settings: Settings):
        self.db = db
        self.users = users
        self.settings = settings

    def _token_for(self, user: User) -> TokenOut:
        token = create_access_token(user.id, self.settings.secret_key, self.settings.access_token_expire_minutes)
        return TokenOut(access_token=token, user=UserOut.model_validate(user))

    def register(self, data: RegisterIn) -> TokenOut:
        if self.users.get_by_email(data.email):
            raise ConflictError(EMAIL_TAKEN)
        try:
            user = self.users.add(User(email=data.email, name=data.name, hashed_password=hash_password(data.password)))
            self.db.commit()
        except IntegrityError:  # two sign-ups for the same email at once
            self.db.rollback()
            raise ConflictError(EMAIL_TAKEN) from None
        return self._token_for(user)

    def login(self, data: LoginIn) -> TokenOut:
        user = self.users.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise InvalidCredentials("Email or password is incorrect.")
        return self._token_for(user)

    def user_from_token(self, token: str | None) -> CurrentUser:
        user_id = decode_access_token(token, self.settings.secret_key) if token else None
        user = self.users.get(user_id) if user_id is not None else None
        if user is None:
            raise NotAuthenticated("Sign in to continue.")
        return CurrentUser.model_validate(user)
