from __future__ import annotations

import html
import re
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
    summary: str | None = None


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


def concise_summary(value: Any, title: str = "", *, max_chars: int = 360) -> str | None:
    """Turn a feed-provided description into one or two plain-text sentences."""
    if value is None:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value)))
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -|\n\t")
    if not text:
        return None
    comparable = lambda item: re.sub(r"[^a-z0-9]+", "", item.casefold())
    if comparable(text) == comparable(title):
        return None
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    result = " ".join(sentences[:2]) if sentences else text
    if len(result) > max_chars:
        cut = result.rfind(" ", 0, max_chars - 1)
        result = result[: cut if cut > max_chars // 2 else max_chars - 1].rstrip(" ,;:-") + "."
    elif result[-1] not in ".!?":
        result += "."
    return result
