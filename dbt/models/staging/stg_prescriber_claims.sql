{{
  config(
    materialized='view',
    tags=['staging', 'daily'],
    description='Cleaned prescriber claims from raw CMS data'
  )
}}

SELECT
    CAST(PRSCRBR_NPI AS INTEGER) AS prescriber_id,
    PRSCRBR_LAST_ORG_NAME AS provider_org_name,
    PRSCRBR_FIRST_NAME AS provider_first_name,
    PRSCRBR_CITY AS provider_city,
    PRSCRBR_STATE_ABRVTN AS provider_state,
    PRSCRBR_TYPE AS prescriber_type,
    BRND_NAME AS drug_brand_name,
    GNRC_NAME AS drug_generic_name,
    CAST(TOT_CLMS AS INTEGER) AS claim_count,
    CAST(TOT_30DAY_FILLS AS INTEGER) AS fills_30_day,
    CAST(TOT_DAY_SUPLY AS INTEGER) AS day_supply,
    CAST(TOT_DRUG_CST AS DECIMAL(12, 2)) AS drug_cost_usd,
    TRY_CAST(TOT_BENES AS INTEGER) AS beneficiary_count,  -- NULL if CMS suppressed (<11)
    LOADED_AT AS source_loaded_at,
    CURRENT_TIMESTAMP() AS dbt_inserted_at
FROM {{ source('raw', 'prescriber_claims') }}
WHERE PRSCRBR_NPI IS NOT NULL
    AND PRSCRBR_STATE_ABRVTN IS NOT NULL
    AND BRND_NAME IS NOT NULL
    AND CAST(TOT_CLMS AS INTEGER) > 0
