# Unified LaTeX Report (`DBMS_EW_Group2`)

This directory contains the LaTeX sources for the CO3021 Database Management Systems report and presentation. The submission PDFs are at the repository root: `DBMS_Group2_report.pdf` and `Group02_EW_Presentation.pdf`.

## Structure of the V3 Report (5 Main Chapters + 1 Appendix)

- `main.tex`: Master report document (`\documentclass[a4paper,10pt,oneside]{report}`) with HCMUT cover page, continuous chapter layout, and running headers.
- `source/frontmatter/TeamContributions.tex`: Group 02 member roster and task contributions.
- `source/abstract/Abstract.tex`: Concise 3-paragraph summary of the workload-first methodology and key empirical findings.
- `source/chapters/01-introduction.tex`: **Chapter 1 — Introduction** (Assignment objectives and rubric, physical structures vs. indexing techniques vs. sparse/filtered indexes, and six-UC overview table).
- `source/chapters/02-background.tex` and `02-diagrams.tex`: **Chapter 2 — Use Cases and Indexing Solutions** (six access-path diagrams, one per use case).
- `source/chapters/03-methodology.tex`: **Chapter 3 — Datasets and Experimental Methodology** (Three verified datasets, key EDA distributions, representative records, A/B/C index configurations, 5 experimental fairness rules, and pre-benchmark expectations).
- `source/chapters/04-implementation.tex`: **Chapter 4 — Experimental Results** (experiment recaps, compact read tables, plan explanations, separate cost tables, and verdicts for UC1–UC6).
- `source/chapters/05-results.tex`: **Chapter 5 — Discussion and Conclusion** (course answers, four-column engineering guide, and limitations).
- `source/References/References.tex`: Official SQL Server 2025, MongoDB 7.0, and textbook bibliography.
- `source/chapters/06-conclusion.tex`: **Appendix A — Data Provenance, Artifact Manifest, and Reproduction Guide** (SHA-256 dataset checksums, script/evidence paths, build commands, and 3-part live demo plan).

## Build Commands

From the workspace root (`DBMS_EW_Group2`), using the checked-in figures:

```powershell
Push-Location report
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build presentation.tex
Copy-Item build/main.pdf ../DBMS_Group2_report.pdf -Force
Copy-Item build/presentation.pdf ../Group02_EW_Presentation.pdf -Force
Pop-Location
```

## Archived Report Versions

Historical build and archive directories are local-only and excluded from Git. The submitted PDFs and current LaTeX sources are tracked.
