from app.utils.security import create_access_token, decode_access_token, hash_password, verify_password

SECRET = "unit-test-secret-at-least-32-bytes-long"


def test_password_hash_round_trip():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong horse", hashed)


def test_verify_password_handles_malformed_hash():
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_access_token_round_trip():
    token = create_access_token(42, SECRET, expire_minutes=5)
    assert decode_access_token(token, SECRET) == 42


def test_decode_rejects_wrong_secret_expired_and_garbage():
    assert decode_access_token(create_access_token(1, SECRET, 5), "another-secret-that-is-32-bytes-long") is None
    assert decode_access_token(create_access_token(1, SECRET, expire_minutes=-1), SECRET) is None
    assert decode_access_token("not.a.jwt", SECRET) is None
