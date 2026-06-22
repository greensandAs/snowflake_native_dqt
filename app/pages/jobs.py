# Execution/Jobs page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
import json as json_lib
import pandas as pd
from shared.db import session, FQN
from shared.helpers import empty_state, flush_toast, div, style_table, sticky_header


def page():
    sticky_header("Execution &rsaquo; Jobs", "Run DQ checks")
    flush_toast()

    @st.cache_data(ttl=60)
    def load_exec_datasets():
        return session.sql(
            f"SELECT DATASET_ID,DATASET_NAME,DATABASE_NAME,SCHEMA_NAME,TABLE_NAME "
            f"FROM {FQN}.DQ_DATASET ORDER BY DATASET_NAME"
        ).to_pandas()

    @st.cache_data(ttl=30)
    def rule_counts(dsid):
        total = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID=?",
            params=[dsid]).to_pandas()["C"][0])
        active = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID=? AND IS_ACTIVE=TRUE",
            params=[dsid]).to_pandas()["C"][0])
        sev_df = session.sql(
            f"SELECT SEVERITY,COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG "
            f"WHERE DATASET_ID=? AND IS_ACTIVE=TRUE GROUP BY SEVERITY",
            params=[dsid]).to_pandas()
        return total, active, sev_df

    @st.cache_data(ttl=30)
    def run_history(dsid):
        return session.sql(
            f"SELECT DATASET_RUN_ID,RUN_STATUS,EVALUATED_EXPECTATIONS,"
            f"SUCCESSFULL_EXPECTATIONS,UNSUCCESSFULL_EXPECTATIONS,"
            f"SUCCESS_PERCENT,RUN_TIME,CREATED_TIMESTAMP "
            f"FROM {FQN}.DQ_DATASET_RUN_LOG WHERE DATASET_ID=? "
            f"ORDER BY CREATED_TIMESTAMP DESC LIMIT 10",
            params=[int(dsid)],
        ).to_pandas()

    exec_ds = load_exec_datasets()

    tab_proj, tab_ds = st.tabs(["\U0001f4e6  Project", "\U0001f4cb  Dataset"])

    with tab_proj:
        st.markdown("## Run all datasets in a project")
        st.caption("Runs every dataset in the selected project; rules parallelize per dataset. "
                   "All dataset runs share one BATCH_ID.")
        _pj = session.sql(f"SELECT PROJECT_ID, PROJECT_NAME FROM {FQN}.DQ_PROJECTS ORDER BY PROJECT_NAME").to_pandas()
        if _pj.empty:
            empty_state("\U0001f4c1", "No projects", "Create a project first.")
        else:
            _popts = dict(zip(_pj["PROJECT_NAME"], _pj["PROJECT_ID"]))
            _psel = st.selectbox("Project", list(_popts.keys()), key="jobs_proj_sel")
            if _psel and st.button("\U0001f680  Run All Datasets", type="primary", key="jobs_proj_btn"):
                _pid = int(_popts[_psel])
                with st.status(f"Running all datasets in {_psel}\u2026", expanded=True) as _ps:
                    try:
                        _raw = session.call(f"{FQN}.EXECUTE_DQ_RULES_PROJECT", _pid)
                        _su = json_lib.loads(_raw) if isinstance(_raw, str) else _raw
                        st.write(f"\U0001f4e6  Batch ID: **{_su.get('batch_id')}**")
                        st.write(f"\U0001f4ca  {_su.get('datasets_run',0)} run \u00b7 "
                                 f"{_su.get('datasets_skipped',0)} skipped \u00b7 of {_su.get('datasets_total',0)} total")
                        st.write(f"\u2705  {_su.get('passed',0)} passed \u00b7 \u26a0\ufe0f  {_su.get('failed',0)} failed \u00b7 \U0001f534  {_su.get('errored',0)} errored")
                        _state = "error" if _su.get("status") == "ERROR" else "complete"
                        _ps.update(label=f"Project run complete \u2014 {_su.get('status')}", state=_state, expanded=True)
                        _det = _su.get("details", [])
                        if _det:
                            st.dataframe(pd.DataFrame(_det), use_container_width=True, hide_index=True)
                        rule_counts.clear(); run_history.clear()
                    except Exception as e:
                        _ps.update(label="Project run failed", state="error", expanded=True)
                        st.error(f"\u274c  Couldn't run the project: {e}")

            div()
            st.markdown("### Project Run History")
            _hist = session.sql(
                f"SELECT PROJECT_RUN_ID, BATCH_ID, DATASETS_RUN, DATASETS_SKIPPED, "
                f"PASSED, FAILED, ERRORED, RUN_STATUS, SUCCESS_PERCENT, RUN_TIME, CREATED_TIMESTAMP "
                f"FROM {FQN}.DQ_PROJECT_RUN_LOG WHERE PROJECT_ID = {int(_popts[_psel])} "
                f"ORDER BY PROJECT_RUN_ID DESC LIMIT 10"
            ).to_pandas()
            if _hist.empty:
                empty_state("\U0001f4dc", "No project runs yet", "Run the project to see history here.")
            else:
                _icons = {"SUCCESS": "\u2705", "FAILURE": "\u26a0\ufe0f", "ERROR": "\U0001f534", "NO_DATASETS": "\u2205"}
                _default_icon = "\u2753"
                _hist["STATUS"] = _hist["RUN_STATUS"].apply(lambda s: f"{_icons.get(str(s).upper(), _default_icon)}  {s}")
                _hist["PASS %"] = _hist["SUCCESS_PERCENT"].apply(lambda x: f"{float(x):.1f}%" if pd.notna(x) else "\u2014")
                _hist["RUN TIME"] = _hist["RUN_TIME"].apply(lambda x: f"{float(x):.1f}s" if pd.notna(x) else "\u2014")
                st.dataframe(
                    _hist[["PROJECT_RUN_ID", "BATCH_ID", "STATUS", "DATASETS_RUN", "DATASETS_SKIPPED",
                           "PASSED", "FAILED", "ERRORED", "PASS %", "RUN TIME", "CREATED_TIMESTAMP"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "PROJECT_RUN_ID":   st.column_config.NumberColumn("Run", width=55),
                        "BATCH_ID":         st.column_config.NumberColumn("Batch", width=70),
                        "STATUS":           st.column_config.TextColumn("Status", width=110),
                        "DATASETS_RUN":     st.column_config.NumberColumn("Datasets", width=75),
                        "DATASETS_SKIPPED": st.column_config.NumberColumn("Skipped", width=70),
                        "PASSED":           st.column_config.NumberColumn("Pass", width=55),
                        "FAILED":           st.column_config.NumberColumn("Fail", width=55),
                        "ERRORED":          st.column_config.NumberColumn("Err", width=55),
                        "PASS %":           st.column_config.TextColumn("Pass %", width=70),
                        "RUN TIME":         st.column_config.TextColumn("Run Time", width=80),
                        "CREATED_TIMESTAMP": st.column_config.DatetimeColumn(
                            "Timestamp", format="MMM DD, YYYY HH:mm"),
                    },
                )

    with tab_ds:
        if exec_ds.empty:
            empty_state("\U0001f4e6", "No datasets found", "Create a dataset first.")
            return

        exec_opts = dict(zip(exec_ds["DATASET_NAME"], exec_ds["DATASET_ID"]))
        sel_ds = st.selectbox("Select Dataset", list(exec_opts.keys()))
        sel_id = int(exec_opts[sel_ds])
        total_r, active_r, sev_dist = rule_counts(sel_id)

        st.markdown("## Pre-flight Check")
        for ok, msg_ok, msg_fail in [
            (active_r > 0, f"{active_r} active rules ready", "No active rules \u2014 configure rules first"),
            (total_r > 0, f"{total_r} total rules configured", "Add at least one rule"),
        ]:
            cls = "preflight-ok" if ok else "preflight-fail"
            icon = "\u2705" if ok else "\u274c"
            st.markdown(
                f'<div class="preflight-item {cls}">{icon}  {msg_ok if ok else msg_fail}</div>',
                unsafe_allow_html=True)

        if not sev_dist.empty:
            sev_colors = {"CRITICAL": "#F85149", "HIGH": "#FFA657", "MEDIUM": "#D29922", "LOW": "#3FB950"}
            parts = "  ".join(
                f'<span style="color:{sev_colors.get(str(r["SEVERITY"]).upper(),"#8B949E")};'
                f'font-weight:700">{r["SEVERITY"]}: {int(r["C"])}</span>'
                for _, r in sev_dist.iterrows()
            )
            st.markdown(f'<div class="preflight-item preflight-ok">\U0001f3f7\ufe0f  {parts}</div>',
                        unsafe_allow_html=True)

        div()
        col_ctrl, col_hist = st.columns([4, 6])

        with col_ctrl:
            st.markdown("## Execution Settings")
            parallel = st.slider("Parallel Jobs", 1, 10, 2, key="exec_parallel")
            scope_choice = st.radio(
                "Run Scope", ["All active rules", "Selected rules", "Retry last failed"],
                horizontal=True, key="exec_scope")
            rule_ids_param = None
            if scope_choice == "Selected rules":
                _ar = session.sql(
                    f"SELECT RULE_CONFIG_ID, EXPECTATION_NAME, COALESCE(COLUMN_NAME,'') AS COLUMN_NAME "
                    f"FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID = {sel_id} AND IS_ACTIVE = TRUE "
                    f"ORDER BY RULE_CONFIG_ID"
                ).to_pandas()
                _opts = {f"#{int(r.RULE_CONFIG_ID)} \u00b7 {r.EXPECTATION_NAME}"
                         + (f" ({r.COLUMN_NAME})" if r.COLUMN_NAME else ""): int(r.RULE_CONFIG_ID)
                         for r in _ar.itertuples()}
                _picked = st.multiselect("Rules to run", list(_opts.keys()), key="exec_rule_pick")
                rule_ids_param = ",".join(str(_opts[p]) for p in _picked) if _picked else None
                if not _picked:
                    st.warning("Pick at least one rule, or switch scope to 'All active rules'.")
            elif scope_choice == "Retry last failed":
                _ff = session.sql(
                    f"SELECT DISTINCT RULE_CONFIG_ID FROM {FQN}.DQ_RULE_RESULTS "
                    f"WHERE DATASET_ID = {sel_id} AND IS_SUCCESS = FALSE "
                    f"AND DATASET_RUN_ID = (SELECT MAX(DATASET_RUN_ID) FROM {FQN}.DQ_RULE_RESULTS WHERE DATASET_ID = {sel_id})"
                ).to_pandas()
                _failed_ids = [int(x) for x in _ff["RULE_CONFIG_ID"].tolist()]
                if _failed_ids:
                    rule_ids_param = ",".join(str(i) for i in _failed_ids)
                    st.info(f"Will re-run {len(_failed_ids)} failed rule(s): {rule_ids_param}")
                else:
                    st.success("No failed rules in the last run \u2014 nothing to retry.")

            if active_r == 0:
                st.button("\U0001f680  Execute", disabled=True, use_container_width=True)
                st.warning("\u26a0\ufe0f  Configure active rules before executing.")
            else:
                if st.button("\U0001f680  Run DQ Rules", use_container_width=True,
                             type="primary", key="exec_run_btn"):
                    with st.status(f"Running {active_r} rules for {sel_ds}\u2026",
                                   expanded=True) as status:
                        try:
                            st.write("\U0001f4e5  Fetching active rules\u2026")
                            st.write(f"\U0001f9f5  Distributing across {parallel} parallel job(s)\u2026")
                            if rule_ids_param:
                                st.write(f"\U0001f3af  Scope: selective ({rule_ids_param})")
                                result = int(session.call(
                                    f"{FQN}.EXECUTE_DQ_RULES_MASTER", sel_id, parallel, rule_ids_param))
                            else:
                                result = int(session.call(
                                    f"{FQN}.EXECUTE_DQ_RULES_MASTER", sel_id, parallel))
                            run_history.clear(); rule_counts.clear()
                            if result == 200:
                                st.write("\u2705  All rules passed.")
                                status.update(label="Complete \u2014 all rules passed",
                                              state="complete", expanded=False)
                                st.session_state["_toast_msg"] = "DQ run complete \u2014 all rules passed"
                            elif result == 300:
                                st.write("\u26a0\ufe0f  Some rules failed \u2014 open **Rule Results** for details.")
                                status.update(label="Complete \u2014 some failures",
                                              state="complete", expanded=False)
                                st.session_state["_toast_msg"] = "DQ run complete \u2014 some rules failed"
                            else:
                                st.write(f"\U0001f534  One or more rules **errored** (code {result}).")
                                status.update(label=f"Execution error (code {result})",
                                              state="error", expanded=True)
                            if result in (200, 300):
                                st.rerun()
                        except Exception as e:
                            status.update(label="Execution failed", state="error", expanded=True)
                            st.error(f"\u274c  Couldn't run the DQ procedure: {e}")

        with col_hist:
            st.markdown("## Run History")
            hist_df = run_history(sel_id)
            if hist_df.empty:
                empty_state("\u23f1\ufe0f", "No runs yet", "Execute to see history here.")
            else:
                status_icons = {"SUCCESS": "\u2705", "FAILURE": "\u274c", "ERROR": "\U0001f534", "PARTIAL_SUCCESS": "\u26a0\ufe0f"}
                _fallback_icon = "\u2753"
                hist_df["STATUS"] = hist_df["RUN_STATUS"].apply(
                    lambda s: f"{status_icons.get(str(s).upper(), _fallback_icon)}  {s}")
                hist_df["PASS %"] = hist_df["SUCCESS_PERCENT"].apply(
                    lambda x: f"{float(x):.1f}%" if pd.notna(x) else "\u2014")
                hist_df["RUN TIME"] = hist_df["RUN_TIME"].apply(
                    lambda x: f"{float(x):.1f}s" if pd.notna(x) else "\u2014")
                st.dataframe(
                    style_table(hist_df[["DATASET_RUN_ID", "STATUS", "EVALUATED_EXPECTATIONS",
                              "SUCCESSFULL_EXPECTATIONS", "UNSUCCESSFULL_EXPECTATIONS",
                              "PASS %", "RUN TIME", "CREATED_TIMESTAMP"]]),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "DATASET_RUN_ID":              st.column_config.NumberColumn("Run ID", width=70),
                        "STATUS":                      st.column_config.TextColumn("Status", width=120),
                        "EVALUATED_EXPECTATIONS":      st.column_config.NumberColumn("Total", width=60),
                        "SUCCESSFULL_EXPECTATIONS":    st.column_config.NumberColumn("Passed", width=65),
                        "UNSUCCESSFULL_EXPECTATIONS":  st.column_config.NumberColumn("Failed", width=65),
                        "PASS %":                      st.column_config.TextColumn("Pass %", width=70),
                        "RUN TIME":                    st.column_config.TextColumn("Run Time", width=80),
                        "CREATED_TIMESTAMP":           st.column_config.DatetimeColumn(
                            "Timestamp", format="MMM DD, YYYY HH:mm"),
                    },
                )
