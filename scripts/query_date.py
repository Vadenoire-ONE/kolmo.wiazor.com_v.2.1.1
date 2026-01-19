import asyncio
import asyncpg
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from kolmo.config import Settings


async def main():
    settings = Settings()
    dsn = (
        f"postgresql://{settings.database_user}:{settings.database_password}"
        f"@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    try:
        row = await pool.fetchrow(
            "SELECT date, r_iou2, r_me4u, r_uome, kolmo_value, kolmo_state, winner FROM mcol1_compute_data WHERE date = $1",
            date(2022, 4, 22)
        )
        if row:
            print(f"Date: {row['date']}")
            print(f"r_iou2 (EUR/USD): {row['r_iou2']}")
            print(f"r_me4u (USD/CNY): {row['r_me4u']}")
            print(f"r_uome (CNY/EUR): {row['r_uome']}")
            print(f"KOLMO Value: {row['kolmo_value']}")
            print(f"KOLMO State: {row['kolmo_state']}")
            print(f"Winner: {row['winner']}")
        else:
            print("No data found for 2022-04-22")
    finally:
        await pool.close()


asyncio.run(main())
