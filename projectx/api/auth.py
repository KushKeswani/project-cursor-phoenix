"""API-key login, session JWT, and proactive refresh via /api/Auth/validate."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests

from projectx.api.endpoints import Paths


@dataclass
class AuthConfig:
    base_url: str
    user_name: str
    api_key: str
    refresh_margin_seconds: float = 1800.0
    request_timeout: float = 30.0


class ProjectXAuth:
    """Obtains and refreshes the Gateway session token (~24h); thread-safe."""

    def __init__(self, cfg: AuthConfig, session: Optional[requests.Session] = None):
        self._cfg = cfg
        self._session = session or requests.Session()
        self._lock = threading.RLock()
        self._token: Optional[str] = None
        self._token_obtained_at: float = 0.0
        self._token_ttl_seconds: float = 23 * 3600

    def get_token(self) -> str:
        with self._lock:
            self._ensure_fresh_locked()
            assert self._token is not None
            return self._token

    def _ensure_fresh_locked(self) -> None:
        if self._token is None:
            self._login_locked()
            return
        age = time.monotonic() - self._token_obtained_at
        if age >= self._token_ttl_seconds - self._cfg.refresh_margin_seconds:
            if not self._try_validate_locked():
                self._login_locked()

    def _login_locked(self) -> None:
        url = self._cfg.base_url.rstrip("/") + Paths.AUTH_LOGIN_KEY
        payload = {"userName": self._cfg.user_name, "apiKey": self._cfg.api_key}
        resp = self._session.post(
            url,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self._cfg.request_timeout,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if not data.get("success") or data.get("errorCode", -1) != 0:
            code = data.get("errorCode")
            hint = {
                1: "UserNotFound",
                2: "PasswordVerificationFailed",
                3: "InvalidCredentials (check userName + apiKey and firm API URL)",
                9: "ApiSubscriptionNotFound",
                10: "ApiKeyAuthenticationDisabled",
            }.get(code, "")
            extra = f" ({hint})" if hint else ""
            raise RuntimeError(
                f"loginKey failed: errorCode={code}{extra} "
                f"message={data.get('errorMessage')}"
            )
        token = data.get("token")
        if not token:
            raise RuntimeError("loginKey response missing token")
        self._token = token
        self._token_obtained_at = time.monotonic()

    def _try_validate_locked(self) -> bool:
        url = self._cfg.base_url.rstrip("/") + Paths.AUTH_VALIDATE
        try:
            resp = self._session.post(
                url,
                json={},
                headers=self._authorized_headers(),
                timeout=self._cfg.request_timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (requests.RequestException, ValueError):
            return False
        if not data.get("success") or data.get("errorCode", -1) != 0:
            return False
        new_token = data.get("newToken") or self._token
        if new_token:
            self._token = new_token
            self._token_obtained_at = time.monotonic()
        return True

    def _authorized_headers(self) -> dict[str, str]:
        assert self._token
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

    def force_refresh(self) -> None:
        with self._lock:
            if not self._try_validate_locked():
                self._login_locked()

    def access_token_factory(self) -> Callable[[], str]:
        """For transports that need a live token string (e.g. RTC URL)."""

        def _factory() -> str:
            return self.get_token()

        return _factory
