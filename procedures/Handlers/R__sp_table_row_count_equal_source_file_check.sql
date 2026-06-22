-- Source-file to CORE row-count recon handler (reads sync counts from an audit-control table)
USE DATABASE {{framework_db}};
USE SCHEMA {{framework_schema}};
CREATE OR REPLACE PROCEDURE SP_TABLE_ROW_COUNT_EQUAL_SOURCE_FILE_CHECK("RULE" VARIANT)
RETURNS NUMBER(38, 0)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python==*')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import datetime
import json


def main(session, RULE):
    proc = "SP_TABLE_ROW_COUNT_EQUAL_SOURCE_FILE_CHECK"
    run_id = int(RULE.get("DATASET_RUN_ID", -1))
    cfg_id = int(RULE.get("RULE_CONFIG_ID", -1))
    ds_id = int(RULE.get("DATASET_ID", -1))
    ds_name = RULE.get("DATASET_NAME")
    exp_id = RULE.get("EXPECTATION_ID")
    exp_nm = RULE.get("EXPECTATION_NAME")
    run_nm = RULE.get("RUN_NAME")
    dimension = RULE.get("DIMENSION") or "VOLUME"
    src_db, src_sch, src_tbl = RULE.get("DATABASE_NAME"), RULE.get("SCHEMA_NAME"), RULE.get("TABLE_NAME")

    kw = RULE.get("KWARGS") or {}
    if isinstance(kw, str):
        try:
            kw = json.loads(kw)
        except Exception:
            kw = {}

    def audit(step, status, msg=None, err=None, start=None):
        start = start or datetime.datetime.now()
        session.sql(
            "INSERT INTO DQ_RULE_AUDIT_LOG "
            "(DATASET_RUN_ID, RULE_CONFIG_ID, PROCEDURE_NAME, STEP_NAME, "
            "LOG_MESSAGE, START_TIMESTAMP, END_TIMESTAMP, STATUS, ERROR_MESSAGE) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP(), ?, ?)",
            params=[run_id, cfg_id, proc, step, msg, start, status, err]
        ).collect()

    # --- Config / return codes ---
    try:
        cfg = session.sql(
            "SELECT DQ_DB_NAME, DQ_SCHEMA_NAME, SUCCESS_CODE, FAILED_CODE, EXECUTION_ERROR "
            "FROM DQ_JOB_EXEC_CONFIG LIMIT 1"
        ).collect()[0]
        success_code = int(cfg["SUCCESS_CODE"])
        failed_code = int(cfg["FAILED_CODE"])
        error_code = int(cfg["EXECUTION_ERROR"])
        fw = f'{cfg["DQ_DB_NAME"]}.{cfg["DQ_SCHEMA_NAME"]}'
    except Exception as e:
        try:
            audit("CONFIG_LOADING", "FAILED", err=str(e))
        except Exception:
            pass
        return 400
    audit("CONFIG_LOADING", "COMPLETED", msg="Config loaded")

    # --- Parse params (with defaults matching the reference audit-control template) ---
    try:
        audit_table = kw.get("audit_control_table") or "PRISM_META_PROD.META.AUDIT_CONTROL"
        sync_level = kw.get("sync_level") or "SOURCE_TO_CORE"
        tgt_col = kw.get("target_table_col") or "TARGET_TABLE"
        src_cnt_col = kw.get("source_count_col") or "NUMBER_OF_RECORDS_SOURCE"
        core_cnt_col = kw.get("target_count_col") or "NUMBER_OF_RECORDS_TARGET"
        date_col = kw.get("sync_date_col") or "SYNC_START_DATE_TIME"

        # Target table to look up in the audit table (override or build from dataset)
        target_table = kw.get("target_table")
        if not target_table:
            if src_db and src_sch and src_tbl:
                target_table = f"{src_db}.{src_sch}.{src_tbl}"
            else:
                audit("RULE_PARSING", "FAILED",
                      err="Cannot resolve target table: provide kwargs.target_table or dataset db/schema/table")
                return failed_code
        audit("RULE_PARSING", "COMPLETED",
              msg=f"audit_table={audit_table}, sync_level={sync_level}, target={target_table}")
    except Exception as e:
        audit("RULE_PARSING", "FAILED", err=str(e))
        return error_code

    # --- Fetch latest SOURCE->CORE sync counts for the target table ---
    try:
        q = (
            f"SELECT TO_VARCHAR({src_cnt_col}::INT) AS SRC_VALUE, "
            f"       TO_VARCHAR({core_cnt_col}::INT) AS CORE_VALUE, "
            f"       CASE WHEN SPLIT_PART(SPLIT_PART({tgt_col}, '.', 3), '_', 1) = 'IPSEN' "
            f"            THEN 'ROSTER' "
            f"            ELSE SPLIT_PART(SPLIT_PART({tgt_col}, '.', 3), '_', 1) END AS SOURCE_LABEL "
            f"FROM {audit_table} "
            f"WHERE {tgt_col} ILIKE ? AND SYNC_LEVEL = ? "
            f"  AND TO_DATE({date_col}) = ("
            f"      SELECT MAX(TO_DATE({date_col})) FROM {audit_table} "
            f"      WHERE {tgt_col} ILIKE ? AND SYNC_LEVEL = ?) "
            f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {tgt_col} ORDER BY {date_col} DESC) = 1"
        )
        rows = session.sql(q, params=[target_table, sync_level, target_table, sync_level]).collect()
        if not rows:
            # No audit record found -> treat as failure (cannot confirm load)
            src_val, core_val, source_label, result = "NO_AUDIT_RECORD", "NO_AUDIT_RECORD", "UNKNOWN", "FAIL"
        else:
            src_val = rows[0]["SRC_VALUE"]
            core_val = rows[0]["CORE_VALUE"]
            source_label = rows[0]["SOURCE_LABEL"] or "UNKNOWN"
            result = "PASS" if src_val == core_val else "FAIL"
        overall_pass = (result == "PASS")
        audit("MAIN_QUERY", "COMPLETED",
              msg=f"target={target_table} src={src_val} core={core_val} result={result}")
    except Exception as e:
        audit("MAIN_QUERY", "FAILED", err=str(e))
        return error_code

    # --- Write recon detail (CORE layer; source-vs-core) ---
    try:
        session.sql(
            "INSERT INTO DQ_RECON_RESULTS "
            "(DATASET_RUN_ID, DATASET_ID, RULE_CONFIG_ID, LAYER, DATA_SOURCE, TABLE_NAME, "
            "VALIDATION_ON, SRC_VALUE, CORE_VALUE, CONFORMED_VALUE, CONSUMPTION_VALUE, "
            "RESULT, VALIDATION_LOGIC, AUDIT_TIMESTAMP) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, CURRENT_TIMESTAMP())",
            params=[run_id, ds_id, cfg_id, "CORE", str(source_label), str(target_table),
                    "SOURCE_TO_CORE_COUNT", str(src_val), str(core_val), result,
                    "WHEN SRC_VALUE = CORE_VALUE THEN PASS ELSE FAIL"]
        ).collect()
        audit("INSERT_RECON_RESULTS", "COMPLETED", msg="Recon detail stored")
    except Exception as e:
        audit("INSERT_RECON_RESULTS", "FAILED", err=str(e))
        return error_code

    # --- Summary into DQ_RULE_RESULTS ---
    try:
        results_obj = {"source_to_core": {"src": src_val, "core": core_val, "result": result}}
        try:
            mism = abs(int(src_val) - int(core_val))
            total = int(core_val)
        except Exception:
            mism, total = 0, 0
        session.sql(
            f"INSERT INTO {fw}.DQ_RULE_RESULTS "
            "(DATASET_RUN_ID, DATASET_ID, RULE_CONFIG_ID, EXPECTATION_ID, RUN_NAME, "
            "RUN_TIMESTAMP, DATASET_NAME, IS_SUCCESS, RESULTS, EXPECTATION_NAME, "
            "ELEMENT_COUNT, UNEXPECTED_COUNT, DIMENSION) "
            "SELECT ?, ?, ?, ?, ?, CURRENT_TIMESTAMP(), ?, ?, PARSE_JSON(?), ?, ?, ?, ?",
            params=[run_id, ds_id, cfg_id, exp_id, run_nm, ds_name,
                    overall_pass, json.dumps(results_obj), exp_nm, total, mism, dimension]
        ).collect()
        audit("INSERT_DQ_RESULTS_TABLE", "COMPLETED", msg="Result stored")
    except Exception as e:
        audit("INSERT_DQ_RESULTS_TABLE", "FAILED", err=str(e))
        return error_code

    return success_code if overall_pass else failed_code
$$;
