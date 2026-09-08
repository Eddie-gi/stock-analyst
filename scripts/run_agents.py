from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.config import load_settings
from agents.orchestrator import AgentOrchestrator, export_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Signal Desk premarket agent network.")
    parser.add_argument("--config", default=ROOT / "config" / "watchlist.yaml", type=Path)
    parser.add_argument("--output", default=ROOT / "public" / "data" / "latest.json", type=Path)
    parser.add_argument("--archive", default=ROOT / "public" / "data" / "history", type=Path)
    parser.add_argument("--workers", default=4, type=int)
    parser.add_argument("--skip-sec", action="store_true", help="Skip SEC calls for a faster diagnostic run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(args.config)
    orchestrator = AgentOrchestrator(settings, max_workers=args.workers)
    report = orchestrator.run(include_sec=not args.skip_sec)
    export_report(report, args.output, args.archive, settings.archive_days)
    print(
        f"Signal Desk refresh complete: {len(report['portfolio'])} holdings, "
        f"{len(report['candidates'])} candidates, quality {report['quality']['score']}/100."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
