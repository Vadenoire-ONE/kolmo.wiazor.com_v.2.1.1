"""
KOLMO Historical Data Backfill Script - CORRECTED VERSION

🔒 REQ-2.4: RelativePath = (dist_prev - dist_curr) / dist_prev × 100
🔒 REQ-2.5: Winner = coin with highest POSITIVE relpath
🔒 REQ-2.6: Tie-break alphabetically: IOU2 < ME4U < UOME

Запуск:
    python scripts/backfill_historical.py [--start-date 2021-07-01] [--end-date 2026-01-15]
"""

import asyncio
import logging
import sys
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional
import argparse
import uuid

import httpx
import asyncpg
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kolmo.config import Settings
from kolmo.models import WinnerCoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Constants
FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"
BATCH_SIZE = 30  # Days per batch request
PRECISION_6 = Decimal("0.000001")  # 6 decimal places for rates
PRECISION_18 = Decimal("0.000000000000000001")  # 18 decimal places for kolmo_value
PRECISION_4 = Decimal("0.0001")  # 4 decimal places for deviations


class HistoricalBackfill:
    """
    Загрузчик исторических данных KOLMO.
    
    IMPORTANT: RelativePath is computed using PREVIOUS day's distance:
    relpath = (dist_prev - dist_curr) / dist_prev × 100
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: Optional[asyncpg.Pool] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.stats = {
            "fetched": 0,
            "inserted": 0,
            "skipped": 0,
            "errors": 0
        }
        # Store previous day's distances for RelativePath calculation
        self.prev_distances: dict[str, Decimal] = {}
        # Store previous day's rates for Volatility calculation
        self.prev_rates: dict[str, Decimal] = {}
    
    async def connect(self) -> None:
        """Установить подключения к БД и HTTP."""
        dsn = (
            f"postgresql://{self.settings.database_user}:{self.settings.database_password}"
            f"@{self.settings.database_host}:{self.settings.database_port}"
            f"/{self.settings.database_name}"
        )
        self.pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        self.http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("✅ Connected to database and HTTP client ready")
    
    async def close(self) -> None:
        """Закрыть подключения."""
        if self.http_client:
            await self.http_client.aclose()
        if self.pool:
            await self.pool.close()
        logger.info("🔒 Connections closed")
    
    async def fetch_frankfurter_range(
        self, 
        start_date: date, 
        end_date: date
    ) -> dict[date, dict[str, Decimal]]:
        """
        Получить курсы EUR/USD и EUR/CNY из Frankfurter API за диапазон дат.
        """
        url = f"{FRANKFURTER_BASE_URL}/{start_date}..{end_date}"
        params = {"symbols": "USD,CNY"}
        
        try:
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            result = {}
            rates_data = data.get("rates", {})
            
            for date_str, rates in rates_data.items():
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                if "USD" in rates and "CNY" in rates:
                    result[d] = {
                        "eur_usd": Decimal(str(rates["USD"])),
                        "eur_cny": Decimal(str(rates["CNY"]))
                    }
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error fetching {start_date}..{end_date}: {e}")
            return {}
    
    async def get_previous_distances(self, rate_date: date) -> dict[str, Decimal] | None:
        """
        Get previous day's distances from database (for continuation of existing data).
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT dist_me4u, dist_iou2, dist_uome 
                FROM mcol1_compute_data 
                WHERE date < $1 
                ORDER BY date DESC 
                LIMIT 1
            """, rate_date)
            
            if row:
                return {
                    "dist_me4u": row["dist_me4u"],
                    "dist_iou2": row["dist_iou2"],
                    "dist_uome": row["dist_uome"]
                }
            return None
    
    async def get_previous_rates(self, rate_date: date) -> dict[str, Decimal] | None:
        """
        Get previous day's rates from database (for volatility calculation).
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT r_me4u, r_iou2, r_uome 
                FROM mcol1_compute_data 
                WHERE date < $1 
                ORDER BY date DESC 
                LIMIT 1
            """, rate_date)
            
            if row:
                return {
                    "r_me4u": row["r_me4u"],
                    "r_iou2": row["r_iou2"],
                    "r_uome": row["r_uome"]
                }
            return None
    
    def compute_kolmo_metrics(
        self, 
        eur_usd: Decimal, 
        eur_cny: Decimal,
        prev_dist_me4u: Decimal | None,
        prev_dist_iou2: Decimal | None,
        prev_dist_uome: Decimal | None,
        prev_r_me4u: Decimal | None,
        prev_r_iou2: Decimal | None,
        prev_r_uome: Decimal | None
    ) -> dict:
        """
        🔒 Compute KOLMO metrics following specification.
        
        KOLMO notation:
        - r_me4u = EUR/USD ÷ EUR/CNY = USD per 1 CNY
        - r_iou2 = 1 ÷ EUR/USD = EUR per 1 USD  
        - r_uome = EUR/CNY = CNY per 1 EUR
        
        Distance: dist = |rate - 1.0| × 100
        RelativePath: relpath = (dist_prev - dist_curr) / dist_prev × 100
        
        🔒 REQ-2.4: relpath > 0 means improvement toward parity
        🔒 REQ-2.5: Winner = highest POSITIVE relpath
        """
        # Transform rates to KOLMO notation
        r_me4u = (eur_usd / eur_cny).quantize(PRECISION_6, rounding=ROUND_HALF_UP)
        r_iou2 = (Decimal("1") / eur_usd).quantize(PRECISION_6, rounding=ROUND_HALF_UP)
        r_uome = eur_cny.quantize(PRECISION_6, rounding=ROUND_HALF_UP)
        
        # Calculate KOLMO invariant (exact product)
        kolmo_value = r_me4u * r_iou2 * r_uome
        
        # Deviation from 1.0 as percentage (NO ROUNDING - same as kolmo_value)
        kolmo_deviation = (kolmo_value - Decimal("1")) * Decimal("100")
        
        # Determine state
        abs_deviation = abs(kolmo_deviation)
        if abs_deviation <= Decimal("1"):
            kolmo_state = "OK"
        elif abs_deviation <= Decimal("5"):
            kolmo_state = "WARN"
        else:
            kolmo_state = "CRITICAL"
        
        # 🔒 REQ-2.3: Distance = |rate - 1.0| × 100 (ABSOLUTE value!)
        dist_me4u = (abs(r_me4u - Decimal("1")) * Decimal("100")).quantize(PRECISION_4, rounding=ROUND_HALF_UP)
        dist_iou2 = (abs(r_iou2 - Decimal("1")) * Decimal("100")).quantize(PRECISION_4, rounding=ROUND_HALF_UP)
        dist_uome = (abs(r_uome - Decimal("1")) * Decimal("100")).quantize(PRECISION_4, rounding=ROUND_HALF_UP)
        
        # 🔒 REQ-2.4: RelativePath = (dist_prev - dist_curr) / dist_prev × 100
        # Positive = improving toward parity, Negative = deteriorating
        relpath_me4u = self._compute_relativepath(dist_me4u, prev_dist_me4u)
        relpath_iou2 = self._compute_relativepath(dist_iou2, prev_dist_iou2)
        relpath_uome = self._compute_relativepath(dist_uome, prev_dist_uome)
        
        # 🔒 REQ-2.5 & REQ-2.6: Select winner
        winner, winner_reason = self._select_winner(relpath_me4u, relpath_iou2, relpath_uome)
        
        # Daily Volatility = (rate_today - rate_yesterday) / rate_yesterday × 100
        vol_me4u = self._compute_volatility(r_me4u, prev_r_me4u)
        vol_iou2 = self._compute_volatility(r_iou2, prev_r_iou2)
        vol_uome = self._compute_volatility(r_uome, prev_r_uome)
        
        return {
            "r_me4u": r_me4u,
            "r_iou2": r_iou2,
            "r_uome": r_uome,
            "kolmo_value": kolmo_value,
            "kolmo_deviation": kolmo_deviation,
            "kolmo_state": kolmo_state,
            "dist_me4u": dist_me4u,
            "dist_iou2": dist_iou2,
            "dist_uome": dist_uome,
            "relpath_me4u": relpath_me4u,
            "relpath_iou2": relpath_iou2,
            "relpath_uome": relpath_uome,
            "vol_me4u": vol_me4u,
            "vol_iou2": vol_iou2,
            "vol_uome": vol_uome,
            "winner": winner,
            "winner_reason": winner_reason
        }
    
    def _compute_relativepath(
        self, 
        dist_curr: Decimal, 
        dist_prev: Decimal | None
    ) -> Decimal | None:
        """
        🔒 REQ-2.4: Compute RelativePath.
        
        relpath = (dist_prev - dist_curr) / dist_prev × 100
        
        Returns None if no previous data or division by zero.
        """
        if dist_prev is None or dist_prev == Decimal("0"):
            return None
        
        return ((dist_prev - dist_curr) / dist_prev) * Decimal("100")
    
    def _compute_volatility(
        self,
        rate_curr: Decimal,
        rate_prev: Decimal | None
    ) -> Decimal | None:
        """
        Compute daily volatility (percentage change from previous day).
        
        vol = (rate_today - rate_yesterday) / rate_yesterday × 100
        
        Positive = rate increased, Negative = rate decreased.
        Returns None if no previous data or division by zero.
        """
        if rate_prev is None or rate_prev == Decimal("0"):
            return None
        
        return ((rate_curr - rate_prev) / rate_prev) * Decimal("100")
    
    def _select_winner(
        self,
        relpath_me4u: Decimal | None,
        relpath_iou2: Decimal | None,
        relpath_uome: Decimal | None
    ) -> tuple[str, dict]:
        """
        🔒 REQ-2.5: Winner = max positive relpath
        🔒 REQ-2.6: Tie-break alphabetically IOU2 < ME4U < UOME
        """
        candidates = {}
        
        if relpath_iou2 is not None:
            candidates["IOU2"] = relpath_iou2
        if relpath_me4u is not None:
            candidates["ME4U"] = relpath_me4u
        if relpath_uome is not None:
            candidates["UOME"] = relpath_uome
        
        # Build reason JSON
        reason = {
            "me4u_relpath": float(relpath_me4u) if relpath_me4u is not None else None,
            "iou2_relpath": float(relpath_iou2) if relpath_iou2 is not None else None,
            "uome_relpath": float(relpath_uome) if relpath_uome is not None else None,
        }
        
        # Case 1: All NULL (first day)
        if not candidates:
            reason["selection_rule"] = "default_first_day"
            reason["winner"] = "IOU2"
            return "IOU2", reason
        
        # Find positive candidates
        positive = [(coin, rp) for coin, rp in candidates.items() if rp > Decimal("0")]
        
        if positive:
            # 🔒 REQ-2.5: Max positive, then alphabetical
            positive.sort(key=lambda x: (-x[1], x[0]))
            winner = positive[0][0]
            reason["selection_rule"] = "max_positive_alphabetical_tiebreak"
        else:
            # All negative/zero - take least negative (closest to 0)
            all_sorted = sorted(candidates.items(), key=lambda x: (-x[1], x[0]))
            winner = all_sorted[0][0]
            reason["selection_rule"] = "least_negative"
        
        reason["winner"] = winner
        return winner, reason
    
    async def insert_data(
        self, 
        rate_date: date,
        eur_usd: Decimal,
        eur_cny: Decimal,
        metrics: dict
    ) -> bool:
        """Вставить данные в таблицы."""
        async with self.pool.acquire() as conn:
            # If compute data already exists for this date, skip (nothing to do)
            existing_compute = await conn.fetchval(
                "SELECT 1 FROM mcol1_compute_data WHERE date = $1",
                rate_date
            )

            if existing_compute:
                self.stats["skipped"] += 1
                return False

            snapshot_id = uuid.uuid4()

            sources = {
                "frankfurter": {
                    "url": f"{FRANKFURTER_BASE_URL}/{rate_date}",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "backfill": True
                }
            }

            async with conn.transaction():
                # Insert external data only if it's missing (avoid unique constraint)
                existing_external = await conn.fetchval(
                    "SELECT 1 FROM mcol1_external_data WHERE date = $1",
                    rate_date
                )

                if not existing_external:
                    await conn.execute(
                        """
                        INSERT INTO mcol1_external_data 
                        (date, eur_usd, eur_usd_pair_desc, eur_cny, eur_cny_pair_desc,
                         mcol1_snapshot_id, sources)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        rate_date, eur_usd, "EUR/USD", eur_cny, "EUR/CNY",
                        snapshot_id, json.dumps(sources)
                    )

                await conn.execute(
                    """
                    INSERT INTO mcol1_compute_data
                    (date, r_me4u, r_iou2, r_uome, 
                     kolmo_value, kolmo_deviation, kolmo_state,
                     dist_me4u, dist_iou2, dist_uome,
                     relpath_me4u, relpath_iou2, relpath_uome,
                     vol_me4u, vol_iou2, vol_uome,
                     winner, winner_reason, mcol1_snapshot_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                    """,
                    rate_date,
                    metrics["r_me4u"],
                    metrics["r_iou2"],
                    metrics["r_uome"],
                    metrics["kolmo_value"],
                    metrics["kolmo_deviation"],
                    metrics["kolmo_state"],
                    metrics["dist_me4u"],
                    metrics["dist_iou2"],
                    metrics["dist_uome"],
                    metrics["relpath_me4u"],
                    metrics["relpath_iou2"],
                    metrics["relpath_uome"],
                    metrics["vol_me4u"],
                    metrics["vol_iou2"],
                    metrics["vol_uome"],
                    metrics["winner"],
                    json.dumps(metrics["winner_reason"]),
                    snapshot_id
                )

                self.stats["inserted"] += 1
                return True
    
    async def backfill(self, start_date: date, end_date: date) -> None:
        """
        Выполнить загрузку исторических данных.
        
        IMPORTANT: Process dates in chronological order to compute RelativePath correctly!
        """
        logger.info(f"🚀 Starting backfill from {start_date} to {end_date}")
        
        # Step 1: Fetch ALL data first
        logger.info("📥 Fetching all historical data...")
        all_rates: dict[date, dict[str, Decimal]] = {}
        
        current = start_date
        batch_num = 0
        
        while current <= end_date:
            batch_num += 1
            batch_end = min(current + timedelta(days=BATCH_SIZE - 1), end_date)
            
            logger.info(f"📦 Batch {batch_num}: {current} → {batch_end}")
            
            rates = await self.fetch_frankfurter_range(current, batch_end)
            all_rates.update(rates)
            
            current = batch_end + timedelta(days=1)
            await asyncio.sleep(0.3)
        
        self.stats["fetched"] = len(all_rates)
        logger.info(f"📊 Fetched {len(all_rates)} days of data")
        
        # Step 2: Try to get previous distances and rates from existing DB data
        sorted_dates = sorted(all_rates.keys())
        if sorted_dates:
            prev_dist = await self.get_previous_distances(sorted_dates[0])
            if prev_dist:
                self.prev_distances = prev_dist
                logger.info(f"📚 Found previous distances in DB")
            prev_rates = await self.get_previous_rates(sorted_dates[0])
            if prev_rates:
                self.prev_rates = prev_rates
                logger.info(f"📚 Found previous rates in DB")
        
        # Step 3: Process in chronological order (crucial for RelativePath!)
        logger.info("🔄 Processing data in chronological order...")
        
        for rate_date in sorted_dates:
            try:
                rate_values = all_rates[rate_date]
                eur_usd = rate_values["eur_usd"]
                eur_cny = rate_values["eur_cny"]
                
                # Compute metrics using previous day's distances and rates
                metrics = self.compute_kolmo_metrics(
                    eur_usd, 
                    eur_cny,
                    self.prev_distances.get("dist_me4u"),
                    self.prev_distances.get("dist_iou2"),
                    self.prev_distances.get("dist_uome"),
                    self.prev_rates.get("r_me4u"),
                    self.prev_rates.get("r_iou2"),
                    self.prev_rates.get("r_uome")
                )
                
                # Insert into database
                inserted = await self.insert_data(rate_date, eur_usd, eur_cny, metrics)
                
                # 🔒 CRITICAL: Update previous distances and rates for NEXT day's calculation
                if inserted:
                    self.prev_distances = {
                        "dist_me4u": metrics["dist_me4u"],
                        "dist_iou2": metrics["dist_iou2"],
                        "dist_uome": metrics["dist_uome"]
                    }
                    self.prev_rates = {
                        "r_me4u": metrics["r_me4u"],
                        "r_iou2": metrics["r_iou2"],
                        "r_uome": metrics["r_uome"]
                    }
                
            except Exception as e:
                logger.error(f"❌ Error processing {rate_date}: {e}")
                self.stats["errors"] += 1
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📈 BACKFILL COMPLETE")
        logger.info(f"   Fetched:  {self.stats['fetched']} days")
        logger.info(f"   Inserted: {self.stats['inserted']} records")
        logger.info(f"   Skipped:  {self.stats['skipped']} (already exist)")
        logger.info(f"   Errors:   {self.stats['errors']}")
        logger.info("=" * 60)
        
        # 🔒 AUTO-EXPORT: Update fixed JSON file after backfill
        await self._auto_export_json()
    
    async def _auto_export_json(self) -> None:
        """
        Automatically export full history to fixed JSON file.
        """
        try:
            from kolmo.export.json_exporter import export_full_history_auto
            
            logger.info("📤 Auto-exporting to JSON...")
            filepath = await export_full_history_auto()
            
            if filepath:
                logger.info(f"✅ JSON exported: {filepath}")
            else:
                logger.warning("⚠️ JSON export returned no file")
                
        except Exception as e:
            logger.error(f"❌ Auto-export failed: {e}")


async def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description="KOLMO Historical Data Backfill")
    parser.add_argument(
        "--start-date", 
        type=str, 
        default="2021-07-01",
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=str(date.today()),
        help="End date (YYYY-MM-DD)"
    )
    
    args = parser.parse_args()
    
    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    
    # Load environment
    load_dotenv()
    settings = Settings()
    
    # Run backfill
    backfiller = HistoricalBackfill(settings)
    
    try:
        await backfiller.connect()
        await backfiller.backfill(start, end)
    finally:
        await backfiller.close()


if __name__ == "__main__":
    asyncio.run(main())
