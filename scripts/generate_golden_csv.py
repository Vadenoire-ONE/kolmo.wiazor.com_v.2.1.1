#!/usr/bin/env python3
"""Generate `tests/golden/kolmo_reference_data.csv` from DB compute + external tables.

Usage:
  python scripts/generate_golden_csv.py --start 2025-01-01 --end 2025-03-31

If no range provided, exports all available dates.
"""

import argparse
import asyncio
import csv
from pathlib import Path
import sys

# Ensure src on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncpg
from kolmo.config import Settings
from datetime import date


CSV_HEADER = [
    "date",
    "eur_usd",
    "eur_cny",
    "eur_rub",
    "eur_inr",
    "eur_aed",
    "r_me4u",
    "r_iou2",
    "r_uome",
    "kolmo_value_exact",
    "dist_me4u",
    "dist_iou2",
    "dist_uome",
    "relpath_me4u",
    "relpath_iou2",
    "relpath_uome",
    "winner",
]


async def fetch_rows(pool: asyncpg.Pool, start_date: str | None, end_date: str | None):
    q = """
    SELECT
      c.date,
      e.eur_usd, e.eur_cny, e.eur_rub, e.eur_inr, e.eur_aed,
      c.r_me4u, c.r_iou2, c.r_uome,
      c.kolmo_value, c.dist_me4u, c.dist_iou2, c.dist_uome,
      c.relpath_me4u, c.relpath_iou2, c.relpath_uome,
      c.winner
    FROM mcol1_compute_data c
    LEFT JOIN mcol1_external_data e
      ON e.mcol1_snapshot_id = c.mcol1_snapshot_id
    """
    params = []
    if start_date and end_date:
        q += " WHERE c.date BETWEEN $1 AND $2 "
        q += " ORDER BY c.date ASC"
        params = [start_date, end_date]
    else:
        q += " ORDER BY c.date ASC"

    rows = await pool.fetch(q, *params) if params else await pool.fetch(q)
    return rows


async def main():
    parser = argparse.ArgumentParser(description="Generate golden CSV from DB")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD", default=None)
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD", default=None)
    parser.add_argument("--output", type=str, help="Output CSV path", default="tests/golden/kolmo_reference_data.csv")
    args = parser.parse_args()

    settings = Settings()
    # Convert start/end to date objects for asyncpg parameter binding
    start_date = date.fromisoformat(args.start) if args.start else None
    end_date = date.fromisoformat(args.end) if args.end else None

    dsn = (
        f"postgresql://{settings.database_user}:{settings.database_password}"
        f"@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    try:
        rows = await fetch_rows(pool, start_date, end_date)

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            for r in rows:
                writer.writerow([
                    r["date"].isoformat(),
                    str(r["eur_usd"]) if r.get("eur_usd") is not None else "",
                    str(r["eur_cny"]) if r.get("eur_cny") is not None else "",
                    str(r["eur_rub"]) if r.get("eur_rub") is not None else "",
                    str(r["eur_inr"]) if r.get("eur_inr") is not None else "",
                    str(r["eur_aed"]) if r.get("eur_aed") is not None else "",
                    str(r["r_me4u"]),
                    str(r["r_iou2"]),
                    str(r["r_uome"]),
                    str(r["kolmo_value"]),
                    f"{float(r['dist_me4u']):.7f}" if r.get("dist_me4u") is not None else "",
                    f"{float(r['dist_iou2']):.7f}" if r.get("dist_iou2") is not None else "",
                    f"{float(r['dist_uome']):.7f}" if r.get("dist_uome") is not None else "",
                    (f"{float(r['relpath_me4u']):.7f}" if r.get("relpath_me4u") is not None else ""),
                    (f"{float(r['relpath_iou2']):.7f}" if r.get("relpath_iou2") is not None else ""),
                    (f"{float(r['relpath_uome']):.7f}" if r.get("relpath_uome") is not None else ""),
                    r["winner"] if r.get("winner") is not None else "",
                ])

        print(f"Wrote {out_path} ({len(rows)} rows)")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
