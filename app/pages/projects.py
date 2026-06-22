# Projects CRUD page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
from shared.db import session, FQN
from shared.helpers import empty_state, flush_toast, search_df, paginate, dialog, sticky_header


def page():
    sticky_header("Configuration &rsaquo; Projects", "Manage DQ projects")

    @st.cache_data(ttl=60)
    def load_projects():
        return session.sql(
            f"SELECT PROJECT_ID,BU_NAME,APP_NAME,PROJECT_NAME,PROJECT_DESC,"
            f"CREATED_BY,CREATED_TIMESTAMP FROM {FQN}.DQ_PROJECTS "
            f"ORDER BY CREATED_TIMESTAMP DESC"
        ).to_pandas()

    projects_df = load_projects()

    @dialog("\u2795  New Project")
    def new_project_dialog():
        st.markdown('<div class="card-title">\U0001f4c1  Project Details</div>', unsafe_allow_html=True)
        p_name = st.text_input("Project Name *", placeholder="e.g., Monthly Reconciliation DQ", key="np_name")
        c1, c2 = st.columns(2)
        with c1:
            p_bu = st.text_input("Business Unit", placeholder="e.g., Finance", key="np_bu")
        with c2:
            p_app = st.text_input("Application", placeholder="e.g., SAP, Salesforce", key="np_app")
        p_desc = st.text_area("Description", placeholder="Purpose of this project\u2026",
                               height=90, key="np_desc")
        if st.button("\u2728  Create Project", use_container_width=True,
                     type="primary", key="np_submit"):
            if not p_name.strip():
                st.error("\u274c  Project Name is required.")
            else:
                try:
                    nid = int(session.sql(
                        f"SELECT COALESCE(MAX(PROJECT_ID),0)+1 n FROM {FQN}.DQ_PROJECTS"
                    ).to_pandas()["N"][0])
                    session.sql(
                        f"INSERT INTO {FQN}.DQ_PROJECTS "
                        f"(PROJECT_ID,BU_NAME,APP_NAME,PROJECT_NAME,PROJECT_DESC,"
                        f"CREATED_BY,CREATED_TIMESTAMP) "
                        f"VALUES(?,?,?,?,?,CURRENT_USER(),CURRENT_TIMESTAMP())",
                        params=[nid, (p_bu or "").upper() or None,
                                (p_app or "").upper() or None,
                                p_name.strip().upper(),
                                p_desc.strip().capitalize() or None],
                    ).collect()
                    load_projects.clear()
                    st.session_state["_toast_msg"] = f"Project {p_name.upper()} created \u2014 ID {nid}"
                    st.rerun()
                except Exception as e:
                    st.error(f"\u274c  {e}")

    flush_toast()

    top_l, top_r = st.columns([5, 1])
    with top_l:
        srch = st.text_input("\U0001f50d  Search projects\u2026",
                             placeholder="Name, business unit, application\u2026",
                             label_visibility="collapsed", key="p_search")
    with top_r:
        if st.button("\u2795  New", use_container_width=True, type="primary", key="p_new_btn"):
            new_project_dialog()

    if projects_df.empty:
        empty_state("\U0001f4c1", "No projects yet",
                    "Create your first project to start monitoring data quality.")
    else:
        filtered = search_df(projects_df, srch)
        st.caption(f"{len(filtered)} of {len(projects_df)} projects")
        page_df = paginate(filtered, "projects")
        st.dataframe(page_df, use_container_width=True, hide_index=True,
            column_config={
                "PROJECT_ID":   st.column_config.NumberColumn("ID", width=55),
                "BU_NAME":      st.column_config.TextColumn("Business Unit", width=140),
                "APP_NAME":     st.column_config.TextColumn("Application", width=130),
                "PROJECT_NAME": st.column_config.TextColumn("Project", width=180),
                "PROJECT_DESC": st.column_config.TextColumn("Description", width=220),
                "CREATED_BY":   st.column_config.TextColumn("Created By", width=120),
                "CREATED_TIMESTAMP": st.column_config.DatetimeColumn(
                    "Created", format="MMM DD, YYYY"),
            })
