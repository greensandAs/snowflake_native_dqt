-- Consolidated SQL for secure early-access Streamlit rollout with RBAC, cost tracking, and read-only enforcement
-- ═══════════════════════════════════════════════════════════════════════════════
-- DQ FRAMEWORK — STREAMLIT EARLY-ACCESS ROLLOUT
-- ═══════════════════════════════════════════════════════════════════════════════
-- This script provisions:
--   1. Role hierarchy for early-access control
--   2. Dedicated warehouse + resource monitor for cost tracking
--   3. Read-only enforcement on DQ_FRAMEWORK.METADATA
--   4. App owner grants for write operations via stored procedures
--   5. Streamlit app access grants
--   6. Verification & audit queries
--
-- PREREQUISITES:
--   - Run as ACCOUNTADMIN (or SECURITYADMIN for role/grant operations)
--   - Streamlit app must already be created before running Section 5
--   - Adjust <APP_DB>, <APP_SCHEMA>, <APP_NAME> placeholders in Section 5
-- ═══════════════════════════════════════════════════════════════════════════════

USE ROLE ACCOUNTADMIN;
CREATE SCHEMA IF NOT EXISTS DQ_FRAMEWORK.APP;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 1: ROLE HIERARCHY
-- ═══════════════════════════════════════════════════════════════════════════════

-- Early-access viewer role (read-only, limited user set)
CREATE ROLE IF NOT EXISTS DQ_APP_EARLY_ACCESS
  COMMENT = 'Early-access viewers for DQ Framework Streamlit app';

-- App owner role (deploys and manages the Streamlit app)
CREATE ROLE IF NOT EXISTS DQ_APP_OWNER
  COMMENT = 'Owner role for DQ Framework Streamlit app — has write access to metadata';

-- Establish hierarchy so SYSADMIN can manage both
GRANT ROLE DQ_APP_EARLY_ACCESS TO ROLE SYSADMIN;
GRANT ROLE DQ_APP_OWNER TO ROLE SYSADMIN;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 2: GRANT EARLY ACCESS TO SPECIFIC USERS
-- ═══════════════════════════════════════════════════════════════════════════════
-- Add/remove users here to control who gets early access.
-- When ready for GA, grant a broader role (e.g., DQ_APP_VIEWER) instead.
SHOW USERS;
CREATE USER IF NOT EXISTS TEST_USER 
  PASSWORD = 'Testpassword123'
  LOGIN_NAME = 'TEST_USER'
  DISPLAY_NAME = 'TEST_USER'
  EMAIL = 'aslam26hlw@gmail.com'
  MUST_CHANGE_PASSWORD =  FALSE
  TYPE = PERSON
  COMMENT = 'Consumer App User';
GRANT ROLE DQ_APP_EARLY_ACCESS TO USER TEST_USER ;
-- GRANT ROLE DQ_APP_EARLY_ACCESS TO USER <USER_B>;
-- GRANT ROLE DQ_APP_EARLY_ACCESS TO USER <USER_C>;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 3: DEDICATED WAREHOUSE + RESOURCE MONITOR
-- ═══════════════════════════════════════════════════════════════════════════════

-- Dedicated warehouse for cost isolation and performance tracking
CREATE WAREHOUSE IF NOT EXISTS DQ_APP_EARLY_WH
  WAREHOUSE_SIZE   = 'X-SMALL'
  AUTO_SUSPEND     = 60
  AUTO_RESUME      = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Dedicated warehouse for DQ Streamlit early-access — enables cost attribution';

-- Resource monitor to cap spend and alert on usage thresholds
CREATE RESOURCE MONITOR IF NOT EXISTS DQ_EARLY_ACCESS_MONITOR
  WITH CREDIT_QUOTA = 50
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE DQ_APP_EARLY_WH SET RESOURCE_MONITOR = DQ_EARLY_ACCESS_MONITOR;

-- Grant warehouse usage to both roles
GRANT USAGE ON WAREHOUSE DQ_APP_EARLY_WH TO ROLE DQ_APP_EARLY_ACCESS;
GRANT USAGE ON WAREHOUSE DQ_APP_EARLY_WH TO ROLE DQ_APP_OWNER;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 4: READ-ONLY ACCESS ON DQ_FRAMEWORK.METADATA
-- ═══════════════════════════════════════════════════════════════════════════════
-- Early-access users can VIEW metadata but NEVER modify it directly.

-- Database and schema USAGE (required for any object access)
GRANT USAGE ON DATABASE DQ_FRAMEWORK TO ROLE DQ_APP_EARLY_ACCESS;
GRANT USAGE ON SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;

-- SELECT only on all current and future tables
GRANT SELECT ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;

-- SELECT only on all current and future views
GRANT SELECT ON ALL VIEWS IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;

-- EXPLICITLY: No INSERT, UPDATE, DELETE, TRUNCATE granted.
-- Users with DQ_APP_EARLY_ACCESS cannot write to metadata via worksheets or SnowSQL.


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 4B: APP OWNER GRANTS (write access for rule execution)
-- ═══════════════════════════════════════════════════════════════════════════════
-- The app owner role needs DML to write results when executing DQ rules.

GRANT USAGE ON DATABASE DQ_FRAMEWORK TO ROLE DQ_APP_OWNER;
GRANT USAGE ON SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;

-- Full DML on metadata tables (for stored procedure execution)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;
GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;

-- Procedure execution rights
GRANT USAGE ON ALL PROCEDURES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;
GRANT USAGE ON FUTURE PROCEDURES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;

-- Read access to source data (SAMPLE_DATA) for recon rules
GRANT USAGE ON DATABASE SAMPLE_DATA TO ROLE DQ_APP_OWNER;
GRANT USAGE ON SCHEMA SAMPLE_DATA.PUBLIC TO ROLE DQ_APP_OWNER;
GRANT USAGE ON SCHEMA SAMPLE_DATA.CONFORMED TO ROLE DQ_APP_OWNER;
GRANT SELECT ON ALL TABLES IN SCHEMA SAMPLE_DATA.PUBLIC TO ROLE DQ_APP_OWNER;
GRANT SELECT ON ALL TABLES IN SCHEMA SAMPLE_DATA.CONFORMED TO ROLE DQ_APP_OWNER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SAMPLE_DATA.PUBLIC TO ROLE DQ_APP_OWNER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SAMPLE_DATA.CONFORMED TO ROLE DQ_APP_OWNER;

-- Early-access viewers also need read on SAMPLE_DATA for app dashboards
GRANT USAGE ON DATABASE SAMPLE_DATA TO ROLE DQ_APP_EARLY_ACCESS;
GRANT USAGE ON SCHEMA SAMPLE_DATA.PUBLIC TO ROLE DQ_APP_EARLY_ACCESS;
GRANT USAGE ON SCHEMA SAMPLE_DATA.CONFORMED TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON ALL TABLES IN SCHEMA SAMPLE_DATA.PUBLIC TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON ALL TABLES IN SCHEMA SAMPLE_DATA.CONFORMED TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SAMPLE_DATA.PUBLIC TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SAMPLE_DATA.CONFORMED TO ROLE DQ_APP_EARLY_ACCESS;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 5: STREAMLIT APP ACCESS
-- ═══════════════════════════════════════════════════════════════════════════════
-- ⚠️  Replace <APP_DB>.<APP_SCHEMA>.<APP_NAME> with your actual Streamlit object name.
-- Run this section AFTER the Streamlit app has been created.

-- Grant app USAGE to early-access role only
GRANT USAGE ON STREAMLIT DQ_FRAMEWORK.APP.DQAPP_EA TO ROLE DQ_APP_EARLY_ACCESS;

-- Assign the dedicated warehouse to the app for automatic query routing
ALTER STREAMLIT DQ_FRAMEWORK.APP.DQAPP_EA SET QUERY_WAREHOUSE = DQ_APP_EARLY_WH;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 6: VERIFICATION & AUDIT QUERIES
-- ═══════════════════════════════════════════════════════════════════════════════

-- 6A: List all grants to the early-access role
SHOW GRANTS TO ROLE DQ_APP_EARLY_ACCESS;

-- 6B: Confirm NO write privileges exist on DQ_FRAMEWORK for early-access
SELECT
    PRIVILEGE,
    GRANTED_ON,
    TABLE_CATALOG,
    TABLE_SCHEMA,
    NAME
FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
WHERE GRANTEE_NAME = 'DQ_APP_EARLY_ACCESS'
  AND PRIVILEGE IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
  AND TABLE_CATALOG = 'DQ_FRAMEWORK'
  AND DELETED_ON IS NULL;
-- Expected: 0 rows (no write access)

-- 6C: Cost tracking — daily credit usage for the dedicated warehouse
SELECT
    TO_DATE(START_TIME) AS USAGE_DATE,
    SUM(CREDITS_USED) AS CREDITS_CONSUMED
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE WAREHOUSE_NAME = 'DQ_APP_EARLY_WH'
  AND START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 1;

-- 6D: Query activity by user on the early-access warehouse
SELECT
    USER_NAME,
    COUNT(*) AS QUERY_COUNT,
    SUM(TOTAL_ELAPSED_TIME) / 1000 AS TOTAL_SECONDS,
    AVG(TOTAL_ELAPSED_TIME) / 1000 AS AVG_SECONDS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE WAREHOUSE_NAME = 'DQ_APP_EARLY_WH'
  AND START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 2 DESC;

-- 6E: Resource monitor status
SHOW RESOURCE MONITORS LIKE 'DQ_EARLY_ACCESS_MONITOR';


-- ═══════════════════════════════════════════════════════════════════════════════
-- GA TRANSITION (run when ready to open access to all users)
-- ═══════════════════════════════════════════════════════════════════════════════
-- Option A: Grant a broader role access to the app
-- CREATE ROLE IF NOT EXISTS DQ_APP_VIEWER;
-- GRANT USAGE ON STREAMLIT <APP_DB>.<APP_SCHEMA>.<APP_NAME> TO ROLE DQ_APP_VIEWER;
-- GRANT USAGE ON WAREHOUSE DQ_APP_EARLY_WH TO ROLE DQ_APP_VIEWER;
-- (repeat read-only grants from Section 4 for DQ_APP_VIEWER)

-- Option B: Reassign warehouse to a shared one for GA
-- ALTER STREAMLIT <APP_DB>.<APP_SCHEMA>.<APP_NAME> SET QUERY_WAREHOUSE = COMPUTE_WH;
