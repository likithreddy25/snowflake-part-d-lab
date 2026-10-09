{{
  config(
    materialized='table',
    tags=['marts', 'daily', 'high_impact'],
    description='Top 100 drugs by total cost'
  )
}}

SELECT
    ROW_NUMBER() OVER (ORDER BY total_cost_usd DESC) AS rank,
    drug_brand_name,
    drug_generic_name,
    prescriber_count,
    total_claims,
    total_cost_usd,
    ROUND(total_cost_usd / NULLIF(prescriber_count, 0), 2) AS avg_cost_per_prescriber,
    ROUND(total_cost_usd / NULLIF(total_claims, 0), 2) AS avg_cost_per_claim,
    CURRENT_TIMESTAMP() AS snapshot_date
FROM (
    SELECT
        drug_brand_name,
        drug_generic_name,
        COUNT(DISTINCT prescriber_id) AS prescriber_count,
        SUM(claim_count) AS total_claims,
        SUM(drug_cost_usd) AS total_cost_usd
    FROM {{ ref('stg_prescriber_claims') }}
    GROUP BY 1, 2
)
QUALIFY ROW_NUMBER() OVER (ORDER BY total_cost_usd DESC) <= 100
