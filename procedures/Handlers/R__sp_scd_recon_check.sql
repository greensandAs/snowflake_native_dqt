USE DATABASE DQ_FRAMEWORK;
USE SCHEMA METADATA;
CREATE OR REPLACE PROCEDURE SP_SCD_RECON_CHECK("RULE" VARIANT)
RETURNS NUMBER(38, 0)
LANGUAGE PYTHON
RUNTIME_VERSION = ''3.11''
PACKAGES = (''snowflake-snowpark-python==*'')
HANDLER = ''main''
EXECUTE AS CALLER
AS ''
import datetime
import json


def main(session, RULE):
    proc_name = "SP_SCD_RECON_CHECK"
    run_id = int(RULE.get("DATASET_RUN_ID", -1))
    cfg_id = int(RULE.get("RULE_CONFIG_ID", -1))
    dataset_id = int(RULE.get("DATASET_ID", -1))
    dataset_name = RULE.get("DATASET_NAME")
    expectation_id = RULE.get("EXPECTATION_ID")
    expectation_name = RULE.get("EXPECTATION_NAME")
    run_name = RULE.get("RUN_NAME")
    dimension = RULE.get("DIMENSION") or "RECONCILIATION"

    # KWARGS arrives as a nested object (dict) or a JSON string
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
            params=[run_id, cfg_id, proc_name, step, msg, start, status, err]
        ).collect()

    # --- Load framework config / return codes ---
    try:
        cfg = session.sql(
            "SELECT DQ_DB_NAME, DQ_SCHEMA_NAME, SUCCESS_CODE, FAILED_CODE, EXECUTION_ERROR "
            "FROM DQ_JOB_EXEC_CONFIG LIMIT 1"
        ).collect()[0]
        success_code = int(cfg["SUCCESS_CODE"])
        failed_code = int(cfg["FAILED_CODE"])
        error_code = int(cfg["EXECUTION_ERROR"])
        fw = f''{cfg["DQ_DB_NAME"]}.{cfg["DQ_SCHEMA_NAME"]}''
    except Exception as e:
        try:
            audit("CONFIG_LOADING", "FAILED", err=str(e))
        except Exception:
            pass
        return 400

    audit("CONFIG_LOADING", "COMPLETED", msg="Config loaded")

    # --- Parse recon parameters ---
    try:
        core_table = kw.get("core_table")
        conformed_table = kw.get("conformed_table")
        source_label = kw.get("source_label") or "MDM"
        layer = kw.get("layer") or "CONFORMED"
        core_date = kw.get("core_insert_date_col") or "INSERT_DATE_TIME"
        conf_date = kw.get("conformed_update_date_col") or "UPDATE_DATE_TIME"
        flag_col = kw.get("active_flag_col") or "IS_ACTIVE"
        active_value = kw.get("active_value", "Y")
        inactive_value = kw.get("inactive_value", "N")
        scd_type = int(kw.get("scd_type", 2))

        partition_keys = kw.get("partition_keys") or []
        compare_cols = kw.get("compare_cols") or partition_keys
        if isinstance(partition_keys, str):
            partition_keys = [c.strip() for c in partition_keys.split(",") if c.strip()]
        if isinstance(compare_cols, str):
            compare_cols = [c.strip() for c in compare_cols.split(",") if c.strip()]
        if not partition_keys:
            partition_keys = compare_cols

        if not core_table or not conformed_table or not compare_cols:
            audit("PARAM_PARSING", "FAILED",
                  err="core_table, conformed_table and compare_cols/partition_keys are required")
            return failed_code

        keys_csv = ", ".join(partition_keys)
        trimmed = ", ".join([f"COALESCE(TRIM({c}), ''NA'')" for c in compare_cols])
        audit("PARAM_PARSING", "COMPLETED",
              msg=f"core={core_table}, conformed={conformed_table}, keys={keys_csv}")
    except Exception as e:
        audit("PARAM_PARSING", "FAILED", err=str(e))
        return error_code

    # --- Helper: run a count comparison (flag optional → SCD1 omits it) ---
    def reconcile(validation_on, flag_value=None):
        conf_flag = f" AND {flag_col} = ?" if flag_value is not None else ""
        core_dedup = (
            f"SELECT * FROM {core_table} "
            f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {keys_csv} "
            f"ORDER BY {core_date} DESC) = 1"
        )
        core_sql = (
            f"SELECT COUNT(*)::INT AS CNT FROM ({core_dedup}) "
            f"WHERE {core_date} = (SELECT MAX({core_date}) FROM {core_table}) "
            f"AND ({trimmed}) IN ("
            f"  SELECT {trimmed} FROM {conformed_table} "
            f"  WHERE {conf_date} = (SELECT MAX({conf_date}) FROM {conformed_table})"
            f"{conf_flag})"
        )
        conf_sql = (
            f"SELECT COUNT(*)::INT AS CNT FROM {conformed_table} "
            f"WHERE {conf_date} = (SELECT MAX({conf_date}) FROM {conformed_table})"
            f"{conf_flag}"
        )
        bind = [flag_value] if flag_value is not None else []
        core_val = int(session.sql(core_sql, params=bind).collect()[0]["CNT"])
        conf_val = int(session.sql(conf_sql, params=bind).collect()[0]["CNT"])
        result = "PASS" if core_val == conf_val else "FAIL"
        logic = "WHEN CORE_VALUE = CONFORMED_VALUE THEN PASS ELSE FAIL"
        session.sql(
            "INSERT INTO DQ_RECON_RESULTS "
            "(DATASET_RUN_ID, DATASET_ID, RULE_CONFIG_ID, LAYER, DATA_SOURCE, TABLE_NAME, "
            "VALIDATION_ON, SRC_VALUE, CORE_VALUE, CONFORMED_VALUE, CONSUMPTION_VALUE, "
            "RESULT, VALIDATION_LOGIC, AUDIT_TIMESTAMP) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?, CURRENT_TIMESTAMP())",
            params=[run_id, dataset_id, cfg_id, layer, source_label, conformed_table,
                    validation_on, str(core_val), str(conf_val), result, logic]
        ).collect()
        return core_val, conf_val, result

    # --- Run reconciliation (SCD1 = single total count · SCD2 = active + inactive) ---
    try:
        if scd_type == 1:
            t_core, t_conf, t_res = reconcile("TOTAL_COUNT", None)
            overall_pass = (t_res == "PASS")
            total = t_core
            mismatch = abs(t_core - t_conf)
            results_obj = {"total": {"core": t_core, "conformed": t_conf, "result": t_res}}
            audit("RECON_EXECUTION", "COMPLETED",
                  msg=f"SCD1 TOTAL core={t_core}/conf={t_conf} {t_res}")
        else:
            a_core, a_conf, a_res = reconcile("ACTIVE_COUNT", active_value)
            i_core, i_conf, i_res = reconcile("INACTIVE_COUNT", inactive_value)
            overall_pass = (a_res == "PASS") and (i_res == "PASS")
            total = a_core + i_core
            mismatch = abs(a_core - a_conf) + abs(i_core - i_conf)
            results_obj = {
                "active": {"core": a_core, "conformed": a_conf, "result": a_res},
                "inactive": {"core": i_core, "conformed": i_conf, "result": i_res},
            }
            audit("RECON_EXECUTION", "COMPLETED",
                  msg=f"SCD2 ACTIVE core={a_core}/conf={a_conf} {a_res}; "
                      f"INACTIVE core={i_core}/conf={i_conf} {i_res}")
    except Exception as e:
        audit("RECON_EXECUTION", "FAILED", err=str(e))
        return error_code

    # --- Summary into DQ_RULE_RESULTS so it shows in standard dashboards ---
    try:
        session.sql(
            f"INSERT INTO {fw}.DQ_RULE_RESULTS "
            "(DATASET_RUN_ID, DATASET_ID, RULE_CONFIG_ID, EXPECTATION_ID, RUN_NAME, "
            "RUN_TIMESTAMP, DATASET_NAME, IS_SUCCESS, RESULTS, EXPECTATION_NAME, "
            "ELEMENT_COUNT, UNEXPECTED_COUNT, DIMENSION) "
            "SELECT ?, ?, ?, ?, ?, CURRENT_TIMESTAMP(), ?, ?, PARSE_JSON(?), ?, ?, ?, ?",
            params=[run_id, dataset_id, cfg_id, expectation_id, run_name, dataset_name,
                    overall_pass, json.dumps(results_obj), expectation_name,
                    total, mismatch, dimension]
        ).collect()
        audit("INSERT_DQ_RESULTS_TABLE", "COMPLETED", msg="Recon summary stored")
    except Exception as e:
        audit("INSERT_DQ_RESULTS_TABLE", "FAILED", err=str(e))
        return error_code

    return success_code if overall_pass else failed_code
'';
