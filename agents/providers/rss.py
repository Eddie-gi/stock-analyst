from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..config import FeedSource
from ..models import FeedHealth, NewsItem, concise_summary


class RssFeedProvider:
    """Keyless RSS/Atom headline collector for international and video sources."""

    def __init__(self, opener: Callable[..., object] = urlopen) -> None:
        self._opener = opener

    def fetch(self, source: FeedSource) -> tuple[list[NewsItem], FeedHealth]:
        try:
            request = Request(
                source.url,
                headers={
                    "User-Agent": "SignalDesk/2.0 (personal market research)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                },
            )
            with self._opener(request, timeout=20) as response:
                payload = response.read()
            items = parse_feed(payload, source)[: source.max_items]
            latest = max((item.published_at for item in items if item.published_at), default=None)
            return items, FeedHealth(
                name=source.name,
                url=source.url,
                source_type=source.source_type,
                region=source.region,
                status="healthy" if items else "empty",
                item_count=len(items),
                latest_published_at=latest,
            )
        except Exception as exc:
            return [], FeedHealth(
                name=source.name,
                url=source.url,
                source_type=source.source_type,
                region=source.region,
                status="failed",
                item_count=0,
                error=f"{type(exc).__name__}: {str(exc)[:120]}",
            )


def parse_feed(payload: bytes | str, source: FeedSource) -> list[NewsItem]:
    root = ET.fromstring(payload)
    nodes = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    items: list[NewsItem] = []
    seen: set[str] = set()
    for node in nodes:
        title = _clean(_child_text(node, "title"))
        url = _entry_url(node)
        if not title or not _safe_url(url):
            continue
        key = re.sub(r"\W+", "", title.casefold())
        if not key or key in seen:
            continue
        seen.add(key)
        publisher = (
            _clean(_child_text(node, "source"))
            or _clean(_descendant_text(node, "name"))
            or _clean(_child_text(node, "creator"))
            or source.name
        )
        published = (
            _child_text(node, "published")
            or _child_text(node, "pubDate")
            or _child_text(node, "updated")
            or _child_text(node, "date")
        )
        description = (
            _child_text(node, "description")
            or _child_text(node, "summary")
            or _child_text(node, "content")
            or _descendant_text(node, "description")
        )
        items.append(
            NewsItem(
                title=title,
                url=url,
                publisher=publisher,
                published_at=_normalize_date(published),
                source_type=source.source_type,
                region=source.region,
                topic=source.topic,
                summary=concise_summary(description, title),
            )
        )
    return items


def _entry_url(node: ET.Element) -> str:
    for child in node:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "").strip()
        rel = child.attrib.get("rel", "alternate")
        if href and rel in {"alternate", ""}:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def _child_text(node: ET.Element, name: str) -> str:
    for child in node:
        if _local_name(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _descendant_text(node: ET.Element, name: str) -> str:
    for child in node.iter():
        if child is not node and _local_name(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean(value: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_date(value: str) -> str | None:
    if not value:
        return None
    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()
