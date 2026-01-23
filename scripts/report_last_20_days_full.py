#!/usr/bin/env python3
"""Full DB report for last 20 days: status + all column values per date"""

import os
from datetime import datetime, timedelta, date
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CFG = {
    "host": os.getenv("DATABASE_HOST", "localhost"),
    "port": int(os.getenv("DATABASE_PORT", 5432)),
    "database": os.getenv("DATABASE_NAME", "kolmo_db"),
    "user": os.getenv("DATABASE_USER", "postgres"),
    "password": os.getenv("DATABASE_PASSWORD", "postgres"),
}


def business_days(start: date, end: date) -> set[date]:
    days = set()
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.add(cur)
        cur += timedelta(days=1)
    return days


def main() -> int:
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=20)

    # Connect
    conn = psycopg2.connect(**DB_CFG)

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch rows in range
        cur.execute(
            """
            SELECT *
            FROM mcol1_external_data
            WHERE date >= %s AND date <= %s
            ORDER BY date DESC
            """,
            (start_date, end_date),
        )
        rows = cur.fetchall()

        # Collect dates present
        present_dates = {r["date"] for r in rows}
        bdays = business_days(start_date, end_date)
        missing = sorted(bdays - present_dates, reverse=True)

        # Header
        print("\n" + "=" * 80)
        print("📊 DATABASE REPORT - LAST 20 DAYS (FULL)")
        print("=" * 80)
        print(f"Date Range: {start_date} to {end_date}")
        print(f"Business days (Mon-Fri): {len(bdays)}")
        print(f"Dates with data: {len(present_dates)}/{len(bdays)}")
        print(f"Missing dates: {len(missing)}")
        if missing:
            print("\nMissing dates:")
            for d in missing:
                print(f"  - {d}")
        print("-" * 80)

        # Print all columns for each row (per date)
        for r in rows:
            print(f"\n📅 {r['date']}")
            print("-" * 40)
            # Sort keys for stable output: date first, then others
            keys = ["id", "date", "eur_usd", "eur_usd_pair_desc", "eur_cny", "eur_cny_pair_desc",
                    "eur_rub", "eur_rub_pair_desc", "eur_inr", "eur_inr_pair_desc", "eur_aed", "eur_aed_pair_desc",
                    "mcol1_snapshot_id", "trace_id", "sources", "created_at", "updated_at"]
            # Fallback if schema changes
            keys = [k for k in keys if k in r.keys()] + [k for k in r.keys() if k not in keys]

            for k in keys:
                val = r.get(k)
                # Truncate very long values for readability
                s = str(val)
                if s is not None and len(s) > 300:
                    s = s[:300] + "... (truncated)"
                print(f"{k:20s}: {s}")

        print("\n" + "=" * 80 + "\n")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
