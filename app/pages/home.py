# Dashboard/Home page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
import pandas as pd
from shared.db import session, FQN
from shared.helpers import sev_badge, pct_bar, empty_state, div, sticky_header
from shared.charts import chart_donut


def page():
    sticky_header("Home", "Overview of data quality health")

    @st.cache_data(ttl=60)
    def dash_stats():
        p = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_PROJECTS").to_pandas()["C"][0])
        d = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_DATASET").to_pandas()["C"][0])
        rt = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG").to_pandas()["C"][0])
        ra = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE IS_ACTIVE=TRUE"
        ).to_pandas()["C"][0])
        return p, d, rt, ra

    @st.cache_data(ttl=60)
    def dash_sev_dist():
        return session.sql(
            f"SELECT SEVERITY, COUNT(*) CNT FROM {FQN}.DQ_RULE_CONFIG "
            f"WHERE IS_ACTIVE=TRUE GROUP BY SEVERITY ORDER BY CNT DESC"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def dash_dim_dist():
        return session.sql(
            f"SELECT DIMENSION, COUNT(*) CNT FROM {FQN}.DQ_RULE_CONFIG "
            f"GROUP BY DIMENSION ORDER BY CNT DESC"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def dash_recent_runs():
        return session.sql(f"""
            SELECT d.DATASET_NAME, l.RUN_STATUS,
                   l.SUCCESSFULL_EXPECTATIONS, l.UNSUCCESSFULL_EXPECTATIONS,
                   l.SUCCESS_PERCENT, l.CREATED_TIMESTAMP
            FROM {FQN}.DQ_DATASET_RUN_LOG l
            LEFT JOIN {FQN}.DQ_DATASET d ON l.DATASET_ID = d.DATASET_ID
            ORDER BY l.CREATED_TIMESTAMP DESC LIMIT 8
        """).to_pandas()

    @st.cache_data(ttl=60)
    def dash_recon_health():
        try:
            return session.sql(f"""
                SELECT d.DATASET_NAME,
                       SUM(CASE WHEN rr.RESULT='PASS' THEN 1 ELSE 0 END) AS PASSED,
                       COUNT(*) AS TOTAL, MAX(rr.AUDIT_TIMESTAMP) AS LAST_RUN
                FROM {FQN}.DQ_RECON_RESULTS rr
                LEFT JOIN {FQN}.DQ_DATASET d ON rr.DATASET_ID = d.DATASET_ID
                WHERE rr.DATASET_RUN_ID IN (
                    SELECT MAX(DATASET_RUN_ID) FROM {FQN}.DQ_RECON_RESULTS GROUP BY DATASET_ID
                )
                GROUP BY d.DATASET_NAME
            """).to_pandas()
        except Exception:
            return pd.DataFrame()

    @st.cache_data(ttl=60)
    def dash_audit():
        return session.sql(f"""
            SELECT CREATED_BY AS "User", CREATED_TIMESTAMP AS "Timestamp",
                   'Project Created' AS "Action", PROJECT_NAME AS "Detail"
            FROM {FQN}.DQ_PROJECTS
            UNION ALL
            SELECT CREATED_BY, CREATED_TIMESTAMP, 'Dataset Created', DATASET_NAME
            FROM {FQN}.DQ_DATASET
            UNION ALL
            SELECT CREATED_BY, CREATED_TIMESTAMP, 'Rule Created', EXPECTATION_NAME
            FROM {FQN}.DQ_RULE_CONFIG
            ORDER BY "Timestamp" DESC LIMIT 20
        """).to_pandas()

    p, d, rt, ra = dash_stats()
    active_pct = round(100 * ra / rt) if rt else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Projects", p)
    with k2: st.metric("Datasets", d)
    with k3: st.metric("Total Rules", rt)
    with k4: st.metric("Active Rules", ra, delta=f"{active_pct}% activated")

    recon_health = dash_recon_health()
    if not recon_health.empty:
        failed_recon = recon_health[recon_health["PASSED"] < recon_health["TOTAL"]]
        if not failed_recon.empty:
            names = ", ".join(failed_recon["DATASET_NAME"].dropna().tolist())
            st.error(f"\u26a0\ufe0f  **Reconciliation failures detected** in: {names}")
        else:
            st.success(f"\u2705  All reconciliation checks passing across {len(recon_health)} dataset(s).")

    div()
    col_l, col_r = st.columns([5, 7])

    with col_l:
        st.markdown("## Severity Distribution")
        sev_df = dash_sev_dist()
        sev_colors = {"CRITICAL": "#F85149", "HIGH": "#FFA657",
                      "MEDIUM": "#D29922", "LOW": "#3FB950"}
        if not sev_df.empty:
            for _, row in sev_df.iterrows():
                s = str(row["SEVERITY"]).upper()
                cnt = int(row["CNT"])
                pct = round(100 * cnt / rt) if rt else 0
                c = sev_colors.get(s, "#F15A22")
                st.markdown(f"""
                <div style="margin-bottom:.75rem">
                  <div style="display:flex;justify-content:space-between;
                              font-size:.8125rem;font-weight:600;margin-bottom:4px">
                    <span>{sev_badge(s)}</span>
                    <span style="color:var(--c-text-sub)">{cnt} rules</span>
                  </div>
                  {pct_bar(pct, c)}
                </div>""", unsafe_allow_html=True)
        else:
            empty_state("\U0001f4ca", "No rules yet")

        st.markdown("## By Dimension")
        dim_df = dash_dim_dist()
        if not dim_df.empty:
            dim_pal = {"COMPLETENESS": "#3FB950", "UNIQUENESS": "#58A6FF", "VALIDITY": "#FFA657",
                       "CONSISTENCY": "#BC8CFF", "ACCURACY": "#FF7B72", "TIMELINESS": "#79C0FF",
                       "SCHEMA": "#D29922", "RECONCILIATION": "#F15A22", "VOLUME": "#39D353",
                       "NUMERIC": "#A371F7", "FRESHNESS": "#56D4DD", "CONFORMITY": "#E3B341", "SQL": "#FF7B72"}
            st.altair_chart(chart_donut(dim_df, "DIMENSION", "CNT", dim_pal, height=240),
                            use_container_width=True)
        else:
            st.caption("No rules configured yet.")

        if not recon_health.empty:
            st.markdown("## Reconciliation Health")
            for _, r in recon_health.iterrows():
                ok = int(r["PASSED"]) == int(r["TOTAL"])
                pct = round(100 * int(r["PASSED"]) / int(r["TOTAL"])) if r["TOTAL"] else 0
                c = "#3FB950" if ok else "#F85149"
                ts = (pd.to_datetime(r["LAST_RUN"]).strftime("%b %d %H:%M")
                       if pd.notna(r.get("LAST_RUN")) else "")
                st.markdown(f"""
                <div class="info-item">
                  <span class="info-label">{r['DATASET_NAME']}</span>
                  <span style="display:flex;align-items:center;gap:.75rem">
                    <span style="font-size:.75rem;color:var(--c-text-muted)">{ts}</span>
                    <span style="font-weight:800;color:{c}">{pct}%</span>
                  </span>
                </div>""", unsafe_allow_html=True)

    with col_r:
        st.markdown("## Recent Executions")
        try:
            runs_df = dash_recent_runs()
            if not runs_df.empty:
                for _, r in runs_df.iterrows():
                    sp = float(r.get("SUCCESS_PERCENT", 0) or 0)
                    passed = int(r.get("SUCCESSFULL_EXPECTATIONS", 0) or 0)
                    failed = int(r.get("UNSUCCESSFULL_EXPECTATIONS", 0) or 0)
                    color = "#3FB950" if sp >= 100 else "#D29922" if sp >= 80 else "#F85149"
                    ts = (pd.to_datetime(r["CREATED_TIMESTAMP"]).strftime("%b %d %H:%M")
                          if pd.notna(r["CREATED_TIMESTAMP"]) else "")
                    st.markdown(f"""
                    <div style="background:var(--c-surface2);border:1px solid var(--c-border);
                                border-radius:var(--r-md);padding:.875rem 1rem;margin-bottom:.5rem">
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="font-weight:600;font-size:.875rem">{r['DATASET_NAME']}</span>
                        <span style="font-size:.75rem;color:var(--c-text-sub)">{ts}</span>
                      </div>
                      <div style="display:flex;gap:.75rem;margin-top:.375rem;
                                  font-size:.8rem;color:var(--c-text-sub)">
                        <span>\u2713 {passed}</span><span>\u2717 {failed}</span>
                        <span style="color:{color};font-weight:700">{sp:.1f}%</span>
                      </div>
                      {pct_bar(sp, color)}
                    </div>""", unsafe_allow_html=True)
            else:
                empty_state("\u23f1\ufe0f", "No executions yet", "Run DQ rules to see results here")
        except Exception:
            st.info("Run history not available yet.")

    div()
    st.markdown("## Recent Activity")
    try:
        audit_df = dash_audit()
        if not audit_df.empty:
            st.dataframe(audit_df, use_container_width=True, hide_index=True,
                column_config={"Timestamp": st.column_config.DatetimeColumn(
                    format="MMM DD, YYYY HH:mm")})
        else:
            empty_state("\U0001f4cb", "No activity yet")
    except Exception:
        st.info("Audit log not available.")
