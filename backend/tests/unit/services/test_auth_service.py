import pytest

from app.config import Settings
from app.repository.models import User
from app.schema.auth import LoginIn, RegisterIn
from app.services.auth_service import AuthService
from app.services.exceptions import ConflictError, InvalidCredentials, NotAuthenticated
from app.utils.security import create_access_token, hash_password
from tests.helpers import FakeSession
from tests.unit.services.fakes import FakeUsers

SECRET = "auth-service-test-secret-32-bytes-long"


@pytest.fixture
def svc():
    settings = Settings(_env_file=None, secret_key=SECRET, access_token_expire_minutes=5)
    return AuthService(FakeSession(), FakeUsers(), settings)


def test_register_creates_user_and_returns_working_token(svc):
    out = svc.register(RegisterIn(email="Ann@Example.com", password="password123", name=" Ann "))
    assert (out.user.email, out.user.name, out.token_type) == ("ann@example.com", "Ann", "bearer")
    assert svc.user_from_token(out.access_token).id == out.user.id
    stored = svc.users.get(out.user.id)
    assert stored.hashed_password != "password123" and svc.db.commits == 1


def test_register_duplicate_email_conflicts(svc):
    svc.register(RegisterIn(email="ann@example.com", password="password123"))
    with pytest.raises(ConflictError, match="already exists"):
        svc.register(RegisterIn(email="ANN@example.com", password="password123"))


def test_login(svc):
    svc.users.add(User(email="ann@example.com", name="Ann", hashed_password=hash_password("password123")))
    assert svc.login(LoginIn(email="ann@example.com", password="password123")).user.email == "ann@example.com"
    for email, password in [("ann@example.com", "wrong-pass"), ("nobody@example.com", "password123")]:
        with pytest.raises(InvalidCredentials, match="Email or password is incorrect."):
            svc.login(LoginIn(email=email, password=password))


@pytest.mark.parametrize("token", [None, "", "garbage", create_access_token(1, "some-other-secret-32-bytes-long!!", 5),
                                   create_access_token(999, SECRET, 5)])
def test_user_from_token_rejects_invalid_or_unknown(svc, token):
    with pytest.raises(NotAuthenticated, match="Sign in to continue."):
        svc.user_from_token(token)
