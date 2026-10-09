{{
  config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['prescriber_id', 'provider_state', 'prescriber_type', 'source_loaded_at'],
    tags=['marts', 'incremental', 'snapshot'],
    description='Incremental snapshot table: per-prescriber aggregates at each data load batch'
  )
}}

SELECT
    prescriber_id,
    provider_org_name,
    provider_first_name,
    provider_state,
    prescriber_type,
    COUNT(DISTINCT drug_brand_name) AS unique_drugs_prescribed,
    SUM(claim_count) AS total_claims,
    SUM(drug_cost_usd) AS total_cost_usd,
    AVG(drug_cost_usd) AS avg_drug_cost_usd,
    source_loaded_at,
    CURRENT_TIMESTAMP() AS dbt_updated_at

FROM {{ ref('stg_prescriber_claims') }}

{% if is_incremental() %}
WHERE source_loaded_at > (SELECT MAX(source_loaded_at) FROM {{ this }})
{% endif %}

GROUP BY 1, 2, 3, 4, 5, 10
