# Telegram helpers (Project Cursor root)

Small tools that **do not** live under `projectx/`. They only read the **repository root** `.env` (copy from `.env.example` one level up).

## Get your `chat_id`

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Add to **Project Cursor** root `.env`: `PROJECTX_TELEGRAM_BOT_TOKEN=...`
3. In Telegram, open your bot → **Start** → send any message.
4. From the **Project Cursor** directory run:

```bash
python3 telegram/chat_id_helper.py
```

5. Add the printed `PROJECTX_TELEGRAM_CHAT_ID=...` to the same `.env`.

Phoenix / scripts still use the same variable names; `projectx` continues to load root `.env` + `projectx/.env` for the main app.
