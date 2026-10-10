# Medicare Part D Healthcare Analytics Warehouse on Snowflake

A comprehensive data engineering portfolio project demonstrating **Snowflake**, **dbt**, **governance**, and **cost control** using public CMS Medicare Part D prescriber data.

**Status:** Built and run end to end on a Snowflake trial account. Measured results are in the [Results](#results) section: dbt build PASS=72 WARN=1 ERROR=0, with row counts and cost.

---

## Project Overview

This project builds a modern data warehouse for healthcare analytics using:

- **Snowflake** as the cloud data platform
- **dbt** for ELT and testing (62 data tests, 1 incremental model, 1 Dynamic Table)
- **Governance** with dynamic masking, row access policies, and column tagging
- **Cost control** via resource monitors, auto-suspend, and scheduled tasks
- **CI/CD** with GitHub Actions (dbt parse + pytest)
- **Public data source** from CMS (Medicare Part D, non-PHI, aggregate)

**Use Case:** Analyze prescribing patterns, drug costs, specialty utilization, and opioid prescribing trends across the United States using publicly available data.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Data Ingestion (Python)                     │
│  CMS Public API / CSV → scripts/download_cms_data.py             │
│  Output: 500K rows × 11 columns (≈50MB)                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Snowflake (Cloud DW)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ RAW Schema (SQL)                                         │  │
│  │ ├─ PRESCRIBER_CLAIMS (raw CMS data)                     │  │
│  │ └─ STREAM_PRESCRIBER_CLAIMS (change capture)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ STAGING Schema (dbt Views)                              │  │
│  │ ├─ stg_prescriber_claims                                │  │
│  │ ├─ int_specialty_drug_aggregates                        │  │
│  │ └─ int_state_drug_aggregates                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ MARTS Schema (dbt Tables + Dynamic Tables)              │  │
│  │ ├─ fct_cost_by_specialty_state                          │  │
│  │ ├─ fct_brand_vs_generic_share                           │  │
│  │ ├─ fct_top_drugs_by_cost                                │  │
│  │ ├─ fct_opioid_prescribing_by_specialty                  │  │
│  │ ├─ fct_prescriber_cost_trends (INCREMENTAL)             │  │
│  │ └─ dyn_top_drugs_by_state (DYNAMIC TABLE, auto-refresh) │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ GOVERNANCE Schema (SQL + Policies)                      │  │
│  │ ├─ MASK_PROVIDER_NAME (dynamic masking)                 │  │
│  │ ├─ MASK_NPI (dynamic masking)                           │  │
│  │ ├─ RAP_STATE_FILTER (row access policy)                 │  │
│  │ └─ TAG_* (column tags for audit)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Cost Control                                             │  │
│  │ ├─ WH_PARTD: X-SMALL, auto-suspend 60sec               │  │
│  │ ├─ RM_PARTD: 20-credit resource monitor                │  │
│  │ └─ TASK_INCREMENTAL_MERGE: initially suspended          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Analytics & BI (dbt + SQL)                    │
│  ├─ 62 data tests (generic + singular reconciliation tests)      │
│  ├─ Metrics (total_prescribers, total_claims, total_spend)      │
│  └─ Optional: Streamlit dashboard for quick viz                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
snowflake-part-d-lab/
├── .gitignore                          # Exclude secrets, keys, target/
├── .env.template                       # Template for environment variables
├── README.md                           # This file
│
├── scripts/
│   ├── generate_keypair.sh             # Generate RSA key pair for auth
│   └── download_cms_data.py            # Download & validate CMS data
│
├── setup/
│   ├── 01_account_setup.sql            # Warehouse, database, roles (ACCOUNTADMIN)
│   ├── 02_load.sql                     # Create tables, stream, load data
│   └── 03_governance.sql               # Masking policies, RAP, tags
│
├── dbt/
│   ├── dbt_project.yml                 # dbt project configuration
│   ├── profiles.yml.template           # dbt profile (read env_var() only)
│   ├── models/
│   │   ├── staging/
│   │   │   └─ stg_prescriber_claims.sql
│   │   ├── intermediate/
│   │   │   ├─ int_specialty_drug_aggregates.sql
│   │   │   └─ int_state_drug_aggregates.sql
│   │   ├── marts/
│   │   │   ├─ fct_cost_by_specialty_state.sql
│   │   │   ├─ fct_brand_vs_generic_share.sql
│   │   │   ├─ fct_top_drugs_by_cost.sql
│   │   │   ├─ fct_opioid_prescribing_by_specialty.sql
│   │   │   ├─ fct_prescriber_cost_trends.sql (INCREMENTAL)
│   │   │   ├─ dyn_top_drugs_by_state.sql (DYNAMIC TABLE)
│   │   │   └─ schema.yml              # Source/model/test definitions
│   ├── tests/
│   │   ├── generic/
│   │   │   └─ positive_values.sql
│   │   └─ singular/
│   │       ├─ reconcile_cost_by_specialty_state.sql
│   │       ├─ reconcile_top_drugs.sql
│   │       ├─ brand_generic_share_validation.sql
│   │       ├─ no_duplicate_claims.sql
│   │       └─ detect_cost_outliers.sql
│
├── docs/
│   ├── governance.md                   # Access control model, masking policies
│   ├── cost.md                         # Cost tracking, resource monitor config
│   └── architecture.md                 # Detailed architecture notes
│
├── .github/
│   └── workflows/
│       └─ ci.yml                       # GitHub Actions: dbt parse + pytest
│
├── tests/
│   └─ test_cms_downloader.py           # pytest suite for data download script
│
├── requirements.txt                    # Python dependencies
└── keys/                               # (git-ignored) RSA key pair
    ├─ your_username_private_key.p8
    └─ your_username_public_key.pub
```

---

## Quick Start

### 1. Prerequisites

- **Snowflake Trial Account** (free, $400 credits)
- **Python 3.11+** with pip
- **Git** and **GitHub** (for CI/CD)
- **OpenSSL** (for key generation)

### 2. Clone & Setup

```bash
git clone <this-repo>
cd snowflake-part-d-lab

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.template .env
# Edit .env with your Snowflake credentials (see steps below)
```

### 3. Generate RSA Key Pair (Recommended Auth)

```bash
chmod +x scripts/generate_keypair.sh
./scripts/generate_keypair.sh your_username

# Output:
# ✓ Key pair generated:
#   Private key: keys/your_username_private_key.p8
#   Public key:  keys/your_username_public_key.pub
#
# Next: Register the public key in Snowflake:
#   1. Copy the contents of keys/your_username_public_key.pub
#   2. Run in Snowsight as ACCOUNTADMIN:
#      ALTER USER your_username SET RSA_PUBLIC_KEY = '<public_key_content>';
#   3. Set environment variables:
#      export SNOWFLAKE_PRIVATE_KEY_PATH=keys/your_username_private_key.p8
#      export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=<passphrase_you_entered>
```

---

## Execution Order

### Phase 1: Snowflake Account Setup (Snowsight, ACCOUNTADMIN)

**Run in Snowsight as ACCOUNTADMIN:**

```sql
-- Copy-paste entire contents of setup/01_account_setup.sql
-- This creates:
-- - WH_PARTD warehouse (X-SMALL, auto-suspend 60sec, initially suspended)
-- - RM_PARTD resource monitor (20 credits, suspend at 100%)
-- - PARTD_LAB database with RAW, STAGING, MARTS, GOVERNANCE schemas
-- - PARTD_ENGINEER and PARTD_ANALYST roles
-- - Internal stage for data loading
```

**Then:**

```sql
-- Register your public RSA key
ALTER USER your_username SET RSA_PUBLIC_KEY = '<contents_of_public_key.pub>';
```

### Phase 2: Set Environment Variables (Terminal)

```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1  # From welcome email
export SNOWFLAKE_USER=your_username
export SNOWFLAKE_ROLE=PARTD_ENGINEER
export SNOWFLAKE_WAREHOUSE=WH_PARTD
export SNOWFLAKE_DATABASE=PARTD_LAB
export SNOWFLAKE_PRIVATE_KEY_PATH=keys/your_username_private_key.p8
export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=your_passphrase
```

### Phase 3: Download Data (Terminal)

```bash
# Download REAL CMS data (2024 dataset): first 20K rows per state for the first 25 states
# alphabetically (AL to MO), in NPI order. Not a national or random sample (see Limitations).
python scripts/download_cms_data.py

# Example log format only. The counts below are illustrative, not the real run.
# The measured numbers are in the Results section.
# 2024-10-09 15:30:45 | INFO | Starting REAL CMS data download
# 2024-10-09 15:30:45 | INFO | Fetching from 25+ states, 20000 rows per state
# 2024-10-09 15:30:47 | INFO |   Fetching AL...
# 2024-10-09 15:30:47 | INFO |     ✓ 18,234 rows from AL
# 2024-10-09 15:30:48 | INFO |   Fetching AK...
# 2024-10-09 15:30:48 | INFO |     ✓ 5,123 rows from AK
# ... (continues for ~25 states)
# 2024-10-09 15:32:15 | INFO | ✓ Combined 487,234 rows from 25 states: AL, AK, AZ, ...
# 2024-10-09 15:32:17 | INFO | ✓ Data passed realism checks:
# 2024-10-09 15:32:17 | INFO |   Prescribers: 45,123 (min: 1,000)
# 2024-10-09 15:32:17 | INFO |   States: 25 (min: 20)
# 2024-10-09 15:32:17 | INFO |   Drugs: 2,847 (min: 100)
# 2024-10-09 15:32:19 | INFO | ✓ Saved 487,234 rows to data/raw/cms_partd_20241009_153050.csv
# 2024-10-09 15:32:19 | INFO | Metadata file: data/raw/cms_partd_20241009_153050_metadata.json

# Customize sampling:
python scripts/download_cms_data.py --rows-per-state 10000  # 10K per state (~250K total)
python scripts/download_cms_data.py --rows-per-state 50000  # 50K per state (~1.25M total)

# If CMS API is temporarily down, generate synthetic sample data instead:
python scripts/download_cms_data.py --synthetic

# Output will include warning:
# ⚠️  GENERATING SYNTHETIC SAMPLE DATA (NOT REAL CMS DATA)
# File will be named: cms_partd_20241009_153050_SYNTHETIC.csv
# Metadata will include: "data_source": "SYNTHETIC", "WARNING": "..."
```

### Phase 4: Load Data into Snowflake (Snowsight)

**In Snowsight, switch to PARTD_ENGINEER role and run:**

```sql
-- Upload CSV file to internal stage
PUT file:///path/to/data/raw/cms_partd_YYYYMMDD_HHMMSS.csv @PARTD_LAB.RAW.STG_PARTD;

-- Copy entire contents of setup/02_load.sql
-- This creates RAW and STAGING tables, stream, and scheduled task
```

**Verify load:**

```sql
SELECT COUNT(*) as row_count FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS;
-- Expected: 500,000 (see Results for the measured reconciliation)
```

### Phase 5: Apply Governance Policies (Snowsight)

**In Snowsight, run entire contents of setup/03_governance.sql:**

```sql
-- This creates masking policies, row access policies, and tags
```

**Verify masking (as PARTD_ENGINEER):**

```sql
USE ROLE PARTD_ENGINEER;
SELECT NPI, PROVIDER_LAST_NAME FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS LIMIT 1;
-- Example of the expected shape: 1234567890 | Smith
```

**Verify masking (as PARTD_ANALYST):**

```sql
USE ROLE PARTD_ANALYST;
SELECT NPI, PROVIDER_LAST_NAME FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS LIMIT 1;
-- Example of the expected shape: hash pseudonym | ***MASKED***
```

### Phase 6: dbt ELT Pipeline (Terminal)

```bash
cd dbt

# Set up dbt profile
cp profiles.yml.template ~/.dbt/profiles.yml
# Verify profiles.yml uses env_var() for all credentials (no hardcoding)

# Validate profile and connection
dbt debug

# Run all models (staging + marts)
dbt run

# Run all tests (62 generic + singular data tests)
dbt test

# Generate documentation
dbt docs generate
```

**dbt Build Results (Actual Run):**

| Model | Type | Rows | Materialization |
|-------|------|------|-----------------|
| stg_prescriber_claims | View | 500K | view |
| int_specialty_drug_aggregates | View | ~2K | view |
| int_state_drug_aggregates | View | ~15K | view |
| fct_cost_by_specialty_state | Table | 1,411 | table |
| fct_brand_vs_generic_share | Table | 180 | table |
| fct_top_drugs_by_cost | Table | 100 | table |
| fct_opioid_prescribing_by_specialty | Table | 169 | table |
| fct_prescriber_cost_trends | Table | 20,252 | incremental |
| dyn_top_drugs_by_state | Dynamic Table | 1,250 | dynamic |

### Phase 7: CI/CD Pipeline (GitHub)

```bash
# Push to GitHub
git add -A
git commit -m "Initial commit: Snowflake Part D analytics warehouse"
git push origin main

# GitHub Actions automatically runs:
# - dbt parse (validates project, no Snowflake connection)
# - pytest (tests data download script with mocked HTTP)
# - flake8, black, isort (code quality)
```

### Phase 8 (Optional): Streamlit Dashboard

```bash
# streamlit_app.py reads marts via Snowflake connector
streamlit run streamlit_app.py

# Opens at http://localhost:8501
# Shows: top drugs by cost, specialty breakdown, state heatmap
```

---

## Results

### Data Ingestion Results

**CMS Medicare Part D 2024 Dataset (Real Data, First 25 States Alphabetically AL–MO):**

- **Source:** CMS "Medicare Part D Prescribers - by Provider and Drug", 2024 release (full dataset: 28,023,892 rows)
- **Sample Strategy:** First 25 states alphabetically (AL to MO), up to 20,000 rows per state in NPI order (not a national sample, not random)
- **Rows Downloaded:** 500,000
- **Unique Prescribers:** 20,252
- **Unique States:** 25
- **Unique Drugs:** 3,219
- **Total Cost (USD):** $3,996,523,549.72
- **Beneficiary Count (TOT_BENES):** 278,244 rows have NULL values (CMS suppression under 11 beneficiaries); kept as NULL per design
- **Row Drop Tracking:** Logged to downloader metadata; per-column NaN counts captured before filtering
- **File:** `data/raw/cms_partd_YYYYMMDD_HHMMSS.csv` (no SYNTHETIC marker)
- **Metadata:** `data/raw/cms_partd_YYYYMMDD_HHMMSS_metadata.json`
  - `data_source: "REAL_CMS"`
  - `sampling_method: "first 25 states alphabetically (AL to MO), up to 20000 rows each in NPI order"`
  - `rows_dropped_breakdown: {nan_per_column: {...}, rows_in: 500000, rows_out: 500000, ...}`
  - `api_endpoint: "https://data.cms.gov/data-api/v1/dataset/9552739e-3d05-4c1b-8eff-ecabf391e2e5/data"`

### Snowflake Load Results

**RAW.PRESCRIBER_CLAIMS Reconciliation:**

Snowflake load reconciled exactly to downloader metadata:
- **Total Rows:** 500,000
- **Unique Prescribers:** 20,252
- **Unique States:** 25
- **Total Cost (USD):** $3,996,523,549.72
- **NULL TOT_BENES:** 278,244 rows (CMS suppression for <11 beneficiaries, intentional, preserved)

### dbt Build Results

**Build Status: PASS=72 WARN=1 ERROR=0 SKIP=0 TOTAL=73**

- **62 Data Tests:** All passed (generic tests: not_null, unique, positive_values, accepted_values; singular tests: reconciliation, validation, outlier monitoring, grain checks)
- **Models:** 1 staging view, 2 intermediate views, 4 table models, 1 incremental model, 1 dynamic table
  - `stg_prescriber_claims` (staging view)
  - `int_specialty_drug_aggregates`, `int_state_drug_aggregates` (intermediate views)
  - `fct_cost_by_specialty_state` (table)
  - `fct_brand_vs_generic_share` (table)
  - `fct_top_drugs_by_cost` (table, top 100 drugs by cost)
  - `fct_opioid_prescribing_by_specialty` (table)
  - `fct_prescriber_cost_trends` (incremental model)
  - `dyn_top_drugs_by_state` (dynamic table, auto-refresh every 60 min)

**Mart Row Counts:**
| Mart | Rows |
|------|------|
| DYN_TOP_DRUGS_BY_STATE | 1,250 (25 states × top 50 drugs) |
| FCT_TOP_DRUGS_BY_COST | 100 |
| FCT_PRESCRIBER_COST_TRENDS | 20,252 (one snapshot per prescriber) |
| FCT_COST_BY_SPECIALTY_STATE | 1,411 |
| FCT_BRAND_VS_GENERIC_SHARE | 180 |
| FCT_OPIOID_PRESCRIBING_BY_SPECIALTY | 169 |

**Test Warnings:**
- 1 WARN: `detect_cost_outliers` (monitoring signal, flagged 100 rows for high drug costs >2× 99th percentile; severity='warn' so does not block build)

**Reconciliation Tests:**
- Total cost matches exactly between staging and all aggregated marts ($3,996,523,549.72)
- Per-mart reconciliation: `fct_cost_by_specialty_state` reconciles to staging; `fct_top_drugs_by_cost` reconciles to its own top-100 subset (by design)
- Note: Reconciliation tests were fixed to return rows only on mismatch (tolerance ±$0.01); earlier versions always returned 2 rows and always failed due to test design

### Governance Verification (Dynamic Masking Demo)

**Masking Test (5 sample rows, PARTD_ENGINEER vs PARTD_ANALYST):**

| Role | PRSCRBR_NPI | PRSCRBR_LAST_ORG_NAME | PRSCRBR_FIRST_NAME |
|------|-------------|----------------------|-------------------|
| PARTD_ENGINEER | *real NPI* | *real name* | *real name* |
| PARTD_ANALYST | *deterministic hash pseudonym* | ***MASKED*** | ***MASKED*** |

- **NPI Masking:** ENGINEER sees actual NPI; ANALYST sees consistent hash-based pseudonym (not anonymization; NPI is public here)
- **Name Masking:** ENGINEER sees real provider names; ANALYST sees `***MASKED***`
- **Note:** This demonstrates the mechanism; masking applied to RAW table only. Marts contain unmasked names and NPI (governance demo, not production security)

### Cost Usage

**Snowflake Credits Consumed:**
- **WH_PARTD (compute):** 0.284 credits
- **COMPUTE_WH (supporting):** 0.114 credits
- **Cloud services:** 0.0008 credits
- **Total:** ~0.40 credits
- **Resource Monitor (RM_PARTD):** 20-credit cap; auto-suspend at 60 seconds idle
- **Warehouse Configuration:** X-SMALL, auto-suspend 60 seconds

### Notes on Incremental Model

**FCT_PRESCRIBER_COST_TRENDS (Incremental):**
- This is a snapshot table per data load batch, **not a time trend** (only one load batch exists so far)
- To view trends over time, query multiple snapshots grouped by `source_loaded_at`
- Uses `incremental_strategy='merge'` with `unique_key=['prescriber_id', 'provider_state', 'prescriber_type', 'source_loaded_at']`
- Merge task (TASK_INCREMENTAL_MERGE) is suspended by default to save costs

---

## Key Features

### ✅ **Data Warehouse**
- 500K rows of real CMS Medicare Part D public data
- Snowflake cloud DW with intelligent caching & compression
- RAW → STAGING → MARTS medallion architecture

### ✅ **dbt ELT**
- 1 staging model (clean, deduplicate)
- 2 intermediate models (aggregations)
- 6 mart models (analytics-ready tables)
- 1 incremental model (efficient delta loads)
- 1 Dynamic Table (auto-refreshing metrics)
- 62 data tests (generic, custom, singular reconciliation)
- Documented models, columns, metrics

### ✅ **Governance**
- Dynamic masking: Hide PII (NPI, provider names) from analysts
- Row access policy: Ready for state-based filtering
- Column tagging: Mark sensitive data for audit
- Audit trail: Query log of sensitive column access
- **No hardcoded credentials:** All auth via environment variables

### ✅ **Cost Control**
- **Resource Monitor:** 20-credit cap, suspend at 100%
- **Auto-Suspend:** 60 seconds idle = $0 cost
- **Incremental Models:** Only process new data
- **Dynamic Tables:** Auto-refresh only if needed
- **Scheduled Task:** Initially suspended (enable manually)
- **Measured cost:** about 0.40 credits for the full run (see Cost Usage). Any monthly figure is an estimate

### ✅ **CI/CD**
- GitHub Actions: dbt parse + pytest
- No Snowflake secrets in CI (uses env vars)
- Automated code quality (black, isort, flake8)

### ✅ **Security**
- RSA key-pair authentication (not password)
- .gitignore excludes secrets, keys, target/
- profiles.yml reads from env_var() only
- All credentials from environment variables

---

## Documentation

- **[docs/governance.md](docs/governance.md)** — Access control, masking policies, audit trail
- **[docs/cost.md](docs/cost.md)** — Resource monitor config, credit tracking, cost optimization
- **[dbt/models/schema.yml](dbt/models/schema.yml)** — Model documentation, tests, metrics

---

## Troubleshooting

### "dbt: command not found"
```bash
pip install dbt-snowflake
```

### "Snowflake connector error"
```bash
# Verify environment variables
echo $SNOWFLAKE_ACCOUNT
echo $SNOWFLAKE_USER
echo $SNOWFLAKE_PRIVATE_KEY_PATH

# Test connection
snowsql -a $SNOWFLAKE_ACCOUNT -u $SNOWFLAKE_USER --private-key-path $SNOWFLAKE_PRIVATE_KEY_PATH -q "SELECT CURRENT_ROLE();"
```

### "Permission denied on PARTD_LAB"
```bash
# Verify you're using PARTD_ENGINEER role
dbt run --target dev  # Not ACCOUNTADMIN
```

### "Task not running (incremental load)"
```sql
-- Task is suspended by default to save costs
ALTER TASK PARTD_LAB.STAGING.TASK_INCREMENTAL_MERGE RESUME;

-- Verify status
SHOW TASKS;
```

### "dbt tests failing"
```bash
# Run singular test independently to see details
dbt test --select test_type:singular --test-new-connection
```

---

## Limitations

1. **Public Aggregate Data Only:** This is aggregate, non-PHI CMS data. Not suitable for clinical decision-making. Safe for analytics learning and demonstration.
2. **Trial Account:** Snowflake trial account with limited free credits. Costs ~$0.40 per full run at current scale.
3. **Single Region:** Data in Snowflake default region only (no multi-region replication).
4. **Geographic Sampling (First 25 States, AL–MO, in NPI Order):** Not a national sample. Data is the first 20,000 rows per state for AL through MO only (25 states, not all 50). NPI allocation is not uniform geographically, so this sample biases toward states with more prescribers. Results are NOT nationally representative and NOT random.
5. **Incremental Model Has No Trend Yet:** `fct_prescriber_cost_trends` is a snapshot table per load batch. Only one load batch exists, so it shows no time trend. Multiple loads over time would enable trend analysis.
6. **Row Filtering:** Data cleaning drops rows with null critical columns (NPI, state, drug, claims) or non-positive claims. Beneficiary counts (TOT_BENES) are kept as NULL for <11 beneficiaries per CMS suppression policy (not a data quality issue). Metrics using beneficiary data must exclude NULL rows.
7. **Governance Demo Only:** Dynamic masking is applied to RAW table only. Marts expose unmasked provider names and NPI. Merge task is suspended (not running live). This demonstrates governance mechanisms, not production-grade protection.
8. **Marts are aggregated fact tables, not a full star schema:** there are no dimension tables, and no dbt snapshots or slowly changing dimensions, so point-in-time history is not modelled.
9. **No BI Deployment:** Streamlit app code present but not deployed.
10. **Simplified Models:** Opioid classification uses simple keyword matching, not clinical algorithms.
11. **Code Authored with Claude:** This project was written with assistance from Claude (AI code generator).

---

## Next Steps

1. **Monitor costs** via `docs/cost.md` queries
2. **Extend marts** with your own analysis (e.g., geographic heatmaps, specialty trends)
3. **Integrate BI tools** (Tableau, Looker, Power BI)
4. **Scale to a larger dataset** (adjust `MAX_RECORDS` in downloader)

---

## Data Source

**REAL CMS DATA (2024 Dataset):**
- **Provider:** CMS (Centers for Medicare & Medicaid Services)
- **Dataset:** Medicare Part D Prescribers - by Provider and Drug
- **Release Year:** 2024 Medicare Part D Prescriber Public Use File
- **Total Records in Dataset:** 28,023,892 rows
- **Dataset ID:** 9552739e-3d05-4c1b-8eff-ecabf391e2e5
- **Public Dataset Link:** https://data.cms.gov/dataset/Medicare-Part-D-Prescribers-by-Provider-and-Drug
- **API Endpoint:** https://data.cms.gov/data-api/v1/dataset/9552739e-3d05-4c1b-8eff-ecabf391e2e5/data
- **Data Type:** Aggregate, non-PHI, publicly available
- **License:** Public domain (US government)
- **Validation:** Script validates ≥1,000 prescribers, ≥20 states, ≥100 drugs before accepting

**Real Column Names (from CMS 2024 dataset):**
- `Prscrbr_NPI` — Prescriber National Provider Identifier
- `Prscrbr_Last_Org_Name`, `Prscrbr_First_Name` — Provider name
- `Prscrbr_City`, `Prscrbr_State_Abrvtn` — Provider location
- `Prscrbr_Type` — Provider type (MD, DO, NP, PA, etc.)
- `Brnd_Name`, `Gnrc_Name` — Brand and generic drug names
- `Tot_Clms` — Total claims
- `Tot_30day_Fills` — Total 30-day fills
- `Tot_Day_Suply` — Total day supply
- `Tot_Drug_Cst` — Total drug cost
- `Tot_Benes` — Total beneficiaries

**Sampling Strategy (First N Rows Per State in NPI Order):**
- CMS API returns data sorted by NPI (prescriber identifier)
- We download the **first N rows per state** from the **first 25 states alphabetically (AL through MO)**
- Default: first 20,000 rows per state × 25 states
- Customizable: `--rows-per-state 10000` for fewer rows or `--rows-per-state 50000` for more
- Not a random sample, but ensures consistent geographic representation of early-alphabetic states

**Fallback Option (if API unavailable):**
- Use `python scripts/download_cms_data.py --synthetic` to generate test data
- Output clearly marked SYNTHETIC in filename and metadata
- Includes 500+ unique prescribers and 40+ states for testing purposes

---

## Code Quality

- ✅ **2024 CMS Dataset:** Real data from verified CMS API (9552739e-3d05-4c1b-8eff-ecabf391e2e5)
- ✅ **Per-State Sampling:** First 20K rows per state for 25 states (AL to MO). Not a national or random sample; see Limitations
- ✅ **API Respect:** Polite delays between requests, respects max page size (50K rows), retries with backoff
- ✅ **Data Validation:** Hard-fails if data shows <1,000 prescribers, <20 states, or <100 drugs
- ✅ **Explicit Synthetic Mode:** Use `--synthetic` flag for test data (clearly marked SYNTHETIC)
- ✅ **dbt parse:** Validates project structure (no Snowflake connection)
- ✅ **21 Pytest tests:** Per-state sampling, pagination, validation, realism checks (mocked HTTP)
- ✅ **Linting:** flake8, black, isort pass
- ✅ **No hardcoded secrets:** All credentials from env vars
- ✅ **Documented:** Models, columns, tests in schema.yml

---

## Built With

- **Snowflake** — Cloud data warehouse
- **dbt-snowflake** — Analytics engineering & testing
- **Python 3.11** — Data ingestion & validation
- **pytest** — Unit testing
- **GitHub Actions** — CI/CD
- **OpenSSL** — Key pair auth
- *Optional:* **Streamlit** — Dashboard

---

## Credits

This project was built with Claude's assistance to demonstrate best practices in data engineering: governance, cost control, testing, and reproducible analytics.

---

## License

MIT License — feel free to use this as a portfolio template.

---

## Questions?

See [docs/](docs/) for detailed documentation. Check CI logs in [.github/workflows/](.github/workflows/) for automated test results.

