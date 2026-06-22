# Schedules page: manage Snowflake Task-based scheduled DQ runs
# Co-authored with CoCo

import streamlit as st
import pandas as pd
from shared.db import session, FQN
from shared.helpers import empty_state, flush_toast, div, style_table, sticky_header


CRON_PRESETS = {
    "Daily at 6 AM": "0 6 * * *",
    "Daily at 9 AM": "0 9 * * *",
    "Daily at midnight": "0 0 * * *",
    "Every hour": "0 * * * *",
    "Weekdays at 8 AM": "0 8 * * 1-5",
    "Every Monday at 7 AM": "0 7 * * 1",
    "First of month at 6 AM": "0 6 1 * *",
    "Custom": "",
}


def page():
    sticky_header("Execution &rsaquo; Schedules", "Automate DQ runs with Snowflake Tasks")
    flush_toast()

    @st.cache_data(ttl=30)
    def load_schedules():
        return session.sql(
            f"SELECT s.SCHEDULE_ID, s.SCHEDULE_NAME, s.SCHEDULE_TYPE, s.TARGET_ID, "
            f"s.CRON_EXPRESSION, s.TIMEZONE, s.WAREHOUSE, s.PARALLEL_JOBS, "
            f"s.IS_ACTIVE, s.TASK_NAME, s.LAST_RECONCILED_AT, s.CREATED_BY, s.CREATED_AT, "
            f"CASE WHEN s.SCHEDULE_TYPE = 'PROJECT' THEN p.PROJECT_NAME "
            f"     ELSE d.DATASET_NAME END AS TARGET_NAME "
            f"FROM {FQN}.DQ_SCHEDULE_CONFIG s "
            f"LEFT JOIN {FQN}.DQ_PROJECTS p ON s.SCHEDULE_TYPE = 'PROJECT' AND s.TARGET_ID = p.PROJECT_ID "
            f"LEFT JOIN {FQN}.DQ_DATASET d ON s.SCHEDULE_TYPE = 'DATASET' AND s.TARGET_ID = d.DATASET_ID "
            f"ORDER BY s.IS_ACTIVE DESC, s.SCHEDULE_NAME"
        ).to_pandas()

    @st.cache_data(ttl=30)
    def load_run_log(schedule_id):
        return session.sql(
            f"SELECT SCHEDULE_RUN_ID, RUN_STATUS, RESULT_CODE, BATCH_ID, "
            f"RUN_STARTED_AT, RUN_COMPLETED_AT, ERROR_MESSAGE "
            f"FROM {FQN}.DQ_SCHEDULE_RUN_LOG WHERE SCHEDULE_ID = {int(schedule_id)} "
            f"ORDER BY RUN_STARTED_AT DESC LIMIT 20"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_projects():
        return session.sql(
            f"SELECT PROJECT_ID, PROJECT_NAME FROM {FQN}.DQ_PROJECTS ORDER BY PROJECT_NAME"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_datasets():
        return session.sql(
            f"SELECT DATASET_ID, DATASET_NAME FROM {FQN}.DQ_DATASET ORDER BY DATASET_NAME"
        ).to_pandas()

    # ── Page layout ──
    tab_list, tab_create = st.tabs(["\U0001f4cb  Schedules", "\u2795  Create Schedule"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB: List / Manage Schedules
    # ══════════════════════════════════════════════════════════════════════════
    with tab_list:
        st.markdown("## Scheduled DQ Runs")
        st.caption("Manage Snowflake Task-based schedules for automated DQ execution. "
                   "Changes take effect after reconciliation.")

        schedules_df = load_schedules()
        if schedules_df.empty:
            empty_state("\u23f0", "No schedules configured",
                        "Create a schedule to automate your DQ runs.")
        else:
            # Summary metrics
            c1, c2, c3 = st.columns(3)
            active_count = int(schedules_df["IS_ACTIVE"].sum())
            c1.metric("Total Schedules", len(schedules_df))
            c2.metric("Active", active_count)
            c3.metric("Suspended", len(schedules_df) - active_count)

            div()

            # Display schedule table
            display_df = schedules_df.copy()
            display_df["STATUS"] = display_df["IS_ACTIVE"].apply(
                lambda x: "\u2705 Active" if x else "\u23f8\ufe0f Suspended")
            display_df["CRON"] = display_df.apply(
                lambda r: f"{r['CRON_EXPRESSION']} ({r['TIMEZONE']})", axis=1)

            st.dataframe(
                display_df[["SCHEDULE_NAME", "SCHEDULE_TYPE", "TARGET_NAME",
                            "CRON", "STATUS", "WAREHOUSE", "LAST_RECONCILED_AT"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "SCHEDULE_NAME": st.column_config.TextColumn("Schedule", width=160),
                    "SCHEDULE_TYPE": st.column_config.TextColumn("Type", width=80),
                    "TARGET_NAME": st.column_config.TextColumn("Target", width=150),
                    "CRON": st.column_config.TextColumn("Cron", width=180),
                    "STATUS": st.column_config.TextColumn("Status", width=120),
                    "WAREHOUSE": st.column_config.TextColumn("Warehouse", width=130),
                    "LAST_RECONCILED_AT": st.column_config.DatetimeColumn(
                        "Last Synced", format="MMM DD HH:mm", width=120),
                },
            )

            div()

            # ── Manage individual schedule ──
            st.markdown("### Manage Schedule")
            sched_opts = dict(zip(
                schedules_df["SCHEDULE_NAME"] + " (" + schedules_df["SCHEDULE_TYPE"] + ")",
                schedules_df["SCHEDULE_ID"]
            ))
            sel_sched_label = st.selectbox("Select schedule", list(sched_opts.keys()),
                                           key="sched_manage_sel")
            sel_sched_id = int(sched_opts[sel_sched_label])
            sel_row = schedules_df[schedules_df["SCHEDULE_ID"] == sel_sched_id].iloc[0]

            col_act, col_del = st.columns([3, 1])
            with col_act:
                if sel_row["IS_ACTIVE"]:
                    if st.button("\u23f8\ufe0f  Suspend", key="sched_suspend"):
                        session.sql(
                            f"UPDATE {FQN}.DQ_SCHEDULE_CONFIG SET IS_ACTIVE = FALSE, "
                            f"UPDATED_AT = CURRENT_TIMESTAMP() WHERE SCHEDULE_ID = {sel_sched_id}"
                        ).collect()
                        load_schedules.clear()
                        st.session_state["_toast_msg"] = "Schedule suspended"
                        st.rerun()
                else:
                    if st.button("\u25b6\ufe0f  Activate", key="sched_activate"):
                        session.sql(
                            f"UPDATE {FQN}.DQ_SCHEDULE_CONFIG SET IS_ACTIVE = TRUE, "
                            f"UPDATED_AT = CURRENT_TIMESTAMP() WHERE SCHEDULE_ID = {sel_sched_id}"
                        ).collect()
                        load_schedules.clear()
                        st.session_state["_toast_msg"] = "Schedule activated"
                        st.rerun()

            with col_del:
                if st.button("\U0001f5d1\ufe0f  Delete", key="sched_delete", type="secondary"):
                    session.sql(
                        f"DELETE FROM {FQN}.DQ_SCHEDULE_CONFIG WHERE SCHEDULE_ID = {sel_sched_id}"
                    ).collect()
                    load_schedules.clear()
                    st.session_state["_toast_msg"] = "Schedule deleted"
                    st.rerun()

            div()

            # ── Reconcile button ──
            st.markdown("### Reconcile Tasks")
            st.caption("Sync DQ_SCHEDULE_CONFIG into live Snowflake Tasks "
                       "(create, update, suspend, or drop tasks).")
            if st.button("\U0001f504  Reconcile Now", type="primary", key="sched_reconcile"):
                with st.status("Reconciling schedules with Snowflake Tasks\u2026", expanded=True) as sts:
                    try:
                        import json as json_lib
                        raw = session.call(f"{FQN}.SP_MANAGE_DQ_SCHEDULES")
                        result = json_lib.loads(raw) if isinstance(raw, str) else raw
                        created = len(result.get("created", []))
                        updated = len(result.get("updated", []))
                        suspended = len(result.get("suspended", []))
                        dropped = len(result.get("dropped", []))
                        errors = result.get("errors", [])
                        st.write(f"\u2705 Created: {created} | Updated: {updated} | "
                                 f"Suspended: {suspended} | Dropped: {dropped}")
                        if errors:
                            for e in errors:
                                st.warning(f"Error: {e}")
                        sts.update(label="Reconciliation complete", state="complete")
                        load_schedules.clear()
                    except Exception as e:
                        sts.update(label="Reconciliation failed", state="error")
                        st.error(f"\u274c {e}")

            div()

            # ── Run history for selected schedule ──
            st.markdown("### Run History")
            run_log = load_run_log(sel_sched_id)
            if run_log.empty:
                empty_state("\u23f1\ufe0f", "No scheduled runs yet",
                            "Runs will appear here after the task executes.")
            else:
                run_log["DURATION"] = (
                    pd.to_datetime(run_log["RUN_COMPLETED_AT"]) -
                    pd.to_datetime(run_log["RUN_STARTED_AT"])
                ).dt.total_seconds().apply(lambda x: f"{x:.1f}s" if pd.notna(x) else "\u2014")
                status_icons = {"SUCCESS": "\u2705", "FAILURE": "\u26a0\ufe0f", "ERROR": "\U0001f534"}
                _default_icon = "\u2753"
                run_log["STATUS"] = run_log["RUN_STATUS"].apply(
                    lambda s: f"{status_icons.get(str(s).upper(), _default_icon)} {s}")
                st.dataframe(
                    run_log[["SCHEDULE_RUN_ID", "STATUS", "BATCH_ID", "DURATION",
                             "RUN_STARTED_AT", "ERROR_MESSAGE"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "SCHEDULE_RUN_ID": st.column_config.NumberColumn("Run", width=60),
                        "STATUS": st.column_config.TextColumn("Status", width=110),
                        "BATCH_ID": st.column_config.NumberColumn("Batch", width=80),
                        "DURATION": st.column_config.TextColumn("Duration", width=80),
                        "RUN_STARTED_AT": st.column_config.DatetimeColumn(
                            "Started", format="MMM DD HH:mm", width=130),
                        "ERROR_MESSAGE": st.column_config.TextColumn("Error", width=250),
                    },
                )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB: Create New Schedule
    # ══════════════════════════════════════════════════════════════════════════
    with tab_create:
        st.markdown("## Create New Schedule")
        st.caption("Configure an automated Snowflake Task to run DQ rules on a cron schedule.")

        # 1. Schedule Level (top)
        schedule_type = st.radio("Schedule Level", ["PROJECT", "DATASET"],
                                 horizontal=True, key="sched_type")

        # 2. Target selection — dynamic based on level
        target_id = None
        target_name = ""
        if schedule_type == "PROJECT":
            projects_df = load_projects()
            if projects_df.empty:
                st.warning("No projects found. Create a project first.")
            else:
                proj_opts = dict(zip(projects_df["PROJECT_NAME"], projects_df["PROJECT_ID"]))
                sel_target = st.selectbox("Target Project", list(proj_opts.keys()),
                                          key="sched_target_proj")
                target_id = int(proj_opts[sel_target]) if sel_target else None
                target_name = sel_target or ""
        else:
            datasets_df = load_datasets()
            if datasets_df.empty:
                st.warning("No datasets found. Create a dataset first.")
            else:
                ds_opts = dict(zip(datasets_df["DATASET_NAME"], datasets_df["DATASET_ID"]))
                sel_target = st.selectbox("Target Dataset", list(ds_opts.keys()),
                                          key="sched_target_ds")
                target_id = int(ds_opts[sel_target]) if sel_target else None
                target_name = sel_target or ""

        # 3. Schedule Name — auto-populated as TASK_P_<project> or TASK_D_<dataset>
        # Write directly to session state so Streamlit picks it up (value= is ignored after first interaction)
        prefix = "TASK_P_" if schedule_type == "PROJECT" else "TASK_D_"
        auto_name = (prefix + target_name.replace(" ", "_")).upper() if target_name else ""
        if auto_name:
            st.session_state["sched_name"] = auto_name
        schedule_name = st.text_input("Schedule Name", key="sched_name")

        # 4. Cron configuration
        # Use a callback on the preset selectbox to push the cron value into session state.
        # This ensures the text_input picks up the new value even after user interaction.
        def _on_preset_change():
            selected = st.session_state.get("sched_preset", "")
            cron_val = CRON_PRESETS.get(selected, "")
            if cron_val:  # not "Custom"
                st.session_state["sched_cron"] = cron_val

        col_preset, col_cron = st.columns([1, 1])
        with col_preset:
            preset = st.selectbox("Frequency Preset", list(CRON_PRESETS.keys()),
                                  key="sched_preset", on_change=_on_preset_change)
        with col_cron:
            # Initialize cron value if not yet set
            if "sched_cron" not in st.session_state:
                st.session_state["sched_cron"] = CRON_PRESETS.get(preset, "0 6 * * *") or "0 6 * * *"
            cron_expr = st.text_input("Cron Expression (5-field)",
                                      placeholder="0 6 * * *",
                                      key="sched_cron")

        # 5. Advanced settings in a popover
        with st.popover("\u2699\ufe0f Advanced Settings", use_container_width=True):
            timezone = st.text_input("Timezone", value="UTC", key="sched_tz")
            warehouse = st.text_input("Warehouse", value="DQ_EXECUTION_WH", key="sched_wh")
            parallel_jobs = st.number_input("Parallel Jobs", 1, 10, 2, key="sched_par")

        div()

        # Submit button
        if st.button("\u2795  Create Schedule", type="primary", use_container_width=True,
                     key="sched_submit"):
            if not schedule_name or not schedule_name.strip():
                st.error("Schedule name is required.")
            elif not cron_expr or not cron_expr.strip():
                st.error("Cron expression is required.")
            elif target_id is None:
                st.error("Select a valid target.")
            else:
                try:
                    session.sql(
                        f"INSERT INTO {FQN}.DQ_SCHEDULE_CONFIG "
                        f"(SCHEDULE_NAME, SCHEDULE_TYPE, TARGET_ID, CRON_EXPRESSION, "
                        f" TIMEZONE, WAREHOUSE, PARALLEL_JOBS, IS_ACTIVE) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?, TRUE)",
                        params=[schedule_name.strip(), schedule_type, target_id,
                                cron_expr.strip(), timezone.strip(),
                                warehouse.strip(), int(parallel_jobs)]
                    ).collect()
                    load_schedules.clear()
                    # Clear form state
                    for k in ["sched_name", "sched_cron", "sched_preset",
                              "sched_target_proj", "sched_target_ds"]:
                        st.session_state.pop(k, None)
                    st.session_state["_toast_msg"] = f"Schedule '{schedule_name}' created"
                    st.rerun()
                except Exception as e:
                    st.error(f"\u274c Failed to create schedule: {e}")

        div()
        st.markdown("### Cron Reference")
        st.code(
            "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500 minute (0-59)\n"
            "\u2502 \u250c\u2500\u2500\u2500\u2500\u2500 hour (0-23)\n"
            "\u2502 \u2502 \u250c\u2500\u2500\u2500 day of month (1-31)\n"
            "\u2502 \u2502 \u2502 \u250c\u2500 month (1-12)\n"
            "\u2502 \u2502 \u2502 \u2502 \u250c day of week (0-7, Sun=0 or 7)\n"
            "\u2502 \u2502 \u2502 \u2502 \u2502\n"
            "* * * * *\n\n"
            "Examples:\n"
            "  0 6 * * *     Daily at 6:00 AM\n"
            "  0 9 * * 1-5   Weekdays at 9:00 AM\n"
            "  0 */2 * * *   Every 2 hours\n"
            "  30 8 1 * *    1st of month at 8:30 AM",
            language=None,
        )
