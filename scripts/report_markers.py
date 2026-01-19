"""
Generate a report of key KOLMO markers for the latest 10 days.

Outputs rows with: date, provider, winner, kolmo_value, kolmo_state,
 r_me4u, r_iou2, r_uome, relpath_me4u, relpath_iou2, relpath_uome
"""

import asyncio
from decimal import Decimal
from typing import Any

import asyncpg
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kolmo.config import Settings


async def fetch_latest_markers(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    query = """
    SELECT 
        c.date,
        c.winner,
        c.kolmo_value,
        c.kolmo_state,
        c.r_me4u,
        c.r_iou2,
        c.r_uome,
        c.relpath_me4u,
        c.relpath_iou2,
        c.relpath_uome,
        e.sources
    FROM mcol1_compute_data c
    JOIN mcol1_external_data e
      ON e.mcol1_snapshot_id = c.mcol1_snapshot_id
    ORDER BY c.date DESC
    LIMIT 10;
    """
    rows = await pool.fetch(query)
    results: list[dict[str, Any]] = []
    for r in rows:
        sources = r["sources"] or {}
        provider = sources.get("provider") if isinstance(sources, dict) else None
        results.append({
            "date": r["date"].isoformat(),
            "provider": provider,
            "winner": r["winner"],
            "kolmo_value": str(r["kolmo_value"]),
            "kolmo_state": r["kolmo_state"],
            "r_me4u": str(r["r_me4u"]),
            "r_iou2": str(r["r_iou2"]),
            "r_uome": str(r["r_uome"]),
            "relpath_me4u": float(r["relpath_me4u"]) if r["relpath_me4u"] is not None else None,
            "relpath_iou2": float(r["relpath_iou2"]) if r["relpath_iou2"] is not None else None,
            "relpath_uome": float(r["relpath_uome"]) if r["relpath_uome"] is not None else None,
        })
    return results


async def main():
    settings = Settings()
    dsn = (
        f"postgresql://{settings.database_user}:{settings.database_password}"
        f"@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    try:
        records = await fetch_latest_markers(pool)
        # Pretty print as simple table
        header = (
            "Date        Provider     Winner  KOLMO Value             State    "
            "ME4U      IOU2      UOME      rel_ME4U  rel_IOU2  rel_UOME"
        )
        print(header)
        print("-" * len(header))
        for rec in records:
            print(
                f"{rec['date']:10}  "
                f"{(rec['provider'] or '-'):11}  "
                f"{rec['winner']:6}  "
                f"{rec['kolmo_value']:22}  "
                f"{rec['kolmo_state']:7}  "
                f"{rec['r_me4u']:8}  "
                f"{rec['r_iou2']:8}  "
                f"{rec['r_uome']:8}  "
                f"{(rec['relpath_me4u'] if rec['relpath_me4u'] is not None else '-'):8}  "
                f"{(rec['relpath_iou2'] if rec['relpath_iou2'] is not None else '-'):8}  "
                f"{(rec['relpath_uome'] if rec['relpath_uome'] is not None else '-'):8}"
            )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
