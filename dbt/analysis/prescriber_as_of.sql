-- Point-in-time lookup against the SCD2 snapshot.
-- Which attributes did each prescriber have on a given date?
-- Replace the date literal. Rows with dbt_valid_to IS NULL are the current version.
SELECT
    prescriber_key,
    prescriber_id,
    provider_state,
    provider_org_name,
    provider_city,
    prescriber_type,
    dbt_valid_from,
    dbt_valid_to
FROM {{ ref('snap_prescriber') }}
WHERE dbt_valid_from <= '2026-10-01'::timestamp
  AND (dbt_valid_to IS NULL OR dbt_valid_to > '2026-10-01'::timestamp)
