{{ config(severity='warn') }}

-- Outlier detection: monitoring signal for unusually high drug costs
-- Identifies costs >2x the 99th percentile (legitimate high-cost drugs like oncology, biologics)
-- Status: WARN severity (monitoring, not a gate)

WITH cost_stats AS (
    SELECT
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY drug_cost_usd) OVER () AS p99_cost
    FROM {{ ref('stg_prescriber_claims') }}
)

SELECT
    prescriber_id,
    provider_state,
    prescriber_type,
    drug_brand_name,
    drug_cost_usd,
    cost_stats.p99_cost,
    ROUND(drug_cost_usd / cost_stats.p99_cost, 2) AS multiple_of_p99
FROM {{ ref('stg_prescriber_claims') }}, cost_stats
WHERE drug_cost_usd > cost_stats.p99_cost * 2
LIMIT 100  -- Show top 100 outliers
