#!/usr/bin/env python
"""Удалить записи для указанных дат из mcol1_external_data и mcol1_compute_data."""

import asyncio
import asyncpg
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from kolmo.config import Settings


async def main():
    settings = Settings()
    dsn = (
        f"postgresql://{settings.database_user}:{settings.database_password}"
        f"@{settings.database_host}:{settings.database_port}"
        f"/{settings.database_name}"
    )
    
    conn = await asyncpg.connect(dsn)
    
    # Даты для удаления
    dates_to_delete = [
        date(2026, 1, 29),
        date(2026, 1, 30),
        date(2026, 2, 2),
        date(2026, 2, 3),
    ]
    
    for d in dates_to_delete:
        deleted_ext = await conn.execute(
            'DELETE FROM mcol1_external_data WHERE date = $1', d
        )
        deleted_comp = await conn.execute(
            'DELETE FROM mcol1_compute_data WHERE date = $1', d
        )
        print(f'{d}: external={deleted_ext}, compute={deleted_comp}')
    
    await conn.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
