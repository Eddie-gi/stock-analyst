import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agents.config import FeedSource
from agents.models import FeedHealth, NewsItem
from agents.nodes.intelligence import IntelligenceAgent
from agents.providers.rss import parse_feed
from scripts.should_run_premarket import should_run


class FeedTests(unittest.TestCase):
    def test_parses_rss_and_atom_without_article_bodies(self) -> None:
        source = FeedSource("Test", "https://example.com/feed", "international", "Asia", "markets", 10)
        rss = b"""<rss><channel><item><title>Asia chips rise</title><link>https://example.com/a</link><pubDate>Wed, 09 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
        atom = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Market video</title><link rel='alternate' href='https://youtube.com/watch?v=x'/><author><name>Channel</name></author><published>2026-09-09T11:00:00Z</published></entry></feed>"""
        self.assertEqual(parse_feed(rss, source)[0].title, "Asia chips rise")
        self.assertEqual(parse_feed(atom, source)[0].publisher, "Channel")

    def test_triage_prioritizes_filing_and_watchlist_match(self) -> None:
        now = datetime(2026, 9, 10, 11, tzinfo=timezone.utc)
        holdings = [{"ticker": "NVDA", "news": [], "filings": [{"form": "8-K", "description": "Current report", "filed_at": "2026-09-10", "url": "https://sec.gov/a"}]}]
        feeds = [NewsItem("Nvidia chip export rules change", "https://example.com/nvda", "Asia Desk", now.isoformat(), "international", "Asia", "markets")]
        health = [FeedHealth("Asia Desk", "https://example.com/feed", "international", "Asia", "healthy", 1, now.isoformat())]
        result = IntelligenceAgent().run(holdings, feeds, health, now, limit=20)
        self.assertEqual(result["must_review_count"], 2)
        self.assertEqual(result["review_queue"][0]["source_type"], "filing")
        self.assertIn("NVDA", result["review_queue"][1]["tickers"])


class PremarketGateTests(unittest.TestCase):
    def test_redundant_schedule_runs_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "latest.json"
            report.write_text(json.dumps({"generated_at": "2026-09-09T11:00:00Z"}), encoding="utf-8")
            run, _ = should_run(now=datetime.fromisoformat("2026-09-10T06:11:00-04:00"), report_path=report, event_name="schedule")
            self.assertTrue(run)
            report.write_text(json.dumps({"generated_at": "2026-09-10T06:12:00-04:00"}), encoding="utf-8")
            run, _ = should_run(now=datetime.fromisoformat("2026-09-10T07:11:00-04:00"), report_path=report, event_name="schedule")
            self.assertFalse(run)

    def test_manual_dispatch_bypasses_window(self) -> None:
        run, _ = should_run(now=datetime.fromisoformat("2026-09-10T12:00:00-04:00"), report_path=Path("missing.json"), event_name="workflow_dispatch")
        self.assertTrue(run)


if __name__ == "__main__":
    unittest.main()
