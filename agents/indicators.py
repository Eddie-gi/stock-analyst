from __future__ import annotations

import math

import pandas as pd

from .models import finite_float


def calculate_indicators(history: pd.DataFrame) -> dict[str, float | None]:
    if history.empty or "Close" not in history:
        return _empty_indicators()

    frame = history.dropna(subset=["Close"]).copy()
    if len(frame) < 2:
        return _empty_indicators()

    close = frame["Close"].astype(float)
    high = frame.get("High", close).astype(float)
    low = frame.get("Low", close).astype(float)
    volume = frame.get("Volume", pd.Series(index=frame.index, dtype=float)).astype(float)

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    relative_strength = gains / losses.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + relative_strength))
    if losses.iloc[-1] == 0 and gains.iloc[-1] > 0:
        rsi.iloc[-1] = 100

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(alpha=1 / 14, adjust=False).mean()

    daily_returns = close.pct_change().dropna().tail(20)
    volatility = daily_returns.std(ddof=0) * math.sqrt(252) * 100 if len(daily_returns) > 1 else None
    volume_average = volume.tail(20).mean() if not volume.empty else None

    return {
        "previous_close": finite_float(close.iloc[-2]),
        "change_pct": _return_pct(close, 1),
        "return_5d_pct": _return_pct(close, 5),
        "return_20d_pct": _return_pct(close, 20),
        "ema20": finite_float(ema20.iloc[-1]),
        "ema50": finite_float(ema50.iloc[-1]),
        "rsi14": finite_float(rsi.iloc[-1]),
        "atr_pct": finite_float((atr.iloc[-1] / close.iloc[-1]) * 100),
        "volume_ratio": finite_float(volume.iloc[-1] / volume_average) if volume_average else None,
        "volatility20_pct": finite_float(volatility),
    }


def make_chart(history: pd.DataFrame, points: int = 60) -> list[dict[str, float | str]]:
    if history.empty or "Close" not in history:
        return []
    chart: list[dict[str, float | str]] = []
    for index, value in history["Close"].dropna().tail(points).items():
        date = index.date().isoformat() if hasattr(index, "date") else str(index)[:10]
        chart.append({"date": date, "close": round(float(value), 4)})
    return chart


def _return_pct(close: pd.Series, sessions: int) -> float | None:
    if len(close) <= sessions:
        return None
    baseline = float(close.iloc[-(sessions + 1)])
    if baseline == 0:
        return None
    return finite_float((float(close.iloc[-1]) / baseline - 1) * 100)


def _empty_indicators() -> dict[str, None]:
    return {
        "previous_close": None,
        "change_pct": None,
        "return_5d_pct": None,
        "return_20d_pct": None,
        "ema20": None,
        "ema50": None,
        "rsi14": None,
        "atr_pct": None,
        "volume_ratio": None,
        "volatility20_pct": None,
    }
