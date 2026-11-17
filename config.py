"""
Configuration loader.

All sensitive values (the Telegram bot token) are read from environment
variables so that nothing secret is ever committed to git. Copy
``.env.example`` to ``.env``, fill in your token, and this module will pick
it up automatically when ``python-dotenv`` is installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in production
    pass


def _get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(
            f"Environment variable '{name}' is missing. "
            f"Copy '.env.example' to '.env' and fill in your value."
        )
    return value or ""


@dataclass(frozen=True)
class Settings:
    bot_token: str
    qr_error_correction: int  # qrcode.constants level
    qr_box_size: int  # pixel size of each QR module
    qr_border: int  # number of border modules
    max_input_length: int  # safety cap to avoid oversized payloads
    request_timeout: int  # HTTP timeout for Telegram API calls


def load_settings() -> Settings:
    """Load settings from environment variables with safe defaults."""

    import qrcode

    # qrcode error correction: L=7%, M=15%, Q=25%, H=30% of codewords
    correction_map = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    correction_label = _get_env("QR_ERROR_CORRECTION", "M").upper()
    if correction_label not in correction_map:
        correction_label = "M"

    return Settings(
        bot_token=_get_env("BOT_TOKEN", required=True),
        qr_error_correction=correction_map[correction_label],
        qr_box_size=int(_get_env("QR_BOX_SIZE", "10")),
        qr_border=int(_get_env("QR_BORDER", "4")),
        max_input_length=int(_get_env("MAX_INPUT_LENGTH", "1500")),
        request_timeout=int(_get_env("REQUEST_TIMEOUT", "30")),
    )
