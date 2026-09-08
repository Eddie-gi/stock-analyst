from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from urllib.request import Request, urlopen

from ..models import FilingItem


class SecFilingsProvider:
    """Keyless SEC EDGAR submissions adapter with source links and a small in-memory cache."""

    name = "SEC EDGAR"
    _ticker_map_url = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str, timeout: int = 20) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._ticker_map: dict[str, int] | None = None

    def recent_filings(self, ticker: str, *, days: int = 45, limit: int = 4) -> list[FilingItem]:
        cik = self._get_ticker_map().get(ticker.upper())
        if cik is None:
            return []
        payload = self._get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        recent = payload.get("filings", {}).get("recent", {})
        cutoff = date.today() - timedelta(days=days)
        filings: list[FilingItem] = []
        relevant_forms = {"8-K", "10-Q", "10-K", "6-K", "20-F", "40-F", "DEF 14A"}

        forms = recent.get("form", [])
        for index, form in enumerate(forms):
            filed_at = _at(recent, "filingDate", index)
            if form not in relevant_forms or not filed_at or date.fromisoformat(filed_at) < cutoff:
                continue
            accession = _at(recent, "accessionNumber", index)
            primary_document = _at(recent, "primaryDocument", index)
            if not accession or not primary_document:
                continue
            accession_path = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{primary_document}"
            description = _at(recent, "primaryDocDescription", index) or _at(recent, "items", index) or form
            filings.append(FilingItem(form=form, filed_at=filed_at, description=description, url=url))
            if len(filings) >= limit:
                break
        return filings

    def _get_ticker_map(self) -> dict[str, int]:
        if self._ticker_map is None:
            payload = self._get_json(self._ticker_map_url)
            self._ticker_map = {
                str(record["ticker"]).upper(): int(record["cik_str"])
                for record in payload.values()
                if record.get("ticker") and record.get("cik_str")
            }
        return self._ticker_map

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)


def _at(mapping: dict[str, list[Any]], key: str, index: int) -> str:
    values = mapping.get(key, [])
    if index >= len(values) or values[index] is None:
        return ""
    return str(values[index]).strip()
