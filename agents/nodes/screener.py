from __future__ import annotations

from typing import Any

from ..models import MarketSnapshot


class ScreenerAgent:
    id = "mega-cap-screener"
    label = "Mega-cap screener"

    def run(
        self,
        snapshots: list[MarketSnapshot],
        *,
        market_cap_min: float,
        max_candidates: int,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for snapshot in snapshots:
            if snapshot.price is None or snapshot.market_cap is None or snapshot.market_cap < market_cap_min:
                continue
            score, thesis = _setup_score(snapshot)
            atr_dollars = snapshot.price * ((snapshot.atr_pct or 2.5) / 100)
            model_target = min(max(snapshot.price + 3 * atr_dollars, snapshot.price * 1.10), snapshot.price * 1.20)
            model_stop = max(0.01, snapshot.price - 1.5 * atr_dollars)
            reward = model_target - snapshot.price
            risk = snapshot.price - model_stop
            candidates.append(
                {
                    **snapshot.to_dict(),
                    "setup_score": score,
                    "thesis": thesis,
                    "entry_zone": [round(snapshot.price - 0.3 * atr_dollars, 2), round(snapshot.price + 0.3 * atr_dollars, 2)],
                    "model_target": round(model_target, 2),
                    "model_stop": round(model_stop, 2),
                    "modeled_upside_pct": round((model_target / snapshot.price - 1) * 100, 1),
                    "reward_risk_ratio": round(reward / risk, 2) if risk else None,
                    "horizon": "1-2 months",
                    "target_note": "Mechanical 3-ATR research scenario, bounded to 10-20%; not a forecast.",
                }
            )
        candidates.sort(key=lambda item: (-item["setup_score"], item["ticker"]))
        return candidates[:max_candidates]


def _setup_score(snapshot: MarketSnapshot) -> tuple[int, list[str]]:
    score = 40.0
    thesis: list[str] = []
    if snapshot.price and snapshot.ema20 and snapshot.ema50:
        if snapshot.price > snapshot.ema20 > snapshot.ema50:
            score += 25
            thesis.append("Price, 20-day EMA, and 50-day EMA are positively aligned.")
        elif snapshot.price > snapshot.ema50:
            score += 12
            thesis.append("Price remains above the intermediate trend.")
        else:
            score -= 15
            thesis.append("Price is below the 50-day trend.")
    if snapshot.return_20d_pct is not None:
        if 2 <= snapshot.return_20d_pct <= 15:
            score += 15
            thesis.append("One-month momentum is positive without being extreme.")
        elif snapshot.return_20d_pct > 20:
            score -= 8
            thesis.append("Recent momentum is extended, increasing entry risk.")
        elif snapshot.return_20d_pct < -5:
            score -= 10
            thesis.append("One-month momentum is negative.")
    if snapshot.rsi14 is not None:
        if 48 <= snapshot.rsi14 <= 67:
            score += 12
            thesis.append("RSI sits in the preferred momentum band.")
        elif snapshot.rsi14 >= 75:
            score -= 10
            thesis.append("RSI is overextended.")
    if snapshot.volume_ratio is not None and snapshot.volume_ratio >= 1.2:
        score += min(8, (snapshot.volume_ratio - 1) * 8)
        thesis.append("Volume is supporting the move.")
    if snapshot.earnings_days is not None and 0 <= snapshot.earnings_days <= 14:
        score -= 5
        thesis.append("Near-term earnings add binary event risk.")
    return round(max(0, min(100, score))), thesis[:4]
