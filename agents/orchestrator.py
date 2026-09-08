from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, TypeVar
from zoneinfo import ZoneInfo

from .config import Settings
from .models import AgentRun, MarketSnapshot
from .nodes import PortfolioMonitorAgent, QualityAgent, RiskAgent, ScreenerAgent, SynthesisAgent
from .providers import SecFilingsProvider, YahooFinanceProvider

T = TypeVar("T")


class AgentOrchestrator:
    """Small, auditable DAG: collect -> monitor/screen -> risk -> synthesize -> quality."""

    def __init__(
        self,
        settings: Settings,
        *,
        market_provider: YahooFinanceProvider | None = None,
        sec_provider: SecFilingsProvider | None = None,
        max_workers: int = 4,
    ) -> None:
        self.settings = settings
        self.market_provider = market_provider or YahooFinanceProvider()
        self.sec_provider = sec_provider or SecFilingsProvider(settings.sec_user_agent)
        self.max_workers = max(1, min(max_workers, 6))
        self.runs: list[AgentRun] = []

    def run(self, *, include_sec: bool = True) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc)
        watchlist = list(self.settings.watchlist)
        universe = list(dict.fromkeys([*watchlist, *self.settings.screener_universe]))

        snapshots = self._phase(
            "market-data",
            "Market and news collector",
            lambda: self._collect_market_data(universe, set(watchlist)),
            lambda result: f"Collected {sum(item.price is not None for item in result)}/{len(result)} price snapshots.",
        )
        if include_sec:
            self._phase(
                "sec-filings",
                "SEC filings collector",
                lambda: self._attach_filings(snapshots, watchlist),
                lambda result: f"Linked {sum(len(item.filings) for item in result)} recent filing(s).",
            )

        snapshot_by_ticker = {snapshot.ticker: snapshot for snapshot in snapshots}
        portfolio_snapshots = [snapshot_by_ticker[ticker] for ticker in watchlist if ticker in snapshot_by_ticker]
        universe_snapshots = [snapshot_by_ticker[ticker] for ticker in self.settings.screener_universe if ticker in snapshot_by_ticker]

        holdings, alerts = self._phase(
            PortfolioMonitorAgent.id,
            PortfolioMonitorAgent.label,
            lambda: PortfolioMonitorAgent().run(portfolio_snapshots),
            lambda result: f"Scored {len(result[0])} holdings and raised {len(result[1])} alert(s).",
        )
        candidates = self._phase(
            ScreenerAgent.id,
            ScreenerAgent.label,
            lambda: ScreenerAgent().run(
                universe_snapshots,
                market_cap_min=self.settings.market_cap_min,
                max_candidates=self.settings.max_candidates,
            ),
            lambda result: f"Ranked {len(result)} mega-cap candidate(s).",
        )
        risk = self._phase(
            RiskAgent.id,
            RiskAgent.label,
            lambda: RiskAgent().run(holdings, candidates),
            lambda result: f"Portfolio risk classified as {result['level']}.",
        )
        summary = self._phase(
            SynthesisAgent.id,
            SynthesisAgent.label,
            lambda: SynthesisAgent().run(holdings, candidates, alerts, risk),
            lambda result: result["headline"],
        )
        quality = self._phase(
            QualityAgent.id,
            QualityAgent.label,
            lambda: QualityAgent().run(holdings, generated_at),
            lambda result: f"Data quality score {result['score']}/100.",
        )

        return {
            "schema_version": 1,
            "run_id": generated_at.strftime("%Y%m%dT%H%M%SZ"),
            "generated_at": generated_at.isoformat(),
            "is_demo": False,
            "market": _market_context(generated_at),
            "summary": summary,
            "quality": quality,
            "risk": risk,
            "alerts": alerts,
            "portfolio": holdings,
            "candidates": candidates,
            "agents": [run.to_dict() for run in self.runs],
            "sources": [
                {
                    "name": "Yahoo Finance via yfinance",
                    "url": "https://ranaroussi.github.io/yfinance/",
                    "cost": "Free; personal research use only",
                    "covers": "Prices, market cap, earnings dates, news search",
                },
                {
                    "name": "SEC EDGAR",
                    "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
                    "cost": "Free; no API key",
                    "covers": "Recent company filings",
                },
            ],
        }

    def _collect_market_data(self, tickers: list[str], watchlist: set[str]) -> list[MarketSnapshot]:
        snapshots: dict[str, MarketSnapshot] = {}
        remaining = list(tickers)
        # yfinance initializes small SQLite caches on first use. Warm them once in
        # the main thread so parallel workers never race while creating tables.
        if remaining:
            first = remaining.pop(0)
            try:
                snapshots[first] = self.market_provider.snapshot(
                    first,
                    include_news=first in watchlist,
                    news_count=self.settings.news_per_ticker,
                )
            except Exception as exc:
                snapshots[first] = _failed_snapshot(first, f"collector failed: {type(exc).__name__}")
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="signal-desk") as executor:
            futures = {
                executor.submit(
                    self.market_provider.snapshot,
                    ticker,
                    include_news=ticker in watchlist,
                    news_count=self.settings.news_per_ticker,
                ): ticker
                for ticker in remaining
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    snapshots[ticker] = future.result()
                except Exception as exc:
                    snapshots[ticker] = _failed_snapshot(ticker, f"collector failed: {type(exc).__name__}")
        return [snapshots[ticker] for ticker in tickers]

    def _attach_filings(self, snapshots: list[MarketSnapshot], watchlist: list[str]) -> list[MarketSnapshot]:
        by_ticker = {item.ticker: item for item in snapshots}
        for ticker in watchlist:
            snapshot = by_ticker.get(ticker)
            if snapshot is None:
                continue
            try:
                snapshot.filings = self.sec_provider.recent_filings(ticker)
            except Exception as exc:
                snapshot.errors.append(f"SEC filings unavailable: {type(exc).__name__}")
        return snapshots

    def _phase(
        self,
        agent_id: str,
        label: str,
        operation: Callable[[], T],
        summarize: Callable[[T], str],
    ) -> T:
        started = perf_counter()
        try:
            result = operation()
            status = "complete"
            summary = summarize(result)
        except Exception as exc:
            status = "failed"
            summary = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = round((perf_counter() - started) * 1000)
            self.runs.append(AgentRun(agent_id, label, status, duration_ms, summary))
        return result


def export_report(report: dict[str, Any], output_path: str | Path, archive_dir: str | Path, archive_days: int) -> None:
    output = Path(output_path)
    archive = Path(archive_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, output)

    dated = archive / f"{report['generated_at'][:10]}.json"
    dated.write_text(encoded, encoding="utf-8")
    _prune_archive(archive, archive_days)
    index = sorted((path.name for path in archive.glob("*.json") if path.name != "index.json"), reverse=True)
    (archive / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def _prune_archive(archive: Path, keep: int) -> None:
    files = sorted((path for path in archive.glob("*.json") if path.name != "index.json"), reverse=True)
    for path in files[max(1, keep) :]:
        path.unlink()


def _failed_snapshot(ticker: str, error: str) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker,
        name=ticker,
        currency="USD",
        price=None,
        previous_close=None,
        change_pct=None,
        return_5d_pct=None,
        return_20d_pct=None,
        ema20=None,
        ema50=None,
        rsi14=None,
        atr_pct=None,
        volume_ratio=None,
        volatility20_pct=None,
        market_cap=None,
        next_earnings=None,
        earnings_days=None,
        errors=[error],
    )


def _market_context(now_utc: datetime) -> dict[str, Any]:
    eastern = now_utc.astimezone(ZoneInfo("America/New_York"))
    current = eastern.time()
    if eastern.weekday() >= 5:
        session = "closed"
    elif current < time(9, 30):
        session = "premarket"
    elif current <= time(16, 0):
        session = "open"
    else:
        session = "after-hours"
    return {
        "session": session,
        "as_of_et": eastern.isoformat(),
        "next_scheduled_refresh": "7:17 AM America/New_York on weekdays",
    }
