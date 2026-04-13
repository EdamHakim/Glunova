import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost:5432/x")
os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.core import security  # noqa: E402


def test_hash_password() -> None:
    h = security.hash_password("Str0ngPass!")
    assert security.verify_password("Str0ngPass!", h)
    assert not security.verify_password("wrong", h)


def test_jwt_access_roundtrip() -> None:
    token = security.create_access_token("550e8400-e29b-41d4-a716-446655440000")
    payload = security.decode_token(token)
    security.verify_token_type(payload, "access")
    assert payload["sub"] == "550e8400-e29b-41d4-a716-446655440000"
