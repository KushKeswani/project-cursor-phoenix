"""Config loading, time windows, and bracket tick math."""

from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional
from zoneinfo import ZoneInfo

import yaml


def deep_merge(base: MutableMapping[str, Any], override: Mapping[str, Any]) -> None:
    for k, v in override.items():
        if (
            k in base
            and isinstance(base[k], dict)
            and isinstance(v, Mapping)
        ):
            deep_merge(base[k], v)  # type: ignore[arg-type]
        else:
            base[k] = v


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return data


def apply_env_overrides(cfg: MutableMapping[str, Any]) -> None:
    """Optional env: credentials, account id, and API host overrides."""
    cred = cfg.setdefault("credentials", {})
    if os.environ.get("PROJECTX_USERNAME"):
        cred["user_name"] = os.environ["PROJECTX_USERNAME"]
    if os.environ.get("PROJECTX_API_KEY"):
        cred["api_key"] = os.environ["PROJECTX_API_KEY"]
    trade = cfg.setdefault("trading", {})
    if os.environ.get("PROJECTX_ACCOUNT_ID"):
        trade["account_id"] = int(os.environ["PROJECTX_ACCOUNT_ID"])
    api = cfg.setdefault("api", {})
    if os.environ.get("PROJECTX_API_BASE_URL"):
        api["base_url"] = os.environ["PROJECTX_API_BASE_URL"].rstrip("/")
    if os.environ.get("PROJECTX_RTC_USER_HUB"):
        api["rtc_user_hub"] = os.environ["PROJECTX_RTC_USER_HUB"].rstrip("/")


def _merge_dotenv_file(path: Path) -> None:
    """Set os.environ from .env; non-empty keys win. Empty values do not wipe existing vars."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    if not path.is_file():
        return
    for key, val in dotenv_values(path).items():
        if val is None:
            continue
        s = str(val).strip()
        if not s:
            continue
        os.environ[key] = s


def load_dotenv_for_projectx() -> None:
    """Load env files into ``os.environ`` (later files override earlier keys).

    Order:

    1. Optional ``PROJECTX_DOTENV_PATH`` (explicit file).
    2. Repository root ``.env`` (Project Cursor root when this tree is the workspace).
    3. ``projectx/.env`` (Gateway / overrides).

    Requires ``python-dotenv`` (see ``requirements.txt`` / ``projectx/requirements.txt``).
    """
    pkg_root = Path(__file__).resolve().parents[1]
    repo_root = pkg_root.parent
    custom = os.environ.get("PROJECTX_DOTENV_PATH")
    if custom:
        _merge_dotenv_file(Path(custom).expanduser())
    _merge_dotenv_file(repo_root / ".env")
    _merge_dotenv_file(pkg_root / ".env")


def load_settings(config_path: Optional[Path] = None) -> dict[str, Any]:
    load_dotenv_for_projectx()
    root = Path(__file__).resolve().parents[1]
    path = config_path or (root / "config" / "settings.yaml")
    cfg = load_yaml(path)
    apply_env_overrides(cfg)
    return cfg


def now_ny() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


def parse_hhmm(s: str) -> time:
    h, m = s.strip().split(":")
    return time(int(h), int(m))


def within_session(ny_now: datetime, start: str, end: str) -> bool:
    """Inclusive session window in America/New_York (wall clock)."""
    t = ny_now.time()
    a, b = parse_hhmm(start), parse_hhmm(end)
    if a <= b:
        return a <= t <= b
    return t >= a or t <= b


def round_price_to_tick(price: float, tick_size: float) -> float:
    """Round ``price`` to the nearest valid increment of ``tick_size``."""
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    return round(float(price) / tick_size) * tick_size


def price_to_bracket_ticks(
    *,
    reference_price: float,
    stop_price: float,
    take_profit_price: float,
    tick_size: float,
    side_long: bool,
) -> tuple[int, int]:
    """
    Convert absolute SL/TP prices to integer tick offsets for PlaceOrderBracket.
    Long: SL below ref (Stop), TP above ref (Limit). Short: inverted.
    """
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    if side_long:
        sl_ticks = int(round((reference_price - stop_price) / tick_size))
        tp_ticks = int(round((take_profit_price - reference_price) / tick_size))
    else:
        sl_ticks = int(round((stop_price - reference_price) / tick_size))
        tp_ticks = int(round((reference_price - take_profit_price) / tick_size))
    if sl_ticks < 1 or tp_ticks < 1:
        raise ValueError(
            f"Bracket ticks must be >= 1 (got sl={sl_ticks}, tp={tp_ticks}); "
            "check prices, reference_price, and tick_size."
        )
    return sl_ticks, tp_ticks


def gateway_signed_bracket_ticks(
    sl_ticks: int, tp_ticks: int, *, side_long: bool
) -> tuple[int, int]:
    """
    Gateway validates signed offsets: for a long, SL is below entry → negative tick count;
    TP above → positive. Short uses the opposite signs.
    """
    if side_long:
        return (-abs(sl_ticks), abs(tp_ticks))
    return (abs(sl_ticks), -abs(tp_ticks))


def dollar_risk_to_bracket_ticks(
    *,
    risk_usd: float,
    reward_usd: float,
    tick_value: float,
    contracts: int,
) -> tuple[int, int]:
    """
    Convert total $ risk / reward across all contracts to bracket tick counts.
    tick_value = Gateway ContractModel.tickValue (USD per tick, one contract).
    """
    if tick_value <= 0 or contracts < 1:
        raise ValueError("tick_value and contracts must be positive")
    if risk_usd <= 0 or reward_usd <= 0:
        raise ValueError("risk_usd and reward_usd must be positive")
    usd_per_tick = tick_value * float(contracts)
    sl_ticks = max(1, int(round(risk_usd / usd_per_tick)))
    tp_ticks = max(1, int(round(reward_usd / usd_per_tick)))
    return sl_ticks, tp_ticks


# Gateway enums (OrderType)
ORDER_TYPE_LIMIT = 1
ORDER_TYPE_MARKET = 2
ORDER_TYPE_STOP = 4

# OrderSide: Bid = long entry, Ask = short entry (per ProjectX examples)
ORDER_SIDE_BID = 0
ORDER_SIDE_ASK = 1
