# Phase 3 — UC1 compound index benchmark

**Date:** 2026-10-24 (Asia/Saigon). **Status: PASS for Phase 3 local execution.** SQL Server 2025 (17.0.1145.4) and MongoDB 7.0.12 were measured on disposable 100K copies. This is one local run per configuration; repeat on the intended presentation machine before treating the latency ratios as general results. Phase 2 remains PARTIAL because the SSMS UI and write/index-build helpers were not exercised there; its complete `sqlcmd` XML plan has since been extracted to `results/phase2_smoke/plans/sql_SMOKE.sqlplan`.

## Reproduction and provenance

SQL database `DBMS_EW_Group02`, source `dbo.DEMO_BIG_TABLE_100K`; Mongo database `dbms_ew_group02`, source `big_table_100k`. Each engine's setup made one read copy and three independent write copies. SQL copies were heaps with no secondary index; Mongo copies had only `_id_`. All copies started with 100,000 records and ID sum 5,000,050,000. SQL copies matched the source `CHECKSUM_AGG` fingerprint 1,692,732,528. Mongo copies matched the source OBJECT_ID sum 3,262,143,302. The originals retained their existing indexes; no UC1 index was created on either original.

| Query | Predicate and sort | Matches | Selectivity |
|---|---|---:|---:|
| U1a | `OWNER=SYS, OBJECT_TYPE=TABLE, OBJECT_ID=16` | 2 | 0.002% |
| U1b | `OWNER=SYS, OBJECT_TYPE=TABLE` | 3,405 | 3.405% |
| U1c | `OBJECT_TYPE=TABLE, OBJECT_ID=16` | 2 | 0.002% |
| U1d | `OWNER=CTXSYS`, sort `OBJECT_TYPE ASC, OBJECT_ID ASC` | 398 | 0.398% |

Within each engine, A has no optional index; B has `OWNER`; C has `(OWNER, OBJECT_TYPE, OBJECT_ID)`. Two warmups preceded 25 timed reads per query/configuration. SQL materialized projected rows (`ID, OWNER, OBJECT_TYPE, OBJECT_ID`) with `FOR JSON PATH` inside the server and validated the count/fingerprint; Mongo consumed the full projected cursor and validated count and ID sums. These timer boundaries differ, so **do not compare SQL milliseconds with Mongo milliseconds**. U1d's actual sort remained in each query. Plans and IO/examined counts were collected outside the timed loop. No access path was forced. SQL logical reads below are from the separate actual-plan pass; Mongo key/doc counts are from `explain('executionStats')`.

### SQL Server read results

| Query | A p50 / p95 ms; reads | B p50 / p95 ms; reads | C p50 / p95 ms; reads | A→B / A→C / B→C p50 speedup |
|---|---:|---:|---:|---:|
| U1a | 32.363 / 43.877; 2,730 | 24.531 / 40.795; 2,730 | 9.458 / 51.119; 5 | 1.32× / 3.42× / 2.59× |
| U1b | 104.476 / 236.768; 2,730 | 84.286 / 171.097; 2,730 | 97.990 / 673.343; 2,730 | 1.24× / 1.07× / 0.86× |
| U1c | 37.011 / 61.306; 2,730 | 31.973 / 48.092; 2,730 | 20.043 / 52.595; 657 | 1.16× / 1.85× / 1.60× |
| U1d | 38.024 / 57.349; 2,730 | 11.117 / 56.564; 403 | 10.523 / 29.107; 405 | 3.42× / 3.61× / 1.06× |

Actual plan operators: A uses `Table Scan` for all four, with `Sort` for U1d. B uses `Table Scan` for U1a–c; U1d uses `Index Seek` + `RID Lookup` + `Sort`. C uses `Index Seek` + `RID Lookup` for U1a/U1d, `Table Scan` for U1b, and `Index Scan` + `RID Lookup` for U1c. C's U1d has no `Sort`. In particular, U1b's p50 change in C does **not** reflect an index seek. U1c's C index scan is an optimizer choice despite the missing leading key, not a selective seek. The high C U1b p95 (673.343 ms) signals run variation; do not generalize a 7% p50 difference.

### MongoDB read results

| Query | A p50 / p95 ms; keys/docs | B p50 / p95 ms; keys/docs | C p50 / p95 ms; keys/docs | A→B / A→C / B→C p50 speedup |
|---|---:|---:|---:|---:|
| U1a | 241.03 / 254.67; 0/100,000 | 462.78 / 499.91; 71,802/71,802 | 2.34 / 2.91; 2/2 | 0.52× / 103.00× / 197.77× |
| U1b | 253.16 / 285.96; 0/100,000 | 457.73 / 498.85; 71,802/71,802 | 39.31 / 51.48; 3,405/3,405 | 0.55× / 6.44× / 11.64× |
| U1c | 228.33 / 237.80; 0/100,000 | 204.50 / 240.45; 0/100,000 | 232.18 / 245.36; 0/100,000 | 1.12× / 0.98× / 0.88× |
| U1d | 236.43 / 266.97; 0/100,000 | 10.04 / 14.05; 398/398 | 7.97 / 8.95; 398/398 | 23.55× / 29.66× / 1.26× |

Mongo A uses `COLLSCAN` for all four and `SORT` for U1d. B uses `IXSCAN` + `FETCH` for U1a/b/d and `COLLSCAN` for U1c; B retains `SORT` for U1d. C uses `IXSCAN` + `FETCH` for U1a/b/d without `SORT` on U1d, and `COLLSCAN` for U1c. The `OWNER` only index scans 71,802 keys/documents for SYS queries, explaining its poor selectivity. U1c's small p50 differences cannot be attributed to index use; run order/cache/noise may contribute. The C index's leading prefix and key order match U1a/b/d; U1c has no leading OWNER predicate.

### Build, storage and writes

| Engine | B build / index bytes | C build / index bytes | C − B bytes |
|---|---:|---:|---:|
| SQL Server | 235.955 ms / 2,768,896 used (3,293,184 reserved) | 1,969.345 ms / 5,439,488 used (5,980,160 reserved) | +2,670,592 used |
| MongoDB | 879 ms / 503,808 | 931 ms / 946,176 | +442,368 |

A's optional index size is zero: A→B and A→C increase storage by the absolute B/C values above. Index build timers exclude copying source data. These are single build observations; SQL C was built after dropping B, and the earlier A/B read workloads may have warmed pages. Storage measures use SQL partition used pages × 8,192 and Mongo collection index statistics, so their accounting is engine specific.

Each write copy began at the same 100K snapshot. B/C indexes were installed before write timing. Each configuration inserted 20 batches of 1,000 rows, then updated OWNER in 20 batches of 1,000 rows. Each finished at 120,000 rows with 20,000 updated rows. Insert rate is total inserted rows divided by timed insert duration; update p50 is per batch.

| Engine | A insert rows/s; update p50 ms | B insert rows/s; update p50 ms | C insert rows/s; update p50 ms |
|---|---:|---:|---:|
| SQL Server | 6,148; 287.635 | 17,698; 390.058 | 18,393; 254.847 |
| MongoDB | 39,368; 409.68 | 28,438; 437.47 | 26,191; 426.70 |

SQL insert B/A=2.88×, C/A=2.99×, C/B=1.04×; update B/A latency=1.36×, C/A=0.89×, C/B=0.65×. Mongo insert B/A=0.72×, C/A=0.67×, C/B=0.92×; update B/A latency=1.07×, C/A=1.04×, C/B=0.98×. The nonmonotonic SQL insert and update timings mean this single sequential run cannot isolate index maintenance cost from cache, allocation, optimizer and write progression. These are measured trade-offs, not a claim that extra indexes make writes faster. Do not compare write rates across engines.

## Evidence files

- `results/uc1/accepted/phase3_uc1_sql_setup.txt`: source/copy parity and initial index inventory.
- `results/uc1/accepted/phase3_uc1_sql_benchmark.txt`: 300 read samples, 12 summaries, build/storage rows, 60 insert batches, 60 update batches, write summaries, final PASS.
- `results/uc1/accepted/phase3_uc1_run.rpt`: separate SSMS SQLCMD run on 2026-10-24; `UC1_SESSION_BEFORE_BENCHMARK`, `CORE_READY`, and `UC1_SESSION_AFTER_CORE` share SPID 68, followed by `RUN_COMPLETE ... PASS`. Its timings are a second run; the SQL result table above uses `phase3_uc1_sql_benchmark.txt`.
- `results/uc1/plans/phase3_uc1_sql_diagnostics.txt`: 12 complete, parseable `ShowPlanXML` elements (7,704–12,164 characters), plan markers and SQL IO/TIME messages. This is the saved actual-plan evidence, not the truncated `.rpt` export. Individual `.sqlplan` files have been extracted by A/B/C and U1 query ID into `results/uc1/plans/`; `results/PLAN_INDEX.csv` maps each to its transcript.
- `results/uc1/plans/phase3_uc1_sql_diagnostics_rerun.txt`: second complete diagnostic capture after the user's SSMS run; 12 markers and 12 closed `ShowPlanXML` elements. The user's `phase3_uc1_diagnostics.rpt` has 12 markers but truncated XML (zero closing tags), so use this `.txt` file for full plan evidence.
- `results/uc1/accepted/phase3_uc1_mongo_cleanup_rerun.jsonl`: dropped only four prior UC1 copies; source remained 100K.
- `results/uc1/accepted/phase3_uc1_mongo_setup_rerun.jsonl`: new copy parity and `_id_` only inventories.
- `results/uc1/accepted/phase3_uc1_mongo_benchmark_rerun.jsonl`: **current Mongo evidence**; 12 raw arrays of 25 samples, 12 summaries, 12 full `executionStats` plans, build/storage/write data and final PASS. The original `phase3_uc1_mongo_setup.jsonl` and `phase3_uc1_mongo_benchmark.jsonl` were accidentally overwritten to zero bytes by a failed PowerShell pipe on 2026-10-24; do not cite them as evidence.
- `results/uc1/accepted/phase3_uc1_sql_source_postcheck.txt` and `results/uc1/archive/phase3_uc1_mongo_source_postcheck.jsonl`: read-only checks after both benchmarks. SQL source still has 100,000 rows, ID sum 5,000,050,000, and its three original secondary indexes; Mongo source still has 100,000 documents and `_id_`/`TEMPORARY_1` indexes.
- `results/uc1/accepted/phase3_uc1_mongo_source_postcheck_rerun.jsonl`: read-only source check after the Mongo rerun; still 100,000 documents with `_id_` and `TEMPORARY_1`.
- `results/uc1/archive/phase3_uc1_mongo_setup_failed_typecheck.jsonl`: initial setup stopped on a BSON numeric type comparison; setup was corrected, affected disposable copy reset, and the complete setup/benchmark rerun successfully. It is not counted as a measurement.

## Exact execution order

**SSMS:** Execute `sql/uc1_compound/uc1_setup.sql` once against `DBMS_EW_Group02`. Enable **Query > SQLCMD Mode**, select no text, and press F5 on either `sql/uc1_compound/uc1_benchmark.sql` directly or `sql/uc1_compound/uc1_run.sql`. The benchmark file itself uses `:r` to load `benchmark_core.sql` in its connection. When using the runner, `UC1_SESSION_BEFORE_BENCHMARK`, `CORE_READY`, and `UC1_SESSION_AFTER_CORE` must show the same `session_id`; direct execution shows the latter two. Execute `sql/uc1_compound/uc1_diagnostics.sql` separately with Results to Grid and save XML cells if individual `.sqlplan` files are needed. After exporting evidence, run `sql/uc1_compound/uc1_cleanup.sql`. The diagnostic script changes only the disposable read copy's UC1 indexes. Existing copies from a prior run require cleanup before setup; preserve their evidence first.

**PowerShell/mongosh:** Run from the `EW_redo` workspace root. If authentication/URI is needed, pass the same connection arguments to every call. Reruns require cleanup first because setup refuses existing UC1 copies; save any existing output before cleanup. Use a **new filename** for each run, check `$LASTEXITCODE` after each command, and check `RUN_COMPLETE` before treating output as evidence. For example: `mongosh --quiet --file mongo/uc1_compound/uc1_setup.js *> results/uc1/accepted/phase3_uc1_mongo_setup_new.jsonl`; after verifying success, `mongosh --quiet --file mongo/uc1_compound/uc1_benchmark.js *> results/uc1/accepted/phase3_uc1_mongo_benchmark_new.jsonl`. The earlier `| Out-File` commands overwrote successful output with empty files when the scripts failed; avoid reusing those paths. Run `mongosh --quiet --file mongo/uc1_compound/uc1_cleanup.js` only after evidence is saved and no further plan inspection is needed.

## Limitations

SQL was executed through `sqlcmd` using the same native T-SQL that can run in SSMS; the SSMS UI path itself was not retested. The separate SQL plan pass re-created A/B/C indexes and ran the same projected SELECTs outside timing. SQL plan XML is stored in one full transcript rather than 12 individual `.sqlplan` files. The current local disposable copies remain available for SSMS export and cleanup. The original Phase 2 truncated `.rpt` remains a Phase 2 evidence blocker; Phase 3's plan pass does not retroactively make that artifact complete.

The SQL script relies on SQL Server `FOR JSON PATH` preserving the ordered query input for U1d, and diagnostic plans confirm `Sort` removal in C. Mongo plan measurements use `explain('executionStats')`, which reports examined keys/documents independently of the timed cursor; see [Microsoft FOR JSON PATH](https://learn.microsoft.com/en-us/sql/relational-databases/json/format-query-results-as-json-with-for-json-sql-server), [Microsoft SET STATISTICS XML](https://learn.microsoft.com/en-us/sql/t-sql/statements/set-statistics-xml-transact-sql), and [MongoDB explain results](https://www.mongodb.com/docs/v7.0/reference/explain-results/).
