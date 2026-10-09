-- Analysis: Verify reconciliation for fct_top_drugs_by_cost
-- Purpose: Check if top 100 drugs capture expected portion of total cost

WITH staging_totals AS (
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT drug_brand_name) AS total_unique_drugs,
        SUM(drug_cost_usd) AS total_cost
    FROM {{ ref('stg_prescriber_claims') }}
),

top_100_drugs AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY SUM(drug_cost_usd) DESC) AS rank,
        drug_brand_name,
        drug_generic_name,
        SUM(drug_cost_usd) AS drug_total_cost,
        COUNT(DISTINCT prescriber_id) AS prescriber_count,
        SUM(claim_count) AS total_claims
    FROM {{ ref('stg_prescriber_claims') }}
    GROUP BY 1, 2
    ORDER BY SUM(drug_cost_usd) DESC
    LIMIT 100
),

top_100_totals AS (
    SELECT
        COUNT(*) AS top_100_drug_count,
        SUM(drug_total_cost) AS top_100_cost
    FROM top_100_drugs
)

SELECT
    staging_totals.total_rows,
    staging_totals.total_unique_drugs,
    staging_totals.total_cost AS staging_total_cost,
    top_100_totals.top_100_drug_count,
    top_100_totals.top_100_cost,
    ROUND(100.0 * top_100_totals.top_100_cost / staging_totals.total_cost, 2) AS pct_of_total_cost,
    ROUND(staging_totals.total_cost - top_100_totals.top_100_cost, 2) AS remaining_cost_in_other_drugs
FROM staging_totals, top_100_totals
