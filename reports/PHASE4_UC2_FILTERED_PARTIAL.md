# Phase 4 — UC2 filtered/partial index

**Date:** 2026-10-24. **Status: PASS for the local 100K and 1M experiment.** Native T-SQL and mongosh ran on disposable copies only. SQL Server 17.0.1145.4 and MongoDB 7.0.12 source counts and `Y` counts were rechecked after the runs. This is one timed run per final configuration and engine; repeat on the presentation machine before generalizing small latency differences.

## Controlled design

SQL sources: `dbo.DEMO_BIG_TABLE_100K` and `dbo.DEMO_BIG_TABLE_1000K`, both heaps. Mongo sources: exact-case `big_table_100k` and `big_table_1000K`. The 1M suffix is **`1000K`** in this project. Each scale uses one read copy and three independent write copies. SQL copies start as heaps without secondary indexes; Mongo copies start with `_id_` only. Existing source indexes were preserved. No optional UC2 index was built on a source.

| Config | SQL Server | MongoDB |
|---|---|---|
| A | No optional index | Only mandatory `_id_` |
| B | `(OBJECT_TYPE, OBJECT_ID) INCLUDE (TEMPORARY)` | `{OBJECT_TYPE:1, OBJECT_ID:1, TEMPORARY:1}` |
| C | Same keys/INCLUDE as B, `WHERE TEMPORARY=N'Y'` | Same keys as B, `partialFilterExpression:{TEMPORARY:'Y'}` |

Both reads project only `OBJECT_TYPE, OBJECT_ID, TEMPORARY` and filter `OBJECT_TYPE='TABLE'`, `OBJECT_ID BETWEEN 1 AND 10000`, plus `TEMPORARY='Y'` (inside) or `'N'` (outside). SQL uses a **literal** for this main comparison; the parameter test is separate. Source-matched counts are 82 Y / 2,108 N at 100K and 615 Y / 15,810 N at 1M. Total subset membership is 254/100,000 (0.254%) and 2,405/1,000,000 (0.2405%). Every timed read verified count and projected-value checksum/sum; every plan was collected outside timed loops.

There were 2 warmups and 25 timed reads for each of 12 scale/config/query cells (300 SQL and 300 Mongo samples). SQL materialized the full projection with `FOR JSON PATH` in server memory; mongosh fully consumed the projected cursor. **Their timer boundaries differ; do not compare SQL milliseconds against Mongo milliseconds.** SQL logical reads below come from the separate `SET STATISTICS XML` pass; Mongo examined counts come from separate `explain('executionStats')` calls.

## Read latency and access path

**SQL Server** — p50 milliseconds, with logical reads in parentheses:

| Scale/query | A | B | C | B→C p50 speedup |
|---|---:|---:|---:|---:|
| 100K Y | 30.655 (2,732) | 3.047 (14) | 1.002 (3) | 3.04× |
| 100K N | 52.667 (2,732) | 19.382 (14) | 52.722 (2,732) | 0.37× |
| 1M Y | 92.318 (28,032) | 8.998 (81) | 5.992 (6) | 1.50× |
| 1M N | 347.952 (28,032) | 292.283 (81) | 349.618 (28,032) | 0.84× |

SQL actual plans show B `Index Seek` for Y and N, C `Index Seek` for Y and `Table Scan` for N. A scans. The separate C parameter probes with `@p=Y/N`, both cached and `OPTION (RECOMPILE)`, selected table scans in this local run; this observation does not imply every SQL parameterized filtered-index query must scan. Full 20 plan XML elements and IO messages are in the diagnostic transcript.

**MongoDB** — p50 milliseconds, with keys/docs examined in parentheses:

| Scale/query | A | B | C | B→C p50 speedup |
|---|---:|---:|---:|---:|
| 100K Y | 238.95 (0/100,000) | 8.82 (1,137/0) | 2.24 (83/0) | 3.94× |
| 100K N | 263.78 (0/100,000) | 21.98 (2,150/0) | 256.30 (0/100,000) | 0.09× |
| 1M Y | 2,418.94 (0/1,000,000) | 17.17 (1,670/0) | 6.13 (616/0) | 2.80× |
| 1M N | 2,447.95 (0/1,000,000) | 69.45 (15,852/0) | 2,438.73 (0/1,000,000) | 0.03× |

Mongo plans show `COLLSCAN` for A and C/N, and covered `IXSCAN` with zero documents examined for B/Y, B/N and C/Y. C cannot serve N completely because N documents are absent from that partial index. B scans more keys for Y because `TEMPORARY` is its trailing key; C has only Y members. The four query results match the corresponding source within each engine.

Read speedup ratios (baseline p50 ÷ candidate p50; below 1× means the candidate was slower):

| Engine/scale/query | A→B | A→C | B→C |
|---|---:|---:|---:|
| SQL 100K Y / N | 10.06× / 2.72× | 30.59× / 1.00× | 3.04× / 0.37× |
| SQL 1M Y / N | 10.26× / 1.19× | 15.41× / 1.00× | 1.50× / 0.84× |
| Mongo 100K Y / N | 27.09× / 12.00× | 106.67× / 1.03× | 3.94× / 0.09× |
| Mongo 1M Y / N | 140.88× / 35.25× | 394.61× / 1.00× | 2.80× / 0.03× |

## Storage and index build

| Engine/scale | B build; index bytes | C build; index bytes | C storage reduction vs B |
|---|---:|---:|---:|
| SQL 100K | 197.512 ms; 4,677,632 | 29.304 ms; 49,152 | 98.95% |
| SQL 1M | 1,741.435 ms; 45,867,008 | 179.262 ms; 131,072 | 99.71% |
| Mongo 100K | 1,076 ms; 1,249,280 | 270 ms; 20,480 | 98.36% |
| Mongo 1M | 9,967 ms; 12,525,568 | 2,947 ms; 53,248 | 99.57% |

A has zero **optional** index bytes; A→B and A→C absolute increases equal the respective B/C byte values. These timers exclude copying source data. Each B index was dropped before building C on the read copy. Mongo `_id_` storage is excluded from the B/C figures; SQL bytes are used pages × 8,192. The build times are one observation each, not distributions.

## Write probes and limits

Each independent A/B/C write copy started from the same scale's source image. B/C indexes were installed before timing. Per configuration: 10 batches × 20 real-source rows for `INSERT_N`, the same for `INSERT_Y`, 10 disjoint batches × 20 original IDs for `N_TO_Y`, and 10 × 20 for `Y_TO_N`. The same payloads and IDs were used across configurations within each engine; insert samples and update ID lists were prepared **outside** the timers. All six copies finished at source size + 400 rows, and every batch affected exactly 20 rows. Values below are median milliseconds per 20-row batch; raw samples and p95 are in the evidence files.

| Engine/scale | Operation | A p50 | B p50 | C p50 |
|---|---|---:|---:|---:|
| SQL 100K | INSERT N / INSERT Y | 1.114 / 1.483 | 1.481 / 1.954 | 1.111 / 1.897 |
| SQL 100K | N→Y / Y→N | 85.162 / 49.002 | 99.650 / 46.332 | 97.066 / 26.412 |
| SQL 1M | INSERT N / INSERT Y | 1.007 / 1.007 | 2.016 / 1.986 | 1.016 / 1.109 |
| SQL 1M | N→Y / Y→N | 154.816 / 142.086 | 151.538 / 93.008 | 151.113 / 49.265 |
| Mongo 100K | INSERT N / INSERT Y | 3.10 / 2.33 | 2.96 / 2.63 | 1.43 / 3.06 |
| Mongo 100K | N→Y / Y→N | 383.61 / 315.55 | 383.75 / 305.63 | 394.21 / 320.65 |
| Mongo 1M | INSERT N / INSERT Y | 1.54 / 1.95 | 2.13 / 1.83 | 1.80 / 2.38 |
| Mongo 1M | N→Y / Y→N | 3,735.59 / 3,161.33 | 3,790.37 / 3,168.80 | 3,832.92 / 3,234.23 |

INSERT rates in rows/s and UPDATE p95 values are preserved per engine/scale/config/operation in raw `WRITE_SUMMARY` entries. An INSERT N should avoid a new C index entry, whereas INSERT Y and both transitions affect membership, but the observed latencies also include heap/collection writes and scheduling noise. UPDATE finds target IDs on an unindexed SQL heap / Mongo collection (Mongo `_id_` is a different field); full-table search dominates many update timings, especially at 1M. **These update numbers do not isolate index maintenance alone.** The 20-row batch is constrained by the 254 source Y rows at 100K and is much smaller than production batch sizes.

## Evidence and rerun

- `sql/uc2_filtered/uc2_run.sql`: standalone SSMS T-SQL, no SQLCMD Mode dependency; creates eight copies, measures A/B/C on 100K/1M, emits raw and summaries.
- `sql/uc2_filtered/uc2_diagnostics.sql`: separate 12 literal + 8 SQL parameter actual plans with IO; capture via `sqlcmd -y 0` or save SSMS XML cells as `.sqlplan`.
- `sql/uc2_filtered/uc2_cleanup.sql`: explicit eight-copy cleanup after evidence export.
- `mongo/uc2_partial/uc2_run.js` and `uc2_cleanup.js`: direct mongosh scripts with JSONL output.
- `results/uc2/accepted/phase4_uc2_sql_run_v4.txt`: accepted SQL raw evidence, 300 read + 240 write samples, 12 read + 24 write summaries, 4 builds, `RUN_COMPLETE PASS`.
- `results/uc2/plans/phase4_uc2_sql_diagnostics_v4.txt`: accepted complete SQL plan evidence, 12 literal + 8 parameter markers and 20 closed XML plans.
- `results/uc2/plans/sql_*.sqlplan` and `mongo_*.json`: individual plans extracted from accepted transcripts; see `results/PLAN_INDEX.csv` for each scale/configuration/query mapping.
- `results/uc2/accepted/phase4_uc2_mongo_run.jsonl`: accepted Mongo evidence, 8 copy inventories, 12 raw read arrays and plans, 24 raw write arrays and summaries, `RUN_COMPLETE PASS`.
- `results/uc2/accepted/phase4_uc2_sql_source_postcheck.txt` and `phase4_uc2_sql_source_indexes_postcheck.txt`: source count/Y and original three-index inventory for both SQL scales.
- `results/uc2/accepted/phase4_uc2_mongo_source_postcheck.jsonl`: both Mongo sources still have 100K/254 Y and 1M/2,405 Y, with original `_id_` and `TEMPORARY_1` indexes.

The first SQL attempt truncated the `1000K` copy name to `1000`; those eight experimental copies were removed after detecting it. SQL v2 used a parameter in the main read workload, and SQL v3 included source sample selection in the write timer. Both were corrected and rerun; **v4 alone supplies the accepted SQL result tables above**. Earlier attempt outputs remain in `results/uc2/archive/` for audit, not for conclusions.

From the `EW_redo` root, after saving prior UC2 output and running the UC2 cleanup scripts if copies already exist:

```powershell
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -s '|' -y 0 -i sql/uc2_filtered/uc2_run.sql -o results/uc2/archive/phase4_uc2_sql_run_next.txt
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -y 0 -i sql/uc2_filtered/uc2_diagnostics.sql -o results/uc2/plans/phase4_uc2_sql_diagnostics_next.txt
mongosh --quiet --file mongo/uc2_partial/uc2_run.js *> results/uc2/accepted/phase4_uc2_mongo_run_next.jsonl
```

Check exit codes and `RUN_COMPLETE PASS`. Use new output names for every attempt, because shell redirection can truncate an existing evidence file even when the script fails. Do not run the two timed engines at the same time on this machine. The current disposable copies remain for inspection; use the explicit cleanup files only after saving any further plan exports.

Mechanism references: [Microsoft filtered indexes and required SET options](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/create-filtered-indexes), [Microsoft CREATE INDEX](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-index-transact-sql?view=sql-server-ver17), [MongoDB 7.0 partial-index eligibility](https://www.mongodb.com/docs/v7.0/core/index-partial/).
