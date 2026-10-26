# Benchmark results index

The old flat `results/raw/` directory was reorganized on 2026-10-25. **No original output file was deleted or edited.** `MANIFEST.csv` maps all 57 original files to their new locations, records their `decision` (`primary_measurement`, `primary_plan`, `supporting`, or `not_used_in_conclusions`), and includes byte lengths and SHA-256 hashes recorded before the move. `PLAN_INDEX.csv` maps 98 extracted, individually openable plans to their original transcripts. The transcripts remain authoritative; extracted plans are navigation copies.

## Directory rule

```text
results/
  phase2_smoke/{accepted,plans,archive}/
  uc1/{accepted,plans,archive}/
  uc2/{accepted,plans,archive}/
  uc3/{accepted,plans}/
  uc4/{eda,accepted,plans,archive}/    # UC4 corpus analysis and completed 10K benchmark
  uc5/{accepted,plans,archive}/
  uc6/{accepted,plans,archive}/     # optional multikey/normalized tag experiment
  shared/accepted/
  MANIFEST.csv
  PLAN_INDEX.csv
```

- `accepted/`: completed measurement, setup/cleanup and source postcheck outputs used by the phase report. A secondary successful SSMS run may be here too; the report specifies which run supplies its numeric table.
- `plans/`: complete SQL diagnostic transcript(s), derived `.sqlplan` files and derived Mongo `explain` JSON. SQL `.sqlplan` files can be opened in SSMS; Mongo JSON retains the source `READ_PLAN` record including `executionStats`.
- `archive/`: earlier attempts, superseded runs, truncated XML exports, zero-byte outputs and troubleshooting logs. These preserve provenance; **do not use them for benchmark conclusions**.
- `shared/`: one source postcheck used by UC3 and UC5.

The plan files were extracted from complete SQL `ShowPlanXML` elements and accepted Mongo JSONL records. Each SQL XML document was parsed before export. For UC2 the 20 SQL plans include 12 literal-query plans and eight parameter tests. Phase 2's one SQL plan came from the complete `sqlcmd` transcript; this does not establish that SSMS plan export was exercised.

## Results to use

| Study | SQL measurement | Mongo measurement | Plans | Report |
|---|---|---|---|---|
| Phase 2 smoke | [SQL smoke](phase2_smoke/accepted/phase2_sql_smoke.txt) | [Mongo smoke](phase2_smoke/accepted/phase2_mongo_smoke.jsonl) | [Plan folder](phase2_smoke/plans/) | [Phase 2](../reports/PHASE2_BENCHMARK_INFRASTRUCTURE.md) |
| UC1 compound | [SQL benchmark](uc1/accepted/phase3_uc1_sql_benchmark.txt) | [Mongo rerun](uc1/accepted/phase3_uc1_mongo_benchmark_rerun.jsonl) | [Plan folder](uc1/plans/) | [Phase 3](../reports/PHASE3_UC1_COMPOUND.md) |
| UC2 filtered/partial | [SQL v4](uc2/accepted/phase4_uc2_sql_run_v4.txt) | [Mongo run](uc2/accepted/phase4_uc2_mongo_run.jsonl) | [Plan folder](uc2/plans/) | [Phase 4](../reports/PHASE4_UC2_FILTERED_PARTIAL.md) |
| UC3 covering | [SQL run](uc3/accepted/phase5_uc3_sql_run.txt) | [Mongo run](uc3/accepted/phase5_uc3_mongo_run.jsonl) | [Plan folder](uc3/plans/) | [Phase 5](../reports/PHASE5_UC3_COVERING.md) |
| UC4 text search | [SQL run](uc4/accepted/uc4_sql_run.txt) | [Mongo run](uc4/accepted/uc4_mongo_run.jsonl) | [Plan folder](uc4/plans/) | [UC4 benchmark](../reports/UC4_FULL_TEXT_BENCHMARK.md) |
| UC5 columnstore | [SQL v2](uc5/accepted/phase6_uc5_sql_run_v2.txt) | N/A | [Plan folder](uc5/plans/) | [Phase 6](../reports/PHASE6_UC5_COLUMNSTORE.md) |
| UC6 multikey | [SQL run](uc6/accepted/uc6_sql_run.txt) | [Mongo run](uc6/accepted/uc6_mongo_run.jsonl) | [Plan index](uc6/PLAN_INDEX.csv) | [Phase 7](../reports/PHASE7_UC6_MULTIKEY.md) |

**UC1 specifics:** The user's [SSMS `run.rpt`](uc1/accepted/phase3_uc1_run.rpt) also ended in PASS, but Phase 3's numeric table uses `phase3_uc1_sql_benchmark.txt`. The user's [benchmark error `.rpt`](uc1/archive/phase3_uc1_benchmark.rpt), zero-byte outputs and truncated [diagnostics `.rpt`](uc1/archive/phase3_uc1_diagnostics.rpt) remain in `archive/`. The complete SQL plans are in `plans/`.

**UC2 specifics:** Some earlier SQL outputs ended in PASS while their workload definition was subsequently corrected. Only `phase4_uc2_sql_run_v4.txt` and `phase4_uc2_sql_diagnostics_v4.txt` support the reported SQL conclusions. See the [Phase 4 report](../reports/PHASE4_UC2_FILTERED_PARTIAL.md) for the correction history.

**UC5 specifics:** [The first run](uc5/archive/phase6_uc5_sql_run.txt) stopped at a script checksum check and was rerun after correction. Use `phase6_uc5_sql_run_v2.txt` for results.

**UC4 specifics:** [Validated summary](uc4/accepted/uc4_summary.json) compares all matched ID sets and p95 values. [Full-row parity](uc4/accepted/uc4_seed_parity.json) passed on 10,000 source rows and all four read copies. SQL's first benchmark script attempt had a syntax error and remains in `uc4/archive/`; the corrected run ended in `PASS`. UC4 was executed after the earlier Phase 6 UC5 experiment, so its folder name is the use case, not a renumbered phase.
[UC4 manifest](uc4/MANIFEST.csv) lists its 36 output files with hashes and evidence roles; [UC4 plan index](uc4/PLAN_INDEX.csv) maps all 24 individual plans to their source transcripts. The root `MANIFEST.csv` and `PLAN_INDEX.csv` remain the historical move/extraction inventories for earlier results.

**UC6 specifics:** [Corpus parity](uc6/accepted/uc6_corpus_parity.json) passed for all SQL/Mongo seed and read copies; [validated summary](uc6/accepted/uc6_summary.json) checked complete parent-ID sets for four one/two-tag queries. The [UC6 manifest](uc6/MANIFEST.csv) records output hashes. UC6 is the optional Phase 7 experiment on 10K derived categorical tags; it is separate from UC4's news-text corpus.

## Saving a new run

Choose the relevant UC directory and a **new filename** so a failed redirection cannot overwrite accepted evidence. Save benchmark output under `accepted/` only after checking its exit code, result parity and completion marker; otherwise put it in `archive/`. Save complete plan transcripts and individual `.sqlplan`/Mongo explain files under `plans/`. Add the new files to the index and update the phase report. Do not mix SQL and Mongo elapsed time as one directly comparable metric; their timing boundaries differ.
