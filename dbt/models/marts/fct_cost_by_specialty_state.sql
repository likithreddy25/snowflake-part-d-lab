{{
  config(
    materialized='table',
    tags=['marts', 'daily', 'core'],
    description='Fact table: cost aggregated by specialty and state'
  )
}}

SELECT
    prescriber_type,
    provider_state,
    COUNT(DISTINCT prescriber_id) AS prescriber_count,
    SUM(claim_count) AS total_claims,
    SUM(drug_cost_usd) AS total_cost_usd,
    ROUND(SUM(drug_cost_usd) / NULLIF(COUNT(DISTINCT prescriber_id), 0), 2) AS cost_per_prescriber,
    COUNT(DISTINCT drug_brand_name) AS unique_drugs,
    CURRENT_TIMESTAMP() AS created_at
FROM {{ ref('stg_prescriber_claims') }}
GROUP BY 1, 2
