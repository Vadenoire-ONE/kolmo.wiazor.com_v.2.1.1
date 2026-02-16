"""
Массовая загрузка курсов валют с ЦБ РФ (CBR) за диапазон дат.
Сохраняет данные в базу данных через стандартные методы.

Использование:
    python scripts/fetch_cbr_bulk.py --start-date 2022-07-01 --end-date 2026-01-29
"""
import argparse
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from kolmo.providers.cbr import CBRClient
from kolmo.database import get_connection

CURRENCY_KEYS = [
    "eur_usd", "eur_cny", "eur_rub", "eur_inr", "eur_aed",
    "eur_cad", "eur_sgd", "eur_thb", "eur_vnd", "eur_hkd", "eur_huf"
]

async def save_rates(date: str, rates: dict):
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO mcol1_external_data (
                date, eur_usd, eur_cny, eur_rub, eur_inr, eur_aed,
                eur_cad, eur_sgd, eur_thb, eur_vnd, eur_hkd, eur_huf, source
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
            ) ON CONFLICT (date) DO UPDATE SET
                eur_usd=EXCLUDED.eur_usd, eur_cny=EXCLUDED.eur_cny, eur_rub=EXCLUDED.eur_rub,
                eur_inr=EXCLUDED.eur_inr, eur_aed=EXCLUDED.eur_aed, eur_cad=EXCLUDED.eur_cad,
                eur_sgd=EXCLUDED.eur_sgd, eur_thb=EXCLUDED.eur_thb, eur_vnd=EXCLUDED.eur_vnd,
                eur_hkd=EXCLUDED.eur_hkd, eur_huf=EXCLUDED.eur_huf, source=EXCLUDED.source
            """,
            date,
            *(rates.get(key) for key in CURRENCY_KEYS),
            "cbr"
        )

async def fetch_and_save_cbr(start_date: str, end_date: str):
    client = CBRClient()
    d1 = datetime.strptime(start_date, "%Y-%m-%d")
    d2 = datetime.strptime(end_date, "%Y-%m-%d")
    total = (d2 - d1).days + 1
    for i in range(total):
        day = d1 + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        try:
            rates = await client.fetch_rates(day_str)
            await save_rates(day_str, rates)
            print(f"{day_str}: OK")
        except Exception as e:
            print(f"{day_str}: ERROR {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    asyncio.run(fetch_and_save_cbr(args.start_date, args.end_date))
