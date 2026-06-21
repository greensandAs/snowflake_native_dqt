# Generates an up-to-date schemachange seed script (works both locally and inside Snowflake workspace)

import argparse
import os
import sys
import datetime
from decimal import Decimal
from pathlib import Path

try:
    import snowflake.connector
except ImportError:
    sys.exit("Install: pip install snowflake-connector-python")

FW = "DQ_FRAMEWORK.METADATA"
TABLES = [
    "DQ_JOB_EXEC_CONFIG",
    "DQ_EXPECTATION_MASTER",
    "DQ_EXPECTATION_HANDLER_MAPPING",
    "DQ_EXPECTATION_ARGUMENTS",
]


def _is_snowflake_workspace() -> bool:
    """Detect if running inside a Snowflake workspace kernel."""
    token_path = os.environ.get("SNOWFLAKE_TOKEN_FILE_PATH", "/snowflake/session/token")
    return os.path.exists(token_path) and bool(os.environ.get("SNOWFLAKE_HOST"))


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, (datetime.datetime, datetime.date)):
        return "'" + str(v) + "'"
    return "'" + str(v).replace("'", "''") + "'"


def connect(connection_name=None):
    # 1. In-Snowflake OAuth token (workspace kernel)
    token_path = os.environ.get("SNOWFLAKE_TOKEN_FILE_PATH", "/snowflake/session/token")
    if os.path.exists(token_path) and os.environ.get("SNOWFLAKE_HOST"):
        with open(token_path) as fh:
            token = fh.read().strip()
        print("Connecting via Snowflake workspace OAuth token")
        return snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"],
            account=os.environ.get("SNOWFLAKE_ACCOUNT"),
            token=token,
            authenticator="oauth",
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        )

    # 2. Named connection
    if connection_name:
        print(f"Connecting via named connection: {connection_name}")
        return snowflake.connector.connect(connection_name=connection_name)

    # 3. Env-var password auth
    acct = os.environ.get("SNOWFLAKE_ACCOUNT")
    user = os.environ.get("SNOWFLAKE_USER")
    role = os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
    wh = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    if not acct or not user:
        sys.exit(
            "No credentials found. Provide --connection <name>, or set env vars:\n"
            "  $env:SNOWFLAKE_ACCOUNT = 'jb19822.west-europe.azure'\n"
            "  $env:SNOWFLAKE_USER = 'ASLAM'\n"
            "  $env:SNOWFLAKE_PASSWORD = '...'"
        )

    password = os.environ.get("SNOWFLAKE_PASSWORD")
    if password:
        print(f"Connecting as {user}@{acct} (password auth)")
        return snowflake.connector.connect(
            account=acct, user=user, password=password,
            role=role, warehouse=wh)

    # 4. Key-pair auth
    pk_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    if pk_path and os.path.exists(pk_path):
        from cryptography.hazmat.primitives import serialization
        print(f"Connecting as {user}@{acct} (key-pair auth)")
        passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
        with open(pk_path, "rb") as f:
            pkey = serialization.load_pem_private_key(
                f.read(),
                password=passphrase.encode() if passphrase else None)
        der = pkey.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption())
        return snowflake.connector.connect(
            account=acct, user=user, private_key=der,
            role=role, warehouse=wh)

    sys.exit(
        f"User '{user}' found but no password or key path set.\n"
        "Set $env:SNOWFLAKE_PASSWORD or $env:SNOWFLAKE_PRIVATE_KEY_PATH"
    )


def generate_seed(connection_name=None, output_path=None):
    conn = connect(connection_name)
    cur = conn.cursor()

    out = []
    out.append("-- DQ Framework: seed data for reference/config tables (schemachange versioned)")
    out.append("-- Co-authored with CoCo")
    out.append("-- Idempotent reseed - safe to re-run.")
    out.append("-- Generated on " + datetime.datetime.now().isoformat(timespec="seconds"))
    out.append("USE DATABASE DQ_FRAMEWORK;")
    out.append("USE SCHEMA METADATA;")
    out.append("")

    total_rows = 0
    for tbl in TABLES:
        fq = FW + "." + tbl
        cur.execute("SELECT * FROM " + fq + " ORDER BY 1")
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        total_rows += len(rows)
        out.append("-- " + tbl + " (" + str(len(rows)) + " rows)")
        out.append("DELETE FROM " + fq + ";")
        if rows:
            out.append("INSERT INTO " + fq + " (" + ", ".join(cols) + ") VALUES")
            vals = ["    (" + ", ".join(lit(v) for v in r) + ")" for r in rows]
            out.append(",\n".join(vals) + ";")
        out.append("")

    conn.close()

    if output_path:
        target = Path(output_path)
    else:
        target = Path("V1.1.0__seed_metadata.sql")

    target.write_text("\n".join(out))
    print(f"Wrote {target} ({total_rows} total rows across {len(TABLES)} tables)")


def main():
    parser = argparse.ArgumentParser(description="Generate seed SQL from live Snowflake tables.")
    parser.add_argument("--connection", "-c", default=None,
                        help="Named connection from ~/.snowflake/connections.toml")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path (default: V1.1.0__seed_metadata.sql in current dir)")
    args = parser.parse_args()
    generate_seed(connection_name=args.connection, output_path=args.output)


# ── Entry point: workspace kernel bypasses argparse, CLI uses it ──
if _is_snowflake_workspace():
    generate_seed()
elif __name__ == "__main__":
    main()
