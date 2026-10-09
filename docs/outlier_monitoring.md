# Cost Outlier Monitoring

## Overview

The outlier detection test (`tests/singular/detect_cost_outliers.sql`) is a **monitoring signal**, not a data quality gate. It identifies unusually high drug costs that warrant manual review.

## Test Logic

**Threshold:** Drug costs > 2× the 99th percentile

- Calculate the 99th percentile of all `drug_cost_usd` values in staging
- Flag rows where `drug_cost_usd > p99_cost × 2`
- Severity: `warn` (does not block dbt build)

## Why This Threshold is Reasonable

Pharmaceutical pricing naturally has high-cost outliers:

1. **Specialty or high-cost drugs:** very expensive drugs (for example biologics or oncology products) can legitimately produce high cost values. Review flagged rows against the actual drug and claim counts rather than assuming they are errors.
2. **Clinical variation:** Different patient populations drive different cost distributions
3. **Real data:** High costs reflect legitimate healthcare economics, not data errors

The 2× multiplier catches extreme cases while allowing legitimate high-cost therapies to pass silently.

## Manual Review

To inspect the top outliers and categorize them:

```bash
dbt run-operation execute_sql --sql "SELECT * FROM ({{ ref('top_cost_outliers') }}) LIMIT 20"
```

Or query the analysis directly:
```sql
SELECT rank, prescriber_id, provider_state, drug_brand_name, drug_cost_usd, multiple_of_p99, review_flag
FROM <dbt_compiled_analysis>/top_cost_outliers.sql
WHERE outlier_category = 'EXTREME (>5x p99)'
ORDER BY drug_cost_usd DESC;
```

The analysis includes a `review_flag` column that suggests:
- `LIKELY_SPECIALTY` — Matches known specialty drug keywords (oncology, biologic, immunosuppressant)
- `POTENTIALLY_RARE_DRUG` — Very high cost with few claims (rare/niche drugs)
- `VERIFY` — Requires manual review

## When to Investigate

Investigate outliers if:
- A non-specialty drug appears with unexpectedly high cost
- Cost is >5× the 99th percentile AND claim count is low (possible data error)
- A prescriber's average cost is much higher than peers in the same state/type

## When to Ignore

Safe to ignore:
- Specialty drugs matching expected categories (oncology, biologics, etc.)
- Legitimate high-cost drugs with normal claim counts
- Regional/clinical variation in prescribing patterns

## Test Severity

This test has `severity='warn'`, meaning:
- ✅ Does not block `dbt build`
- ✅ Appears in test output summary
- ✅ Alerts you to review manually
- ✅ Useful for trend monitoring across runs
