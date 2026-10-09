{{
  config(
    materialized='table',
    tags=['marts', 'daily', 'clinical_monitoring'],
    description='Opioid prescribing metrics by specialty for clinical monitoring'
  )
}}

WITH opioid_classification AS (
    SELECT
        prescriber_type,
        prescriber_id,
        drug_brand_name,
        claim_count,
        drug_cost_usd,
        CASE
            WHEN drug_brand_name ILIKE '%Morphine%'
                OR drug_brand_name ILIKE '%Codeine%'
                OR drug_brand_name ILIKE '%Oxycodone%'
                OR drug_brand_name ILIKE '%Hydrocodone%'
                OR drug_brand_name ILIKE '%Tramadol%'
                OR drug_brand_name ILIKE '%Fentanyl%'
                OR drug_brand_name ILIKE '%Methadone%'
            THEN 'Opioid'
            ELSE 'Non-Opioid'
        END AS drug_class
    FROM {{ ref('stg_prescriber_claims') }}
)

SELECT
    prescriber_type,
    drug_class,
    COUNT(DISTINCT prescriber_id) AS prescriber_count,
    SUM(claim_count) AS total_claims,
    ROUND(100.0 * SUM(claim_count) / SUM(SUM(claim_count)) OVER (PARTITION BY prescriber_type), 2) AS pct_of_claims,
    SUM(drug_cost_usd) AS total_cost_usd,
    ROUND(100.0 * SUM(drug_cost_usd) / SUM(SUM(drug_cost_usd)) OVER (PARTITION BY prescriber_type), 2) AS pct_of_cost
FROM opioid_classification
GROUP BY 1, 2
ORDER BY prescriber_type, drug_class
