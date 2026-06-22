# Shared database connection and Snowflake helper functions for DQ Framework
# Co-authored with CoCo

import streamlit as st
import os
import json as json_lib

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL", 3600))
session = conn.session()

# Read framework location from config table (single source of truth)
# Falls back to defaults if config table is unreachable (e.g., first deploy)
_DEFAULT_DB = "DQ_FRAMEWORK"
_DEFAULT_SCHEMA = "METADATA"
try:
    _cfg = session.sql(
        f"SELECT DQ_DB_NAME, DQ_SCHEMA_NAME "
        f"FROM {_DEFAULT_DB}.{_DEFAULT_SCHEMA}.DQ_JOB_EXEC_CONFIG LIMIT 1"
    ).to_pandas()
    DQ_DB = str(_cfg["DQ_DB_NAME"][0])
    DQ_SCHEMA = str(_cfg["DQ_SCHEMA_NAME"][0])
except Exception:
    DQ_DB = _DEFAULT_DB
    DQ_SCHEMA = _DEFAULT_SCHEMA
FQN = f"{DQ_DB}.{DQ_SCHEMA}"


@st.cache_data(ttl=120)
def get_columns(db, sch, tbl):
    df = session.sql(f'SHOW COLUMNS IN "{db}"."{sch}"."{tbl}"').to_pandas()
    return df[df.columns[2]].tolist()


@st.cache_data(ttl=120)
def get_columns_with_types(db, sch, tbl):
    df = session.sql(f'SHOW COLUMNS IN "{db}"."{sch}"."{tbl}"').to_pandas()
    result = {}
    for _, row in df.iterrows():
        col = row[df.columns[2]]
        try:
            sf_type = json_lib.loads(row[df.columns[3]]).get("type", "TEXT").upper()
        except Exception:
            sf_type = "TEXT"
        result[col] = sf_type
    return result


def filter_cols_by_type(col_type_map, expected_datatype):
    if not expected_datatype or expected_datatype.strip().upper() in ("", "ALL"):
        return list(col_type_map.keys())
    allowed = [t.strip().upper() for t in expected_datatype.split(",")]
    mapping = {
        "NUMBER": ["FIXED", "REAL"], "FLOAT": ["FIXED", "REAL"],
        "TEXT": ["TEXT"], "VARCHAR": ["TEXT"],
        "TIMESTAMP_LTZ": ["TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ"],
        "TIMESTAMP_NTZ": ["TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ"],
        "DATE": ["DATE"],
    }
    sf_ok = set()
    for a in allowed:
        sf_ok.update(mapping.get(a, [a]))
    return [c for c, t in col_type_map.items() if t in sf_ok]


@st.cache_data(ttl=120)
def get_databases():
    df = session.sql("SHOW DATABASES").to_pandas()
    return sorted([n for n in df[df.columns[1]].tolist()
                   if n not in (DQ_DB, "SNOWFLAKE", "COST_MANAGEMENT") and not n.startswith("USER$")])


@st.cache_data(ttl=120)
def get_schemas(db):
    df = session.sql(f'SHOW SCHEMAS IN DATABASE "{db}"').to_pandas()
    return sorted([n for n in df[df.columns[1]].tolist() if n != "INFORMATION_SCHEMA"])


@st.cache_data(ttl=120)
def get_tables(db, schema):
    df = session.sql(f'SHOW TABLES IN "{db}"."{schema}"').to_pandas()
    return sorted(df[df.columns[1]].tolist())
