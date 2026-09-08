import unittest

import pandas as pd

from agents.indicators import calculate_indicators, make_chart


class IndicatorTests(unittest.TestCase):
    def setUp(self) -> None:
        index = pd.date_range("2026-01-01", periods=80, freq="B")
        close = pd.Series([100 + index * 0.5 for index in range(80)], index=index)
        self.frame = pd.DataFrame(
            {
                "Open": close - 0.5,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": [1_000_000] * 79 + [2_000_000],
            },
            index=index,
        )

    def test_uptrend_indicators_are_finite(self) -> None:
        result = calculate_indicators(self.frame)
        self.assertGreater(result["ema20"], result["ema50"])
        self.assertEqual(result["rsi14"], 100)
        self.assertGreater(result["return_20d_pct"], 0)
        self.assertGreater(result["volume_ratio"], 1)

    def test_chart_is_bounded(self) -> None:
        chart = make_chart(self.frame, points=30)
        self.assertEqual(len(chart), 30)
        self.assertEqual(set(chart[-1]), {"date", "close"})


if __name__ == "__main__":
    unittest.main()
