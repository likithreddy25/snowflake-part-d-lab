-- Singular test: verify grain of raw prescriber claims table
-- Each row should be unique by (PRSCRBR_NPI, PRSCRBR_STATE_ABRVTN, BRND_NAME, GNRC_NAME)

SELECT
  PRSCRBR_NPI,
  PRSCRBR_STATE_ABRVTN,
  BRND_NAME,
  GNRC_NAME,
  COUNT(*) AS row_count
FROM {{ source('raw', 'prescriber_claims') }}
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1
