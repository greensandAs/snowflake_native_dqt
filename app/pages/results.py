# Rule Results page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
import json as json_lib
import pandas as pd
from shared.db import session, FQN
from shared.helpers import empty_state, sev_badge, div, search_df, paginate, style_table, sticky_header


def page():
    sticky_header("Results &rsaquo; Rule Results", "Inspect DQ rule outcomes")

    @st.cache_data(ttl=60)
    def load_result_datasets():
        return session.sql(
            f"SELECT DISTINCT d.DATASET_ID, d.DATASET_NAME "
            f"FROM {FQN}.DQ_DATASET d "
            f"INNER JOIN {FQN}.DQ_DATASET_RUN_LOG l ON d.DATASET_ID = l.DATASET_ID "
            f"ORDER BY d.DATASET_NAME"
        ).to_pandas()

    @st.cache_data(ttl=30)
    def load_results(dsid, run_id=None):
        filt = f"AND r.DATASET_RUN_ID = {int(run_id)}" if run_id else ""
        if not run_id:
            filt = (f"AND r.DATASET_RUN_ID = "
                    f"(SELECT MAX(DATASET_RUN_ID) FROM {FQN}.DQ_RULE_RESULTS WHERE DATASET_ID = {int(dsid)})")
        return session.sql(f"""
            SELECT r.RULE_CONFIG_ID, r.DATASET_RUN_ID, r.EXPECTATION_NAME,
                   r.IS_SUCCESS, r.ELEMENT_COUNT, r.UNEXPECTED_COUNT,
                   r.UNEXPECTED_PERCENT, r.RUN_TIMESTAMP,
                   rc.COLUMN_NAME, rc.SEVERITY, rc.DIMENSION
            FROM {FQN}.DQ_RULE_RESULTS r
            LEFT JOIN {FQN}.DQ_RULE_CONFIG rc ON r.RULE_CONFIG_ID = rc.RULE_CONFIG_ID
            WHERE r.DATASET_ID = {int(dsid)} {filt}
            ORDER BY r.IS_SUCCESS ASC, r.RULE_CONFIG_ID
        """).to_pandas()

    @st.cache_data(ttl=60)
    def load_runs_for_dataset(dsid):
        return session.sql(
            f"SELECT DATASET_RUN_ID, RUN_STATUS, SUCCESS_PERCENT, CREATED_TIMESTAMP "
            f"FROM {FQN}.DQ_DATASET_RUN_LOG WHERE DATASET_ID = {int(dsid)} "
            f"ORDER BY CREATED_TIMESTAMP DESC LIMIT 30"
        ).to_pandas()

    res_ds = load_result_datasets()
    if res_ds.empty:
        empty_state("\U0001f4ca", "No results yet", "Execute DQ rules to see results here.")
        return

    res_opts = dict(zip(res_ds["DATASET_NAME"], res_ds["DATASET_ID"]))
    sel_name = st.selectbox("Dataset", list(res_opts.keys()), key="res_ds_sel")
    sel_id = int(res_opts[sel_name])

    runs_df = load_runs_for_dataset(sel_id)
    run_labels = {}
    for _, r in runs_df.iterrows():
        ts = pd.to_datetime(r["CREATED_TIMESTAMP"]).strftime("%b %d %H:%M") if pd.notna(r["CREATED_TIMESTAMP"]) else "?"
        label = f"#{int(r['DATASET_RUN_ID'])} \u2014 {r['RUN_STATUS']} \u2014 {ts}"
        run_labels[label] = int(r["DATASET_RUN_ID"])

    sel_run_label = st.selectbox("Run", list(run_labels.keys()), key="res_run_sel")
    sel_run_id = run_labels[sel_run_label]

    results_df = load_results(sel_id, sel_run_id)

    if results_df.empty:
        empty_state("\U0001f4cb", "No rule results for this run")
        return

    total = len(results_df)
    passed = int(results_df["IS_SUCCESS"].sum())
    failed = total - passed
    pass_pct = round(100 * passed / total) if total else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Total Rules", total)
    with k2: st.metric("Passed", passed)
    with k3: st.metric("Failed", failed)
    with k4: st.metric("Pass Rate", f"{pass_pct}%")

    div()

    tab_all, tab_failed, tab_chart = st.tabs(["\U0001f4cb  All Results", "\u274c  Failures Only", "\U0001f4ca  Charts"])

    with tab_all:
        disp = results_df.copy()
        disp["STATUS"] = disp["IS_SUCCESS"].apply(lambda x: "PASS" if x else "FAIL")
        disp["UNEXPECTED_%"] = disp["UNEXPECTED_PERCENT"].apply(
            lambda x: f"{float(x):.2f}%" if pd.notna(x) else "\u2014")
        srch = st.text_input("\U0001f50d  Search\u2026", key="res_search", label_visibility="collapsed")
        show_df = search_df(disp, srch)
        st.caption(f"{len(show_df)} results")
        page_df = paginate(show_df, "results_all")
        st.dataframe(style_table(page_df[["RULE_CONFIG_ID", "EXPECTATION_NAME", "COLUMN_NAME",
                                          "DIMENSION", "SEVERITY", "STATUS",
                                          "ELEMENT_COUNT", "UNEXPECTED_COUNT", "UNEXPECTED_%"]]),
                     use_container_width=True, hide_index=True,
                     column_config={
                         "RULE_CONFIG_ID":  st.column_config.NumberColumn("Rule ID", width=65),
                         "EXPECTATION_NAME": st.column_config.TextColumn("Expectation", width=200),
                         "COLUMN_NAME":     st.column_config.TextColumn("Column", width=120),
                         "DIMENSION":       st.column_config.TextColumn("Dim", width=100),
                         "SEVERITY":        st.column_config.TextColumn("Sev", width=85),
                         "STATUS":          st.column_config.TextColumn("Result", width=70),
                         "ELEMENT_COUNT":   st.column_config.NumberColumn("Rows", width=80),
                         "UNEXPECTED_COUNT": st.column_config.NumberColumn("Unexpected", width=95),
                         "UNEXPECTED_%":    st.column_config.TextColumn("Unexp %", width=75),
                     })

    with tab_failed:
        fail_df = results_df[results_df["IS_SUCCESS"] == False].copy()
        if fail_df.empty:
            empty_state("\u2705", "All rules passed!", "No failures in this run.")
        else:
            for _, r in fail_df.iterrows():
                ue_pct = f"{float(r['UNEXPECTED_PERCENT']):.2f}%" if pd.notna(r['UNEXPECTED_PERCENT']) else "\u2014"
                col_name = r['COLUMN_NAME'] or "\u2014"
                st.markdown(f"""
                <div style="background:var(--c-surface2);border:1px solid var(--c-border);
                            border-left:4px solid var(--c-red);border-radius:var(--r-md);
                            padding:.875rem 1rem;margin-bottom:.5rem">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-weight:700;font-size:.875rem">{r['EXPECTATION_NAME']}</span>
                    {sev_badge(str(r['SEVERITY']))}
                  </div>
                  <div style="display:flex;gap:1rem;margin-top:.375rem;
                              font-size:.8rem;color:var(--c-text-sub)">
                    <span>Column: <b>{col_name}</b></span>
                    <span>Unexpected: <b style="color:var(--c-red)">{int(r['UNEXPECTED_COUNT'] or 0)}</b></span>
                    <span>{ue_pct}</span>
                  </div>
                </div>""", unsafe_allow_html=True)

    with tab_chart:
        if "DIMENSION" in results_df.columns:
            by_dim = results_df.groupby("DIMENSION").agg(
                Passed=("IS_SUCCESS", "sum"),
                Total=("IS_SUCCESS", "count")
            ).reset_index()
            by_dim["Failed"] = by_dim["Total"] - by_dim["Passed"]
            if not by_dim.empty:
                st.markdown("### Pass / Fail by Dimension")
                st.altair_chart(chart_passfail(by_dim, "DIMENSION"), use_container_width=True)

        if "SEVERITY" in results_df.columns:
            by_sev = results_df.groupby("SEVERITY").agg(
                Passed=("IS_SUCCESS", "sum"),
                Total=("IS_SUCCESS", "count")
            ).reset_index()
            by_sev["Failed"] = by_sev["Total"] - by_sev["Passed"]
            if not by_sev.empty:
                st.markdown("### Pass / Fail by Severity")
                st.altair_chart(chart_passfail(by_sev, "SEVERITY", height=200), use_container_width=True)
