import asyncio
import asyncpg
import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from kolmo.config import Settings


async def main():
    parser = argparse.ArgumentParser(description="Query KOLMO DB for a specific date")
    parser.add_argument("--date", "-d", type=str, required=True, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)

    settings = Settings()
    dsn = (
        f"postgresql://{settings.database_user}:{settings.database_password}"
        f"@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    try:
        row = await pool.fetchrow(
            """
            SELECT 
                date,
                r_me4u, r_iou2, r_uome,
                kolmo_value, kolmo_deviation, kolmo_state,
                dist_me4u, dist_iou2, dist_uome,
                relpath_me4u, relpath_iou2, relpath_uome,
                vol_me4u, vol_iou2, vol_uome,
                winner, winner_reason
            FROM mcol1_compute_data
            WHERE date = $1
            """,
            target_date
        )
        if row:
            print(f"Date: {row['date'].isoformat()}")
            print(f"Winner: {row['winner']}")
            print(f"KOLMO Value: {row['kolmo_value']}")
            print(f"KOLMO Deviation: {row['kolmo_deviation']}")
            print(f"KOLMO State: {row['kolmo_state']}")
            print(f"Rates: r_me4u(USD/CNY)={row['r_me4u']}, r_iou2(EUR/USD)={row['r_iou2']}, r_uome(CNY/EUR)={row['r_uome']}")
            print(f"Distances: dist_me4u={row['dist_me4u']}, dist_iou2={row['dist_iou2']}, dist_uome={row['dist_uome']}")
            print(f"RelativePaths: me4u={row['relpath_me4u']}, iou2={row['relpath_iou2']}, uome={row['relpath_uome']}")
            print(f"Volatility: vol_me4u={row['vol_me4u']}, vol_iou2={row['vol_iou2']}, vol_uome={row['vol_uome']}")
            print(f"Winner Reason: {row['winner_reason']}")
        else:
            print(f"No data found for {target_date.isoformat()}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
