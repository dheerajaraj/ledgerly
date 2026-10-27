from app.repository.models import User
from app.repository.user_repository import UserRepository


def test_user_repository_lookups(db):
    user = UserRepository(db).add(User(email="a@example.com", name="A", hashed_password="x"))
    repo = UserRepository(db)
    assert repo.get(user.id).email == "a@example.com"
    assert repo.get_by_email("a@example.com").id == user.id
    assert repo.get_by_email("missing@example.com") is None
    assert repo.get(99_999) is None
