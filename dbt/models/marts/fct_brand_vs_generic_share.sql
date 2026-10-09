{{
  config(
    materialized='table',
    tags=['marts', 'daily', 'market_analysis'],
    description='Brand vs generic market share by prescriber type'
  )
}}

WITH drug_classification AS (
    SELECT
        prescriber_type,
        CASE
            WHEN drug_brand_name = drug_generic_name OR drug_generic_name IS NULL
            THEN 'Generic'
            ELSE 'Brand'
        END AS drug_type,
        drug_brand_name,
        claim_count,
        drug_cost_usd
    FROM {{ ref('stg_prescriber_claims') }}
)

SELECT
    prescriber_type,
    drug_type,
    COUNT(DISTINCT drug_brand_name) AS unique_drugs,
    SUM(claim_count) AS total_claims,
    ROUND(100.0 * SUM(claim_count) / SUM(SUM(claim_count)) OVER (PARTITION BY prescriber_type), 2) AS pct_of_claims,
    SUM(drug_cost_usd) AS total_cost_usd,
    ROUND(100.0 * SUM(drug_cost_usd) / SUM(SUM(drug_cost_usd)) OVER (PARTITION BY prescriber_type), 2) AS pct_of_cost
FROM drug_classification
GROUP BY 1, 2
