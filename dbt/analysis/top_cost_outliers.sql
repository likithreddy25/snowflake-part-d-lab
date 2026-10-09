-- Analysis: Top cost outliers for manual review
-- Purpose: Identify unusually high drug costs (>2x 99th percentile) to distinguish
--          legitimate high-cost specialty drugs from potential data errors
-- Usage: dbt run-operation analyze_top_cost_outliers or manually query results

WITH cost_stats AS (
    SELECT
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY drug_cost_usd) OVER () AS p99_cost,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY drug_cost_usd) OVER () AS p95_cost,
        AVG(drug_cost_usd) AS avg_cost,
        MAX(drug_cost_usd) AS max_cost
    FROM {{ ref('stg_prescriber_claims') }}
),

outliers AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY drug_cost_usd DESC) AS rank,
        prescriber_id,
        provider_state,
        prescriber_type,
        drug_brand_name,
        drug_generic_name,
        claim_count,
        drug_cost_usd,
        cost_stats.p99_cost,
        cost_stats.p95_cost,
        ROUND(drug_cost_usd / cost_stats.p99_cost, 2) AS multiple_of_p99,
        CASE
            WHEN drug_cost_usd > cost_stats.p99_cost * 5 THEN 'EXTREME (>5x p99)'
            WHEN drug_cost_usd > cost_stats.p99_cost * 2 THEN 'HIGH (>2x p99)'
            ELSE 'ELEVATED'
        END AS outlier_category
    FROM {{ ref('stg_prescriber_claims') }}, cost_stats
    WHERE drug_cost_usd > cost_stats.p99_cost
)

SELECT
    rank,
    prescriber_id,
    provider_state,
    prescriber_type,
    drug_brand_name,
    drug_generic_name,
    claim_count,
    drug_cost_usd,
    multiple_of_p99,
    outlier_category,
    CASE
        WHEN drug_brand_name ILIKE '%oncolog%' OR drug_brand_name ILIKE '%immunosuppressant%'
             OR drug_brand_name ILIKE '%biologic%' OR drug_brand_name ILIKE '%insulin%'
             OR drug_brand_name ILIKE '%monoclonal%' OR drug_generic_name ILIKE '%biologic%'
        THEN 'LIKELY_SPECIALTY'
        WHEN drug_cost_usd > 50000 AND claim_count <= 5
        THEN 'POTENTIALLY_RARE_DRUG'
        ELSE 'VERIFY'
    END AS review_flag
FROM outliers
ORDER BY drug_cost_usd DESC
