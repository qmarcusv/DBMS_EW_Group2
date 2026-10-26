# Phase 8 — accepted-evidence review before report and demo

**Date:** 2026-10-25. **Decision:** `PASS` for using the accepted UC1–UC6 result files in the new report and Streamlit demo, subject to the interpretation limits below. This review did not rerun a benchmark or mutate a database. It excludes the older V1.1 Python/native report and demo corpus.

The [read audit script](../analysis/phase8_review.py) re-read the selected raw SQL transcripts and Mongo JSONL, checked each completion marker, sample sequence and result count, recalculated every median and p95 from raw samples, and verified 136 indexed plan files parse and exist. Its [machine-readable review](../results/phase8/evidence_review.json) contains 128 read cells, input SHA-256 values and source paths; [CSV](../results/phase8/read_cases.csv) is the chart feed. For UC1–UC3 it checked cross-engine result **counts**, not cross-engine complete ID equality. The [write audit](../analysis/phase8_write_review.py) checked 104 write cells, sample counts, median/p95, affected rows and insert throughput where applicable; [JSON](../results/phase8/write_cases.json) and [CSV](../results/phase8/write_cases.csv) are the write chart feeds.

| Use case | Accepted run and method checked | Read cells | Plan files | Review outcome |
|---|---|---:|---:|---|
| UC1 compound | SQL benchmark + Mongo rerun; 100K | 24 | 24 | PASS; U1b SQL C still scans, U1c lacks leading key |
| UC2 filtered/partial | SQL **v4** + Mongo run; 100K/1M | 24 | 32 | PASS; C helps Y, cannot serve N as an indexed subset |
| UC3 covering | SQL/Mongo runs; 100K/1M | 36 | 36 | PASS; C coverage observed, with sub-ms SQL timer limits |
| UC4 full-text | Native SQL/Mongo 10K news corpus | 24 | 24 | PASS; SQL A/C differ in ID set for all six queries; Mongo differs for `election` |
| UC5 columnstore | SQL **v2**; 1M | 4 | 4 | PASS; SQL-only physical-layout comparison |
| UC6 multikey | Native SQL/Mongo 10K derived tags | 16 | 16 | PASS; complete parent/tag and query ID parity |
| **Total** | | **128** | **136** | **104 write cells also checked** |

UC4's [full-row parity](../results/uc4/accepted/uc4_seed_parity.json) checks the 10K news corpus and all four read copies. UC6's [full-row parity](../results/uc6/accepted/uc6_corpus_parity.json) checks all 10K parents and 30,471 memberships across six seed/read snapshots. Their [validated UC4](../results/uc4/accepted/uc4_summary.json) and [UC6 summaries](../results/uc6/accepted/uc6_summary.json) compare complete result-ID lists. For UC1–UC3, the native scripts checked query-level counts and fingerprints within each engine; this Phase 8 audit does not claim a new row-by-row cross-engine proof for those earlier studies.

## Rules applied to the report and demo

- Show comparisons **within one DBMS and one query/scale**. SQL server-side batch timing and mongosh cursor timing differ. SQL logical reads, Mongo keys/documents examined and SQL catalog/index bytes are separate units.
- Label C as a faster same-result configuration only when IDs or the experiment's recorded result proof match. UC4 SQL substring versus token/phrase results differ; use latency and correctness panels, with no same-result speedup. Five Mongo UC4 A/C queries have equal IDs; `election` does not.
- Treat SQL UC3/UC6 `0.000 ms` cells as below timer resolution; display `N/A` for a ratio with zero denominator. Small changes and p95 estimates from one local run are descriptive, not a general guarantee.
- Keep UC5 SQL-only. Its 1M rowstore/columnstore comparison cannot be paired with a Mongo columnstore result. UC6 is a derived categorical-tag experiment; `probe:added` appears only in independent write copies.
- Phase 2 smoke infrastructure retains its earlier `PARTIAL` status because SSMS UI and some helper paths were not exercised there. Subsequent UC native runs are individually accepted; Phase 2's status is not silently upgraded.
- The older `report_simply` and `demo` assets belong to a V1.1 scenario suite. They are excluded from this evidence review and must not feed the new charts.

The report should cite the per-UC documents and actual artifacts by path. Course lecture slides were not present in this workspace at review time, so no exact slide/page attribution is asserted; official DBMS documentation supports the mechanism descriptions.
