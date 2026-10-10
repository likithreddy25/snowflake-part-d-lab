-- Grain check: one row per (prescriber_key, drug_key).
SELECT prescriber_key, drug_key, COUNT(*) AS row_count
FROM {{ ref('fct_drug_claims') }}
GROUP BY 1, 2
HAVING COUNT(*) > 1
