-- Complete initial Snowflake account setup: cost intelligence, warehouses, budgets, tagging, and RBAC for the DQ Framework
-- Co-authored with CoCo
-- ═══════════════════════════════════════════════════════════════════════════════════
-- DQ FRAMEWORK — INITIAL ACCOUNT SETUP (REPLICABLE)
-- ═══════════════════════════════════════════════════════════════════════════════════
--
-- PURPOSE:
--   One-shot provisioning script to set up a new Snowflake account with:
--     1. Cost management infrastructure (tags, budgets, resource monitors)
--     2. Warehouses per team & workload (dev, consumer, DQ execution)
--     3. Role hierarchy (development team, consumer team, budget admin)
--     4. DQ Framework database and schemas
--     5. Account-level budget activation
--
-- TEAMS:
--   • Development — builds & maintains DQ procedures, AI monitoring, data pipelines
--   • Consumer    — uses Streamlit app to configure rules and view results
--
-- RUN AS: ACCOUNTADMIN
-- IDEMPOTENT: Yes (uses IF NOT EXISTS / IF EXISTS throughout)
-- ═══════════════════════════════════════════════════════════════════════════════════

USE ROLE ACCOUNTADMIN;


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 1: COST MANAGEMENT INFRASTRUCTURE                                   ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- 1A: Cost management database and schema for tags & budgets
CREATE DATABASE IF NOT EXISTS COST_MANAGEMENT
  COMMENT = 'Central cost governance: tags, budgets, and attribution config';

CREATE SCHEMA IF NOT EXISTS COST_MANAGEMENT.TAGS
  COMMENT = 'Tag definitions for cost attribution and chargeback';

CREATE SCHEMA IF NOT EXISTS COST_MANAGEMENT.BUDGETS
  COMMENT = 'Custom budget objects for per-team spend tracking';



-- 1B: Tags for cost attribution
-- TEAM tag — primary chargeback dimension
CREATE  OR ALTER TAG COST_MANAGEMENT.TAGS.TEAM
  ALLOWED_VALUES 'development', 'consumer'
  COMMENT = 'Primary team attribution for cost chargeback';

-- COMPONENT tag — workload-level granularity
CREATE OR ALTER TAG COST_MANAGEMENT.TAGS.COMPONENT
  ALLOWED_VALUES 'dq_framework', 'dq_app', 'adhoc'
  COMMENT = 'Component/workload attribution within a team';

-- ENVIRONMENT tag — separate dev/test/prod costs
CREATE OR ALTER TAG COST_MANAGEMENT.TAGS.ENVIRONMENT
  ALLOWED_VALUES 'development', 'staging', 'production'
  COMMENT = 'Environment classification for cost separation';


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 2: ROLE HIERARCHY                                                    ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- 2A: Development team roles
CREATE ROLE IF NOT EXISTS DQ_DEVELOPER
  COMMENT = 'Development team — builds/maintains DQ procedures, deploys framework';

CREATE ROLE IF NOT EXISTS DQ_APP_OWNER
  COMMENT = 'Owns the Streamlit app — has write access to DQ metadata';

-- 2B: Consumer team roles
CREATE ROLE IF NOT EXISTS DQ_APP_EARLY_ACCESS
  COMMENT = 'Consumer team — read-only access to DQ app and results';

-- 2C: Cost governance roles
CREATE ROLE IF NOT EXISTS BUDGET_ADMIN
  COMMENT = 'Manages budgets, resource monitors, and cost tags';

-- 2D: Hierarchy — all roll up to SYSADMIN
GRANT ROLE DQ_DEVELOPER        TO ROLE SYSADMIN;
GRANT ROLE DQ_APP_OWNER        TO ROLE SYSADMIN;
GRANT ROLE DQ_APP_EARLY_ACCESS TO ROLE SYSADMIN;
GRANT ROLE BUDGET_ADMIN        TO ROLE SYSADMIN;

-- DQ_APP_OWNER inherits DQ_APP_EARLY_ACCESS (owner can also consume)
GRANT ROLE DQ_APP_EARLY_ACCESS TO ROLE DQ_APP_OWNER;
-- DQ_DEVELOPER inherits DQ_APP_OWNER (devs can also manage the app)
GRANT ROLE DQ_APP_OWNER TO ROLE DQ_DEVELOPER;


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 3: WAREHOUSES (per-team, per-workload)                               ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- ─────────────────────────────────────────────────────────────────────────────
-- 3A: COMPUTE_WH — Development team ad-hoc queries & exploration
-- ─────────────────────────────────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_SIZE   = 'XSMALL'
  AUTO_SUSPEND     = 60
  AUTO_RESUME      = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Development team — ad-hoc queries, testing, exploration';

ALTER WAREHOUSE COMPUTE_WH SET TAG
  COST_MANAGEMENT.TAGS.TEAM        = 'development',
  COST_MANAGEMENT.TAGS.COMPONENT   = 'adhoc',
  COST_MANAGEMENT.TAGS.ENVIRONMENT = 'development';

GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE DQ_DEVELOPER;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3B: DQ_EXECUTION_WH — Dedicated for DQ stored procedure runs
-- ─────────────────────────────────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS DQ_EXECUTION_WH
  WAREHOUSE_SIZE   = 'XSMALL'
  AUTO_SUSPEND     = 60
  AUTO_RESUME      = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'DQ Framework — dedicated for EXECUTE_DQ_RULES_MASTER procedure runs';

ALTER WAREHOUSE DQ_EXECUTION_WH SET TAG
  COST_MANAGEMENT.TAGS.TEAM        = 'development',
  COST_MANAGEMENT.TAGS.COMPONENT   = 'dq_framework',
  COST_MANAGEMENT.TAGS.ENVIRONMENT = 'production';

GRANT USAGE ON WAREHOUSE DQ_EXECUTION_WH TO ROLE DQ_DEVELOPER;
GRANT USAGE ON WAREHOUSE DQ_EXECUTION_WH TO ROLE DQ_APP_OWNER;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3C: DQ_APP_EARLY_WH — Consumer team Streamlit app usage
-- ─────────────────────────────────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS DQ_APP_EARLY_WH
  WAREHOUSE_SIZE   = 'XSMALL'
  AUTO_SUSPEND     = 60
  AUTO_RESUME      = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Consumer team — Streamlit DQ app queries. Aggressive auto-suspend for interactive use.';

ALTER WAREHOUSE DQ_APP_EARLY_WH SET TAG
  COST_MANAGEMENT.TAGS.TEAM        = 'consumer',
  COST_MANAGEMENT.TAGS.COMPONENT   = 'dq_app',
  COST_MANAGEMENT.TAGS.ENVIRONMENT = 'production';

GRANT USAGE ON WAREHOUSE DQ_APP_EARLY_WH TO ROLE DQ_APP_EARLY_ACCESS;
GRANT USAGE ON WAREHOUSE DQ_APP_EARLY_WH TO ROLE DQ_APP_OWNER;


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 4: RESOURCE MONITORS (hard suspend safety nets)                      ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- 4A: Account-level resource monitor (global safety net)
CREATE RESOURCE MONITOR IF NOT EXISTS ACCOUNT_MONTHLY_LIMIT
  WITH CREDIT_QUOTA = 250
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 50 PERCENT DO NOTIFY
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER ACCOUNT SET RESOURCE_MONITOR = ACCOUNT_MONTHLY_LIMIT;


-- 4B: Development warehouse monitor
CREATE RESOURCE MONITOR IF NOT EXISTS DEV_WH_MONITOR
  WITH CREDIT_QUOTA = 150
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE COMPUTE_WH SET RESOURCE_MONITOR = DEV_WH_MONITOR;


-- 4C: DQ Execution warehouse monitor
CREATE RESOURCE MONITOR IF NOT EXISTS DQ_EXECUTION_MONITOR
  WITH CREDIT_QUOTA = 50
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE DQ_EXECUTION_WH SET RESOURCE_MONITOR = DQ_EXECUTION_MONITOR;


-- 4D: Consumer app warehouse monitor
CREATE RESOURCE MONITOR IF NOT EXISTS DQ_APP_MONITOR
  WITH CREDIT_QUOTA = 50
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 50 PERCENT DO NOTIFY
    ON 80 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE DQ_APP_EARLY_WH SET RESOURCE_MONITOR = DQ_APP_MONITOR;


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 5: BUDGETS (alerting & tracking — does NOT suspend)                  ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- 5A: Activate the account-level budget (monitors ALL credit usage)
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!ACTIVATE();
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_SPENDING_LIMIT(250);
-- ⚠️ Replace with your actual admin email(s)
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_EMAIL_NOTIFICATIONS(
    'aslam26hlw@gmail.com'
);


-- 5B: Development team custom budget (tag-based)
CREATE SNOWFLAKE.CORE.BUDGET IF NOT EXISTS COST_MANAGEMENT.BUDGETS.DEVELOPMENT_BUDGET();

CALL COST_MANAGEMENT.BUDGETS.DEVELOPMENT_BUDGET!SET_SPENDING_LIMIT(200);

GRANT APPLYBUDGET ON TAG COST_MANAGEMENT.TAGS.TEAM TO ROLE ACCOUNTADMIN;

CALL COST_MANAGEMENT.BUDGETS.DEVELOPMENT_BUDGET!SET_RESOURCE_TAGS(
    [
        [(SELECT SYSTEM$REFERENCE('TAG', 'COST_MANAGEMENT.TAGS.TEAM', 'SESSION', 'APPLYBUDGET')), 'development']
    ],
    'UNION'
);

-- ⚠️ Replace with your dev lead email
CALL COST_MANAGEMENT.BUDGETS.DEVELOPMENT_BUDGET!SET_EMAIL_NOTIFICATIONS(
    'aslam26hlw@gmail.com'
);


-- 5C: Consumer team custom budget (tag-based)
CREATE SNOWFLAKE.CORE.BUDGET IF NOT EXISTS COST_MANAGEMENT.BUDGETS.CONSUMER_BUDGET();

CALL COST_MANAGEMENT.BUDGETS.CONSUMER_BUDGET!SET_SPENDING_LIMIT(50);

CALL COST_MANAGEMENT.BUDGETS.CONSUMER_BUDGET!SET_RESOURCE_TAGS(
    [
        [(SELECT SYSTEM$REFERENCE('TAG', 'COST_MANAGEMENT.TAGS.TEAM', 'SESSION', 'APPLYBUDGET')), 'consumer']
    ],
    'UNION'
);

-- ⚠️ Replace with your product owner email
CALL COST_MANAGEMENT.BUDGETS.CONSUMER_BUDGET!SET_EMAIL_NOTIFICATIONS(
    'aslam26hlw@gmail.com'
);


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 6: DQ FRAMEWORK DATABASE & SCHEMAS                                   ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

CREATE DATABASE IF NOT EXISTS DQ_FRAMEWORK
  COMMENT = 'Data Quality Framework — metadata-driven quality engine';

CREATE SCHEMA IF NOT EXISTS DQ_FRAMEWORK.METADATA
  COMMENT = 'Rule config, results, audit logs';

CREATE SCHEMA IF NOT EXISTS DQ_FRAMEWORK.DQ_ERRORS
  COMMENT = 'Failed row capture tables (one per dataset)';

CREATE SCHEMA IF NOT EXISTS DQ_FRAMEWORK.APP
  COMMENT = 'Streamlit app objects';

-- Tag the database for cost tracking
ALTER DATABASE DQ_FRAMEWORK SET TAG
  COST_MANAGEMENT.TAGS.TEAM      = 'development',
  COST_MANAGEMENT.TAGS.COMPONENT = 'dq_framework';


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 7: RBAC GRANTS FOR DQ FRAMEWORK                                     ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- 7A: Development team — full access
GRANT USAGE ON DATABASE DQ_FRAMEWORK TO ROLE DQ_DEVELOPER;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DQ_FRAMEWORK TO ROLE DQ_DEVELOPER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_DEVELOPER;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_DEVELOPER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.DQ_ERRORS TO ROLE DQ_DEVELOPER;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.DQ_ERRORS TO ROLE DQ_DEVELOPER;
GRANT CREATE PROCEDURE ON SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_DEVELOPER;

-- 7B: App owner — write (for procedure execution)
GRANT USAGE ON DATABASE DQ_FRAMEWORK TO ROLE DQ_APP_OWNER;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DQ_FRAMEWORK TO ROLE DQ_APP_OWNER;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;
GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.DQ_ERRORS TO ROLE DQ_APP_OWNER;
GRANT SELECT, INSERT ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.DQ_ERRORS TO ROLE DQ_APP_OWNER;

-- 7C: Consumer team — read-only
GRANT USAGE ON DATABASE DQ_FRAMEWORK TO ROLE DQ_APP_EARLY_ACCESS;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DQ_FRAMEWORK TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON ALL TABLES IN SCHEMA DQ_FRAMEWORK.DQ_ERRORS TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE TABLES IN SCHEMA DQ_FRAMEWORK.DQ_ERRORS TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON ALL VIEWS IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_EARLY_ACCESS;

-- 7D: Budget admin — cost governance access
GRANT USAGE ON DATABASE COST_MANAGEMENT TO ROLE BUDGET_ADMIN;
GRANT USAGE ON ALL SCHEMAS IN DATABASE COST_MANAGEMENT TO ROLE BUDGET_ADMIN;
GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE BUDGET_ADMIN;
GRANT DATABASE ROLE SNOWFLAKE.GOVERNANCE_VIEWER TO ROLE BUDGET_ADMIN;


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 8: COST MANAGEMENT VIEWS (reporting queries)                         ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

CREATE SCHEMA IF NOT EXISTS COST_MANAGEMENT.REPORTING;

-- 8A: Daily credit usage by warehouse and team tag
CREATE OR REPLACE VIEW COST_MANAGEMENT.REPORTING.V_DAILY_CREDITS_BY_TEAM AS
SELECT
    TO_DATE(wmh.START_TIME)            AS USAGE_DATE,
    wmh.WAREHOUSE_NAME,
    COALESCE(tr.TAG_VALUE, '(untagged)') AS TEAM,
    SUM(wmh.CREDITS_USED)             AS CREDITS_CONSUMED
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
LEFT JOIN (
    SELECT OBJECT_NAME, TAG_VALUE
    FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
    WHERE TAG_NAME = 'TEAM'
      AND TAG_SCHEMA = 'TAGS'
      AND TAG_DATABASE = 'COST_MANAGEMENT'
      AND DOMAIN = 'WAREHOUSE'
) tr ON tr.OBJECT_NAME = wmh.WAREHOUSE_NAME
WHERE wmh.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC;

-- 8B: Monthly summary by component
CREATE OR REPLACE VIEW COST_MANAGEMENT.REPORTING.V_MONTHLY_CREDITS_BY_COMPONENT AS
SELECT
    DATE_TRUNC('MONTH', wmh.START_TIME)  AS USAGE_MONTH,
    wmh.WAREHOUSE_NAME,
    COALESCE(tr.TAG_VALUE, '(untagged)') AS COMPONENT,
    SUM(wmh.CREDITS_USED)               AS CREDITS_CONSUMED
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
LEFT JOIN (
    SELECT OBJECT_NAME, TAG_VALUE
    FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
    WHERE TAG_NAME = 'COMPONENT'
      AND TAG_SCHEMA = 'TAGS'
      AND TAG_DATABASE = 'COST_MANAGEMENT'
      AND DOMAIN = 'WAREHOUSE'
) tr ON tr.OBJECT_NAME = wmh.WAREHOUSE_NAME
WHERE wmh.START_TIME >= DATEADD('month', -6, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC;

-- 8C: Resource monitor status check
-- (Run manually — cannot be in a view)
-- SHOW RESOURCE MONITORS;

-- Grant reporting views to budget admin
GRANT SELECT ON ALL VIEWS IN SCHEMA COST_MANAGEMENT.REPORTING TO ROLE BUDGET_ADMIN;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA COST_MANAGEMENT.REPORTING TO ROLE BUDGET_ADMIN;


-- ╔═══════════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 9: VERIFICATION                                                      ║
-- ╚═══════════════════════════════════════════════════════════════════════════════╝

-- 9A: Confirm warehouses are tagged
SELECT
    OBJECT_DATABASE,
    OBJECT_NAME,
    TAG_NAME,
    TAG_VALUE
FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
WHERE TAG_DATABASE = 'COST_MANAGEMENT'
  AND DOMAIN = 'WAREHOUSE'
ORDER BY OBJECT_NAME, TAG_NAME;

-- 9B: Confirm resource monitors are assigned
SHOW RESOURCE MONITORS;

-- 9C: Confirm budget status
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!GET_SPENDING_LIMIT();

-- 9D: Confirm role hierarchy
SHOW GRANTS TO ROLE DQ_DEVELOPER;
SHOW GRANTS TO ROLE DQ_APP_EARLY_ACCESS;


-- ═══════════════════════════════════════════════════════════════════════════════════
-- ✅ SETUP COMPLETE
-- ═══════════════════════════════════════════════════════════════════════════════════
--
-- NEXT STEPS:
--   1. Replace email placeholders (search for @yourcompany.com)
--   2. Adjust CREDIT_QUOTA values in resource monitors to match your Snowflake plan
--   3. Adjust SET_SPENDING_LIMIT values in budgets as needed
--   4. Run DQM/DDL/V1.0.0__create_framework_tables.sql for DQ tables
--   5. Run DQM/DML.sql for seed metadata
--   6. Run DQM/Procedures/*.sql for stored procedures
--   7. Deploy the Streamlit app (DQM/app/)
--   8. Grant DQ_APP_EARLY_ACCESS to consumer users:
--        GRANT ROLE DQ_APP_EARLY_ACCESS TO USER <username>;
--   9. Grant DQ_DEVELOPER to development users:
--        GRANT ROLE DQ_DEVELOPER TO USER <username>;
--
-- COST CONTROL SUMMARY:
--   ┌──────────────────┬────────────┬──────────────────┬─────────────────────┐
--   │ Warehouse        │ Team       │ Resource Monitor │ Budget              │
--   ├──────────────────┼────────────┼──────────────────┼─────────────────────┤
--   │ COMPUTE_WH       │ dev        │ 150 cr/mo        │ DEVELOPMENT (200)   │
--   │ DQ_EXECUTION_WH  │ dev        │ 50 cr/mo        │ DEVELOPMENT (200)   │
--   │ DQ_APP_EARLY_WH  │ consumer   │ 50 cr/mo        │ CONSUMER (50)      │
--   ├──────────────────┼────────────┼──────────────────┼─────────────────────┤
--   │ ACCOUNT TOTAL    │ all        │ 250 cr/mo        │ ACCOUNT (500)       │
--   └──────────────────┴────────────┴──────────────────┴─────────────────────┘
-- ═══════════════════════════════════════════════════════════════════════════════════
