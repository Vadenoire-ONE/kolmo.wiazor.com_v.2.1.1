"""
KOLMO.wiazor.com Main Application Entry Point

🔒 REQ-1.7: Daily schedule (22:00 EST) with manual trigger capability
🔒 REQ-3.1: Four-stage pipeline implementation
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any
from uuid import uuid4

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kolmo import __version__
from kolmo.api import router
from kolmo.computation import ComputationEngine
from kolmo.computation.engine import persist_compute_data, persist_external_data
from kolmo.config import get_settings
from kolmo.database import close_pool, get_pool
from kolmo.models import CurrencyPair, ExternalDataCreate
from kolmo.providers import ProviderManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Global scheduler
scheduler: AsyncIOScheduler | None = None


async def run_daily_pipeline(target_date: date | None = None) -> dict[str, Any]:
    """
    🔒 REQ-3.1: Execute the four-stage KOLMO pipeline.
    
    Stage 1: Data Acquisition (fetch from providers)
    Stage 2: Storage (persist raw data)
    Stage 3: Computation (calculate KOLMO metrics)
    Stage 4: API Serving (data available via REST)
    
    Args:
        target_date: Date to fetch rates for. Defaults to today.
    
    Returns:
        Dictionary with pipeline execution results
    """
    if target_date is None:
        target_date = date.today()
    
    date_str = target_date.isoformat()
    trace_id = uuid4()
    
    logger.info(f"🚀 Starting KOLMO pipeline for {date_str} (trace: {trace_id})")
    
    try:
        # === STAGE 1: DATA ACQUISITION ===
        logger.info("📥 Stage 1: Data Acquisition")
        provider_manager = ProviderManager()
        
        rates, provider_used = await provider_manager.fetch_with_fallback(date_str)
        
        logger.info(f"✅ Stage 1 complete: Data from {provider_used}")
        
        # === STAGE 2: STORAGE ===
        logger.info("💾 Stage 2: Storage")
        
        external_data = ExternalDataCreate(
            date=target_date,
            eur_usd=rates["eur_usd"],
            eur_usd_pair_desc=CurrencyPair.EUR_USD,
            eur_cny=rates["eur_cny"],
            eur_cny_pair_desc=CurrencyPair.EUR_CNY,
            eur_rub=rates.get("eur_rub"),
            eur_rub_pair_desc=CurrencyPair.EUR_RUB if rates.get("eur_rub") else None,
            eur_inr=rates.get("eur_inr"),
            eur_inr_pair_desc=CurrencyPair.EUR_INR if rates.get("eur_inr") else None,
            eur_aed=rates.get("eur_aed"),
            eur_aed_pair_desc=CurrencyPair.EUR_AED if rates.get("eur_aed") else None,
            trace_id=trace_id,
            sources={
                "provider": provider_used,
                "fetch_time": datetime.utcnow().isoformat()
            }
        )
        
        await persist_external_data(external_data)
        logger.info(f"✅ Stage 2 complete: Raw data persisted (snapshot: {external_data.mcol1_snapshot_id})")
        
        # === STAGE 3: COMPUTATION ===
        logger.info("🧮 Stage 3: Computation")
        
        engine = ComputationEngine()
        compute_data = await engine.compute_daily_metrics(external_data)
        
        await persist_compute_data(compute_data)
        logger.info(
            f"✅ Stage 3 complete: Winner={compute_data.winner.value}, "
            f"KOLMO={compute_data.kolmo_value}"
        )
        
        # === STAGE 4: API SERVING ===
        logger.info("🌐 Stage 4: API Ready")
        logger.info(f"✅ Pipeline complete for {date_str}")
        
        return {
            "success": True,
            "date": date_str,
            "provider": provider_used,
            "winner": compute_data.winner.value,
            "kolmo_value": str(compute_data.kolmo_value),
            "kolmo_state": compute_data.kolmo_state.value,
            "trace_id": str(trace_id)
        }
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed for {date_str}: {e}")
        return {
            "success": False,
            "date": date_str,
            "error": str(e),
            "trace_id": str(trace_id)
        }


async def scheduled_job():
    """Scheduled daily job wrapper."""
    logger.info("⏰ Scheduled job triggered")
    result = await run_daily_pipeline()
    if result["success"]:
        logger.info(f"⏰ Scheduled job completed: Winner={result['winner']}")
    else:
        logger.error(f"⏰ Scheduled job failed: {result.get('error')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global scheduler
    
    settings = get_settings()
    
    # Startup
    logger.info(f"🚀 Starting KOLMO v.{__version__}")
    
    # Initialize database pool
    try:
        await get_pool()
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.warning(f"⚠️ Database not available: {e}")
    
    # Initialize scheduler
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    
    # Add daily job at configured time (default: 22:00 EST)
    scheduler.add_job(
        scheduled_job,
        CronTrigger(
            hour=settings.scheduler_cron_hour,
            minute=settings.scheduler_cron_minute
        ),
        id="daily_kolmo_pipeline",
        name="Daily KOLMO Pipeline",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(
        f"⏰ Scheduler started: Daily job at "
        f"{settings.scheduler_cron_hour:02d}:{settings.scheduler_cron_minute:02d} "
        f"{settings.scheduler_timezone}"
    )
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down KOLMO")
    
    if scheduler:
        scheduler.shutdown()
        logger.info("⏰ Scheduler stopped")
    
    await close_pool()
    logger.info("✅ Shutdown complete")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="KOLMO.wiazor.com",
        description="DTKT Currency Triangle Monitoring System",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(router)
    
    # Manual trigger endpoint (for gap-filling and testing)
    @app.post("/api/v1/trigger/{date_str}")
    async def trigger_pipeline(date_str: str):
        """
        🔒 REQ-1.7: Manual trigger capability for gap-filling and corrections.
        
        Args:
            date_str: ISO 8601 date (YYYY-MM-DD)
        """
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return {"error": f"Invalid date format: {date_str}. Use YYYY-MM-DD."}
        
        result = await run_daily_pipeline(target_date)
        return result
    
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "KOLMO.wiazor.com",
            "version": __version__,
            "description": "DTKT Currency Triangle Monitoring System",
            "docs": "/docs",
            "api": {
                "winner_latest": "/api/v1/winner/latest",
                "rates_by_date": "/api/v1/rates/{date}",
                "health": "/api/v1/health",
                "trigger": "/api/v1/trigger/{date}"
            }
        }
    
    return app


# Create application instance
app = create_app()


def main():
    """Main entry point for running the server."""
    settings = get_settings()
    
    logger.info(f"Starting KOLMO server on {settings.api_host}:{settings.api_port}")
    
    uvicorn.run(
        "kolmo.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
