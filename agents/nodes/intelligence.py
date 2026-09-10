from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from ..models import FeedHealth, NewsItem


class IntelligenceAgent:
    id = "intelligence-triage"
    label = "Source triage and deduplication"

    def run(
        self,
        holdings: list[dict[str, Any]],
        feed_items: list[NewsItem],
        feed_health: list[FeedHealth],
        generated_at: datetime,
        *,
        limit: int,
    ) -> dict[str, Any]:
        watchlist = [item["ticker"] for item in holdings]
        evidence: list[NewsItem] = list(feed_items)
        for holding in holdings:
            evidence.extend(NewsItem(**item) for item in holding.get("news", []))
            evidence.extend(
                NewsItem(
                    title=f"{holding['ticker']} filed {filing['form']}: {filing['description']}",
                    url=filing["url"],
                    publisher="SEC EDGAR",
                    published_at=filing["filed_at"],
                    source_type="filing",
                    region="US",
                    topic="filings",
                    summary=(
                        f"SEC EDGAR lists {_indefinite_article(filing['form'])} {filing['form']} filing for {holding['ticker']}. "
                        "Open the primary filing to review the disclosed event and any material details."
                    ),
                )
                for filing in holding.get("filings", [])
            )

        queue: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in evidence:
            key = _dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            tickers = _find_tickers(f"{item.title} {item.summary or ''}", watchlist)
            topic = _infer_topic(item.title, item.topic)
            age_hours = _age_hours(item.published_at, generated_at)
            if age_hours is not None and age_hours > (168 if item.source_type == "filing" else 72):
                continue
            score, reasons = _priority(item, tickers, topic, age_hours)
            queue.append(
                {
                    "id": hashlib.sha1(f"{item.url}|{item.title}".encode("utf-8")).hexdigest()[:12],
                    "title": item.title,
                    "summary": _summary(item, tickers, topic),
                    "url": item.url,
                    "publisher": item.publisher,
                    "published_at": item.published_at,
                    "source_type": item.source_type,
                    "region": item.region,
                    "topic": topic,
                    "tickers": tickers,
                    "priority_score": score,
                    "priority": "must-review" if score >= 94 else "scan" if score >= 70 else "background",
                    "why_flagged": " ".join(reasons),
                    "age_hours": round(age_hours, 1) if age_hours is not None else None,
                }
            )
        queue.sort(key=lambda item: (-item["priority_score"], item["age_hours"] or 10_000, item["title"]))
        queue = _balanced_queue(queue, limit)

        priority_count = sum(item["priority"] == "must-review" for item in queue)
        scan_count = sum(item["priority"] == "scan" for item in queue)
        international = sum(item["source_type"] == "international" for item in queue)
        videos = sum(item["source_type"] == "video" for item in queue)
        filings = sum(item["source_type"] == "filing" for item in queue)
        publishers = sorted({item["publisher"] for item in queue})
        regions = sorted({item["region"] for item in queue})
        themes = _themes(queue)
        active_tickers = sorted({ticker for item in queue[:20] for ticker in item["tickers"]})
        healthy = sum(health.status == "healthy" for health in feed_health)

        digest: list[str] = []
        if international:
            digest.append(f"{international} Asia/international headlines are in the review window.")
        if videos:
            digest.append(f"{videos} recent market videos were indexed; titles are triaged without copying transcripts.")
        if active_tickers:
            digest.append(f"Fresh coverage mentions {', '.join(active_tickers[:6])}.")
        if themes:
            digest.append(f"Most active theme: {themes[0]['label']} ({themes[0]['count']} items).")

        return {
            "headline": (
                f"{priority_count} source item{'s' if priority_count != 1 else ''} need a closer look before the open."
                if priority_count
                else "No source item crossed the high-priority threshold this morning."
            ),
            "digest": digest or ["The source scan completed without a concentrated new theme."],
            "review_queue": queue,
            "must_review_count": priority_count,
            "scan_count": scan_count,
            "estimated_review_minutes": max(1, math.ceil(priority_count * 0.75 + min(scan_count, 12) * 0.3)),
            "themes": themes,
            "coverage": {
                "total_items": len(queue),
                "international_items": international,
                "video_items": videos,
                "filing_items": filings,
                "publisher_count": len(publishers),
                "publishers": publishers,
                "regions": regions,
                "healthy_feeds": healthy,
                "total_feeds": len(feed_health),
            },
            "feed_health": [health.to_dict() for health in feed_health],
        }


def _dedupe_key(item: NewsItem) -> str:
    title = re.sub(r"[^a-z0-9]+", "", item.title.casefold())
    return title[:180] or item.url


def _summary(item: NewsItem, tickers: list[str], topic: str) -> str:
    if item.summary:
        return item.summary
    subject = f" involving {', '.join(tickers)}" if tickers else ""
    readable_topic = topic.replace("-", " ")
    if item.source_type == "filing":
        return (
            f"SEC EDGAR published a new regulatory filing{subject}. "
            "Open the primary document to review the disclosed event and any material details."
        )
    if item.source_type == "video":
        return (
            f"{item.publisher} published a recent market video about {readable_topic}{subject}. "
            "Signal Desk indexed its title and source metadata; the full transcript was not analyzed."
        )
    if item.source_type == "international":
        return (
            f"{item.publisher} published a recent {item.region} report about {readable_topic}{subject}. "
            "Open the original source to assess its implications for the US session."
        )
    return (
        f"{item.publisher} published a recent {readable_topic} report{subject}. "
        "Open the original source to verify the details and assess their significance."
    )


def _indefinite_article(value: str) -> str:
    return "an" if value[:1].casefold() in {"a", "e", "i", "o", "u", "8"} else "a"


def _find_tickers(title: str, watchlist: list[str]) -> list[str]:
    upper = title.upper()
    found = {ticker for ticker in watchlist if re.search(rf"(?<![A-Z]){re.escape(ticker)}(?![A-Z])", upper)}
    aliases = {
        "NVIDIA": "NVDA", "APPLE": "AAPL", "AMAZON": "AMZN", "META": "META",
        "MICRON": "MU", "SANDISK": "SNDK", "MICROSOFT": "MSFT", "GOOGLE": "GOOGL",
        "ALPHABET": "GOOGL", "BROADCOM": "AVGO", "TESLA": "TSLA",
    }
    for alias, ticker in aliases.items():
        if ticker in watchlist and re.search(rf"\b{alias}\b", upper):
            found.add(ticker)
    return sorted(found)


def _infer_topic(title: str, configured: str) -> str:
    value = title.casefold()
    groups = [
        ("semiconductors", ("chip", "semiconductor", "nvidia", "micron", "tsmc", "broadcom")),
        ("policy", ("fed ", "federal reserve", "rate cut", "rate hike", "tariff", "sanction", "export control", "boj", "pboc")),
        ("macro", ("inflation", "jobs report", "payroll", "gdp", "recession", "yield", "currency", "oil price")),
        ("earnings", ("earnings", "guidance", "revenue", "profit", "forecast")),
        ("deals", ("acquisition", "merger", "takeover", "stake in")),
    ]
    for topic, words in groups:
        if any(word in value for word in words):
            return topic
    return configured or "markets"


def _priority(item: NewsItem, tickers: list[str], topic: str, age_hours: float | None) -> tuple[int, list[str]]:
    base = {"filing": 84, "international": 57, "video": 46, "company-news": 55, "news": 50}.get(item.source_type, 45)
    reasons: list[str] = []
    if tickers:
        base += min(18, 8 + len(tickers) * 4)
        reasons.append(f"Matches watchlist: {', '.join(tickers)}.")
    if item.source_type == "filing":
        reasons.append("Primary regulatory filing.")
    elif item.source_type == "international":
        base += 7
        reasons.append(f"Early {item.region} read-through.")
    elif item.source_type == "video":
        reasons.append("Recent video from a configured market channel.")
    if topic in {"policy", "earnings", "semiconductors", "deals"}:
        base += 9
        reasons.append(f"Tagged {topic}.")
    if age_hours is not None:
        if age_hours <= 6:
            base += 14
            reasons.append("Published within six hours.")
        elif age_hours <= 24:
            base += 8
            reasons.append("Published within 24 hours.")
        elif age_hours <= 48:
            base += 3
    if not reasons:
        reasons.append("Recent item from a configured source.")
    return max(0, min(100, round(base))), reasons[:3]


def _age_hours(value: str | None, now: datetime) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{value}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (now.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600)


def _themes(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    tickers: dict[str, set[str]] = {}
    for item in queue:
        topic = item["topic"]
        counts[topic] = counts.get(topic, 0) + 1
        tickers.setdefault(topic, set()).update(item["tickers"])
    return [
        {"id": topic, "label": topic.replace("-", " ").title(), "count": count, "tickers": sorted(tickers[topic])}
        for topic, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:6]
    ]


def _balanced_queue(queue: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Preserve source diversity so lower-volume videos are never crowded out."""
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    quotas = {"filing": 6, "international": 12, "video": 10, "company-news": 18}
    for source_type, quota in quotas.items():
        for item in (entry for entry in queue if entry["source_type"] == source_type):
            if len([entry for entry in selected if entry["source_type"] == source_type]) >= quota:
                break
            selected.append(item)
            selected_ids.add(item["id"])
    for item in queue:
        if len(selected) >= limit:
            break
        if item["id"] not in selected_ids:
            selected.append(item)
            selected_ids.add(item["id"])
    selected.sort(key=lambda item: (-item["priority_score"], item["age_hours"] or 10_000, item["title"]))
    return selected[:limit]
