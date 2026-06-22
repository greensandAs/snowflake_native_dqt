-- Data retention policies: TTL-based cleanup tasks for DQ_RULE_AUDIT_LOG and DQ_FAILED_ROW_KEYS

USE DATABASE DQ_FRAMEWORK;
USE SCHEMA METADATA;

-- ============================================================================
-- RETENTION CONFIGURATION
-- Default: 90 days for audit logs, 30 days for failed row keys
-- Adjust these values based on your compliance and debugging needs.
-- ============================================================================

-- Add a retention config table to make TTLs configurable without code changes
CREATE TABLE IF NOT EXISTS DQ_RETENTION_CONFIG (
    TABLE_NAME          VARCHAR(255) NOT NULL,
    RETENTION_DAYS      NUMBER(38, 0) NOT NULL DEFAULT 90,
    IS_ACTIVE           BOOLEAN DEFAULT TRUE,
    LAST_CLEANUP_AT     TIMESTAMP_NTZ(9),
    ROWS_DELETED_LAST   NUMBER(38, 0),
    CREATED_AT          TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT          TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
);

-- Seed default retention periods
MERGE INTO DQ_RETENTION_CONFIG tgt
USING (
    SELECT 'DQ_RULE_AUDIT_LOG' AS TABLE_NAME, 90 AS RETENTION_DAYS
    UNION ALL
    SELECT 'DQ_FAILED_ROW_KEYS', 30
    UNION ALL
    SELECT 'DQ_RULE_RESULTS', 180
    UNION ALL
    SELECT 'DQ_DATASET_RUN_LOG', 180
    UNION ALL
    SELECT 'DQ_RECON_RESULTS', 90
) src
ON tgt.TABLE_NAME = src.TABLE_NAME
WHEN NOT MATCHED THEN
    INSERT (TABLE_NAME, RETENTION_DAYS) VALUES (src.TABLE_NAME, src.RETENTION_DAYS);

-- ============================================================================
-- CLEANUP STORED PROCEDURE
-- Deletes rows older than the configured retention period per table.
-- Returns a summary of what was deleted.
-- ============================================================================

CREATE OR REPLACE PROCEDURE SP_DATA_RETENTION_CLEANUP()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
DECLARE
    v_result VARIANT DEFAULT PARSE_JSON('[]');
    v_table VARCHAR;
    v_days NUMBER;
    v_deleted NUMBER;
    v_ts_col VARCHAR;
    v_sql VARCHAR;
    c1 CURSOR FOR
        SELECT TABLE_NAME, RETENTION_DAYS
        FROM DQ_FRAMEWORK.METADATA.DQ_RETENTION_CONFIG
        WHERE IS_ACTIVE = TRUE;
BEGIN
    OPEN c1;
    FOR rec IN c1 DO
        v_table := rec.TABLE_NAME;
        v_days := rec.RETENTION_DAYS;

        -- Determine the timestamp column for each table
        CASE v_table
            WHEN 'DQ_RULE_AUDIT_LOG' THEN v_ts_col := 'START_TIMESTAMP';
            WHEN 'DQ_FAILED_ROW_KEYS' THEN v_ts_col := 'LOAD_TIMESTAMP';
            WHEN 'DQ_RULE_RESULTS' THEN v_ts_col := 'RUN_TIMESTAMP';
            WHEN 'DQ_DATASET_RUN_LOG' THEN v_ts_col := 'CREATED_TIMESTAMP';
            WHEN 'DQ_RECON_RESULTS' THEN v_ts_col := 'AUDIT_TIMESTAMP';
            ELSE v_ts_col := NULL;
        END CASE;

        IF (v_ts_col IS NOT NULL) THEN
            v_sql := 'DELETE FROM DQ_FRAMEWORK.METADATA.' || :v_table ||
                     ' WHERE ' || :v_ts_col || ' < DATEADD(DAY, -' || :v_days || ', CURRENT_TIMESTAMP())';
            EXECUTE IMMEDIATE :v_sql;

            -- Get rows affected (Snowflake returns this via SQLROWCOUNT)
            v_deleted := SQLROWCOUNT;

            -- Update tracking
            UPDATE DQ_FRAMEWORK.METADATA.DQ_RETENTION_CONFIG
            SET LAST_CLEANUP_AT = CURRENT_TIMESTAMP(),
                ROWS_DELETED_LAST = :v_deleted,
                UPDATED_AT = CURRENT_TIMESTAMP()
            WHERE TABLE_NAME = :v_table;

            v_result := ARRAY_APPEND(:v_result, OBJECT_CONSTRUCT(
                'table', :v_table,
                'retention_days', :v_days,
                'rows_deleted', :v_deleted,
                'status', 'SUCCESS'
            ));
        END IF;
    END FOR;
    CLOSE c1;
    RETURN :v_result;
END;

-- ============================================================================
-- SCHEDULED TASK
-- Runs daily at 2:00 AM UTC. Adjust CRON and warehouse as needed.
-- ============================================================================

CREATE TASK IF NOT EXISTS DQ_FRAMEWORK.METADATA.TASK_DATA_RETENTION_CLEANUP
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 0 2 * * * UTC'
    COMMENT = 'Daily cleanup of expired DQ audit/result data per DQ_RETENTION_CONFIG'
AS
    CALL DQ_FRAMEWORK.METADATA.SP_DATA_RETENTION_CLEANUP();

-- NOTE: Tasks are created in SUSPENDED state. Run this to activate:
-- ALTER TASK DQ_FRAMEWORK.METADATA.TASK_DATA_RETENTION_CLEANUP RESUME;
