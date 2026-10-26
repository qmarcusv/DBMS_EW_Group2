"""Validate accepted UC4 transcripts, compare ID sets, and extract plans.

Run after both UC4 benchmarks: py -3.13 analysis/uc4_summarize.py
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / "results/uc4/accepted"
PLANS = ROOT / "results/uc4/plans"
QUERIES = ("K_HIGH", "K_MED", "K_LOW", "P_HIGH", "P_MED", "P_LOW")


def main():
    sql_text = (ACCEPTED / "uc4_sql_run.txt").read_text(encoding="utf-8-sig")
    if "RUN_COMPLETE PASS" not in sql_text:
        raise ValueError("SQL run incomplete")
    sql_ids, sql_read, sql_write, sql_raw, sql_write_raw = {}, {}, {}, {}, {}
    for line in sql_text.splitlines():
        m = re.fullmatch(r"READ_IDS\s+(\S+)\s+([AC])\s+(\d+)\s+([\d,]+)", line.strip())
        if m:
            query, config, count, ids = m.groups()
            values = [int(x) for x in ids.split(",")]
            if len(values) != int(count) or values != sorted(set(values)):
                raise ValueError("SQL ID list malformed")
            sql_ids[(query, config)] = values
        m = re.fullmatch(r"READ_SUMMARY\s+([AC])\s+(\S+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)", line.strip())
        if m:
            config, query, count, median, p95 = m.groups()
            sql_read[(query, config)] = {"count": int(count), "median_ms": float(median), "p95_ms": float(p95)}
        m = re.fullmatch(r"WRITE_SUMMARY\s+([AC])\s+(INSERT|UPDATE)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+(\S+)", line.strip())
        if m:
            config, kind, rows, median, p95, rate = m.groups()
            sql_write[(kind, config)] = {"rows": int(rows), "median_ms": float(median),
                                         "p95_ms": float(p95), "rows_per_second": None if rate == "NULL" else float(rate)}
        m = re.fullmatch(r"READ_RAW\s+([AC])\s+(\S+)\s+(\d+)\s+([\d.]+)\s+(\d+)", line.strip())
        if m:
            config, query, iteration, elapsed, rows = m.groups()
            sql_raw.setdefault((query,config), []).append((int(iteration),int(rows)))
        m = re.fullmatch(r"WRITE_RAW\s+([AC])\s+(INSERT|UPDATE)\s+(\d+)\s+([\d.]+)\s+(\d+)", line.strip())
        if m:
            config, kind, iteration, elapsed, rows = m.groups()
            sql_write_raw.setdefault((kind,config), []).append((int(iteration),int(rows)))
    mongo_lines = [json.loads(line) for line in (ACCEPTED / "uc4_mongo_run.jsonl").open(encoding="utf-8-sig") if line.strip()]
    if not any(x.get("section") == "RUN_COMPLETE" and x.get("status") == "PASS" for x in mongo_lines):
        raise ValueError("Mongo run incomplete")
    mongo_ids = {(x["query_id"], x["config"]): x["doc_ids"] for x in mongo_lines if x["section"] == "READ_IDS"}
    mongo_read = {(x["query_id"], x["config"]): {"count": x["matched_rows"],
                  "median_ms": x["query_median_ms"], "p95_ms": x["query_p95_ms"]}
                  for x in mongo_lines if x["section"] == "READ_SUMMARY"}
    mongo_write = {(x["kind"], x["config"]): {"rows": x["rows"],
                   "median_ms": x["query_median_ms"], "p95_ms": x["query_p95_ms"],
                   "rows_per_second": x["rows_per_second"]}
                   for x in mongo_lines if x["section"] == "WRITE_SUMMARY"}
    expected = {(q, c) for q in QUERIES for c in "AC"}
    if any(set(d) != expected for d in (sql_ids, sql_read, mongo_ids, mongo_read)):
        raise ValueError("Missing read query/configuration")
    if len(sql_write) != 4 or len(mongo_write) != 4:
        raise ValueError("Missing write summary")
    if set(sql_raw) != expected or any([i for i, _ in sql_raw[key]] != list(range(1,26)) or
        any(n != sql_read[key]["count"] for _,n in sql_raw[key]) for key in expected):
        raise ValueError("SQL read sample count or result count mismatch")
    if set(sql_write_raw) != set(sql_write) or any([i for i,_ in rows] != list(range(1,11)) or
        any(n != 20 for _,n in rows) for rows in sql_write_raw.values()):
        raise ValueError("SQL write sample count mismatch")
    mongo_read_raw = {(x["query_id"], x["config"]): x["samples"] for x in mongo_lines if x["section"] == "READ_RAW"}
    mongo_write_raw = {(x["kind"], x["config"]): x["samples"] for x in mongo_lines if x["section"] == "WRITE_RAW"}
    if set(mongo_read_raw) != expected or any(len(mongo_read_raw[key]) != 25 or
        [x["iteration"] for x in mongo_read_raw[key]] != list(range(1,26)) or
        any(x["matched_rows"] != mongo_read[key]["count"] for x in mongo_read_raw[key]) for key in expected):
        raise ValueError("Mongo read sample count or result count mismatch")
    if set(mongo_write_raw) != set(mongo_write) or any(len(rows) != 10 or
        [x["iteration"] for x in rows] != list(range(1,11)) or any(x["affected"] != 20 for x in rows)
        for rows in mongo_write_raw.values()):
        raise ValueError("Mongo write sample count mismatch")
    for x in mongo_lines:
        if x["section"] == "READ_PLAN":
            path = PLANS / f"uc4_mongo_{x['query_id']}_{x['config']}.json"
            path.write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mongo_plans = len(list(PLANS.glob("uc4_mongo_*_?.json")))
    if mongo_plans != 12:
        raise ValueError("Expected 12 Mongo plans")
    diag = (PLANS / "uc4_sql_diagnostics.txt").read_text(encoding="utf-8-sig")
    if "DIAGNOSTICS_COMPLETE PASS" not in diag:
        raise ValueError("SQL diagnostics incomplete")
    xml_strings = re.findall(r"<ShowPlanXML\b.*?</ShowPlanXML>", diag, re.S)
    sql_plan_count = 0
    plan_operators = {}
    for xml in xml_strings:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        statements = [e.attrib.get("StatementText", "") for e in root.iter() if e.tag.endswith("StmtSimple")]
        text = " ".join(statements)
        config = "A" if "dbo.UC4_Read_A" in text else "C" if "dbo.UC4_Read_C" in text else None
        if config is None:
            continue
        # Marker preceding this XML identifies the query. Cursor/control XML is ignored.
        position = diag.find(xml)
        markers = re.findall(r"^PLAN_FOR\s+(\S+)\s+([AC])\s+", diag[:position], re.M)
        if not markers:
            continue
        query, marker_config = markers[-1]
        if marker_config != config:
            continue
        path = PLANS / f"uc4_sql_{query}_{config}.sqlplan"
        path.write_text(xml, encoding="utf-8")
        sql_plan_count += 1
        plan_operators[(query, config)] = sorted({e.attrib.get("PhysicalOp") for e in root.iter()
                                                  if e.tag.endswith("RelOp") and e.attrib.get("PhysicalOp")})
    if sql_plan_count != 12:
        raise ValueError(f"Expected 12 SQL read plans, found {sql_plan_count}")
    comparisons = []
    for query in QUERIES:
        for engine, ids, measures in (("SQL_SERVER", sql_ids, sql_read), ("MONGODB", mongo_ids, mongo_read)):
            a, c = set(ids[(query, "A")]), set(ids[(query, "C")])
            comparisons.append({"engine": engine, "query_id": query,
                "A": measures[(query,"A")], "C": measures[(query,"C")],
                "same_id_set": a == c, "A_only": len(a-c), "C_only": len(c-a),
                "same_result_speedup_A_over_C": round(measures[(query,"A")]["median_ms"] /
                    measures[(query,"C")]["median_ms"], 3) if a == c else None})
    result = {"section": "UC4_VALIDATED_SUMMARY", "source_rows": 10000,
              "sql_plan_count": sql_plan_count, "mongo_plan_count": mongo_plans,
              "read": comparisons, "write": {"SQL_SERVER": sql_write, "MONGODB": mongo_write},
              "cross_engine_id_set": {f"{q}_{c}": {
                  "same": set(sql_ids[(q,c)]) == set(mongo_ids[(q,c)]),
                  "SQL_only": len(set(sql_ids[(q,c)]) - set(mongo_ids[(q,c)])),
                  "MONGO_only": len(set(mongo_ids[(q,c)]) - set(sql_ids[(q,c)]))}
                  for q in QUERIES for c in "AC"},
              "sql_plan_operators": {f"{q}_{c}": ops for (q,c),ops in plan_operators.items()},
              "freshness": {"SQL_SERVER": next((line for line in sql_text.splitlines() if line.startswith("FRESHNESS ")), None),
                            "MONGODB": next((x for x in mongo_lines if x["section"] == "FRESHNESS"), None)},
              "status": "PASS"}
    # JSON does not permit tuple keys; make write mapping serializable.
    result["write"] = {engine: {f"{kind}_{config}": value for (kind,config),value in rows.items()}
                       for engine,rows in result["write"].items()}
    (ACCEPTED / "uc4_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (PLANS.parent / "PLAN_INDEX.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("group", "dbms", "label", "plan_path", "source_transcript"))
        for query in QUERIES:
            for config in "AC":
                writer.writerow(("uc4", "SQL", f"{query}_{config}",
                    f"results/uc4/plans/uc4_sql_{query}_{config}.sqlplan",
                    "results/uc4/plans/uc4_sql_diagnostics.txt"))
                writer.writerow(("uc4", "Mongo", f"{query}_{config}",
                    f"results/uc4/plans/uc4_mongo_{query}_{config}.json",
                    "results/uc4/accepted/uc4_mongo_run.jsonl"))
    with (PLANS.parent / "MANIFEST.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("group", "role", "decision", "path", "original_path", "bytes", "sha256"))
        for role in ("accepted", "plans", "archive"):
            for path in sorted((PLANS.parent / role).glob("*")):
                if not path.is_file():
                    continue
                decision = ("not_used_in_conclusions" if role == "archive" else
                            "primary_plan" if role == "plans" else
                            "primary_measurement" if path.name in
                            ("uc4_sql_run.txt", "uc4_mongo_run.jsonl", "uc4_summary.json") else "supporting")
                writer.writerow(("uc4", role, decision, path.relative_to(ROOT).as_posix(), "",
                                 path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()))
    print(json.dumps({"status": result["status"], "sql_plans": sql_plan_count,
                      "mongo_plans": mongo_plans, "comparisons": len(comparisons)}))


if __name__ == "__main__":
    main()
