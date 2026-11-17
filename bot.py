"""
Telegram bot entry point.

Run with:
    python bot.py

The token is read from the BOT_TOKEN environment variable (see .env.example).
The bot:
  * Greets the user on /start and /help.
  * Accepts text or URL messages and replies with a QR code PNG image.
  * Asks the user for valid input whenever the message is empty, too long,
    or otherwise unusable.
  * Asks for text/URL when the user sends a photo, sticker or document,
    because raw binary media cannot be encoded into a QR code directly.
"""

from __future__ import annotations

import html
import io
import logging
import sys
import time
import traceback
from typing import Dict, Tuple

from telegram import Update
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import validators
from config import Settings, load_settings
from qr_generator import generate_qr_png
from validators import InvalidInputError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
# Telegram library is noisy on DEBUG; keep it on INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)

logger = logging.getLogger("qr-bot")

CAPTION = "Here is your QR code"

# ---------------------------------------------------------------------------
# Obligatory channel subscription + support contact
# ---------------------------------------------------------------------------
#
# Every user must join CHANNEL before they can use the bot. The check is
# performed via ``Bot.get_chat_member``. For this to work, the bot MUST be
# added as an administrator in @gifthubai (otherwise the API returns an
# error and we fall back to allowing the request through).
#
# These values can be overridden via environment variables if you ever want
# to reuse the code for a different brand.

import os as _os

CHANNEL_USERNAME = _os.getenv("REQUIRED_CHANNEL_USERNAME", "@gifthubai")
CHANNEL_URL = _os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/gifthubai")
SUPPORT_USERNAME = _os.getenv("SUPPORT_USERNAME", "@vxgiyx")

# Cache (user_id -> (timestamp, is_subscribed)) so we do not hammer the API.
_SUBSCRIPTION_TTL_SECONDS = 30
_subscription_cache: Dict[int, Tuple[float, bool]] = {}

GREETING_TEXT = (
    "Hi. Send me any text or a URL (http/https) and I will turn it into a QR code.\n\n"
    f"Support: {SUPPORT_USERNAME}"
)

NOT_SUBSCRIBED_TEXT = (
    "To use this bot, please subscribe to our channel first:\n"
    f"{CHANNEL_URL}\n\n"
    "After joining, send /start again."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _is_subscribed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if the user has joined the required channel.

    Falls back to True on API errors (e.g. the bot is not an admin in the
    channel) so the bot never hard-blocks users because of a misconfiguration.
    """

    user = update.effective_user
    if user is None:
        return False

    now = time.monotonic()
    cached = _subscription_cache.get(user.id)
    if cached is not None and now - cached[0] < _SUBSCRIPTION_TTL_SECONDS:
        return cached[1]

    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        subscribed = member.status not in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        )
    except Exception as exc:  # noqa: BLE001 - log and fail open
        logger.warning(
            "Subscription check failed for user %s: %s. Allowing request.",
            user.id,
            exc,
        )
        subscribed = True

    _subscription_cache[user.id] = (now, subscribed)
    return subscribed


async def _reply_with_qr(update: Update, payload: str, settings: Settings) -> None:
    """Render a QR for ``payload`` and send it back as a PNG photo."""

    png_bytes = generate_qr_png(payload, settings)

    # Send directly from memory; no temp files on disk.
    await update.message.reply_photo(
        photo=io.BytesIO(png_bytes),
        caption=CAPTION,
        parse_mode=ParseMode.HTML,
    )
    logger.info("Sent QR for payload of %d chars.", len(payload))


async def _reply_invalid(update: Update, reason: str) -> None:
    """Send a friendly, HTML-escaped error message asking for valid input."""

    safe_reason = html.escape(reason)
    text = (
        "That input is invalid.\n"
        f"<i>Reason:</i> {safe_reason}\n\n"
        "Please send valid text or a URL (http/https) so I can generate your QR code."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_subscribed(update, context):
        await update.message.reply_text(NOT_SUBSCRIBED_TEXT)
        return
    await update.message.reply_text(GREETING_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_subscribed(update, context):
        await update.message.reply_text(NOT_SUBSCRIBED_TEXT)
        return
    await update.message.reply_text(GREETING_TEXT)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text / URL messages: check subscription, then QR."""

    if not await _is_subscribed(update, context):
        await update.message.reply_text(NOT_SUBSCRIBED_TEXT)
        return

    settings: Settings = context.bot_data["settings"]
    raw_text = update.message.text or ""

    try:
        payload = validators.classify(raw_text, max_length=settings.max_input_length)
    except InvalidInputError as exc:
        await _reply_invalid(update, str(exc))
        return

    try:
        await _reply_with_qr(update, payload, settings)
    except InvalidInputError as exc:
        await _reply_invalid(update, str(exc))
    except Exception:  # noqa: BLE001 - we want to log everything
        logger.error("QR generation failed:\n%s", traceback.format_exc())
        await _reply_invalid(update, "Could not generate the QR code. Please try again.")


async def non_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Photos, stickers, documents, voice... none of these can go into a QR."""

    if not await _is_subscribed(update, context):
        await update.message.reply_text(NOT_SUBSCRIBED_TEXT)
        return

    await _reply_invalid(
        update,
        "Images and files cannot be encoded into a QR code directly. "
        "Send the text or URL you want to encode instead.",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler so the bot never silently crashes on a user."""

    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Something went wrong on my side. Please try again."
            )
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def build_application(settings: Settings) -> Application:
    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .read_timeout(settings.request_timeout)
        .write_timeout(settings.request_timeout)
        .connect_timeout(settings.request_timeout)
        .pool_timeout(settings.request_timeout)
        .build()
    )

    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    # Text only (no commands, no captions).
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
    )
    # Anything that is not text: photos, stickers, documents, voice, video...
    app.add_handler(
        MessageHandler(~filters.TEXT & ~filters.COMMAND, non_text_handler)
    )

    app.add_error_handler(error_handler)
    return app


def main() -> None:
    settings = load_settings()
    app = build_application(settings)

    logger.info("Starting QR bot. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
