# Execution Runbook

Copy-paste these exact commands in order. Each phase is sequential.

---

## Phase 0: Local Setup (Terminal)

```bash
# 1. Clone and enter directory
cd ~/snowflake-part-d-lab

# 2. Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify Python packages
pip list | grep -E "dbt|snowflake|pandas|requests"
```

---

## Phase 1: Snowflake Account Setup (Snowsight Worksheet)

**Run as ACCOUNTADMIN in a new Snowsight worksheet:**

```sql
-- Copy-paste entire file: setup/01_account_setup.sql
-- This creates warehouse, database, roles, stage, resource monitor
-- After it runs, copy-paste this:

ALTER USER <YOUR_USERNAME> SET RSA_PUBLIC_KEY = '<COPY_PUBLIC_KEY_HERE>';
-- (You'll generate the public key in Phase 2)
```

**Wait for above to complete, then verify:**

```sql
SHOW WAREHOUSES;
SHOW DATABASES;
SHOW ROLES LIKE 'PARTD_%';
```

---

## Phase 2: Generate & Register Keys (Terminal + Snowsight)

**Terminal:**

```bash
cd ~/snowflake-part-d-lab

# Generate RSA key pair
./scripts/generate_keypair.sh your_username

# Output: public key saved to keys/your_username_public_key.pub
# Keep passphrase somewhere safe
```

**Snowsight (ACCOUNTADMIN):**

```bash
# Read public key content
cat ~/snowflake-part-d-lab/keys/your_username_public_key.pub

# Copy entire output (including -----BEGIN PUBLIC KEY----- and END line)
# Then run in Snowsight:
```

```sql
ALTER USER your_username SET RSA_PUBLIC_KEY = '-----BEGIN PUBLIC KEY-----
<PASTE_ENTIRE_PUBLIC_KEY_HERE>
-----END PUBLIC KEY-----';
```

**Verify registration:**

```sql
SELECT * FROM INFORMATION_SCHEMA.USERS WHERE NAME = 'YOUR_USERNAME';
-- RSA_PUBLIC_KEY_FP should be non-null
```

---

## Phase 3: Set Environment Variables (Terminal)

```bash
# Edit .env with your Snowflake details
cp .env.template .env
nano .env  # or vim, VSCode, etc.

# Then source it
source .env

# Verify all env vars are set
echo $SNOWFLAKE_ACCOUNT
echo $SNOWFLAKE_USER
echo $SNOWFLAKE_ROLE
echo $SNOWFLAKE_WAREHOUSE
echo $SNOWFLAKE_DATABASE
echo $SNOWFLAKE_PRIVATE_KEY_PATH
echo $SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
```

---

## Phase 4: Download CMS Data (Terminal)

```bash
# Ensure venv is still active
source venv/bin/activate

# Download and validate data
python scripts/download_cms_data.py

# Output will show:
# ✓ Saved 500000 rows to data/raw/cms_partd_YYYYMMDD_HHMMSS.csv
# Keep the filename for Phase 5
```

**Copy the output CSV filename (you'll need it next):**

```bash
ls -lh data/raw/cms_partd_*.csv
# Note the full path
```

---

## Phase 5: Load Data into Snowflake (Snowsight + Terminal)

**Terminal (upload to internal stage):**

```bash
# Get the CSV file path
CSV_FILE=$(ls -t data/raw/cms_partd_*.csv | head -1)
echo $CSV_FILE

# Upload to Snowflake stage using snowsql
snowsql -a $SNOWFLAKE_ACCOUNT -u $SNOWFLAKE_USER \
  --private-key-path $SNOWFLAKE_PRIVATE_KEY_PATH \
  --role PARTD_ENGINEER \
  --warehouse WH_PARTD \
  --database PARTD_LAB \
  --schema RAW \
  -c "PUT 'file://$CSV_FILE' @STG_PARTD AUTO_COMPRESS=TRUE;"
```

**Snowsight (PARTD_ENGINEER role):**

```sql
-- Run entire file: setup/02_load.sql
-- This creates RAW.PRESCRIBER_CLAIMS table, stream, and task

-- Then verify load completed
SELECT
    COUNT(*) as row_count,
    COUNT(DISTINCT NPI) as unique_prescribers,
    COUNT(DISTINCT PROVIDER_STATE) as unique_states,
    SUM(TOTAL_DRUG_COST) as total_cost_usd
FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS;

-- Note the results (for README)
```

---

## Phase 6: Apply Governance Policies (Snowsight)

**Snowsight (PARTD_ENGINEER role):**

```sql
-- Run entire file: setup/03_governance.sql
-- This creates masking policies, row access policies, tags

-- Verify masking as ENGINEER (should see unmasked):
USE ROLE PARTD_ENGINEER;
SELECT NPI, PROVIDER_LAST_NAME FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS LIMIT 3;

-- Switch to ANALYST and verify masking works:
USE ROLE PARTD_ANALYST;
SELECT NPI, PROVIDER_LAST_NAME FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS LIMIT 3;
-- Should show: NPI*** | ***MASKED***

-- Copy the ANALYST output to paste into README
```

---

## Phase 7: dbt ELT Pipeline (Terminal)

```bash
# Ensure venv is active
source venv/bin/activate

# Enter dbt directory
cd dbt

# Validate connection and profile
dbt debug
# Should show: "Connection successful"

# Run all models (staging + intermediate + marts)
dbt run
# Watch for: "Completed successfully"

# Run all tests (25+ tests)
dbt test
# Watch for: "Passed" count

# Generate documentation
dbt docs generate

# Verify models were created in Snowflake
dbt ls
```

**Get test results for README:**

```bash
dbt test --select fct_cost_by_specialty_state 2>&1 | tee /tmp/dbt_test_results.txt
# Copy output to README
```

---

## Phase 8: Verify Marts in Snowflake (Snowsight)

**Run as PARTD_ENGINEER to verify all marts:**

```sql
-- Check table counts
SELECT 'fct_cost_by_specialty_state' as table_name, COUNT(*) as row_count FROM PARTD_LAB.MARTS.FCT_COST_BY_SPECIALTY_STATE
UNION ALL
SELECT 'fct_brand_vs_generic_share', COUNT(*) FROM PARTD_LAB.MARTS.FCT_BRAND_VS_GENERIC_SHARE
UNION ALL
SELECT 'fct_top_drugs_by_cost', COUNT(*) FROM PARTD_LAB.MARTS.FCT_TOP_DRUGS_BY_COST
UNION ALL
SELECT 'fct_opioid_prescribing_by_specialty', COUNT(*) FROM PARTD_LAB.MARTS.FCT_OPIOID_PRESCRIBING_BY_SPECIALTY
UNION ALL
SELECT 'fct_prescriber_cost_trends', COUNT(*) FROM PARTD_LAB.MARTS.FCT_PRESCRIBER_COST_TRENDS
UNION ALL
SELECT 'dyn_top_drugs_by_state', COUNT(*) FROM PARTD_LAB.MARTS.DYN_TOP_DRUGS_BY_STATE;

-- Copy results to README
```

---

## Phase 9: Measure Credits Used (Snowsight)

**After pipeline is complete, measure actual credit usage:**

```sql
SELECT
    'Total Credits (7 days)' as metric,
    ROUND(SUM(CREDITS_USED), 2) as value
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE WAREHOUSE_NAME = 'WH_PARTD'
  AND START_TIME >= CURRENT_DATE - INTERVAL '7 days'
UNION ALL
SELECT
    'Average per Query',
    ROUND(AVG(CREDITS_USED), 4)
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE WAREHOUSE_NAME = 'WH_PARTD'
  AND START_TIME >= CURRENT_DATE - INTERVAL '7 days';

-- Copy results to docs/cost.md
```

---

## Phase 10: CI/CD Setup (GitHub)

```bash
# Exit venv
deactivate

# Initialize git (if not already done)
cd ~/snowflake-part-d-lab
git init
git add -A
git commit -m "Initial: Snowflake Part D analytics warehouse

- Snowflake setup with resource monitor and governance
- dbt project: 8 models, 25+ tests, 1 incremental, 1 dynamic table
- Data ingestion: CMS Medicare Part D public data (500K rows)
- Governance: Dynamic masking, row access policies, column tags
- CI/CD: GitHub Actions for dbt parse and pytest
- Cost control: Auto-suspend warehouse, scheduled task

This is portfolio work built with Claude's assistance."

# Push to GitHub (requires GitHub remote to be configured)
git remote add origin https://github.com/your_username/snowflake-part-d-lab.git
git branch -M main
git push -u origin main
```

---

## Phase 11: Optional - Streamlit Dashboard (Terminal)

```bash
# Activate venv
source venv/bin/activate

# Run Streamlit
streamlit run streamlit_app.py

# Opens at http://localhost:8501
# Requires dbt marts to be populated (Phase 7)
```

---

## Checklist Before Committing

- [ ] .gitignore exists and excludes .env, *.p8, *.pem, target/, logs/
- [ ] .env is NOT committed (only .env.template)
- [ ] No hardcoded Snowflake credentials in any file
- [ ] dbt/profiles.yml uses env_var() for all secrets
- [ ] README.md has real results (copy-pasted from Snowsight)
- [ ] docs/cost.md has actual credit usage
- [ ] docs/governance.md has actual masking test output
- [ ] GitHub Actions CI passes (dbt parse + pytest)
- [ ] All dbt tests pass (25+ tests)
- [ ] Task TASK_INCREMENTAL_MERGE is SUSPENDED by default

---

## Troubleshooting

### "dbt: command not found"
```bash
source venv/bin/activate
pip install dbt-snowflake
```

### "No SNOWFLAKE_ACCOUNT in env"
```bash
source .env
echo $SNOWFLAKE_ACCOUNT
```

### "Private key permission denied"
```bash
chmod 600 keys/*.p8
```

### "warehouse is suspended"
```sql
-- Resume manually in Snowsight:
ALTER WAREHOUSE WH_PARTD RESUME;
```

### "Task is running (burning credits)"
```sql
-- Suspend immediately:
ALTER TASK PARTD_LAB.STAGING.TASK_INCREMENTAL_MERGE SUSPEND;
```

---

## After Everything Works

1. **Paste real results** from Snowsight queries into README.md
2. **Update docs/cost.md** with actual warehouse metering data
3. **Document any custom marts** you add
4. **Share the repo** as part of your portfolio
5. **Clean up keys/** directory before sharing (never commit private keys)

---

## Support

See README.md and docs/ for detailed documentation.

