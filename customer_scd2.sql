-- Incremental SCD2 recon demo: table setup, initial load, and PASS/FAIL test scenarios

USE DATABASE SAMPLE_DATA;
USE SCHEMA PUBLIC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 1: TABLE CREATION
-- ═══════════════════════════════════════════════════════════════════════════════

-- Core table: first landing from source files (one row per customer, latest state)
CREATE OR REPLACE TABLE CUSTOMERS_CORE (
    CUSTOMER_ID      NUMBER PRIMARY KEY,
    CUSTOMER_NAME    VARCHAR(100),
    EMAIL            VARCHAR(200),
    CITY             VARCHAR(50),
    TIER             VARCHAR(20),
    INSERT_DATE_TIME TIMESTAMP_NTZ 
);

-- Conformed SCD2 table: current + historical versions (IS_ACTIVE tracks live row)
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
--
-- DELETE FROM DQ_DATASET_RUN_LOG where dataset_id = 3;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 2: INITIAL LOAD (baseline data)
-- Core: 5 distinct customers from source file at 2025-01-24 ~11:10
-- Conformed: 8 rows (5 active + 3 historical), processed ~3 hrs later at 14:15
-- ═══════════════════════════════════════════════════════════════════════════════

-- Core load (source file landed at 11:10)
INSERT INTO CUSTOMERS_CORE (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, INSERT_DATE_TIME)
VALUES
    (101, 'Alice Smith',   'alice@example.com',   'London',    'GOLD',   '2025-01-24 11:10:05.000'),
    (102, 'Bob Johnson',   'bob@example.com',     'Paris',     'SILVER', '2025-01-24 11:10:06.000'),
    (103, 'Carol White',   'carol@example.com',   'Berlin',    'GOLD',   '2025-01-24 11:10:07.000'),
    (104, 'David Brown',   'david@example.com',   'Madrid',    'BRONZE', '2025-01-24 11:11:05.000'),
    (105, 'Eve Davis',     'eve@example.com',     'Rome',      'SILVER', '2025-01-24 11:12:05.000');

-- Conformed SCD2 load (ETL ran ~3 hrs later at 14:15)
INSERT INTO CUSTOMERS_CONFORMED (CUSTOMER_SK, CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, IS_ACTIVE, INSERT_DATE_TIME, UPDATE_DATE_TIME)
VALUES
    -- Historical (inactive) rows — expired when current versions arrived
    (1, 101, 'Alice Smith',   'alice_old@example.com', 'Manchester', 'SILVER', 'N', '2024-06-01 14:30:00.000', '2025-01-24 14:15:00.000'),
    (2, 102, 'Bob Johnson',   'bob@example.com',       'Lyon',       'BRONZE', 'N', '2024-06-01 14:30:00.000', '2025-01-24 14:15:00.000'),
    (3, 103, 'Carol White',   'carol@example.com',     'Munich',     'SILVER', 'N', '2024-06-01 14:30:00.000', '2025-01-24 14:15:00.000'),
    -- Current (active) rows — UPDATE_DATE_TIME is ~3 hrs after core load
    (4, 101, 'Alice Smith',   'alice@example.com',     'London',     'GOLD',   'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (5, 102, 'Bob Johnson',   'bob@example.com',       'Paris',      'SILVER', 'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (6, 103, 'Carol White',   'carol@example.com',     'Berlin',     'GOLD',   'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (7, 104, 'David Brown',   'david@example.com',     'Madrid',     'BRONZE', 'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000'),
    (8, 105, 'Eve Davis',     'eve@example.com',       'Rome',       'SILVER', 'Y', '2025-01-24 14:15:00.000', '2025-01-24 14:15:00.000');

-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 3: BASELINE RECON RUN (full mode — establishes watermarks)
-- First run with recon_mode="incremental" auto-falls back to full mode,
-- checks ACTIVE_COUNT (core=5, conformed=5 → PASS), and stores watermarks:
--   core_watermark  = 2025-01-24 11:12:05.000
--   conf_watermark  = 2025-01-24 14:15:00.000
-- ═══════════════════════════════════════════════════════════════════════════════

-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(3, 2);
-- Expected: 200 (PASS) — ACTIVE_COUNT: CORE=5, CONFORMED=5

-- Verify watermark stored:
-- SELECT OBSERVED_VALUE FROM DQ_FRAMEWORK.METADATA.DQ_RULE_RESULTS
-- WHERE RULE_CONFIG_ID = 4 ORDER BY RUN_TIMESTAMP DESC LIMIT 1;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SECTION 4: INCREMENTAL SCENARIOS (run AFTER baseline)
-- After baseline, watermarks exist → subsequent runs use true incremental mode
-- ═══════════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════════
-- SCENARIO 1: PASS — Balanced incremental load
-- Delta: 2 new customers (106, 107) + 1 update (104 city change Madrid→Barcelona)
-- Expected:
--   ACTIVE_COUNT:   core new distinct after watermark = 3 (104,106,107)
--                   conformed active after watermark  = 3 (104,106,107)  → PASS
--   INACTIVE_COUNT: core keys that existed in conformed pre-watermark = 1 (104)
--                   conformed inactive after watermark = 1 (104 expired) → PASS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Step 1: Insert new + updated records into CORE (simulates source file landing)
INSERT INTO CUSTOMERS_CORE (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, INSERT_DATE_TIME)
VALUES
    (104, 'David Brown',  'david@example.com',  'Barcelona', 'GOLD',   '2025-02-01 10:10:02.000'),
    (106, 'Frank Miller', 'frank@example.com',  'Vienna',    'GOLD',   '2025-02-01 10:10:03.000'),
    (107, 'Grace Lee',    'grace@example.com',  'Tokyo',     'SILVER', '2025-02-01 10:10:04.000');

-- Step 2: Apply SCD2 in CONFORMED (~4 hours later)
-- 2a: Expire old active row for customer 104
UPDATE CUSTOMERS_CONFORMED
SET IS_ACTIVE = 'N', UPDATE_DATE_TIME = '2025-02-01 14:30:00.000'
WHERE CUSTOMER_ID = 104 AND IS_ACTIVE = 'Y';

-- 2b: Insert new active versions
INSERT INTO CUSTOMERS_CONFORMED (CUSTOMER_SK, CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, IS_ACTIVE, INSERT_DATE_TIME, UPDATE_DATE_TIME)
VALUES
    (9,  104, 'David Brown',  'david@example.com',  'Barcelona', 'GOLD',   'Y', '2025-02-01 14:30:00.000', '2025-02-01 14:30:00.000'),
    (10, 106, 'Frank Miller', 'frank@example.com',  'Vienna',    'GOLD',   'Y', '2025-02-01 14:30:00.000', '2025-02-01 14:30:00.000'),
    (11, 107, 'Grace Lee',    'grace@example.com',  'Tokyo',     'SILVER', 'Y', '2025-02-01 14:30:00.000', '2025-02-01 14:30:00.000');

-- Step 3: Run the recon check → Expected: 200 (PASS)
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(3, 2);

-- Verify:
-- SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RECON_RESULTS WHERE DATASET_ID = 3 ORDER BY AUDIT_TIMESTAMP DESC LIMIT 5;
-- Expected:
--   ACTIVE_COUNT:   CORE_VALUE=3, CONFORMED_VALUE=3, RESULT=PASS
--   INACTIVE_COUNT: CORE_VALUE=1, CONFORMED_VALUE=1, RESULT=PASS


-- ═══════════════════════════════════════════════════════════════════════════════
-- SCENARIO 2: FAIL — Core has records that conformed hasn't processed yet
-- Delta: 2 new customers land in core (108, 109) but conformed ETL hasn't run
-- Expected:
--   ACTIVE_COUNT:   core new distinct after watermark = 2 (108,109)
--                   conformed active after watermark  = 0               → FAIL
--   INACTIVE_COUNT: core keys that existed before = 0
--                   conformed inactive after watermark = 0              → PASS
--   Overall: FAIL (active mismatch)
-- ═══════════════════════════════════════════════════════════════════════════════

-- *** Run Scenario 1 first and verify it passes, then run Scenario 2 ***
-- *** To test Scenario 2, uncomment the block below ***

-- Step 1: New records land in core but conformed ETL is delayed/failed
INSERT INTO CUSTOMERS_CORE (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, INSERT_DATE_TIME)
VALUES
    (108, 'Henry Zhang', 'henry@example.com', 'Shanghai', 'GOLD',   '2025-02-15 09:45:01.000'),
    (109, 'Iris Park',   'iris@example.com',  'Seoul',    'BRONZE', '2025-02-15 09:45:02.000');

-- Step 2: NO conformed inserts (simulates ETL failure / delay)
-- (nothing here — that's the point)

-- Step 3: Run the recon check → Expected: 300 (FAIL)
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(3, 2);

-- Verify:
-- SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RECON_RESULTS WHERE DATASET_ID = 3 ORDER BY AUDIT_TIMESTAMP DESC LIMIT 5;
-- Expected:
--   ACTIVE_COUNT:   CORE_VALUE=2, CONFORMED_VALUE=0, RESULT=FAIL
--   INACTIVE_COUNT: CORE_VALUE=0, CONFORMED_VALUE=0, RESULT=PASS


-- ═══════════════════════════════════════════════════════════════════════════════
-- SCENARIO 3: FAIL — Conformed expired a record without a matching core update
-- This simulates a bug in the SCD2 ETL that incorrectly expires a row
-- Expected:
--   ACTIVE_COUNT:   core new distinct after watermark = 0
--                   conformed active after watermark  = 0               → PASS
--   INACTIVE_COUNT: core keys that existed before = 0
--                   conformed inactive after watermark = 1 (orphan)     → FAIL
--   Overall: FAIL (inactive mismatch — conformed expired a row with no core trigger)
-- ═══════════════════════════════════════════════════════════════════════════════

-- *** Run after resetting from Scenario 2, or on a fresh baseline ***
-- *** To test Scenario 3, uncomment the block below ***

-- Step 1: No new core records (no delta file arrived)
-- (nothing)

-- Step 2: Conformed ETL bug — incorrectly expires customer 105
UPDATE CUSTOMERS_CONFORMED
SET IS_ACTIVE = 'N', UPDATE_DATE_TIME = '2025-03-01 14:00:00.000'
WHERE CUSTOMER_ID = 105 AND IS_ACTIVE = 'Y';

INSERT INTO CUSTOMERS_CONFORMED (CUSTOMER_SK, CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, IS_ACTIVE, INSERT_DATE_TIME, UPDATE_DATE_TIME)
VALUES (12, 105, 'Eve Davis', 'eve@example.com', 'Rome', 'SILVER', 'Y', '2025-03-01 14:00:00.000', '2025-03-01 14:00:00.000');

-- Step 3: Run the recon check → Expected: 300 (FAIL)
-- CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(3, 2);

-- Verify:
-- SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RECON_RESULTS WHERE DATASET_ID = 3 ORDER BY AUDIT_TIMESTAMP DESC LIMIT 5;
-- Expected:
--   ACTIVE_COUNT:   CORE_VALUE=0, CONFORMED_VALUE=1, RESULT=FAIL  (new active row appeared without core trigger)
--   INACTIVE_COUNT: CORE_VALUE=0, CONFORMED_VALUE=1, RESULT=FAIL  (orphan expiry)


-- ═══════════════════════════════════════════════════════════════════════════════
-- RESET: Restore tables to baseline state (before running scenarios)
-- ═══════════════════════════════════════════════════════════════════════════════

-- DELETE FROM CUSTOMERS_CORE WHERE CUSTOMER_ID IN (104, 106, 107, 108, 109) AND INSERT_DATE_TIME > '2025-01-25';
-- INSERT INTO CUSTOMERS_CORE (CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, TIER, INSERT_DATE_TIME)
-- VALUES (104, 'David Brown', 'david@example.com', 'Madrid', 'BRONZE', '2025-01-24 11:11:05.000');
-- DELETE FROM CUSTOMERS_CONFORMED WHERE CUSTOMER_SK >= 9;
-- UPDATE CUSTOMERS_CONFORMED SET IS_ACTIVE = 'Y', UPDATE_DATE_TIME = '2025-01-24 14:15:00.000' WHERE CUSTOMER_ID IN (104, 105) AND IS_ACTIVE = 'N' AND UPDATE_DATE_TIME > '2025-01-25';
