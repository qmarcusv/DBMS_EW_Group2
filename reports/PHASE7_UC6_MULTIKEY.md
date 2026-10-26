# Phase 7 — UC6 multikey and normalized tag membership

**Date:** 2026-10-25. **Status: PASS for the optional 10K experiment.** SQL Server 17.0.1145.4 and MongoDB 7.0.12 ran on disposable UC6 copies. All six seed/read snapshots passed a complete parent/tag field comparison with one canonical file. The experiment is an optional extension of the original research plan; it does not use the separate UC4 news corpus.

## Corpus and comparable membership semantics

[The deterministic builder](../analysis/uc6_prepare.py) reads the verified `BIG_TABLE_10K.csv` (SHA-256 `7f41f9d5a36b932a25101cc8929aad540a3f9f76ae68b5d434a221b7d6d4f116`) and creates [one parent/tag JSONL](../local_data/derived/uc6/parents_10k.jsonl) (SHA-256 `19519d7bcb66fa8231287298654a3fecc045d45a33a64e00ecb14b240f28ccd1`). Each parent has distinct, sorted tags derived from its real source fields: `owner:<OWNER>`, `type:<OBJECT_TYPE>`, `temporary:<TEMPORARY>`, optionally `generated:Y` and `subobject:present`. Tags are categorical encodings of Oracle object metadata, not hand-labeled topics. Source duplicates inside one parent's tag array are removed by construction.

| Distinct tags per parent | Parent count |
|---:|---:|
| 3 | 9,631 |
| 4 | 267 |
| 5 | 102 |
| **Total** | **10,000 parents; 30,471 memberships** |

Mongo A/C stores the same parents with `tags` arrays. SQL A/C uses `UC6_*_Parent` and `UC6_*_Tag` with a foreign key and `(PARENT_ID,TAG)` primary key. SQL C adds `(TAG,PARENT_ID)`; Mongo C adds `{tags:1}`, which [MongoDB 7.0 automatically treats as multikey](https://www.mongodb.com/docs/v7.0/core/indexes/index-types/index-multikey/). A retains necessary primary/`_id_` indexes. B is N/A for Mongo because an ordinary array-field index becomes multikey. SQL C is a relational access-path counterpart, not the same physical index type.

[Full-row parity](../results/uc6/accepted/uc6_corpus_parity.json) compared `PARENT_ID`, `SOURCE_ROW`, `OWNER`, `OBJECT_TYPE` and every tag against canonical JSONL for SQL seed/read A/read C and Mongo seed/read A/read C. Each copy had 10,000 parents, 30,471 memberships and zero mismatched parents. The [corpus manifest](../local_data/derived/uc6/manifest.json) records tag rules, lengths and expected query counts.

## Read workload and observed access

Each query projects complete parent IDs, with two warmups and 25 measured executions per A/C configuration. SQL times server-side JSON materialization; mongosh times full cursor consumption. These timing boundaries differ, so only within-engine comparisons are reported. The one-tag SQL query filters `TAG`; the two-tag SQL query filters both tags then groups by `PARENT_ID` with `HAVING COUNT(DISTINCT TAG)=2`. Mongo uses equality for one tag and `$all` for two. [The validated summary](../results/uc6/accepted/uc6_summary.json) checked the **complete sorted parent-ID list** for all eight cells per engine against the canonical expected-ID file.

| Query | Tags | Parents | SQL A → C median ms | Mongo A → C median ms |
|---|---|---:|---:|---:|
| `ONE_TABLE` | `type:TABLE` | 1,247 | 13.120 → 4.001 | 18.083 → 11.578 |
| `TWO_SYS_TABLE` | `owner:SYS`, `type:TABLE` | 1,125 | 16.659 → 11.694 | 21.728 → 13.074 |
| `ONE_TEMP_Y` | `temporary:Y` | 51 | 10.509 → 0.000* | 28.237 → 2.840 |
| `TWO_TABLE_TEMP_Y` | `type:TABLE`, `temporary:Y` | 41 | 10.853 → 2.014 | 28.530 → 2.061 |

*SQL `0.000 ms` is below the effective batch timer resolution, not zero work; no ratio is calculated for this cell. The other SQL median ratios are about 3.28×, 1.42× and 5.39×. Mongo ratios are about 1.56×, 1.66×, 9.94× and 13.85×. These are one local run's within-engine ratios on this derived categorical workload.

The [SQL diagnostic transcript](../results/uc6/plans/uc6_sql_diagnostics.txt) contains `STATISTICS IO/TIME` and eight actual ShowPlan XML documents. A plans scan the `(PARENT_ID,TAG)` clustered child key; C plans use `Index Seek` on `(TAG,PARENT_ID)`, followed by grouping. Mongo [eight explains](../results/uc6/PLAN_INDEX.csv) show A `COLLSCAN` with 10,000 documents examined. C has `isMultiKey:true` and `IXSCAN` followed by `FETCH`. For `TWO_SYS_TABLE`, C examined 1,247 keys and documents to return 1,125 parents: it bounded the index on `type:TABLE` and checked `owner:SYS` in `FETCH`. For `TWO_TABLE_TEMP_Y`, C examined 51 keys/documents to return 41. A two-tag `$all` result is therefore not proof that both tags were resolved by index intersection. SQL and Mongo have different physical work counters.

## Index and write costs

| Measure | SQL `(TAG,PARENT_ID)` | Mongo `{tags:1}` |
|---|---:|---:|
| Read-copy index build, one observation | 173.917 ms | 211.342 ms |
| Read-copy index footprint | 1,359,872 used bytes | 180,224 `indexSizes` bytes |
| INSERT throughput A → C, 10 × 20 copied real parents | 2,222 → 3,733 parents/s | 7,451 → 5,272 parents/s |
| Add one tag A → C median per 20 parents | 1.937 → 1.994 ms | 27.062 → 35.997 ms |

For a controlled membership mutation, the scripts added `probe:added` to 200 parents in write-only copies. Mongo used `$addToSet`; SQL inserted 200 child rows. This synthetic **write probe** is never part of the source corpus or read workload. SQL's insert throughput rose in this one run even with the extra index; batch ordering, page cache and noise prevent interpreting that as a maintenance benefit. Mongo C's lower insert throughput and higher tag-add median are observed index costs for this workload. SQL used page allocation counters; Mongo used `indexSizes`, which are different accounting conventions. The [SQL raw transcript](../results/uc6/accepted/uc6_sql_run.txt) and [Mongo JSONL](../results/uc6/accepted/uc6_mongo_run.jsonl) retain all samples and p95 values.

## Reproduce

From the workspace root, execute each engine's read timing separately:

```powershell
py -3.13 analysis/uc6_prepare.py
py -3.13 analysis/uc6_load_sql.py
mongoimport --db dbms_ew_group02 --collection uc6_seed_10k --file local_data/derived/uc6/parents_10k.jsonl --type json --stopOnError
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -i sql/uc6_normalized/uc6_setup.sql -o results/uc6/accepted/uc6_sql_setup.txt -y 0 -w 65535
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -i sql/uc6_normalized/uc6_run.sql -o results/uc6/accepted/uc6_sql_run.txt -y 0 -w 65535
mongosh --quiet --file mongo/uc6_multikey/uc6_run.js > results/uc6/accepted/uc6_mongo_run.jsonl
sqlcmd -S localhost -d DBMS_EW_Group02 -E -C -b -i sql/uc6_normalized/uc6_diagnostics.sql -o results/uc6/plans/uc6_sql_diagnostics.txt -y 0 -w 65535
py -3.13 analysis/uc6_verify.py
py -3.13 analysis/uc6_summarize.py
```

The scripts refuse pre-existing disposable copies. Save evidence, then run [SQL cleanup](../sql/uc6_normalized/uc6_cleanup.sql) and [Mongo cleanup](../mongo/uc6_multikey/uc6_cleanup.js) before rerunning. The current UC6 objects remain available for inspection. Original BIG_TABLE data and other UC results were not changed. [Microsoft's SQL `CREATE INDEX` documentation](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-index-transact-sql?view=sql-server-ver17) defines the relational rowstore index used here.
