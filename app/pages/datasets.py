# Datasets CRUD page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
import json as json_lib
from shared.db import session, FQN, get_databases, get_schemas, get_tables, get_columns
from shared.helpers import empty_state, search_df, paginate, sticky_header


def page():
    sticky_header("Configuration &rsaquo; Datasets", "Register and manage datasets")

    @st.cache_data(ttl=60)
    def load_datasets():
        return session.sql(
            f"SELECT DATASET_ID,PROJECT_ID,DATASET_TYPE,DATASET_NAME,DATABASE_NAME,"
            f"SCHEMA_NAME,TABLE_NAME,CREATED_BY,CREATED_TIMESTAMP "
            f"FROM {FQN}.DQ_DATASET ORDER BY CREATED_TIMESTAMP DESC"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_projects_for_ds():
        return session.sql(
            f"SELECT PROJECT_ID,PROJECT_NAME FROM {FQN}.DQ_PROJECTS ORDER BY PROJECT_NAME"
        ).to_pandas()

    datasets_df = load_datasets()
    projects_df = load_projects_for_ds()
    proj_options = (dict(zip(projects_df["PROJECT_NAME"], projects_df["PROJECT_ID"]))
                    if not projects_df.empty else {})

    tab_list, tab_new = st.tabs(["\U0001f4cb  All Datasets", "\u2795  Create New"])

    with tab_list:
        if datasets_df.empty:
            empty_state("\U0001f4e6", "No datasets yet",
                        "Link a table or SQL query to start writing rules.")
        else:
            srch = st.text_input("\U0001f50d  Search datasets\u2026", label_visibility="collapsed",
                                 key="ds_search", placeholder="Name, database, table\u2026")
            filtered = search_df(datasets_df, srch)
            st.caption(f"{len(filtered)} of {len(datasets_df)} datasets")
            page_df = paginate(filtered, "datasets")
            st.dataframe(page_df, use_container_width=True, hide_index=True,
                column_config={
                    "DATASET_ID":    st.column_config.NumberColumn("ID", width=55),
                    "DATASET_TYPE":  st.column_config.TextColumn("Type", width=80),
                    "DATASET_NAME":  st.column_config.TextColumn("Name", width=160),
                    "DATABASE_NAME": st.column_config.TextColumn("Database", width=120),
                    "SCHEMA_NAME":   st.column_config.TextColumn("Schema", width=120),
                    "TABLE_NAME":    st.column_config.TextColumn("Table", width=130),
                    "CREATED_TIMESTAMP": st.column_config.DatetimeColumn(
                        "Created", format="MMM DD, YYYY"),
                })

    with tab_new:
        if not proj_options:
            st.warning("\u26a0\ufe0f  No projects found \u2014 create a project first.")
        else:
            st.markdown('<div class="card"><div class="card-title">\U0001f4e6  Dataset Details</div>',
                        unsafe_allow_html=True)

            d_project = st.selectbox("Project *", list(proj_options.keys()))
            d_type = st.selectbox(
                "Dataset Type *", ["TABLE", "QUERY"],
                help="TABLE = direct table \u00b7 QUERY = custom SQL. "
                     "(Reconciliation is now a rule: add 'expect_table_row_count_to_equal_other_table'.)",
            )
            d_name = st.text_input("Dataset Name *", placeholder="e.g., Customer Master")
            d_desc = st.text_area("Description", placeholder="What data does this contain?",
                                  height=70)

            d_db = d_schema_val = d_table = d_custom_sql = None
            d_pk = []

            if d_type == "TABLE":
                st.markdown(
                    '<div class="card-title" style="margin-top:1rem">\U0001f5c4\ufe0f  Source Location</div>',
                    unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1: d_db = st.selectbox("Database *", get_databases(), key="ds_db")
                with c2:
                    d_schema_val = st.selectbox("Schema *",
                        get_schemas(d_db) if d_db else [], key="ds_schema")
                with c3:
                    d_table = st.selectbox("Table *",
                        get_tables(d_db, d_schema_val) if d_db and d_schema_val else [],
                        key="ds_table")
                if d_db and d_schema_val and d_table:
                    d_pk = st.multiselect("Primary Key Columns",
                                          options=get_columns(d_db, d_schema_val, d_table),
                                          key="ds_pk",
                                          help="Columns that uniquely identify each row")

            elif d_type == "QUERY":
                d_custom_sql = st.text_area("Custom SQL Query *",
                    placeholder="SELECT * FROM schema.table WHERE \u2026", height=150, key="ds_sql")

            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("\u2728  Create Dataset", use_container_width=True, type="primary"):
                if not d_name.strip():
                    st.error("\u274c  Dataset Name is required.")
                elif d_type == "TABLE" and not (d_db and d_schema_val and d_table):
                    st.error("\u274c  Database, Schema, and Table are all required.")
                elif d_type == "QUERY" and not d_custom_sql:
                    st.error("\u274c  Custom SQL is required.")
                else:
                    try:
                        pid = int(proj_options[d_project])
                        pk_json = json_lib.dumps({"primary_key": [k.upper() for k in d_pk]}) if d_pk else None
                        nid = int(session.sql(
                            f"SELECT COALESCE(MAX(DATASET_ID),0)+1 n FROM {FQN}.DQ_DATASET"
                        ).to_pandas()["N"][0])
                        session.sql(
                            f"INSERT INTO {FQN}.DQ_DATASET "
                            f"(DATASET_ID,PROJECT_ID,DATASET_TYPE,DATASET_NAME,DATABASE_NAME,"
                            f"SCHEMA_NAME,TABLE_NAME,CUSTOM_SQL,PRIMARY_KEY_COLUMNS,"
                            f"DATASET_DESCRIPTION,CREATED_BY,CREATED_TIMESTAMP) "
                            f"VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_USER(),CURRENT_TIMESTAMP())",
                            params=[nid, pid, d_type, d_name.strip().upper(),
                                    (d_db or "").upper() or None,
                                    (d_schema_val or "").upper() or None,
                                    (d_table or "").upper() or None,
                                    d_custom_sql or None, pk_json,
                                    d_desc.strip().capitalize() or None],
                        ).collect()
                        st.success(f"\u2705  Dataset **{d_name.upper()}** created \u2014 ID {nid}")
                        load_datasets.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"\u274c  {e}")
