-- Analysis: Quantify cost loss at each filtering step
-- Purpose: Find where $1.034B in costs are being dropped between raw and staging

WITH raw_base AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(CAST(TOT_DRUG_CST AS DECIMAL(15, 2))) AS total_cost,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_prescribers,
        COUNT(DISTINCT PRSCRBR_STATE_ABRVTN) AS unique_states
    FROM {{ source('raw', 'prescriber_claims') }}
),

filter_npi_null AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(CAST(TOT_DRUG_CST AS DECIMAL(15, 2))) AS total_cost,
        COUNT(DISTINCT PRSCRBR_NPI) AS unique_prescribers
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NULL
),

filter_state_null AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(CAST(TOT_DRUG_CST AS DECIMAL(15, 2))) AS total_cost
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NULL
),

filter_drug_null AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(CAST(TOT_DRUG_CST AS DECIMAL(15, 2))) AS total_cost
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NOT NULL
        AND BRND_NAME IS NULL
),

filter_claims_zero AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(CAST(TOT_DRUG_CST AS DECIMAL(15, 2))) AS total_cost
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NOT NULL
        AND BRND_NAME IS NOT NULL
        AND CAST(TOT_CLMS AS INTEGER) <= 0
),

filter_cost_null AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(CAST(TOT_DRUG_CST AS DECIMAL(15, 2))) AS total_cost
    FROM {{ source('raw', 'prescriber_claims') }}
    WHERE PRSCRBR_NPI IS NOT NULL
        AND PRSCRBR_STATE_ABRVTN IS NOT NULL
        AND BRND_NAME IS NOT NULL
        AND CAST(TOT_CLMS AS INTEGER) > 0
        AND (TOT_DRUG_CST IS NULL OR CAST(TOT_DRUG_CST AS DECIMAL(15, 2)) = 0)
),

staging_final AS (
    SELECT
        COUNT(*) AS row_count,
        SUM(drug_cost_usd) AS total_cost
    FROM {{ ref('stg_prescriber_claims') }}
)

SELECT
    'RAW (total)' AS filter_step,
    raw_base.row_count,
    raw_base.total_cost,
    NULL::DECIMAL AS cost_dropped,
    NULL::INT AS rows_dropped,
    raw_base.unique_prescribers,
    raw_base.unique_states
FROM raw_base

UNION ALL

SELECT
    'Dropped: PRSCRBR_NPI IS NULL',
    filter_npi_null.row_count,
    filter_npi_null.total_cost,
    ROUND(raw_base.total_cost - filter_npi_null.total_cost, 2),
    raw_base.row_count - filter_npi_null.row_count,
    filter_npi_null.unique_prescribers,
    NULL
FROM filter_npi_null, raw_base

UNION ALL

SELECT
    'Dropped: PRSCRBR_STATE_ABRVTN IS NULL',
    filter_state_null.row_count,
    filter_state_null.total_cost,
    filter_state_null.total_cost,
    filter_state_null.row_count,
    NULL,
    NULL
FROM filter_state_null

UNION ALL

SELECT
    'Dropped: BRND_NAME IS NULL',
    filter_drug_null.row_count,
    filter_drug_null.total_cost,
    filter_drug_null.total_cost,
    filter_drug_null.row_count,
    NULL,
    NULL
FROM filter_drug_null

UNION ALL

SELECT
    'Dropped: TOT_CLMS <= 0',
    filter_claims_zero.row_count,
    filter_claims_zero.total_cost,
    filter_claims_zero.total_cost,
    filter_claims_zero.row_count,
    NULL,
    NULL
FROM filter_claims_zero

UNION ALL

SELECT
    'Dropped: TOT_DRUG_CST NULL or zero',
    filter_cost_null.row_count,
    filter_cost_null.total_cost,
    filter_cost_null.total_cost,
    filter_cost_null.row_count,
    NULL,
    NULL
FROM filter_cost_null

UNION ALL

SELECT
    'STAGING (final)',
    staging_final.row_count,
    staging_final.total_cost,
    raw_base.total_cost - staging_final.total_cost,
    NULL,
    NULL,
    NULL
FROM staging_final, raw_base
