from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from ..indicators import calculate_indicators, make_chart
from ..models import MarketSnapshot, NewsItem, finite_float


class YahooFinanceProvider:
    """Personal-research market data adapter backed by the open-source yfinance client."""

    name = "Yahoo Finance via yfinance"

    def snapshot(self, ticker_symbol: str, *, include_news: bool, news_count: int) -> MarketSnapshot:
        symbol = ticker_symbol.upper()
        errors: list[str] = []
        ticker = yf.Ticker(symbol)

        try:
            history = ticker.history(period="6mo", interval="1d", auto_adjust=True, repair=False)
        except Exception as exc:  # provider failures must not stop the full network
            history = pd.DataFrame()
            errors.append(f"price history unavailable: {type(exc).__name__}")

        indicators = calculate_indicators(history)
        price = finite_float(history["Close"].dropna().iloc[-1]) if not history.empty else None

        name = symbol
        currency = "USD"
        market_cap = None
        try:
            fast_info = ticker.fast_info
            market_cap = finite_float(_read_mapping(fast_info, "marketCap", "market_cap"))
            currency = str(_read_mapping(fast_info, "currency") or "USD")
        except Exception as exc:
            errors.append(f"quote metadata unavailable: {type(exc).__name__}")

        next_earnings = None
        earnings_days = None
        try:
            raw_earnings = _read_mapping(ticker.calendar or {}, "Earnings Date", "earningsDate")
            earnings_date = _first_datetime(raw_earnings)
            if earnings_date is not None:
                now = datetime.now(earnings_date.tzinfo or timezone.utc)
                next_earnings = earnings_date.date().isoformat()
                earnings_days = (earnings_date.date() - now.date()).days
        except Exception as exc:
            errors.append(f"earnings date unavailable: {type(exc).__name__}")

        news: list[NewsItem] = []
        if include_news:
            try:
                news = [_parse_news_item(item) for item in yf.Search(symbol, news_count=news_count).news]
                news = [item for item in news if item.title and item.url][:news_count]
            except Exception as exc:
                errors.append(f"news unavailable: {type(exc).__name__}")

        return MarketSnapshot(
            ticker=symbol,
            name=name,
            currency=currency,
            price=price,
            previous_close=indicators["previous_close"],
            change_pct=indicators["change_pct"],
            return_5d_pct=indicators["return_5d_pct"],
            return_20d_pct=indicators["return_20d_pct"],
            ema20=indicators["ema20"],
            ema50=indicators["ema50"],
            rsi14=indicators["rsi14"],
            atr_pct=indicators["atr_pct"],
            volume_ratio=indicators["volume_ratio"],
            volatility20_pct=indicators["volatility20_pct"],
            market_cap=market_cap,
            next_earnings=next_earnings,
            earnings_days=earnings_days,
            chart=make_chart(history),
            news=news,
            errors=errors,
        )


def _read_mapping(mapping: Any, *keys: str) -> Any:
    for key in keys:
        try:
            value = mapping.get(key)
        except (AttributeError, KeyError, TypeError):
            try:
                value = mapping[key]
            except (KeyError, TypeError):
                value = None
        if value is not None:
            return value
    return None


def _first_datetime(value: Any) -> datetime | None:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    try:
        parsed = pd.Timestamp(value)
        return None if pd.isna(parsed) else parsed.to_pydatetime()
    except (TypeError, ValueError):
        return None


def _parse_news_item(item: dict[str, Any]) -> NewsItem:
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    title = str(content.get("title") or item.get("title") or "").strip()
    canonical = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
    url = canonical.get("url") if isinstance(canonical, dict) else canonical
    url = str(url or content.get("link") or item.get("link") or "").strip()
    provider = content.get("provider") or item.get("publisher") or "Yahoo Finance"
    if isinstance(provider, dict):
        provider = provider.get("displayName") or provider.get("name") or "Yahoo Finance"
    published = content.get("pubDate") or item.get("providerPublishTime")
    if isinstance(published, (int, float)):
        published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
    return NewsItem(title=title, url=url, publisher=str(provider), published_at=str(published) if published else None)
