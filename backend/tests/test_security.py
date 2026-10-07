"""Unit tests for password hashing and JWT handling (docs/07-testing-strategy.md section 2)."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import UnauthorizedException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# --- Password hashing -------------------------------------------------------

def test_hash_password_returns_hash_not_plaintext():
    password = "Password123!"

    hashed = hash_password(password)

    assert hashed != password
    assert password not in hashed
    # Argon2 hashes are self-describing and start with the algorithm id.
    assert hashed.startswith("$argon2")


def test_verify_password_accepts_correct_password():
    hashed = hash_password("Password123!")

    assert verify_password("Password123!", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("Password123!")

    assert verify_password("WrongPassword123!", hashed) is False


def test_same_password_produces_different_hashes():
    """Each hash must be salted, otherwise identical passwords look identical."""
    first = hash_password("Password123!")
    second = hash_password("Password123!")

    assert first != second
    assert verify_password("Password123!", first) is True
    assert verify_password("Password123!", second) is True


def test_verify_password_handles_malformed_hash():
    """A corrupted stored hash must not raise; it must simply not verify."""
    assert verify_password("Password123!", "not-a-real-hash") is False


# --- JWT creation and decoding ---------------------------------------------

def test_create_and_decode_access_token_round_trip():
    user_id = uuid4()

    token = create_access_token(user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]


def test_token_does_not_contain_sensitive_data():
    """Only identifiers and timing belong in the payload."""
    token = create_access_token(uuid4())

    payload = decode_access_token(token)

    assert set(payload) == {"sub", "iat", "exp", "type"}


def test_decode_rejects_expired_token():
    token = create_access_token(uuid4(), expires_delta=timedelta(seconds=-10))

    with pytest.raises(UnauthorizedException):
        decode_access_token(token)


def test_decode_rejects_token_signed_with_another_secret(monkeypatch):
    from app.core import config

    token = create_access_token(uuid4())

    # Simulate a token forged with a different key.
    monkeypatch.setattr(config.settings, "SECRET_KEY", "a-completely-different-secret")

    with pytest.raises(UnauthorizedException):
        decode_access_token(token)


def test_decode_rejects_garbage_token():
    with pytest.raises(UnauthorizedException):
        decode_access_token("this.is.not.a.jwt")


def test_decode_rejects_token_of_another_type():
    """Tokens that are not access tokens (e.g. future refresh tokens) are refused."""
    from jose import jwt

    from app.core.config import settings

    token = jwt.encode(
        {"sub": str(uuid4()), "type": "refresh"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(UnauthorizedException):
        decode_access_token(token)