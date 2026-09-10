from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
WINDOW_START = time(5, 30)
WINDOW_END = time(9, 20)


def should_run(*, now: datetime, report_path: Path, event_name: str) -> tuple[bool, str]:
    if event_name == "workflow_dispatch":
        return True, "manual dispatch always refreshes"
    eastern = now.astimezone(EASTERN)
    if eastern.weekday() >= 5:
        return False, "weekend"
    if not WINDOW_START <= eastern.time().replace(tzinfo=None) <= WINDOW_END:
        return False, f"outside premarket window ({eastern:%H:%M ET})"

    try:
        raw = json.loads(report_path.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(str(raw["generated_at"]).replace("Z", "+00:00")).astimezone(EASTERN)
        already_fresh = generated.date() == eastern.date() and generated.time().replace(tzinfo=None) >= WINDOW_START
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        already_fresh = False
    if already_fresh:
        return False, "today's premarket report already exists"
    return True, "first eligible run in the premarket window"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate redundant GitHub schedules to one premarket refresh.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--event", default=os.getenv("GITHUB_EVENT_NAME", "schedule"))
    parser.add_argument("--now", help="ISO timestamp used by tests or diagnostics")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(EASTERN)
    run, reason = should_run(now=now, report_path=args.report, event_name=args.event)
    output = f"should_run={'true' if run else 'false'}\n"
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            handle.write(output)
    else:
        print(output, end="")
    print(f"Premarket gate: {reason}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
