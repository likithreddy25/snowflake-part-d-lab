-- Reconciliation: the star-schema fact table must carry exactly the staging totals.
-- Returns a row only when row count, claims or cost differ (cost tolerance $0.01).
WITH staging AS (
    SELECT COUNT(*) AS n_rows, SUM(claim_count) AS claims, SUM(drug_cost_usd) AS cost
    FROM {{ ref('stg_prescriber_claims') }}
),
fact AS (
    SELECT COUNT(*) AS n_rows, SUM(claim_count) AS claims, SUM(drug_cost_usd) AS cost
    FROM {{ ref('fct_drug_claims') }}
)
SELECT staging.n_rows AS staging_rows, fact.n_rows AS fact_rows,
       staging.claims AS staging_claims, fact.claims AS fact_claims,
       staging.cost AS staging_cost, fact.cost AS fact_cost
FROM staging CROSS JOIN fact
WHERE staging.n_rows != fact.n_rows
   OR staging.claims != fact.claims
   OR ABS(staging.cost - fact.cost) > 0.01
