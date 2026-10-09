-- Test: verify no duplicate prescriber-state-drug combinations in staging
-- Grain: one row per (prescriber_id, provider_state, drug_brand_name, drug_generic_name)

SELECT
    prescriber_id,
    provider_state,
    drug_brand_name,
    drug_generic_name,
    COUNT(*) AS row_count
FROM {{ ref('stg_prescriber_claims') }}
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1
