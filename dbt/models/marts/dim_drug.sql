{{
  config(
    materialized='table',
    tags=['marts', 'dimension'],
    description='Drug dimension. Grain: one row per (brand name, generic name).'
  )
}}

SELECT DISTINCT
    MD5(CONCAT_WS('|', COALESCE(drug_brand_name, ''), COALESCE(drug_generic_name, ''))) AS drug_key,
    drug_brand_name,
    drug_generic_name
FROM {{ ref('stg_prescriber_claims') }}
