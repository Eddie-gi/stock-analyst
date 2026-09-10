from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"report is not valid JSON: {exc}"]

    required = {
        "schema_version", "generated_at", "summary", "quality", "portfolio", "candidates",
        "agents", "sources", "intelligence", "global_markets",
    }
    missing = sorted(required - report.keys())
    if missing:
        errors.append(f"missing top-level keys: {', '.join(missing)}")
    if report.get("schema_version") != 2:
        errors.append("unsupported schema_version")
    if not isinstance(report.get("portfolio"), list) or not report.get("portfolio"):
        errors.append("portfolio must contain at least one holding")
    for collection_name in ("portfolio", "candidates"):
        for index, item in enumerate(report.get(collection_name, [])):
            if not item.get("ticker"):
                errors.append(f"{collection_name}[{index}] has no ticker")
            score_key = "signal_score" if collection_name == "portfolio" else "setup_score"
            score = item.get(score_key)
            if not isinstance(score, (int, float)) or not 0 <= score <= 100:
                errors.append(f"{collection_name}[{index}].{score_key} is outside 0-100")
            for source_group in ("news", "filings"):
                for source in item.get(source_group, []):
                    url = source.get("url", "")
                    if url and urlparse(url).scheme not in {"https", "http"}:
                        errors.append(f"unsafe source URL for {item.get('ticker')}")
    intelligence = report.get("intelligence", {})
    if not isinstance(intelligence.get("review_queue"), list):
        errors.append("intelligence.review_queue must be a list")
    for item in intelligence.get("review_queue", []):
        if not item.get("title") or not item.get("publisher"):
            errors.append("intelligence item is missing a title or publisher")
        if urlparse(item.get("url", "")).scheme not in {"https", "http"}:
            errors.append("intelligence item has an unsafe source URL")
        if item.get("priority") not in {"must-review", "scan", "background"}:
            errors.append("intelligence item has an invalid priority")
    for market in report.get("global_markets", []):
        if market.get("url") and urlparse(market["url"]).scheme not in {"https", "http"}:
            errors.append("global market has an unsafe source URL")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Signal Desk JSON report.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        print("Report validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Report validation passed: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
