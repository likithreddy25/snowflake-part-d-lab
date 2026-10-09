# Cost Control & Warehouse Metrics

## Resource Monitor Configuration

The warehouse `WH_PARTD` has a resource monitor cap to prevent runaway costs:

```
Credit Quota: 20 credits per month
Suspension Triggers:
  - At 75%: notify (15 credits)
  - At 100%: suspend warehouse (20 credits)
Auto-Suspend: 60 seconds of inactivity
Auto-Resume: Yes
Initial State: SUSPENDED (must manually resume for queries)
```

This setup ensures:
1. **Cost ceiling:** Never exceeds 20 credits/month
2. **Idle cost savings:** Auto-suspends after 60 seconds of inactivity
3. **Monitoring:** Email alert at 75% usage

---

## Credit Usage Tracking

To query actual credit consumption:

```sql
SELECT
    DATE(START_TIME) AS usage_date,
    WAREHOUSE_NAME,
    SUM(CREDITS_USED) AS credits_used,
    COUNT(*) AS query_count,
    ROUND(SUM(CREDITS_USED) / NULLIF(COUNT(*), 0), 4) AS avg_credits_per_query
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE WAREHOUSE_NAME = 'WH_PARTD'
  AND START_TIME >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1 DESC;
```

---

## Baseline Costs (after running full pipeline)

**Run this query after executing the lab to capture actual costs:**

```bash
# Set environment variables
export SNOWFLAKE_ACCOUNT=<your_account>
export SNOWFLAKE_USER=<your_user>
export SNOWFLAKE_WAREHOUSE=WH_PARTD
export SNOWFLAKE_DATABASE=PARTD_LAB

# Query warehouse credits (requires access to ACCOUNT_USAGE)
snowsql -q "
    SELECT
        'Total Credits Used (30 days)' AS metric,
        ROUND(SUM(CREDITS_USED), 2) AS value
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE WAREHOUSE_NAME = 'WH_PARTD'
        AND START_TIME >= CURRENT_DATE - INTERVAL '30 days'
    UNION ALL
    SELECT
        'Avg Credits per Query',
        ROUND(AVG(CREDITS_USED), 4)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE WAREHOUSE_NAME = 'WH_PARTD'
        AND START_TIME >= CURRENT_DATE - INTERVAL '7 days'
"
```

---

## Cost Results (Not run yet)

| Phase | Action | Data Size | Credits Used | Notes |
|-------|--------|-----------|--------------|-------|
| Setup | 01_account_setup.sql | N/A | ~0.05 | Warehouse/role creation only |
| Ingestion | Download + COPY INTO | ~500K rows (50MB CSV) | not run yet | Depends on cluster size, compression |
| dbt run (staging + marts) | stg_* + int_* + fct_* + dyn_* | 500K rows → ~50MB stored | not run yet | Includes 1 incremental, 1 dynamic table |
| dbt test | 25+ tests (generic + singular) | N/A | not run yet | Query cost for validation only |
| **Total** | Full pipeline | | not run yet | |

---

## Cost Optimization Strategies

### 1. **Auto-Suspend**
- Warehouse suspends after 60 seconds of inactivity
- Cost: `0 credits` when suspended
- Resume: Automatic on next query (~10-30 sec startup)

### 2. **Incremental dbt Models**
- `fct_prescriber_cost_trends` uses `incremental` materialization
- Only processes new/changed data after initial load
- Cost: Grows slowly with each load cycle

### 3. **Dynamic Tables**
- `dyn_top_drugs_by_state` auto-refreshes every 60 minutes
- Snowflake optimizes refresh: only if upstream data changed
- Cost: 1 minute of warehouse time per refresh (~0.01 credits/refresh)

### 4. **Scheduled Task (Initially Suspended)**
- `TASK_INCREMENTAL_MERGE` is **suspended by default**
- Resume only when needed: `ALTER TASK TASK_INCREMENTAL_MERGE RESUME;`
- Cost: ~0.05 credits per hourly run when enabled

### 5. **Query Profiling**
Use `EXPLAIN` to optimize slow queries before running:
```sql
EXPLAIN SELECT * FROM PARTD_LAB.MARTS.FCT_COST_BY_SPECIALTY_STATE WHERE TOTAL_COST_USD > 1000000;
```

### 6. **Materialized Views vs Tables**
- Staging/intermediate models are materialized as **views** (no storage cost)
- Marts are materialized as **tables** (small storage cost, faster queries)

---

## Monitoring Credit Usage

### Query history in Snowsight:
1. Open Snowsight → Admin → Billing & Usage
2. Warehouse Metering → WH_PARTD
3. View daily and hourly breakdown

### Programmatic monitoring:
```python
# Check credit usage (requires snowflake-connector-python)
from snowflake.connector import connect

ctx = connect(
    account='<your_account>',
    user='<your_user>',
    private_key_path='keys/your_user_private_key.p8',
    private_key_passphrase='<passphrase>',
    warehouse='WH_PARTD',
    database='PARTD_LAB'
)

cursor = ctx.cursor()
cursor.execute("""
    SELECT
        SUM(CREDITS_USED) as total_credits,
        COUNT(*) as query_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE WAREHOUSE_NAME = 'WH_PARTD'
      AND START_TIME >= CURRENT_DATE
""")

result = cursor.fetchone()
print(f"Today's usage: {result[0]} credits ({result[1]} queries)")
ctx.close()
```

---

## Estimated Monthly Costs (Trial Account)

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Compute (WH_PARTD, X-SMALL) | $2–5 | Depends on query frequency, auto-suspend helps |
| Storage (500K rows ≈ 50MB) | < $1 | Very small dataset |
| Resource Monitor | Included | No extra charge |
| **Total** | **~$2–6/month** | Well under free tier limits |

---

## Free Trial Considerations

- **Snowflake Free Trial:** $400 credits (typically 30 days)
- **This lab:** ~$2–6/month if run daily
- **Runway:** 60+ months on trial credits

---

## Cost Control Checklist

- [ ] Warehouse WH_PARTD is INITIALLY_SUSPENDED (verify with: `SHOW WAREHOUSES;`)
- [ ] Resource monitor RM_PARTD has 20 credit limit (verify: `SHOW RESOURCE MONITORS;`)
- [ ] Task TASK_INCREMENTAL_MERGE is suspended (verify: `SHOW TASKS;`)
- [ ] dbt models use views for staging (check: `SHOW VIEWS IN PARTD_LAB.STAGING;`)
- [ ] Monitor warehouse metering weekly (query above)
- [ ] Resume task only when needed for incremental loads

---

## References

- [Snowflake Warehouse Auto-Suspend](https://docs.snowflake.com/en/user-guide/warehouses-create.html#auto-suspend)
- [Snowflake Resource Monitors](https://docs.snowflake.com/en/user-guide/resource-monitors.html)
- [Snowflake Account Usage](https://docs.snowflake.com/en/sql-reference/account-usage.html)
- [dbt Incremental Models](https://docs.snowflake.com/en/user-guide/warehouses-create.html)
