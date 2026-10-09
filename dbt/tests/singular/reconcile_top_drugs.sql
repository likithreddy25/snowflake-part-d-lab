-- Reconciliation test: verify fct_top_drugs_by_cost matches top-100 drugs subset
-- fct_top_drugs_by_cost is intentionally limited to the 100 highest-cost drugs
-- This test compares the mart against the same top-100 subset (not all staging data)
-- Fails if cost differs by more than $0.01 within that subset
-- Returns empty result if totals match, single row if they diverge

WITH top_100_drugs_from_staging AS (
    SELECT
        drug_brand_name,
        drug_generic_name,
        SUM(drug_cost_usd) AS drug_total_cost
    FROM {{ ref('stg_prescriber_claims') }}
    GROUP BY 1, 2
    ORDER BY SUM(drug_cost_usd) DESC
    LIMIT 100
),
top_100_staging_total AS (
    SELECT SUM(drug_total_cost) AS total_cost
    FROM top_100_drugs_from_staging
),
mart_total AS (
    SELECT SUM(total_cost_usd) AS total_cost
    FROM {{ ref('fct_top_drugs_by_cost') }}
)
SELECT
    staging.total_cost AS top_100_staging_total,
    mart.total_cost AS mart_total,
    staging.total_cost - mart.total_cost AS difference
FROM top_100_staging_total staging CROSS JOIN mart_total mart
WHERE ABS(staging.total_cost - mart.total_cost) > 0.01
