{{
  config(
    materialized='table',
    tags=['marts', 'dimension'],
    description='Prescriber dimension. Grain: one row per (prescriber_id, provider_state).'
  )
}}

-- Surrogate key: hash of the natural key columns, so the fact table can join without
-- carrying descriptive attributes. MAX() picks one value per attribute if a prescriber's
-- descriptive columns differ between drug rows (a test below checks that this is stable).
SELECT
    MD5(CONCAT_WS('|', CAST(prescriber_id AS VARCHAR), provider_state)) AS prescriber_key,
    prescriber_id,
    provider_state,
    MAX(provider_org_name)   AS provider_org_name,
    MAX(provider_first_name) AS provider_first_name,
    MAX(provider_city)       AS provider_city,
    MAX(prescriber_type)     AS prescriber_type
FROM {{ ref('stg_prescriber_claims') }}
GROUP BY prescriber_id, provider_state
