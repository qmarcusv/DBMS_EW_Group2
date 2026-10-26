"""Validate Phase 7 raw evidence, compare complete parent-ID sets and extract plans."""
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/uc6"
ACCEPTED = BASE / "accepted"
PLANS = BASE / "plans"
QUERIES = ("ONE_TABLE", "TWO_SYS_TABLE", "ONE_TEMP_Y", "TWO_TABLE_TEMP_Y")


def main():
    manifest = json.loads((ROOT / "local_data/derived/uc6/manifest.json").read_text(encoding="utf-8"))
    expected_ids = json.loads((ROOT / "local_data/derived/uc6/expected_ids.json").read_text(encoding="utf-8"))
    parity = json.loads((ACCEPTED / "uc6_corpus_parity.json").read_text(encoding="utf-8-sig"))
    if parity["status"] != "PASS" or parity["corpus_sha256"] != manifest["jsonl_sha256"]:
        raise ValueError("Corpus parity unverified")
    sql_text = (ACCEPTED / "uc6_sql_run.txt").read_text(encoding="utf-8-sig")
    if "RUN_COMPLETE PASS" not in sql_text:
        raise ValueError("SQL run incomplete")
    sql_ids, sql_read, sql_write, sql_raw, sql_write_raw = {}, {}, {}, {}, {}
    for line in sql_text.splitlines():
        line = line.strip()
        m = re.fullmatch(r"READ_IDS\s+(\S+)\s+([AC])\s+(\d+)\s+([\d,]+)", line)
        if m:
            query,config,count,ids = m.groups()
            values = [int(x) for x in ids.split(",")]
            if len(values) != int(count) or values != expected_ids[query]:
                raise ValueError("SQL parent ID set mismatch: " + query + config)
            sql_ids[(query,config)] = values
        m = re.fullmatch(r"READ_SUMMARY\s+([AC])\s+(\S+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)", line)
        if m:
            config,query,count,median,p95 = m.groups()
            sql_read[(query,config)] = {"matched_parents":int(count),"median_ms":float(median),"p95_ms":float(p95)}
        m = re.fullmatch(r"READ_RAW\s+([AC])\s+(\S+)\s+(\d+)\s+([\d.]+)\s+(\d+)", line)
        if m:
            config,query,iteration,elapsed,count = m.groups()
            sql_raw.setdefault((query,config),[]).append((int(iteration),int(count)))
        m = re.fullmatch(r"WRITE_SUMMARY\s+([AC])\s+(INSERT|ADD_TAG)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+(\S+)", line)
        if m:
            config,kind,rows,median,p95,rate = m.groups()
            sql_write[(kind,config)] = {"parents":int(rows),"median_ms":float(median),
                "p95_ms":float(p95),"parents_per_second":None if rate=="NULL" else float(rate)}
        m = re.fullmatch(r"WRITE_RAW\s+([AC])\s+(INSERT|ADD_TAG)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(\d+)", line)
        if m:
            config,kind,iteration,elapsed,affected,tags = m.groups()
            sql_write_raw.setdefault((kind,config),[]).append((int(iteration),int(affected),int(tags)))
    mongo = [json.loads(line) for line in (ACCEPTED / "uc6_mongo_run.jsonl").open(encoding="utf-8-sig") if line.strip()]
    if not any(x.get("section")=="RUN_COMPLETE" and x.get("status")=="PASS" for x in mongo):
        raise ValueError("Mongo run incomplete")
    mongo_ids = {(x["query_id"],x["config"]):x["parent_ids"] for x in mongo if x["section"]=="READ_IDS"}
    mongo_read = {(x["query_id"],x["config"]):{"matched_parents":x["matched_parents"],
        "median_ms":x["query_median_ms"],"p95_ms":x["query_p95_ms"]} for x in mongo if x["section"]=="READ_SUMMARY"}
    mongo_write = {(x["kind"],x["config"]):{"parents":x["rows"],
        "median_ms":x["query_median_ms"],"p95_ms":x["query_p95_ms"],
        "parents_per_second":x["rows_per_second"]} for x in mongo if x["section"]=="WRITE_SUMMARY"}
    expected_keys = {(q,c) for q in QUERIES for c in "AC"}
    if any(set(d)!=expected_keys for d in (sql_ids,sql_read,sql_raw,mongo_ids,mongo_read)):
        raise ValueError("Missing read case")
    for key in expected_keys:
        query,config = key
        if (mongo_ids[key] != expected_ids[query] or
            sql_read[key]["matched_parents"] != len(expected_ids[query]) or
            mongo_read[key]["matched_parents"] != len(expected_ids[query])):
            raise ValueError("Parent ID mismatch: " + query + config)
        if [i for i,_ in sql_raw[key]] != list(range(1,26)) or any(n != len(expected_ids[query]) for _,n in sql_raw[key]):
            raise ValueError("SQL read sample mismatch")
    mongo_raw = {(x["query_id"],x["config"]):x["samples"] for x in mongo if x["section"]=="READ_RAW"}
    if set(mongo_raw)!=expected_keys or any([x["iteration"] for x in rows]!=list(range(1,26)) or
        any(x["matched_parents"] != len(expected_ids[key[0]]) for x in rows)
        for key,rows in mongo_raw.items()):
        raise ValueError("Mongo read sample mismatch")
    write_keys = {(kind,c) for kind in ("INSERT","ADD_TAG") for c in "AC"}
    mongo_write_raw = {(x["kind"],x["config"]):x["samples"] for x in mongo if x["section"]=="WRITE_RAW"}
    if any(set(d)!=write_keys for d in (sql_write,sql_write_raw,mongo_write,mongo_write_raw)):
        raise ValueError("Missing write case")
    if any([i for i,_,_ in rows]!=list(range(1,11)) or any(affected!=20 for _,affected,_ in rows)
           for rows in sql_write_raw.values()) or any([x["iteration"] for x in rows]!=list(range(1,11)) or
           any(x["affected"]!=20 for x in rows) for rows in mongo_write_raw.values()):
        raise ValueError("Write sample mismatch")
    mongo_plans = {}
    for x in mongo:
        if x["section"]=="READ_PLAN":
            key=(x["query_id"],x["config"])
            mongo_plans[key]={"keys_examined":x["total_keys_examined"],
                "docs_examined":x["total_docs_examined"]}
            (PLANS / f"uc6_mongo_{key[0]}_{key[1]}.json").write_text(
                json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if set(mongo_plans)!=expected_keys:
        raise ValueError("Missing Mongo explain")
    diag = (PLANS / "uc6_sql_diagnostics.txt").read_text(encoding="utf-8-sig")
    if "DIAGNOSTICS_COMPLETE PASS" not in diag:
        raise ValueError("SQL diagnostics incomplete")
    markers=list(re.finditer(r"^PLAN_FOR\s+(\S+)\s+([AC])\s+",diag,re.M))
    sql_plans={}
    for i,m in enumerate(markers):
        query,config=m.group(1),m.group(2)
        segment=diag[m.end():markers[i+1].start() if i+1<len(markers) else len(diag)]
        xmls=re.findall(r"<ShowPlanXML\b.*?</ShowPlanXML>",segment,re.S)
        if len(xmls)!=1:
            raise ValueError(f"Expected one SQL plan for {query}{config}, got {len(xmls)}")
        root=ET.fromstring(xmls[0])
        (PLANS/f"uc6_sql_{query}_{config}.sqlplan").write_text(xmls[0],encoding="utf-8")
        sql_plans[(query,config)]=sorted({x.attrib["PhysicalOp"] for x in root.iter()
            if x.tag.endswith("RelOp") and "PhysicalOp" in x.attrib})
    if set(sql_plans)!=expected_keys:
        raise ValueError("Missing SQL plans")
    build_sql=re.findall(r"^INDEX_BUILD\s+(Read|Write)\s+C\s+([\d.]+)\s+(\d+)$",
                         (ACCEPTED/"uc6_sql_setup.txt").read_text(encoding="utf-8-sig"),re.M)
    build_mongo=[x for x in mongo if x["section"]=="INDEX_BUILD"]
    if len(build_sql)!=2 or len(build_mongo)!=2:
        raise ValueError("Index build evidence missing")
    results=[]
    for engine,reads in (("SQL_SERVER",sql_read),("MONGODB",mongo_read)):
        for query in QUERIES:
            a,c=reads[(query,"A")],reads[(query,"C")]
            results.append({"engine":engine,"query_id":query,"A":a,"C":c,
                "same_parent_ids":True,"median_ratio_A_over_C":None if c["median_ms"]==0 else
                round(a["median_ms"]/c["median_ms"],3)})
    out={"section":"UC6_VALIDATED_SUMMARY","status":"PASS","dataset_id":manifest["dataset_id"],
         "source_csv_sha256":manifest["source_csv_sha256"],"corpus_sha256":manifest["jsonl_sha256"],
         "parents":10000,"tag_rows":manifest["tag_rows"],"array_lengths":manifest["distinct_array_lengths"],
         "read":results,"write":{"SQL_SERVER":{f"{k}_{c}":v for (k,c),v in sql_write.items()},
                                  "MONGODB":{f"{k}_{c}":v for (k,c),v in mongo_write.items()}},
         "index_build":{"SQL_SERVER":{role:{"elapsed_ms":float(ms),"used_bytes":int(size)} for role,ms,size in build_sql},
                        "MONGODB":{x["role"]:{"elapsed_ms":x["elapsed_ms"],"index_storage_bytes":x["index_storage_bytes"]}
                                   for x in build_mongo}},
         "plans":{"SQL_SERVER":{f"{q}_{c}":v for (q,c),v in sql_plans.items()},
                  "MONGODB":{f"{q}_{c}":v for (q,c),v in mongo_plans.items()}}}
    (ACCEPTED/"uc6_summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (BASE/"PLAN_INDEX.csv").open("w",encoding="utf-8",newline="") as stream:
        w=csv.writer(stream);w.writerow(("group","dbms","label","plan_path","source_transcript"))
        for q in QUERIES:
            for c in "AC":
                w.writerow(("uc6","SQL",f"{q}_{c}",f"results/uc6/plans/uc6_sql_{q}_{c}.sqlplan",
                            "results/uc6/plans/uc6_sql_diagnostics.txt"))
                w.writerow(("uc6","Mongo",f"{q}_{c}",f"results/uc6/plans/uc6_mongo_{q}_{c}.json",
                            "results/uc6/accepted/uc6_mongo_run.jsonl"))
    with (BASE/"MANIFEST.csv").open("w",encoding="utf-8",newline="") as stream:
        w=csv.writer(stream);w.writerow(("group","role","decision","path","original_path","bytes","sha256"))
        for role in ("accepted","plans","archive"):
            for path in sorted((BASE/role).glob("*")):
                if not path.is_file():
                    continue
                decision=("not_used_in_conclusions" if role=="archive" else "primary_plan" if role=="plans"
                          else "primary_measurement" if path.name in
                          ("uc6_sql_run.txt","uc6_mongo_run.jsonl","uc6_summary.json") else "supporting")
                w.writerow(("uc6",role,decision,path.relative_to(ROOT).as_posix(),"",
                            path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest()))
    print(json.dumps({"status":"PASS","read_cells":len(results),"sql_plans":len(sql_plans),
                      "mongo_plans":len(mongo_plans)}))


if __name__=="__main__":
    main()
