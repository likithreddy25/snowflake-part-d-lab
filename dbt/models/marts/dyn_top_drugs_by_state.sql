{{
  config(
    materialized='dynamic_table',
    tags=['marts', 'dynamic', 'high_impact'],
    description='Dynamic Table: Top 50 drugs by cost per state (auto-refreshing every 60 min)',
    refresh_mode='AUTO',
    snowflake_warehouse='WH_PARTD',
    target_lag='60 minutes',
    on_configuration_change='apply'
  )
}}

-- Dynamic Tables automatically refresh based on their upstream dependencies.
-- This table refreshes every 60 minutes or when upstream data changes (whichever is more frequent).
-- Use Dynamic Tables for metrics that need to stay fresh without manual scheduling.

WITH ranked_drugs AS (
    SELECT
        provider_state,
        drug_brand_name,
        drug_generic_name,
        COUNT(DISTINCT prescriber_id) AS prescriber_count,
        SUM(claim_count) AS total_claims,
        SUM(drug_cost_usd) AS total_cost_usd,
        ROUND(SUM(drug_cost_usd) / NULLIF(SUM(claim_count), 0), 2) AS avg_cost_per_claim,
        ROW_NUMBER() OVER (PARTITION BY provider_state ORDER BY SUM(drug_cost_usd) DESC) AS rank_by_state
    FROM {{ ref('stg_prescriber_claims') }}
    GROUP BY 1, 2, 3
)

SELECT
    provider_state,
    rank_by_state AS rank,
    drug_brand_name,
    drug_generic_name,
    prescriber_count,
    total_claims,
    total_cost_usd,
    avg_cost_per_claim,
    CURRENT_TIMESTAMP() AS refresh_timestamp
FROM ranked_drugs
WHERE rank_by_state <= 50
ORDER BY provider_state, rank

-- Why Dynamic Table?
-- Metrics like "top drugs by state" change frequently as new claims are loaded.
-- A Dynamic Table keeps this mart in sync automatically without needing scheduled tasks,
-- ensuring analysts always see current data when they query it.
-- Cost: minimal, as Snowflake only refreshes when upstream data actually changes.
