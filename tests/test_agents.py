import unittest

from agents.models import MarketSnapshot
from agents.nodes.portfolio_monitor import PortfolioMonitorAgent
from agents.nodes.risk import RiskAgent
from agents.nodes.screener import ScreenerAgent


def snapshot(ticker: str, *, market_cap: float = 2_000_000_000_000, price: float = 120) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker,
        name=ticker,
        currency="USD",
        price=price,
        previous_close=118,
        change_pct=1.7,
        return_5d_pct=3.0,
        return_20d_pct=8.0,
        ema20=115,
        ema50=108,
        rsi14=60,
        atr_pct=3.0,
        volume_ratio=1.4,
        volatility20_pct=32,
        market_cap=market_cap,
        next_earnings="2026-10-01",
        earnings_days=23,
    )


class AgentTests(unittest.TestCase):
    def test_monitor_scores_constructive_trend(self) -> None:
        holdings, alerts = PortfolioMonitorAgent().run([snapshot("TEST")])
        self.assertGreaterEqual(holdings[0]["signal_score"], 75)
        self.assertEqual(holdings[0]["stance"], "Constructive")
        self.assertEqual(alerts, [])

    def test_screener_enforces_market_cap_and_target_bounds(self) -> None:
        agent = ScreenerAgent()
        result = agent.run(
            [snapshot("BIG"), snapshot("SMALL", market_cap=500_000_000_000)],
            market_cap_min=1_000_000_000_000,
            max_candidates=5,
        )
        self.assertEqual([item["ticker"] for item in result], ["BIG"])
        self.assertGreaterEqual(result[0]["modeled_upside_pct"], 10)
        self.assertLessEqual(result[0]["modeled_upside_pct"], 20)

    def test_risk_agent_applies_bounded_research_cap(self) -> None:
        holdings, _ = PortfolioMonitorAgent().run([snapshot("TEST")])
        candidates = ScreenerAgent().run(
            [snapshot("TEST")], market_cap_min=1_000_000_000_000, max_candidates=5
        )
        risk = RiskAgent().run(holdings, candidates)
        self.assertEqual(risk["level"], "normal")
        self.assertGreaterEqual(candidates[0]["research_allocation_cap_pct"], 2)
        self.assertLessEqual(candidates[0]["research_allocation_cap_pct"], 8)


if __name__ == "__main__":
    unittest.main()
