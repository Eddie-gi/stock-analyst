from __future__ import annotations

from typing import Any


class RiskAgent:
    id = "risk-auditor"
    label = "Risk auditor"

    def run(self, holdings: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        high_risk = [item["ticker"] for item in holdings if item["risk_level"] in {"high", "unknown"}]
        earnings_cluster = [
            item["ticker"]
            for item in holdings
            if item.get("earnings_days") is not None and 0 <= item["earnings_days"] <= 14
        ]
        for candidate in candidates:
            volatility = candidate.get("volatility20_pct") or 35
            candidate["research_allocation_cap_pct"] = round(max(2, min(8, 180 / max(volatility, 1))), 1)
            candidate["risk_flags"] = _candidate_flags(candidate)

        notes: list[str] = []
        if high_risk:
            notes.append(f"High or unknown event risk: {', '.join(high_risk)}.")
        if len(earnings_cluster) >= 2:
            notes.append(f"Earnings risk is clustered across {len(earnings_cluster)} holdings in the next 14 days.")
        if not notes:
            notes.append("No portfolio-wide rule breach was detected from the available data.")
        notes.append("Allocation caps are volatility heuristics for research, not personalized sizing advice.")
        return {
            "level": "high" if high_risk else "elevated" if earnings_cluster else "normal",
            "high_risk_tickers": high_risk,
            "earnings_cluster": earnings_cluster,
            "notes": notes,
        }


def _candidate_flags(candidate: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if (candidate.get("rsi14") or 0) >= 70:
        flags.append("Momentum is extended")
    if (candidate.get("atr_pct") or 0) >= 4:
        flags.append("High daily range")
    if candidate.get("earnings_days") is not None and 0 <= candidate["earnings_days"] <= 21:
        flags.append("Earnings inside three weeks")
    if not flags:
        flags.append("No mechanical risk flag")
    return flags
