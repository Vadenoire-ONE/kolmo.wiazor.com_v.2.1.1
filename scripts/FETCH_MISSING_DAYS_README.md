## Fetch Missing Days - Smart Data Fetcher

Intelligent program that fetches exchange rate data **only for dates missing from the database**, avoiding redundant API calls and saving bandwidth and time.

### 🎯 Purpose

Instead of naively fetching all dates in a range (which would hammer the providers with requests for data you already have), this program:

1. **Queries** the database to find which dates have existing data
2. **Identifies** which dates are missing in a given range
3. **Fetches** data from providers **ONLY** for those missing dates
4. **Inserts** successfully fetched data into `mcol1_external_data`
5. **Reports** comprehensive statistics

### 📋 Features

✅ **Smart filtering** — Query database first, fetch only missing dates  
✅ **Batch processing** — Concurrent requests with configurable batch size  
✅ **Fallback providers** — Uses ProviderManager (Frankfurter → CBR → TwelveData)  
✅ **Business days only** — Automatically skips weekends  
✅ **Dry-run mode** — Preview what would be fetched without inserting  
✅ **Comprehensive logging** — File + console logs with timestamps  
✅ **Error handling** — Logs errors but continues processing  
✅ **Statistics reporting** — Summary of fetched, inserted, skipped, errors  

### 🚀 Usage

**Fetch today if missing:**
```bash
python scripts/fetch_missing_days.py
```

**Fetch a date range:**
```bash
python scripts/fetch_missing_days.py --start-date 2026-01-01 --end-date 2026-01-22
```

**Preview without inserting (dry-run):**
```bash
python scripts/fetch_missing_days.py --start-date 2026-01-01 --dry-run
```

**Custom batch size (more concurrent requests):**
```bash
python scripts/fetch_missing_days.py --start-date 2026-01-01 --batch-size 10
```

### 📊 Output Example

```
2026-01-22 10:15:23 - kolmo.scripts - INFO - ✅ Connected to database: localhost:5432/kolmo_db
2026-01-22 10:15:24 - kolmo.scripts - INFO - 📊 Database contains 250 dates with data
2026-01-22 10:15:24 - kolmo.scripts - INFO - 📅 Date range: 2026-01-01 to 2026-01-22 (22 days)
2026-01-22 10:15:24 - kolmo.scripts - INFO - 📈 Analysis: 16 business days | ✅ 14 existing | ❌ 2 missing
2026-01-22 10:15:24 - kolmo.scripts - INFO - 🚀 Starting fetch for 2 missing dates...
2026-01-22 10:15:24 - kolmo.scripts - INFO - ⬇️  Fetching 2026-01-21...
2026-01-22 10:15:26 - kolmo.scripts - INFO - ✅ Fetched from frankfurter: 2026-01-21
2026-01-22 10:15:26 - kolmo.scripts - INFO - 💾 Inserted 2026-01-21 (provider: frankfurter)
2026-01-22 10:15:26 - kolmo.scripts - INFO - 
======================================================================
📊 FETCH SUMMARY
======================================================================
  Business days queried:  16
  Days with data:         14
  Missing days found:     2
  Successfully fetched:   2
  Successfully inserted:  2
  Skipped (duplicate):    0
  Errors:                 0
======================================================================
```

### 📍 Log Files

Logs are saved to `./logs/fetch_missing_YYYYMMDD_HHMMSS.log` for audit trail.

### 🔧 Database Tables

**Reads from:** `mcol1_external_data` (to find existing dates)  
**Writes to:** `mcol1_external_data` (inserts new raw rate data)  

Automatic conflict handling — if a date somehow already exists, the insert is skipped gracefully.

### ⚙️ Configuration

All settings come from `.env`:
- `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`
- `FRANKFURTER_BASE_URL`, `CBR_BASE_URL`, `TWELVEDATA_API_KEY`

### 💡 Use Cases

1. **Initial backfill** — Fill in missing historical data:
   ```bash
   python scripts/fetch_missing_days.py --start-date 2021-07-01 --end-date 2026-01-22
   ```

2. **Weekly catch-up** — Get the last 7 days:
   ```bash
   python scripts/fetch_missing_days.py
   ```

3. **Gap repair** — Find and fix specific missing ranges:
   ```bash
   python scripts/fetch_missing_days.py --start-date 2025-12-01 --end-date 2025-12-31
   ```

4. **Scheduled task** — Run via cron/Task Scheduler to keep database current:
   ```bash
   # In crontab: Daily at 10 PM
   0 22 * * * cd /path/to/rates_winners && python scripts/fetch_missing_days.py
   ```

### 📈 Performance

- **Smart querying** saves 90%+ API calls vs. naive backfill
- Batch processing (default 5 concurrent) prevents provider rate-limiting
- Detailed logging helps identify which providers are slow/unreliable

### 🐛 Troubleshooting

**"All providers failed":**
- Check `.env` for API keys and base URLs
- Verify internet connection
- Check provider status (Frankfurter, CBR, TwelveData)

**"ON CONFLICT DO NOTHING skipped":**
- This is normal — date already exists in database
- Safe to run multiple times (idempotent)

**No logs in `./logs/`:**
- Ensure `logs/` directory exists or will be created
- Check write permissions in project directory
