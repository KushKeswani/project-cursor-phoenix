#!/usr/bin/env python3
"""Print Telegram chat ids using your bot token (same var names as Phoenix notifications).

1. Create a bot with @BotFather → copy the API token.
2. Put it in the **Project Cursor root** ``.env`` as ``PROJECTX_TELEGRAM_BOT_TOKEN``.
3. Message your bot (Start + “hi”).
4. From the Project Cursor root run::

       python3 telegram/chat_id_helper.py

Loads **only** ``<repo root>/.env`` — does not import ``projectx``.

Exit codes: 0 if ok or empty updates with instructions; 1 if token missing or API error.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Project Cursor repo root (parent of telegram/)
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_root_dotenv() -> None:
    """Parse repo-root ``.env`` into ``os.environ`` (does not override existing env)."""
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


def _token() -> str:
    return (
        os.environ.get("PROJECTX_TELEGRAM_BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()


def main() -> int:
    _load_root_dotenv()
    token = _token()
    if not token:
        print(
            "Set PROJECTX_TELEGRAM_BOT_TOKEN (or TELEGRAM_BOT_TOKEN) in .env "
            f"at {_REPO_ROOT}",
            file=sys.stderr,
        )
        return 1

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        print(f"Telegram HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"Invalid JSON: {raw[:300]!r}", file=sys.stderr)
        return 1

    if not isinstance(data, dict) or data.get("ok") is not True:
        print(f"Unexpected response: {raw[:500]}", file=sys.stderr)
        return 1

    updates = data.get("result") or []
    if not updates:
        print(
            "No messages yet. In Telegram: open your bot → Start → send “hi”. "
            "Then run this script again."
        )
        return 0

    seen: set[int] = set()
    for u in updates:
        if not isinstance(u, dict):
            continue
        msg = u.get("message") or u.get("edited_message") or u.get("channel_post")
        if not isinstance(msg, dict):
            continue
        chat = msg.get("chat") or {}
        if not isinstance(chat, dict):
            continue
        cid = chat.get("id")
        if cid is None:
            continue
        try:
            icid = int(cid)
        except (TypeError, ValueError):
            continue
        if icid in seen:
            continue
        seen.add(icid)
        title = chat.get("title") or chat.get("username") or chat.get("first_name") or ""
        kind = chat.get("type", "?")
        print(f"chat_id={icid}  type={kind}  name={title!s}")

    if not seen:
        print(
            "Updates exist but no chat id parsed. Try sending your bot a new message "
            "or add the bot to a group and send a message there."
        )
    else:
        print()
        if len(seen) == 1:
            only = next(iter(seen))
            print("Put this in .env:")
            print(f"PROJECTX_TELEGRAM_CHAT_ID={only}")
        else:
            print(
                "Several chats seen — pick the row that is **your** DM with the bot "
                "(type=private) or your group, then set PROJECTX_TELEGRAM_CHAT_ID to that number."
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
