from __future__ import annotations

import glob
import os
import sys
import time

try:
    import snowflake.connector
except ImportError:
    sys.exit("snowflake-connector-python is required:  pip install snowflake-connector-python")

# ── Paths — kernel CWD is already inside DQM/ ──
HERE = os.getcwd()
DDL_DIR = os.path.join(HERE, "DDL")
SEED_FILE = os.path.join(HERE, "DML.sql")
PROC_DIR = os.path.join(HERE, "Procedures")
HANDLER_DIR = os.path.join(PROC_DIR, "Handlers")

FRAMEWORK_DB = "DQ_FRAMEWORK"
FRAMEWORK_SCHEMA = "METADATA"


def get_connection():
    token_path = os.environ.get("SNOWFLAKE_TOKEN_FILE_PATH", "/snowflake/session/token")
    if os.path.exists(token_path) and os.environ.get("SNOWFLAKE_HOST"):
        with open(token_path) as fh:
            token = fh.read().strip()
        return snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"],
            account=os.environ.get("SNOWFLAKE_ACCOUNT"),
            token=token,
            authenticator="oauth",
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ.get("SNOWFLAKE_PASSWORD"),
        authenticator=os.environ.get("SNOWFLAKE_AUTHENTICATOR", "snowflake"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    )


def run_file(conn, path: str) -> tuple[bool, str]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        sql = fh.read()
    try:
        cursors = conn.execute_string(sql, remove_comments=False)
        for cur in cursors:
            _ = cur.rowcount
        return True, ""
    except Exception as e:
        return False, str(e)


def collect_files(phase: str) -> list[str]:
    files: list[str] = []
    if phase in ("tables", "all"):
        files.extend(sorted(glob.glob(os.path.join(DDL_DIR, "V*__*.sql"))))
    if phase in ("seed", "all"):
        if os.path.exists(SEED_FILE):
            files.append(SEED_FILE)
    if phase in ("procedures", "all"):
        for fn in ("R__execute_dq_rules_master.sql", "R__execute_dq_rules_project.sql"):
            p = os.path.join(PROC_DIR, fn)
            if os.path.exists(p):
                files.append(p)
        files.extend(sorted(glob.glob(os.path.join(HANDLER_DIR, "R__*.sql"))))
    return files


def deploy(phase: str = "all") -> int:
    files = collect_files(phase)
    if not files:
        print(f"No files found for phase '{phase}'.")
        return 1

    print(f"Phase: {phase}  |  {len(files)} file(s) to deploy")
    if phase in ("tables", "all"):
        print("'tables' phase uses CREATE TABLE IF NOT EXISTS — existing tables/data preserved.")

    conn = get_connection()
    try:
        conn.cursor().execute(f"USE DATABASE {FRAMEWORK_DB}")
        conn.cursor().execute(f"USE SCHEMA {FRAMEWORK_SCHEMA}")
    except Exception:
        pass

    ok, failed = 0, []
    t0 = time.time()
    for f in files:
        rel = os.path.relpath(f, HERE)
        success, err = run_file(conn, f)
        if success:
            ok += 1
            print(f"  OK: {rel}")
        else:
            failed.append((rel, err))
            print(f"  FAIL: {rel}\n       {err.splitlines()[0] if err else ''}")

    conn.close()
    dur = time.time() - t0
    print(f"\nDone in {dur:.1f}s — {ok} succeeded, {len(failed)} failed.")
    if failed:
        print("\nFailures:")
        for rel, err in failed:
            print(f"  - {rel}: {err.splitlines()[0] if err else ''}")
        return 1
    return 0


# ── Deploy all phases ──
deploy(phase="all")
