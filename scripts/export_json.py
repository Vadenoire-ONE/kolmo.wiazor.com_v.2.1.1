#!/usr/bin/env python
"""
Export KOLMO data to JSON

Usage:
    # Export today's data
    python scripts/export_json.py
    
    # Export specific date
    python scripts/export_json.py --date 2026-01-15
    
    # Export date range
    python scripts/export_json.py --start 2026-01-01 --end 2026-01-15
    
    # Custom output directory
    python scripts/export_json.py --output ./my_exports
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kolmo.export.json_exporter import (
    export_from_database,
    export_history_to_json,
)


async def main():
    parser = argparse.ArgumentParser(
        description="Export KOLMO data to JSON files"
    )
    parser.add_argument(
        "--date", "-d",
        type=str,
        help="Single date to export (YYYY-MM-DD). Default: today"
    )
    parser.add_argument(
        "--start", "-s",
        type=str,
        help="Start date for range export (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", "-e",
        type=str,
        help="End date for range export (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./data/export",
        help="Output directory (default: ./data/export)"
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Range export
    if args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
        print(f"📊 Exporting KOLMO history: {start_date} → {end_date}")
        
        filepath = await export_history_to_json(start_date, end_date, output_dir)
        
        if filepath:
            print(f"✅ History exported to: {filepath}")
        else:
            print("❌ No data found for specified range")
            sys.exit(1)
    
    # Single date export
    else:
        target_date = date.fromisoformat(args.date) if args.date else date.today()
        print(f"📊 Exporting KOLMO data for: {target_date}")
        
        filepath = await export_from_database(target_date, output_dir)
        
        if filepath:
            print(f"✅ Exported to: {filepath}")
        else:
            print(f"❌ No data found for {target_date}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
