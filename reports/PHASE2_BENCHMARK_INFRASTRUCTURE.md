# Phase 2 — native benchmark infrastructure

**Date:** 2026-10-24 (Asia/Saigon). **Status: PARTIAL.** Both read-only 10K smoke tests executed successfully through `sqlcmd` and mongosh. The SQL was not separately run through the SSMS interface, and disposable-copy write/index-build helpers were implemented but not executed. No UC1–UC6 experiment or reference-data mutation occurred.

## Files and roles

| File | Purpose |
|---|---|
| `sql/benchmark/benchmark_core.sql` | Session-local `#bench_read`, `#bench_storage`, `#bench_action`, raw timing and action tables. |
| `sql/benchmark/benchmark_smoke.sql` | Read-only 10K aggregate, seven timed repetitions after two warm-ups, native summary, storage inventory and separate IO/CPU/XML-plan diagnostic. |
| `mongo/benchmark/benchmark_core.js` | `BenchmarkCore` read timing, full cursor consumption, percentile summary, explain, index inventory, and guarded disposable-copy write helpers. |
| `mongo/benchmark/benchmark_smoke.js` | Read-only 10K cursor test, seven timed repetitions after two warm-ups, JSON-line summary, inventory and separate explain. |
| `results/phase2_smoke/accepted/phase2_sql_smoke.txt` | Final local `sqlcmd` transcript with raw samples, summary, 10K index storage, IO/CPU messages and complete XML plan. |
| `results/phase2_smoke/accepted/phase2_mongo_smoke.jsonl` | Final local mongosh JSON-line transcript with raw samples, summary, inventory and explain plan. |

Earlier debugging transcripts are retained in `results/phase2_smoke/archive/` (`*initial*`, `*plan_truncated*`, and `*pre_schema*`). The first SQL query was too short for a useful timer smoke, and the first full-table SQL transcript truncated XML at `sqlcmd`'s default display width. The final SQL command used `-y 0` without `-W` or `-h` and preserved the complete XML element. Its plan and Mongo explain record have been extracted to `results/phase2_smoke/plans/`.

## Run the smoke tests

### SQL Server Management Studio

Connect to the intended SQL Server instance using a login with SELECT and SHOWPLAN rights on `DBMS_EW_Group02`. Keep **one query window/session**. Execute `sql/benchmark/benchmark_core.sql`, then replace the editor text with `sql/benchmark/benchmark_smoke.sql` and execute again in that same window. The core creates only session-local temporary objects. Opening the second file in a separate SSMS query window loses those objects.

In SSMS 22, each Query tab normally has its own connection. The `CORE_READY` result now shows `session_id` (`@@SPID`) and `sample_table_object_id`. Before running smoke in that same tab, you can check `SELECT @@SPID AS session_id, OBJECT_ID('tempdb..#bench_samples') AS sample_table_object_id;`: both values must be non-null, and the session ID must match `CORE_READY`. `GO` in the script does not change the connection. Reconnecting, closing the tab, or opening smoke in a new Query tab loses the temporary objects and produces error 50100. If that happens, rerun core and smoke in one tab.

Alternatively, enable **SQLCMD Mode** in SSMS and execute a single query window containing two `:r` directives with absolute paths, first core and then smoke. `:r` is a client command, not text to place inside `sp_executesql`. The scripts themselves contain no `GO` inside dynamic SQL.

Use Results to Grid, Text or File and save the raw and summary result sets. Save the Messages pane for `SET STATISTICS IO/TIME`. The diagnostic query uses `SET STATISTICS XML ON`; leave the SSMS toolbar's **Include Actual Execution Plan** toggle off, then save its XML result as `.sqlplan`. These diagnostics run **after** the timed loop. The SQL smoke itself performs no persistent DDL or DML.

The local validation used PowerShell only to feed the two native files into one `sqlcmd` connection and save native output:

```powershell
Get-Content -LiteralPath 'sql/benchmark/benchmark_core.sql','sql/benchmark/benchmark_smoke.sql' -Raw |
  sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -s '|' -y 0 -o 'results/phase2_smoke/accepted/phase2_sql_smoke_new.txt'
```

On this local ODBC 18 installation, `-C` trusts the server certificate. `-y 0` is needed for the full XML plan in the CLI transcript; it cannot be combined with `-W` or `-h`. This PowerShell command is a validation/export convenience, **not** a benchmark runner; all timed work occurs in T-SQL.

### MongoDB Shell

From the `EW_redo` workspace root:

```powershell
mongosh "mongodb://localhost:27017/dbms_ew_group02" --quiet --file ".\mongo\benchmark\benchmark_smoke.js" |
  Tee-Object -FilePath 'results/phase2_smoke/accepted/phase2_mongo_smoke_new.jsonl'
```

If `mongosh` is not on `PATH`, use `C:\Users\ADMIN\AppData\Local\Programs\mongosh\mongosh.exe`. Inside an interactive shell started from the workspace root, `load('mongo/benchmark/benchmark_core.js')` exposes `BenchmarkCore`; the smoke file loads it itself. `load()` uses a path relative to the shell's working directory. The script selects `db.getSiblingDB('dbms_ew_group02')` and exact-case `big_table_10K`.

## Measurement contract and output schema

The default infrastructure setting is two warm-ups and 25 measured repetitions; smoke tests use seven measurements. All raw values are retained in iteration order. Both summaries use **continuous interpolation** at positions `(n-1) × 0.50` and `(n-1) × 0.95`, so they compute the same p50/p95 definition. SQL uses `PERCENTILE_CONT`; MongoDB sorts a copy of its elapsed samples. Warm-ups are not included in the distribution. Every timed iteration checks result count and a stable fingerprint/ID sum.

SQL timings use `SYSUTCDATETIME()` around `sp_executesql` and `DATEDIFF_BIG(MICROSECOND, ...) / 1000.0`. This is a **server T-SQL batch interval**; it is not SSMS rendering time. The SQL work contract assigns `@actual_rows` and `@fingerprint`. The smoke aggregate fully processes its input and returns one aggregate row; its `returned_rows` field denotes **matched source rows**, not rows rendered to the client. Future UCs with row-returning projections must materialize their actual projection into a query-specific `#result` inside `@WorkSql` and count/check it there, or document a different consistent retrieval boundary. Materialization and any temp-table work must remain identical across A/B/C. A count-only query must never be presented as an ordinary retrieval benchmark.

MongoDB timings use `Date.now()` around cursor creation **and full `forEach` consumption**; they include shell-side fetching, decoding, count and ID-sum checks, but exclude printing. `Date.now()` has millisecond resolution, so very short operations can produce ties or zero values. Increase workload/repetitions and report that limitation if it appears. The ID sum is a cheap stability check, **not** a collision-resistant dataset digest. Future UCs must compare projected IDs/results using a query-appropriate correctness check.

The common result fields are `run_id`, UTC `timestamp`, `phase`, `use_case`, `dbms`, `server_version`, `dataset`, `dataset_row_count`, `query_id`, `configuration`, `warmup_count`, `repetition_count`, `timing_method`, `query_median_ms`, `query_p95_ms`, raw samples/timings, `returned_rows`, `correctness_status`, index storage, build/write metrics, DBMS work metrics, `query_plan_reference`, and notes. SQL emits separate labeled `RAW_SAMPLE`, `BENCHMARK_SUMMARY`, `INDEX_STORAGE` and diagnostic result sets; MongoDB emits `RAW_SAMPLES`, `BENCHMARK_SUMMARY`, `INDEX_INVENTORY` and `PLAN` JSON objects. DBMS-specific fields are null when inapplicable or collected only in another section. For example, SQL `logical_reads` is null in the timed summary and appears in separate `STATISTICS IO` Messages; MongoDB `total_keys_examined` and `total_docs_examined` come from separate explain.

Representative formats, abbreviated from the native outputs:

```text
BENCHMARK_SUMMARY|<run_id>|<timestamp_utc>|PHASE2|SMOKE|SQL_SERVER|...|query_median_ms|query_p95_ms|10000|...|PASS|...
```

```json
{"section":"BENCHMARK_SUMMARY","run_id":"...","phase":"PHASE2","dbms":"MONGODB","repetition_count":7,"query_median_ms":42,"query_p95_ms":51.1,"returned_rows":10000,"correctness_status":"PASS"}
```

No cross-DBMS speed comparison is valid from these smoke values: one test times a server aggregate, the other times client cursor consumption.

## Index storage, plans and write helpers

`#bench_storage` joins `sys.indexes`, `sys.index_columns` and `sys.dm_db_partition_stats`. It sums `used_page_count` and `reserved_page_count` across partitions and multiplies by 8,192 bytes/page. `index_id=0` is the heap base; `index_id=1` is a clustered base; `index_id>1` is a secondary index. These categories must not be added together and called only “index bytes.” MongoDB inventory uses `getIndexes()` and `collection.stats({scale:1}).indexSizes` in bytes. Metadata sizes may be affected by allocation and background activity; capture before/after under a consistent protocol.

The SQL actual XML plan and `STATISTICS IO/TIME` are collected in a separate execution. MongoDB `find(...).explain('executionStats')` is also called separately and records `totalKeysExamined`, `totalDocsExamined`, `nReturned` and the plan. Explain time and plan instrumentation are excluded from primary timing samples. Save the plan with its run ID and query ID.

For future disposable copies, `#bench_action` records elapsed time for one `INDEX_BUILD`, `INSERT` or `UPDATE`; the caller's action SQL should assign `@affected_rows` for INSERT/UPDATE. INSERT throughput is `affected_rows × 1000 / elapsed_ms`; repeat UPDATE actions on equivalent independent copies and summarize their raw latencies with the same p50/p95 pattern. The SQL helper only checks the declared `dbo.UC[1-6]_*` or `dbo.BENCH_*` table name. **It cannot parse arbitrary caller-supplied SQL to prove that the statement writes only that table.** Review future action SQL and copy setup before execution; never pass original `dbo.DEMO_BIG_TABLE_*` as a write target. Do not put `GO` in `@ActionSql`.

MongoDB's `timeIndexBuild`, `timeInsert`, `timeUpdate` and `dropDisposable` call methods on the explicitly passed collection and reject names outside `uc1_`–`uc6_` or `bench_` in `dbms_ew_group02`. They were **not executed** in this phase. For every future A/B/C copy, record source name, exact row count/ID checks, inherited `_id`, optional index definitions, copy preparation, mutation batch and cleanup. Never create/drop an index or write on the Phase 1 reference objects. The SQL source tables already have three optional indexes; MongoDB 100K/1M sources already have a partial `TEMPORARY_1` index. A fresh copy's index inventory must be recorded before timing.

## Executed smoke results and limitations

| Check | SQL Server | MongoDB |
|---|---|---|
| Execution | `sqlcmd` exit 0; SSMS UI not run here | mongosh 2.13.0 exit 0 |
| Warm-ups / samples | 2 / 7 | 2 / 7 |
| Correctness | 7/7 PASS; matched rows 10,000; fingerprint stable | 7/7 PASS; returned documents 10,000; ID sum stable |
| p50 / p95 | 6.011 / 7.065 ms, server aggregate | 42 / 51.1 ms, fully consumed cursor |
| Separate diagnostics | 117 logical reads; complete 6,093-character XML plan in raw transcript | 0 keys examined, 10,000 docs examined; executionStats plan in JSONL |
| Storage inventory | Heap plus three existing secondary indexes, with used/reserved bytes | Existing `_id_` index and byte size |

These are **smoke observations only** and can vary on rerun. The SQL timer's first short-range test produced zero-duration samples; the final full-10K aggregate avoids that specific resolution problem. SQL p50/p95 were also checked against the seven raw values, and MongoDB p50/p95 against its seven raw values. The CLI XML plan is complete, but SSMS `.sqlplan` export has not been manually exercised. Index-build, INSERT and UPDATE helpers and MongoDB DDL permission remain untested until disposable copies are prepared. Complete row-by-row SQL/Mongo data equivalence remains outside this Phase 2 smoke.

## Readiness for Phase 3 (UC1)

1. Create independent 100K copies with exact source names from Phase 1; verify row counts, IDs and a stronger content check before A/B/C measurements. Do not copy original optional indexes into the baseline unnoticed.
2. Test SQL and MongoDB index creation/drop permissions **on those copies**. Confirm the exact retained `_id`/heap and other baseline indexes.
3. Run the SQL core and UC1 code in one SSMS session, and load the Mongo core from the workspace root. Use at least 20–30 measured repetitions for substantive UC1 results, plus a documented cache/warm-up protocol.
4. Use one exact predicate/projection/result order per A/B/C comparison, validate result IDs and counts, and keep row materialization/cursor consumption equivalent within each DBMS.
5. Export raw samples, separate diagnostics/plans, index bytes and build/write costs with run IDs before drawing conclusions. Any SSMS-specific export issue should be resolved during this handoff.

### Documentation used

Context7 was unavailable in this environment; the implementation was checked against the installed SQL Server 17.x / MongoDB 7.0.12 runtime and primary documentation. Relevant references: [SQL partition statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-partition-stats-transact-sql), [SQL `SET STATISTICS XML`](https://learn.microsoft.com/en-us/sql/t-sql/statements/set-statistics-xml-transact-sql), [SQL `PERCENTILE_CONT`](https://learn.microsoft.com/en-us/sql/t-sql/functions/percentile-cont-transact-sql), [MongoDB 7.0 explain](https://www.mongodb.com/docs/v7.0/reference/explain-results), [MongoDB 7.0 collection stats](https://www.mongodb.com/docs/v7.0/reference/method/db.collection.stats/), and [mongosh scripts](https://www.mongodb.com/docs/mongodb-shell/write-scripts/). A different patch level or shell version may change output fields or client display behavior; recheck those points when moving environments.
