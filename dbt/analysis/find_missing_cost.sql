-- Analysis: Comprehensive cost reconciliation to find the $1.034B gap
-- This single query shows cost at each step: raw → staging → mart

WITH step_0_raw_all AS (
    SELECT
        'STEP_0_RAW_ALL' AS step_name,
        COUNT(*) AS row_count,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_npis,
        COUNT(DISTINCT PRSCRBR_STATE_ABRVTN) AS unique_states,
        ROUND(SUM(TRY_CAST(TOT_DRUG_CST AS DECIMAL(15,2))), 2) AS total_cost_usd
    FROM {{ source('raw', 'prescriber_claims') }}
),

step_1_npi_not_null AS (
    SELECT
        'STEP_1_NPI_NOT_NULL' AS step_name,
        COUNT(*) AS row_count,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_npis,
        COUNT(DISTINCT PRSCRBR_STATE_ABRVTN) AS unique_states,
        ROUND(SUM(TRY_CAST(TOT_DRUG_CST AS DECIMAL(15,2))), 2) AS total_cost_usd
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
),

step_2_state_not_null AS (
    SELECT
        'STEP_2_STATE_NOT_NULL' AS step_name,
        COUNT(*) AS row_count,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_npis,
        COUNT(DISTINCT PRSCRBR_STATE_ABRVTN) AS unique_states,
        ROUND(SUM(TRY_CAST(TOT_DRUG_CST AS DECIMAL(15,2))), 2) AS total_cost_usd
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NOT NULL
),

step_3_drug_not_null AS (
    SELECT
        'STEP_3_DRUG_NOT_NULL' AS step_name,
        COUNT(*) AS row_count,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_npis,
        COUNT(DISTINCT PRSCRBR_STATE_ABRVTN) AS unique_states,
        ROUND(SUM(TRY_CAST(TOT_DRUG_CST AS DECIMAL(15,2))), 2) AS total_cost_usd
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NOT NULL
        AND BRND_NAME IS NOT NULL
),

step_4_claims_gt_zero AS (
    SELECT
        'STEP_4_CLAIMS_GT_ZERO' AS step_name,
        COUNT(*) AS row_count,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_npis,
        COUNT(DISTINCT PRSCRBR_STATE_ABRVTN) AS unique_states,
        ROUND(SUM(TRY_CAST(TOT_DRUG_CST AS DECIMAL(15,2))), 2) AS total_cost_usd
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NOT NULL
        AND BRND_NAME IS NOT NULL
        AND CAST(TOT_CLMS AS INTEGER) > 0
),

step_5_staging_final AS (
    SELECT
        'STEP_5_STAGING_FINAL' AS step_name,
        COUNT(*) AS row_count,
        COUNT(DISTINCT prescriber_id) AS unique_npis,
        COUNT(DISTINCT provider_state) AS unique_states,
        ROUND(SUM(drug_cost_usd), 2) AS total_cost_usd
    FROM {{ ref('stg_prescriber_claims') }}
),

step_6_check_nulls_in_staging AS (
    SELECT
        'STEP_6_NULL_PRESCRIBER_TYPE' AS step_name,
        COUNT(*) AS row_count,
        NULL::INT AS unique_npis,
        NULL::INT AS unique_states,
        ROUND(SUM(drug_cost_usd), 2) AS total_cost_usd
    FROM {{ ref('stg_prescriber_claims') }}
    WHERE prescriber_type IS NULL
),

step_7_check_nulls_provider_state AS (
    SELECT
        'STEP_7_NULL_PROVIDER_STATE' AS step_name,
        COUNT(*) AS row_count,
        NULL::INT AS unique_npis,
        NULL::INT AS unique_states,
        ROUND(SUM(drug_cost_usd), 2) AS total_cost_usd
    FROM {{ ref('stg_prescriber_claims') }}
    WHERE provider_state IS NULL
),

step_8_mart_fct_cost_by_specialty_state AS (
    SELECT
        'STEP_8_MART_COST_BY_SPECIALTY_STATE' AS step_name,
        COUNT(*) AS row_count,
        NULL::INT AS unique_npis,
        NULL::INT AS unique_states,
        ROUND(SUM(total_cost_usd), 2) AS total_cost_usd
    FROM {{ ref('fct_cost_by_specialty_state') }}
),

step_9_mart_top_drugs AS (
    SELECT
        'STEP_9_MART_TOP_DRUGS' AS step_name,
        COUNT(*) AS row_count,
        NULL::INT AS unique_npis,
        NULL::INT AS unique_states,
        ROUND(SUM(total_cost_usd), 2) AS total_cost_usd
    FROM {{ ref('fct_top_drugs_by_cost') }}
)

SELECT * FROM step_0_raw_all
UNION ALL SELECT * FROM step_1_npi_not_null
UNION ALL SELECT * FROM step_2_state_not_null
UNION ALL SELECT * FROM step_3_drug_not_null
UNION ALL SELECT * FROM step_4_claims_gt_zero
UNION ALL SELECT * FROM step_5_staging_final
UNION ALL SELECT * FROM step_6_check_nulls_in_staging
UNION ALL SELECT * FROM step_7_check_nulls_provider_state
UNION ALL SELECT * FROM step_8_mart_fct_cost_by_specialty_state
UNION ALL SELECT * FROM step_9_mart_top_drugs
ORDER BY step_name
