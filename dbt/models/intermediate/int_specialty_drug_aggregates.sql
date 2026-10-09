{{
  config(
    materialized='view',
    tags=['intermediate', 'daily'],
    description='Aggregate claims by prescriber type and drug'
  )
}}

SELECT
    prescriber_type,
    drug_brand_name,
    drug_generic_name,
    COUNT(DISTINCT prescriber_id) AS prescriber_count,
    SUM(claim_count) AS total_claims,
    SUM(fills_30_day) AS total_fills,
    SUM(day_supply) AS total_day_supply,
    SUM(drug_cost_usd) AS total_cost_usd,
    AVG(drug_cost_usd) AS avg_cost_per_prescriber_usd,
    MIN(drug_cost_usd) AS min_cost_usd,
    MAX(drug_cost_usd) AS max_cost_usd
FROM {{ ref('stg_prescriber_claims') }}
GROUP BY 1, 2, 3
