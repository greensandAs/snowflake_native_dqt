# DQ Framework — Snowflake-Native Data Quality Engine

## What is this?

A **metadata-driven, zero-code data quality framework** built entirely on Snowflake. It allows teams to define, execute, and monitor data quality rules against any table or custom SQL query — without writing validation logic manually.

The framework ships with **45 pre-built check types** (not-null, uniqueness, range, regex, data type, freshness, SCD reconciliation, source-file count match, and more) that can be configured via a Streamlit UI or direct metadata inserts.

---

## Why do you need it?

| Problem | How this framework solves it |
|---------|------------------------------|
| Bad data reaches downstream consumers silently | Rules run proactively and flag failures before consumption |
| Every team writes ad-hoc validation scripts | Centralized rule library — configure once, reuse everywhere |
| No visibility into data health over time | Results dashboard with pass/fail trends by dimension |
| Hard to trace what failed and why | Full audit trail per rule, per step, per run |
| Failed records are lost or hard to find | Structured failure tables capture exact rows that violated rules |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       DQ_FRAMEWORK (Database)                        │
├───────────────────────────┬─────────────────────────────────────────┤
│     METADATA (Schema)     │            DQ_ERRORS (Schema)           │
│                           │                                         │
│  DQ_PROJECTS              │  <DATASET>_DQ_FAILURE   (failed rows)   │
│  DQ_DATASET               │  VW_<DATASET>_DQ_FAILURE (pivot view)   │
│  DQ_RULE_CONFIG           │                                         │
│  DQ_EXPECTATION_MASTER    │                                         │
│  DQ_EXPECTATION_ARGUMENTS │                                         │
│  DQ_EXPECTATION_HANDLER_  │                                         │
│    MAPPING                │                                         │
│  DQ_RULE_RESULTS          │                                         │
│  DQ_RULE_AUDIT_LOG        │                                         │
│  DQ_DATASET_RUN_LOG       │                                         │
│  DQ_PROJECT_RUN_LOG       │                                         │
│  DQ_FAILED_ROW_KEYS       │                                         │
│  DQ_JOB_EXEC_CONFIG       │                                         │
│  DQ_RECON_RESULTS         │                                         │
│  RUN_ID_SEQ (Sequence)    │                                         │
└───────────────────────────┴─────────────────────────────────────────┘
```

---

## How it works — Execution Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│  CALL EXECUTE_DQ_RULES_PROJECT(project_id, parallel_jobs)            │
│    └─► loops all datasets in project, correlates via BATCH_ID        │
│                                                                      │
│  CALL EXECUTE_DQ_RULES_MASTER(dataset_id, parallel_jobs)             │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  1. CONFIG_LOADING     │  Read DQ_JOB_EXEC_CONFIG
                 └───────────┬───────────┘
                             ▼
                 ┌───────────────────────┐
                 │  2. VALIDATE DATASET  │  Fetch DB/Schema/Table from DQ_DATASET
                 └───────────┬───────────┘
                             ▼
                 ┌───────────────────────┐
                 │  3. RULES_FETCHING    │  Join RULE_CONFIG + EXPECTATION_MASTER
                 │                       │  + HANDLER_MAPPING → get SP names
                 └───────────┬───────────┘
                             ▼
                 ┌───────────────────────┐
                 │  4. SQL_EXECUTION     │  Execute handler SPs in PARALLEL
                 │     (joblib threads)  │  Each SP returns: 200 / 300 / 400
                 └───────────┬───────────┘
                             ▼
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌────────────────────┐       ┌────────────────────┐
   │  5. VIEW_CREATION  │       │  6. RUN_LOG_INSERT │
   │  Pivot view across │       │  Summary record in │
   │  last 90 runs      │       │  DQ_DATASET_RUN_LOG│
   └────────────────────┘       └────────────────────┘
```

**Return codes:** `200` = SUCCESS, `300` = FAILURE (rule violations found), `400` = EXECUTION_ERROR

---

## What each Handler SP does (per rule)

```
  ┌─────────────────────────────────────────────────────────┐
  │  Handler SP (e.g. SP_NOT_NULL_CHECK)                    │
  │                                                         │
  │  1. CONFIG_LOADING    → Parse rule config + kwargs      │
  │  2. RULE_PARSING      → Build WHERE clause condition    │
  │  3. INCREMENTAL_FILTER→ Apply date filter if enabled    │
  │  4. MAIN_QUERY        → COUNT total, unexpected, missing│
  │  5. CAPTURE_FAILED_KEYS → PK values of failed rows     │
  │  6. INSERT_FAILED_RECORDS → Full rows → DQ_ERRORS      │
  │  7. INSERT_DQ_RESULTS → Summary → DQ_RULE_RESULTS      │
  │                                                         │
  │  • ERROR_FLAG toggle skips steps 5–6 per rule           │
  │  • Every step is audit-logged to DQ_RULE_AUDIT_LOG      │
  └─────────────────────────────────────────────────────────┘
```

---

## Available Check Types (45 handlers)

| Category | Checks |
|----------|--------|
| **Completeness** | not_null, null_only, proportion_non_null |
| **Uniqueness** | uniqueness, compound_columns_unique, unique_values_within_record, proportion_unique |
| **Validity** | range_value, value_in_set, value_not_in_set, regex_match, regex_match_list, regex_not_match, regex_not_match_list, data_type |
| **Consistency** | column_pair_equal, column_pair_a_greater_than_b, column_pair_in_set, multicolumn_sum_equal |
| **Accuracy** | min_value_between, max_value_between, mean_range, median_range, sum_range, stdev_between, zscore_less_than |
| **Timeliness** | freshness |
| **Schema** | table_row_count, table_row_count_equal, table_row_count_equal_other_table, table_column_count_between, table_column_count_equal, columns_match_set, columns_match_ordered_list, column_to_exist |
| **Volume** | table_row_count_equal_source_file (source-file count match) |
| **Length** | value_length_between, value_length_equal |
| **Distribution** | distinct_values_in_set, distinct_values_equal_set, distinct_values_to_contain_set, most_common_value_in_set, unique_value_count_between |
| **Reconciliation** | scd_recon (SCD1/SCD2 source-target reconciliation) |
| **Custom** | unexpected_rows (arbitrary SQL WHERE clause) |

---

## Folder Structure

```
DQM/
├── DDL/
│   ├── V1.0.0__create_framework_tables.sql   # All table + sequence DDL (IF NOT EXISTS)
│   └── V1.1.0__seed_metadata.sql             # Reference data (DELETE + INSERT)
├── DML.sql                                    # Idempotent seed (INSERT WHERE NOT EXISTS)
├── Procedures/
│   ├── R__execute_dq_rules_master.sql         # Dataset orchestrator (Python SP, joblib)
│   ├── R__execute_dq_rules_project.sql        # Project orchestrator (batch all datasets)
│   └── Handlers/
│       ├── R__sp_not_null_check.sql           # One SQL SP per check type
│       ├── R__sp_uniqueness_check.sql
│       ├── R__sp_range_value_check.sql
│       ├── R__sp_scd_recon_check.sql
│       └── ... (45 handlers total)
├── app/
│   ├── streamlit_app.py                       # Admin UI (7 pages)
│   ├── snowflake.yml                          # SPCS deployment config
│   ├── pyproject.toml                         # Python dependencies
│   └── .streamlit/config.toml                 # Theme config
├── deploy.py                                  # Automated deployer (workspace + CLI)
├── gen_seed.py                                # Generates seed SQL from live tables
├── CI.sql                                     # Account setup (warehouses, budgets, RBAC)
├── early_access_rollout.sql                   # Streamlit EA role hierarchy + grants
├── data.sql                                   # Sample queries / reference
└── README.md                                  # This file
```

---

## Deployment

### Automated (recommended)

Run `deploy.py` inside a Snowflake Workspace or from CLI:

```bash
# Full first-time setup (tables + seed + all procedures):
python deploy.py --phase all

# Redeploy only procedures (safe, non-destructive):
python deploy.py --phase procedures

# Individual phases:
python deploy.py --phase tables
python deploy.py --phase seed
```

Inside a **Snowflake Workspace**, open `deploy.py` and run it — it auto-detects the OAuth session token. No configuration needed.

From **CLI**, it resolves credentials in order:
1. `--connection <name>` (from `~/.snowflake/connections.toml`)
2. Environment variables (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`)
3. In-Snowflake token (`/snowflake/session/token`)

### Generate seed SQL from live tables

```bash
python gen_seed.py                    # outputs V1.1.0__seed_metadata.sql
python gen_seed.py -o my_seed.sql     # custom output path
python gen_seed.py -c my_connection   # use named connection (CLI only)
```

Also works inside Snowflake Workspace — auto-detects OAuth token.

---

## Quick Start

```sql
-- 1. Deploy (or run deploy.py --phase all)

-- 2. Register a dataset (via Streamlit UI or SQL)
-- 3. Configure rules against it (via Streamlit UI or SQL)

-- 4. Execute a single dataset
CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_MASTER(<dataset_id>, 2);

-- 5. Execute all datasets in a project
CALL DQ_FRAMEWORK.METADATA.EXECUTE_DQ_RULES_PROJECT(<project_id>, 2);

-- 6. Check results
SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RULE_RESULTS WHERE DATASET_RUN_ID = <run_id>;

-- 7. Inspect failures
SELECT * FROM DQ_FRAMEWORK.DQ_ERRORS.<DATASET_NAME>_DQ_FAILURE;

-- 8. Audit trail
SELECT * FROM DQ_FRAMEWORK.METADATA.DQ_RULE_AUDIT_LOG WHERE DATASET_RUN_ID = <run_id>;
```

---

## Streamlit Admin UI

Deployed as `DQ_FRAMEWORK.APP.DQAPP_EA` on SPCS (Container Runtime).

| Page | Purpose |
|------|---------|
| **Home** | KPIs, severity distribution, dimension donut chart, recent executions, recon health banner |
| **Projects** | CRUD with dialog-based creation, search, pagination |
| **Datasets** | Register TABLE or QUERY type datasets, pick PKs from column list |
| **Rules** | Select dataset → pick expectation by dimension → dynamic argument form → create with severity |
| **Jobs** | Project-level (batch) and Dataset-level execution with pre-flight checks, scope selection (all/selected/retry-failed) |
| **Rule Results** | Pass/fail metrics, dimension and severity breakdowns, rule-level detail |
| **Reconciliation** | SCD2 cross-layer validation display |

---

## Key Design Decisions

- **Metadata-driven** — All rules are config rows, not code
- **Parallel execution** — Rules run concurrently via `joblib` (configurable parallelism)
- **Two-level orchestration** — Dataset-level (`EXECUTE_DQ_RULES_MASTER`) and project-level (`EXECUTE_DQ_RULES_PROJECT`) with batch correlation
- **Separation of concerns** — Metadata in `METADATA` schema, failures in `DQ_ERRORS` schema
- **Incremental support** — Rules can filter by date columns for incremental loads
- **ERROR_FLAG toggle** — Per-rule control to skip failed-record and key capture
- **Full audit trail** — Every step of every rule logged with timestamps and errors
- **Extensible** — Add a new check type by inserting one row in `DQ_EXPECTATION_MASTER` + one handler SP + one row in `DQ_EXPECTATION_HANDLER_MAPPING`
- **Schemachange-compatible** — DDL uses `V` prefix (versioned), procedures use `R__` prefix (repeatable)
- **Dual-mode deployer** — `deploy.py` works both in Snowflake Workspace (OAuth token) and locally (env vars / named connections)
- **RBAC-ready** — `early_access_rollout.sql` provisions role hierarchy with read-only enforcement for consumers
