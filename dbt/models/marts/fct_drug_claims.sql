{{
  config(
    materialized='table',
    tags=['marts', 'fact', 'core'],
    description='Claim-level fact table. Grain: one row per (prescriber_key, drug_key).'
  )
}}

-- Keys only plus measures. Descriptive attributes live in dim_prescriber and dim_drug.
SELECT
    MD5(CONCAT_WS('|', CAST(prescriber_id AS VARCHAR), provider_state)) AS prescriber_key,
    MD5(CONCAT_WS('|', COALESCE(drug_brand_name, ''), COALESCE(drug_generic_name, ''))) AS drug_key,
    claim_count,
    fills_30_day,
    day_supply,
    drug_cost_usd,
    beneficiary_count,        -- NULL when CMS suppressed (<11 beneficiaries)
    source_loaded_at
FROM {{ ref('stg_prescriber_claims') }}
