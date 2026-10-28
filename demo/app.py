"""Two-page, evidence-backed companion to the Group 02 indexing presentation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import streamlit as st

from report_content import STORIES


ROOT = Path(__file__).resolve().parents[1]
READ_REVIEW = ROOT / "results/phase8/evidence_review.json"
WRITE_REVIEW = ROOT / "results/phase8/write_cases.json"
UC4_SUMMARY = ROOT / "results/uc4/accepted/uc4_summary.json"
PLAN_INDEXES = (
    ROOT / "results/PLAN_INDEX.csv",
    ROOT / "results/uc4/PLAN_INDEX.csv",
    ROOT / "results/uc6/PLAN_INDEX.csv",
)
ENGINES = {"SQL_SERVER": "SQL Server 2025", "MONGODB": "MongoDB 7.0"}

# The descriptions follow slides 5–29. Query text comes from the existing
# presentation companion; accepted measurements always come from Phase 8.
USE_CASES = {
    "uc1": {
        "title": "Compound B-tree",
        "workload": "Filter several catalog fields and sort by adjacent keys (100K rows).",
        "structure": "Ordered rowstore B-tree; compound key design.",
        "index": "C: (OWNER, OBJECT_TYPE, OBJECT_ID) in both engines; B: OWNER only.",
        "mechanism": "A matching leading prefix narrows the seek. Key order can eliminate a separate Sort.",
        "tradeoff": "Missing OWNER blocks a leading-key seek. A skewed OWNER-only index can fetch many rows; C uses more space and slows inserts.",
        "queries": {
            "U1a": "Full-key equality: SYS, TABLE, OBJECT_ID 16.",
            "U1b": "Two-key prefix: SYS and TABLE; 3,405 matches.",
            "U1c": "Missing leading OWNER: TABLE and OBJECT_ID 16.",
            "U1d": "CTXSYS filter, ordered by OBJECT_TYPE and OBJECT_ID.",
        },
    },
    "uc2": {
        "title": "Filtered / partial index",
        "workload": "Read a rare TEMPORARY='Y' subset (0.24% of 1M rows).",
        "structure": "Predicate-limited B-tree; SQL filtered index / MongoDB partial index.",
        "index": "B: full composite index; C: same access keys, restricted to Y rows.",
        "mechanism": "C stores only qualifying Y rows, reducing index pages and keys examined.",
        "tradeoff": "C cannot serve N queries. Parameterized SQL predicates need plan checks; the observed probes scanned.",
        "queries": {"Y": "TABLE, OBJECT_ID range 1–10,000, TEMPORARY='Y'.", "N": "Same range and type, but TEMPORARY='N'."},
    },
    "uc3": {
        "title": "Covering index",
        "workload": "Return ID, OWNER, OBJECT_NAME and OBJECT_TYPE for an OBJECT_ID range (100K / 1M).",
        "structure": "B-tree with included payload in SQL; compound projection keys in MongoDB.",
        "index": "B: narrow OBJECT_ID index; C: OBJECT_ID plus projected output fields.",
        "mechanism": "C returns projected fields from the index and removes SQL RID Lookup / MongoDB FETCH.",
        "tradeoff": "A wider index costs 5.94× SQL / 10.47× MongoDB space at 1M; small cached ranges may regress.",
        "queries": {"POINT": "One row: OBJECT_ID=16 and ID=1.", "SMALL": "Small OBJECT_ID range, 60–98 rows.", "MEDIUM": "Medium OBJECT_ID range, 1,694–2,775 rows."},
    },
    "uc4": {
        "title": "Full-text / text search",
        "workload": "Find words and phrases in 10K English news articles.",
        "structure": "Inverted token index, with posting lists rather than a conventional string B-tree.",
        "index": "A: SQL LIKE substring / MongoDB regex scan; C: SQL CONTAINS / MongoDB text index.",
        "mechanism": "Token lookup avoids scanning every article's characters.",
        "tradeoff": "Linguistic matching may return different IDs from substring matching. Build, writes and search visibility have costs.",
        "queries": {
            "K_HIGH": "Frequent keyword: election.", "K_MED": "Medium keyword: climate.",
            "K_LOW": "Rare keyword: bitcoin.", "P_HIGH": "Phrase: white house.",
            "P_MED": "Phrase: climate change.", "P_LOW": "Phrase: stock market.",
        },
    },
    "uc5": {
        "title": "Clustered columnstore",
        "workload": "Group 1M catalog rows by OBJECT_TYPE; SQL Server only.",
        "structure": "Compressed column segments, with batch-oriented scans.",
        "index": "B: rowstore heap; C: clustered columnstore. Configuration A does not apply.",
        "mechanism": "The aggregate reads compressed column segments; both measured aggregate plans used batch mode.",
        "tradeoff": "Small-batch inserts were slower. The unindexed point probe still scans rather than seeking an ID B-tree.",
        "queries": {"AGG": "GROUP BY OBJECT_TYPE with count and OBJECT_ID sum (35 groups).", "POINT": "Unindexed ID=1 point probe; a scan-control case."},
    },
    "uc6": {
        "title": "Multikey / tag-first child index",
        "workload": "Search 10K objects with 30,471 tag memberships.",
        "structure": "MongoDB array multikey B-tree; SQL normalized child table with a (TAG, PARENT_ID) B-tree.",
        "index": "A: no tag-first index; C: MongoDB tags multikey / SQL (TAG, PARENT_ID).",
        "mechanism": "One index entry per tag enables selective tag seeks.",
        "tradeoff": "Each tag adds index entries. MongoDB two-tag queries still FETCH candidates to test the second tag.",
        "queries": {
            "ONE_TABLE": "One common tag: type:TABLE.",
            "TWO_SYS_TABLE": "Two common tags: owner:SYS and type:TABLE.",
            "ONE_TEMP_Y": "One rare tag: temporary:Y.",
            "TWO_TABLE_TEMP_Y": "Two tags: type:TABLE and temporary:Y.",
        },
    },
}

VERDICTS = {
    "uc1": ("Conditional", "Aligned predicates win: Mongo U1a 241.03 → 2.34 ms. OWNER-only B is slower than A for skewed SYS; missing OWNER prevents a leading-key seek."),
    "uc2": ("Good for Y", "SQL Y 92.32 → 5.99 ms; Mongo Y 2,418.94 → 6.13 ms. The Y-only index saves over 99.5% versus B but N falls back to scans."),
    "uc3": ("Conditional", "Covering removes measured base lookups. SQL 1M medium B 49.78 → C 32.23 ms; Mongo 100K small B 2.83 → C 4.40 ms."),
    "uc4": ("Qualified", "Mongo climate returns the same IDs at 299.96 → 6.41 ms. SQL LIKE and CONTAINS differed on all six queries: no same-result speedup claim."),
    "uc5": ("Good for analytics", "SQL aggregate B 123.20 → C 42.44 ms; C used 23.15× less whole-copy space. Small-batch INSERT throughput nearly halved."),
    "uc6": ("Good for selective tags", "The 41-parent two-tag query: SQL 10.85 → 2.01 ms; Mongo 28.53 → 2.06 ms. Mongo still FETCHed 51 candidates."),
}

TAB_DECISIONS = {
    "uc1": "Use the compound index when filters include the leading OWNER key and align with the sort order.",
    "uc2": "Use the filtered or partial index for the stable, rare TEMPORARY='Y' workload.",
    "uc3": "Use the covering index when avoiding base-row lookups outweighs its larger storage cost.",
    "uc4": "Use full-text search for linguistic matching after checking that its result set fits the use case.",
    "uc5": "Use clustered columnstore for the measured scan and aggregate workload.",
    "uc6": "Use the tag-first index for selective tag membership searches.",
}

# One projected record per query, selected from the pinned derived corpora.
# UC4 examples are substring (A) matches; text-index (C) ID sets can differ.
QUERY_EXAMPLES = {
    "uc1": {
        "U1a": {"ID": 1, "OWNER": "SYS", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 16},
        "U1b": {"ID": 1, "OWNER": "SYS", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 16},
        "U1c": {"ID": 1, "OWNER": "SYS", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 16},
        "U1d": {"ID": 59588, "OWNER": "CTXSYS", "OBJECT_TYPE": "FUNCTION", "OBJECT_ID": 65317},
    },
    "uc2": {
        "Y": {"OBJECT_TYPE": "TABLE", "OBJECT_ID": 131, "TEMPORARY": "Y"},
        "N": {"OBJECT_TYPE": "TABLE", "OBJECT_ID": 16, "TEMPORARY": "N"},
    },
    "uc3": {
        "POINT": {"ID": 1, "OWNER": "SYS", "OBJECT_NAME": "TS$", "OBJECT_TYPE": "TABLE"},
        "SMALL": {"ID": 10, "OWNER": "SYS", "OBJECT_NAME": "I_OBJ#", "OBJECT_TYPE": "INDEX"},
        "MEDIUM": {"ID": 1, "OWNER": "SYS", "OBJECT_NAME": "TS$", "OBJECT_TYPE": "TABLE"},
    },
    "uc4": {
        "K_HIGH": {"DOC_ID": 2},
        "K_MED": {"DOC_ID": 141},
        "K_LOW": {"DOC_ID": 6931},
        "P_HIGH": {"DOC_ID": 35},
        "P_MED": {"DOC_ID": 141},
        "P_LOW": {"DOC_ID": 520},
    },
    "uc5": {
        "AGG": {"OBJECT_TYPE": "TABLE", "n": 35497, "s": 686768526},
        "POINT": {"ID": 1, "OWNER": "SYS", "OBJECT_NAME": "TS$", "OBJECT_TYPE": "TABLE"},
    },
    "uc6": {
        "ONE_TABLE": {"PARENT_ID": 1},
        "TWO_SYS_TABLE": {"PARENT_ID": 1},
        "ONE_TEMP_Y": {"PARENT_ID": 127},
        "TWO_TABLE_TEMP_Y": {"PARENT_ID": 127},
    },
}

SOURCE_RECORDS = {
    "uc1": {"ID": 1, "OWNER": "SYS", "OBJECT_NAME": "TS$", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 16, "TEMPORARY": "N"},
    "uc2": {"ID": 127, "OWNER": "SYS", "OBJECT_NAME": "EDITIONING_TYPES$", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 131, "TEMPORARY": "Y"},
    "uc3": {"ID": 1, "OWNER": "SYS", "OBJECT_NAME": "TS$", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 16},
    "uc4": {"DOC_ID": 141, "TITLE": "Hawaiians Had The Perfect Signs To Infuriate Trump When He Landed There", "BODY excerpt": "specially resonate on the islands: climate change, nuclear threats, racism pic.twi"},
    "uc5": {"ID": 1, "OWNER": "SYS", "OBJECT_NAME": "TS$", "OBJECT_TYPE": "TABLE", "OBJECT_ID": 16},
    "uc6": {"PARENT_ID": 127, "OWNER": "SYS", "OBJECT_TYPE": "TABLE", "tags": ["owner:SYS", "temporary:Y", "type:TABLE"]},
}

SAMPLE_SOURCES = {
    "uc1": "local_data/derived/BIG_TABLE_100K.csv",
    "uc2": "local_data/derived/BIG_TABLE_1000K.csv",
    "uc3": "local_data/derived/BIG_TABLE_1000K.csv",
    "uc4": "local_data/derived/uc4/corpus_10k.jsonl; substring A sample",
    "uc5": "local_data/derived/BIG_TABLE_1000K.csv; AGG computed over all 1M rows",
    "uc6": "local_data/derived/uc6/parents_10k.jsonl and expected_ids.json",
}

WORKFLOWS = {
    "uc1": (
        '''flowchart LR
          Q["Catalog query: WHERE plus ORDER BY"] --> K["Compound B-tree: OWNER, TYPE, ID"]
          K --> P{"Leading OWNER supplied?"}
          P -->|Yes| S["Narrow seek; ordered leaf walk"] --> R["Projected rows; Sort may disappear"]
          P -->|No| F["Index or table scan"] --> R''',
        '''flowchart LR
          A["U1a: SYS, TABLE, 16"] --> B["Locate matching key range"] --> C["Return 2 rows"]
          D["U1d: CTXSYS plus ORDER BY"] --> E["Read TYPE and ID in leaf order"] --> F["Return 398 sorted rows"]''',
    ),
    "uc2": (
        '''flowchart LR
          R["1M source rows"] --> B["Full B-tree B: all rows"]
          R --> P{"TEMPORARY = Y?"}
          P -->|Yes| C["Partial B-tree C: 2,405 rows"]
          P -->|No| X["Excluded from C"]''',
        '''flowchart LR
          Q["Dashboard asks for TABLE in ID range"] --> P{"Flag value?"}
          P -->|Y| S["Seek Y-only C"] --> Y["615 matching rows at 1M"]
          P -->|N| F["C cannot answer; scan or use B"] --> N["15,810 matching rows at 1M"]''',
    ),
    "uc3": (
        '''flowchart LR
          Q["OBJECT_ID range"] --> B["Narrow B: key and row pointer"] --> L["RID Lookup or FETCH per match"] --> R["Four output columns"]
          Q --> C["Covering C: key and output columns"] --> R''',
        '''flowchart LR
          Q["Medium range query"] --> P["Find 1,694 or 2,775 rows"]
          P --> B["B may fetch base rows or scan table"]
          P --> C["C reads projected fields in index"]
          B --> R["Result"]
          C --> R''',
    ),
    "uc4": (
        '''flowchart LR
          D["Article BODY"] --> T["Tokenize and normalize"] --> P["Inverted token postings"] --> I["Candidate document IDs"]
          I --> V["Phrase verification when needed"]''',
        '''flowchart LR
          Q["Word or phrase query"] --> A["A: substring or regex scan"] --> X["Substring ID set"]
          Q --> C["C: token index lookup"] --> Y["Linguistic ID set"]
          X --> G{"Same complete IDs?"}
          Y --> G
          G -->|No| N["Do not claim same-result speedup"]''',
    ),
    "uc5": (
        '''flowchart LR
          R["Rowstore B: 14 fields per row"] --> S["Scan full rows"]
          C["Columnstore C: compressed TYPE and ID segments"] --> A["Read needed segments"] --> G["GROUP BY TYPE; SUM ID"]
          S --> G''',
        '''flowchart LR
          Q["1M-row GROUP BY query"] --> B["B: heap scan"] --> R["35 result groups"]
          Q --> C["C: compressed column scan"] --> R
          P["ID = 1 probe"] --> X["No ID B-tree: still a scan"]''',
    ),
    "uc6": (
        '''flowchart LR
          D["One parent with 3 to 5 tags"] --> M["Mongo multikey: one entry per tag"]
          D --> S["SQL child rows: one row per tag"]
          M --> I["tags key seek"]
          S --> K["TAG, PARENT_ID key seek"]''',
        '''flowchart LR
          Q["Find TABLE plus TEMP Y"] --> I["Seek selective TEMP Y tag: 51 candidates"]
          I --> F["Mongo FETCH checks TABLE tag"] --> R["41 parent IDs"]
          Q --> S["SQL two tag seeks and grouping"] --> R''',
    ),
}

# Tables 4.2, 4.4, 4.6, 4.8, 4.10 and 4.12 in DBMS_Group2_report.pdf.
# These are the report's rounded display values, not newly measured runs.
PDF_COST_TABLES = {
    "uc1": [
        {"Engine": "SQL", "Index": "A: none", "Size (MiB)": 0, "Build (ms)": 0, "INSERT (rows/s)": 6148},
        {"Engine": "SQL", "Index": "B: owner", "Size (MiB)": 2.64, "Build (ms)": 236, "INSERT (rows/s)": 17698},
        {"Engine": "SQL", "Index": "C: compound", "Size (MiB)": 5.19, "Build (ms)": 1969, "INSERT (rows/s)": 18393},
        {"Engine": "Mongo", "Index": "A: none", "Size (MiB)": 0, "Build (ms)": 0, "INSERT (rows/s)": 39368},
        {"Engine": "Mongo", "Index": "B: owner", "Size (MiB)": 0.48, "Build (ms)": 879, "INSERT (rows/s)": 28438},
        {"Engine": "Mongo", "Index": "C: compound", "Size (MiB)": 0.90, "Build (ms)": 931, "INSERT (rows/s)": 26191},
    ],
    "uc2": [
        {"Engine / scale": "SQL 100K", "Config": "B", "Size (MiB)": 4.46, "Build (ms)": 197.5, "N insert p50 (ms)": 1.48, "Y insert p50 (ms)": 1.95},
        {"Engine / scale": "SQL 100K", "Config": "C", "Size (MiB)": 0.05, "Build (ms)": 29.3, "N insert p50 (ms)": 1.11, "Y insert p50 (ms)": 1.90},
        {"Engine / scale": "SQL 1M", "Config": "B", "Size (MiB)": 43.74, "Build (ms)": 1741.4, "N insert p50 (ms)": 2.02, "Y insert p50 (ms)": 1.99},
        {"Engine / scale": "SQL 1M", "Config": "C", "Size (MiB)": 0.13, "Build (ms)": 179.3, "N insert p50 (ms)": 1.02, "Y insert p50 (ms)": 1.11},
        {"Engine / scale": "Mongo 100K", "Config": "B", "Size (MiB)": 1.19, "Build (ms)": 1076, "N insert p50 (ms)": 2.96, "Y insert p50 (ms)": 2.63},
        {"Engine / scale": "Mongo 100K", "Config": "C", "Size (MiB)": 0.02, "Build (ms)": 270, "N insert p50 (ms)": 1.43, "Y insert p50 (ms)": 3.06},
        {"Engine / scale": "Mongo 1M", "Config": "B", "Size (MiB)": 11.95, "Build (ms)": 9967, "N insert p50 (ms)": 2.13, "Y insert p50 (ms)": 1.83},
        {"Engine / scale": "Mongo 1M", "Config": "C", "Size (MiB)": 0.05, "Build (ms)": 2947, "N insert p50 (ms)": 1.80, "Y insert p50 (ms)": 2.38},
    ],
    "uc3": [
        {"Engine / scale": "SQL 100K", "Config": "B", "Size (MiB)": 2.27, "Build (ms)": 118, "INSERT (rows/s)": 3694},
        {"Engine / scale": "SQL 100K", "Config": "C", "Size (MiB)": 12.45, "Build (ms)": 260, "INSERT (rows/s)": 3888},
        {"Engine / scale": "SQL 1M", "Config": "B", "Size (MiB)": 21.46, "Build (ms)": 1510, "INSERT (rows/s)": 5813},
        {"Engine / scale": "SQL 1M", "Config": "C", "Size (MiB)": 127.42, "Build (ms)": 1250, "INSERT (rows/s)": 5230},
        {"Engine / scale": "Mongo 100K", "Config": "B", "Size (MiB)": 0.82, "Build (ms)": 801, "INSERT (rows/s)": 4472},
        {"Engine / scale": "Mongo 100K", "Config": "C", "Size (MiB)": 6.66, "Build (ms)": 892, "INSERT (rows/s)": 4077},
        {"Engine / scale": "Mongo 1M", "Config": "B", "Size (MiB)": 6.39, "Build (ms)": 10363, "INSERT (rows/s)": 2190},
        {"Engine / scale": "Mongo 1M", "Config": "C", "Size (MiB)": 66.85, "Build (ms)": 13702, "INSERT (rows/s)": 2928},
    ],
    "uc4": [
        {"Engine": "SQL", "Config": "A: PK only", "Reported size": 0, "Build (s)": 0, "INSERT (rows/s)": 4574, "UPDATE p50 (ms)": 2.99},
        {"Engine": "SQL", "Config": "C: full-text", "Reported size": 13.0, "Build (s)": 15.20, "INSERT (rows/s)": 3362, "UPDATE p50 (ms)": 3.00},
        {"Engine": "Mongo", "Config": "A: PK only", "Reported size": 0, "Build (s)": 0, "INSERT (rows/s)": 2538, "UPDATE p50 (ms)": 38.71},
        {"Engine": "Mongo", "Config": "C: text", "Reported size": 25.19, "Build (s)": 11.58, "INSERT (rows/s)": 119, "UPDATE p50 (ms)": 115.47},
    ],
    "uc5": [
        {"Layout": "B: rowstore heap", "Used space (MiB)": 219.00, "Build (s)": 0, "INSERT (rows/s)": 13265, "UPDATE p50 (ms)": 154.44},
        {"Layout": "C: clustered columnstore", "Used space (MiB)": 9.46, "Build (s)": 22.29, "INSERT (rows/s)": 6642, "UPDATE p50 (ms)": 34.51},
    ],
    "uc6": [
        {"Engine": "SQL", "Config": "A: child PK", "Size (MiB)": 0, "Build (ms)": 0, "INSERT (parents/s)": 2222, "Add tag p50 (ms)": 1.94},
        {"Engine": "SQL", "Config": "C: TAG, parent", "Size (MiB)": 1.30, "Build (ms)": 173.9, "INSERT (parents/s)": 3733, "Add tag p50 (ms)": 1.99},
        {"Engine": "Mongo", "Config": "A: no tag index", "Size (MiB)": 0, "Build (ms)": 0, "INSERT (parents/s)": 7451, "Add tag p50 (ms)": 27.06},
        {"Engine": "Mongo", "Config": "C: multikey", "Size (MiB)": 0.17, "Build (ms)": 211.3, "INSERT (parents/s)": 5272, "Add tag p50 (ms)": 36.00},
    ],
}

PDF_FIGURES = {
    "uc1": "Compound index latency across four query shapes",
    "uc2": "Rare-subset latency and index storage",
    "uc3": "Medium-range latency and covering-index storage",
    "uc4": "Equal-result MongoDB text latency and write throughput",
    "uc5": "Rowstore versus columnstore storage and latency",
    "uc6": "Supplemental UC6 chart generated from the same accepted measurements; not embedded in DBMS_Group2_report.pdf",
}

PDF_TABLE_NOTES = {
    "uc1": "SQL A INSERT ran first and incurred initial file growth; its throughput is not a clean index-maintenance baseline.",
    "uc2": "B is a full index and C contains only Y rows. Insert p50 is per 20-row batch.",
    "uc3": "Coverage removed lookups in measured plans, but C is much wider. INSERT rates do not isolate maintenance cost.",
    "uc4": "SQL reported size is catalog logical MB; MongoDB size is MiB of index bytes. These are not directly comparable. SQL build includes background population.",
    "uc5": "Whole-copy space is measured here. UPDATE includes locating rows without an ID index.",
    "uc6": "SQL A retains the child primary key. MongoDB A retains the default _id index. SQL INSERT rates are not interpreted as an indexing gain.",
}

PDF_WORK_NOTES = {
    "uc1": "U1a in C: SQL 5 logical page reads; MongoDB 2 documents examined. U1b in SQL still scans 2,730 pages.",
    "uc2": "At 1M, Y in C: SQL 6 logical page reads; MongoDB 616 keys. N in C falls back to a full scan.",
    "uc3": "Medium range in C: SQL 1M reads 49 index pages; MongoDB 1M examines zero base documents.",
    "uc4": "SQL A scans 7,960 pages; C uses FulltextMatch. SQL A/C IDs differ for all six searches; MongoDB election also differs.",
    "uc5": "The aggregate in C recorded 1,105 LOB reads and batch mode; B recorded 28,032 logical page reads. Those are different counter types.",
    "uc6": "For TABLE plus TEMP Y, MongoDB C seeks 51 tag entries, FETCHes 51 candidates and returns 41 parents.",
}


@st.cache_data(show_spinner=False, max_entries=1)
def load_verified() -> dict:
    """Read only accepted evidence and stop if any audited input has changed."""
    required = (READ_REVIEW, WRITE_REVIEW, UC4_SUMMARY, *PLAN_INDEXES)
    missing = [p for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing evidence: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))

    review = json.loads(READ_REVIEW.read_text(encoding="utf-8"))
    writes = json.loads(WRITE_REVIEW.read_text(encoding="utf-8"))
    if review.get("status") != "PASS" or writes.get("status") != "PASS":
        raise ValueError("Phase 8 read/write review has not passed")
    if len(review.get("cases", [])) != 128 or len(writes.get("cases", [])) != 104:
        raise ValueError("Expected 128 accepted read cells and 104 accepted write cells")

    for relative, expected in review["sources"].items():
        source = ROOT / relative
        if not source.is_file() or source.stat().st_size != expected["bytes"]:
            raise ValueError(f"Missing or changed measurement source: {relative}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError(f"SHA-256 mismatch for measurement source: {relative}")

    plans = []
    for index in PLAN_INDEXES:
        with index.open(encoding="utf-8-sig", newline="") as stream:
            plans.extend(row for row in csv.DictReader(stream) if row["group"] in USE_CASES)
    if len(plans) != 136:
        raise ValueError(f"Expected 136 plans, found {len(plans)}")
    for plan in plans:
        if not (ROOT / plan["plan_path"]).is_file():
            raise FileNotFoundError(f"Missing actual plan: {plan['plan_path']}")
    return {"read": review["cases"], "write": writes["cases"], "plans": plans, "sources": review["sources"]}


def render_study() -> None:
    st.title("Use cases and index design")
    st.caption("Group 02 · SQL Server 2025 and MongoDB 7.0")
    st.markdown(
        "Six workloads motivate six index choices.\n\n"
        "- **A:** No optional experiment index.\n"
        "- **B:** Conventional indexed alternative, where applicable.\n"
        "- **C:** Workload-targeted design.\n\n"
        "UC5 compares rowstore B with columnstore C. UC4 and UC6 have no B."
    )

    st.subheader("What was measured")
    st.dataframe(
        [
            {"Metric": "Read latency ↓", "Measure": "Median (p50) and p95 in ms; 2 warmups and 25 timed runs", "Interpretation": "Lower is faster within the same engine."},
            {"Metric": "Physical work ↓", "Measure": "SQL logical 8 KB page reads; MongoDB keys and documents examined", "Interpretation": "Lower work is preferable for the same result; units differ across engines."},
            {"Metric": "Actual plan", "Measure": "Seek, scan, sort, lookup, IXSCAN, FETCH, batch mode", "Interpretation": "An index being present does not prove it was chosen."},
            {"Metric": "Index / copy size ↓", "Measure": "Storage used by the index or whole copy", "Interpretation": "Lower storage cost is preferable for the same workload."},
            {"Metric": "Build time ↓", "Measure": "Time to create the index", "Interpretation": "Lower build cost is preferable."},
            {"Metric": "INSERT throughput ↑", "Measure": "Inserted rows or parents per second", "Interpretation": "Higher throughput is preferable."},
            {"Metric": "Write latency ↓", "Measure": "INSERT or UPDATE p50 duration", "Interpretation": "Lower duration is preferable; UPDATE may include locating a row."},
            {"Metric": "Result parity", "Measure": "Counts and complete IDs where needed", "Interpretation": "Different results cannot support a same-result speedup."},
        ],
        hide_index=True,
        alt="Measurement definitions and interpretation rules",
    )

    st.subheader("Workload map")
    st.dataframe(
        [{"Use case": key.upper(), "Query need": case["workload"], "Index C": case["title"], "Structure": case["structure"]}
         for key, case in USE_CASES.items()],
        hide_index=True,
        alt="Six workloads, target indexes, and underlying structures",
    )
    st.mermaid_chart(
        '''flowchart LR
          Q["Measured workload"] --> T{"Access need"}
          T -->|"Keys, subset, projection, tags"| B["B-tree design: UC1, UC2, UC3, UC6"]
          T -->|"Words and phrases"| I["Inverted postings: UC4"]
          T -->|"Few-column aggregation"| C["Compressed column segments: UC5"]
          B --> P["Check actual plan and total cost"]
          I --> P
          C --> P''',
        alt="Query needs lead to B-tree designs, inverted postings, or column segments before plan and cost checks",
    )

    st.subheader("Queries, access paths, and tradeoffs")
    for key, case in USE_CASES.items():
        with st.expander(f"{key.upper()} · {case['title']}", expanded=key == "uc1"):
            st.markdown(f"**Problem.** {case['workload']}")
            st.markdown(f"**Structure and index.** {case['structure']} {case['index']}")
            st.markdown(f"**Why it can help.** {case['mechanism']}")
            st.markdown("**One source record**")
            st.code(json.dumps(SOURCE_RECORDS[key], ensure_ascii=False, indent=2), language="json")
            st.markdown("**Index structure workflow**")
            st.mermaid_chart(WORKFLOWS[key][0], alt=f"{key.upper()} index structure and physical access path")
            st.markdown("**Use case workflow**")
            st.mermaid_chart(WORKFLOWS[key][1], alt=f"{key.upper()} query path from predicate to result")
            st.dataframe(
                [{"Query": query, "Question tested": description} for query, description in case["queries"].items()],
                hide_index=True,
                alt=f"{key.upper()} representative queries and what each tests",
            )
            with st.expander("Queries and one example result per query"):
                for query in case["queries"]:
                    source = STORIES[key]["queries"][query]
                    st.markdown(f"**{query}: {case['queries'][query]}**")
                    st.caption("SQL Server query")
                    st.code(source["sql"], language="sql")
                    if key != "uc5":
                        st.caption("MongoDB query")
                        st.code(source["mongo"], language="javascript")
                    st.caption("One expected output record from the pinned source corpus")
                    st.code(json.dumps(QUERY_EXAMPLES[key][query], ensure_ascii=False, indent=2), language="json")
                st.caption(f"Example source: {SAMPLE_SOURCES[key]}. These are sample records, not timed benchmark outputs.")
                if key == "uc4":
                    st.caption("UC4 examples match substring scan A. Full-text C may return a different ID set.")
            st.markdown(f"**Tradeoff.** {case['tradeoff']}")


def read_table(cases: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for cell in cases:
        key = (cell["uc"], cell["engine"], cell["scale"], cell["query_id"])
        row = grouped.setdefault(key, {
            "Use case": cell["uc"].upper(), "Engine": ENGINES[cell["engine"]],
            "Scale": cell["scale"], "Query": cell["query_id"],
            "Same results A/C": "N/A" if cell["uc"] == "uc5" else ("Yes" if cell["semantic_parity"] else "No"),
            "A rows": None, "B rows": None, "C rows": None,
            "A p50 ms": None, "B p50 ms": None, "C p50 ms": None,
            "A p95 ms": None, "B p95 ms": None, "C p95 ms": None,
        })
        row[f"{cell['config']} rows"] = cell["matched_rows"]
        row[f"{cell['config']} p50 ms"] = round(cell["median_ms"], 3)
        row[f"{cell['config']} p95 ms"] = round(cell["p95_ms"], 3)
        if cell["uc"] != "uc5" and not cell["semantic_parity"]:
            row["Same results A/C"] = "No"
    return [grouped[key] for key in sorted(grouped)]


def write_table(cases: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for cell in cases:
        key = (cell["uc"], cell["engine"], cell.get("scale", ""), cell["kind"])
        row = grouped.setdefault(key, {
            "Use case": cell["uc"].upper(), "Engine": ENGINES[cell["engine"]],
            "Scale": cell.get("scale", ""), "Operation": cell["kind"],
            "A p50 ms": None, "B p50 ms": None, "C p50 ms": None,
            "A rows/s": None, "B rows/s": None, "C rows/s": None,
        })
        row[f"{cell['config']} p50 ms"] = round(cell["median_ms"], 3)
        if cell.get("rows_per_second") is not None:
            row[f"{cell['config']} rows/s"] = round(cell["rows_per_second"])
    return [grouped[key] for key in sorted(grouped)]


def show_metric_directions(rows: list[dict]) -> list[dict]:
    """Add interpretation arrows to displayed metric headers without changing evidence keys."""
    lower = {"Size (MiB)", "Used space (MiB)", "Reported size", "Build (ms)", "Build (s)"}
    upper = {"INSERT (rows/s)", "INSERT (parents/s)"}

    def label(key: str) -> str:
        if key in lower or key.endswith((" p50 ms", " p95 ms", " p50 (ms)")):
            return f"{key} ↓"
        if key in upper or key.endswith(" rows/s"):
            return f"{key} ↑"
        return key

    return [{label(key): value for key, value in row.items()} for row in rows]


def render_results(bundle: dict) -> None:
    st.title("Results and conclusions")
    st.caption("Group 02")
    st.markdown(
        "**How to read the tables**\n\n"
        "- **Latency ↓:** Lower is better. **INSERT throughput ↑:** Higher is better.\n"
        "- Compare A, B and C only within the same engine, scale and query.\n"
        "- B is an indexed alternative and is not always the baseline.\n"
        "- UC5 has no A. SQL and MongoDB timing boundaries differ."
    )

    st.subheader("Figures and summary tables from the report")
    st.markdown(
        "Source: **DBMS_Group2_report.pdf**\n\n"
        "- UC1–UC5 charts reproduce Figures 4.1–4.5; the UC6 chart is supplemental.\n"
        "- Read tables summarize Tables 4.1, 4.3, 4.5, 4.7, 4.9 and 4.11, "
        "with p95 and result counts added from accepted evidence.\n"
        "- Cost tables reproduce Tables 4.2, 4.4, 4.6, 4.8, 4.10 and 4.12.\n"
        "- Values are rounded for display."
    )
    report_tabs = st.tabs([f"{key.upper()} · {case['title']}" for key, case in USE_CASES.items()])
    all_reads = read_table(bundle["read"])
    for (key, case), tab in zip(USE_CASES.items(), report_tabs):
        with tab:
            figure = ROOT / "demo/assets" / f"{key}_diagram.png"
            st.image(figure, width="stretch", caption=PDF_FIGURES[key], alt=PDF_FIGURES[key])
            st.markdown("**Read outcomes (report Table 4." + str(2 * int(key[-1]) - 1) + ")**")
            st.dataframe(
                show_metric_directions([row for row in all_reads if row["Use case"] == key.upper()]),
                hide_index=True,
                alt=f"{key.upper()} accepted read medians, tail latencies, result counts and parity",
            )
            st.caption(f"Physical work and plan: {PDF_WORK_NOTES[key]}")
            st.markdown("**Index cost (report Table 4." + str(2 * int(key[-1])) + ")**")
            st.dataframe(show_metric_directions(PDF_COST_TABLES[key]), hide_index=True, alt=f"{key.upper()} report index cost table")
            st.caption(PDF_TABLE_NOTES[key])
            st.markdown(f"**Conclusion — {key.upper()}**")
            st.markdown(
                f"- **Decision:** {TAB_DECISIONS[key]}\n"
                f"- **Measured evidence:** {VERDICTS[key][1]}\n"
                f"- **Trade-off:** {case['tradeoff']}"
            )

    st.subheader("What the six experiments show")
    st.dataframe(
        [{"Use case": key.upper(), "Target index": USE_CASES[key]["title"],
          "Verdict": verdict, "Evidence and limitation": finding}
         for key, (verdict, finding) in VERDICTS.items()],
        hide_index=True,
        alt="Six evidence-based index verdicts with gains and limitations",
    )

    st.subheader("Complete read comparison")
    st.caption("All 128 accepted read cells are grouped by engine, scale and query. A/B/C columns show p50 and p95 in milliseconds. A reported 0.000 ms is below timer resolution and must not be used as a speedup divisor.")
    st.dataframe(show_metric_directions(all_reads), hide_index=True, alt="Accepted A B C read latency comparison for all measured queries")
    st.markdown(
        "**Reading the exceptions:** UC1 Mongo U1a's OWNER-only B is slower than A (462.78 vs 241.03 ms). "
        "UC2 N is excluded from the Y-only C index. UC3 Mongo 100K small is slower under C than B "
        "(4.40 vs 2.83 ms). UC4 SQL A/C do not return identical IDs; Mongo election also differs. "
        "These cases prevent a blanket claim that every index improves every query."
    )

    st.subheader("Write cost comparison")
    st.caption("All 104 accepted write cells are grouped by operation. UPDATE duration can include locating an unindexed row, so it is not an isolated measure of index maintenance.")
    st.dataframe(show_metric_directions(write_table(bundle["write"])), hide_index=True, alt="Accepted A B C write latency and insert throughput comparison")

    st.subheader("Conclusion")
    st.markdown(
        "- **Overall:** An index helps its intended workload when predicate selectivity, key order and "
        "projected columns match the measured access path.\n"
        "- **UC1–UC3:** Compound keys help aligned filters and sorting; filtered indexes fit stable rare "
        "subsets; covering indexes help ranges that would otherwise need lookups.\n"
        "- **UC4–UC6:** Inverted indexes serve linguistic search; columnstore suits scans and aggregates; "
        "tag-first indexes help selective membership.\n"
        "- **Trade-offs:** Unmatched predicates may scan, wider indexes use more storage and can slow writes, "
        "and full-text search may change the result set.\n"
    )
    st.markdown(
        f"- **Evidence check:** {len(bundle['read'])} read cells, {len(bundle['write'])} write cells, "
        f"{len(bundle['plans'])} actual plans and {len(bundle['sources'])} hash-checked source files.\n"
        "- **Sources:** `results/phase8/evidence_review.json` and `results/phase8/write_cases.json`."
    )


def main() -> None:
    st.set_page_config(page_title="DBMS indexing study · Group 02", layout="wide")
    with st.sidebar:
        st.title("DBMS indexing study")
        st.caption("Group 02 · SQL Server 2025 · MongoDB 7.0")
        page = st.radio("Page", ("Use cases and method", "Results and conclusions"))
        # st.caption("Presentation: slides 5–29 · Accepted Phase 8 evidence")

    try:
        bundle = load_verified()
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Evidence integrity check failed: {exc}")
        st.stop()

    if page == "Use cases and method":
        render_study()
    else:
        render_results(bundle)


if __name__ == "__main__":
    main()
