{{
  config(
    materialized='view',
    tags=['intermediate', 'daily'],
    description='Aggregate claims by state and drug'
  )
}}

SELECT
    provider_state,
    drug_brand_name,
    drug_generic_name,
    COUNT(DISTINCT prescriber_id) AS prescriber_count,
    SUM(claim_count) AS total_claims,
    SUM(drug_cost_usd) AS total_cost_usd
FROM {{ ref('stg_prescriber_claims') }}
GROUP BY 1, 2, 3
