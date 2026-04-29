"""Pre-trade gates: session, size, daily loss, drawdown, kill switch, etc."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from projectx.state.state_manager import StateManager
from projectx.utils.helpers import now_ny, within_session


@dataclass
class RiskConfig:
    max_daily_loss_usd: float
    max_drawdown_from_peak_usd: float
    max_position_contracts: int
    max_trades_per_day: int
    max_consecutive_losses: int
    ny_session_enabled: bool
    ny_session_start: str
    ny_session_end: str
    emergency_halt: bool
    kill_switch_path: Optional[str] = None


class RiskCheckError(Exception):
    """Raised when a signal fails risk checks (expected control flow)."""


class RiskManager:
    def __init__(self, cfg: RiskConfig, state: StateManager):
        self._cfg = cfg
        self._state = state

    def validate_signal(
        self,
        signal: dict[str, Any],
        *,
        require_price_brackets: bool = True,
        ignore_ny_session: bool = False,
    ) -> None:
        if self._cfg.emergency_halt:
            raise RiskCheckError("emergency_halt is enabled in config")
        ks = self._cfg.kill_switch_path
        if ks and Path(ks).expanduser().exists():
            raise RiskCheckError(f"kill switch file present: {ks}")

        if self._cfg.ny_session_enabled and not ignore_ny_session:
            if not within_session(
                now_ny(), self._cfg.ny_session_start, self._cfg.ny_session_end
            ):
                raise RiskCheckError(
                    "outside configured NY session window "
                    "(use --ignore-ny-session for nearly-24h futures)"
                )

        if not self._state.can_trade:
            raise RiskCheckError("account canTrade is false")

        size = int(signal.get("size", 0))
        if size < 1:
            raise RiskCheckError("size must be >= 1")
        if size > self._cfg.max_position_contracts:
            raise RiskCheckError(
                f"size {size} exceeds max_position_contracts "
                f"{self._cfg.max_position_contracts}"
            )

        d = self._state.daily
        if d.trades_count >= self._cfg.max_trades_per_day:
            raise RiskCheckError("max_trades_per_day reached")

        if d.consecutive_losses >= self._cfg.max_consecutive_losses:
            raise RiskCheckError("max_consecutive_losses reached")

        if d.session_start_balance is not None:
            dd = d.session_start_balance - self._state.balance
            if dd >= self._cfg.max_daily_loss_usd:
                raise RiskCheckError("max_daily_loss_usd breached (session start vs now)")

        if d.peak_balance is not None:
            dd_peak = d.peak_balance - self._state.balance
            if dd_peak >= self._cfg.max_drawdown_from_peak_usd:
                raise RiskCheckError("max_drawdown_from_peak_usd breached")

        if require_price_brackets:
            if signal.get("stop_loss") is None or signal.get("take_profit") is None:
                raise RiskCheckError("stop_loss and take_profit are required")

            if signal.get("reference_price") is None:
                raise RiskCheckError("reference_price is required for bracket tick math")
