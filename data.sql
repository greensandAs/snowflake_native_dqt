-- Sample data for DQ framework: ROW_COUNT_MATCH (plain + SCD2) and SOURCE_FILE_COUNT_MATCH checks
-- Co-authored with CoCo



SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_PROJECT_RUN_LOG;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 1: Create SAMPLE_DATA database and tables
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS SAMPLE_DATA;
CREATE SCHEMA IF NOT EXISTS SAMPLE_DATA.PUBLIC;
USE DATABASE SAMPLE_DATA;
USE SCHEMA PUBLIC;

-- ─── Plain row-count comparison tables ───────────────────────────────────────

-- Core table (first landing from source files)
CREATE OR REPLACE TABLE ORDERS_CORE (
    ORDER_ID         NUMBER PRIMARY KEY,
    CUSTOMER_ID      NUMBER,
    ORDER_DATE       DATE,
    AMOUNT           NUMBER(12,2),
    STATUS           VARCHAR(20),
    INSERT_DATE_TIME TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Conformed table (downstream transformed layer — should match core count)
CREATE OR REPLACE TABLE ORDERS_CONFORMED (
    ORDER_ID         NUMBER PRIMARY KEY,
    CUSTOMER_ID      NUMBER,
    ORDER_DATE       DATE,
    AMOUNT           NUMBER(12,2),
    STATUS           VARCHAR(20),
    IS_ACTIVE        VARCHAR(1) DEFAULT 'Y',
    INSERT_DATE_TIME TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UPDATE_DATE_TIME TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ─── SCD Type 2 tables ──────────────────────────────────────────────────────

-- Core: 5 distinct customers (landed from source files)
CREATE OR REPLACE TABLE CUSTOMERS_CORE (
    CUSTOMER_ID      NUMBER PRIMARY KEY,
    CUSTOMER_NAME    VARCHAR(100),
    EMAIL            VARCHAR(200),
    CITY             VARCHAR(50),
    TIER             VARCHAR(20),
    INSERT_DATE_TIME TIMESTAMP_NTZ 
);

-- Conformed SCD2: contains current + historical versions (IS_ACTIVE flag tracks which is live)
CREATE OR REPLACE TABLE CUSTOMERS_CONFORMED (
    CUSTOMER_SK      NUMBER,
    CUSTOMER_ID      NUMBER,
    CUSTOMER_NAME    VARCHAR(100),
    EMAIL            VARCHAR(200),
    CITY             VARCHAR(50),
    TIER             VARCHAR(20),
    IS_ACTIVE        VARCHAR(1) DEFAULT 'Y',
    INSERT_DATE_TIME TIMESTAMP_NTZ ,
    UPDATE_DATE_TIME TIMESTAMP_NTZ 
);

-- ─── Audit control table (TEST_AUDIT_LOG) ────────────────────────────────────
-- Mirrors the real PRISM_META_PROD.META.AUDIT_CONTROL structure

CREATE OR REPLACE TABLE TEST_AUDIT_LOG (
    ID                        NUMBER AUTOINCREMENT PRIMARY KEY,
    BATCH_ID                  VARCHAR(200),
    RUN_ID                    VARCHAR(200),
    JOB_ID                    VARCHAR(200),
    SOURCE_OBJECT_NAME        VARCHAR(1000),
    TARGET_TABLE              VARCHAR(500),
    NUMBER_OF_RECORDS_SOURCE  NUMBER,
    NUMBER_OF_RECORDS_TARGET  NUMBER,
    SYNC_LEVEL                VARCHAR(50),
    SYNC_STATUS               VARCHAR(20),
    SYNC_START_DATE_TIME      TIMESTAMP_TZ,
    SYNC_END_DATE_TIME        TIMESTAMP_TZ
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 2: Insert sample data
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─── Orders (plain row-count test: 10 core = 10 conformed → PASS) ────────────

INSERT INTO ORDERS_CORE (ORDER_ID, CUSTOMER_ID, ORDER_DATE, AMOUNT, STATUS)
VALUES
    (1, 101, '2025-01-15', 250.00, 'COMPLETED'),
    (2, 102, '2025-01-16', 120.50, 'COMPLETED'),
    (3, 103, '2025-01-17', 89.99, 'PENDING'),
    (4, 101, '2025-01-18', 340.00, 'COMPLETED'),
    (5, 104, '2025-01-19', 75.25, 'CANCELLED'),
    (6, 105, '2025-01-20', 199.99, 'COMPLETED'),
    (7, 102, '2025-01-21', 450.00, 'PENDING'),
    (8, 106, '2025-01-22', 67.50, 'COMPLETED'),
    (9, 103, '2025-01-23', 310.00, 'COMPLETED'),
    (10, 107, '2025-01-24', 155.75, 'COMPLETED');

INSERT INTO ORDERS_CONFORMED (ORDER_ID, CUSTOMER_ID, ORDER_DATE, AMOUNT, STATUS)
SELECT ORDER_ID, CUSTOMER_ID, ORDER_DATE, AMOUNT, STATUS FROM ORDERS_CORE;

-- ─── Customers SCD2 test ─────────────────────────────────────────────────────
-- Core has 5 distinct customers (landed from source files)
-- INSERT_DATE_TIME reflects when file landed in core (source-to-core sync time)
INSERT INTO CUSTOMERS_CORE (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, INSERT_DATE_TIME)
VALUES
    (101, 'Alice Smith',   'alice@example.com',   'London',    'GOLD',   '2025-01-24 11:10:05.000'),
    (102, 'Bob Johnson',   'bob@example.com',     'Paris',     'SILVER', '2025-01-24 11:10:06.000'),
    (103, 'Carol White',   'carol@example.com',   'Berlin',    'GOLD',   '2025-01-24 11:10:07.000'),
    (104, 'David Brown',   'david@example.com',   'Madrid',    'BRONZE', '2025-01-24 11:11:05.000'),
    (105, 'Eve Davis',     'eve@example.com',     'Rome',      'SILVER', '2025-01-24 11:12:05.000');

-- Conformed SCD2 has 8 rows: 5 active (current) + 3 inactive (historical versions)
-- Active count (5) should equal core count (5) → PASS
-- UPDATE_DATE_TIME is 3-5 hours after core INSERT_DATE_TIME (conformed ETL runs later)
INSERT INTO CUSTOMERS_CONFORMED (CUSTOMER_SK, CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, IS_ACTIVE, INSERT_DATE_TIME, UPDATE_DATE_TIME)
VALUES
    -- Historical (inactive) rows (expired when current versions arrived)
    (1, 101, 'Alice Smith',   'alice_old@example.com', 'Manchester', 'SILVER', 'N', '2024-06-01 14:30:00.000', '2025-01-24 14:15:00.000'),
    (2, 102, 'Bob Johnson',   'bob@example.com',       'Lyon',       'BRONZE', 'N', '2024-06-01 14:30:00.000', '2025-01-24 14:15:00.000'),
    (3, 103, 'Carol White',   'carol@example.com',     'Munich',     'SILVER', 'N', '2024-06-01 14:30:00.000', '2025-01-24 14:15:00.000'),
    -- Current (active) rows — UPDATE_DATE_TIME is ~3 hrs after core load (11:10 → 14:15)
    (4, 101, 'Alice Smith',   'alice@example.com',     'London',     'GOLD',   'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (5, 102, 'Bob Johnson',   'bob@example.com',       'Paris',      'SILVER', 'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (6, 103, 'Carol White',   'carol@example.com',     'Berlin',     'GOLD',   'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (7, 104, 'David Brown',   'david@example.com',     'Madrid',     'BRONZE', 'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (8, 105, 'Eve Davis',     'eve@example.com',       'Rome',       'SILVER', 'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000');

-- ─── Audit log entries ───────────────────────────────────────────────────────
-- Realistic sample data matching the PRISM audit control pattern
-- Records file→core sync counts (SOURCE_TO_CORE level)
INSERT INTO TEST_AUDIT_LOG (BATCH_ID, RUN_ID, JOB_ID, SOURCE_OBJECT_NAME, TARGET_TABLE, NUMBER_OF_RECORDS_SOURCE, NUMBER_OF_RECORDS_TARGET, SYNC_LEVEL, SYNC_STATUS, SYNC_START_DATE_TIME, SYNC_END_DATE_TIME)
VALUES
    -- ORDERS_CORE: 10 records synced from file to core (SOURCE=10, TARGET=10 → PASS)
    ('orders_20250124', 'run_20250124101500', 'src_to_core_20250124',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/orders/input/orders_20250124.csv#orders#core/orders_s3.json',
     'SAMPLE_DATA.PUBLIC.ORDERS_CORE', 10, 10, 'SOURCE_TO_CORE', 'Success',
     '2025-01-24 10:15:00.000 -0500', '2025-01-24 10:15:05.000 -0500'),

    -- CUSTOMERS_CORE: 5 records synced from file to core (SOURCE=5, TARGET=5 → PASS)
    ('customers_20250124', 'run_20250124111000', 'src_to_core_20250124',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/customers/input/Customer_DELTA_20250124.csv#customers#core/customers_s3.json',
     'SAMPLE_DATA.PUBLIC.CUSTOMERS_CORE', 5, 5, 'SOURCE_TO_CORE', 'Success',
     '2025-01-24 11:10:00.000 -0500', '2025-01-24 11:10:12.000 -0500'),

    -- MDM_HCP example (large volume, simulates real-world pattern)
    ('mdm_20250124', 'run_20250124120000', 'src_to_core_20250124',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/mdm/input/Individual_DELTA_20250124.csv#mdm_hcp#core/mdm_s3.json',
     'SAMPLE_DATA.PUBLIC.MDM_HCP', 483194, 483194, 'SOURCE_TO_CORE', 'Success',
     '2025-01-24 12:00:00.000 -0500', '2025-01-24 12:00:17.000 -0500'),

    -- VCRM_USER: zero-record sync (no new data — still valid)
    ('vcrm_20250124', 'run_20250124130000', 'src_to_core_20250124',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/vcrm/input/.*user*#user#core/vcrm_s3.json',
     'SAMPLE_DATA.PUBLIC.VCRM_USER_C', 0, 0, 'SOURCE_TO_CORE', 'Success',
     '2025-01-24 13:00:00.000 -0500', '2025-01-24 13:00:01.000 -0500'),

    -- Failed sync example (can be used to test filtering by SYNC_STATUS)
    ('orders_20250120', 'run_20250120090000', 'src_to_core_20250120',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/orders/input/orders_20250120.csv#orders#core/orders_s3.json',
     'SAMPLE_DATA.PUBLIC.ORDERS_CORE', 10, 0, 'SOURCE_TO_CORE', 'Failure',
     '2025-01-20 09:00:00.000 -0500', '2025-01-20 09:00:00.500 -0500'),

    -- Retry of the failed sync (succeeded)
    ('orders_20250120', 'run_20250120091500', 'src_to_core_20250120',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/orders/input/orders_20250120.csv#orders#core/orders_s3.json',
     'SAMPLE_DATA.PUBLIC.ORDERS_CORE', 10, 10, 'SOURCE_TO_CORE', 'Success',
     '2025-01-20 09:15:00.000 -0500', '2025-01-20 09:15:04.000 -0500');

-- -- ═══════════════════════════════════════════════════════════════════════════════
-- -- SECTION 3: Fix handler mapping for expectation 4 (ROW_COUNT_MATCH)
-- -- The handler SP_TABLE_ROW_COUNT_EQUAL_OTHER_TABLE_CHECK is mapped to
-- -- TABLE_ROW_COUNT_CMP_CHECK but the expectation master uses ROW_COUNT_MATCH.
-- -- ═══════════════════════════════════════════════════════════════════════════════

-- USE DATABASE DQ_FRAMEWORK;
-- USE SCHEMA METADATA;

-- -- Add correct mapping if missing
-- INSERT INTO DQ_EXPECTATION_HANDLER_MAPPING (CHECK_TYPE, EXPECTATION_TYPE, SP_NAME, HANDLER_VERSION, IS_ACTIVE, CREATED_AT, UPDATED_AT)
-- SELECT 'ROW_COUNT_MATCH', 'expect_table_row_count_to_equal_other_table', 'SP_TABLE_ROW_COUNT_EQUAL_OTHER_TABLE_CHECK', 'v1.0', TRUE, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_EXPECTATION_HANDLER_MAPPING WHERE CHECK_TYPE = 'ROW_COUNT_MATCH');

-- -- ═══════════════════════════════════════════════════════════════════════════════
-- -- SECTION 4: Register project and datasets
-- -- ═══════════════════════════════════════════════════════════════════════════════

-- -- Project
-- INSERT INTO DQ_PROJECTS (PROJECT_ID, PROJECT_NAME, PROJECT_DESCRIPTION, CREATED_BY, CREATED_TIMESTAMP)
-- SELECT 1, 'SAMPLE_PROJECT', 'Sample project for testing row-count and SCD2 checks', CURRENT_USER(), CURRENT_TIMESTAMP()
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_PROJECTS WHERE PROJECT_ID = 1);

-- -- Dataset 1: ORDERS_CONFORMED (the conformed table being validated)
-- INSERT INTO DQ_DATASET (DATASET_ID, PROJECT_ID, DATASET_TYPE, DATASET_NAME, PROJECT_NAME,
--     DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, PRIMARY_KEY_COLUMNS, DATASET_DESCRIPTION,
--     CREATED_BY, CREATED_TIMESTAMP)
-- SELECT 1, 1, 'TABLE', 'ORDERS_CONFORMED', 'SAMPLE_PROJECT',
--     'SAMPLE_DATA', 'PUBLIC', 'ORDERS_CONFORMED', 'ORDER_ID',
--     'Conformed orders table — validated against core layer',
--     CURRENT_USER(), CURRENT_TIMESTAMP()
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_DATASET WHERE DATASET_ID = 1);

-- -- Dataset 2: CUSTOMERS_CONFORMED (SCD Type 2 conformed table being validated)
-- INSERT INTO DQ_DATASET (DATASET_ID, PROJECT_ID, DATASET_TYPE, DATASET_NAME, PROJECT_NAME,
--     DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, PRIMARY_KEY_COLUMNS, DATASET_DESCRIPTION,
--     CREATED_BY, CREATED_TIMESTAMP)
-- SELECT 2, 1, 'TABLE', 'CUSTOMERS_CONFORMED', 'SAMPLE_PROJECT',
--     'SAMPLE_DATA', 'PUBLIC', 'CUSTOMERS_CONFORMED', 'CUSTOMER_SK',
--     'SCD2 conformed customers — active count validated against core',
--     CURRENT_USER(), CURRENT_TIMESTAMP()
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_DATASET WHERE DATASET_ID = 2);

-- -- ═══════════════════════════════════════════════════════════════════════════════
-- -- SECTION 5: Configure DQ rules
-- -- ═══════════════════════════════════════════════════════════════════════════════

-- -- Rule 1: Plain row count comparison (scd_type=0)
-- -- ORDERS_CONFORMED (10 rows) vs ORDERS_CORE (10 rows) → PASS
-- -- "source" in KWARGS = the core table we compare against
-- INSERT INTO DQ_RULE_CONFIG (
--     RULE_CONFIG_ID, EXPECTATION_ID, DATASET_ID, EXPECTATION_NAME, EXPECTATION_TYPE,
--     KWARGS, DIMENSION, COLUMN_NAME, RULE_DESCRIPTION, CHECK_TYPE, SEVERITY,
--     IS_ACTIVE, CREATED_BY, CREATED_TIMESTAMP, ERROR_FLAG
-- )
-- SELECT 1, 4, 1,
--     'expect_table_row_count_to_equal_other_table', 'expect_table_row_count_to_equal_other_table',
--     '{"source_database": "SAMPLE_DATA", "source_schema": "PUBLIC", "source_table": "ORDERS_CORE", "scd_type": 0}',
--     'VOLUME', NULL,
--     'Conformed orders row count must equal core table count (plain)',
--     'ROW_COUNT_MATCH', 'HIGH',
--     TRUE, CURRENT_USER(), CURRENT_TIMESTAMP(), TRUE
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_RULE_CONFIG WHERE RULE_CONFIG_ID = 1);

-- -- Rule 2: SCD Type 2 active-count comparison (scd_type=2)
-- -- CUSTOMERS_CONFORMED active rows (5) vs CUSTOMERS_CORE (5) → PASS
-- -- The handler counts only active rows in the conformed (dataset) table,
-- -- then compares against the full count of the core ("source") table.
-- INSERT INTO DQ_RULE_CONFIG (
--     RULE_CONFIG_ID, EXPECTATION_ID, DATASET_ID, EXPECTATION_NAME, EXPECTATION_TYPE,
--     KWARGS, DIMENSION, COLUMN_NAME, RULE_DESCRIPTION, CHECK_TYPE, SEVERITY,
--     IS_ACTIVE, CREATED_BY, CREATED_TIMESTAMP, ERROR_FLAG
-- )
-- SELECT 2, 4, 2,
--     'expect_table_row_count_to_equal_other_table', 'expect_table_row_count_to_equal_other_table',
--     '{"source_database": "SAMPLE_DATA", "source_schema": "PUBLIC", "source_table": "CUSTOMERS_CORE", "scd_type": 2, "active_flag_col": "IS_ACTIVE", "active_value": "Y", "inactive_value": "N"}',
--     'VOLUME', NULL,
--     'Conformed SCD2 active customer count must equal core count',
--     'ROW_COUNT_MATCH', 'HIGH',
--     TRUE, CURRENT_USER(), CURRENT_TIMESTAMP(), TRUE
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_RULE_CONFIG WHERE RULE_CONFIG_ID = 2);

-- -- Rule 3: Source file count match for ORDERS_CORE
-- -- Validates that ORDERS_CORE row count matches what the audit log recorded from the file
-- INSERT INTO DQ_RULE_CONFIG (
--     RULE_CONFIG_ID, EXPECTATION_ID, DATASET_ID, EXPECTATION_NAME, EXPECTATION_TYPE,
--     KWARGS, DIMENSION, COLUMN_NAME, RULE_DESCRIPTION, CHECK_TYPE, SEVERITY,
--     IS_ACTIVE, CREATED_BY, CREATED_TIMESTAMP, ERROR_FLAG
-- )
-- SELECT 3, 26, 1,
--     'expect_table_row_count_to_equal_source_file', 'expect_table_row_count_to_equal_source_file',
--     '{"audit_control_table": "SAMPLE_DATA.PUBLIC.TEST_AUDIT_LOG", "sync_level": "SOURCE_TO_CORE", "target_table": "SAMPLE_DATA.PUBLIC.ORDERS_CORE"}',
--     'VOLUME', NULL,
--     'Core orders count must match source file record count in TEST_AUDIT_LOG',
--     'SOURCE_FILE_COUNT_MATCH', 'HIGH',
--     TRUE, CURRENT_USER(), CURRENT_TIMESTAMP(), TRUE
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_RULE_CONFIG WHERE RULE_CONFIG_ID = 3);

-- -- Rule 4: Source file count match for CUSTOMERS_CORE
-- -- Validates that CUSTOMERS_CORE row count matches what the audit log recorded from the file
-- INSERT INTO DQ_RULE_CONFIG (
--     RULE_CONFIG_ID, EXPECTATION_ID, DATASET_ID, EXPECTATION_NAME, EXPECTATION_TYPE,
--     KWARGS, DIMENSION, COLUMN_NAME, RULE_DESCRIPTION, CHECK_TYPE, SEVERITY,
--     IS_ACTIVE, CREATED_BY, CREATED_TIMESTAMP, ERROR_FLAG
-- )
-- SELECT 4, 26, 2,
--     'expect_table_row_count_to_equal_source_file', 'expect_table_row_count_to_equal_source_file',
--     '{"audit_control_table": "SAMPLE_DATA.PUBLIC.TEST_AUDIT_LOG", "sync_level": "SOURCE_TO_CORE", "target_table": "SAMPLE_DATA.PUBLIC.CUSTOMERS_CORE"}',
--     'VOLUME', NULL,
--     'Core customers count must match source file record count in TEST_AUDIT_LOG',
--     'SOURCE_FILE_COUNT_MATCH', 'HIGH',
--     TRUE, CURRENT_USER(), CURRENT_TIMESTAMP(), TRUE
-- WHERE NOT EXISTS (SELECT 1 FROM DQ_RULE_CONFIG WHERE RULE_CONFIG_ID = 4);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 6: Execute
-- ═══════════════════════════════════════════════════════════════════════════════

-- Run all rules for ORDERS_CONFORMED:
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(1, 2);

-- Run all rules for CUSTOMERS_CONFORMED:
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(2, 2);

-- Run entire project (both datasets):
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_PROJECT(1, 2);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 6B: Incremental SCD2 row count check
-- Simulates a delta load: 2 new customers + 1 update (address change for ID 104)
-- After this increment:
--   CUSTOMERS_CORE   = 7 rows (5 original + 2 new from delta)
--   CUSTOMERS_CONFORMED = 12 rows total (7 active + 5 historical)
--   Active count (7) = Core count (7) → PASS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Step 1: New delta rows arrive in CORE (new customers from source file)
INSERT INTO CUSTOMERS_CORE (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, INSERT_DATE_TIME)
VALUES
    (106, 'Frank Miller',  'frank@example.com',  'Vienna',    'GOLD',   '2025-02-01 10:10:05.000'),
    (107, 'Grace Lee',     'grace@example.com',  'Tokyo',     'SILVER', '2025-02-01 10:10:05.000');

-- Step 2: Apply SCD2 in CONFORMED
-- 2a: Expire the old active row for customer 104 (address changed Madrid → Barcelona)
UPDATE CUSTOMERS_CONFORMED
SET IS_ACTIVE = 'N', UPDATE_DATE_TIME = '2025-02-01 14:30:00.000'
WHERE CUSTOMER_ID = 104 AND IS_ACTIVE = 'Y';

-- 2b: Insert new active version for customer 104 + new customers 106, 107
-- UPDATE_DATE_TIME is ~4.5 hrs after core INSERT_DATE_TIME (10:10 → 14:30)
INSERT INTO CUSTOMERS_CONFORMED (CUSTOMER_SK, CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, IS_ACTIVE, INSERT_DATE_TIME, UPDATE_DATE_TIME)
VALUES
    -- Updated version of 104 (new active row)
    (9,  104, 'David Brown',  'david@example.com',  'Barcelona', 'GOLD',   'Y', '2025-02-01 14:30:00.000', '2025-02-01 14:30:00.000'),
    -- Brand new customers
    (10, 106, 'Frank Miller', 'frank@example.com',  'Vienna',    'GOLD',   'Y', '2025-02-01 14:30:00.000', '2025-02-01 14:30:00.000'),
    (11, 107, 'Grace Lee',    'grace@example.com',  'Tokyo',     'SILVER', 'Y', '2025-02-01 14:30:00.000', '2025-02-01 14:30:00.000');

-- Step 3: Update audit log for the incremental file
INSERT INTO TEST_AUDIT_LOG (BATCH_ID, RUN_ID, JOB_ID, SOURCE_OBJECT_NAME, TARGET_TABLE, NUMBER_OF_RECORDS_SOURCE, NUMBER_OF_RECORDS_TARGET, SYNC_LEVEL, SYNC_STATUS, SYNC_START_DATE_TIME, SYNC_END_DATE_TIME)
VALUES
    ('customers_20250201', 'run_20250201101000', 'src_to_core_20250201',
     '@SAMPLE_DATA.PUBLIC.LANDING_STAGE/customers/input/Customer_DELTA_20250201.csv#customers#core/customers_s3.json',
     'SAMPLE_DATA.PUBLIC.CUSTOMERS_CORE', 3, 3, 'SOURCE_TO_CORE', 'Success',
     '2025-02-01 10:10:00.000 -0500', '2025-02-01 10:10:08.000 -0500');

-- Verification queries:
-- SELECT COUNT(*) FROM CUSTOMERS_CORE;                                          -- Expected: 7
-- SELECT COUNT(*) FROM CUSTOMERS_CONFORMED WHERE IS_ACTIVE = 'Y';              -- Expected: 7 (PASS)
-- SELECT COUNT(*) FROM CUSTOMERS_CONFORMED;                                     -- Expected: 12 total (7 active + 5 historical)

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 7: Simulate FAILURE scenarios (uncomment to test)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Scenario A: Add row to core without updating conformed → conformed < core (Rule 1 FAILS)
-- INSERT INTO SAMPLE_DATA.PUBLIC.ORDERS_CORE VALUES (11, 108, '2025-01-25', 500.00, 'COMPLETED', CURRENT_TIMESTAMP());

-- Scenario B: Add a new active customer to conformed without updating core → conformed active > core (Rule 2 FAILS)
-- INSERT INTO SAMPLE_DATA.PUBLIC.CUSTOMERS_CONFORMED VALUES (9, 106, 'Frank Miller', 'frank@example.com', 'Vienna', 'GOLD', 'Y', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());

-- Scenario C: Update audit log to say 12 records from source → file count > core count (Rule 3 FAILS)
-- UPDATE SAMPLE_DATA.PUBLIC.TEST_AUDIT_LOG SET NUMBER_OF_RECORDS_SOURCE = 12 WHERE BATCH_ID = 'orders_20250124';

-- Re-run after failure injection:
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(1, 2);
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(2, 2);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 8: Useful queries
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RULE_RESULTS ORDER BY DATASET_RUN_ID DESC;
SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_DATASET_RUN_LOG ORDER BY DATASET_RUN_ID DESC;
SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RULE_AUDIT_LOG ORDER BY START_TIMESTAMP DESC;
SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RULE_CONFIG WHERE DATASET_ID IN (1, 2);
SELECT * FROM SAMPLE_DATA.PUBLIC.TEST_AUDIT_LOG;


delete from dq_rule_results where dataset_id = 3; order by run_timestamp desc ;


select * from sample_data.public.customers_core;
select * from sample_data.public.customers_conformed;



