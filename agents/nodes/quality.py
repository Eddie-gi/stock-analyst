from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class QualityAgent:
    id = "quality-controller"
    label = "Quality controller"

    def run(self, holdings: list[dict[str, Any]], generated_at: datetime) -> dict[str, Any]:
        ticker_count = len(holdings)
        priced = sum(1 for item in holdings if item.get("price") is not None)
        with_news = sum(1 for item in holdings if item.get("news"))
        errors = [f"{item['ticker']}: {error}" for item in holdings for error in item.get("errors", [])]
        source_count = sum(1 + len(item.get("news", [])) + len(item.get("filings", [])) for item in holdings if item.get("price") is not None)

        price_coverage = priced / ticker_count if ticker_count else 0
        news_coverage = with_news / ticker_count if ticker_count else 0
        score = round((price_coverage * 75 + news_coverage * 25))
        age_minutes = max(0, int((datetime.now(timezone.utc) - generated_at).total_seconds() / 60))
        warnings: list[str] = []
        if price_coverage < 1:
            warnings.append(f"Price data missing for {ticker_count - priced} ticker(s).")
        if news_coverage < 0.5:
            warnings.append("News coverage is limited; the report may miss qualitative catalysts.")
        if errors:
            warnings.append(f"{len(errors)} provider warning(s) were recorded.")

        return {
            "score": score,
            "source_count": source_count,
            "price_coverage_pct": round(price_coverage * 100),
            "news_coverage_pct": round(news_coverage * 100),
            "provider_warning_count": len(errors),
            "provider_warnings": errors[:12],
            "age_minutes": age_minutes,
            "stale": age_minutes > 240,
            "warnings": warnings,
        }
