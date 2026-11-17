# Telegram QR Bot

A small, self-contained Telegram bot written in **pure Python** that turns any
text or URL into a QR code image. The bot replies with a PNG and a short
caption: *"Here is your QR code"*.

If the user sends something invalid (empty text, an image, a sticker, a
document, or text that is too long), the bot replies with a friendly message
asking for valid input.

---

## Features

- Accepts plain text and `http` / `https` URLs.
- Replies with a QR code PNG and the caption *"Here is your QR code"*.
- Validates input and rejects anything that cannot be encoded.
- Asks the user for text/URL when a photo, sticker or file is sent.
- Reads the bot token from an environment variable — nothing secret is ever
  hardcoded.
- No temporary files on disk: QR images are rendered entirely in memory.
- Global error handler so the bot never crashes silently on a bad message.

---

## Project layout

```
telegram-qr-bot/
├── bot.py              # Entry point: Telegram handlers
├── qr_generator.py     # QR rendering (in-memory PNG)
├── validators.py       # Input validation & classification
├── config.py           # Loads settings from environment / .env
├── requirements.txt    # Python dependencies
├── .env.example        # Template for your secret config
├── .gitignore          # Keeps secrets & artifacts out of git
├── LICENSE             # MIT
└── README.md           # This file
```

---

## Setup

### 1. Create the bot and get a token

1. Open Telegram and talk to [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow the prompts.
3. Copy the **HTTP API token** it gives you.

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Python 3.11 or newer is required (works on 3.11, 3.12, 3.13 and 3.14 on
Windows, macOS and Linux). The project uses:
- `python-telegram-bot` v22.4+ (needed for Python 3.14's `asyncio` changes),
- qrcode's **pure-Python PNG factory** so it does **not** depend on Pillow,
  meaning no C compiler or native libraries are needed at install time.

### 3. Configure the token

```bash
cp .env.example .env
```

Open `.env` and paste your token:

```
BOT_TOKEN=123456789:abcdef-your-token-here
```

The `.gitignore` already excludes `.env`, so your token will never be
committed by accident.

### 4. Run the bot

```bash
python bot.py
```

Open your bot in Telegram, send `/start`, then send any URL or text. You
should get a QR image back.

---

## Security notes

This project was built with publishing on GitHub in mind.

- **No hardcoded secrets.** The token is read from the `BOT_TOKEN`
  environment variable via `config.py`. `.env.example` contains only a
  placeholder.
- **`.env` is git-ignored.** Only `.env.example` is committed.
- **Input validation.** `validators.py` rejects empty input, strips
  zero-width characters that could hide payloads, caps the length
  (default 1500 chars), and only accepts `http`/`https` URLs.
- **No URL fetching.** URLs are validated structurally only; the bot
  never opens a network connection to the user-supplied URL.
- **No disk writes.** QR images are rendered with `io.BytesIO` and sent
  directly to Telegram, so there is no path traversal or temp-file race.
- **No shell execution.** Nothing the user sends is ever passed to a
  shell or to `eval`/`exec`.
- **HTML-escaped error messages.** Any user-supplied text that appears
  in an error reply is escaped with `html.escape`.
- **Global error handler.** Unexpected exceptions are logged and the
  user gets a generic "something went wrong" message, never a stack
  trace.
- **Sanitised logging.** Logs record lengths and events, never the raw
  token or full payload contents.
- **HTTP timeouts.** All Telegram API calls have explicit timeouts so a
  slow network cannot hang the bot.

### Before you push to GitHub

1. Double-check that `.env` is **not** staged: `git status`
2. Search the repo for any token you may have pasted by accident:
   ```bash
   git grep -nE "[0-9]{8,}:[A-Za-z0-9_-]{30,}"
   ```
3. If you ever leak a token, **revoke it immediately** in
   [@BotFather](https://t.me/BotFather) with `/revoke`, then generate a
   new one.

---

## Optional configuration

All of these are optional and have sensible defaults in `.env.example`.

| Variable                     | Default           | Description                                                        |
| ---------------------------- | ----------------- | ------------------------------------------------------------------ |
| `BOT_TOKEN`                  | —                 | Required. Telegram bot token.                                      |
| `QR_ERROR_CORRECTION`        | `M`               | `L` / `M` / `Q` / `H` (more = bigger QR).                          |
| `QR_BOX_SIZE`                | `10`              | Pixel size of each QR module.                                      |
| `QR_BORDER`                  | `4`               | Quiet-zone modules around the QR.                                  |
| `MAX_INPUT_LENGTH`           | `1500`            | Max characters accepted from the user.                             |
| `REQUEST_TIMEOUT`            | `30`              | HTTP timeout (seconds) for Telegram API calls                      |
| `REQUIRED_CHANNEL_USERNAME`  | `@gifthubai`      | Channel the user must join before the bot responds.                |
| `REQUIRED_CHANNEL_URL`       | `https://t.me/gifthubai` | Public URL shown in the subscribe prompt.                    |
| `SUPPORT_USERNAME`           | `@vxgiyx`         | Username shown in the `/start` greeting as the support contact.    |

---

## Obligatory channel subscription

The bot refuses to generate QR codes until the user has joined
`@gifthubai`. The check uses `Bot.get_chat_member`, so **the bot must be
added as an administrator in the `@gifthubai` channel** (with at least the
*Read* permission). If you skip this step the API call will fail and the
bot falls back to allowing the request through (logged as a warning) so a
misconfiguration never hard-blocks users.

Subscription status is cached per user for 30 seconds to avoid hammering
the Telegram API.

---

## How it works

1. User sends a text message.
2. `validators.classify()` trims, strips hidden characters, caps length,
   and decides whether the content is a URL or plain text.
3. `qr_generator.generate_qr_png()` renders the validated payload as a
   PNG entirely in memory.
4. `bot.py` sends the PNG back as a photo with the caption
   *"Here is your QR code"*.
5. If validation or rendering fails, the bot replies with an
   HTML-escaped error message asking the user for valid input.

---

## License

MIT — see [LICENSE](LICENSE).
