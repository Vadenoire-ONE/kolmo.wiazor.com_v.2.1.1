# KOLMO.wiazor.com v.2.1.1

**DTKT Currency Triangle Monitoring System**

KOLMO monitors three exchange rates forming a currency triangle (CNY ↔ USD ↔ EUR ↔ CNY) and identifies which currency path is improving toward arbitrage-free fairness each day.

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Amendment A1** | Exact decimal precision `NUMERIC(28,18)` with DB constraint |
| **Volatility Metrics** | Daily volatility index tracking (`vol_me4u`, `vol_iou2`, `vol_uome`) |
| **Explainability** | `winner_reason` JSONB tracks why each coin won |
| **Provider Stats** | `mcol1_provider_stats` table for operational visibility |
| **Multi-Provider** | Frankfurter → CBR → TwelveData fallback hierarchy |
| **API for Analytics** | Latest winner and historical date endpoints for dashboards |
| **JSON Export** | Automatic daily JSON export for external analytics (Plotly, Figma plugins, etc.) |
| **Example UI** | React + Plotly (plotly.js-dist-min) demo in example/ |
| **DTKT Connector** | Standalone program to link rates_winners and kolmo_analysis |
| **Security** | No hardcoded credentials, Vault/KMS integration ready |

## 📋 Requirements

- Python 3.11+
- PostgreSQL 15+ with TimescaleDB 2.x (optional)
- External API access to Frankfurter.dev

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd kolmo.wiazor.com_v2.1.1/rates_winners
python -m venv venv
venv\Scripts\activate  # Windows
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
copy .env.example .env
# Edit .env with your database credentials
```

### 3. Initialize Database

```bash
psql -U postgres -d kolmo_db -f db/migrations/001_initial_schema.sql
```

### 4. Run Server

```bash
python -m kolmo.main
```

### 5. Access API

- Winner: http://localhost:8000/api/v1/winner/latest
- Rates by date: http://localhost:8000/api/v1/rates/{date}
- Health: http://localhost:8000/api/v1/health
- OpenAPI: http://localhost:8000/docs

### 6. Launch Full DTKT System (API + UI)

```bash
# Check status
python dtkt_connector.py status

# Initialize kolmo_analysis frontend
python dtkt_connector.py init-analysis

# Start both API and UI
python dtkt_connector.py start-all
```

See [CONNECTOR_README.md](CONNECTOR_README.md) for details.

## 📊 KOLMO Rates (Standard Notation)

```python
r_me4u: Decimal  # ME4U coin = USD/CNY (US Dollars per 1 Chinese Yuan)
                 # Example: Decimal('0.1434') means "1 yuan = 0.1434 dollars"
                 # Or equivalently: "1 dollar buys 6.9748 yuan"

r_iou2: Decimal  # IOU2 coin = EUR/USD (Euros per 1 US Dollar)  
                 # Example: Decimal('0.8599') means "1 dollar = 0.8599 euros"
                 # Or equivalently: "1 euro buys 1.163 dollars"

r_uome: Decimal  # UOME coin = CNY/EUR (Chinese Yuan per 1 Euro)
                 # Example: Decimal('8.11') means "1 euro = 8.11 yuan"
                 # Or equivalently: "1 yuan buys 0.1233 euros"
```

### KOLMO Invariant

$$K = r_{ME4U} × r_{IOU2} × r_{UOME}$$

- `K = 1.0`: Perfect arbitrage-free market
- `0.995 ≤ K ≤ 1.005`: Normal conditions
- `K < 0.995` or `K > 1.005`: Market inefficiency

## 🏗️ Architecture

```
┌─ STAGE 1: DATA ACQUISITION ─┐
│ Provider Manager (fallback) │
│ INSERT INTO mcol1_external  │
└──────────────┬──────────────┘
               ↓
┌─ STAGE 2: STORAGE LAYER ────┐
│ PostgreSQL + TimescaleDB    │
│ mcol1_external_data (raw)   │
│ mcol1_compute_data (derived)│
└──────────────┬──────────────┘
               ↓
┌─ STAGE 3: COMPUTATION ──────┐
│ Rate Transformer            │
│ KOLMO Calculator (Decimal)  │
│ Winner Selector             │
└──────────────┬──────────────┘
               ↓
┌─ STAGE 4: API SERVING ──────┐
│ FastAPI REST endpoints      │
│ GET /api/v1/winner/latest   │
└─────────────────────────────┘
```

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=src/kolmo --cov-report=html

# Golden dataset tests only
pytest tests/test_golden_dataset.py
```

## 📁 Project Structure

```
rates_winners/
├── src/kolmo/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Settings management
│   ├── models.py            # Pydantic data models
│   ├── database.py          # Database connection
│   ├── providers/           # External data providers
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── frankfurter.py
│   │   ├── cbr.py
│   │   ├── twelvedata.py
│   │   └── manager.py
│   ├── computation/         # KOLMO computation engine
│   │   ├── __init__.py
│   │   ├── transformer.py
│   │   ├── calculator.py
│   │   ├── winner.py
│   │   └── engine.py
│   ├── export/              # JSON export module
│   │   ├── __init__.py
│   │   └── json_exporter.py
│   └── api/                 # FastAPI routes
│       ├── __init__.py
│       ├── routes.py
│       └── schemas.py
├── db/migrations/
│   └── 001_initial_schema.sql
├── scripts/
│   ├── backfill_historical.py
│   ├── export_json.py       # Manual JSON export script
│   ├── query_date.py
│   ├── report_markers.py
│   ├── run_migrations.py
│   └── test_k_value.py
├── example/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── Attributions.md
│   ├── components/
│   ├── guidelines/
│   └── styles/
├── tests/
│   ├── golden/
│   │   └── kolmo_reference_data.csv
│   ├── test_computation.py
│   └── test_golden_dataset.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── structure.md
├── dtkt_connector.py        # DTKT system launcher
├── CONNECTOR_README.md      # Connector documentation
└── README.md
```

## 📚 API Usage

### Base URL

Local development:

```
http://localhost:8000
```

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/winner/latest | Latest winner and metrics |
| GET | /api/v1/rates/{date} | Metrics for a specific date (YYYY-MM-DD) |
| GET | /api/v1/health | Health status |

### Example: latest winner

```
curl http://localhost:8000/api/v1/winner/latest
```

### Example: specific date

```
curl http://localhost:8000/api/v1/rates/2026-01-15
```

### Example: fetch in React (Plotly data source)

```
const res = await fetch("http://localhost:8000/api/v1/winner/latest");
const data = await res.json();

const date = data.date; // "YYYY-MM-DD"
const kolmo = Number(data.kolmo_value_str); // precise decimal to number for charting
```

> For audit-grade math, keep `kolmo_value_str` as a string and use decimal handling in the backend. For charts, converting to number is acceptable.

## 📊 Applicable Variables (for Plotly/React)

These fields are returned by both `/api/v1/winner/latest` and `/api/v1/rates/{date}`.

### Time & Identity

- `date` (string, YYYY-MM-DD)
- `winner` (enum: IOU2, ME4U, UOME)

### KOLMO Invariant

- `kolmo_value_str` (string, 18 decimals, authoritative)
- `kolmo_value` (float, deprecated convenience)
- `kolmo_deviation` (float, |K − 1| × 100)
- `kolmo_state` (enum: OK, WARN, CRITICAL)

### KOLMO Rates

- `r_me4u` (string, 6 decimals) — USD/CNY
- `r_iou2` (string, 6 decimals) — EUR/USD
- `r_uome` (string, 6 decimals) — CNY/EUR

### Distance & RelativePath

- `dist_me4u`, `dist_iou2`, `dist_uome` (float)
- `relpath_me4u`, `relpath_iou2`, `relpath_uome` (float)

### Volatility (Daily Volatility Index)

- `vol_me4u`, `vol_iou2`, `vol_uome` (float, nullable)
- Formula: `vol = (rate_today - rate_yesterday) / rate_yesterday × 100`
- Positive = rate increased, Negative = rate decreased, NULL = first day

### Explainability

- `winner_reason.me4u_relpath`
- `winner_reason.iou2_relpath`
- `winner_reason.uome_relpath`
- `winner_reason.max_relpath`
- `winner_reason.tied_coins` (array)
- `winner_reason.selection_rule` (string)
- `winner_reason.winner` (enum)

### Plotly mapping guidance (example folder)

- Use `date` for the x-axis.
- Plot `kolmo_deviation` as a line (system stability).
- Plot `r_me4u`, `r_iou2`, `r_uome` as rate series.
- Plot `relpath_me4u`, `relpath_iou2`, `relpath_uome` for winner dynamics.

## 📚 API Reference

### GET /api/v1/winner/latest

Returns today's winning KOLMO coin for M0.1 integration.

**Response:**
```json
{
  "date": "2026-01-15",
  "winner": "IOU2",
  "kolmo_value_str": "1.000041342600000000",
  "kolmo_value": 1.000041,
  "r_me4u": "0.143400",
  "r_iou2": "0.859948",
  "r_uome": "8.110000",
  "kolmo_deviation": 0.0041,
  "kolmo_state": "OK",
  "winner_reason": {
    "me4u_relpath": -0.35,
    "iou2_relpath": 3.24,
    "uome_relpath": 0.05,
    "max_relpath": 3.24,
    "tied_coins": ["IOU2"],
    "selection_rule": "max_positive_alphabetical_tiebreak",
    "winner": "IOU2"
  },
  "dist_me4u": 0.12,
  "dist_iou2": 0.08,
  "dist_uome": 0.15,
  "relpath_me4u": -0.35,
  "relpath_iou2": 3.24,
  "relpath_uome": 0.05,
  "vol_me4u": 0.9859,
  "vol_iou2": -0.5896,
  "vol_uome": 0.1234
}
```

## �️ Database Schema: `mcol1_compute_data`

The main table storing derived KOLMO metrics. All columns are documented below.

### Primary Key & Date

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Auto-generated unique identifier |
| `date` | DATE | NOT NULL, UNIQUE | Date of the rate data |

### KOLMO Rates (Standardized Notation)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `r_me4u` | NUMERIC(18,6) | NOT NULL, > 0 | ME4U rate: USD/CNY (US Dollars per 1 Chinese Yuan) |
| `r_iou2` | NUMERIC(18,6) | NOT NULL, > 0 | IOU2 rate: EUR/USD (Euros per 1 US Dollar) |
| `r_uome` | NUMERIC(18,6) | NOT NULL, > 0 | UOME rate: CNY/EUR (Chinese Yuan per 1 Euro) |

### KOLMO Invariant (Amendment A1)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `kolmo_value` | NUMERIC(28,18) | NOT NULL | 🔒 Exact product `r_me4u × r_iou2 × r_uome` (no rounding) |
| `kolmo_deviation` | NUMERIC(8,4) | NOT NULL | Deviation from 1.0 as percentage |
| `kolmo_state` | VARCHAR(25) | IN ('OK','WARN','CRITICAL') | OK: <1%, WARN: 1-5%, CRITICAL: ≥5% |

### Distance Metrics (Deviation from Parity)

| Column | Type | Description |
|--------|------|-------------|
| `dist_me4u` | NUMERIC(10,4) | `\|r_me4u - 1.0\| × 100` — distance from parity (%) |
| `dist_iou2` | NUMERIC(10,4) | `\|r_iou2 - 1.0\| × 100` — distance from parity (%) |
| `dist_uome` | NUMERIC(10,4) | `\|r_uome - 1.0\| × 100` — distance from parity (%) |

### RelativePath Metrics (Improvement Tracking)

| Column | Type | Description |
|--------|------|-------------|
| `relpath_me4u` | NUMERIC(10,4) | `(dist_prev - dist_curr) / dist_prev × 100` — improvement % |
| `relpath_iou2` | NUMERIC(10,4) | Positive = improving toward parity |
| `relpath_uome` | NUMERIC(10,4) | NULL on first day (no previous data) |

### Volatility Metrics (Daily Volatility Index)

| Column | Type | Description |
|--------|------|-------------|
| `vol_me4u` | NUMERIC(28,18) | `(rate_today - rate_yesterday) / rate_yesterday × 100` |
| `vol_iou2` | NUMERIC(28,18) | Positive = rate increased, Negative = rate decreased |
| `vol_uome` | NUMERIC(28,18) | NULL on first day (no previous data) |

### Winner Selection

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `winner` | VARCHAR(5) | IN ('ME4U','IOU2','UOME') | Winning coin for the day |
| `winner_reason` | JSONB | NOT NULL | Explainability metadata (see below) |

**winner_reason JSON structure:**
```json
{
  "me4u_relpath": -0.35,
  "iou2_relpath": 3.24,
  "uome_relpath": 0.05,
  "max_relpath": 3.24,
  "tied_coins": ["IOU2"],
  "selection_rule": "max_positive_alphabetical_tiebreak",
  "winner": "IOU2"
}
```

### Audit Trail

| Column | Type | Description |
|--------|------|-------------|
| `mcol1_snapshot_id` | UUID | FK → `mcol1_external_data.mcol1_snapshot_id` |
| `mcol1_snapshot_compute_id` | UUID | Unique ID for this computation snapshot |
| `trace_compute_id` | UUID | Trace ID for debugging/logging |

### Timestamps

| Column | Type | Description |
|--------|------|-------------|
| `created_at` | TIMESTAMPTZ | Record creation time (UTC) |
| `updated_at` | TIMESTAMPTZ | Last update time (UTC) |

### Database Constraints

- **chk_kolmo_exact_product**: Enforces `kolmo_value = r_me4u * r_iou2 * r_uome`
- **trg_validate_kolmo_invariant**: Trigger validates exact product before INSERT/UPDATE
- **FK to mcol1_external_data**: `ON DELETE RESTRICT` prevents orphaned records

## 📤 JSON Export

KOLMO automatically exports daily metrics to JSON files for external analytics tools.

### Automatic Export

After each pipeline run, a JSON file is created in `./data/export/`:

```json
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
```

### Manual Export

```bash
# Export today's data
python scripts/export_json.py

# Export specific date
python scripts/export_json.py --date 2026-01-15

# Export date range (creates single file with array)
python scripts/export_json.py --start 2026-01-01 --end 2026-01-15

# Custom output directory
python scripts/export_json.py --output ./my_exports
```

### Configuration

Set in `.env`:
```
JSON_EXPORT_ENABLED=true
JSON_EXPORT_DIR=./data/export
```

### Using with Figma

For visualization in Figma, use plugins that support JSON import:
- **Google Sheets Sync** — import JSON via Google Sheets
- **JSON to Figma** — direct JSON data import
- **Content Reel** — connect to local JSON files

## 📜 License

MIT License - DTKT Architecture Team

## 📖 Documentation

See [KOLMO.wiazor.com Technical Specification v.2.1.1](instructions/KOLMO.wiazor.com%20Technical%20Specification%20v.2.1.1.md) for complete requirements.
