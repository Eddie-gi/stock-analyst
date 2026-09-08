from __future__ import annotations

from datetime import date
from typing import Any

from ..models import MarketSnapshot


class PortfolioMonitorAgent:
    id = "portfolio-monitor"
    label = "Portfolio monitor"

    def run(self, snapshots: list[MarketSnapshot]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        holdings: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        for snapshot in snapshots:
            score, rationale = _signal_score(snapshot)
            catalysts = _catalysts(snapshot)
            risk_level = _risk_level(snapshot)
            stance = "Constructive" if score >= 75 else "Watch" if score >= 55 else "Cautious"
            holding = snapshot.to_dict()
            holding.update(
                {
                    "signal_score": score,
                    "stance": stance,
                    "risk_level": risk_level,
                    "rationale": rationale,
                    "catalysts": catalysts,
                }
            )
            holdings.append(holding)
            alerts.extend(_alerts(snapshot, risk_level))

        severity_order = {"critical": 0, "high": 1, "elevated": 2, "watch": 3}
        alerts.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["ticker"]))
        holdings.sort(key=lambda item: (-item["signal_score"], item["ticker"]))
        return holdings, alerts


def _signal_score(snapshot: MarketSnapshot) -> tuple[int, list[str]]:
    if snapshot.price is None:
        return 0, ["No current price was available, so the signal is not usable."]

    score = 50.0
    rationale: list[str] = []
    if snapshot.ema20 is not None:
        if snapshot.price > snapshot.ema20:
            score += 10
            rationale.append("Price is above its 20-day trend.")
        else:
            score -= 10
            rationale.append("Price is below its 20-day trend.")
    if snapshot.ema50 is not None:
        if snapshot.price > snapshot.ema50:
            score += 10
            rationale.append("Price remains above its 50-day trend.")
        else:
            score -= 10
            rationale.append("Price is below its 50-day trend.")
    if snapshot.return_20d_pct is not None:
        score += max(-15, min(15, snapshot.return_20d_pct * 0.75))
        direction = "positive" if snapshot.return_20d_pct >= 0 else "negative"
        rationale.append(f"Twenty-session momentum is {direction} at {snapshot.return_20d_pct:.1f}%.")
    if snapshot.rsi14 is not None:
        if 45 <= snapshot.rsi14 <= 68:
            score += 8
            rationale.append("RSI is in a constructive, non-extreme range.")
        elif snapshot.rsi14 >= 75:
            score -= 8
            rationale.append("RSI is extended and raises pullback risk.")
        elif snapshot.rsi14 < 35:
            score -= 5
            rationale.append("RSI shows weak momentum despite possible oversold conditions.")
    if snapshot.volume_ratio is not None and snapshot.volume_ratio >= 1.5:
        score += 4
        rationale.append("Latest volume is meaningfully above its 20-session average.")
    if snapshot.earnings_days is not None and 0 <= snapshot.earnings_days <= 7:
        score -= 5
        rationale.append("Earnings are within seven days, increasing event risk.")
    return round(max(0, min(100, score))), rationale[:4]


def _risk_level(snapshot: MarketSnapshot) -> str:
    if snapshot.price is None:
        return "unknown"
    if snapshot.earnings_days is not None and 0 <= snapshot.earnings_days <= 7:
        return "high"
    if (snapshot.atr_pct or 0) >= 5 or abs(snapshot.change_pct or 0) >= 5:
        return "high"
    if (snapshot.atr_pct or 0) >= 3 or (snapshot.volume_ratio or 0) >= 1.7:
        return "elevated"
    return "normal"


def _catalysts(snapshot: MarketSnapshot) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if snapshot.next_earnings and snapshot.earnings_days is not None and snapshot.earnings_days >= 0:
        result.append(
            {
                "type": "earnings",
                "date": snapshot.next_earnings,
                "label": f"Earnings in {snapshot.earnings_days} days",
            }
        )
    for filing in snapshot.filings[:2]:
        result.append({"type": "filing", "date": filing.filed_at, "label": f"SEC {filing.form} filed"})
    return result


def _alerts(snapshot: MarketSnapshot, risk_level: str) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if snapshot.price is None:
        alerts.append(
            {
                "ticker": snapshot.ticker,
                "severity": "watch",
                "type": "data",
                "title": "Price data unavailable",
                "detail": "Treat all signals for this ticker as incomplete until the next successful refresh.",
            }
        )
        return alerts
    if snapshot.earnings_days is not None and 0 <= snapshot.earnings_days <= 14:
        alerts.append(
            {
                "ticker": snapshot.ticker,
                "severity": "high" if snapshot.earnings_days <= 7 else "elevated",
                "type": "earnings",
                "title": f"Earnings in {snapshot.earnings_days} days",
                "detail": "Review primary earnings materials and position risk before the event.",
                "date": snapshot.next_earnings,
            }
        )
    if abs(snapshot.change_pct or 0) >= 5:
        alerts.append(
            {
                "ticker": snapshot.ticker,
                "severity": "high",
                "type": "price",
                "title": f"Large one-session move: {snapshot.change_pct:+.1f}%",
                "detail": "Check the linked news and filings for a company-specific cause.",
            }
        )
    if (snapshot.volume_ratio or 0) >= 2:
        alerts.append(
            {
                "ticker": snapshot.ticker,
                "severity": "elevated",
                "type": "volume",
                "title": f"Volume is {snapshot.volume_ratio:.1f}x normal",
                "detail": "Unusual participation can confirm a move or signal event-driven risk.",
            }
        )
    if (snapshot.atr_pct or 0) >= 5:
        alerts.append(
            {
                "ticker": snapshot.ticker,
                "severity": "high",
                "type": "volatility",
                "title": f"Daily range is elevated at {snapshot.atr_pct:.1f}%",
                "detail": "Wide average ranges increase gap and stop-loss risk; review exposure before adding risk.",
            }
        )
    if snapshot.filings and snapshot.filings[0].filed_at >= (date.today().isoformat()):
        alerts.append(
            {
                "ticker": snapshot.ticker,
                "severity": "elevated" if snapshot.filings[0].form == "8-K" else "watch",
                "type": "filing",
                "title": f"New SEC {snapshot.filings[0].form}",
                "detail": snapshot.filings[0].description,
                "url": snapshot.filings[0].url,
            }
        )
    return alerts
