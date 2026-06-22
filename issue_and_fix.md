# DQM Framework — Full Analysis & Resolution Tracker

## Architecture Overview

The framework is a **metadata-driven Data Quality engine** on Snowflake with:
- **45 handler stored procedures** (one per check type)
- **A Python orchestrator** (`EXECUTE_DQ_RULES_MASTER`) that dispatches rules via async queries with batched concurrency
- **A project-level orchestrator** (`EXECUTE_DQ_RULES_PROJECT`) for batch dataset execution
- **A multi-page Streamlit app** for rule configuration, execution, results, reconciliation, and scheduling
- **DDL/seed/migration scripts** managed via schemachange
- **Snowflake Tasks** for automated scheduled execution with run logging
- **Data retention policies** with configurable TTL-based cleanup

---

## Resolution Status

### FIXED — Completed Items

| # | Issue | Resolution |
|---|---|---|
| 1 | **joblib thread-safety** | Replaced with Snowflake async queries (`collect_nowait()`) with batched concurrency. Sequential fallback if unavailable. No `joblib` dependency. |
| 3 | **Hardcoded framework path** | `DQ_JOB_EXEC_CONFIG` is the single source of truth. Both orchestrators read DB/schema from config at runtime. |
| 5 | **Snowflake Tasks for scheduling** | `V1.4.0__scheduled_tasks.sql` — `DQ_SCHEDULE_CONFIG` table, `SP_MANAGE_DQ_SCHEDULES` reconciler, `SP_DQ_SCHEDULED_RUN_WRAPPER` for logging, Streamlit Schedules page. |
| 6 | **Split Streamlit app** | Multi-page architecture: `pages/home.py`, `projects.py`, `datasets.py`, `rules.py`, `jobs.py`, `results.py`, `reconciliation.py`, `schedules.py`. Shared modules: `shared/db.py`, `shared/style.py`, `shared/helpers.py`, `shared/charts.py`. |
| 7 | **Clustering keys** | `V1.3.0__add_clustering_keys.sql` — clustering on `DQ_RULE_RESULTS`, `DQ_RULE_AUDIT_LOG`, `DQ_DATASET_RUN_LOG`. |
| 10 | **Dead code removal** | File generation block replaced with a conditional failure-pivot view that only fires when row-level failures exist and the failure table is present. |
| 12 | **Migration system** | `schemachange-config.yml` configured. Versioned migrations under `ddl_dml/` (`V1.0.0` through `V1.4.0`). |
| 14 | **Data retention policies** | `V1.2.0__data_retention_policies.sql` — `DQ_RETENTION_CONFIG` table, `SP_DATA_RETENTION_CLEANUP` proc, daily scheduled task. |
| — | **Selective/retry execution** | `P_RULE_CONFIG_IDS` parameter added to master orchestrator. Supports full, selective, and retry-failed-only scopes with `RUN_SCOPE` tracking. |
| — | **BATCH_ID race condition** | Mitigated via pre/post `MAX(DATASET_RUN_ID)` pattern. The UPDATE targets a specific captured ID, not a live `MAX()`. Residual risk only with overlapping project runs on the same dataset (extremely unlikely; impact is mislabeled batch, not data corruption). |
| — | **Identifier quoting** | `q_ident()` helper added to master orchestrator. Used for SP paths, DB/schema names, table references. |

---

### REMAINING — Items to Address Later

#### High Priority

| # | Issue | Impact | Recommended Fix |
|---|---|---|---|
| 2 | **Handler code duplication** | 45 handlers repeat ~100 lines of boilerplate. High maintenance cost. | Create a template procedure that accepts a "check expression" SQL fragment. Each handler becomes a thin wrapper passing only its validation logic. |
| 4 | **SQL injection in run-log INSERT** | `session.get_current_user()` and `data_asset['DATASET_NAME']` are interpolated into the final INSERT (line 593 of master). | Use `params=[]` for the run-log INSERT, or escape via `format_for_sql()` consistently. |
| — | **SQL injection in handlers** | All 45 SQL handlers build dynamic SQL via concatenation. Column names quoted with `"` but not validated against embedded double-quotes. | Validate identifiers against `^[A-Za-z0-9_]+$` regex before use, or use `IDENTIFIER()` function. |

#### Medium Priority

| # | Issue | Impact | Recommended Fix |
|---|---|---|---|
| 8 | **No dry-run mode** | Misconfigs (bad column name, missing table, unparseable KWARGS) only surface at execution time, wasting compute. | Add `SP_VALIDATE_RULE_CONFIG(P_DATASET_ID)` that checks table existence, column existence, and KWARGS parsing without executing. Wire into the Streamlit "Pre-flight Check" section. |
| 9 | **No alerting** | Failures are only visible via the Streamlit app. No proactive notification. | `CREATE ALERT` on `DQ_DATASET_RUN_LOG` for `RUN_STATUS IN ('FAILURE', 'ERROR')`. Send to email or webhook via notification integration. |
| — | **No retry/idempotency** | Interrupted runs can't resume. Re-running creates a new `DATASET_RUN_ID`. | Track per-rule execution status in `DQ_RULE_RESULTS`; on retry, skip already-passed rules within the same `DATASET_RUN_ID`. |
| — | **No handler versioning** | Handler logic changes make historical results incomparable. | Add `HANDLER_VERSION` column to `DQ_RULE_RESULTS`; handlers set it from a constant. |
| — | **VIEW creation performance** | Failure pivot view joins last 90 FULL runs. Slows as rule count grows. | Limit to last 10 runs, or build the view incrementally / on-demand only. |
| — | **Error swallowing** | `try: ... except: pass` in several places silently discards failures. | At minimum, log to `DQ_RULE_AUDIT_LOG` before swallowing. Never bare `except: pass`. |

#### Low Priority

| # | Issue | Impact | Recommended Fix |
|---|---|---|---|
| 11 | **deploy.py broken paths** | References `DDL/`, `Procedures/`, `DML.sql` which don't exist. | Fix to `ddl_dml/`, `procedures/`, or deprecate in favor of schemachange. |
| 13 | **Consider Snowflake DMFs** | Simple checks (NOT_NULL, UNIQUENESS, RANGE) could use native Data Metric Functions for better performance. | Evaluate for high-volume tables where procedure overhead is significant. |
| — | **RBAC gaps in CI.sql** | Missing grants on sequences for non-ACCOUNTADMIN roles. `ALL PRIVILEGES` too broad for DQ_DEVELOPER. | Replace with explicit `SELECT, INSERT, UPDATE, DELETE` grants. Add `GRANT USAGE ON SEQUENCE` for RUN_ID_SEQ and BATCH_ID_SEQ. |
| — | **Seed data fragility** | Manual ID numbering (EXPECTATION_ID, ARG_ID). DELETE+INSERT not wrapped in transaction. | Use `MERGE` for seed data. Consider AUTOINCREMENT or sequences for IDs. |
| — | **Font bloat** | 14 font variants shipped, only ~3 used. | Remove unused weights from `assest/fonts/`. |
| — | **No testing framework** | No unit/integration tests for handlers. | Add a `tests/` directory with sample data and expected outcomes per handler. |

---

## File-by-File Analysis

### 1. `CI.sql` — Infrastructure Setup
**Good:** Idempotent, well-sectioned, includes cost tagging, RBAC, resource monitors, and budgets.

**Remaining Issues:**
- Hardcoded email `aslam26hlw@gmail.com` — should be parameterized
- `ALL PRIVILEGES` to DQ_DEVELOPER — too broad
- Missing grants on SEQUENCES for non-ACCOUNTADMIN roles

### 2. `V1.0.0__create_framework_tables.sql` — DDL
**Good:** Uses `IF NOT EXISTS`, reasonable schema design.

**Remaining Issues:**
- No foreign key constraints — referential integrity is application-enforced
- `DQ_FAILED_ROW_KEYS.FAILED_KEY` is VARIANT without search optimization

### 3. `V1.1.0__seed_metadata.sql` — Seed Data
**Remaining Issues:**
- Uses `DELETE` + `INSERT` (not transactional). Should use `MERGE`
- Manual ID numbering is fragile

### 4. `R__execute_dq_rules_master.sql` — Core Orchestrator
**Fixed:** Async execution, framework path config, identifier quoting, selective execution, dead code cleanup.

**Remaining Issues:**
- `session.get_current_user()` and `data_asset['DATASET_NAME']` interpolated into run-log INSERT without parameterization
- `try: ... except: pass` on final log insert

### 5. `R__execute_dq_rules_project.sql` — Project Orchestrator
**Fixed:** Framework path from config, BATCH_ID race mitigated via pre/post pattern.

**Remaining Issues:**
- Sequential dataset execution (acceptable for most workloads, but no parallelism across datasets)
- `except Exception: pass` on BATCH_ID update and project log insert

### 6. Handler Procedures (45+ handlers)
**Remaining Issues (ALL handlers):**
- Massive code duplication (~100 lines repeated per handler)
- Dynamic SQL via string concatenation (SQL injection risk on column names)
- Excessive audit logging (5-7 rows per rule per run)
- Config loaded per-handler (should be passed through)
- `CREATE TABLE IF NOT EXISTS` runs per failed check (should be once per dataset)
- No LIMIT on failure capture when `v_failed_rows_cnt_limit` is NULL

### 7. `SP_TABLE_ROW_COUNT_EQUAL_OTHER_TABLE_CHECK` (Python Handler)
**Good:** Parameterized queries, watermark-based incremental recon.

**Remaining Issues:**
- `COALESCE(TRIM(col), 'NA')` silently converts NULLs — could produce false matches
- No timeout on dedup CTE for large tables

### 8. Streamlit App (multi-page)
**Fixed:** Split into pages/modules, caching via `@st.cache_data`, shared DB module.

**Remaining Issues:**
- Runs as `EXECUTE AS OWNER` — elevated privileges for all app users

### 9. `utility/deploy.py`
**Remaining Issues:**
- Broken directory paths — doesn't find files. Superseded by schemachange.

---

## Summary

The framework has been significantly improved. The critical issues (unsafe parallelism, hardcoded paths, no scheduling, monolithic app) are resolved. The main remaining technical debt is: (1) handler code duplication making maintenance expensive, (2) residual SQL injection risk in the run-log INSERT and handlers, and (3) no proactive alerting on failures. These are medium-term improvements that don't block production use but should be planned for.
