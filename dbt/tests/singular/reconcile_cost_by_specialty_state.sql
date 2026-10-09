-- Reconciliation test: verify fct_cost_by_specialty_state totals match staging
-- Fails if the aggregated cost differs by more than $0.01 (tolerance for floating-point rounding)
-- Returns empty result if totals match, single row if they diverge

WITH staging AS (
    SELECT SUM(drug_cost_usd) AS total_cost
    FROM {{ ref('stg_prescriber_claims') }}
),
mart AS (
    SELECT SUM(total_cost_usd) AS total_cost
    FROM {{ ref('fct_cost_by_specialty_state') }}
)
SELECT
    staging.total_cost AS staging_total,
    mart.total_cost AS mart_total,
    staging.total_cost - mart.total_cost AS difference
FROM staging CROSS JOIN mart
WHERE ABS(staging.total_cost - mart.total_cost) > 0.01
