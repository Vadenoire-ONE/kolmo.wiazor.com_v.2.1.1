"""
KOLMO Missing Days Fetcher

Intelligently fetches provider data ONLY for missing dates in the database,
avoiding redundant API calls for dates that already have data.

Usage:
    python scripts/fetch_missing_days.py                    # Fetch today if missing
    python scripts/fetch_missing_days.py --start-date 2026-01-01 --end-date 2026-01-22
    python scripts/fetch_missing_days.py --start-date 2026-01-01 --dry-run
    
Features:
    ✅ Queries existing data in mcol1_external_data table
    ✅ Identifies missing dates in range
    ✅ Fetches only missing data (no redundant API calls)
    ✅ Logs statistics: fetched, inserted, skipped, errors
    ✅ Supports dry-run mode for inspection
"""

import asyncio
import logging
import sys
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
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
from kolmo.providers.manager import ProviderManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path(__file__).parent.parent / "logs" / f"fetch_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger(__name__)


class MissingDaysFetcher:
    """
    Fetches exchange rates ONLY for dates missing from the database.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: Optional[asyncpg.Pool] = None
        self.provider_manager = ProviderManager()
        self.stats = {
            "queried": 0,           # Dates checked in database
            "missing": 0,           # Dates without data
            "fetched": 0,           # Successfully fetched from providers
            "inserted": 0,          # Successfully inserted to DB
            "skipped": 0,           # Already in database
            "errors": 0             # Fetch/insert errors
        }
        self.error_log: list[str] = []
    
    async def connect(self) -> None:
        """Establish database connection."""
        dsn = (
            f"postgresql://{self.settings.database_user}:{self.settings.database_password}"
            f"@{self.settings.database_host}:{self.settings.database_port}"
            f"/{self.settings.database_name}"
        )
        self.pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        logger.info(f"✅ Connected to database: {self.settings.database_host}:{self.settings.database_port}/{self.settings.database_name}")
    
    async def close(self) -> None:
        """Close database connection."""
        if self.pool:
            await self.pool.close()
        logger.info("🔒 Database connection closed")
    
    async def get_existing_dates(self) -> set[date]:
        """
        Query database for all dates with existing data.
        
        Returns:
            Set of date objects that have data in mcol1_external_data
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT date 
                FROM mcol1_external_data 
                ORDER BY date
                """
            )
        
        existing = {row['date'] for row in rows}
        logger.info(f"📊 Database contains {len(existing)} dates with data")
        return existing
    
    def get_date_range(self, start_date: Optional[date], end_date: Optional[date]) -> tuple[date, date]:
        """
        Get date range for processing.
        
        Args:
            start_date: Start date (or None for 7 days ago)
            end_date: End date (or None for today)
        
        Returns:
            Tuple of (start_date, end_date)
        """
        today = date.today()
        
        if end_date is None:
            end_date = today
        
        if start_date is None:
            # Default: 7 days ago
            start_date = end_date - timedelta(days=7)
        
        logger.info(f"📅 Date range: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
        return start_date, end_date
    
    def find_missing_dates(
        self, 
        start_date: date, 
        end_date: date,
        existing_dates: set[date]
    ) -> list[date]:
        """
        Find dates in range that are missing from database.
        
        Args:
            start_date: Start of range
            end_date: End of range
            existing_dates: Set of dates with existing data
        
        Returns:
            List of missing dates (sorted)
        """
        all_dates = set()
        current = start_date
        while current <= end_date:
            # Skip weekends (market closed)
            if current.weekday() < 5:  # Monday=0, Friday=4
                all_dates.add(current)
            current += timedelta(days=1)
        
        missing = sorted(all_dates - existing_dates)
        
        self.stats["queried"] = len(all_dates)
        self.stats["missing"] = len(missing)
        self.stats["skipped"] = len(all_dates - set(missing))
        
        logger.info(
            f"📈 Analysis: {len(all_dates)} business days | "
            f"✅ {len(all_dates) - len(missing)} existing | "
            f"❌ {len(missing)} missing"
        )
        
        return missing
    
    async def fetch_for_date(self, target_date: date) -> Optional[dict]:
        """
        Fetch exchange rates for a specific date using provider manager.
        
        Args:
            target_date: Date to fetch for
        
        Returns:
            Dict with rates or None on error
        """
        try:
            date_str = target_date.isoformat()
            logger.info(f"⬇️  Fetching {date_str}...")
            
            rates, provider_name = await self.provider_manager.fetch_with_fallback(date_str)
            
            logger.info(f"✅ Fetched from {provider_name}: {date_str}")
            return {
                "date": target_date,
                "rates": rates,
                "provider": provider_name,
                "timestamp": datetime.utcnow()
            }
        
        except Exception as e:
            error_msg = f"❌ Error fetching {target_date.isoformat()}: {str(e)}"
            logger.error(error_msg)
            self.error_log.append(error_msg)
            self.stats["errors"] += 1
            return None
    
    async def insert_external_data(
        self,
        fetch_result: dict
    ) -> bool:
        """
        Insert fetched rates into mcol1_external_data table.
        
        Args:
            fetch_result: Dict from fetch_for_date()
        
        Returns:
            True if successful, False on error
        """
        try:
            target_date = fetch_result["date"]
            rates = fetch_result["rates"]
            provider_name = fetch_result["provider"]
            
            # Transform rates into table columns
            # rates dict should contain: eur_usd, eur_cny, etc.
            
            eur_usd = rates.get("eur_usd")
            eur_cny = rates.get("eur_cny")
            eur_rub = rates.get("eur_rub")
            eur_inr = rates.get("eur_inr")
            eur_aed = rates.get("eur_aed")
            
            snapshot_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO mcol1_external_data 
                    (date, eur_usd, eur_usd_pair_desc, eur_cny, eur_cny_pair_desc,
                     eur_rub, eur_rub_pair_desc, eur_inr, eur_inr_pair_desc,
                     eur_aed, eur_aed_pair_desc, mcol1_snapshot_id, trace_id, sources)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (date) DO NOTHING
                    """,
                    target_date,
                    eur_usd, "EUR/USD" if eur_usd else None,
                    eur_cny, "EUR/CNY" if eur_cny else None,
                    eur_rub, "EUR/RUB" if eur_rub else None,
                    eur_inr, "EUR/INR" if eur_inr else None,
                    eur_aed, "EUR/AED" if eur_aed else None,
                    snapshot_id,
                    trace_id,
                    json.dumps({"provider": provider_name, "fetch_time": fetch_result["timestamp"].isoformat()})
                )
            
            self.stats["inserted"] += 1
            logger.info(f"💾 Inserted {target_date.isoformat()} (provider: {provider_name})")
            return True
        
        except asyncpg.UniqueViolationError:
            logger.debug(f"⏭️  {target_date.isoformat()} already in database")
            self.stats["skipped"] += 1
            return True
        
        except Exception as e:
            error_msg = f"❌ Error inserting {target_date.isoformat()}: {str(e)}"
            logger.error(error_msg)
            self.error_log.append(error_msg)
            self.stats["errors"] += 1
            return False
    
    async def process_missing_dates(
        self,
        missing_dates: list[date],
        dry_run: bool = False,
        batch_size: int = 5
    ) -> None:
        """
        Process missing dates in batches.
        
        Args:
            missing_dates: List of dates to fetch
            dry_run: If True, don't insert to database
            batch_size: Number of dates to process concurrently
        """
        if not missing_dates:
            logger.info("🎉 No missing dates - database is complete!")
            return
        
        if dry_run:
            logger.info(f"🔍 DRY RUN: Would fetch {len(missing_dates)} dates")
            for d in missing_dates[:10]:
                logger.info(f"   {d.isoformat()}")
            if len(missing_dates) > 10:
                logger.info(f"   ... and {len(missing_dates) - 10} more")
            return
        
        logger.info(f"🚀 Starting fetch for {len(missing_dates)} missing dates...")
        
        for i in range(0, len(missing_dates), batch_size):
            batch = missing_dates[i:i + batch_size]
            logger.info(f"📦 Processing batch {i // batch_size + 1}/{(len(missing_dates) + batch_size - 1) // batch_size}")
            
            # Fetch all dates in batch concurrently
            fetch_tasks = [self.fetch_for_date(d) for d in batch]
            fetch_results = await asyncio.gather(*fetch_tasks)
            
            # Insert successful fetches
            insert_tasks = [
                self.insert_external_data(result)
                for result in fetch_results
                if result is not None
            ]
            
            if insert_tasks:
                await asyncio.gather(*insert_tasks)
            
            # Brief pause between batches to avoid rate limiting
            if i + batch_size < len(missing_dates):
                await asyncio.sleep(2)
    
    def print_summary(self) -> None:
        """Print processing statistics."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 FETCH SUMMARY")
        logger.info("=" * 70)
        logger.info(f"  Business days queried:  {self.stats['queried']}")
        logger.info(f"  Days with data:         {self.stats['queried'] - self.stats['missing']}")
        logger.info(f"  Missing days found:     {self.stats['missing']}")
        logger.info(f"  Successfully fetched:   {self.stats['fetched']}")
        logger.info(f"  Successfully inserted:  {self.stats['inserted']}")
        logger.info(f"  Skipped (duplicate):    {self.stats['skipped']}")
        logger.info(f"  Errors:                 {self.stats['errors']}")
        logger.info("=" * 70)
        
        if self.error_log:
            logger.warning("\n⚠️  ERRORS ENCOUNTERED:")
            for error in self.error_log:
                logger.warning(f"   {error}")
        
        logger.info("")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch exchange rates only for missing days in the database"
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Start date (YYYY-MM-DD), default: 7 days ago"
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="End date (YYYY-MM-DD), default: today"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without inserting to database"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of dates to fetch concurrently (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Load environment
    load_dotenv()
    settings = Settings()
    
    # Create logs directory if needed
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Initialize fetcher
    fetcher = MissingDaysFetcher(settings)
    
    try:
        await fetcher.connect()
        
        # Get existing data and find missing dates
        existing_dates = await fetcher.get_existing_dates()
        start_date, end_date = fetcher.get_date_range(args.start_date, args.end_date)
        missing_dates = fetcher.find_missing_dates(start_date, end_date, existing_dates)
        
        # Process missing dates
        await fetcher.process_missing_dates(
            missing_dates,
            dry_run=args.dry_run,
            batch_size=args.batch_size
        )
        
        # Update fetch stats for successful results
        if not args.dry_run:
            fetcher.stats["fetched"] = fetcher.stats["inserted"] + fetcher.stats["skipped"]
        
        fetcher.print_summary()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        await fetcher.close()


if __name__ == "__main__":
    asyncio.run(main())
