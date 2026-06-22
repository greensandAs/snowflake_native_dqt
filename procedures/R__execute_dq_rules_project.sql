-- Project-level DQ orchestrator: runs every dataset in a project, correlated by a shared BATCH_ID
-- Co-authored with CoCo
USE DATABASE {{framework_db}};
USE SCHEMA {{framework_schema}};
CREATE OR REPLACE PROCEDURE EXECUTE_DQ_RULES_PROJECT("P_PROJECT_ID" NUMBER(38, 0), "P_PARALLEL_JOBS" NUMBER(38, 0) DEFAULT 2)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python==*')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import json
import datetime


def main(session, P_PROJECT_ID, P_PARALLEL_JOBS):
    # Default framework location — must be fully qualified since EXECUTE AS CALLER
    # means the session context is the caller's, not the procedure's home schema.
    _DEFAULT_FQN = "DQ_FRAMEWORK.METADATA"

    # Read framework location from config (single source of truth)
    _cfg = session.sql(
        f"SELECT DQ_DB_NAME, DQ_SCHEMA_NAME, SUCCESS_CODE, FAILED_CODE, EXECUTION_ERROR "
        f"FROM {_DEFAULT_FQN}.DQ_JOB_EXEC_CONFIG LIMIT 1"
    ).collect()[0]
    fw = f"{_cfg['DQ_DB_NAME']}.{_cfg['DQ_SCHEMA_NAME']}"
    success_code = int(_cfg["SUCCESS_CODE"])
    failed_code = int(_cfg["FAILED_CODE"])
    error_code = int(_cfg["EXECUTION_ERROR"])
    started = datetime.datetime.now()

    # One batch id correlates all dataset runs of this project execution
    batch_id = int(session.sql(f"SELECT {fw}.BATCH_ID_SEQ.NEXTVAL").collect()[0][0])

    # Datasets in this project
    ds_rows = session.sql(
        f"SELECT DATASET_ID, DATASET_NAME FROM {fw}.DQ_DATASET "
        f"WHERE PROJECT_ID = {int(P_PROJECT_ID)} ORDER BY DATASET_ID"
    ).collect()

    summary = {
        "project_id": int(P_PROJECT_ID),
        "batch_id": batch_id,
        "datasets_total": len(ds_rows),
        "datasets_run": 0,
        "datasets_skipped": 0,
        "passed": 0, "failed": 0, "errored": 0,
        "details": [],
    }

    if not ds_rows:
        summary["status"] = "NO_DATASETS"
        return summary

    worst = success_code  # escalate to failed/error as we go

    for ds in ds_rows:
        ds_id = int(ds["DATASET_ID"])
        ds_name = ds["DATASET_NAME"]

        # Skip datasets with no active SQL rules (avoids a false EXECUTION_ERROR)
        active = int(session.sql(
            f"SELECT COUNT(*) AS C FROM {fw}.DQ_RULE_CONFIG "
            f"WHERE DATASET_ID = {ds_id} AND IS_ACTIVE = TRUE "
            f"AND (DQ_ENGINE IS NULL OR UPPER(DQ_ENGINE) = 'SQL')"
        ).collect()[0]["C"])
        if active == 0:
            summary["datasets_skipped"] += 1
            summary["details"].append({"dataset_id": ds_id, "dataset_name": ds_name,
                                       "status": "SKIPPED_NO_RULES"})
            continue

        # Capture the current max run ID BEFORE calling the master,
        # so we only stamp BATCH_ID on a genuinely new run.
        pre_max_run = int(session.sql(
            f"SELECT COALESCE(MAX(DATASET_RUN_ID), 0) AS M "
            f"FROM {fw}.DQ_DATASET_RUN_LOG WHERE DATASET_ID = {ds_id}"
        ).collect()[0]["M"])

        # Run the dataset (rules parallelized inside the master)
        try:
            code = int(session.call(f"{fw}.EXECUTE_DQ_RULES_MASTER", ds_id, int(P_PARALLEL_JOBS)))
        except Exception as e:
            code = error_code
            summary["details"].append({"dataset_id": ds_id, "dataset_name": ds_name,
                                       "status": "CALL_EXCEPTION", "error": str(e)[:500]})

        # Stamp the BATCH_ID only if a NEW run was created (avoids corrupting older runs)
        try:
            post_max_run = int(session.sql(
                f"SELECT COALESCE(MAX(DATASET_RUN_ID), 0) AS M "
                f"FROM {fw}.DQ_DATASET_RUN_LOG WHERE DATASET_ID = {ds_id}"
            ).collect()[0]["M"])
            if post_max_run > pre_max_run:
                session.sql(
                    f"UPDATE {fw}.DQ_DATASET_RUN_LOG SET BATCH_ID = {batch_id} "
                    f"WHERE DATASET_ID = {ds_id} AND DATASET_RUN_ID = {post_max_run}"
                ).collect()
        except Exception as e:
            summary.setdefault("_warnings", []).append(
                f"BATCH_ID stamp failed for dataset {ds_id}: {str(e)[:200]}"
            )

        summary["datasets_run"] += 1
        if code == success_code:
            summary["passed"] += 1
            status = "PASS"
        elif code == failed_code:
            summary["failed"] += 1
            status = "FAIL"
            worst = failed_code if worst != error_code else worst
        else:
            summary["errored"] += 1
            status = "ERROR"
            worst = error_code
        # only append if not already appended by exception path
        if not (summary["details"] and summary["details"][-1].get("dataset_id") == ds_id
                and summary["details"][-1].get("status") == "CALL_EXCEPTION"):
            summary["details"].append({"dataset_id": ds_id, "dataset_name": ds_name,
                                       "status": status, "code": code})

    summary["status"] = ("ERROR" if worst == error_code
                         else "FAILURE" if worst == failed_code
                         else "SUCCESS")
    summary["overall_code"] = worst

    # Persist project-level summary row
    try:
        run_time = (datetime.datetime.now() - started).total_seconds()
        success_pct = (summary["passed"] * 100.0 / summary["datasets_run"]) if summary["datasets_run"] else 0
        session.sql(
            f"INSERT INTO {fw}.DQ_PROJECT_RUN_LOG "
            "(BATCH_ID, PROJECT_ID, DATASETS_TOTAL, DATASETS_RUN, DATASETS_SKIPPED, "
            "PASSED, FAILED, ERRORED, RUN_STATUS, SUCCESS_PERCENT, RUN_TIME, CREATED_BY) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_USER())",
            params=[batch_id, int(P_PROJECT_ID), summary["datasets_total"], summary["datasets_run"],
                    summary["datasets_skipped"], summary["passed"], summary["failed"],
                    summary["errored"], summary["status"], success_pct, run_time]
        ).collect()
    except Exception as e:
        summary["_log_error"] = str(e)[:300]

    return summary
$$;
