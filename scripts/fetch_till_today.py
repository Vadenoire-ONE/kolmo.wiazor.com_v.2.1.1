#!/usr/bin/env python3
"""Fetch DB with actual data till the last rate recorded in provider"""

import psycopg2
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import subprocess

load_dotenv()

def get_last_date_in_db():
    """Get the last date with data in the database"""
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'kolmo_db'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD', 'postgres')
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM mcol1_external_data")
    result = cursor.fetchone()
    last_date = result[0] if result[0] else None
    
    cursor.close()
    conn.close()
    
    return last_date

def main():
    print("\n" + "="*80)
    print("🔄 FETCHING DATA FROM LAST RECORDED TO TODAY")
    print("="*80)
    
    # Get last date in DB
    last_date = get_last_date_in_db()
    today = datetime.now().date()
    
    print(f"\n📊 Status:")
    print(f"  Last date in DB: {last_date if last_date else 'No data'}")
    print(f"  Today: {today}")
    
    if not last_date:
        print("\n⚠️  Database is empty. Starting from 2021-07-01...")
        start_date = "2021-07-01"
    else:
        # Start from the day after last recorded date
        start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    end_date = today.strftime('%Y-%m-%d')
    
    print(f"\n🚀 Fetching from {start_date} to {end_date}...")
    print("="*80 + "\n")
    
    # Run fetch_missing_days with the calculated range
    cmd = [
        'python',
        'scripts/fetch_missing_days.py',
        '--start-date', start_date,
        '--end-date', end_date
    ]
    
    result = subprocess.run(cmd, cwd='.')
    
    print("\n" + "="*80)
    if result.returncode == 0:
        print("✅ Fetch completed successfully!")
    else:
        print("❌ Fetch completed with errors!")
    print("="*80 + "\n")
    
    return result.returncode

if __name__ == '__main__':
    exit(main())
