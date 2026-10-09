-- ==============================================================================
-- Governance Setup: Dynamic masking, row access policies, and tags
-- ==============================================================================
-- Run as PARTD_ENGINEER to set up access controls and governance.
-- ==============================================================================

USE WAREHOUSE WH_PARTD;
USE DATABASE PARTD_LAB;
USE SCHEMA GOVERNANCE;

-- ============================================================================
-- 1. Dynamic Masking Policy: Hide provider names and NPI from PARTD_ANALYST
-- ============================================================================

-- Masking policy for provider names
CREATE OR REPLACE MASKING POLICY MASK_PROVIDER_NAME AS
    (val VARCHAR) RETURNS VARCHAR ->
    CASE
        WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN', 'PARTD_ENGINEER') THEN val
        ELSE '***MASKED***'
    END
COMMENT = 'Mask provider names; visible to ENGINEER only, masked for ANALYST'
;

-- Masking policy for NPI (prescriber identifier)
-- Note: In a real healthcare context, NPI might be considered sensitive.
-- Here it's in aggregate public data, but we mask it for demo governance.
CREATE OR REPLACE MASKING POLICY MASK_NPI AS
    (val NUMBER) RETURNS VARCHAR ->
    CASE
        WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN', 'PARTD_ENGINEER') THEN CAST(val AS VARCHAR)
        WHEN CURRENT_ROLE() = 'PARTD_ANALYST' THEN 'NPI***'
        ELSE NULL
    END
COMMENT = 'Mask NPI; visible to ENGINEER, hashed for ANALYST, null otherwise'
;

-- ============================================================================
-- 2. Row Access Policy: Filter by state for regional ANALYST roles
-- ============================================================================

CREATE OR REPLACE ROW ACCESS POLICY RAP_STATE_FILTER AS
    (state_col VARCHAR) RETURNS BOOLEAN ->
    CASE
        WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN', 'PARTD_ENGINEER') THEN TRUE
        -- Example: If you create a PARTD_ANALYST_CA role, they see only CA data
        -- WHEN CURRENT_ROLE() = 'PARTD_ANALYST_CA' THEN state_col = 'CA'
        -- For now, PARTD_ANALYST sees all states
        WHEN CURRENT_ROLE() = 'PARTD_ANALYST' THEN TRUE
        ELSE FALSE
    END
COMMENT = 'Row-level filtering by state; can restrict ANALYST to specific states'
;

-- ============================================================================
-- 3. Tags for sensitive columns
-- ============================================================================

CREATE OR REPLACE TAG TAG_PII COMMENT = 'Column contains personally identifiable information';
CREATE OR REPLACE TAG TAG_FINANCIAL COMMENT = 'Column contains financial data (cost)';
CREATE OR REPLACE TAG TAG_SENSITIVE COMMENT = 'Generally sensitive column requiring audit trail';

-- ============================================================================
-- 4. Apply masking policies to RAW table columns
-- ============================================================================

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN PRSCRBR_LAST_ORG_NAME
    SET MASKING POLICY MASK_PROVIDER_NAME
;

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN PRSCRBR_FIRST_NAME
    SET MASKING POLICY MASK_PROVIDER_NAME
;

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN PRSCRBR_NPI
    SET MASKING POLICY MASK_NPI
;

-- Apply row access policy
ALTER TABLE RAW.PRESCRIBER_CLAIMS
    ADD ROW ACCESS POLICY RAP_STATE_FILTER ON (PRSCRBR_STATE_ABRVTN)
;

-- ============================================================================
-- 5. Tag sensitive columns
-- ============================================================================

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN PRSCRBR_NPI SET TAG TAG_PII = 'yes', TAG_SENSITIVE = 'prescriber_id'
;

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN PRSCRBR_LAST_ORG_NAME SET TAG TAG_PII = 'yes'
;

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN PRSCRBR_FIRST_NAME SET TAG TAG_PII = 'yes'
;

ALTER TABLE RAW.PRESCRIBER_CLAIMS
    MODIFY COLUMN TOT_DRUG_CST SET TAG TAG_FINANCIAL = 'yes'
;

-- ============================================================================
-- 6. Verification queries (run these to see masking in effect)
-- ============================================================================

-- As PARTD_ENGINEER, you see unmasked data:
-- SELECT CURRENT_ROLE();
-- SELECT PRSCRBR_NPI, PRSCRBR_LAST_ORG_NAME, PRSCRBR_FIRST_NAME, PRSCRBR_STATE_ABRVTN
-- FROM RAW.PRESCRIBER_CLAIMS
-- LIMIT 5;
-- Output: NPI and names visible

-- As PARTD_ANALYST, you see masked data:
-- USE ROLE PARTD_ANALYST;
-- SELECT PRSCRBR_NPI, PRSCRBR_LAST_ORG_NAME, PRSCRBR_FIRST_NAME, PRSCRBR_STATE_ABRVTN
-- FROM RAW.PRESCRIBER_CLAIMS
-- LIMIT 5;
-- Output: PRSCRBR_NPI shows as 'NPI***', names show as '***MASKED***'

-- ============================================================================
-- 7. Audit trail: Query on sensitive columns is logged
-- ============================================================================

CREATE OR REPLACE VIEW GOVERNANCE.V_RECENT_SENSITIVE_QUERIES AS
    SELECT
        QUERY_ID,
        USER_NAME,
        EXECUTION_TIME,
        QUERY_TEXT,
        WAREHOUSE_NAME
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE (QUERY_TEXT ILIKE '%PRSCRBR_NPI%'
           OR QUERY_TEXT ILIKE '%PRSCRBR_LAST_ORG_NAME%'
           OR QUERY_TEXT ILIKE '%TOT_DRUG_CST%')
        AND EXECUTION_TIME > CURRENT_TIMESTAMP() - INTERVAL '7 days'
    ORDER BY EXECUTION_TIME DESC
COMMENT = 'View of queries touching sensitive columns (audit trail)'
;

-- ============================================================================
-- 8. Summary
-- ============================================================================

SELECT '
Governance Setup Complete
==========================

Masking Policies Applied:
  - MASK_PROVIDER_NAME: NPI, Provider First/Last Name
    → PARTD_ENGINEER: sees actual values
    → PARTD_ANALYST: sees ***MASKED***

  - MASK_NPI: NPI field
    → PARTD_ENGINEER: sees actual NPI
    → PARTD_ANALYST: sees NPI***

Row Access Policy:
  - RAP_STATE_FILTER on PRSCRBR_STATE_ABRVTN
    → Can restrict ANALYST to specific states (example: PARTD_ANALYST_CA)

Tags:
  - TAG_PII: Marks PRSCRBR_NPI, provider names
  - TAG_FINANCIAL: Marks TOT_DRUG_CST
  - TAG_SENSITIVE: Marks sensitive columns

Audit Trail:
  - V_RECENT_SENSITIVE_QUERIES: Shows all queries on masked columns

Testing Masking:
  1. As PARTD_ENGINEER (or ACCOUNTADMIN):
     USE ROLE PARTD_ENGINEER;
     SELECT PRSCRBR_NPI, PRSCRBR_LAST_ORG_NAME FROM RAW.PRESCRIBER_CLAIMS LIMIT 5;
     → See actual values

  2. As PARTD_ANALYST:
     USE ROLE PARTD_ANALYST;
     SELECT PRSCRBR_NPI, PRSCRBR_LAST_ORG_NAME FROM RAW.PRESCRIBER_CLAIMS LIMIT 5;
     → See ***MASKED*** and NPI***

' as summary;
