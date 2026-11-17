"""
Input validation helpers.

These helpers only check shape and length. They never execute, parse or
dereference user content, so there is no injection surface here. URLs are
validated structurally; we never fetch them.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Telegram message text cap. We stay well under it.
_HARD_TEXT_LIMIT = 4096

# QR alphanumeric mode fits ~2953 chars at the highest correction level;
# we keep a generous but safe ceiling.
_DEFAULT_MAX_LENGTH = 1500

# A reasonably strict URL pattern. Scheme must be http/https.
_URL_RE = re.compile(
    r"^https?://"
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"[A-Z]{2,63}"
    r"(?::\d{1,5})?"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)


class InvalidInputError(ValueError):
    """Raised when user input cannot be turned into a QR code."""


def normalize_input(raw: str) -> str:
    """Trim surrounding whitespace and drop zero-width chars from the text."""

    if raw is None:
        raise InvalidInputError("Empty input.")
    text = raw.strip()
    # Strip common invisible characters that could be used to hide payload.
    text = re.sub(r"[\u200b-\u200f\u2028-\u202f\u2060\ufeff]", "", text)
    if not text:
        raise InvalidInputError("Empty input.")
    return text


def validate_text(text: str, max_length: int = _DEFAULT_MAX_LENGTH) -> str:
    """Validate free text that will be encoded into the QR code."""

    text = normalize_input(text)
    if len(text) > max_length:
        raise InvalidInputError(
            f"Text is too long ({len(text)} chars). Maximum is {max_length}."
        )
    if len(text) > _HARD_TEXT_LIMIT:
        raise InvalidInputError("Text exceeds Telegram message limits.")
    return text


def is_url(text: str) -> bool:
    """Return True if ``text`` looks like a valid http/https URL."""

    try:
        text = normalize_input(text)
    except InvalidInputError:
        return False
    return bool(_URL_RE.match(text))


def validate_url(text: str, max_length: int = _DEFAULT_MAX_LENGTH) -> str:
    """Validate a URL structurally. Does NOT fetch the URL."""

    text = validate_text(text, max_length=max_length)
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise InvalidInputError("Only http and https URLs are supported.")
    if not parsed.netloc or "." not in parsed.netloc:
        raise InvalidInputError("URL seems to be missing a valid domain.")
    return text


def classify(text: str, max_length: int = _DEFAULT_MAX_LENGTH) -> str:
    """
    Return the validated string that should be encoded into the QR code.

    We accept both plain URLs and arbitrary text. URLs are normalised to
    guarantee a scheme, plain text is accepted as-is. Anything that fails
    validation raises ``InvalidInputError`` so the caller can reply with a
    friendly error message.
    """

    text = validate_text(text, max_length=max_length)
    if is_url(text):
        return validate_url(text, max_length=max_length)
    return text
