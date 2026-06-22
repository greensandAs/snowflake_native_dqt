-- SCD recon handler: uses INSERT_DATE_TIME for inactive-count existence check with MIN() fallback
USE DATABASE {{framework_db}};
USE SCHEMA {{framework_schema}};
CREATE OR REPLACE PROCEDURE SP_TABLE_ROW_COUNT_EQUAL_OTHER_TABLE_CHECK("RULE" VARIANT)
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
    proc = "SP_TABLE_ROW_COUNT_EQUAL_OTHER_TABLE_CHECK"
    run_id = int(RULE.get("DATASET_RUN_ID", -1))
    cfg_id = int(RULE.get("RULE_CONFIG_ID", -1))
    ds_id = int(RULE.get("DATASET_ID", -1))
    ds_name = RULE.get("DATASET_NAME")
    exp_id = RULE.get("EXPECTATION_ID")
    exp_nm = RULE.get("EXPECTATION_NAME")
    run_nm = RULE.get("RUN_NAME")
    dimension = RULE.get("DIMENSION") or "VOLUME"
    src_type = (RULE.get("DATASET_TYPE") or "TABLE").upper()
    src_db, src_sch, src_tbl = RULE.get("DATABASE_NAME"), RULE.get("SCHEMA_NAME"), RULE.get("TABLE_NAME")
    src_sql = RULE.get("CUSTOM_SQL")

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

    # ─── 1. CONFIG LOADING ───────────────────────────────────────────────────
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

    # ─── 2. RULE PARSING ─────────────────────────────────────────────────────
    try:
        def from_clause(t, db, sch, tbl, q):
            if t == "QUERY":
                return f"({q})"
            return f'"{db}"."{sch}"."{tbl}"'

        conf_from = from_clause(src_type, src_db, src_sch, src_tbl, src_sql)

        s_db = kw.get("source_database")
        s_sch = kw.get("source_schema")
        s_tbl = kw.get("source_table")
        other_name = kw.get("other_dataset_name")
        if s_db and s_sch and s_tbl:
            core_from = f'"{s_db}"."{s_sch}"."{s_tbl}"'
            source_label = f"{s_db}.{s_sch}.{s_tbl}"
        elif other_name:
            row = session.sql(
                f"SELECT DATASET_TYPE, DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, CUSTOM_SQL "
                f"FROM {fw}.DQ_DATASET WHERE DATASET_NAME = ? LIMIT 1", params=[other_name]
            ).collect()
            if not row:
                audit("RULE_PARSING", "FAILED", err=f"Source dataset {other_name} not found")
                return error_code
            o = row[0]
            core_from = from_clause((o["DATASET_TYPE"] or "TABLE").upper(),
                                    o["DATABASE_NAME"], o["SCHEMA_NAME"], o["TABLE_NAME"], o["CUSTOM_SQL"])
            source_label = other_name
        else:
            audit("RULE_PARSING", "FAILED",
                  err="KWARGS must contain source_database/source_schema/source_table")
            return failed_code

        scd_type = int(kw.get("scd_type", 0) or 0)
        flag_col = kw.get("active_flag_col") or "IS_ACTIVE"
        active_value = kw.get("active_value", "Y")
        inactive_value = kw.get("inactive_value", "N")
        core_date = kw.get("core_insert_date_col") or "INSERT_DATE_TIME"
        conf_date = kw.get("conformed_update_date_col") or "UPDATE_DATE_TIME"
        conf_insert_date_cfg = kw.get("conformed_insert_date_col")
        pk = kw.get("partition_keys") or kw.get("compare_cols") or []
        if isinstance(pk, str):
            pk = [c.strip() for c in pk.split(",") if c.strip()]
        keys_csv = ", ".join(pk)
        trimmed = ", ".join([f"COALESCE(TRIM({c}), 'NA')" for c in pk]) if pk else ""
        audit("RULE_PARSING", "COMPLETED",
              msg=f"source={source_label}, scd_type={scd_type}, keys={keys_csv}")
    except Exception as e:
        audit("RULE_PARSING", "FAILED", err=str(e))
        return error_code

    # ─── Helper: write recon result row ──────────────────────────────────────
    def write_recon(validation_on, core_val, conf_val, result):
        session.sql(
            "INSERT INTO DQ_RECON_RESULTS "
            "(DATASET_RUN_ID, DATASET_ID, RULE_CONFIG_ID, LAYER, DATA_SOURCE, TABLE_NAME, "
            "VALIDATION_ON, SRC_VALUE, CORE_VALUE, CONFORMED_VALUE, CONSUMPTION_VALUE, "
            "RESULT, VALIDATION_LOGIC, AUDIT_TIMESTAMP) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?, CURRENT_TIMESTAMP())",
            params=[run_id, ds_id, cfg_id, "CONFORMED", str(source_label), str(ds_name),
                    validation_on, str(core_val), str(conf_val), result,
                    "WHEN CORE_VALUE = CONFORMED_VALUE THEN PASS ELSE FAIL"]
        ).collect()

    # ─── Resolve conf_insert_date: column used for existence check in INACTIVE_COUNT
    # If explicitly configured in KWARGS, use it. Otherwise check if INSERT_DATE_TIME
    # exists in the conformed table; fall back to conf_date (UPDATE_DATE_TIME) if not.
    # This handles tables that only have UPDATE_DATE_TIME and no separate INSERT_DATE_TIME.
    # NOTE: The MIN(UPDATE_DATE_TIME) fallback assumes the SCD2 pattern does NOT update
    # UPDATE_DATE_TIME on the expired row. If your pattern DOES mutate it on expiry,
    # add an INSERT_DATE_TIME column or set conformed_insert_date_col in KWARGS.
    if conf_insert_date_cfg:
        conf_insert_date = conf_insert_date_cfg
    elif src_type == "TABLE":
        try:
            col_check = session.sql(
                f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                f"WHERE TABLE_CATALOG = ? AND TABLE_SCHEMA = ? AND TABLE_NAME = ? "
                f"AND UPPER(COLUMN_NAME) = 'INSERT_DATE_TIME'",
                params=[src_db, src_sch, src_tbl]
            ).collect()
            conf_insert_date = "INSERT_DATE_TIME" if col_check else conf_date
        except Exception:
            conf_insert_date = conf_date
    else:
        conf_insert_date = conf_date

    if conf_insert_date == conf_date and scd_type == 2:
        audit("COLUMN_RESOLUTION", "COMPLETED",
              msg=f"No INSERT_DATE_TIME in conformed table — using MIN({conf_date}) fallback. "
                  f"If your SCD2 pattern mutates {conf_date} on expiry, add INSERT_DATE_TIME "
                  f"or set conformed_insert_date_col in KWARGS for accurate INACTIVE_COUNT.")

    # ─── 3. RECON MODE & PER-LAYER WATERMARKS ──────────────────────────────
    recon_mode = (kw.get("recon_mode") or "incremental").strip().lower()

    # Per-layer watermarks from the last successful run, stored in OBSERVED_VALUE as
    #   {"core_watermark": "<ts>", "conf_watermark": "<ts>"}
    # CORE and CONFORMED run on different clocks (conformed >= core), so each layer
    # advances independently. Falls back to legacy single "watermark" key if present.
    core_wm = None
    conf_wm = None
    if recon_mode == "incremental" and scd_type in (1, 2):
        try:
            wm_row = session.sql(
                f"SELECT "
                f"COALESCE(OBSERVED_VALUE:core_watermark, OBSERVED_VALUE:watermark)::TIMESTAMP_NTZ AS CORE_WM, "
                f"COALESCE(OBSERVED_VALUE:conf_watermark, OBSERVED_VALUE:watermark)::TIMESTAMP_NTZ AS CONF_WM "
                f"FROM {fw}.DQ_RULE_RESULTS "
                f"WHERE RULE_CONFIG_ID = ? AND IS_SUCCESS = TRUE "
                f"AND (OBSERVED_VALUE:core_watermark IS NOT NULL OR OBSERVED_VALUE:watermark IS NOT NULL) "
                f"ORDER BY RUN_TIMESTAMP DESC LIMIT 1",
                params=[cfg_id]
            ).collect()
            if wm_row:
                core_wm = wm_row[0]["CORE_WM"]
                conf_wm = wm_row[0]["CONF_WM"]
            audit("WATERMARK_LOOKUP", "COMPLETED",
                  msg=f"rule_config_id={cfg_id} core_wm={core_wm or 'first_run'} conf_wm={conf_wm or 'first_run'}")
        except Exception:
            audit("WATERMARK_LOOKUP", "COMPLETED", msg="No prior run found, full scan for this run")

    has_wm = core_wm is not None and conf_wm is not None

    # KEY BEHAVIOR: If recon_mode is incremental but no watermark exists (first run),
    # fall back to full recon to establish a baseline. Subsequent runs will use incremental
    # because this run stores watermarks in OBSERVED_VALUE.
    effective_mode = recon_mode
    if recon_mode == "incremental" and scd_type in (1, 2) and not has_wm:
        effective_mode = "full"
        audit("MODE_FALLBACK", "COMPLETED",
              msg="No watermark found for incremental mode. Falling back to FULL recon for this run to establish baseline.")

    # Capture current max timestamps per layer — these become the NEXT run's watermarks
    current_max_core_date = None
    current_max_conf_date = None
    if recon_mode == "incremental" and scd_type in (1, 2):
        try:
            mx = session.sql(
                f"SELECT MAX({core_date})::VARCHAR AS MX FROM ("
                f"  SELECT * FROM {core_from} "
                f"  QUALIFY ROW_NUMBER() OVER (PARTITION BY {keys_csv} ORDER BY {core_date} DESC) = 1"
                f")"
            ).collect()
            if mx and mx[0]["MX"] is not None:
                current_max_core_date = mx[0]["MX"]
        except Exception:
            pass
        try:
            mxc = session.sql(f"SELECT MAX({conf_date})::VARCHAR AS MX FROM {conf_from}").collect()
            if mxc and mxc[0]["MX"] is not None:
                current_max_conf_date = mxc[0]["MX"]
        except Exception:
            pass

    # ─── 4. MAIN RECON LOGIC ─────────────────────────────────────────────────
    try:
        if scd_type in (1, 2) and pk:
            core_dedup = (
                f"SELECT * FROM {core_from} "
                f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {keys_csv} "
                f"ORDER BY {core_date} DESC) = 1"
            )

            def recon_count(validation_on, flag_value=None):
                """Count comparison for active/inactive/total."""
                cflag = f" AND {flag_col} = ?" if flag_value is not None else ""

                if effective_mode == "full":
                    # Full recon: compare entire tables (no date filter)
                    core_sql = f"SELECT COUNT(*)::INT AS CNT FROM ({core_dedup})"
                    conf_sql = f"SELECT COUNT(*)::INT AS CNT FROM {conf_from} WHERE 1=1{cflag}"
                    core_params = []
                    conf_params = [flag_value] if flag_value is not None else []

                elif has_wm:
                    # Incremental with per-layer watermarks: each side filtered by its own clock
                    core_sql = (
                        f"SELECT COUNT(*)::INT AS CNT FROM ({core_dedup}) "
                        f"WHERE {core_date} > ?"
                    )
                    conf_sql = (
                        f"SELECT COUNT(*)::INT AS CNT FROM {conf_from} "
                        f"WHERE {conf_date} > ?{cflag}"
                    )
                    core_params = [core_wm]
                    conf_params = [conf_wm] + ([flag_value] if flag_value is not None else [])

                else:
                    # Safety net fallback (full)
                    core_sql = f"SELECT COUNT(*)::INT AS CNT FROM ({core_dedup})"
                    conf_sql = f"SELECT COUNT(*)::INT AS CNT FROM {conf_from} WHERE 1=1{cflag}"
                    core_params = []
                    conf_params = [flag_value] if flag_value is not None else []

                cv = int(session.sql(core_sql, params=core_params).collect()[0]["CNT"])
                ov = int(session.sql(conf_sql, params=conf_params).collect()[0]["CNT"])
                r = "PASS" if cv == ov else "FAIL"
                write_recon(validation_on, cv, ov, r)
                return cv, ov, r

            # ─── SCD1: single total count ────────────────────────────────────
            if scd_type == 1:
                cv, ov, r = recon_count("TOTAL_COUNT", None)
                overall_pass = (r == "PASS")
                total, mism = cv, abs(cv - ov)
                results_obj = {"total": {"core": cv, "conformed": ov, "result": r}}

            # ─── SCD2: active count in full mode; active + inactive in incremental ──
            else:
                # ACTIVE_COUNT: core distinct count vs conformed active count
                ac, ao, ar = recon_count("ACTIVE_COUNT", active_value)

                if effective_mode == "full":
                    # Full mode (baseline): only check active count.
                    # INACTIVE_COUNT is not meaningful for core-vs-conformed in full mode
                    # because core does not track historical versions — it only has current state.
                    # The watermark stored here enables true incremental on the next run.
                    overall_pass = (ar == "PASS")
                    total = ac
                    mism = abs(ac - ao)
                    results_obj = {
                        "active": {"core": ac, "conformed": ao, "result": ar},
                    }

                elif has_wm:
                    # Incremental with per-layer watermarks:
                    # INACTIVE_COUNT core side: new core records whose keys ALREADY EXISTED
                    #   in CONFORMED before conf_wm.
                    # If conf_insert_date == conf_date (fallback, no INSERT_DATE_TIME column),
                    #   we use MIN(UPDATE_DATE_TIME) per key via GROUP BY/HAVING. This finds
                    #   the earliest timestamp for each key (= original creation), which
                    #   remains stable even after expiry updates the row's UPDATE_DATE_TIME.
                    # If conf_insert_date != conf_date (dedicated INSERT_DATE_TIME exists),
                    #   we use a simple WHERE filter since that column never changes.
                    if conf_insert_date == conf_date:
                        # Fallback: no INSERT_DATE_TIME — use MIN(UPDATE_DATE_TIME) per key
                        ic_core_sql = (
                            f"SELECT COUNT(*)::INT AS CNT FROM ({core_dedup}) "
                            f"WHERE {core_date} > ? "
                            f"AND ({trimmed}) IN ("
                            f"  SELECT {trimmed} FROM {conf_from} "
                            f"  GROUP BY {trimmed} "
                            f"  HAVING MIN({conf_date}) <= ?)"
                        )
                    else:
                        # Preferred: INSERT_DATE_TIME is immutable, simple filter
                        ic_core_sql = (
                            f"SELECT COUNT(*)::INT AS CNT FROM ({core_dedup}) "
                            f"WHERE {core_date} > ? "
                            f"AND ({trimmed}) IN ("
                            f"  SELECT DISTINCT {trimmed} FROM {conf_from} "
                            f"  WHERE {conf_insert_date} <= ?)"
                        )
                    ic = int(session.sql(ic_core_sql,
                             params=[core_wm, conf_wm]).collect()[0]["CNT"])
                    # CONFORMED side: inactive records created after conf_wm
                    ic_conf_sql = (
                        f"SELECT COUNT(*)::INT AS CNT FROM {conf_from} "
                        f"WHERE {conf_date} > ? AND {flag_col} = ?"
                    )
                    io = int(session.sql(ic_conf_sql,
                             params=[conf_wm, inactive_value]).collect()[0]["CNT"])
                    ir = "PASS" if ic == io else "FAIL"
                    write_recon("INACTIVE_COUNT", ic, io, ir)

                    overall_pass = (ar == "PASS") and (ir == "PASS")
                    total = ac
                    mism = abs(ac - ao) + abs(ic - io)
                    results_obj = {
                        "active": {"core": ac, "conformed": ao, "result": ar},
                        "inactive": {"core": ic, "conformed": io, "result": ir},
                    }

                else:
                    # Safety net: same as full
                    overall_pass = (ar == "PASS")
                    total = ac
                    mism = abs(ac - ao)
                    results_obj = {
                        "active": {"core": ac, "conformed": ao, "result": ar},
                    }
        else:
            # scd_type=0: plain total count (no dedup, no date filter)
            cv = int(session.sql(f"SELECT COUNT(*)::INT AS CNT FROM {core_from}").collect()[0]["CNT"])
            ov = int(session.sql(f"SELECT COUNT(*)::INT AS CNT FROM {conf_from}").collect()[0]["CNT"])
            r = "PASS" if cv == ov else "FAIL"
            write_recon("TOTAL_COUNT", cv, ov, r)
            overall_pass = (r == "PASS")
            total, mism = cv, abs(cv - ov)
            results_obj = {"total": {"core": cv, "conformed": ov, "result": r}}

        audit("MAIN_QUERY", "COMPLETED",
              msg=f"scd_type={scd_type} effective_mode={effective_mode} recon_mode={recon_mode} core_wm={core_wm} conf_wm={conf_wm} pass={overall_pass}")
    except Exception as e:
        audit("MAIN_QUERY", "FAILED", err=str(e))
        return error_code

    # ─── 5. INSERT DQ_RULE_RESULTS (store per-layer watermarks for next run) ──
    try:
        if current_max_core_date or current_max_conf_date:
            observed_json = json.dumps({
                "core_watermark": current_max_core_date,
                "conf_watermark": current_max_conf_date,
            })
        else:
            observed_json = "null"

        session.sql(
            f"INSERT INTO {fw}.DQ_RULE_RESULTS "
            "(DATASET_RUN_ID, DATASET_ID, RULE_CONFIG_ID, EXPECTATION_ID, RUN_NAME, "
            "RUN_TIMESTAMP, DATASET_NAME, IS_SUCCESS, RESULTS, EXPECTATION_NAME, "
            "ELEMENT_COUNT, UNEXPECTED_COUNT, DIMENSION, OBSERVED_VALUE) "
            "SELECT ?, ?, ?, ?, ?, CURRENT_TIMESTAMP(), ?, ?, PARSE_JSON(?), ?, ?, ?, ?, PARSE_JSON(?)",
            params=[run_id, ds_id, cfg_id, exp_id, run_nm, ds_name,
                    overall_pass, json.dumps(results_obj), exp_nm, total, mism, dimension, observed_json]
        ).collect()
        audit("INSERT_DQ_RESULTS_TABLE", "COMPLETED", msg="Result stored")
    except Exception as e:
        audit("INSERT_DQ_RESULTS_TABLE", "FAILED", err=str(e))
        return error_code

    return success_code if overall_pass else failed_code
$$;
