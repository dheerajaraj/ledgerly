from app.repository.client_repository import ClientRepository


def test_client_repository_is_scoped_and_sorted(db, make):
    owner, other = make.user("a@example.com"), make.user("b@example.com")
    zeta = make.client(owner, name="Zeta")
    make.client(owner, name="Alpha")
    foreign = make.client(other, name="Foreign")
    repo = ClientRepository(db)

    assert [c.name for c in repo.list_for_user(owner.id)] == ["Alpha", "Zeta"]
    assert repo.get_for_user(owner.id, zeta.id).id == zeta.id
    assert repo.get_for_user(owner.id, foreign.id) is None
