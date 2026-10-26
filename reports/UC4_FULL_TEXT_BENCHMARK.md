# UC4 — Native full-text benchmark on the 10K news corpus

**Run date:** 2026-10-25. **Status:** both engines completed; corpus and read copies passed full-row parity. This experiment was added after the earlier decision to defer UC4; Phase 6 UC5 evidence remains separate.

## Corpus and protocol

The source is `genesisqu/fake-real-news` at commit `9cca94a438905a40883b71c3b5f91c9673b6eec9`. [Source provenance](../local_data/source/fake_real_news/PROVENANCE.json) records hashes of `Fake.csv` and `True.csv`. [Corpus manifest](../local_data/derived/uc4/manifest.json) identifies the 10K subset: 5,000 nonblank `text` rows per source, chosen by the smallest SHA-256 values of `source filename:1-based row number`. [Corpus JSONL](../local_data/derived/uc4/corpus_10k.jsonl) SHA-256 is `2f09bc3aef865ccc85cc80eba9cc9104aae2af8fa9e81cb845dadc345fd8dd97`. Exact duplicate texts remain. `BODY` alone is indexed; `TITLE`, `SUBJECT`, `RAW_DATE` and source fields preserve provenance. The file label is source metadata, not a verified truth label.

[Full-row parity output](../results/uc4/accepted/uc4_seed_parity.json) checked every field of 10,000 source rows in the SQL seed, Mongo seed, SQL read A/C and Mongo read A/C; all mismatch counts were zero. SQL Server was 17.0.1145.4 with Full-Text Search installed; MongoDB was 7.0.12. The SQL A/C tables each retained a clustered primary key on `DOC_ID`; Mongo A/C each retained `_id_`. There is no B configuration with equivalent token/phrase semantics.

For each of six queries and each A/C copy, the script ran two warmups and 25 timed reads. The SQL timer surrounds T-SQL materialization of all matching `DOC_ID` values to JSON on the server; the Mongo timer surrounds `find(...).toArray()` in mongosh. Both fully consume the result. Plans and IO diagnostics were captured separately. The timing boundaries differ, so only within-engine ratios are meaningful. A is substring `LIKE N'%term%'` or case-insensitive unanchored Mongo regex; C is SQL `CONTAINS(BODY,'"term"',LANGUAGE 1033)` or Mongo `$text` with English text index and quoted phrase search. [Design and EDA](UC4_DATASET_EDA_AND_MEASUREMENT_DESIGN.md) explains the six candidate queries.

## Read results

Counts and median milliseconds below come from the [validated summary](../results/uc4/accepted/uc4_summary.json). `A≠C` means the **set of `DOC_ID` values** differs, even when counts match. Do not report A→C as a same-result speedup in those cases.

| Query | SQL A count / ms | SQL C count / ms | SQL same IDs? | Mongo A count / ms | Mongo C count / ms | Mongo same IDs? |
|---|---:|---:|---|---:|---:|---|
| `election` | 2,577 / 3,294.24 | 2,311 / 21.00 | No | 2,577 / 384.60 | 3,083 / 15.18 | No |
| `climate` | 326 / 3,983.54 | 324 / 17.40 | No | 326 / 299.96 | 326 / 6.41 | Yes |
| `bitcoin` | 7 / 3,986.99 | 6 / 14.86 | No | 7 / 197.50 | 7 / 1.83 | Yes |
| `"white house"` | 1,851 / 3,439.64 | 1,845 / 22.55 | No | 1,851 / 140.53 | 1,851 / 42.58 | Yes |
| `"climate change"` | 214 / 4,041.98 | 215 / 16.63 | No | 214 / 288.39 | 214 / 52.39 | Yes |
| `"stock market"` | 45 / 4,060.09 | 37 / 14.13 | No | 45 / 419.56 | 45 / 25.55 | Yes |

Mongo A and SQL A returned identical `DOC_ID` sets for all six ASCII queries. All six C sets differed between SQL and Mongo. For example, Mongo English stemming expanded `election` to 3,083 matches; SQL returned 2,311. SQL A/C differed for all six queries. Within Mongo, five A/C pairs returned identical IDs; their observed median A/C ratios were approximately 46.8× (`climate`), 107.9× (`bitcoin`), 3.3× (`white house`), 5.5× (`climate change`) and 16.4× (`stock market`). These ratios describe this 10K corpus and run, not a general cross-engine performance ranking. The [summary JSON](../results/uc4/accepted/uc4_summary.json) includes p95, A-only/C-only counts and the exact comparison gates; the [SQL transcript](../results/uc4/accepted/uc4_sql_run.txt) and [Mongo JSONL](../results/uc4/accepted/uc4_mongo_run.jsonl) contain raw samples and complete matched ID lists.

The [SQL diagnostic transcript](../results/uc4/plans/uc4_sql_diagnostics.txt) contains `STATISTICS IO`, `STATISTICS TIME` and actual ShowPlan XML. Twelve individual `.sqlplan` files are in [the plan folder](../results/uc4/plans/). SQL A plans show clustered scans and filters; C plans show a full-text table-valued function joined to the clustered table. Mongo A `explain('executionStats')` shows `COLLSCAN`; C shows `IXSCAN` and `TEXT_MATCH`. Twelve individual Mongo explain JSON files are in the same plan folder. The [UC4 plan index](../results/uc4/PLAN_INDEX.csv) maps each file to its source transcript. The SQL C plan still touches the base table for `DOC_ID`; its measured benefit is not evidence of an index-only plan.

## Build, storage, writes, freshness

| Metric | SQL Server | MongoDB |
|---|---:|---:|
| C read index creation call | 63.06 ms | 11,582.26 ms |
| C read population complete | 15,203.27 ms from index DDL start; 10,000 items | Synchronous `createIndex` completion |
| C read index footprint | 13 logical MB, dedicated full-text catalog | 26,411,008 bytes for `ix_uc4_body_text` |
| INSERT A / C throughput, 200 real-text rows in 10 batches | 4,573.73 / 3,362.02 rows/s | 2,537.98 / 119.06 rows/s |
| UPDATE A / C median per 20-row batch | 2.99 / 3.00 ms | 38.71 / 115.47 ms |
| One update-to-search-visible observation, C | 5,795.36 ms; 93 polls | 21.30 ms; 1 poll |

SQL reports catalog `IndexSize`, a logical size measure; Mongo reports collection `indexSizes`. They are not directly equivalent physical storage figures. SQL's full-text `CHANGE_TRACKING=AUTO` update became searchable asynchronously in this one observation; Mongo's text index was visible at the first post-update poll. Neither one-event freshness measurement estimates a distribution. Write measurements stop at acknowledged DML and do not include subsequent SQL full-text visibility delay. Mongo C's insert rate was strongly affected by maintaining the large text index, and its first batches were slow; see all raw samples and p95 before generalizing.

SQL setup output is [here](../results/uc4/accepted/uc4_sql_setup.txt); Mongo build/storage records are in the [run JSONL](../results/uc4/accepted/uc4_mongo_run.jsonl). The SQL read catalog stayed at 13 logical MB; the write catalog reached 14 logical MB after writes.

## Reproduce and scope

From the workspace root, with SQL Server and MongoDB running and the pinned source CSVs present:

```powershell
py -3.13 analysis/uc4_prepare.py
py -3.13 analysis/uc4_load_sql.py
mongoimport --db dbms_ew_group02 --collection uc4_seed_10k --file local_data/derived/uc4/corpus_10k.jsonl --type json --stopOnError
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -i sql/uc4_text/uc4_setup.sql -o results/uc4/accepted/uc4_sql_setup.txt -y 0 -w 65535
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -i sql/uc4_text/uc4_run.sql -o results/uc4/accepted/uc4_sql_run.txt -y 0 -w 65535
mongosh --quiet --file mongo/uc4_text/uc4_run.js > results/uc4/accepted/uc4_mongo_run.jsonl
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -i sql/uc4_text/uc4_diagnostics.sql -o results/uc4/plans/uc4_sql_diagnostics.txt -y 0 -w 65535
mongoexport --db dbms_ew_group02 --collection uc4_seed_10k --out results/uc4/accepted/uc4_mongo_seed_export.jsonl
py -3.13 analysis/uc4_verify.py
py -3.13 analysis/uc4_summarize.py
```

The scripts guard against existing UC4 copies; preserve output, then use [SQL cleanup](../sql/uc4_text/uc4_cleanup.sql) and [Mongo cleanup](../mongo/uc4_text/uc4_cleanup.js) before rerunning. The current disposable UC4 objects were **left in place** for inspection. No original `BIG_TABLE` or UC1–UC3/UC5 result was changed. This 10K news corpus does not justify a 100K result or claims about other prose domains.

SQL full-text population and catalog size are interpreted using [Microsoft's population guidance](https://learn.microsoft.com/en-us/sql/relational-databases/search/populate-full-text-indexes?view=sql-server-ver17) and [`FULLTEXTCATALOGPROPERTY`](https://learn.microsoft.com/en-us/sql/t-sql/functions/fulltextcatalogproperty-transact-sql?view=sql-server-ver17). Mongo behavior follows the [MongoDB 7.0 `$text` reference](https://www.mongodb.com/docs/v7.0/reference/operator/query/text/) and [text-index language documentation](https://www.mongodb.com/docs/v7.0/core/indexes/index-types/index-text/specify-text-index-language/).
