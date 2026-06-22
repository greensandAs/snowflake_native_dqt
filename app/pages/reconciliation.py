# Reconciliation results page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
import pandas as pd
from shared.db import session, FQN
from shared.helpers import empty_state, div, search_df, paginate, sticky_header


def page():
    sticky_header("Results &rsaquo; Reconciliation", "Source-to-target data reconciliation")

    @st.cache_data(ttl=60)
    def load_recon_datasets():
        return session.sql(
            f"SELECT DISTINCT d.DATASET_ID, d.DATASET_NAME "
            f"FROM {FQN}.DQ_DATASET d "
            f"INNER JOIN {FQN}.DQ_RECON_RESULTS rr ON d.DATASET_ID = rr.DATASET_ID "
            f"ORDER BY d.DATASET_NAME"
        ).to_pandas()

    @st.cache_data(ttl=30)
    def load_recon_results(dsid, run_id=None):
        filt = ""
        if run_id:
            filt = f"AND rr.DATASET_RUN_ID = {int(run_id)}"
        else:
            filt = (f"AND rr.DATASET_RUN_ID = "
                    f"(SELECT MAX(DATASET_RUN_ID) FROM {FQN}.DQ_RECON_RESULTS WHERE DATASET_ID = {int(dsid)})")
        return session.sql(f"""
            SELECT rr.RECON_RESULT_ID, rr.DATASET_RUN_ID, rr.RULE_CONFIG_ID,
                   rr.LAYER, rr.DATA_SOURCE, rr.TABLE_NAME, rr.VALIDATION_ON,
                   rr.SRC_VALUE, rr.CORE_VALUE, rr.CONFORMED_VALUE,
                   rr.CONSUMPTION_VALUE, rr.RESULT, rr.VALIDATION_LOGIC,
                   rr.AUDIT_TIMESTAMP
            FROM {FQN}.DQ_RECON_RESULTS rr
            WHERE rr.DATASET_ID = {int(dsid)} {filt}
            ORDER BY rr.RESULT DESC, rr.AUDIT_TIMESTAMP DESC
        """).to_pandas()

    @st.cache_data(ttl=60)
    def load_recon_runs(dsid):
        return session.sql(
            f"SELECT DISTINCT DATASET_RUN_ID, MAX(AUDIT_TIMESTAMP) AS TS "
            f"FROM {FQN}.DQ_RECON_RESULTS WHERE DATASET_ID = {int(dsid)} "
            f"GROUP BY DATASET_RUN_ID ORDER BY TS DESC LIMIT 20"
        ).to_pandas()

    recon_ds = load_recon_datasets()
    if recon_ds.empty:
        empty_state("\U0001f504", "No reconciliation results yet",
                    "Run a dataset with reconciliation rules to see results here.")
        return

    recon_opts = dict(zip(recon_ds["DATASET_NAME"], recon_ds["DATASET_ID"]))
    sel_name = st.selectbox("Dataset", list(recon_opts.keys()), key="recon_ds")
    sel_id = int(recon_opts[sel_name])

    runs_df = load_recon_runs(sel_id)
    run_labels = {}
    for _, r in runs_df.iterrows():
        ts = pd.to_datetime(r["TS"]).strftime("%b %d %H:%M") if pd.notna(r["TS"]) else "?"
        run_labels[f"#{int(r['DATASET_RUN_ID'])} \u2014 {ts}"] = int(r["DATASET_RUN_ID"])

    sel_run_label = st.selectbox("Run", list(run_labels.keys()), key="recon_run")
    sel_run_id = run_labels[sel_run_label]

    recon_df = load_recon_results(sel_id, sel_run_id)
    if recon_df.empty:
        empty_state("\U0001f4cb", "No reconciliation data for this run")
        return

    total = len(recon_df)
    passed = int((recon_df["RESULT"].str.upper() == "PASS").sum())
    failed = total - passed
    pass_pct = round(100 * passed / total) if total else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Checks", total)
    with k2: st.metric("Passed", passed)
    with k3: st.metric("Failed", failed)
    with k4: st.metric("Pass Rate", f"{pass_pct}%")

    div()

    tab_cards, tab_table = st.tabs(["\U0001f4cb  Detail Cards", "\U0001f4ca  Table View"])

    with tab_cards:
        for _, r in recon_df.iterrows():
            result = str(r["RESULT"]).upper()
            is_pass = result == "PASS"
            cls = "recon-pass" if is_pass else "recon-fail"
            icon = "\u2705" if is_pass else "\u274c"
            src = str(r.get("SRC_VALUE") or "\u2014")
            core = str(r.get("CORE_VALUE") or "\u2014")
            conf = str(r.get("CONFORMED_VALUE") or "\u2014")
            cons = str(r.get("CONSUMPTION_VALUE") or "\u2014")
            layer = str(r.get("LAYER") or "")
            validation = str(r.get("VALIDATION_ON") or "Row Count")

            try:
                delta = abs(int(float(src)) - int(float(core))) if src != "\u2014" and core != "\u2014" else 0
            except (ValueError, TypeError):
                delta = 0
            delta_cls = "recon-delta-zero" if delta == 0 else "recon-delta-pos"

            st.markdown(f"""
            <div class="recon-check-card {cls}">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:700;font-size:.9rem">{icon}  {r.get('TABLE_NAME','')}</span>
                <span style="font-size:.75rem;color:var(--c-text-sub)">{layer} \u00b7 {validation}</span>
              </div>
              <div class="recon-counts">
                <div class="recon-count-item">
                  <span class="recon-count-value">{src}</span>
                  <span class="recon-count-label">Source</span>
                </div>
                <div class="recon-count-item">
                  <span class="recon-count-value">{core}</span>
                  <span class="recon-count-label">Core</span>
                </div>
                <div class="recon-count-item">
                  <span class="recon-count-value">{conf}</span>
                  <span class="recon-count-label">Conformed</span>
                </div>
                <div class="recon-count-item">
                  <span class="recon-count-value">{cons}</span>
                  <span class="recon-count-label">Consumption</span>
                </div>
                <div class="recon-count-item">
                  <span class="recon-count-value {delta_cls}">{delta}</span>
                  <span class="recon-count-label">Delta</span>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

    with tab_table:
        srch = st.text_input("\U0001f50d  Search\u2026", key="recon_srch", label_visibility="collapsed")
        show = search_df(recon_df, srch)
        page_df = paginate(show, "recon_tbl")
        st.dataframe(page_df, use_container_width=True, hide_index=True,
            column_config={
                "RECON_RESULT_ID":  st.column_config.NumberColumn("ID", width=55),
                "DATASET_RUN_ID":   st.column_config.NumberColumn("Run", width=65),
                "TABLE_NAME":       st.column_config.TextColumn("Table", width=140),
                "VALIDATION_ON":    st.column_config.TextColumn("Check", width=120),
                "SRC_VALUE":        st.column_config.TextColumn("Source", width=90),
                "CORE_VALUE":       st.column_config.TextColumn("Core", width=90),
                "CONFORMED_VALUE":  st.column_config.TextColumn("Conformed", width=90),
                "CONSUMPTION_VALUE": st.column_config.TextColumn("Consumption", width=100),
                "RESULT":           st.column_config.TextColumn("Result", width=70),
                "AUDIT_TIMESTAMP":  st.column_config.DatetimeColumn(
                    "Timestamp", format="MMM DD, YYYY HH:mm"),
            })
