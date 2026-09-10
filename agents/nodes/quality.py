from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class QualityAgent:
    id = "quality-controller"
    label = "Quality controller"

    def run(
        self,
        holdings: list[dict[str, Any]],
        generated_at: datetime,
        intelligence: dict[str, Any] | None = None,
        global_markets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        intelligence = intelligence or {}
        global_markets = global_markets or []
        ticker_count = len(holdings)
        priced = sum(1 for item in holdings if item.get("price") is not None)
        with_news = sum(1 for item in holdings if item.get("news"))
        errors = [f"{item['ticker']}: {error}" for item in holdings for error in item.get("errors", [])]
        source_count = len(intelligence.get("review_queue", [])) + sum(
            1 + len(item.get("filings", [])) for item in holdings if item.get("price") is not None
        ) + sum(item.get("status") == "available" for item in global_markets)

        price_coverage = priced / ticker_count if ticker_count else 0
        news_coverage = with_news / ticker_count if ticker_count else 0
        feed_health = intelligence.get("feed_health", [])
        healthy_feeds = sum(item.get("status") == "healthy" for item in feed_health)
        feed_coverage = healthy_feeds / len(feed_health) if feed_health else 0
        global_coverage = (
            sum(item.get("status") == "available" for item in global_markets) / len(global_markets)
            if global_markets else 0
        )
        score = round(price_coverage * 45 + news_coverage * 15 + feed_coverage * 20 + global_coverage * 20)
        age_minutes = max(0, int((datetime.now(timezone.utc) - generated_at).total_seconds() / 60))
        warnings: list[str] = []
        if price_coverage < 1:
            warnings.append(f"Price data missing for {ticker_count - priced} ticker(s).")
        if news_coverage < 0.5:
            warnings.append("News coverage is limited; the report may miss qualitative catalysts.")
        if feed_health and feed_coverage < 0.7:
            warnings.append(f"Only {healthy_feeds}/{len(feed_health)} external headline feeds returned items.")
        if global_markets and global_coverage < 0.7:
            warnings.append("Global market coverage is incomplete.")
        if errors:
            warnings.append(f"{len(errors)} provider warning(s) were recorded.")

        return {
            "score": score,
            "source_count": source_count,
            "price_coverage_pct": round(price_coverage * 100),
            "news_coverage_pct": round(news_coverage * 100),
            "feed_coverage_pct": round(feed_coverage * 100),
            "global_market_coverage_pct": round(global_coverage * 100),
            "publisher_count": intelligence.get("coverage", {}).get("publisher_count", 0),
            "provider_warning_count": len(errors),
            "provider_warnings": errors[:12],
            "age_minutes": age_minutes,
            "stale": age_minutes > 240,
            "warnings": warnings,
        }
