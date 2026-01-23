#!/usr/bin/env python3
"""Report on database content for last 20 days"""

import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    # Connect directly
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'kolmo_db'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD', 'postgres')
    )

    cursor = conn.cursor()

    # Get dates from last 20 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=20)

    # Query data
    query = '''
    SELECT 
        date,
        COUNT(*) as rate_count,
        COUNT(CASE WHEN eur_usd IS NOT NULL THEN 1 END) +
        COUNT(CASE WHEN eur_cny IS NOT NULL THEN 1 END) +
        COUNT(CASE WHEN eur_rub IS NOT NULL THEN 1 END) +
        COUNT(CASE WHEN eur_inr IS NOT NULL THEN 1 END) +
        COUNT(CASE WHEN eur_aed IS NOT NULL THEN 1 END) as currency_count
    FROM mcol1_external_data
    WHERE date >= %s AND date <= %s
    GROUP BY date
    ORDER BY date DESC
    '''

    cursor.execute(query, (start_date, end_date))
    result = cursor.fetchall()

    # Calculate business days in range
    all_dates = set()
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0, Friday=4
            all_dates.add(current)
        current += timedelta(days=1)

    # Get dates with data
    dates_with_data = set(row[0] for row in result)

    print('\n' + '='*80)
    print('📊 DATABASE REPORT - LAST 20 DAYS')
    print('='*80)
    print(f'Date Range: {start_date} to {end_date}')
    print(f'Business days (Mon-Fri): {len(all_dates)}')
    print()
    print('Date            | Records | Currencies')
    print('-'*80)

    for row in result:
        date_val, count, curr_count = row
        print(f'{date_val} | {count:7d} | {curr_count:12d}')

    print('='*80)

    missing_dates = sorted(all_dates - dates_with_data, reverse=True)
    print(f'\n✅ Dates with data: {len(dates_with_data)}/{len(all_dates)} business days')
    print(f'❌ Missing dates: {len(missing_dates)}')

    if missing_dates:
        print('\nMissing dates:')
        for d in missing_dates:
            print(f'  - {d}')

    print('='*80)
    print(f'\nTotal records in range: {sum(row[1] for row in result)}')
    print('='*80 + '\n')

    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
