"""ProjectX user hub (SignalR): accounts, orders, positions, trades."""

from __future__ import annotations

import logging
import threading
import urllib.parse
from typing import Any, Callable, Optional

from projectx.api.auth import ProjectXAuth

try:
    from signalrcore.hub_connection_builder import HubConnectionBuilder
    from signalrcore.types import HttpTransportType

    _HAS_SIGNALR = True
except ImportError:
    HubConnectionBuilder = None  # type: ignore[misc, assignment]
    HttpTransportType = None  # type: ignore[misc, assignment]
    _HAS_SIGNALR = False


class UserHubListener:
    """
    Subscribes to GatewayUser* events and forwards to StateManager callables.
    Token is embedded in the hub URL per ProjectX docs (WebSockets, skip negotiation).
    """

    def __init__(
        self,
        hub_base_url: str,
        auth: ProjectXAuth,
        account_id: int,
        *,
        on_account: Callable[[dict[str, Any]], None],
        on_order: Callable[[dict[str, Any]], None],
        on_position: Callable[[dict[str, Any]], None],
        on_trade: Callable[[dict[str, Any]], None],
        logger: Optional[logging.Logger] = None,
    ):
        self._hub_base = hub_base_url.rstrip("/")
        self._auth = auth
        self._account_id = account_id
        self._on_account = on_account
        self._on_order = on_order
        self._on_position = on_position
        self._on_trade = on_trade
        self._log = logger or logging.getLogger("projectx.realtime")
        self._conn: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def _hub_url_with_token(self) -> str:
        token = self._auth.get_token()
        encoded = urllib.parse.quote(token, safe="")
        sep = "&" if "?" in self._hub_base else "?"
        return f"{self._hub_base}{sep}access_token={encoded}"

    def _subscribe(self) -> None:
        assert self._conn is not None
        self._conn.invoke("SubscribeAccounts", [])
        self._conn.invoke("SubscribeOrders", [self._account_id])
        self._conn.invoke("SubscribePositions", [self._account_id])
        self._conn.invoke("SubscribeTrades", [self._account_id])

    def _attach_handlers(self) -> None:
        assert self._conn is not None

        def _acc(data: Any) -> None:
            if isinstance(data, dict):
                self._on_account(data)

        def _ord(data: Any) -> None:
            if isinstance(data, dict):
                self._on_order(data)

        def _pos(data: Any) -> None:
            if isinstance(data, dict):
                self._on_position(data)

        def _trd(data: Any) -> None:
            if isinstance(data, dict):
                self._on_trade(data)

        self._conn.on("GatewayUserAccount", _acc)
        self._conn.on("GatewayUserOrder", _ord)
        self._conn.on("GatewayUserPosition", _pos)
        self._conn.on("GatewayUserTrade", _trd)

    def start_background(self) -> None:
        if not _HAS_SIGNALR:
            self._log.warning(
                "signalrcore not installed; realtime disabled "
                "(pip install signalrcore websocket-client)"
            )
            return

        def _run() -> None:
            try:
                self._run_loop()
            except Exception as e:
                self._log.exception("User hub crashed: %s", e)

        self._thread = threading.Thread(target=_run, name="projectx-user-hub", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            url = self._hub_url_with_token()
            builder = HubConnectionBuilder().with_url(
                url,
                options={
                    "skip_negotiation": True,
                    "transport": HttpTransportType.web_sockets,
                },
            ).with_automatic_reconnect(
                {"type": "raw", "reconnect_interval": 5, "max_attempts": None}
            )
            self._conn = builder.build()
            self._attach_handlers()

            def _on_open() -> None:
                self._log.info("RTC user hub connected")
                try:
                    self._subscribe()
                except Exception as e:
                    self._log.error("Subscribe failed: %s", e)

            def _on_reconnect(_: Any = None) -> None:
                self._log.warning("RTC user hub reconnected; resubscribing")
                try:
                    self._subscribe()
                except Exception as e:
                    self._log.error("Resubscribe failed: %s", e)

            self._conn.on_open(_on_open)
            self._conn.on_reconnect(_on_reconnect)
            self._conn.on_close(lambda: self._log.warning("RTC user hub closed"))

            try:
                ok = self._conn.start()
                if not ok:
                    raise RuntimeError("transport start returned False")
            except Exception as e:
                self._log.error("RTC start error: %s", e)
                if self._stop.wait(10):
                    break
                continue

            self._stop.wait()
            try:
                self._conn.stop()
            except Exception:
                pass
            self._conn = None

    def stop(self) -> None:
        self._stop.set()
        if self._conn is not None:
            try:
                self._conn.stop()
            except Exception:
                pass
