from __future__ import annotations

from typing import Any


class SynthesisAgent:
    id = "lead-synthesizer"
    label = "Lead synthesizer"

    def run(
        self,
        holdings: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
        risk: dict[str, Any],
        intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        intelligence = intelligence or {}
        usable = [item for item in holdings if item.get("price") is not None]
        constructive = [item for item in usable if item.get("stance") == "Constructive"]
        urgent = [item for item in alerts if item.get("severity") in {"critical", "high"}]

        source_priority = int(intelligence.get("must_review_count", 0))
        if source_priority:
            headline = f"{source_priority} high-priority source item{'s' if source_priority != 1 else ''} need review before the open."
        elif urgent:
            headline = f"{len(urgent)} high-priority item{'s' if len(urgent) != 1 else ''} need review before the open."
        elif risk.get("level") == "high":
            headline = "Portfolio trends are constructive, but high-volatility holdings need review."
        elif usable and len(constructive) >= max(1, len(usable) // 2):
            headline = "Portfolio trends are broadly constructive; no urgent rule breach was found."
        elif usable:
            headline = "Portfolio signals are mixed; keep new risk selective."
        else:
            headline = "Market data is incomplete; defer signal-based decisions."

        detail_parts = []
        if constructive:
            detail_parts.append(f"Constructive trends: {', '.join(item['ticker'] for item in constructive[:4])}.")
        if candidates:
            detail_parts.append(f"Top mechanical setup: {candidates[0]['ticker']} ({candidates[0]['setup_score']}/100).")
        if risk.get("earnings_cluster"):
            detail_parts.append("Upcoming earnings increase portfolio event risk.")
        coverage = intelligence.get("coverage", {})
        if coverage.get("international_items"):
            detail_parts.append(f"The scan includes {coverage['international_items']} international item(s).")
        if coverage.get("video_items"):
            detail_parts.append(f"{coverage['video_items']} recent market video(s) were indexed.")

        return {
            "headline": headline,
            "detail": " ".join(detail_parts) or "Review source links and data-quality notes before acting.",
            "risk_level": risk["level"],
            "constructive_count": len(constructive),
            "holdings_count": len(holdings),
            "candidate_count": len(candidates),
            "disclaimer": "Decision-support only. This is not personalized investment advice and no order is placed.",
        }
