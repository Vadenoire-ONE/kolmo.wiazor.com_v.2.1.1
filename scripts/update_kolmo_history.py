"""Update kolmo_history.json to today using Frankfurter API (no DB required).

Fetches EUR/USD and EUR/CNY from Frankfurter, computes all KOLMO metrics
(rates, distances, relpaths, winner, deviation, volatility), adds frank_*
cross-rate fields, and appends new entries.

Usage:
    python scripts/update_kolmo_history.py
    python scripts/update_kolmo_history.py --end-date 2026-02-10
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import date, timedelta
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# Decimal precision matching the project standard
getcontext().prec = 28

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
KOLMO_PATH = ROOT / "data" / "export" / "kolmo_history.json"
API_BASE = "https://api.frankfurter.dev/v1"
CHUNK_DAYS = 365

# Frankfurter queries for frank_* enrichment fields
FRANK_QUERIES: list[tuple[str, str]] = [
    ("USD", "EUR,CNY"),
    ("EUR", "USD,CNY"),
    ("CNY", "USD,EUR"),
]

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def fetch_json(url: str, retries: int = 3, backoff: float = 2.0) -> dict:
    """Fetch URL → JSON with retry logic and mandatory User-Agent."""
    headers = {"User-Agent": "kolmo-updater/1.0 (Python urllib)"}
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

# ---------------------------------------------------------------------------
# Frankfurter data fetching
# ---------------------------------------------------------------------------

def daterange_chunks(start: date, end: date, chunk: int):
    """Yield (chunk_start, chunk_end) pairs covering [start..end]."""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def fetch_timeseries(base: str, symbols: str, start: date, end: date) -> Dict[str, Dict[str, float]]:
    """Fetch Frankfurter time-series in chunks → {date_str: {SYM: rate}}."""
    merged: Dict[str, Dict[str, float]] = {}
    for cs, ce in daterange_chunks(start, end, CHUNK_DAYS):
        url = f"{API_BASE}/{cs.isoformat()}..{ce.isoformat()}?base={base}&symbols={symbols}"
        data = fetch_json(url)
        rates = data.get("rates", {})
        merged.update(rates)
        time.sleep(0.5)
    return merged


def forward_fill(rates_by_date: Dict[str, Dict[str, float]],
                 all_dates: List[str]) -> Dict[str, Dict[str, float]]:
    """Forward-fill missing dates (weekends/holidays) from last known rate."""
    filled: Dict[str, Dict[str, float]] = {}
    last_known: Dict[str, float] | None = None
    for ds in all_dates:
        if ds in rates_by_date:
            last_known = rates_by_date[ds]
        if last_known is not None:
            filled[ds] = last_known
    return filled


# ---------------------------------------------------------------------------
# KOLMO metric computations  (mirrors src/kolmo/computation/)
# ---------------------------------------------------------------------------

def compute_rates(eur_usd: Decimal, eur_cny: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Transform EUR-based rates to KOLMO notation.
    
    r_me4u = eur_usd / eur_cny   (USD/CNY)
    r_iou2 = 1 / eur_usd         (EUR/USD)
    r_uome = eur_cny              (CNY/EUR)
    """
    r_me4u = eur_usd / eur_cny
    r_iou2 = Decimal("1") / eur_usd
    r_uome = eur_cny
    return r_me4u, r_iou2, r_uome


def compute_distance(rate: Decimal) -> Decimal:
    """dist = |rate − 1.0| × 100"""
    return abs(rate - Decimal("1.0")) * Decimal("100")


def compute_relpath(dist_curr: Decimal, dist_prev: Optional[Decimal]) -> Optional[Decimal]:
    """relpath = (dist_prev − dist_curr) / dist_prev × 100"""
    if dist_prev is None or dist_prev == Decimal("0"):
        return None
    return ((dist_prev - dist_curr) / dist_prev) * Decimal("100")


def select_winner(rp_me4u: Optional[Decimal],
                  rp_iou2: Optional[Decimal],
                  rp_uome: Optional[Decimal]) -> str:
    """Select winner coin: max positive relpath, alphabetical tie-break."""
    candidates: Dict[str, Decimal] = {}
    if rp_me4u is not None:
        candidates["ME4U"] = rp_me4u
    if rp_iou2 is not None:
        candidates["IOU2"] = rp_iou2
    if rp_uome is not None:
        candidates["UOME"] = rp_uome
    if not candidates:
        return "IOU2"
    max_val = max(candidates.values())
    tied = sorted(c for c, v in candidates.items() if v == max_val)
    return tied[0]


def compute_volatility(rate_curr: Decimal, rate_prev: Decimal) -> float:
    """vol = (rate_curr − rate_prev) / rate_prev × 100"""
    if rate_prev == Decimal("0"):
        return 0.0
    return float((rate_curr - rate_prev) / rate_prev * Decimal("100"))


def format_deviation(kolmo_value: Decimal) -> str:
    """Format kolmo_deviation as '<val * 1e5>e-5' string matching existing data."""
    deviation = kolmo_value - Decimal("1.0")
    return f"{float(deviation) * 1e5:.18f}e-5"


def format_rate(rate: Decimal) -> str:
    """Format rate to 6 decimal places string matching existing data."""
    return f"{float(rate):.6f}"

# ---------------------------------------------------------------------------
# Previous-day context extraction
# ---------------------------------------------------------------------------

def extract_prev_context(entry: Dict[str, Any]) -> dict:
    """Extract distances and rates from the last kolmo_history entry."""
    r_me4u = Decimal(entry["r_me4u"])
    r_iou2 = Decimal(entry["r_iou2"])
    r_uome = Decimal(entry["r_uome"])
    return {
        "r_me4u": r_me4u,
        "r_iou2": r_iou2,
        "r_uome": r_uome,
        "dist_me4u": compute_distance(r_me4u),
        "dist_iou2": compute_distance(r_iou2),
        "dist_uome": compute_distance(r_uome),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Update kolmo_history.json to today")
    parser.add_argument("--end-date", type=str, default=None,
                        help="Target end date (YYYY-MM-DD). Default: today")
    args = parser.parse_args()

    target_end = date.fromisoformat(args.end_date) if args.end_date else date.today()

    # Load existing data
    print(f"Loading {KOLMO_PATH} ...")
    kolmo: List[Dict[str, Any]] = json.loads(KOLMO_PATH.read_text(encoding="utf-8"))
    last_date_str = kolmo[-1]["date"]
    last_date = date.fromisoformat(last_date_str)
    print(f"  {len(kolmo)} entries, last date: {last_date_str}")

    start_date = last_date + timedelta(days=1)
    if start_date > target_end:
        print(f"  Already up to date (last={last_date_str}, target={target_end}). Nothing to do.")
        return

    # Build calendar of dates to add
    new_dates: List[str] = []
    cur = start_date
    while cur <= target_end:
        new_dates.append(cur.isoformat())
        cur += timedelta(days=1)
    print(f"  Will add {len(new_dates)} dates: {new_dates[0]} → {new_dates[-1]}")

    # -------------------------------------------------------------------
    # Fetch EUR → USD,CNY  (primary rates for KOLMO computation)
    # -------------------------------------------------------------------
    print(f"\nFetching EUR → USD,CNY from Frankfurter ({start_date} .. {target_end}) ...")
    raw_eur = fetch_timeseries("EUR", "USD,CNY", start_date, target_end)
    print(f"  Working-day entries: {len(raw_eur)}")
    eur_filled = forward_fill(raw_eur, new_dates)
    print(f"  After forward-fill: {len(eur_filled)} entries")

    if not eur_filled:
        print("  ⚠ No Frankfurter data available for the requested range. Aborting.")
        return

    # -------------------------------------------------------------------
    # Fetch cross-rates for frank_* enrichment fields
    # -------------------------------------------------------------------
    enrichment: Dict[str, Dict[str, Any]] = {}
    for base, symbols in FRANK_QUERIES:
        sym_list = symbols.split(",")
        print(f"\nFetching frank_* fields: base={base} symbols={symbols} ...")
        raw = fetch_timeseries(base, symbols, start_date, target_end)
        filled = forward_fill(raw, new_dates)
        print(f"  Filled: {len(filled)} entries")
        for ds, rates in filled.items():
            if ds not in enrichment:
                enrichment[ds] = {}
            for sym in sym_list:
                field = f"frank_{base.lower()}_{sym.lower()}"
                enrichment[ds][field] = rates.get(sym)

    # -------------------------------------------------------------------
    # Compute metrics and build new entries
    # -------------------------------------------------------------------
    print(f"\nComputing KOLMO metrics for {len(new_dates)} dates ...")
    prev_ctx = extract_prev_context(kolmo[-1])
    new_entries: List[Dict[str, Any]] = []

    for ds in new_dates:
        if ds not in eur_filled:
            print(f"  ⚠ Skipping {ds}: no rate data")
            continue

        eur_usd = Decimal(str(eur_filled[ds]["USD"]))
        eur_cny = Decimal(str(eur_filled[ds]["CNY"]))

        # Rates (exact internal math: K = r_me4u * r_iou2 * r_uome = 1)
        r_me4u, r_iou2, r_uome = compute_rates(eur_usd, eur_cny)

        # Round rates for storage (6 decimal places, matching existing data)
        # KOLMO invariant arises from market data rounding, not internal math
        r_me4u_stored = Decimal(format_rate(r_me4u))
        r_iou2_stored = Decimal(format_rate(r_iou2))
        r_uome_stored = Decimal(format_rate(r_uome))

        # Distances (from stored/rounded rates)
        dist_me4u = compute_distance(r_me4u_stored)
        dist_iou2 = compute_distance(r_iou2_stored)
        dist_uome = compute_distance(r_uome_stored)

        # Relpaths
        rp_me4u = compute_relpath(dist_me4u, prev_ctx["dist_me4u"])
        rp_iou2 = compute_relpath(dist_iou2, prev_ctx["dist_iou2"])
        rp_uome = compute_relpath(dist_uome, prev_ctx["dist_uome"])

        # Winner
        winner = select_winner(rp_me4u, rp_iou2, rp_uome)

        # KOLMO invariant from STORED (rounded) rates — market deviation
        kolmo_value = r_me4u_stored * r_iou2_stored * r_uome_stored
        deviation_str = format_deviation(kolmo_value)

        # Volatility (from stored rates for consistency)
        vol_me4u = compute_volatility(r_me4u_stored, prev_ctx["r_me4u"])
        vol_iou2 = compute_volatility(r_iou2_stored, prev_ctx["r_iou2"])
        vol_uome = compute_volatility(r_uome_stored, prev_ctx["r_uome"])

        entry: Dict[str, Any] = {
            "date": ds,
            "r_me4u": format_rate(r_me4u),
            "r_iou2": format_rate(r_iou2),
            "r_uome": format_rate(r_uome),
            "relpath_me4u": round(float(rp_me4u), 4) if rp_me4u is not None else None,
            "relpath_iou2": round(float(rp_iou2), 4) if rp_iou2 is not None else None,
            "relpath_uome": round(float(rp_uome), 4) if rp_uome is not None else None,
            "vol_me4u": vol_me4u,
            "vol_iou2": vol_iou2,
            "vol_uome": vol_uome,
            "winner": winner,
            "kolmo_deviation": deviation_str,
        }

        # frank_* fields
        if ds in enrichment:
            entry.update(enrichment[ds])

        new_entries.append(entry)
        print(f"  ✅ {ds}: winner={winner}, K_dev={deviation_str}")

        # Update prev context for next iteration (use stored/rounded values)
        prev_ctx = {
            "r_me4u": r_me4u_stored,
            "r_iou2": r_iou2_stored,
            "r_uome": r_uome_stored,
            "dist_me4u": dist_me4u,
            "dist_iou2": dist_iou2,
            "dist_uome": dist_uome,
        }

    if not new_entries:
        print("\nNo new entries to add.")
        return

    # -------------------------------------------------------------------
    # Save
    # -------------------------------------------------------------------
    kolmo.extend(new_entries)

    bak = KOLMO_PATH.with_suffix(KOLMO_PATH.suffix + ".bak")
    print(f"\nBacking up → {bak}")
    shutil.copy2(KOLMO_PATH, bak)

    print(f"Writing {len(kolmo)} entries to {KOLMO_PATH} ...")
    KOLMO_PATH.write_text(
        json.dumps(kolmo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Done ✓  Added {len(new_entries)} new entries ({new_entries[0]['date']} → {new_entries[-1]['date']})")


if __name__ == "__main__":
    main()
