"""
KOLMO JSON Exporter

🔒 Automatic JSON file generation for external analytics and visualization.

Exports the following fields:
- date, r_me4u, r_iou2, r_uome
- relpath_me4u, relpath_iou2, relpath_uome  
- vol_me4u, vol_iou2, vol_uome
- winner, kolmo_deviation
"""

import json
import logging
from datetime import date as date_type
from decimal import Decimal
from pathlib import Path
from typing import Any

from kolmo.config import get_settings
from kolmo.database import get_connection
from kolmo.models import ComputeDataCreate

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            # Convert to string to preserve precision
            return str(obj)
        if isinstance(obj, date_type):
            return obj.isoformat()
        return super().default(obj)


class JSONExporter:
    """
    Exports KOLMO metrics to JSON files for external analytics.
    
    Output structure:
    {
        "date": "2026-01-19",
        "r_me4u": "0.143400",
        "r_iou2": "0.859948", 
        "r_uome": "8.110000",
        "relpath_me4u": -0.35,
        "relpath_iou2": 3.24,
        "relpath_uome": 0.05,
        "vol_me4u": 0.9859,
        "vol_iou2": -0.5896,
        "vol_uome": 0.1234,
        "winner": "IOU2",
        "kolmo_deviation": 0.0041
    }
    """
    
    def __init__(self, output_dir: str | Path | None = None):
        """
        Initialize JSON exporter.
        
        Args:
            output_dir: Directory for JSON files. Defaults to './data/export'
        """
        if output_dir is None:
            output_dir = Path("./data/export")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"JSON Exporter initialized. Output dir: {self.output_dir}")
    
    def export_from_compute_data(
        self,
        compute_data: ComputeDataCreate,
        volatility: dict[str, Decimal | None] | None = None
    ) -> Path:
        """
        Export computed metrics to JSON file.
        
        Args:
            compute_data: Computed KOLMO metrics
            volatility: Optional volatility metrics dict
        
        Returns:
            Path to created JSON file
        """
        # Build export data structure
        export_data = {
            "date": compute_data.date.isoformat(),
            "r_me4u": str(compute_data.r_me4u),
            "r_iou2": str(compute_data.r_iou2),
            "r_uome": str(compute_data.r_uome),
            "relpath_me4u": float(compute_data.relpath_me4u) if compute_data.relpath_me4u is not None else None,
            "relpath_iou2": float(compute_data.relpath_iou2) if compute_data.relpath_iou2 is not None else None,
            "relpath_uome": float(compute_data.relpath_uome) if compute_data.relpath_uome is not None else None,
            "vol_me4u": None,
            "vol_iou2": None,
            "vol_uome": None,
            "winner": compute_data.winner.value,
            "kolmo_deviation": f"{float(compute_data.kolmo_deviation) * 1e5:.18f}e-5"
        }
        
        # Add volatility if provided
        if volatility:
            export_data["vol_me4u"] = float(volatility["vol_me4u"]) if volatility.get("vol_me4u") is not None else None
            export_data["vol_iou2"] = float(volatility["vol_iou2"]) if volatility.get("vol_iou2") is not None else None
            export_data["vol_uome"] = float(volatility["vol_uome"]) if volatility.get("vol_uome") is not None else None
        
        # Generate filename
        filename = f"kolmo_{compute_data.date.isoformat()}.json"
        filepath = self.output_dir / filename
        
        # Write JSON file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, cls=DecimalEncoder, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Exported JSON: {filepath}")
        return filepath
    
    def export_historical(
        self,
        start_date: date_type,
        end_date: date_type
    ) -> Path:
        """
        Export historical data range to a single JSON file.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        
        Returns:
            Path to created JSON file
        """
        filename = f"kolmo_history_{start_date.isoformat()}_{end_date.isoformat()}.json"
        filepath = self.output_dir / filename
        
        logger.info(f"Exporting historical data: {start_date} to {end_date}")
        return filepath


async def export_daily_json(
    compute_data: ComputeDataCreate,
    output_dir: str | Path | None = None
) -> Path:
    """
    🔒 REQ-6.1: Export daily KOLMO metrics to JSON after computation.
    
    This function is called automatically after persist_compute_data().
    
    Args:
        compute_data: Computed KOLMO metrics
        output_dir: Optional custom output directory
    
    Returns:
        Path to created JSON file
    """
    exporter = JSONExporter(output_dir)
    
    # Fetch volatility from database
    volatility = await _get_volatility_for_date(compute_data.date)
    
    return exporter.export_from_compute_data(compute_data, volatility)


async def _get_volatility_for_date(target_date: date_type) -> dict[str, Decimal | None]:
    """
    Compute volatility metrics by comparing with previous day.
    
    Formula: vol = (rate_today - rate_yesterday) / rate_yesterday × 100
    """
    try:
        async with get_connection() as conn:
            # Get current and previous day rates
            rows = await conn.fetch(
                """
                SELECT date, r_me4u, r_iou2, r_uome
                FROM mcol1_compute_data
                WHERE date <= $1
                ORDER BY date DESC
                LIMIT 2
                """,
                target_date
            )
            
            if len(rows) < 2:
                # First day - no previous data for volatility
                return {"vol_me4u": None, "vol_iou2": None, "vol_uome": None}
            
            current = rows[0]
            previous = rows[1]
            
            # Calculate volatility: (today - yesterday) / yesterday * 100
            vol_me4u = (Decimal(str(current["r_me4u"])) - Decimal(str(previous["r_me4u"]))) / Decimal(str(previous["r_me4u"])) * 100
            vol_iou2 = (Decimal(str(current["r_iou2"])) - Decimal(str(previous["r_iou2"]))) / Decimal(str(previous["r_iou2"])) * 100
            vol_uome = (Decimal(str(current["r_uome"])) - Decimal(str(previous["r_uome"]))) / Decimal(str(previous["r_uome"])) * 100
            
            return {
                "vol_me4u": vol_me4u,
                "vol_iou2": vol_iou2,
                "vol_uome": vol_uome
            }
            
    except Exception as e:
        logger.warning(f"Could not compute volatility: {e}")
        return {"vol_me4u": None, "vol_iou2": None, "vol_uome": None}


async def export_from_database(
    target_date: date_type,
    output_dir: str | Path | None = None
) -> Path | None:
    """
    Export KOLMO metrics for a specific date from database to JSON.
    
    Args:
        target_date: Date to export
        output_dir: Optional custom output directory
    
    Returns:
        Path to created JSON file, or None if date not found
    """
    exporter = JSONExporter(output_dir)
    
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    date, r_me4u, r_iou2, r_uome,
                    relpath_me4u, relpath_iou2, relpath_uome,
                    vol_me4u, vol_iou2, vol_uome,
                    winner, kolmo_deviation
                FROM mcol1_compute_data
                WHERE date = $1
                """,
                target_date
            )
            
            if not row:
                logger.warning(f"No data found for date: {target_date}")
                return None
            
            export_data = {
                "date": row["date"].isoformat(),
                "r_me4u": str(row["r_me4u"]),
                "r_iou2": str(row["r_iou2"]),
                "r_uome": str(row["r_uome"]),
                "relpath_me4u": float(row["relpath_me4u"]) if row["relpath_me4u"] is not None else None,
                "relpath_iou2": float(row["relpath_iou2"]) if row["relpath_iou2"] is not None else None,
                "relpath_uome": float(row["relpath_uome"]) if row["relpath_uome"] is not None else None,
                "vol_me4u": float(row["vol_me4u"]) if row["vol_me4u"] is not None else None,
                "vol_iou2": float(row["vol_iou2"]) if row["vol_iou2"] is not None else None,
                "vol_uome": float(row["vol_uome"]) if row["vol_uome"] is not None else None,
                "winner": row["winner"],
                "kolmo_deviation": f"{float(row['kolmo_deviation']) * 1e5:.18f}e-5"
            }
            
            filename = f"kolmo_{target_date.isoformat()}.json"
            filepath = exporter.output_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Exported from DB: {filepath}")
            return filepath
            
    except Exception as e:
        logger.error(f"Failed to export from database: {e}")
        return None


async def export_history_to_json(
    start_date: date_type,
    end_date: date_type,
    output_dir: str | Path | None = None
) -> Path | None:
    """
    Export historical KOLMO data range to a single JSON array file.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        output_dir: Optional custom output directory
    
    Returns:
        Path to created JSON file, or None on error
    """
    exporter = JSONExporter(output_dir)
    
    try:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    date, r_me4u, r_iou2, r_uome,
                    relpath_me4u, relpath_iou2, relpath_uome,
                    vol_me4u, vol_iou2, vol_uome,
                    winner, kolmo_deviation
                FROM mcol1_compute_data
                WHERE date BETWEEN $1 AND $2
                ORDER BY date ASC
                """,
                start_date, end_date
            )
            
            if not rows:
                logger.warning(f"No data found for range: {start_date} to {end_date}")
                return None
            
            export_data = []
            for row in rows:
                export_data.append({
                    "date": row["date"].isoformat(),
                    "r_me4u": str(row["r_me4u"]),
                    "r_iou2": str(row["r_iou2"]),
                    "r_uome": str(row["r_uome"]),
                    "relpath_me4u": float(row["relpath_me4u"]) if row["relpath_me4u"] is not None else None,
                    "relpath_iou2": float(row["relpath_iou2"]) if row["relpath_iou2"] is not None else None,
                    "relpath_uome": float(row["relpath_uome"]) if row["relpath_uome"] is not None else None,
                    "vol_me4u": float(row["vol_me4u"]) if row["vol_me4u"] is not None else None,
                    "vol_iou2": float(row["vol_iou2"]) if row["vol_iou2"] is not None else None,
                    "vol_uome": float(row["vol_uome"]) if row["vol_uome"] is not None else None,
                    "winner": row["winner"],
                    "kolmo_deviation": f"{float(row['kolmo_deviation']) * 1e5:.18f}e-5"
                })
            
            filename = f"kolmo_history_{start_date.isoformat()}_{end_date.isoformat()}.json"
            filepath = exporter.output_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, cls=DecimalEncoder, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Exported history ({len(export_data)} records): {filepath}")
            return filepath
            
    except Exception as e:
        logger.error(f"Failed to export history: {e}")
        return None


# =============================================================================
# 🔒 FIXED FILENAME EXPORT - kolmo_history.json
# =============================================================================

FIXED_HISTORY_FILENAME = "kolmo_history.json"


async def export_full_history_auto(
    output_dir: str | Path | None = None
) -> Path | None:
    """
    🔒 Export FULL KOLMO history to a FIXED filename.
    
    This function:
    - Queries ALL data from mcol1_compute_data
    - ALWAYS writes to: kolmo_history_2021-07-01_2026-01-22.json
    - Overwrites the file on each call
    
    Use this after backfill or daily updates to keep the export current.
    
    Args:
        output_dir: Optional custom output directory (default: ./data/export)
    
    Returns:
        Path to the fixed JSON file, or None on error
    """
    exporter = JSONExporter(output_dir)
    
    try:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    date, r_me4u, r_iou2, r_uome,
                    relpath_me4u, relpath_iou2, relpath_uome,
                    vol_me4u, vol_iou2, vol_uome,
                    winner, kolmo_deviation
                FROM mcol1_compute_data
                ORDER BY date ASC
                """
            )
            
            if not rows:
                logger.warning("No data found in mcol1_compute_data")
                return None
            
            export_data = []
            for row in rows:
                export_data.append({
                    "date": row["date"].isoformat(),
                    "r_me4u": str(row["r_me4u"]),
                    "r_iou2": str(row["r_iou2"]),
                    "r_uome": str(row["r_uome"]),
                    "relpath_me4u": float(row["relpath_me4u"]) if row["relpath_me4u"] is not None else None,
                    "relpath_iou2": float(row["relpath_iou2"]) if row["relpath_iou2"] is not None else None,
                    "relpath_uome": float(row["relpath_uome"]) if row["relpath_uome"] is not None else None,
                    "vol_me4u": float(row["vol_me4u"]) if row["vol_me4u"] is not None else None,
                    "vol_iou2": float(row["vol_iou2"]) if row["vol_iou2"] is not None else None,
                    "vol_uome": float(row["vol_uome"]) if row["vol_uome"] is not None else None,
                    "winner": row["winner"],
                    "kolmo_deviation": f"{float(row['kolmo_deviation']) * 1e5:.18f}e-5"
                })
            
            # FIXED filename - always the same
            filepath = exporter.output_dir / FIXED_HISTORY_FILENAME
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, cls=DecimalEncoder, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Auto-exported history ({len(export_data)} records): {filepath}")
            return filepath
            
    except Exception as e:
        logger.error(f"Failed to auto-export history: {e}")
        return None
