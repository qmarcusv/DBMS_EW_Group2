# Phase 1 — dataset and database audit

**Observed:** 2026-10-23 (Asia/Saigon). **Phase acceptance: PARTIAL.** The required 10K, 100K and 1M sources are present and their specified counts agree across the local CSV, SQL Server and MongoDB. Full row-by-row identity, MongoDB index-creation permission, and the optional 15M exact checks remain unverified. No benchmark or database write was performed.

## How this audit was run

Run [the SQL script](../sql/phase1_verify.sql) directly in SSMS while connected to the local SQL Server instance. Its first statement selects `DBMS_EW_Group02`; retain all result grids and Messages. The same script ran locally with:

```powershell
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -l 10 -b -i 'sql/phase1_verify.sql' -W -s '|' -h -1
```

`-C` was required by this local ODBC 18 connection because the server certificate was not trusted. The command exited 0. For MongoDB, connect to the local server in mongosh and run `load('mongo/phase1_verify.js')`, or use:

```powershell
& 'C:\Users\ADMIN\AppData\Local\Programs\mongosh\mongosh.exe' 'mongodb://127.0.0.1:27017/dbms_ew_group02?serverSelectionTimeoutMS=5000' --quiet --file 'mongo/phase1_verify.js'
```

This also exited 0. Both scripts are read-only. Their exact scans are limited to the three required scales; 15M is inventoried through metadata/estimate only. `mongosh --version` was independently checked as `2.13.0`.

## Runtime and object inventory

| System | Verified local observation |
|---|---|
| SQL Server | Product `17.0.1145.4`, RTM, Enterprise Developer Edition (64-bit), engine edition 3. Database `DBMS_EW_Group02` is online and read-write, compatibility level `170`, collation `SQL_Latin1_General_CP1_CI_AS`. |
| MongoDB | Server `7.0.12`, WiredTiger persistent storage, database `dbms_ew_group02`; mongosh `2.13.0`. |
| SQL target tables | `dbo.DEMO_BIG_TABLE_10K`, `dbo.DEMO_BIG_TABLE_100K`, `dbo.DEMO_BIG_TABLE_1000K`, `dbo.DEMO_BIG_TABLE_15000K`: all visible, SELECT permission reported as 1, all heaps. Metadata row estimates: 10,000; 100,000; 1,000,000; 15,000,000. |
| MongoDB target collections | Exact case-sensitive names `big_table_10K`, `big_table_100k`, `big_table_1000K`, `big_table_15000K` all present. The 15M estimated document count is 15,000,000. |

All four SQL tables have the same 14 source columns, each declared nullable. The observed SQL type mapping is: `ID`, `OBJECT_ID`, `DATA_OBJECT_ID` = `bigint`; `OWNER` = `nvarchar(128)`; `OBJECT_NAME`, `SUBOBJECT_NAME` = `nvarchar(256)`; `OBJECT_TYPE` = `nvarchar(64)`; `CREATED`, `LAST_DDL_TIME` = `datetime2(3)`; `TIMESTAMP`, `STATUS` = `nvarchar(32)`; `TEMPORARY`, `GENERATED`, `SECONDARY` = `nchar(1)`. The catalog returned no primary/unique key, foreign key, check, or default constraints on the four targets. No provenance columns (`EW_DATASET_ID`, `SOURCE_ROW_NUMBER`) were present on these current tables, so table-name mapping and comparison supply the current load evidence; the historical DATA_READY records refer to other targets.

SQL Server already has three nonclustered indexes on **each** reference table: `IX_DEMO_OBJECT_ID` on `(OBJECT_ID)` with `ID, OWNER, OBJECT_NAME, OBJECT_TYPE` included; `IX_DEMO_S2_Filtered` on `(TEMPORARY)` filtered to `TEMPORARY='Y'`; and `IX_DEMO_S2_Full` on `(TEMPORARY)`. The MongoDB 10K collection has `_id_` only. The MongoDB 100K, 1M and 15M collections have `_id_` plus a partial `TEMPORARY_1` index with `partialFilterExpression: {TEMPORARY:'Y'}`. These existing indexes would contaminate UC1–UC3 A/B/C baselines. Later work must inventory and manage indexes on **disposable copies**; leave the reference objects untouched.

## Source CSV inventory and provenance

The derived files below exist under `local_data/derived/`. SHA-256 values for 1K through 1M were recomputed locally. The 15M hash is **manifest-recorded only**; the 2.24 GB file was not rehashed in this phase.

| Scale | Actual filename | Bytes | SHA-256 / status |
|---|---|---:|---|
| 1K | `BIG_TABLE_1K.csv` | 112,335 | `0ccc54a62854aa02535c45ee33ae96d6d7478f855ce44fa69e252a5a930b939f` |
| 10K | `BIG_TABLE_10K.csv` | 1,186,241 | `7f41f9d5a36b932a25101cc8929aad540a3f9f76ae68b5d434a221b7d6d4f116` |
| 100K | `BIG_TABLE_100K.csv` | 14,377,944 | `9c25e7db9f082818de200dce32da368cc735cdcfaf03839fe1ef18da3d66ef9d` |
| 1M | `BIG_TABLE_1000K.csv` | 147,724,204 | `8183c2bd49a07ba7dd800b2258100051bf02d2be15023ad3436603f40e6fbb4c` |
| 15M | `BIG_TABLE_15000K.csv` | 2,243,169,465 | **Not recomputed.** `scale_datasets_manifest.json` records `fdc03f36fd18ece785b582ec696f010462c69d80fe0548d8260302fd67d3910a`, but names `BIG_TABLE_15M.csv`. |

The plan names `BIG_TABLE_1M.csv` and `BIG_TABLE_15M.csv`; the current files instead use `1000K` and `15000K`. The source export `local_data/source/big table export.sql` exists. Historical 1K/10K DATA_READY records are useful provenance but refer to `dbo.BIG_TABLE` and `big_table_1k`/`big_table_10k`, not the current target names. No current-target import manifest or row-level digest was found in the inspected artifacts.

## Exact parity at required scales

Each cell lists **CSV / SQL / MongoDB**, in that order. CSV values came from parsing each current file; SQL and MongoDB values came from the live Phase 1 scripts. Counts are exact for these scales. They agree with the earlier user-provided preliminary numbers, now independently checked on the current target names.

| Scale | Total | `OBJECT_ID` 100–500 | `SYS` + `TABLE` | `TEMPORARY='Y'` | Status |
|---|---:|---:|---:|---:|---|
| 10K | 10,000 / 10,000 / 10,000 | 332 / 332 / 332 | 1,125 / 1,125 / 1,125 | 51 / 51 / 51 | **PASS** for Phase 1 minimum checks |
| 100K | 100,000 / 100,000 / 100,000 | 664 / 664 / 664 | 3,405 / 3,405 / 3,405 | 254 / 254 / 254 | **PASS** for Phase 1 minimum checks |
| 1M | 1,000,000 / 1,000,000 / 1,000,000 | 4,980 / 4,980 / 4,980 | 25,405 / 25,405 / 25,405 | 2,405 / 2,405 / 2,405 | **PASS** for Phase 1 minimum checks |
| 15M optional | CSV manifest 15,000,000 / SQL metadata 15,000,000 / Mongo estimate 15,000,000 | Not scanned | Not scanned | Not scanned | **WARN**: optional estimates only |

For 10K, 100K and 1M, the SQL exact scans found zero NULL values in `ID`, `OBJECT_ID`, `OWNER`, `OBJECT_TYPE`, `TEMPORARY`, and zero `OBJECT_ID` values that fail bigint conversion. The MongoDB `$type` aggregation found every document's `ID` and `OBJECT_ID` as BSON `int`, and `OWNER`, `OBJECT_TYPE`, `TEMPORARY` as `string`; no null or missing values appeared for those five fields. All three CSV files likewise had zero blank/invalid values in these checked fields. SQL and MongoDB matched on sampled `ID` values 1, 5,000, 10,000, 100,000 and 1,000,000 where present. Examples: `ID=1` maps to `OBJECT_ID=16`, `SYS`, `TABLE`, `N`; `ID=1,000,000` maps to `OBJECT_ID=19192`, `SYS`, `VIEW`, `N`.

This is predicate-count, type and sampled-row parity, **not** a complete row-by-row or content-hash proof. SQL `bigint` and BSON `int` are both numeric but have different storage widths. Future equality and range queries must keep their semantics explicit. Optional columns, date precision and collation/case behavior were not exhaustively compared.

## Full-Text and permissions

`FULLTEXTSERVICEPROPERTY('IsFullTextInstalled') = 1` and `SERVERPROPERTY('IsFullTextInstalled') = 1`. The local `MSSQLFDLauncher` service was running. The current SQL login reported `CREATE TABLE = 1`, `CREATE FULLTEXT CATALOG = 1`, and SELECT/ALTER permissions on the four source tables. This confirms component installation and relevant catalog privileges, but does not prove that the later prose corpus, its required unique non-null key, catalog, full-text index, or population state exists. Those are Phase 6 tasks on disposable objects. MongoDB index-creation permission was **not tested**, because a definitive test would require a write; Phase 2 must check it on disposable copies.

## Requirements before Phase 2

1. Use the verified 100K and 1M exact object names. Correct the plan's two CSV filename references before any automated file mapping; retain the historical DATA_READY target names as historical only.
2. Create independent disposable benchmark copies and verify equivalent rows before timing. Establish a stronger row-level ID/content comparison or digest if complete parity is required; the four counts and sampled IDs alone cannot prove it.
3. Define A/B/C copy setup from the inventoried indexes. Remove or recreate pre-existing optional indexes **only on copies**, then record every retained index and constraint. The current SQL covering and filtered indexes and MongoDB partial indexes can otherwise invalidate baselines.
4. Check MongoDB create/drop-index permissions on a disposable copy. Keep the exact 15M integrity scan optional; if used later, recompute its source hash and exact predicate counts first.
5. For UC4, source and verify a technical-prose corpus, create a valid unique non-null SQL full-text key on its copy, and verify full-text population before measuring search.

Phase 2 infrastructure and every UC experiment remain **not started**.
