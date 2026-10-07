"""Password hashing and JSON Web Token helpers.

Phase 0 shipped this module as a placeholder. Phase 1 implements it:

* Password hashing uses Argon2id through `pwdlib` (one-way, salted).
  Plaintext passwords are never stored or logged.
* Access tokens are JWTs signed with `settings.SECRET_KEY`. The payload only
  contains non-sensitive claims (`sub`, `iat`, `exp`, `type`); the user's role
  and active flag are read from the database on every request so that a
  disabled account or a role change takes effect immediately.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings
from app.core.exceptions import UnauthorizedException

# Argon2id is the only accepted algorithm. pwdlib verifies the parameters that
# are embedded in the stored hash, so previously created hashes keep working.
password_hash = PasswordHash((Argon2Hasher(),))

# Claim used to tell access tokens apart from any future token type
# (refresh tokens, password-reset tokens, ...).
TOKEN_TYPE_ACCESS = "access"

# Hash of a random value, used to keep failed logins roughly as slow as
# successful ones when the email address does not exist. This prevents
# timing-based user enumeration.
_DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-password-" + "x" * 32)


def hash_password(password: str) -> str:
    """Return a salted Argon2id hash for the given plaintext password."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True when `password` matches `hashed_password`.

    Never raises: malformed or legacy hashes are treated as a failed match so
    that a corrupted row cannot crash the login endpoint.
    """
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: UUID | str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token for the given user id."""
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Only non-sensitive identifiers go into the token.
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": TOKEN_TYPE_ACCESS,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate a JWT access token and return its claims.

    Raises:
        UnauthorizedException: if the token is malformed, tampered with,
            signed with a different key, expired, or is not an access token.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise UnauthorizedException(
            "Invalid or expired authentication token"
        ) from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise UnauthorizedException("Invalid token type")

    return payload
