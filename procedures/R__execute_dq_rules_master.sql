-- DQ rules master orchestrator: full + selective (Option B) rule execution with RUN_SCOPE tracking
-- Co-authored with CoCo
USE DATABASE {{framework_db}};
USE SCHEMA {{framework_schema}};
CREATE OR REPLACE PROCEDURE EXECUTE_DQ_RULES_MASTER("P_DATASET_ID" NUMBER(38, 0), "P_PARALLEL_JOBS" NUMBER(38, 0) DEFAULT 2, "P_RULE_CONFIG_IDS" VARCHAR DEFAULT NULL)
RETURNS NUMBER(38, 0)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python==*')
HANDLER = 'main'
EXECUTE AS CALLER
AS '
import snowflake.snowpark as snowpark
import datetime
import json
import re
from json.decoder import JSONDecodeError

def main(session: snowpark.Session, P_DATASET_ID, P_PARALLEL_JOBS, P_RULE_CONFIG_IDS=None):

    # --- Helper to quote SQL identifiers ---
    def q_ident(name: str) -> str:
        """Quotes an identifier for safe SQL use."""
        if name is None: return "NULL"
        name = name.strip(''"'') 
        return ''"'' + name.replace(''"'', ''""'') + ''"''

    # --- Framework location: read from DQ_JOB_EXEC_CONFIG (single source of truth) ---
    # Must use fully-qualified reference because EXECUTE AS CALLER means the session
    # context is the caller''s (e.g. USER$ASLAM.PUBLIC), not the procedure''s home schema.
    _DEFAULT_FQN = "DQ_FRAMEWORK.METADATA"
    try:
        _cfg_row = session.sql(
            f"SELECT DQ_DB_NAME, DQ_SCHEMA_NAME FROM {_DEFAULT_FQN}.DQ_JOB_EXEC_CONFIG LIMIT 1"
        ).collect()[0]
        FRAMEWORK_DB = q_ident(_cfg_row["DQ_DB_NAME"])
        FRAMEWORK_SCHEMA = q_ident(_cfg_row["DQ_SCHEMA_NAME"])
    except Exception:
        FRAMEWORK_DB = q_ident("DQ_FRAMEWORK")
        FRAMEWORK_SCHEMA = q_ident("METADATA")
    FRAMEWORK_PATH = f"{FRAMEWORK_DB}.{FRAMEWORK_SCHEMA}"

    # Pin the active schema so unqualified refs in handlers resolve to the framework
    try:
        session.sql(f"USE SCHEMA {FRAMEWORK_PATH}").collect()
    except Exception:
        pass

    # --- Define Stage (Ensure @ is present for file operations) ---
    DQ_STAGE_NAME = f"@{FRAMEWORK_PATH}.DQ_FAILURES_STAGE" 

    def parallel_worker(worker_session, rule_config, config):
        """Execute a single SQL DQ rule and return its execution status and audit data."""
        start_time = datetime.datetime.now()
        
        try:
            sp_name = rule_config.get("SP_NAME")
            if not sp_name:
                end_time = datetime.datetime.now()
                return {
                    "status": "ERROR",
                    "code": config.get("EXECUTION_ERROR", 400),
                    "audit_log": {
                        "rule_config_id": rule_config.get("RULE_CONFIG_ID"),
                        "status": "ERROR",
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": (end_time - start_time).total_seconds(),
                        "error_message": f"Missing SP_NAME for rule {rule_config.get(''RULE_CONFIG_ID'')}"
                    }
                }
                
            sp_path = f"{FRAMEWORK_PATH}.{q_ident(sp_name)}"
            result = worker_session.call(sp_path, rule_config)
            
            end_time = datetime.datetime.now()
            result_status = "SUCCESS" if str(result) == str(config["SUCCESS_CODE"]) else "FAILURE" if str(result) == str(config["FAILED_CODE"]) else "ERROR"
            
            return {
                "status": result_status,
                "code": result,
                "audit_log": {
                    "rule_config_id": rule_config.get("RULE_CONFIG_ID"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": (end_time - start_time).total_seconds()
                }
            }
        except Exception as e:
            end_time = datetime.datetime.now()
            return {
                "status": "ERROR",
                "code": config.get("EXECUTION_ERROR", 400),
                "audit_log": {
                    "rule_config_id": rule_config.get("RULE_CONFIG_ID"),
                    "status": "ERROR",
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": (end_time - start_time).total_seconds(),
                    "error_message": f"Error during call to {sp_name}: {str(e)}"
                }
            }

    def execute_rules_async(session, rule_configs, config, parallel_jobs):
        """
        Execute rules using Snowflake async queries with batched concurrency.
        Fires up to `parallel_jobs` rules at a time, waits for the batch to complete,
        then fires the next batch. This prevents overwhelming the warehouse while
        still achieving true server-side parallelism within each batch.
        """

        def _dispatch_one(rc):
            """Fire a single rule async. Returns (job_info_dict)."""
            sp_name = rc.get("SP_NAME")
            if not sp_name:
                return {
                    "rule_config": rc,
                    "async_job": None,
                    "immediate_result": {
                        "status": "ERROR",
                        "code": config.get("EXECUTION_ERROR", 400),
                        "audit_log": {
                            "rule_config_id": rc.get("RULE_CONFIG_ID"),
                            "status": "ERROR",
                            "start_time": datetime.datetime.now(),
                            "end_time": datetime.datetime.now(),
                            "duration": 0,
                            "error_message": f"Missing SP_NAME for rule {rc.get(''RULE_CONFIG_ID'')}"
                        }
                    }
                }

            sp_path = f"{FRAMEWORK_PATH}.{q_ident(sp_name)}"
            rule_json = json.dumps(rc).replace("''", "\\''")
            call_sql = f"CALL {sp_path}(PARSE_JSON(''{rule_json}''))"
            start_time = datetime.datetime.now()

            try:
                async_job = session.sql(call_sql).collect_nowait()
                return {
                    "rule_config": rc,
                    "async_job": async_job,
                    "start_time": start_time,
                    "immediate_result": None
                }
            except Exception as e:
                return {
                    "rule_config": rc,
                    "async_job": None,
                    "immediate_result": {
                        "status": "ERROR",
                        "code": config.get("EXECUTION_ERROR", 400),
                        "audit_log": {
                            "rule_config_id": rc.get("RULE_CONFIG_ID"),
                            "status": "ERROR",
                            "start_time": start_time,
                            "end_time": datetime.datetime.now(),
                            "duration": 0,
                            "error_message": f"Async dispatch failed for {sp_name}: {str(e)}"
                        }
                    }
                }

        def _collect_one(job_info):
            """Collect result from one async job. Returns result dict."""
            if job_info["immediate_result"]:
                return job_info["immediate_result"]

            rc = job_info["rule_config"]
            async_job = job_info["async_job"]
            start_time = job_info["start_time"]
            sp_name = rc.get("SP_NAME", "UNKNOWN")

            try:
                query_result = async_job.result()
                end_time = datetime.datetime.now()

                if query_result and len(query_result) > 0:
                    result_code = query_result[0][0]
                else:
                    result_code = config.get("EXECUTION_ERROR", 400)

                result_status = ("SUCCESS" if str(result_code) == str(config["SUCCESS_CODE"])
                                 else "FAILURE" if str(result_code) == str(config["FAILED_CODE"])
                                 else "ERROR")

                return {
                    "status": result_status,
                    "code": result_code,
                    "audit_log": {
                        "rule_config_id": rc.get("RULE_CONFIG_ID"),
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": (end_time - start_time).total_seconds()
                    }
                }
            except Exception as e:
                end_time = datetime.datetime.now()
                return {
                    "status": "ERROR",
                    "code": config.get("EXECUTION_ERROR", 400),
                    "audit_log": {
                        "rule_config_id": rc.get("RULE_CONFIG_ID"),
                        "status": "ERROR",
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": (end_time - start_time).total_seconds(),
                        "error_message": f"Async collect failed for {sp_name}: {str(e)}"
                    }
                }

        # --- Batched execution: fire parallel_jobs at a time, wait, repeat ---
        all_results = []
        batch_size = max(1, int(parallel_jobs))

        for batch_start in range(0, len(rule_configs), batch_size):
            batch = rule_configs[batch_start:batch_start + batch_size]

            # Dispatch entire batch (non-blocking)
            batch_jobs = [_dispatch_one(rc) for rc in batch]

            # Collect entire batch (blocks until all in this batch finish)
            for job_info in batch_jobs:
                all_results.append(_collect_one(job_info))

        return all_results

    def format_for_sql(val, is_string=False):
        if val is None:
            return "NULL"
        if isinstance(val, datetime.datetime):
            val = val.strftime("%Y-%m-%d %H:%M:%S.%f")
            is_string = True
        if is_string:
            escaped_val = str(val).replace("''", "''''")
            return f"''{escaped_val}''"
        return str(val)

    def log_and_return(session, config, master_audit_logs, return_code):
        audit_log_path = f"{config[''DQ_DB_NAME'']}.{config[''DQ_SCHEMA_NAME'']}.DQ_RULE_AUDIT_LOG"
        if master_audit_logs:
            values_list = []
            for log in master_audit_logs:
                run_id_val = format_for_sql(log[0])
                proc_name = format_for_sql(log[1], is_string=True)
                step_name = format_for_sql(log[2], is_string=True)
                log_msg = format_for_sql(log[3], is_string=True)
                start_ts = format_for_sql(log[4], is_string=True)
                end_ts = format_for_sql(log[5], is_string=True)
                status = format_for_sql(log[6], is_string=True)
                error_message = format_for_sql(log[7], is_string=True)
                values_list.append(f"({run_id_val}, {proc_name}, {step_name}, {log_msg}, {start_ts}, {end_ts}, {status}, {error_message})")
            
            insert_sql = f"""
                INSERT INTO {audit_log_path}
                (DATASET_RUN_ID, PROCEDURE_NAME, STEP_NAME, LOG_MESSAGE, START_TIMESTAMP, END_TIMESTAMP, STATUS, ERROR_MESSAGE)
                VALUES {", ".join(values_list)}
            """
            session.sql(insert_sql).collect()
        return return_code

    master_start_time = datetime.datetime.now()
    master_audit_logs = []
    config = {}
    
    run_id_seq_path = f"{FRAMEWORK_PATH}.RUN_ID_SEQ.NEXTVAL"
    run_id = session.sql(f"SELECT {run_id_seq_path}").collect()[0][0]

    try:
        step_start_time = datetime.datetime.now()
        config_table_path = f"{FRAMEWORK_PATH}.DQ_JOB_EXEC_CONFIG"
        
        config_sql = f"""
            SELECT SUCCESS_CODE, FAILED_CODE, EXECUTION_ERROR, DQ_DB_NAME, DQ_SCHEMA_NAME
            FROM {config_table_path} LIMIT 1
        """
        config_result = session.sql(config_sql).collect()
        step_end_time = datetime.datetime.now()
        
        if not config_result:
            config = {
                "DQ_DB_NAME": FRAMEWORK_DB, 
                "DQ_SCHEMA_NAME": FRAMEWORK_SCHEMA, 
                "EXECUTION_ERROR": 404
            }
            master_audit_logs.append((0, "EXECUTE_DQ_RULES_MASTER", "CONFIG_LOADING", "Configuration not found in DQ_JOB_EXEC_CONFIG", step_start_time, step_end_time, "FAILED", "Configuration not found in DQ_JOB_EXEC_CONFIG"))
            return log_and_return(session, config, master_audit_logs, 404)
            
        config = config_result[0].as_dict()
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "CONFIG_LOADING","Captured the configuartion details" ,step_start_time, step_end_time, "COMPLETED", None))
    except Exception as e:
        config = {
            "DQ_DB_NAME": FRAMEWORK_DB, 
            "DQ_SCHEMA_NAME": FRAMEWORK_SCHEMA, 
            "EXECUTION_ERROR": 404
        }
        master_audit_logs.append((0, "EXECUTE_DQ_RULES_MASTER", "CONFIG_LOADING", f"Failed to retrieve config: {str(e)}", step_start_time, datetime.datetime.now(), "FAILED", f"Failed to retrieve config: {str(e)}"))
        return log_and_return(session, config, master_audit_logs, 404)

    parallel_jobs = max(1, P_PARALLEL_JOBS or 2)

    step_start_time = datetime.datetime.now()
    try:
        dataset_table_path = f"{FRAMEWORK_PATH}.DQ_DATASET"
        data_asset_df = session.sql(f"SELECT DATASET_ID, DATASET_NAME, DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, DATASET_TYPE, CUSTOM_SQL FROM {dataset_table_path} WHERE DATASET_ID = {P_DATASET_ID}").collect()
        step_end_time = datetime.datetime.now()
        if not data_asset_df:
            master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "VALIDATE DATASET", f"Dataset ID {P_DATASET_ID} not found.", step_start_time, step_end_time, "FAILED", f"Dataset ID {P_DATASET_ID} not found."))
            return log_and_return(session, config, master_audit_logs, int(config["EXECUTION_ERROR"]))
        data_asset = data_asset_df[0].as_dict()
        db_name, schema_name, table_name, dataset_type, custom_sql = data_asset["DATABASE_NAME"], data_asset["SCHEMA_NAME"], data_asset["TABLE_NAME"], data_asset["DATASET_TYPE"], data_asset["CUSTOM_SQL"]
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "VALIDATE DATASET","Captured the dataset details", step_start_time, step_end_time, "COMPLETED", None))
    except Exception as e:
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "VALIDATE DATASET", f"Error validating dataset: {str(e)}", step_start_time, datetime.datetime.now(), "FAILED", f"Error validating dataset: {str(e)}"))
        return log_and_return(session, config, master_audit_logs, int(config["EXECUTION_ERROR"]))
    
    # --- Parse selective rule list (Option B). NULL/empty => FULL run. ---
    selected_rule_ids = []
    run_scope = "FULL"
    if P_RULE_CONFIG_IDS:
        try:
            selected_rule_ids = [int(x.strip()) for x in str(P_RULE_CONFIG_IDS).split(",") if str(x).strip()]
        except Exception:
            selected_rule_ids = []
        if selected_rule_ids:
            run_scope = "SELECTIVE"

    step_start_time = datetime.datetime.now()
    try:
        rules_config_path = f"{FRAMEWORK_PATH}.DQ_RULE_CONFIG"
        exp_master_path = f"{FRAMEWORK_PATH}.DQ_EXPECTATION_MASTER"
        handler_map_path = f"{FRAMEWORK_PATH}.DQ_EXPECTATION_HANDLER_MAPPING"
        
        rule_id_filter = ""
        if selected_rule_ids:
            ids_csv = ", ".join(str(i) for i in selected_rule_ids)
            rule_id_filter = f" AND cc.RULE_CONFIG_ID IN ({ids_csv})"

        # Updated SQL to remove GE specific checks, assuming SQL engine is the default or filtering explicitly for SQL
        rules_sql = f"""
            SELECT cc.RULE_CONFIG_ID, cc.CHECK_TYPE, COALESCE(cc.COLUMN_NAME, '''') AS COLUMN_NAME, COALESCE(cc.EXPECTATION_ID, ''0'') AS EXPECTATION_ID, cc.EXPECTATION_NAME, cc.KWARGS, cc.DQ_ENGINE, cc.DIMENSION, COALESCE(cc.ERROR_FLAG, TRUE) AS ERROR_FLAG, ehm.SP_NAME 
            FROM {rules_config_path} cc 
            LEFT JOIN {exp_master_path} em ON cc.expectation_id = em.expectation_id 
            LEFT JOIN {handler_map_path} ehm ON UPPER(em.VALIDATION_NAME) = UPPER(ehm.EXPECTATION_TYPE) AND ehm.IS_ACTIVE = TRUE 
            WHERE cc.DATASET_ID = {data_asset[''DATASET_ID'']} AND SP_NAME IS NOT NULL AND cc.IS_ACTIVE = TRUE AND (cc.DQ_ENGINE IS NULL OR UPPER(cc.DQ_ENGINE) = ''SQL''){rule_id_filter}
        """
        rules_df = session.sql(rules_sql).to_pandas()
        step_end_time = datetime.datetime.now()
    except Exception as e:
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "RULES_FETCHING", f"Error fetching rules: {str(e)}", step_start_time, datetime.datetime.now(), "FAILED", f"Error fetching rules: {str(e)}"))
        return log_and_return(session, config, master_audit_logs, int(config["EXECUTION_ERROR"]))
    
    if rules_df.empty:
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "RULES_FETCHING", f"No SQL rules found for dataset_id {P_DATASET_ID}", step_start_time, step_end_time, "FAILED", f"No SQL rules found for dataset_id {P_DATASET_ID}"))
        return log_and_return(session, config, master_audit_logs, int(config["EXECUTION_ERROR"]))
    
    master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "RULES_FETCHING", f"Captured {len(rules_df)} SQL rules for dataset_id {P_DATASET_ID}", step_start_time, step_end_time, "COMPLETED", None))

    success_count, failure_count, error_count, total_rules = 0, 0, 0, 0
    error_rule_ids = []
    
    sql_rules_to_run = rules_df
    
    if not sql_rules_to_run.empty:
        step_start_time = datetime.datetime.now()
        rule_configs = []
        for _, rule in sql_rules_to_run.iterrows():
            kwargs_str, kwargs_obj = rule["KWARGS"], {}
            if kwargs_str:
                try: kwargs_obj = json.loads(kwargs_str)
                except JSONDecodeError as e:
                    master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "KWARGS_PARSING", f"JSON parsing failed for rule {rule[''RULE_CONFIG_ID'']}: {str(e)}", datetime.datetime.now(), datetime.datetime.now(), "FAILED", f"JSON parsing failed for rule {rule[''RULE_CONFIG_ID'']}: {str(e)}"))
                    error_count += 1
                    continue
            rule_configs.append({
                "DATASET_RUN_ID": run_id, "DATASET_ID": data_asset["DATASET_ID"], "RULE_CONFIG_ID": int(rule["RULE_CONFIG_ID"]), "EXPECTATION_ID": rule["EXPECTATION_ID"], "DATABASE_NAME": db_name, "SCHEMA_NAME": schema_name, "TABLE_NAME": table_name, "COLUMN_NAME": rule["COLUMN_NAME"], "EXPECTATION_NAME": rule["EXPECTATION_NAME"], "RUN_NAME": f"DQ_RUN_{run_id}", "DATASET_NAME": data_asset["DATASET_NAME"], "KWARGS": kwargs_obj, "SP_NAME": rule["SP_NAME"], "DATASET_TYPE": dataset_type, "CUSTOM_SQL": custom_sql, "DIMENSION":rule["DIMENSION"], "ERROR_FLAG": bool(rule["ERROR_FLAG"])
            })

        if rule_configs:
            if P_PARALLEL_JOBS is None or P_PARALLEL_JOBS <= 0:
                parallel_jobs = min(len(rule_configs), 10)
            else:
                parallel_jobs = P_PARALLEL_JOBS
                
            parallel_jobs = min(parallel_jobs, 30)
            
            try:
                # Attempt async execution for true server-side parallelism.
                # Each CALL runs in its own server-side execution context.
                # Falls back to sequential if collect_nowait is unavailable.
                results_from_parallel_execution = execute_rules_async(session, rule_configs, config, parallel_jobs)
            except (AttributeError, TypeError):
                # Fallback: collect_nowait not available in this Snowpark version.
                # Run sequentially — still safe and correct.
                results_from_parallel_execution = []
                for rc in rule_configs:
                    results_from_parallel_execution.append(parallel_worker(session, rc, config))
            except Exception as e:
                master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "PARALLEL_EXECUTION", f"Async execution failed, falling back to sequential: {str(e)}", step_start_time, datetime.datetime.now(), "WARNING", str(e)))
                # Fallback to sequential on any unexpected error
                results_from_parallel_execution = []
                for rc in rule_configs:
                    results_from_parallel_execution.append(parallel_worker(session, rc, config))

            failed_rule_ids = []
            
            try:
                for result in results_from_parallel_execution:
                    total_rules += 1
                    if result["status"] == "SUCCESS":
                        success_count += 1
                    elif result["status"] == "FAILURE":
                        failure_count += 1
                        if "audit_log" in result and "rule_config_id" in result["audit_log"]:
                            failed_rule_ids.append(result["audit_log"]["rule_config_id"])
                    else: 
                        error_count += 1
                        if "audit_log" in result and "rule_config_id" in result["audit_log"]:
                            error_rule_ids.append(result["audit_log"]["rule_config_id"])
            except Exception as e:
                master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "RESULT_AGGREGATION", f"Error aggregating results: {str(e)}", step_start_time, datetime.datetime.now(), "FAILED", f"Error aggregating results: {str(e)}"))
                error_count += 1
        
        step_end_time = datetime.datetime.now()
        
        if error_count > 0:
            error_ids_str = ", ".join(map(str, error_rule_ids))
            log_message = f"Rule have Execution error, Please check step of invidulal Rules"
            log_status = "ERROR"
            error_message = f"Execution completed with Execution errors for dataset_id {P_DATASET_ID}. {error_count} rule(s) failed with an error. Errored Rules: {error_ids_str}."
        elif failure_count > 0 and success_count > 0:
            failed_ids_str = ", ".join(map(str, failed_rule_ids))
            log_message = f"Execution completed with partial success for dataset_id {P_DATASET_ID}. {success_count} rule(s) succeeded and {failure_count} rule(s) failed. Failed Rules: {failed_ids_str}."
            log_status = "PARTIAL_SUCCESS"
            error_message = None
        elif success_count > 0 and failure_count == 0 and error_count == 0:
            log_message = f"All {success_count} rules for dataset_id {P_DATASET_ID} executed successfully."
            log_status = "SUCCESS"
            error_message = None
        else: 
            failed_ids_str = ", ".join(map(str, failed_rule_ids))
            log_message = f"All {failure_count} rules for dataset_id {P_DATASET_ID} failed. Failed Rules: {failed_ids_str}."
            log_status = "FAILED"
            error_message = None
        
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "SQL_EXECUTION", log_message, step_start_time, step_end_time, log_status, error_message))

    # =========================================================================
    # DATASET-LEVEL CONSOLIDATED FILE GENERATION 
    # =========================================================================
    file_generation_error = False
    final_file_name = ''NULL''
    source_sql_text = None
    failure_view_name = None

    # Only build the failure pivot view when a row-level failure table actually exists.
    # Aggregate / reconciliation checks (e.g. row-count recon) write to DQ_RECON_RESULTS, not <DATASET>_DQ_FAILURE.
    fail_tbl_exists = False
    clean_dataset_name = re.sub(r''[^a-zA-Z0-9]'', ''_'', data_asset["DATASET_NAME"])
    if failure_count > 0:
        try:
            fail_tbl_exists = session.sql(
                f"SELECT COUNT(*) AS C FROM {q_ident(config[''DQ_DB_NAME''])}.INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = ''DQ_ERRORS'' AND TABLE_NAME = ''{clean_dataset_name.upper()}_DQ_FAILURE''"
            ).collect()[0]["C"] > 0
        except Exception:
            fail_tbl_exists = False

    if failure_count > 0 and fail_tbl_exists:
        step_start_time = datetime.datetime.now()
        try:
            # 1. Prepare Table Names and Paths
            clean_dataset_name = re.sub(r''[^a-zA-Z0-9]'', ''_'', data_asset["DATASET_NAME"])
            failure_table_name = f"{q_ident(config[''DQ_DB_NAME''])}.{q_ident(''DQ_ERRORS'')}.{q_ident(clean_dataset_name + ''_DQ_FAILURE'')}"

            # Fetch Metadata for dynamic headers
            rules_config_table = f"{FRAMEWORK_PATH}.DQ_RULE_CONFIG"
            exp_master_table = f"{FRAMEWORK_PATH}.DQ_EXPECTATION_MASTER"

            all_rules_metadata = session.sql(f"""
                SELECT DISTINCT
                    cc.RULE_CONFIG_ID,
                    cc.EXPECTATION_ID,
                    cc.KWARGS,
                    COALESCE(UPPER(REPLACE(cc.COLUMN_NAME, '' '', ''_'')), ''TABLE'') as COL_NAME,
                    COALESCE(em.CHECK_TYPE, ''UNCATEGORIZED'') as CATEGORY,
                    COALESCE(em.DIMENSION, ''UNCATEGORIZED'') as DIMENSION,
                    COALESCE(em.CHECK_LEVEL, ''ROW'') as CHECK_LEVEL
                FROM {FRAMEWORK_PATH}.DQ_RULE_RESULTS r
                JOIN {rules_config_table} cc ON r.RULE_CONFIG_ID = cc.RULE_CONFIG_ID
                JOIN {exp_master_table} em ON cc.EXPECTATION_ID = em.EXPECTATION_ID
                WHERE r.DATASET_ID = {P_DATASET_ID}
                  AND r.DATASET_RUN_ID IN (
                    SELECT DATASET_RUN_ID FROM (
                      SELECT DATASET_RUN_ID FROM {FRAMEWORK_PATH}.DQ_DATASET_RUN_LOG
                      WHERE DATASET_ID = {P_DATASET_ID}
                      AND COALESCE(RUN_SCOPE, ''FULL'') = ''FULL''
                      ORDER BY DATASET_RUN_ID DESC LIMIT 10
                    )
                    UNION
                    SELECT {run_id}
                  )
            """).collect()

            if not all_rules_metadata:
                master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "VIEW_CREATION", "No rule metadata found for view generation. Skipping.", step_start_time, datetime.datetime.now(), "SKIPPED", None))
            else:
                view_dynamic_cols = []
                for r in all_rules_metadata:
                    category = r[''CATEGORY'']
                    rule_id = r[''RULE_CONFIG_ID'']
                    col_name = r[''COL_NAME'']
                    dimension = r[''DIMENSION'']
                    kwargs_json = r[''KWARGS'']
                    exp_id = r[''EXPECTATION_ID'']
                    if kwargs_json:
                        try:
                            args = json.loads(kwargs_json)
                            if exp_id == 10:
                                rmin = args.get(''min_value'', ''MIN'')
                                rmax = args.get(''max_value'', ''MAX'')
                                category = f"RANGE_CHECK({rmin}_{rmax})"
                            elif exp_id == 7:
                                dtype = args.get(''datatype'', ''UNKNOWN'')
                                category = f"DATATYPE_CHECK({dtype})"
                            elif exp_id == 18:
                                lmin = args.get(''min_value'', ''MIN'')
                                lmax = args.get(''max_value'', ''MAX'')
                                category = f"{category}({lmin}_{lmax})"
                        except Exception:
                            category = f"{category}_PARSE_ERROR"
                    header = f''"{col_name}_{dimension}_{category}_{rule_id}"''
                    check_level = r[''CHECK_LEVEL'']
                    if check_level != ''ROW'':
                        fail_label = f"FAIL - {check_level} CHECK"
                        view_col_sql = f"CASE WHEN MAX(IFF(rr.RULE_CONFIG_ID = {rule_id}, rr.IS_SUCCESS, NULL)) IS NULL THEN ''NOT CONFIGURED'' WHEN MAX(IFF(rr.RULE_CONFIG_ID = {rule_id}, rr.IS_SUCCESS, NULL)) = FALSE THEN ''{fail_label}'' ELSE ''PASS'' END AS {header}"
                    else:
                        view_col_sql = f"CASE WHEN COUNT(IFF(f.RULE_CONFIG_ID = {rule_id}, 1, NULL)) = 0 AND MAX(IFF(rr.RULE_CONFIG_ID = {rule_id}, rr.IS_SUCCESS, NULL)) IS NULL THEN ''NOT CONFIGURED'' WHEN COUNT(IFF(f.RULE_CONFIG_ID = {rule_id}, 1, NULL)) = 0 AND MAX(IFF(rr.RULE_CONFIG_ID = {rule_id}, rr.IS_SUCCESS, NULL)) IS NOT NULL THEN ''PASS'' WHEN MAX(IFF(f.RULE_CONFIG_ID = {rule_id}, 1, 0)) = 1 THEN ''FAIL'' ELSE ''PASS'' END AS {header}"
                    view_dynamic_cols.append(view_col_sql)
                view_pivot_sql_fragment = ", ".join(view_dynamic_cols)

                rule_ids = [r[''RULE_CONFIG_ID''] for r in all_rules_metadata]
                rule_ids_csv = ", ".join(map(str, rule_ids))

                view_name = f"{q_ident(config[''DQ_DB_NAME''])}.{q_ident(''DQ_ERRORS'')}.{q_ident(''VW_'' + clean_dataset_name + ''_DQ_FAILURE'')}"
                view_select_sql = f"""SELECT 
                            f.DATASET_RUN_ID,
                            {P_DATASET_ID} AS DATASET_ID,
                            ''{data_asset[''DATASET_NAME'']}'' AS DATASET_NAME,
                            {view_pivot_sql_fragment},
                            f.* EXCLUDE (RULE_CONFIG_ID, DATASET_RUN_ID, DATASET_ID, DQ_LOAD_TIMESTAMP)
                        FROM {failure_table_name} f
                        LEFT JOIN {FRAMEWORK_PATH}.DQ_RULE_RESULTS rr
                            ON f.DATASET_RUN_ID = rr.DATASET_RUN_ID
                            AND rr.RULE_CONFIG_ID IN ({rule_ids_csv})
                        GROUP BY ALL"""
                create_view_sql = f"""
                    CREATE OR REPLACE VIEW {view_name} AS
                    {view_select_sql}
                """
                session.sql(create_view_sql).collect()
                failure_view_name = view_name.replace(''"'', '''')
                master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "VIEW_CREATION", f"Created pivot view {view_name}", step_start_time, datetime.datetime.now(), "COMPLETED", None))

        except Exception as e:
            file_generation_error = True
            master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "FILE_GENERATION_AND_VIEW", f"File generation/view creation failed: {str(e)}", step_start_time, datetime.datetime.now(), "FAILED", str(e)))
    
    end_time = datetime.datetime.now()
    run_time_seconds = (end_time - master_start_time).total_seconds()
    
    # Determine Final Status (Prioritize Execution Error if File Gen Fails)
    if error_count > 0 or file_generation_error:
        final_status = "ERROR"
    elif failure_count > 0:
        final_status = "FAILURE"
    else:
        final_status = "SUCCESS"
        
    success_percent = (success_count * 100.0) / total_rules if total_rules > 0 else 0
    
    try:
        log_and_return(session, config, master_audit_logs, 0)
    except Exception as log_err:
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "AUDIT_LOG_FLUSH", f"Failed to flush audit logs: {str(log_err)[:300]}", datetime.datetime.now(), datetime.datetime.now(), "FAILED", str(log_err)[:500]))
    
    try:
        run_log_table_path = f"{config[''DQ_DB_NAME'']}.{config[''DQ_SCHEMA_NAME'']}.DQ_DATASET_RUN_LOG"
        
        final_insert_sql = f"""
            INSERT INTO {run_log_table_path} 
            (DATASET_RUN_ID, DATASET_ID, RUN_TIME, EVALUATED_EXPECTATIONS, SUCCESSFULL_EXPECTATIONS, UNSUCCESSFULL_EXPECTATIONS, ERROR_EXPECTATIONS, RUN_STATUS, CREATED_BY, SUCCESS_PERCENT, CREATED_TIMESTAMP, FAILURE_FILE, SOURCE_SQL, FAILURE_VIEW, RUN_SCOPE) 
            VALUES ({run_id}, {P_DATASET_ID}, {run_time_seconds}, {total_rules}, {success_count}, {failure_count}, {error_count}, ''{final_status}'', ''{session.get_current_user()}'', {success_percent}, ''{master_start_time}'',{final_file_name},{format_for_sql(source_sql_text, is_string=True)},{format_for_sql(failure_view_name, is_string=True)},''{run_scope}'')
        """
        session.sql(final_insert_sql).collect()
    except Exception as e:
        master_audit_logs.append((run_id, "EXECUTE_DQ_RULES_MASTER", "RUN_LOG_INSERT", f"Failed to insert run log: {str(e)}", datetime.datetime.now(), datetime.datetime.now(), "FAILED", f"Failed to insert run log: {str(e)}"))
        try:
            log_and_return(session, config, master_audit_logs, 0)
        except Exception as retry_err:
            session.sql(f"INSERT INTO {FRAMEWORK_PATH}.DQ_RULE_AUDIT_LOG (DATASET_RUN_ID, STEP_NAME, SUB_STEP, STEP_DESCRIPTION, STEP_START_TIMESTAMP, STEP_END_TIMESTAMP, STEP_STATUS, ERROR_MESSAGE) VALUES ({run_id}, ''EXECUTE_DQ_RULES_MASTER'', ''FINAL_LOG_RETRY'', ''Audit log flush failed on retry'', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), ''FAILED'', ''{str(retry_err)[:200]}'')").collect()

    # Final Return Code Logic
    if error_count > 0 or file_generation_error: 
        return int(config["EXECUTION_ERROR"])
    elif failure_count > 0: 
        return int(config["FAILED_CODE"])
    else: 
        return int(config["SUCCESS_CODE"])
';
