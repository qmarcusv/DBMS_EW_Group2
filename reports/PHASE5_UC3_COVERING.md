# Phase 5 — UC3 covering/covered (2026-10-24)

**Status: PASS for execution and correctness.** Both DBMSs completed 100K and 1M A/B/C runs. All 18 read result sets per DBMS matched their source projection. Source row counts and indexes were unchanged. Disposable UC3 copies were removed after raw evidence was saved.

## Method and reproducibility

- SQL source: `dbo.DEMO_BIG_TABLE_100K`, `dbo.DEMO_BIG_TABLE_1000K`; both heaps. Mongo source: `big_table_100k`, `big_table_1000K` in `dbms_ew_group02`.
- A: heap scan / Mongo collection scan with mandatory `_id_` index. B: SQL `(OBJECT_ID)` nonclustered / Mongo `{OBJECT_ID:1}`. C: SQL `(OBJECT_ID) INCLUDE (ID,OWNER,OBJECT_NAME,OBJECT_TYPE)` / Mongo compound `{OBJECT_ID:1,ID:1,OWNER:1,OBJECT_NAME:1,OBJECT_TYPE:1}`. SQL INCLUDE payload and Mongo compound keys are different storage mechanisms.
- Projection: `ID, OWNER, OBJECT_NAME, OBJECT_TYPE`; Mongo excludes `_id`. Point is `OBJECT_ID=16 AND ID=1`; small and medium are `OBJECT_ID BETWEEN 1 AND upper_bound`. Counts at 100K: 1, 98, 1,694 with bounds 16 / 50 / 1,000. Counts at 1M: 1, 60, 2,775 with bounds 16 / 5 / 200.
- SQL read time: complete projection materialized as JSON within T-SQL and parsed inside the measured `sp_executesql` call, 2 warmups and 25 samples. Mongo read time: `performance.now()` around complete `find(...).toArray()`, 2 warmups and 25 samples; exact projected documents compared outside the timed interval. SQL and Mongo elapsed times use different boundaries and are **not** a cross-engine speed contest. Actual plans/`explain` were captured separately.
- Build timing starts after the populated copy exists. INSERT and UPDATE each use 10 batches of 20 rows on independent, equally populated copies. Write target IDs were prepared before timing.

Run from workspace root. Execute one benchmark at a time; preserve each output before cleanup:

```powershell
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -s '|' -y 0 -i sql/uc3_covering/uc3_run.sql -o results/uc3/accepted/phase5_uc3_sql_run_new.txt
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -s '|' -y 0 -i sql/uc3_covering/uc3_diagnostics.sql -o results/uc3/plans/phase5_uc3_sql_diagnostics_new.txt
mongosh --quiet --file mongo/uc3_covered/uc3_run.js *> results/uc3/accepted/phase5_uc3_mongo_run_new.jsonl
```

The SQL files are plain T-SQL and run as whole scripts in SSMS. Save actual plans separately if using SSMS. Cleanup scripts are `sql/uc3_covering/uc3_cleanup.sql` and `mongo/uc3_covered/uc3_cleanup.js`.

## Read evidence

Median latency in ms; `0.000` is below the effective SQL batch timer resolution, not zero execution cost.

| DBMS | Scale | Query | A | B | C | B plan | C plan |
|---|---:|---|---:|---:|---:|---|---|
| SQL | 100K | Point | 26.091 | 0.000 | 0.000 | Index Seek + RID Lookup | Index Seek |
| SQL | 100K | Small | 30.010 | 2.013 | 1.518 | Index Seek + RID Lookup | Index Seek |
| SQL | 100K | Medium | 49.589 | 52.223 | 22.633 | Table Scan | Index Seek |
| SQL | 1M | Point | 78.290 | 0.000 | 0.000 | Index Seek + RID Lookup | Index Seek |
| SQL | 1M | Small | 85.711 | 1.127 | 0.000 | Index Seek + RID Lookup | Index Seek |
| SQL | 1M | Medium | 113.925 | 49.777 | 32.231 | Index Seek + RID Lookup | Index Seek |
| Mongo | 100K | Point | 216.06 | 2.68 | 2.59 | 2 docs examined | 0 docs examined |
| Mongo | 100K | Small | 225.39 | 2.83 | 4.40 | 98 docs examined | 0 docs examined |
| Mongo | 100K | Medium | 240.47 | 17.21 | 14.64 | 1,694 docs examined | 0 docs examined |
| Mongo | 1M | Point | 2,176.42 | 3.21 | 2.86 | 15 docs examined | 0 docs examined |
| Mongo | 1M | Small | 2,355.90 | 3.48 | 3.49 | 60 docs examined | 0 docs examined |
| Mongo | 1M | Medium | 2,579.41 | 23.91 | 20.12 | 2,775 docs examined | 0 docs examined |

SQL C had no RID Lookup in any of the six captured actual plans. Mongo C had `totalDocsExamined=0` in all six `executionStats`; B fetched base documents. Coverage therefore occurred in the measured plans. It did **not** yield lower median latency on every query: Mongo 100K small was slower in C, and Mongo 1M small was nearly tied. At SQL 100K medium, B selected a table scan, while C selected an index seek. SQL 1M medium B→C median improved from 49.777 to 32.231 ms (about 1.54×); Mongo 1M medium improved from 23.91 to 20.12 ms (about 1.19×).

## Build, storage, and writes

| DBMS | Scale | B build ms / index bytes | C build ms / index bytes |
|---|---:|---:|---:|
| SQL | 100K | 118 / 2,375,680 | 260 / 13,049,856 |
| SQL | 1M | 1,510 / 22,503,424 | 1,250 / 133,611,520 |
| Mongo | 100K | 801 / 856,064 | 892 / 6,987,776 |
| Mongo | 1M | 10,363 / 6,696,960 | 13,702 / 70,098,944 |

At 1M, C used about 5.94× B's SQL secondary-index bytes and 10.47× B's Mongo index bytes. Build timings are single observations, so their B/C order is not a stable performance claim. At 1M, SQL INSERT throughput was 6,129 / 5,813 / 5,230 rows/s for A/B/C; Mongo was 5,689 / 2,190 / 2,928 rows/s. These are small, 20-row batch workloads, and the Mongo B/C throughput order should not be generalized from one run.

**Write limitation:** UPDATE selected rows by `ID` without a dedicated ID index on the disposable copies. Its latency includes locating rows, often by scanning, plus updating `OBJECT_NAME`; it does not isolate pure index-maintenance cost. Exact UPDATE raw samples remain in the evidence files. SQL point medians of 0.000 ms likewise cannot support a finite speedup calculation.

## Evidence

- [SQL raw timing and correctness](../results/uc3/accepted/phase5_uc3_sql_run.txt); [18 complete SQL actual plans and IO/TIME](../results/uc3/plans/phase5_uc3_sql_diagnostics.txt). XML open and close tag counts were both 18.
- [Mongo raw timing, 18 `explain` plans, and correctness](../results/uc3/accepted/phase5_uc3_mongo_run.jsonl). File ends with `RUN_COMPLETE: PASS`.
- Individual SQL `.sqlplan` and Mongo `explain` JSON files are in [UC3 plans](../results/uc3/plans/); [plan index](../results/PLAN_INDEX.csv) maps each to its transcript.
- [SQL cleanup](../results/uc3/accepted/phase5_uc3_sql_cleanup.txt), [Mongo cleanup](../results/uc3/accepted/phase5_uc3_mongo_cleanup.jsonl), [SQL source postcheck](../results/shared/accepted/phase5_6_sql_source_postcheck.txt), [Mongo source and copy postcheck](../results/uc3/accepted/phase5_uc3_mongo_source_postcheck.jsonl).
