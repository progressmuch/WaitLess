"""Reusable field validators shared by request schemas."""

import re

# Pragmatic email pattern check. Deliberately simple: the goal is to reject
# obvious typos and to guarantee a stable uniqueness key, not to implement
# RFC 5322. Swap for the `email-validator` package if stricter checks are needed.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_EMAIL_LENGTH = 320
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def normalize_email(value: str) -> str:
    """Trim and lower-case an email address, rejecting invalid values.

    Raises:
        ValueError: if the value is empty or not a plausible email address.
    """
    normalized = (value or "").strip().lower()
    if not normalized:
        raise ValueError("Email address is required")
    if len(normalized) > MAX_EMAIL_LENGTH:
        raise ValueError("Email address is too long")
    if not EMAIL_PATTERN.match(normalized):
        raise ValueError("Invalid email address")
    return normalized