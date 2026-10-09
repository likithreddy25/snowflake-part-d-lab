# Part D Analytics Metrics

This document describes key metrics tracked in the Part D analytics warehouse. These are analytical metrics defined for documentation and BI tools, not dbt Semantic Layer metrics (which require a separate semantic model definition).

## Supported Metrics

### total_prescriber_count
- **Definition:** Total number of unique prescribers in dataset
- **Grain:** National (aggregated across all states, specialties, drugs)
- **Source Model:** `stg_prescriber_claims`
- **SQL:** `COUNT(DISTINCT prescriber_id)`
- **Use Case:** Overall prescriber population size

### total_claims_nationwide
- **Definition:** Total claims across all prescribers and drugs
- **Grain:** National
- **Source Model:** `stg_prescriber_claims`
- **SQL:** `SUM(claim_count)`
- **Use Case:** Total prescription volume

### total_drug_spend
- **Definition:** Total nationwide drug spend in USD
- **Grain:** National
- **Source Model:** `stg_prescriber_claims`
- **SQL:** `SUM(drug_cost_usd)`
- **Use Case:** Total spending analysis, cost trends

### avg_cost_per_claim
- **Definition:** Average cost per claim across all prescribers
- **Grain:** National
- **Source Model:** `stg_prescriber_claims`
- **SQL:** `SUM(drug_cost_usd) / SUM(claim_count)`
- **Use Case:** Cost efficiency analysis

## Using These Metrics

For BI tools (Tableau, Looker, etc.), write SQL queries directly against the marts:
```sql
SELECT 
  prescriber_state,
  COUNT(DISTINCT prescriber_id) as unique_prescribers,
  SUM(claim_count) as total_claims,
  SUM(drug_cost_usd) as total_cost,
  SUM(drug_cost_usd) / SUM(claim_count) as avg_cost_per_claim
FROM partd_lab.marts.fct_cost_by_specialty_state
GROUP BY 1
```

Note: Rows with NULL beneficiary counts (CMS suppression for <11 beneficiaries) should be excluded from beneficiary-related metrics:
```sql
WHERE beneficiary_count IS NOT NULL
```
