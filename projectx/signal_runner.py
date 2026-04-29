"""Watch a directory for JSON trade signals and route to the executor."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from projectx.execution.executor import ExecutionError, Executor


def _default_inbox() -> Path:
    return Path(__file__).resolve().parent / "signals" / "inbox"


def process_signal_file(
    path: Path,
    executor: Executor,
    imap: dict[str, dict[str, Any]],
    logger: Any,
) -> None:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("signal must be a JSON object")

    sym = str(data.get("symbol", "")).upper()
    inst = imap.get(sym)
    if not inst:
        raise ValueError(f"Unknown symbol {sym!r}; add to settings trading.instruments")

    sim = bool(data.get("sim_contract_search", False))
    live_param: Optional[bool] = False if sim else None
    ign_ny = bool(data.get("ignore_ny_session", False))

    sig_id = str(data.get("signal_id") or "").strip() or f"file-{uuid.uuid4().hex[:16]}"
    base_tag = str(data.get("custom_tag") or "").strip()
    uniq = uuid.uuid4().hex[:10]
    tag = (f"{base_tag}-{uniq}" if base_tag else f"sig-{uniq}")[:200]

    if data.get("risk_usd") is not None and data.get("reward_usd") is not None:
        result = executor.execute_dollar_risk_bracket(
            symbol=sym,
            side=str(data.get("side", "long")),
            size=int(data["size"]),
            risk_usd=float(data["risk_usd"]),
            reward_usd=float(data["reward_usd"]),
            instrument_cfg=inst,
            signal_id=sig_id,
            custom_tag=tag[:200],
            live_contracts=live_param,
            ignore_ny_session=ign_ny,
        )
        logger.info("Dollar-bracket result: %s", result)
        return

    signal = {
        "symbol": sym,
        "side": data.get("side", "long"),
        "size": int(data["size"]),
        "reference_price": float(data["reference_price"]),
        "stop_loss": float(data["stop_loss"]),
        "take_profit": float(data["take_profit"]),
        "signal_id": sig_id,
        "custom_tag": tag[:200],
    }
    result = executor.execute_signal(signal, inst)
    logger.info("Price-bracket result: %s", result)


def watch_signals_loop(
    inbox: Path,
    poll_seconds: float,
    executor: Executor,
    imap: dict[str, dict[str, Any]],
    logger: Any,
    stop: threading.Event,
) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    base = inbox.parent
    processed = base / "processed"
    failed = base / "failed"
    processed.mkdir(parents=True, exist_ok=True)
    failed.mkdir(parents=True, exist_ok=True)

    while not stop.is_set():
        paths = sorted(inbox.glob("*.json"))
        for path in paths:
            if stop.is_set():
                break
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            try:
                process_signal_file(path, executor, imap, logger)
                dest = processed / f"{ts}_{path.name}"
                path.rename(dest)
                logger.info("Signal file moved to %s", dest)
            except Exception as e:
                logger.exception("Signal file failed %s: %s", path, e)
                try:
                    path.rename(failed / f"{ts}_{path.name}")
                except OSError:
                    pass
        stop.wait(timeout=max(0.5, poll_seconds))


def start_signal_watcher_thread(
    inbox: Path,
    poll_seconds: float,
    executor: Executor,
    imap: dict[str, dict[str, Any]],
    logger: Any,
) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()

    def _run() -> None:
        try:
            watch_signals_loop(inbox, poll_seconds, executor, imap, logger, stop)
        except Exception as e:
            logger.exception("Signal watcher crashed: %s", e)

    t = threading.Thread(target=_run, name="projectx-signals", daemon=True)
    t.start()
    return t, stop
