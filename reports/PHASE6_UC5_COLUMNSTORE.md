# Phase 6 — UC5 rowstore versus columnstore (2026-10-24)

**Status: PASS for the revised execution scope.** The user excluded UC4 full-text because the current dataset contains catalog identifiers rather than prose. Phase 6 therefore executes UC5 on the existing 1M SQL Server dataset. This is a SQL-only physical storage experiment; no MongoDB columnstore claim is made.

## Method

`dbo.UC5_Rowstore` (B, heap) and `dbo.UC5_Columnstore` (C, clustered columnstore) were independent `SELECT * INTO` copies of `dbo.DEMO_BIG_TABLE_1000K`. Both had 1,000,000 rows before index build and no optional secondary indexes. A is N/A for this physical layout comparison. CCI build was timed on the populated C copy. Queries were an aggregation by `OBJECT_TYPE` with `COUNT_BIG(*)` and `SUM(OBJECT_ID)`, plus one `ID=1` point projection. The aggregation returned 35 groups; the point query returned one row. Both configurations matched the source count/checksum checks across 25 measured executions after two warmups.

SQL read timing includes server-side JSON materialization and parsing of the entire projected result, with identical query shape per configuration. `STATISTICS IO/TIME/XML` ran afterward, separately from timing. The diagnostic plans were captured after the controlled writes; they reflect the same layout and an additional 200 inserted rows and 200 updated rows in each copy. The CCI had one compressed rowgroup with 1M rows before writes; afterward it showed 200 deleted rows there and an open delta rowgroup of 400 rows. This is an observed state, not a promised outcome for other workloads. SQL Server's [columnstore DDL](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-columnstore-index-transact-sql) and [partition storage counters](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm_db_partition-stats-transact-sql) define the index and page metrics used here.

## Results

| Metric | B heap rowstore | C clustered columnstore |
|---|---:|---:|
| Used physical bytes before writes | 229,638,144 | 9,920,512 |
| Reserved physical bytes before writes | 229,974,016 | 10,035,200 |
| Aggregation median / p95 ms | 123.203 / 140.229 | 42.438 / 46.936 |
| Point median / p95 ms | 88.805 / 107.293 | 3.626 / 4.416 |
| INSERT throughput, 10 × 20 rows/s | 13,265 | 6,642 |
| UPDATE median per 20 rows, ms | 154.437 | 34.514 |
| CCI build time | N/A | 22,294.926 ms |

The measured used-byte ratio is about 23.15:1 (B/C). The aggregation median ratio is about 2.90:1. The point median ratio is about 24.49:1 in this run; it should not be treated as general point-query superiority of columnstore. Both point queries scanned their base table, and the C copy was much smaller. The actual B aggregation plan included row and batch execution modes; the C aggregation plan used batch mode. B point scan used row mode, C point scan used batch mode. SQL Server can use batch mode on rowstore, so execution mode was read from the actual plan rather than inferred from table type ([Microsoft query performance guidance](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/columnstore-indexes-query-performance)).

INSERT throughput was roughly half on C in this small-batch test. The UPDATE workload also selected by unindexed `ID` and includes the row-location scan; the lower C UPDATE latency in this run is not an isolated index-maintenance advantage. Build time is one observation. No cross-engine timing comparison was attempted.

## Evidence and rerun

The first attempted run, [phase6_uc5_sql_run.txt](../results/uc5/archive/phase6_uc5_sql_run.txt), stopped at a script-level checksum check: the variable holding the aggregation expectation was reused for the point query before the C aggregation. Both copies' direct group checksums matched the source. The script now holds distinct aggregation expectations; the failed copies were removed ([cleanup log](../results/uc5/archive/phase6_uc5_sql_failed_cleanup.txt)) before a fresh run. The accepted evidence is [phase6_uc5_sql_run_v2.txt](../results/uc5/accepted/phase6_uc5_sql_run_v2.txt), ending in `RUN_COMPLETE: PASS`; [four complete actual plans](../results/uc5/plans/phase6_uc5_sql_diagnostics.txt) have matching opening/closing XML tags. Source counts and index names are in the [postcheck](../results/shared/accepted/phase5_6_sql_source_postcheck.txt). Disposable copies were removed after export ([final cleanup](../results/uc5/accepted/phase6_uc5_sql_cleanup.txt)).

The four individual `.sqlplan` files are in [UC5 plans](../results/uc5/plans/) and listed in [PLAN_INDEX.csv](../results/PLAN_INDEX.csv).

Run each file as a whole in SSMS, or from the workspace root:

```powershell
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -s '|' -y 0 -i sql/uc5_columnstore/uc5_run.sql -o results/uc5/accepted/phase6_uc5_sql_run_new.txt
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -l 10 -s '|' -y 0 -i sql/uc5_columnstore/uc5_diagnostics.sql -o results/uc5/plans/phase6_uc5_sql_diagnostics_new.txt
```

The cleanup file is `sql/uc5_columnstore/uc5_cleanup.sql`; run it only after saving the output. Use new output names on reruns so previous raw evidence survives.
