-- ==============================================================================
-- Snowflake Account Setup: ACCOUNTADMIN Worksheet
-- ==============================================================================
-- Run this in Snowsight as ACCOUNTADMIN to set up the warehouse, database,
-- schemas, roles, and resource monitor for the Part D analytics lab.
--
-- Estimated cost: negligible (with AUTO_SUSPEND = 60 and resource monitor)
-- ==============================================================================

-- 1. Create warehouse with auto-suspend and resource monitor support
CREATE OR REPLACE WAREHOUSE WH_PARTD
  WAREHOUSE_SIZE = XSMALL
  AUTO_SUSPEND = 60        -- suspend after 60 sec of inactivity
  AUTO_RESUME = TRUE       -- auto-resume on query
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Part D analytics lab warehouse, auto-suspend to control costs';

-- 2. Create resource monitor: cap at 20 credits with suspend at 75% and 100%
CREATE OR REPLACE RESOURCE MONITOR RM_PARTD
  CREDIT_QUOTA = 20
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

-- 3. Attach resource monitor to warehouse
ALTER WAREHOUSE WH_PARTD SET RESOURCE_MONITOR = RM_PARTD;

-- 4. Create database and schemas
CREATE OR REPLACE DATABASE PARTD_LAB
  COMMENT = 'Medicare Part D prescriber analytics';

CREATE OR REPLACE SCHEMA PARTD_LAB.RAW
  COMMENT = 'Raw data from CMS public data sources';

CREATE OR REPLACE SCHEMA PARTD_LAB.STAGING
  COMMENT = 'Cleaned, deduplicated staging tables';

CREATE OR REPLACE SCHEMA PARTD_LAB.MARTS
  COMMENT = 'Analytics marts for reporting';

CREATE OR REPLACE SCHEMA PARTD_LAB.GOVERNANCE
  COMMENT = 'Governance policies, masks, tags';

-- 5. Create roles with appropriate grants
CREATE OR REPLACE ROLE PARTD_ENGINEER
  COMMENT = 'Read/write access to all schemas for dbt and pipeline work';

CREATE OR REPLACE ROLE PARTD_ANALYST
  COMMENT = 'Read-only access to marts for analytics';

-- Grant warehouse usage to both roles
GRANT USAGE ON WAREHOUSE WH_PARTD TO ROLE PARTD_ENGINEER;
GRANT USAGE ON WAREHOUSE WH_PARTD TO ROLE PARTD_ANALYST;

-- Grant database-level permissions
GRANT USAGE ON DATABASE PARTD_LAB TO ROLE PARTD_ENGINEER;
GRANT USAGE ON DATABASE PARTD_LAB TO ROLE PARTD_ANALYST;

-- Grant schema permissions: ENGINEER gets full access, ANALYST gets usage
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE DYNAMIC TABLE ON SCHEMA PARTD_LAB.RAW TO ROLE PARTD_ENGINEER;
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE DYNAMIC TABLE ON SCHEMA PARTD_LAB.STAGING TO ROLE PARTD_ENGINEER;
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE DYNAMIC TABLE ON SCHEMA PARTD_LAB.MARTS TO ROLE PARTD_ENGINEER;
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE DYNAMIC TABLE ON SCHEMA PARTD_LAB.GOVERNANCE TO ROLE PARTD_ENGINEER;

GRANT USAGE ON SCHEMA PARTD_LAB.MARTS TO ROLE PARTD_ANALYST;
GRANT SELECT ON FUTURE TABLES IN SCHEMA PARTD_LAB.MARTS TO ROLE PARTD_ANALYST;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA PARTD_LAB.MARTS TO ROLE PARTD_ANALYST;
GRANT SELECT ON FUTURE DYNAMIC TABLES IN SCHEMA PARTD_LAB.MARTS TO ROLE PARTD_ANALYST;

-- 6. Set role ownership for dbt (never use ACCOUNTADMIN for dbt runs)
GRANT OWNERSHIP ON DATABASE PARTD_LAB TO ROLE PARTD_ENGINEER;
GRANT OWNERSHIP ON SCHEMA PARTD_LAB.RAW TO ROLE PARTD_ENGINEER;
GRANT OWNERSHIP ON SCHEMA PARTD_LAB.STAGING TO ROLE PARTD_ENGINEER;
GRANT OWNERSHIP ON SCHEMA PARTD_LAB.MARTS TO ROLE PARTD_ENGINEER;
GRANT OWNERSHIP ON SCHEMA PARTD_LAB.GOVERNANCE TO ROLE PARTD_ENGINEER;

-- 7. Create an internal stage for data loading
CREATE OR REPLACE STAGE PARTD_LAB.RAW.STG_PARTD
  COMMENT = 'Internal stage for CMS Medicare Part D CSV ingestion';

GRANT READ, WRITE ON STAGE PARTD_LAB.RAW.STG_PARTD TO ROLE PARTD_ENGINEER;

-- 8. Verify setup
SELECT 'Setup complete' AS status;
SELECT CURRENT_ACCOUNT() AS account, CURRENT_USER() AS user;
