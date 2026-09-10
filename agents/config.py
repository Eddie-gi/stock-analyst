from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class FeedSource:
    name: str
    url: str
    source_type: str
    region: str
    topic: str
    max_items: int


@dataclass(frozen=True, slots=True)
class GlobalMarket:
    symbol: str
    label: str
    region: str
    category: str


@dataclass(frozen=True, slots=True)
class Settings:
    watchlist: tuple[str, ...]
    screener_universe: tuple[str, ...]
    market_cap_min: float
    max_candidates: int
    news_per_ticker: int
    archive_days: int
    sec_user_agent: str
    source_feeds: tuple[FeedSource, ...]
    global_markets: tuple[GlobalMarket, ...]
    review_queue_limit: int


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
        source_feeds=tuple(_feed_sources(raw.get("source_feeds", []))),
        global_markets=tuple(_global_markets(raw.get("global_markets", []))),
        review_queue_limit=max(10, min(int(raw.get("review_queue_limit", 50)), 100)),
    )


def _tickers(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        ticker = str(value).strip().upper()
        if ticker and ticker not in result:
            result.append(ticker)
    return result


def _feed_sources(values: list[object]) -> list[FeedSource]:
    result: list[FeedSource] = []
    for raw in values:
        if not isinstance(raw, dict) or not raw.get("name") or not raw.get("url"):
            continue
        result.append(
            FeedSource(
                name=str(raw["name"]).strip(),
                url=str(raw["url"]).strip(),
                source_type=str(raw.get("source_type", "news")).strip().lower(),
                region=str(raw.get("region", "Global")).strip(),
                topic=str(raw.get("topic", "markets")).strip().lower(),
                max_items=max(1, min(int(raw.get("max_items", 8)), 20)),
            )
        )
    return result


def _global_markets(values: list[object]) -> list[GlobalMarket]:
    result: list[GlobalMarket] = []
    for raw in values:
        if not isinstance(raw, dict) or not raw.get("symbol") or not raw.get("label"):
            continue
        result.append(
            GlobalMarket(
                symbol=str(raw["symbol"]).strip(),
                label=str(raw["label"]).strip(),
                region=str(raw.get("region", "Global")).strip(),
                category=str(raw.get("category", "index")).strip().lower(),
            )
        )
    return result
