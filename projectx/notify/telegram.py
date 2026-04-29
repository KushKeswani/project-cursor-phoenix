"""Send Telegram messages via Bot API when token and chat id are configured."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


def _telegram_token_and_chat() -> tuple[str, str]:
    token = (
        os.environ.get("PROJECTX_TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    ).strip()
    chat = (
        os.environ.get("PROJECTX_TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID") or ""
    ).strip()
    return token, chat


def _telegram_log_failure(message: str, *, logger: Optional[Any]) -> None:
    if logger:
        logger.warning("Phoenix Telegram: %s", message)
    else:
        print(f"Phoenix Telegram: {message}", flush=True)


def send_telegram_if_configured(body: str, *, logger: Optional[Any] = None) -> None:
    """
    If ``PROJECTX_TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_BOT_TOKEN`` and
    ``PROJECTX_TELEGRAM_CHAT_ID`` / ``TELEGRAM_CHAT_ID`` are set, POST ``body`` to the bot.

    Create a bot with @BotFather, copy the token, then send any message to the bot and read
    ``chat_id`` from ``https://api.telegram.org/bot<token>/getUpdates`` (or use a channel id).

    Long bodies are truncated (~4k chars) for the Telegram message limit.
    Failures are logged (or printed if ``logger`` is omitted); never raised.
    """
    token, chat_id = _telegram_token_and_chat()
    if not token or not chat_id or not (body or "").strip():
        return
    text = body.strip()
    if len(text) > 4000:
        text = text[:3990] + " …(truncated)"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
        except OSError:
            err_body = ""
        _telegram_log_failure(f"HTTP {e.code}: {err_body or getattr(e, 'reason', '')}", logger=logger)
        return
    except urllib.error.URLError as e:
        _telegram_log_failure(f"network error: {e.reason}", logger=logger)
        return
    except OSError as e:
        _telegram_log_failure(str(e), logger=logger)
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        _telegram_log_failure(f"invalid JSON response: {raw[:200]!r}", logger=logger)
        return
    if isinstance(data, dict) and data.get("ok") is False:
        desc = data.get("description") or raw[:300]
        _telegram_log_failure(f"API error: {desc}", logger=logger)
