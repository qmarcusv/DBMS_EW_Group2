# Group 02 indexing study dashboard

The Streamlit companion to `DBMS_Group2_report.pdf` and `Group02_EW_Presentation.pdf` has two English-language pages:

1. **Use cases and method** explains six workloads with node workflows for each index structure and query path, one source record per use case, representative SQL and MongoDB queries, one projected output record per query, metrics, and tradeoffs.
2. **Results and conclusions** starts with the report's six read and six index-cost summary tables and result graphics. It then shows six evidence-based verdicts, the complete accepted read and write tables, important counterexamples, and the final workload-based conclusion. The UC6 graphic is supplemental because it is generated from the accepted data but is not embedded in `main.pdf`.

From the `DBMS_EW_Group2` directory, run:

```powershell
py -3.13 -m streamlit run demo/app.py
```

The app reads the accepted Phase 8 review files. Before rendering either page, it checks the review status, the expected 128 read and 104 write cells, SHA-256 hashes of raw measurement sources, and the presence of 136 actual plan files. It does not run benchmarks or access a live database.

Timing comparisons are valid only within the same engine, scale, and query. Configuration B is a conventional indexed alternative where applicable; UC5 compares rowstore B with columnstore C and has no A. UC4 SQL substring and full-text queries return different ID sets, so their times are not a same-result speedup.

The example records come from the pinned derived CSV and JSONL corpora. UC4 query examples show a matching substring-scan A record; C may have a different result set. Summary cost tables contain the rounded display values printed in `main.pdf`. The complete comparison tables continue to read the accepted Phase 8 review files directly.
