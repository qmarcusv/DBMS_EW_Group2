# Native indexing structures in SQL Server and MongoDB

**Course:** CO3021 — Database Management Systems. **Project:** `EW_redo`. **Evidence cutoff:** 2026-10-25. This is the concise unified research narrative; the submission-style LaTeX version is in `report_simply/`. Every numeric claim below comes from the [Phase 8 accepted-evidence review](PHASE8_EVIDENCE_REVIEW.md) or a linked per-UC raw result. The older V1.1 Python simulation report is outside this project's evidence set.

## Research question and systems

How do modern indexing strategies change access paths, read latency, storage, build cost and writes for fixed workloads? The six studies cover compound B-tree, filtered/partial, covering, full-text, clustered columnstore and multikey/normalized membership. SQL Server 2025 build 17.0.1145.4 and MongoDB 7.0.12 were measured locally. UC5 is SQL-only. SQL Server and MongoDB use different timers, plan counters and storage accounting; this report compares each engine with its own baseline, never raw SQL milliseconds against raw Mongo milliseconds.

The main object-metadata corpus comes from the verified `BIG_TABLE_10K` CSV, SHA-256 `7f41f9d5a36b932a25101cc8929aad540a3f9f76ae68b5d434a221b7d6d4f116`, and its loaded 100K/1M scale copies. The [Phase 1 audit](PHASE1_DATA_AUDIT.md) describes schema and provenance limits. UC4 uses a separate [pinned news corpus](UC4_FULL_TEXT_BENCHMARK.md) because object identifiers are unsuitable as prose; UC6 uses deterministic categorical tags derived from the object-metadata CSV. Neither is an unrecorded extra column on the original BIG_TABLE.

## Experimental controls

Each UC created independent disposable read and write copies. A means no optional experiment index; B is a conventional alternative where meaningful; C is the target design. Primary keys and Mongo `_id_` remain. Read loops usually used two warmups and 25 measured samples, consumed complete projected results, and captured actual plans separately. The [review script](../analysis/phase8_review.py) recomputed median and p95 from 128 accepted read cells and parsed 136 plan files. The [write review](../analysis/phase8_write_review.py) checked 104 write cells. Per-UC scripts and [source hash inventory](../results/phase8/evidence_review.json) make each number traceable. These are single local runs, not repeated-machine confidence intervals.

## Findings by mechanism

| Mechanism and fixed query | Within-engine observed read change | Verified access/correctness | Important cost or limit |
|---|---|---|---|
| **UC1 compound**, 100K, `OWNER=SYS`, `OBJECT_TYPE=TABLE`, `OBJECT_ID=16` | SQL A 32.363 → C 9.458 ms; Mongo A 241.03 → C 2.34 ms | C follows leading compound keys for this query; result count 2 | SQL C did **not** seek for every query: U1b scanned; Mongo B scanned 71,802 SYS keys for U1a/b. [Phase 3](PHASE3_UC1_COMPOUND.md). |
| **UC2 filtered/partial**, 1M, qualifying Y | SQL A 92.318 → C 5.992 ms; Mongo A 2,418.94 → C 6.13 ms | C contains the Y subset; N selects scans in C | SQL C index 131,072 bytes versus B 45,867,008; Mongo C 53,248 versus B 12,525,568. N gains no indexed C path. [Phase 4](PHASE4_UC2_FILTERED_PARTIAL.md). |
| **UC3 covering**, 1M medium range | SQL A 113.925 → C 32.231 ms; Mongo A 2,579.41 → C 20.12 ms | SQL C plans remove RID Lookup; Mongo C examined zero base documents | C's 1M index size is 133,611,520 SQL used bytes and 70,098,944 Mongo index bytes; not every C median improved over B. [Phase 5](PHASE5_UC3_COVERING.md). |
| **UC4 full-text**, 10K news, `climate` | SQL substring A 3,983.54 ms; FTS C 17.40 ms, **different IDs**. Mongo regex A 299.96 → text C 6.41 ms, same IDs. | SQL A/C differ for all six UC4 queries; Mongo A/C match for five, but `election` differs due stemming | SQL full-text population 15.20 s, read catalog 13 logical MB; Mongo text index build 11.58 s, 26,411,008 index bytes. Do not call SQL A/C a same-result speedup. [UC4](UC4_FULL_TEXT_BENCHMARK.md). |
| **UC5 clustered columnstore**, SQL 1M aggregate | Heap B 123.203 → CCI C 42.438 ms | Both give 35 aggregate groups; C actual plan uses batch mode | Whole-copy used bytes 229,638,144 B versus 9,920,512 B; CCI build 22.29 s. This does not establish general point-query superiority. [Phase 6](PHASE6_UC5_COLUMNSTORE.md). |
| **UC6 multikey**, 10K, `type:TABLE` + `temporary:Y` | SQL A 10.853 → C 2.014 ms; Mongo A 28.530 → C 2.061 ms | Both engines return the same 41 complete parent IDs; Mongo C is multikey | SQL index 1,359,872 used bytes; Mongo 180,224 index bytes. Mongo C fetched 51 candidates before checking the second tag. [Phase 7](PHASE7_UC6_MULTIKEY.md). |

These selected queries illustrate different behaviors; the [128-cell table](../results/phase8/read_cases.csv) contains all medians, p95 values and source paths. For UC4, tokenization, stemming and substring matching differ. The [UC4 validated summary](../results/uc4/accepted/uc4_summary.json) shows complete A-only/C-only ID counts, so an attractive latency number is not promoted to a semantic speedup without equal results. The [UC6 summary](../results/uc6/accepted/uc6_summary.json) verifies complete parent IDs and array-length distribution.

## Costs, planning and limitations

An index is useful only when the predicate, key order, projection and selectivity align with the access path the optimizer chooses. UC1 U1b and U1c, UC2's N query, and Mongo UC6's two-tag `FETCH` demonstrate why the actual plan matters. UC3's covering index traded extra bytes for avoiding lookups. UC2's subset index saved storage but excluded N rows. UC5 compressed one 1M copy to about 1/23 of the heap used bytes, while its 20-row INSERT throughput fell from 13,265 to 6,642 rows/s in this run. UC4's English full-text/text indexes provide token/phrase behavior and cost far more to build than a simple lookup index; SQL `CHANGE_TRACKING=AUTO` took 5.80 s for one update to become searchable, versus one Mongo observation of 21.30 ms. One freshness probe is not a latency distribution.

Some update workloads locate target rows without a dedicated ID access path; their measured duration includes the search and data write, so it does not isolate index-maintenance overhead. SQL logical 8 KB page reads are not Mongo documents/keys examined. Mongo `indexSizes` and SQL used-page or full-text catalog measures are not directly exchangeable. SQL UC3/UC6 `0.000 ms` values mean below effective timer resolution and cannot form finite ratios. The optional 15M scale and UC6 100K extension were not run.

## Support and demonstration

Microsoft documents [rowstore `CREATE INDEX`](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-index-transact-sql?view=sql-server-ver17), [full-text population](https://learn.microsoft.com/en-us/sql/relational-databases/search/populate-full-text-indexes?view=sql-server-ver17), and [columnstore indexes](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/columnstore-indexes-overview?view=sql-server-ver17). MongoDB 7.0 documents [multikey indexes](https://www.mongodb.com/docs/v7.0/core/indexes/index-types/index-multikey/) and [text search](https://www.mongodb.com/docs/v7.0/reference/operator/query/text/). These describe mechanisms; captured plans establish what occurred in this run. Course lecture slides were not present locally, so no slide/page quotation is asserted.

The Streamlit demo in `demo/` reads only the accepted [Phase 8 review JSON](../results/phase8/evidence_review.json) and [write review](../results/phase8/write_cases.json). It shows within-engine charts, actual plan excerpts and source links, with UC4 result-set gates and SQL-only UC5 labels. For a live three-part presentation, UC1 can show compound key order, UC2 can show Y/N subset behavior, and UC3 can show lookup/FETCH elimination; UC4–UC6 remain available as additional evidence cards. The [results index](../results/README.md) distinguishes accepted output, plans and archived failures. No chart or fallback screenshot should use the archived V1.1 fixtures as `EW_redo` evidence.

## Rubric mapping

| Requirement | Evidence |
|---|---|
| What the indexes are | Mechanism descriptions in master plan and each UC report; official vendor references above |
| How both DBMSs support them | Native SQL/mongosh scripts, DDL/index definitions, 136 actual plans/explains, read/write/build/storage evidence; UC5 explicitly SQL-only |
| Reproducible demo | Isolated UC scripts and the evidence-backed Streamlit dashboard; plan/source links and three short UC1–UC3 storylines |
