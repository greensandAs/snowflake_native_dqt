# Rule configuration page for DQ Framework app
# Co-authored with CoCo

import streamlit as st
import json as json_lib
from shared.db import (session, FQN, get_databases, get_schemas, get_tables,
                       get_columns, get_columns_with_types, filter_cols_by_type)
from shared.helpers import (empty_state, search_df, paginate, style_table,
                            render_stepper, sticky_header)


def page():
    sticky_header("Configuration &rsaquo; Rules", "Configure DQ rule checks")

    @st.cache_data(ttl=60)
    def load_datasets_for_rules():
        return session.sql(
            f"SELECT d.DATASET_ID,d.DATASET_NAME,d.DATABASE_NAME,d.SCHEMA_NAME,"
            f"d.TABLE_NAME,d.DATASET_TYPE,COALESCE(p.PROJECT_NAME,'\u2014') AS PROJECT_NAME "
            f"FROM {FQN}.DQ_DATASET d "
            f"LEFT JOIN {FQN}.DQ_PROJECTS p ON d.PROJECT_ID = p.PROJECT_ID "
            f"ORDER BY d.DATASET_NAME"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_expectations():
        return session.sql(
            f"SELECT EXPECTATION_ID,VALIDATION_NAME,DESCRIPTION,DIMENSION,"
            f"CHECK_TYPE,CHECK_LEVEL,EXPECTED_DATATYPE "
            f"FROM {FQN}.DQ_EXPECTATION_MASTER WHERE IS_ACTIVE='Y' ORDER BY VALIDATION_NAME"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_exp_args(eid):
        return session.sql(
            f"SELECT ARGUMENT_NAME,ARGUMENT_TYPE,ARGUMENT_DESC,IS_MANDATORY,"
            f"DEFAULT_VALUE,HELP_TEXT FROM {FQN}.DQ_EXPECTATION_ARGUMENTS "
            f"WHERE EXPECTATION_ID=?", params=[int(eid)]
        ).to_pandas()

    @st.cache_data(ttl=30)
    def load_rules(dsid):
        return session.sql(
            f"SELECT RULE_CONFIG_ID,EXPECTATION_NAME,COLUMN_NAME,KWARGS,"
            f"DIMENSION,SEVERITY,IS_ACTIVE FROM {FQN}.DQ_RULE_CONFIG "
            f"WHERE DATASET_ID=? ORDER BY RULE_CONFIG_ID", params=[int(dsid)]
        ).to_pandas()

    ds_df = load_datasets_for_rules()
    if ds_df.empty:
        empty_state("\U0001f4e6", "No datasets found", "Create a dataset before configuring rules.")
        return

    ds_opts = dict(zip(ds_df["DATASET_NAME"], ds_df["DATASET_ID"]))
    r_dataset = st.selectbox("Dataset", list(ds_opts.keys()),
                             help="Select a dataset to view or add rules")
    ds_id = int(ds_opts[r_dataset])
    ds_row = ds_df[ds_df["DATASET_ID"] == ds_id].iloc[0]

    rule_count = int(session.sql(
        f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID=?",
        params=[ds_id]).to_pandas()["C"][0])
    render_stepper(ds_row["PROJECT_NAME"], r_dataset, rule_count)

    tab_view, tab_add = st.tabs(["\U0001f4cb  Existing Rules", "\u2795  Add Rule"])

    with tab_view:
        rules_df = load_rules(ds_id)
        if rules_df.empty:
            empty_state("\u2705", "No rules yet",
                        f"Dataset \u201c{r_dataset}\u201d has no validation rules configured.",
                        "\u2192  Open the \u2018\u2795  Add Rule\u2019 tab above to create your first rule.")
        else:
            bar_l, bar_r = st.columns([5, 1])
            with bar_l:
                srch_r = st.text_input("\U0001f50d  Search rules\u2026",
                                       label_visibility="collapsed", key="r_search")
            with bar_r:
                with st.popover("\u2699\ufe0f  Filters", use_container_width=True):
                    fs = st.multiselect("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], key="rf_sev")
                    fx = st.multiselect("Status", ["Active", "Inactive"], key="rf_stat")
                    fd = st.multiselect("Dimension", sorted(rules_df["DIMENSION"].dropna().unique()), key="rf_dim")
                    fc = st.multiselect("Column", sorted(rules_df["COLUMN_NAME"].dropna().unique()), key="rf_col")

            disp = rules_df.copy()
            if fs: disp = disp[disp["SEVERITY"].isin(fs)]
            if fx: disp = disp[disp["IS_ACTIVE"].isin(
                [{"Active": True, "Inactive": False}[s] for s in fx])]
            if fd: disp = disp[disp["DIMENSION"].isin(fd)]
            if fc: disp = disp[disp["COLUMN_NAME"].isin(fc)]
            disp = search_df(disp, srch_r)
            st.caption(f"{len(disp)} of {len(rules_df)} rules")
            page_df = paginate(disp, "rules")
            st.dataframe(style_table(page_df), use_container_width=True, hide_index=True,
                column_config={
                    "RULE_CONFIG_ID":   st.column_config.NumberColumn("ID", width=55),
                    "EXPECTATION_NAME": st.column_config.TextColumn("Expectation", width=200),
                    "COLUMN_NAME":      st.column_config.TextColumn("Column", width=130),
                    "DIMENSION":        st.column_config.TextColumn("Dimension", width=120),
                    "SEVERITY":         st.column_config.TextColumn("Severity", width=90),
                    "IS_ACTIVE":        st.column_config.CheckboxColumn("Active", width=65),
                    "KWARGS":           st.column_config.TextColumn("Config", width=200),
                })

    with tab_add:
        exp_df = load_expectations()
        if exp_df.empty:
            st.warning("\u26a0\ufe0f  No active expectations found \u2014 contact administrator.")
            return

        st.markdown('<div class="card"><div class="card-title">\U0001f3af  Choose Expectation</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            dims = sorted(exp_df["DIMENSION"].dropna().unique().tolist())
            r_dim = st.selectbox("Quality Dimension *", dims)
        with c2:
            fexp = exp_df[exp_df["DIMENSION"] == r_dim]
            exp_opts = dict(zip(fexp["VALIDATION_NAME"], fexp["EXPECTATION_ID"]))
            r_exp = st.selectbox("Expectation *", list(exp_opts.keys()))

        eid = int(exp_opts[r_exp])
        exp_row = fexp[fexp["EXPECTATION_ID"] == eid].iloc[0]
        if exp_row["DESCRIPTION"]:
            st.info(f"\U0001f4d6  {exp_row['DESCRIPTION']}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">\u2699\ufe0f  Arguments</div>',
                    unsafe_allow_html=True)
        args_df = load_exp_args(eid)
        col_list = []
        if (ds_row["DATASET_TYPE"] == "TABLE"
                and ds_row["DATABASE_NAME"] and ds_row["TABLE_NAME"]):
            col_type_map = get_columns_with_types(
                ds_row["DATABASE_NAME"], ds_row["SCHEMA_NAME"], ds_row["TABLE_NAME"])
            col_list = filter_cols_by_type(
                col_type_map, exp_row.get("EXPECTED_DATATYPE", "ALL"))

        kwargs_dict = {}
        RECON_EXP = "expect_table_row_count_to_equal_other_table"
        SRCFILE_EXP = "expect_table_row_count_to_equal_source_file"

        if r_exp == RECON_EXP:
            _render_recon_args(kwargs_dict, ds_row, col_list, r_dataset)
        elif r_exp == SRCFILE_EXP:
            _render_srcfile_args(kwargs_dict, ds_row, r_dataset)
        elif not args_df.empty:
            _render_generic_args(args_df, kwargs_dict, col_list, ds_df, r_dataset)
        else:
            st.caption("No arguments required for this expectation.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">\U0001f3f7\ufe0f  Rule Settings</div>',
                    unsafe_allow_html=True)
        s1, s2 = st.columns(2)
        with s1: r_sev = st.selectbox("Severity *", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        with s2: r_act = st.checkbox("Enable Immediately", value=True)
        r_desc = st.text_area("Rule Description",
                              placeholder="Why this validation matters\u2026", height=80)
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("\u2728  Create Rule", use_container_width=True, type="primary"):
            if r_exp == RECON_EXP:
                missing = ["SOURCE_TABLE"] if not kwargs_dict.get("source_table") else []
            else:
                missing = ([r["ARGUMENT_NAME"].upper()
                            for _, r in args_df.iterrows()
                            if r["IS_MANDATORY"] and not kwargs_dict.get(r["ARGUMENT_NAME"])]
                           if not args_df.empty else [])
            if missing:
                st.error(f"\u274c  Missing required arguments: {', '.join(missing)}")
            else:
                try:
                    kw_json = json_lib.dumps(kwargs_dict) if kwargs_dict else None
                    col_name = (kwargs_dict.get("column")
                                or kwargs_dict.get("column_name")
                                or kwargs_dict.get("COLUMN"))
                    if not col_name:
                        parts = [v for k, v in kwargs_dict.items()
                                 if k.lower() in ("column_a", "column_b") and v]
                        col_name = ",".join(parts) if parts else None
                    nid = int(session.sql(
                        f"SELECT COALESCE(MAX(RULE_CONFIG_ID),0)+1 n "
                        f"FROM {FQN}.DQ_RULE_CONFIG"
                    ).to_pandas()["N"][0])
                    session.sql(
                        f"INSERT INTO {FQN}.DQ_RULE_CONFIG "
                        f"(RULE_CONFIG_ID,EXPECTATION_ID,DATASET_ID,EXPECTATION_NAME,"
                        f"EXPECTATION_TYPE,CHECK_TYPE,KWARGS,DIMENSION,COLUMN_NAME,"
                        f"RULE_DESCRIPTION,SEVERITY,IS_ACTIVE,CREATED_BY,CREATED_TIMESTAMP) "
                        f"VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_USER(),CURRENT_TIMESTAMP())",
                        params=[nid, eid, ds_id, r_exp.upper(),
                                str(exp_row["CHECK_TYPE"]).upper(),
                                str(exp_row["CHECK_TYPE"]).upper(),
                                kw_json, r_dim.upper(),
                                col_name.upper() if col_name else None,
                                r_desc.strip().capitalize() or None,
                                r_sev.upper(), r_act],
                    ).collect()
                    st.success(f"\u2705  Rule **{r_exp.upper()}** created \u2014 ID {nid}")
                    load_rules.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"\u274c  {e}")


def _render_recon_args(kwargs_dict, ds_row, col_list, r_dataset):
    st.caption(f"\U0001f3af  Target (validated) = **{r_dataset}** \u00b7 pick the SOURCE table below.")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        s_db = st.selectbox("Source Database *", get_databases(), key="rc_sdb")
    with sc2:
        s_sch = st.selectbox("Source Schema *",
                             get_schemas(s_db) if s_db else [], key="rc_ssch")
    with sc3:
        src_tbls = get_tables(s_db, s_sch) if s_db and s_sch else []
        if s_db == ds_row["DATABASE_NAME"] and s_sch == ds_row["SCHEMA_NAME"]:
            src_tbls = [t for t in src_tbls if t != ds_row["TABLE_NAME"]]
        s_tbl = st.selectbox("Source Table *", src_tbls, key="rc_stbl")
    kwargs_dict["source_database"] = (s_db or "").upper() or None
    kwargs_dict["source_schema"] = (s_sch or "").upper() or None
    kwargs_dict["source_table"] = (s_tbl or "").upper() or None
    rc_mode = st.radio(
        "Recon Mode",
        ["Plain row-count equality", "SCD Type 1 (total dedup)", "SCD Type 2 (active/inactive)"],
        horizontal=True, key="rc_mode")
    scd = 1 if "Type 1" in rc_mode else (2 if "Type 2" in rc_mode else 0)
    kwargs_dict["scd_type"] = scd
    recon_mode = st.radio(
        "Recon Scope",
        ["Incremental (delta since last run)", "Full (entire table)"],
        horizontal=True, key="rc_recon_mode")
    kwargs_dict["recon_mode"] = "full" if "Full" in recon_mode else "incremental"
    if scd in (1, 2):
        if col_list:
            pkeys = st.multiselect("Business / Partition Keys *", col_list, key="rc_pk")
            kwargs_dict["partition_keys"] = [k.upper() for k in pkeys]
        else:
            pk_txt = st.text_input("Business / Partition Keys * (comma-separated)", key="rc_pk_txt")
            kwargs_dict["partition_keys"] = [k.strip().upper() for k in pk_txt.split(",") if k.strip()]
        src_cols = get_columns(s_db, s_sch, s_tbl) if (s_db and s_sch and s_tbl) else []
        tgt_cols = (get_columns(ds_row["DATABASE_NAME"], ds_row["SCHEMA_NAME"], ds_row["TABLE_NAME"])
                    if ds_row["DATASET_TYPE"] == "TABLE"
                    and ds_row["DATABASE_NAME"] and ds_row["TABLE_NAME"] else [])

        def _date_idx(cols, default):
            return cols.index(default) if default in cols else 0

        d1, d2 = st.columns(2)
        with d1:
            if src_cols:
                kwargs_dict["core_insert_date_col"] = st.selectbox(
                    "Source Date Col", src_cols,
                    index=_date_idx(src_cols, "INSERT_DATE_TIME"), key="rc_cdate").upper()
            else:
                kwargs_dict["core_insert_date_col"] = (st.text_input(
                    "Source Date Col", value="INSERT_DATE_TIME", key="rc_cdate") or "INSERT_DATE_TIME").upper()
        with d2:
            if tgt_cols:
                kwargs_dict["conformed_update_date_col"] = st.selectbox(
                    "Comparison Date Col", tgt_cols,
                    index=_date_idx(tgt_cols, "UPDATE_DATE_TIME"), key="rc_udate").upper()
            else:
                kwargs_dict["conformed_update_date_col"] = (st.text_input(
                    "Comparison Date Col", value="UPDATE_DATE_TIME", key="rc_udate") or "UPDATE_DATE_TIME").upper()
        if scd == 2:
            f1, f2, f3 = st.columns(3)
            with f1:
                kwargs_dict["active_flag_col"] = (st.text_input(
                    "Active Flag Col", value="IS_ACTIVE", key="rc_flagc") or "IS_ACTIVE").upper()
            with f2:
                kwargs_dict["active_value"] = st.text_input("Active Value", value="Y", key="rc_av") or "Y"
            with f3:
                kwargs_dict["inactive_value"] = st.text_input("Inactive Value", value="N", key="rc_iv") or "N"


def _render_srcfile_args(kwargs_dict, ds_row, r_dataset):
    st.caption(f"\U0001f3af  Validates CORE table **{r_dataset}** against source-file counts "
               f"recorded in an audit-control table.")
    DEF_DB, DEF_SCH, DEF_TBL = "PRISM_META_PROD", "META", "AUDIT_CONTROL"

    def _sel_idx(opts, default):
        return opts.index(default) if default in opts else 0

    dbs = get_databases()
    a1, a2, a3 = st.columns(3)
    with a1:
        a_db = st.selectbox("Audit Database", dbs, index=_sel_idx(dbs, DEF_DB), key="sf_db")
    with a2:
        a_schs = get_schemas(a_db) if a_db else []
        a_sch = st.selectbox("Audit Schema", a_schs, index=_sel_idx(a_schs, DEF_SCH), key="sf_sch")
    with a3:
        a_tbls = get_tables(a_db, a_sch) if a_db and a_sch else []
        a_tbl = st.selectbox("Audit Table", a_tbls, index=_sel_idx(a_tbls, DEF_TBL), key="sf_tbl")
    if a_db and a_sch and a_tbl:
        kwargs_dict["audit_control_table"] = f"{a_db}.{a_sch}.{a_tbl}".upper()

    a_cols = get_columns(a_db, a_sch, a_tbl) if (a_db and a_sch and a_tbl) else []
    cc1, cc2 = st.columns(2)
    with cc1:
        if a_cols:
            kwargs_dict["source_count_col"] = st.selectbox(
                "Source Count Column", a_cols,
                index=_sel_idx(a_cols, "NUMBER_OF_RECORDS_SOURCE"), key="sf_srccol").upper()
        else:
            kwargs_dict["source_count_col"] = (st.text_input(
                "Source Count Column", value="NUMBER_OF_RECORDS_SOURCE",
                key="sf_srccol") or "NUMBER_OF_RECORDS_SOURCE").upper()
    with cc2:
        if a_cols:
            kwargs_dict["target_count_col"] = st.selectbox(
                "Target (CORE) Count Column", a_cols,
                index=_sel_idx(a_cols, "NUMBER_OF_RECORDS_TARGET"), key="sf_tgtcol").upper()
        else:
            kwargs_dict["target_count_col"] = (st.text_input(
                "Target (CORE) Count Column", value="NUMBER_OF_RECORDS_TARGET",
                key="sf_tgtcol") or "NUMBER_OF_RECORDS_TARGET").upper()


def _render_generic_args(args_df, kwargs_dict, col_list, ds_df, r_dataset):
    arg_rows = list(args_df.iterrows())
    for i in range(0, len(arg_rows), 2):
        cols = st.columns(2)
        for j, col_ctx in enumerate(cols):
            if i + j >= len(arg_rows):
                break
            _, arg = arg_rows[i + j]
            aname = arg["ARGUMENT_NAME"]
            atype = str(arg["ARGUMENT_TYPE"] or "str").lower()
            mand = arg["IS_MANDATORY"]
            defv = str(arg["DEFAULT_VALUE"] or "").strip()
            help_t = str(arg["HELP_TEXT"] or "").strip()
            desc = str(arg["ARGUMENT_DESC"] or "").strip()
            label = f"{aname.upper()} {'*' if mand else ''}"
            is_col = aname.lower() in ("column", "column_a", "column_b") and col_list
            is_cols = aname.lower() in ("column_set", "column_list", "columns") and col_list
            is_bool = "bool" in atype
            is_num = any(t in atype for t in ("int", "float", "number", "comparable"))
            is_pct = "mostly" in aname.lower()
            is_list = any(t in atype for t in ("list", "set"))
            is_other_ds = aname.lower() == "other_dataset_name"
            with col_ctx:
                if is_other_ds:
                    other_opts = [n for n in ds_df["DATASET_NAME"].tolist() if n != r_dataset]
                    v = st.selectbox(label, [""] + other_opts, key=f"a_{aname}", help=desc)
                    kwargs_dict[aname] = v or None
                elif is_cols:
                    v = st.multiselect(label, col_list, key=f"a_{aname}", help=desc)
                    kwargs_dict[aname] = v or None
                elif is_col:
                    v = st.selectbox(label, [""] + col_list, key=f"a_{aname}", help=desc)
                    kwargs_dict[aname] = v or None
                elif is_bool:
                    v = st.selectbox(label, ["TRUE", "FALSE"],
                                     index=0 if defv.lower() in ("true", "1") else 1,
                                     key=f"a_{aname}", help=desc)
                    kwargs_dict[aname] = v == "TRUE"
                elif is_pct:
                    v = st.number_input(label, 0.0, 1.0,
                                        float(defv) if defv else 1.0,
                                        step=0.01, format="%.2f",
                                        key=f"a_{aname}", help=desc)
                    kwargs_dict[aname] = v
                elif is_num:
                    v = st.number_input(label, value=float(defv) if defv else 0.0,
                                        key=f"a_{aname}", help=desc)
                    kwargs_dict[aname] = v
                elif is_list:
                    v = st.text_input(label, value=defv, key=f"a_{aname}",
                                      help=desc, placeholder=help_t or "Comma-separated values")
                    kwargs_dict[aname] = (
                        "[" + ",".join(f"'{x.strip()}'" for x in v.split(",") if x.strip()) + "]"
                        if v else None
                    )
                else:
                    v = st.text_input(label, value=defv, key=f"a_{aname}",
                                      help=desc, placeholder=help_t)
                    kwargs_dict[aname] = v or None
