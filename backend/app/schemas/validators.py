"""Reusable field validators shared by request schemas."""

import re
from datetime import datetime, timezone
from typing import Optional


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Treat a timestamp without an offset as UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)

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


# Route codes are short, upper-case and URL-safe so they can appear in links
# and on signage, e.g. "HR-CHI" for Harare - Chitungwiza.
ROUTE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")


def normalize_required_text(value: Optional[str], label: str) -> str:
    """Trim a required text field, rejecting empty or null values.

    Args:
        value: the raw value, which may be None when the client sent an
            explicit `null`.
        label: human name of the field, used in the error message.

    Raises:
        ValueError: if the value is None, empty or only whitespace.
    """
    if value is None:
        raise ValueError(f"{label} is required")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required")
    return cleaned


def normalize_route_code(value: str) -> str:
    """Trim and upper-case a route code, rejecting invalid values.

    Raises:
        ValueError: if the value is empty, too long or contains characters
            outside A-Z, 0-9, '-' and '_'.
    """
    normalized = (value or "").strip().upper()
    if not ROUTE_CODE_PATTERN.match(normalized):
        raise ValueError(
            "Route code must be 2-64 characters: letters, digits, '-' or '_'"
        )
    return normalized


# Registration plates and fleet numbers are upper-cased identifiers such as
# "ABC 1234" or "BUS-007".
IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 -]{0,31}$")


def normalize_identifier(value: str, label: str) -> str:
    """Trim, upper-case and validate a registration or fleet number.

    Raises:
        ValueError: if the value is empty or longer than 32 characters, or
            contains characters other than letters, digits, spaces and '-'.
    """
    normalized = normalize_required_text(value, label).upper()
    if not IDENTIFIER_PATTERN.match(normalized):
        raise ValueError(
            f"{label} must be 1-32 characters: letters, digits, spaces or '-'"
        )
    return normalized