# Governance & Access Control

## Overview

This document describes the governance model for the Part D Analytics Lab, including dynamic masking policies, row access policies, and sensitive column tagging.

## Access Control Model

### Roles

| Role | Purpose | Permissions |
|------|---------|-------------|
| `PARTD_ENGINEER` | Data engineering and dbt pipeline development | Read/write all schemas (RAW, STAGING, MARTS, GOVERNANCE) |
| `PARTD_ANALYST` | Analytics and reporting | Read-only access to MARTS schema |

### Warehouse Access

Both roles have usage privileges on `WH_PARTD` (X-SMALL, auto-suspend=60 sec).

---

## Dynamic Masking Policies

All masking policies are enforced at query time. Data is physically unmasked in the database but hidden from users based on their role.

### Policy: `MASK_PROVIDER_NAME`

**Applies to:** `PROVIDER_FIRST_NAME`, `PROVIDER_LAST_NAME`

| Role | Sees | Reason |
|------|------|--------|
| `PARTD_ENGINEER`, `ACCOUNTADMIN` | Actual name | Full data access for pipeline work |
| `PARTD_ANALYST` | `***MASKED***` | Analyst does not need prescriber identities |

**Example Query:**
```sql
USE ROLE PARTD_ENGINEER;
SELECT NPI, PROVIDER_LAST_NAME FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS LIMIT 1;
-- Output: 1234567890 | Smith

USE ROLE PARTD_ANALYST;
SELECT NPI, PROVIDER_LAST_NAME FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS LIMIT 1;
-- Output: NPI*** | ***MASKED***
```

### Policy: `MASK_NPI`

**Applies to:** `NPI` (National Provider Identifier)

| Role | Sees | Reason |
|------|------|--------|
| `PARTD_ENGINEER`, `ACCOUNTADMIN` | Full NPI (e.g., `1234567890`) | Engineering access |
| `PARTD_ANALYST` | Partial NPI (e.g., `NPI***`) | Anonymized for security |

---

## Row Access Policies (RAP)

### Policy: `RAP_STATE_FILTER`

**Applies to:** `PROVIDER_STATE` column

**Current Implementation:** All roles see all states.

**Future Enhancement:** Can restrict ANALYST roles to specific states (e.g., `PARTD_ANALYST_CA` sees only CA data).

Example future setup:
```sql
-- After creating PARTD_ANALYST_CA role:
ALTER ROW ACCESS POLICY RAP_STATE_FILTER
SET (WHEN CURRENT_ROLE() = 'PARTD_ANALYST_CA' THEN PROVIDER_STATE = 'CA')
```

---

## Column Tagging

Sensitive columns are tagged for audit and governance tracking:

| Column | Tags | Reason |
|--------|------|--------|
| `NPI` | `TAG_PII`, `TAG_SENSITIVE` | Provider identifier |
| `PROVIDER_LAST_NAME` | `TAG_PII` | Personal information |
| `PROVIDER_FIRST_NAME` | `TAG_PII` | Personal information |
| `TOTAL_DRUG_COST` | `TAG_FINANCIAL` | Financial data |

**Query to find tagged columns:**
```sql
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
WHERE OBJECT_NAME IN ('NPI', 'PROVIDER_LAST_NAME', 'PROVIDER_FIRST_NAME');
```

---

## Audit Trail

All queries touching masked or tagged columns are logged in:

```sql
SELECT * FROM PARTD_LAB.GOVERNANCE.V_RECENT_SENSITIVE_QUERIES
ORDER BY EXECUTION_TIME DESC;
```

This view shows:
- Query ID
- User name
- Execution time
- Query text
- Warehouse

---

## Testing Masking & Access

### Verify Masking as ENGINEER

```sql
USE ROLE PARTD_ENGINEER;
SELECT
    NPI,
    PROVIDER_LAST_NAME,
    PROVIDER_FIRST_NAME,
    PROVIDER_STATE,
    DRUG_NAME,
    TOTAL_DRUG_COST
FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS
LIMIT 5;
```

**Expected:** All columns visible.

### Verify Masking as ANALYST

```sql
USE ROLE PARTD_ANALYST;
SELECT
    NPI,
    PROVIDER_LAST_NAME,
    PROVIDER_FIRST_NAME,
    PROVIDER_STATE,
    DRUG_NAME,
    TOTAL_DRUG_COST
FROM PARTD_LAB.RAW.PRESCRIBER_CLAIMS
LIMIT 5;
```

**Expected:** NPI shows `NPI***`, names show `***MASKED***`, other columns visible.

---

## Data Classification

The dataset contains **aggregated, non-PHI public data** from CMS:

- **Public Use File Source:** data.cms.gov Medicare Part D Prescribers by Provider and Drug
- **Data Level:** Aggregate (totals across many patients, not individual patient records)
- **Sensitive Elements:**
  - NPI (prescriber identifier, but in public aggregate context)
  - Provider name (public information, but masked for data minimization)
  - Cost data (business sensitive, tagged for audit)

- **NOT HIPAA-Protected:** This is aggregate reporting data, not EHR/patient-level PHI.

---

## Cost Control via Governance

Masking and RAP policies have **zero performance impact** (enforced at result-set layer).

However, they enable cost tracking:

- Tag sensitive queries for audit
- Monitor sensitive column access via `ACCOUNT_USAGE.QUERY_HISTORY`
- Restrict analyst access to specific datasets to reduce unnecessary compute

---

## Future Enhancements

1. **Conditional Role:** Create `PARTD_ANALYST_STATE_X` roles with state-based RAP
2. **Temporal Masking:** Mask NPI for analysts outside of specific time windows
3. **Query Tagging:** Automatically tag queries that touch masked columns for audit
4. **Alerts:** Alert when sensitive columns are exported to external tools

---

## References

- Snowflake Docs: [Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm.html)
- Snowflake Docs: [Row Access Policies](https://docs.snowflake.com/en/user-guide/security-row-level-security.html)
- Snowflake Docs: [Object Tagging](https://docs.snowflake.com/en/user-guide/object-tagging.html)
- CMS Data: [Medicare Part D Prescriber Public Use File](https://data.cms.gov/)
