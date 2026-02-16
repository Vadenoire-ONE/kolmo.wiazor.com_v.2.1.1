"""Enrich kolmo_history.json with Frankfurter API cross-rates for USD, EUR, CNY.

For every entry in kolmo_history.json within [START_DATE..END_DATE] this script
adds six Frankfurter exchange-rate fields:

    frank_usd_eur  –  1 USD → ? EUR
    frank_usd_cny  –  1 USD → ? CNY
    frank_eur_usd  –  1 EUR → ? USD
    frank_eur_cny  –  1 EUR → ? CNY
    frank_cny_usd  –  1 CNY → ? USD
    frank_cny_eur  –  1 CNY → ? EUR

Data source
-----------
Frankfurter API  (https://frankfurter.dev/)

Relevant endpoints used:
    GET /v1/{start_date}..{end_date}?base={BASE}&symbols={SYM1},{SYM2}
        Returns a time-series of daily rates published by the ECB.
        Dates in UTC; only working days are included.
        Default base is EUR.  Tip: filter symbols to reduce payload.

    GET /v1/latest
        Latest working-day rates (updated daily ~16:00 CET).

    GET /v1/{date}
        Historical rates for a specific date.

    GET /v1/currencies
        List of supported ISO 4217 currency codes and names.

Forward-fill strategy
---------------------
Frankfurter publishes rates only on ECB working days (weekdays, no holidays).
For kolmo_history dates that fall on non-working days the script carries forward
the most recent available Frankfurter rate.

Usage
-----
    python scripts/enrich_kolmo_with_frankfurter.py

A backup of the original file is created at kolmo_history.json.bak before write.
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
KOLMO_PATH = ROOT / "data" / "export" / "kolmo_history.json"
START_DATE = "2022-07-01"
END_DATE = "2026-02-03"

# Frankfurter time-series API base
API_BASE = "https://api.frankfurter.dev/v1"

# The three queries we need (base → symbols)
QUERIES: list[tuple[str, str]] = [
    ("USD", "EUR,CNY"),
    ("EUR", "USD,CNY"),
    ("CNY", "USD,EUR"),
]

# Chunk size (days) – Frankfurter can return large payloads; 365 is safe.
CHUNK_DAYS = 365


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fetch_json(url: str, retries: int = 3, backoff: float = 2.0) -> dict:
    """Fetch a URL and return parsed JSON with retry logic."""
    headers = {"User-Agent": "kolmo-enricher/1.0 (Python urllib)"}
    for attempt in range(retries):
        try:
            print(f"  GET {url}")
            req = Request(url, headers=headers)
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            wait = backoff * (attempt + 1)
            print(f"    ⚠ attempt {attempt+1}/{retries} failed: {exc}; retry in {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def daterange_chunks(start: date, end: date, chunk: int):
    """Yield (chunk_start, chunk_end) pairs covering [start..end]."""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def fetch_timeseries(base: str, symbols: str, start: date, end: date) -> Dict[str, Dict[str, float]]:
    """Fetch Frankfurter time-series in chunks, return {date_str: {SYM: rate}}."""
    merged: Dict[str, Dict[str, float]] = {}
    for cs, ce in daterange_chunks(start, end, CHUNK_DAYS):
        url = f"{API_BASE}/{cs.isoformat()}..{ce.isoformat()}?base={base}&symbols={symbols}"
        data = fetch_json(url)
        rates = data.get("rates", {})
        merged.update(rates)
        # polite pause between chunks
        time.sleep(0.5)
    return merged


def forward_fill(rates_by_date: Dict[str, Dict[str, float]],
                 all_dates: List[str]) -> Dict[str, Dict[str, float]]:
    """Produce a dict covering *all_dates* by forward-filling missing ones."""
    filled: Dict[str, Dict[str, float]] = {}
    last_known: Dict[str, float] | None = None
    for ds in all_dates:
        if ds in rates_by_date:
            last_known = rates_by_date[ds]
        if last_known is not None:
            filled[ds] = last_known
    return filled


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    start = date.fromisoformat(START_DATE)
    end = date.fromisoformat(END_DATE)

    print(f"Loading {KOLMO_PATH} ...")
    kolmo: List[Dict[str, Any]] = json.loads(KOLMO_PATH.read_text(encoding="utf-8"))
    print(f"  Loaded {len(kolmo)} entries  ({kolmo[0]['date']} → {kolmo[-1]['date']})")

    # Dates within the enrichment range
    target_dates = sorted({e["date"] for e in kolmo if START_DATE <= e["date"] <= END_DATE})
    print(f"  Entries to enrich: {len(target_dates)}  ({target_dates[0]} → {target_dates[-1]})")

    # Build a full calendar for forward-fill alignment
    all_calendar = []
    cur = start
    while cur <= end:
        all_calendar.append(cur.isoformat())
        cur += timedelta(days=1)

    # -----------------------------------------------------------------------
    # Fetch Frankfurter data
    # -----------------------------------------------------------------------
    # We'll store {date_str: {field_name: rate_value}}
    enrichment: Dict[str, Dict[str, Any]] = {}

    for base, symbols in QUERIES:
        sym_list = symbols.split(",")
        print(f"\nFetching Frankfurter  base={base}  symbols={symbols}  ({START_DATE}..{END_DATE})")
        raw = fetch_timeseries(base, symbols, start, end)
        print(f"  Received {len(raw)} working-day entries")

        filled = forward_fill(raw, all_calendar)
        print(f"  After forward-fill: {len(filled)} entries")

        for ds, rates in filled.items():
            if ds not in enrichment:
                enrichment[ds] = {}
            for sym in sym_list:
                field = f"frank_{base.lower()}_{sym.lower()}"
                enrichment[ds][field] = rates.get(sym)

    # -----------------------------------------------------------------------
    # Merge into kolmo entries
    # -----------------------------------------------------------------------
    enriched_count = 0
    for entry in kolmo:
        ds = entry["date"]
        if ds in enrichment:
            entry.update(enrichment[ds])
            enriched_count += 1

    print(f"\nEnriched {enriched_count} entries out of {len(kolmo)} total.")

    # Backup then write
    bak = KOLMO_PATH.with_suffix(KOLMO_PATH.suffix + ".bak")
    print(f"Backing up → {bak}")
    shutil.copy2(KOLMO_PATH, bak)

    print(f"Writing updated {KOLMO_PATH} ...")
    KOLMO_PATH.write_text(json.dumps(kolmo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Done ✓")


if __name__ == "__main__":
    main()
