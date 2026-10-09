-- Validation test: brand vs generic percentages should sum to ~100% per prescriber type
-- Allowing small tolerance for rounding

SELECT
    prescriber_type,
    ROUND(SUM(pct_of_claims), 1) AS total_pct,
    CASE
        WHEN ROUND(SUM(pct_of_claims), 1) NOT BETWEEN 99.0 AND 101.0
        THEN prescriber_type
        ELSE NULL
    END AS prescriber_type_with_issue
FROM {{ ref('fct_brand_vs_generic_share') }}
GROUP BY 1
HAVING ROUND(SUM(pct_of_claims), 1) NOT BETWEEN 99.0 AND 101.0
