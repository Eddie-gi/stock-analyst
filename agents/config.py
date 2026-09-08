from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class Settings:
    watchlist: tuple[str, ...]
    screener_universe: tuple[str, ...]
    market_cap_min: float
    max_candidates: int
    news_per_ticker: int
    archive_days: int
    sec_user_agent: str


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return Settings(
        watchlist=tuple(_tickers(raw.get("watchlist", []))),
        screener_universe=tuple(_tickers(raw.get("screener_universe", []))),
        market_cap_min=float(raw.get("market_cap_min", 1_000_000_000_000)),
        max_candidates=int(raw.get("max_candidates", 5)),
        news_per_ticker=int(raw.get("news_per_ticker", 5)),
        archive_days=int(raw.get("archive_days", 30)),
        sec_user_agent=os.getenv(
            "SEC_USER_AGENT",
            str(raw.get("sec_user_agent", "SignalDesk research contact@example.com")),
        ),
    )


def _tickers(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        ticker = str(value).strip().upper()
        if ticker and ticker not in result:
            result.append(ticker)
    return result
