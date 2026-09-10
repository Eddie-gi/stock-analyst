from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class NewsItem:
    title: str
    url: str
    publisher: str
    published_at: str | None = None
    source_type: str = "news"
    region: str = "US"
    topic: str = "company"


@dataclass(slots=True)
class FeedHealth:
    name: str
    url: str
    source_type: str
    region: str
    status: str
    item_count: int
    latest_published_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FilingItem:
    form: str
    filed_at: str
    description: str
    url: str


@dataclass(slots=True)
class MarketSnapshot:
    ticker: str
    name: str
    currency: str
    price: float | None
    previous_close: float | None
    change_pct: float | None
    return_5d_pct: float | None
    return_20d_pct: float | None
    ema20: float | None
    ema50: float | None
    rsi14: float | None
    atr_pct: float | None
    volume_ratio: float | None
    volatility20_pct: float | None
    market_cap: float | None
    next_earnings: str | None
    earnings_days: int | None
    chart: list[dict[str, Any]] = field(default_factory=list)
    news: list[NewsItem] = field(default_factory=list)
    filings: list[FilingItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentRun:
    id: str
    label: str
    status: str
    duration_ms: int
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().isoformat()
    return str(value)


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return round(number, 4)
