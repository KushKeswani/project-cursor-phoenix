"""Optional Telegram ping when a CLI script finishes (success or failure).

Loads env via ``projectx.utils.helpers.load_dotenv_for_projectx()``: repo-root ``.env``
then ``projectx/.env`` (same order as ``python -m projectx.main``).

Set ``SKIP_TELEGRAM_SCRIPT_DONE=1`` to disable (tests set this via ``tests/conftest.py``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent


def load_projectx_env_if_present() -> None:
    """Populate ``os.environ`` from layered dotenv files (root ``.env`` + ``projectx/.env``)."""
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from projectx.utils.helpers import load_dotenv_for_projectx

        load_dotenv_for_projectx()
    except Exception:
        # Fallback: optional ``python-dotenv`` missing — parse repo ``projectx/.env`` manually.
        for path in (_REPO_ROOT / ".env", _REPO_ROOT / "projectx" / ".env"):
            if not path.is_file():
                continue
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


def _skip_notify() -> bool:
    return os.environ.get("SKIP_TELEGRAM_SCRIPT_DONE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def notify_script_finished(
    script_name: str,
    *,
    exit_code: int = 0,
    exc: BaseException | None = None,
    detail: str = "",
) -> None:
    if _skip_notify():
        return
    load_projectx_env_if_present()
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from projectx.notify.telegram import send_telegram_if_configured
    except Exception:
        return
    ok = exit_code == 0 and exc is None
    status = "OK" if ok else "FAILED"
    lines = [f"Script {status}: `{script_name}` (exit {exit_code})"]
    if detail.strip():
        lines.append(detail.strip())
    if exc is not None:
        msg = f"{type(exc).__name__}: {exc}"
        lines.append(msg[:500] + ("…" if len(msg) > 500 else ""))
    send_telegram_if_configured("\n".join(lines))


def run_with_telegram(main_callable, *, script_name: str) -> int:
    """Run ``main_callable()`` (must return int exit code), then Telegram notify."""
    code = 0
    try:
        code = int(main_callable())
    except SystemExit as e:
        c = e.code
        if isinstance(c, int):
            code = c
        elif c is None:
            code = 0
        else:
            try:
                code = int(c)
            except (TypeError, ValueError):
                code = 1
    except KeyboardInterrupt:
        notify_script_finished(script_name, exit_code=130, detail="KeyboardInterrupt")
        raise
    except BaseException as e:
        notify_script_finished(script_name, exit_code=1, exc=e)
        raise
    notify_script_finished(script_name, exit_code=code)
    return code
