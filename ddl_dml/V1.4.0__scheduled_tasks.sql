-- Scheduled task infrastructure: metadata-driven Snowflake Tasks for automated DQ execution
-- Co-authored with CoCo

USE DATABASE {{framework_db}};
USE SCHEMA {{framework_schema}};

-- ============================================================================
-- SCHEDULE CONFIGURATION TABLE
-- Stores desired schedules; a stored procedure reconciles these into actual
-- Snowflake Tasks (CREATE/ALTER/DROP).
-- ============================================================================

CREATE TABLE IF NOT EXISTS DQ_SCHEDULE_CONFIG (
    SCHEDULE_ID         NUMBER(38, 0) NOT NULL AUTOINCREMENT START 1 INCREMENT 1,
    SCHEDULE_NAME       VARCHAR(255) NOT NULL,
    SCHEDULE_TYPE       VARCHAR(20) NOT NULL,   -- 'DATASET' or 'PROJECT'
    TARGET_ID           NUMBER(38, 0) NOT NULL, -- DATASET_ID or PROJECT_ID
    CRON_EXPRESSION     VARCHAR(100) NOT NULL,  -- 5-field cron (e.g., '0 6 * * *')
    TIMEZONE            VARCHAR(100) DEFAULT 'UTC',
    WAREHOUSE           VARCHAR(255) DEFAULT 'DQ_EXECUTION_WH',
    PARALLEL_JOBS       NUMBER(38, 0) DEFAULT 2,  -- for PROJECT schedules
    IS_ACTIVE           BOOLEAN DEFAULT TRUE,
    TASK_NAME           VARCHAR(255),           -- auto-populated by reconcile proc
    LAST_RECONCILED_AT  TIMESTAMP_NTZ(9),
    CREATED_BY          VARCHAR(255) DEFAULT CURRENT_USER(),
    CREATED_AT          TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT          TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_DQ_SCHEDULE_CONFIG PRIMARY KEY (SCHEDULE_ID),
    CONSTRAINT CHK_SCHEDULE_TYPE CHECK (SCHEDULE_TYPE IN ('DATASET', 'PROJECT'))
);

-- Schedule execution log — tracks each scheduled run outcome
CREATE TABLE IF NOT EXISTS DQ_SCHEDULE_RUN_LOG (
    SCHEDULE_RUN_ID     NUMBER(38, 0) NOT NULL AUTOINCREMENT START 1 INCREMENT 1,
    SCHEDULE_ID         NUMBER(38, 0) NOT NULL,
    TASK_NAME           VARCHAR(255),
    RUN_STATUS          VARCHAR(50),   -- SUCCESS, FAILURE, ERROR
    RESULT_CODE         NUMBER(38, 0),
    RUN_STARTED_AT      TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    RUN_COMPLETED_AT    TIMESTAMP_NTZ(9),
    ERROR_MESSAGE       VARCHAR(16777216),
    BATCH_ID            NUMBER(38, 0),
    CONSTRAINT PK_DQ_SCHEDULE_RUN_LOG PRIMARY KEY (SCHEDULE_RUN_ID)
);

-- ============================================================================
-- STORED PROCEDURE: SP_MANAGE_DQ_SCHEDULES
-- Reads DQ_SCHEDULE_CONFIG and reconciles Snowflake Tasks accordingly.
-- - Active configs → CREATE OR REPLACE TASK (resumed)
-- - Inactive configs → suspend the task
-- - Deleted configs (task exists but no config row) → DROP TASK
-- ============================================================================

CREATE OR REPLACE PROCEDURE SP_MANAGE_DQ_SCHEDULES()
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python==*')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import json
import datetime


def main(session):
    _DEFAULT_FQN = "DQ_FRAMEWORK.METADATA"

    # Read framework location from config
    _cfg = session.sql(
        f"SELECT DQ_DB_NAME, DQ_SCHEMA_NAME "
        f"FROM {_DEFAULT_FQN}.DQ_JOB_EXEC_CONFIG LIMIT 1"
    ).collect()[0]
    fw = f"{_cfg['DQ_DB_NAME']}.{_cfg['DQ_SCHEMA_NAME']}"

    results = {"created": [], "updated": [], "suspended": [], "dropped": [], "errors": []}

    # Get all schedule configs
    schedules = session.sql(
        f"SELECT SCHEDULE_ID, SCHEDULE_NAME, SCHEDULE_TYPE, TARGET_ID, "
        f"CRON_EXPRESSION, TIMEZONE, WAREHOUSE, PARALLEL_JOBS, IS_ACTIVE, TASK_NAME "
        f"FROM {fw}.DQ_SCHEDULE_CONFIG ORDER BY SCHEDULE_ID"
    ).collect()

    managed_tasks = set()

    for row in schedules:
        schedule_id = int(row["SCHEDULE_ID"])
        schedule_name = row["SCHEDULE_NAME"]
        schedule_type = row["SCHEDULE_TYPE"]
        target_id = int(row["TARGET_ID"])
        cron_expr = row["CRON_EXPRESSION"]
        timezone = row["TIMEZONE"] or "UTC"
        warehouse = row["WAREHOUSE"] or "DQ_EXECUTION_WH"
        parallel_jobs = int(row["PARALLEL_JOBS"]) if row["PARALLEL_JOBS"] else 2
        is_active = row["IS_ACTIVE"]
        existing_task = row["TASK_NAME"]

        # Derive task name
        task_name = f"TASK_DQ_SCHEDULE_{schedule_id}"
        fq_task = f"{fw}.{task_name}"
        managed_tasks.add(task_name)

        try:
            if is_active:
                # Build the CALL statement
                if schedule_type == "PROJECT":
                    call_stmt = f"CALL {fw}.EXECUTE_DQ_RULES_PROJECT({target_id}, {parallel_jobs})"
                else:
                    call_stmt = f"CALL {fw}.EXECUTE_DQ_RULES_MASTER({target_id})"

                # Create or replace the task
                create_sql = (
                    f"CREATE OR REPLACE TASK {fq_task}\n"
                    f"  WAREHOUSE = {warehouse}\n"
                    f"  SCHEDULE = 'USING CRON {cron_expr} {timezone}'\n"
                    f"  COMMENT = 'DQ Schedule: {schedule_name} ({schedule_type} ID={target_id})'\n"
                    f"AS\n"
                    f"  {call_stmt}"
                )
                session.sql(create_sql).collect()

                # Resume the task
                session.sql(f"ALTER TASK {fq_task} RESUME").collect()

                action = "updated" if existing_task else "created"
                results[action].append({"schedule_id": schedule_id, "task": task_name})
            else:
                # Suspend the task if it exists
                if existing_task:
                    try:
                        session.sql(f"ALTER TASK {fq_task} SUSPEND").collect()
                        results["suspended"].append({"schedule_id": schedule_id, "task": task_name})
                    except Exception:
                        pass  # Task may not exist yet

            # Update the config row with the task name and timestamp
            session.sql(
                f"UPDATE {fw}.DQ_SCHEDULE_CONFIG "
                f"SET TASK_NAME = '{task_name}', LAST_RECONCILED_AT = CURRENT_TIMESTAMP(), "
                f"    UPDATED_AT = CURRENT_TIMESTAMP() "
                f"WHERE SCHEDULE_ID = {schedule_id}"
            ).collect()

        except Exception as e:
            results["errors"].append({
                "schedule_id": schedule_id,
                "task": task_name,
                "error": str(e)[:500]
            })

    # Drop orphaned tasks (tasks that match our naming convention but have no config)
    try:
        existing_tasks = session.sql(
            f"SHOW TASKS IN SCHEMA {fw}"
        ).collect()
        for t in existing_tasks:
            t_name = t["name"]
            if t_name.startswith("TASK_DQ_SCHEDULE_") and t_name not in managed_tasks:
                try:
                    session.sql(f"DROP TASK IF EXISTS {fw}.{t_name}").collect()
                    results["dropped"].append({"task": t_name})
                except Exception as e:
                    results["errors"].append({"task": t_name, "error": str(e)[:300]})
    except Exception as e:
        results["errors"].append({"step": "orphan_cleanup", "error": str(e)[:300]})

    results["reconciled_at"] = datetime.datetime.now().isoformat()
    results["total_schedules"] = len(schedules)
    return results
$$;

-- ============================================================================
-- STORED PROCEDURE: SP_DQ_SCHEDULED_RUN_WRAPPER
-- Wrapper called by tasks. Executes the DQ run and logs the outcome to
-- DQ_SCHEDULE_RUN_LOG for observability.
-- ============================================================================

CREATE OR REPLACE PROCEDURE SP_DQ_SCHEDULED_RUN_WRAPPER(
    "P_SCHEDULE_ID" NUMBER(38, 0),
    "P_SCHEDULE_TYPE" VARCHAR,
    "P_TARGET_ID" NUMBER(38, 0),
    "P_PARALLEL_JOBS" NUMBER(38, 0) DEFAULT 2
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python==*')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import json
import datetime


def main(session, P_SCHEDULE_ID, P_SCHEDULE_TYPE, P_TARGET_ID, P_PARALLEL_JOBS):
    _DEFAULT_FQN = "DQ_FRAMEWORK.METADATA"

    _cfg = session.sql(
        f"SELECT DQ_DB_NAME, DQ_SCHEMA_NAME, SUCCESS_CODE, FAILED_CODE, EXECUTION_ERROR "
        f"FROM {_DEFAULT_FQN}.DQ_JOB_EXEC_CONFIG LIMIT 1"
    ).collect()[0]
    fw = f"{_cfg['DQ_DB_NAME']}.{_cfg['DQ_SCHEMA_NAME']}"
    success_code = int(_cfg["SUCCESS_CODE"])

    started = datetime.datetime.now()
    result_code = None
    run_status = None
    error_msg = None
    batch_id = None

    try:
        if P_SCHEDULE_TYPE == "PROJECT":
            result = session.call(f"{fw}.EXECUTE_DQ_RULES_PROJECT", int(P_TARGET_ID), int(P_PARALLEL_JOBS))
            if isinstance(result, str):
                result = json.loads(result)
            run_status = result.get("status", "UNKNOWN")
            result_code = result.get("overall_code")
            batch_id = result.get("batch_id")
        else:
            result_code = int(session.call(f"{fw}.EXECUTE_DQ_RULES_MASTER", int(P_TARGET_ID)))
            run_status = "SUCCESS" if result_code == success_code else "FAILURE"
    except Exception as e:
        run_status = "ERROR"
        error_msg = str(e)[:2000]

    completed = datetime.datetime.now()

    # Log the run
    try:
        task_name = f"TASK_DQ_SCHEDULE_{int(P_SCHEDULE_ID)}"
        session.sql(
            f"INSERT INTO {fw}.DQ_SCHEDULE_RUN_LOG "
            f"(SCHEDULE_ID, TASK_NAME, RUN_STATUS, RESULT_CODE, "
            f" RUN_STARTED_AT, RUN_COMPLETED_AT, ERROR_MESSAGE, BATCH_ID) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            params=[int(P_SCHEDULE_ID), task_name, run_status, result_code,
                    started, completed, error_msg, batch_id]
        ).collect()
    except Exception:
        pass

    return {
        "schedule_id": int(P_SCHEDULE_ID),
        "schedule_type": P_SCHEDULE_TYPE,
        "target_id": int(P_TARGET_ID),
        "run_status": run_status,
        "result_code": result_code,
        "batch_id": batch_id,
        "duration_seconds": (completed - started).total_seconds(),
        "error": error_msg,
    }
$$;

-- ============================================================================
-- UPDATED RECONCILE PROCEDURE: SP_MANAGE_DQ_SCHEDULES_V2
-- Uses the wrapper procedure so that runs are logged automatically.
-- ============================================================================

CREATE OR REPLACE PROCEDURE SP_MANAGE_DQ_SCHEDULES()
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python==*')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import json
import datetime


def main(session):
    _DEFAULT_FQN = "DQ_FRAMEWORK.METADATA"

    _cfg = session.sql(
        f"SELECT DQ_DB_NAME, DQ_SCHEMA_NAME "
        f"FROM {_DEFAULT_FQN}.DQ_JOB_EXEC_CONFIG LIMIT 1"
    ).collect()[0]
    fw = f"{_cfg['DQ_DB_NAME']}.{_cfg['DQ_SCHEMA_NAME']}"

    results = {"created": [], "updated": [], "suspended": [], "dropped": [], "errors": []}

    schedules = session.sql(
        f"SELECT SCHEDULE_ID, SCHEDULE_NAME, SCHEDULE_TYPE, TARGET_ID, "
        f"CRON_EXPRESSION, TIMEZONE, WAREHOUSE, PARALLEL_JOBS, IS_ACTIVE, TASK_NAME "
        f"FROM {fw}.DQ_SCHEDULE_CONFIG ORDER BY SCHEDULE_ID"
    ).collect()

    managed_tasks = set()

    for row in schedules:
        schedule_id = int(row["SCHEDULE_ID"])
        schedule_name = row["SCHEDULE_NAME"]
        schedule_type = row["SCHEDULE_TYPE"]
        target_id = int(row["TARGET_ID"])
        cron_expr = row["CRON_EXPRESSION"]
        timezone = row["TIMEZONE"] or "UTC"
        warehouse = row["WAREHOUSE"] or "DQ_EXECUTION_WH"
        parallel_jobs = int(row["PARALLEL_JOBS"]) if row["PARALLEL_JOBS"] else 2
        is_active = row["IS_ACTIVE"]
        existing_task = row["TASK_NAME"]

        task_name = f"TASK_DQ_SCHEDULE_{schedule_id}"
        fq_task = f"{fw}.{task_name}"
        managed_tasks.add(task_name)

        try:
            if is_active:
                # Use the wrapper proc for logging
                call_stmt = (
                    f"CALL {fw}.SP_DQ_SCHEDULED_RUN_WRAPPER("
                    f"{schedule_id}, '{schedule_type}', {target_id}, {parallel_jobs})"
                )

                create_sql = (
                    f"CREATE OR REPLACE TASK {fq_task}\n"
                    f"  WAREHOUSE = {warehouse}\n"
                    f"  SCHEDULE = 'USING CRON {cron_expr} {timezone}'\n"
                    f"  COMMENT = 'DQ Schedule: {schedule_name} ({schedule_type} ID={target_id})'\n"
                    f"AS\n"
                    f"  {call_stmt}"
                )
                session.sql(create_sql).collect()
                session.sql(f"ALTER TASK {fq_task} RESUME").collect()

                action = "updated" if existing_task else "created"
                results[action].append({"schedule_id": schedule_id, "task": task_name})
            else:
                if existing_task:
                    try:
                        session.sql(f"ALTER TASK {fq_task} SUSPEND").collect()
                        results["suspended"].append({"schedule_id": schedule_id, "task": task_name})
                    except Exception:
                        pass

            session.sql(
                f"UPDATE {fw}.DQ_SCHEDULE_CONFIG "
                f"SET TASK_NAME = '{task_name}', LAST_RECONCILED_AT = CURRENT_TIMESTAMP(), "
                f"    UPDATED_AT = CURRENT_TIMESTAMP() "
                f"WHERE SCHEDULE_ID = {schedule_id}"
            ).collect()

        except Exception as e:
            results["errors"].append({
                "schedule_id": schedule_id,
                "task": task_name,
                "error": str(e)[:500]
            })

    # Drop orphaned tasks
    try:
        existing_tasks = session.sql(f"SHOW TASKS IN SCHEMA {fw}").collect()
        for t in existing_tasks:
            t_name = t["name"]
            if t_name.startswith("TASK_DQ_SCHEDULE_") and t_name not in managed_tasks:
                try:
                    session.sql(f"DROP TASK IF EXISTS {fw}.{t_name}").collect()
                    results["dropped"].append({"task": t_name})
                except Exception as e:
                    results["errors"].append({"task": t_name, "error": str(e)[:300]})
    except Exception as e:
        results["errors"].append({"step": "orphan_cleanup", "error": str(e)[:300]})

    results["reconciled_at"] = datetime.datetime.now().isoformat()
    results["total_schedules"] = len(schedules)
    return results
$$;

-- ============================================================================
-- RBAC: Grant task management privileges
-- ============================================================================

GRANT CREATE TASK ON SCHEMA {{framework_db}}.{{framework_schema}} TO ROLE DQ_DEVELOPER;
GRANT CREATE TASK ON SCHEMA {{framework_db}}.{{framework_schema}} TO ROLE DQ_APP_OWNER;

-- GRANT CREATE TASK ON SCHEMA DQ_FRAMEWORK.METADATA TO ROLE DQ_DEVELOPER;
-- GRANT CREATE TASK ON SCHEMA  DQ_FRAMEWORK.METADATA TO ROLE DQ_APP_OWNER;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE DQ_DEVELOPER;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE DQ_APP_OWNER;

-- ============================================================================
-- NOTE: After deploying this migration, call SP_MANAGE_DQ_SCHEDULES() to
-- reconcile any existing rows in DQ_SCHEDULE_CONFIG into live Snowflake Tasks.
-- Tasks are automatically managed — insert/update/delete rows in
-- DQ_SCHEDULE_CONFIG then call SP_MANAGE_DQ_SCHEDULES() to apply changes.
-- ============================================================================
