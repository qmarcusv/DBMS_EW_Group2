"""Audit accepted UC1-UC6 raw evidence and publish the only demo/report data feed.

This script reads evidence; it never reruns benchmarks or writes to a DBMS.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase8"
FILES = {
    "uc1": {"SQL_SERVER":"results/uc1/accepted/phase3_uc1_sql_benchmark.txt",
            "MONGODB":"results/uc1/accepted/phase3_uc1_mongo_benchmark_rerun.jsonl"},
    "uc2": {"SQL_SERVER":"results/uc2/accepted/phase4_uc2_sql_run_v4.txt",
            "MONGODB":"results/uc2/accepted/phase4_uc2_mongo_run.jsonl"},
    "uc3": {"SQL_SERVER":"results/uc3/accepted/phase5_uc3_sql_run.txt",
            "MONGODB":"results/uc3/accepted/phase5_uc3_mongo_run.jsonl"},
    "uc4": {"SQL_SERVER":"results/uc4/accepted/uc4_sql_run.txt",
            "MONGODB":"results/uc4/accepted/uc4_mongo_run.jsonl"},
    "uc5": {"SQL_SERVER":"results/uc5/accepted/phase6_uc5_sql_run_v2.txt"},
    "uc6": {"SQL_SERVER":"results/uc6/accepted/uc6_sql_run.txt",
            "MONGODB":"results/uc6/accepted/uc6_mongo_run.jsonl"},
}


def pct(values, p):
    ordered = sorted(values)
    pos = (len(ordered)-1)*p
    lo = int(pos)
    return ordered[lo] + (ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(pos-lo)


def key(uc, engine, scale, query, config):
    return (uc,engine,scale,query,config)


def sql_key(uc, parts):
    if uc=="uc1":
        return key(uc,"SQL_SERVER","100K",parts[2],parts[1])
    if uc in ("uc2","uc3"):
        query = {"INSIDE":"Y","OUTSIDE":"N"}.get(parts[2],parts[2]) if uc=="uc2" else parts[2]
        return key(uc,"SQL_SERVER",parts[0],query,parts[1])
    if uc=="uc5":
        return key(uc,"SQL_SERVER","1000K",parts[1],parts[0])
    raise ValueError(uc)


def audit_sql(uc, path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not any(line.startswith("RUN_COMPLETE") and line.endswith("PASS") for line in lines):
        raise ValueError(f"{uc} SQL lacks PASS marker")
    raw, summaries = {}, {}
    for line in lines:
        if line.startswith("READ_RAW|"):
            p=line.split("|")[1:]
            k=sql_key(uc,p)
            idx = {"uc1":3,"uc2":3,"uc3":3,"uc5":2}[uc]
            iteration=int(p[idx]); elapsed=float(p[idx+1]); count=int(p[idx+2])
            if uc=="uc1" and p[7]!="PASS":
                raise ValueError("UC1 SQL raw correctness failed")
            raw.setdefault(k,[]).append((iteration,elapsed,count))
        if line.startswith("READ_SUMMARY|"):
            p=line.split("|")[1:]
            k=sql_key(uc,p)
            if uc=="uc1":
                repeat,median,p95,count=int(p[3]),float(p[4]),float(p[5]),int(p[6])
            elif uc in ("uc2","uc3"):
                repeat,median,p95,count=int(p[3]),float(p[4]),float(p[5]),int(p[6])
            else:
                repeat,median,p95,count=25,float(p[2]),float(p[3]),int(p[4])
            summaries[k]=(repeat,median,p95,count)
    if not summaries or set(raw)!=set(summaries):
        raise ValueError(f"{uc} SQL summary/raw cases differ")
    rows=[]
    for k,(repeat,median,p95,count) in summaries.items():
        samples=raw[k]
        if repeat!=25 or [x[0] for x in samples]!=list(range(1,26)) or any(x[2]!=count for x in samples):
            raise ValueError(f"{uc} SQL sample sequence/count mismatch: {k}")
        times=[x[1] for x in samples]
        if abs(statistics.median(times)-median)>0.0011 or abs(pct(times,.95)-p95)>0.0011:
            raise ValueError(f"{uc} SQL median/p95 mismatch: {k}")
        rows.append(row(k,count,median,p95,path,25))
    return rows


def audit_mongo(uc,path):
    items=[json.loads(line) for line in path.open(encoding="utf-8-sig") if line.strip()]
    if not any(x.get("section")=="RUN_COMPLETE" and x.get("status")=="PASS" for x in items):
        raise ValueError(f"{uc} Mongo lacks PASS marker")
    summaries={}
    raws={}
    for x in items:
        if x.get("section") not in ("READ_RAW","READ_SUMMARY"):
            continue
        if uc=="uc1":
            k=key(uc,"MONGODB","100K",x["query_id"],x["configuration"])
        elif uc=="uc2":
            k=key(uc,"MONGODB",x["scale"],x["value"],x["config"])
        else:
            k=key(uc,"MONGODB",x["scale"],x["query_id"],x["config"])
        if x["section"]=="READ_RAW":
            raws[k]=x["samples"]
        else:
            summaries[k]=x
    if not summaries or set(raws)!=set(summaries):
        raise ValueError(f"{uc} Mongo summary/raw cases differ")
    rows=[]
    for k,x in summaries.items():
        samples=raws[k]
        if x["repetition_count"]!=25 or [s["iteration"] for s in samples]!=list(range(1,26)):
            raise ValueError(f"{uc} Mongo sample sequence mismatch: {k}")
        counts=[s.get("returned_rows",s.get("count",s.get("matched_rows"))) for s in samples]
        count=x.get("returned_rows",x.get("count",x.get("matched_rows")))
        if count is None or any(n!=count for n in counts):
            raise ValueError(f"{uc} Mongo result count changed: {k}")
        if any(s.get("correctness_status","PASS")!="PASS" for s in samples):
            raise ValueError(f"{uc} Mongo correctness failed: {k}")
        times=[s["elapsed_ms"] for s in samples]
        if abs(statistics.median(times)-x["query_median_ms"])>1e-5 or abs(pct(times,.95)-x["query_p95_ms"])>1e-5:
            raise ValueError(f"{uc} Mongo median/p95 mismatch: {k}")
        rows.append(row(k,count,x["query_median_ms"],x["query_p95_ms"],path,25))
    return rows


def row(k,count,median,p95,path,samples):
    return {"uc":k[0],"engine":k[1],"scale":k[2],"query_id":k[3],"config":k[4],
            "matched_rows":count,"median_ms":median,"p95_ms":p95,"samples":samples,
            "source":path.relative_to(ROOT).as_posix(),"semantic_parity":True}


def audit_json_uc(uc):
    summary=json.loads((ROOT/f"results/{uc}/accepted/{uc}_summary.json").read_text(encoding="utf-8"))
    parity_name="seed" if uc=="uc4" else "corpus"
    parity=json.loads((ROOT/f"results/{uc}/accepted/{uc}_{parity_name}_parity.json").read_text(encoding="utf-8-sig"))
    if summary["status"]!="PASS" or parity["status"]!="PASS":
        raise ValueError(f"{uc} summary or parity failed")
    sql_raw=(ROOT/FILES[uc]["SQL_SERVER"]).read_text(encoding="utf-8-sig")
    mongo=[json.loads(line) for line in (ROOT/FILES[uc]["MONGODB"]).open(encoding="utf-8-sig") if line.strip()]
    if "RUN_COMPLETE PASS" not in sql_raw or not any(x.get("section")=="RUN_COMPLETE" and x.get("status")=="PASS" for x in mongo):
        raise ValueError(f"{uc} raw run incomplete")
    sql_samples={}
    for config,query,iteration,elapsed,count in re.findall(
        r"^READ_RAW\s+([AC])\s+(\S+)\s+(\d+)\s+([\d.]+)\s+(\d+)$",sql_raw,re.M):
        sql_samples.setdefault((query,config),[]).append((int(iteration),float(elapsed),int(count)))
    mongo_samples={(x["query_id"],x["config"]):x["samples"]
                   for x in mongo if x.get("section")=="READ_RAW"}
    rows=[]
    for item in summary["read"]:
        engine=item["engine"]
        for config in "AC":
            measure=item[config]
            count=measure.get("count",measure.get("matched_parents"))
            k=key(uc,engine,"10K",item["query_id"],config)
            path=ROOT/FILES[uc][engine]
            if engine=="SQL_SERVER":
                samples=sql_samples.get((item["query_id"],config),[])
                if [x[0] for x in samples]!=list(range(1,26)) or any(x[2]!=count for x in samples):
                    raise ValueError(f"{uc} SQL raw samples incomplete")
                times=[x[1] for x in samples]
            else:
                samples=mongo_samples.get((item["query_id"],config),[])
                count_field="matched_rows" if uc=="uc4" else "matched_parents"
                if [x["iteration"] for x in samples]!=list(range(1,26)) or any(x[count_field]!=count for x in samples):
                    raise ValueError(f"{uc} Mongo raw samples incomplete")
                times=[x["elapsed_ms"] for x in samples]
            if abs(statistics.median(times)-measure["median_ms"])>0.0011 or abs(pct(times,.95)-measure["p95_ms"])>0.0011:
                raise ValueError(f"{uc} median/p95 mismatch")
            output=row(k,count,measure["median_ms"],measure["p95_ms"],path,25)
            output["semantic_parity"]=item.get("same_id_set",item.get("same_parent_ids"))
            rows.append(output)
    return rows


def validate_plans():
    sources=[ROOT/"results/PLAN_INDEX.csv",ROOT/"results/uc4/PLAN_INDEX.csv",ROOT/"results/uc6/PLAN_INDEX.csv"]
    coverage={}
    for source in sources:
        for entry in csv.DictReader(source.open(encoding="utf-8-sig")):
            group=entry["group"]
            if group not in FILES:
                continue
            path=ROOT/entry["plan_path"]
            if not path.is_file() or path.stat().st_size==0:
                raise ValueError(f"Missing plan: {path}")
            if path.suffix==".sqlplan":
                ET.parse(path)
            elif path.suffix==".json":
                json.loads(path.read_text(encoding="utf-8"))
            coverage[group]=coverage.get(group,0)+1
    for group,count in {"uc1":24,"uc2":32,"uc3":36,"uc4":24,"uc5":4,"uc6":16}.items():
        if coverage.get(group,0)<count:
            raise ValueError(f"Plan coverage too low: {group} {coverage.get(group,0)}")
    return coverage


def main():
    rows=[]; sources={}
    for uc,engines in FILES.items():
        for engine,relative in engines.items():
            path=ROOT/relative
            sources[relative]={"bytes":path.stat().st_size,
                               "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
        if uc in ("uc4","uc6"):
            rows.extend(audit_json_uc(uc))
        else:
            rows.extend(audit_sql(uc,ROOT/engines["SQL_SERVER"]))
            if "MONGODB" in engines:
                rows.extend(audit_mongo(uc,ROOT/engines["MONGODB"]))
    index={key(x["uc"],x["engine"],x["scale"],x["query_id"],x["config"]):x for x in rows}
    if len(index)!=len(rows):
        raise ValueError("Duplicate reviewed case")
    for uc in ("uc1","uc2","uc3"):
        for x in rows:
            if x["uc"]!=uc or x["engine"]!="SQL_SERVER":
                continue
            partner=index.get(key(uc,"MONGODB",x["scale"],x["query_id"],x["config"]))
            if not partner or partner["matched_rows"]!=x["matched_rows"]:
                raise ValueError(f"Cross-engine result count mismatch: {uc} {x['query_id']}")
    coverage=validate_plans()
    rows.sort(key=lambda x:(x["uc"],x["engine"],x["scale"],x["query_id"],x["config"]))
    out={"status":"PASS","protocol":"read-only audit of accepted raw artifacts; no reruns",
         "sources":sources,"plan_counts":coverage,
         "cases":rows,"limitations":[
             "SQL and mongosh timer boundaries differ; no cross-engine latency ranking",
             "UC4 substring and full-text result sets differ on SQL, and on one Mongo query",
             "SQL UC3/UC6 zero-ms cells are below effective timer resolution",
             "Phase 2 smoke infrastructure remains PARTIAL for SSMS UI/write helper coverage",
             "One local run per UC/configuration; p95 is descriptive, not a confidence interval"]}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"evidence_review.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (OUT/"read_cases.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    print(json.dumps({"status":"PASS","read_cases":len(rows),"plans":coverage}))


if __name__=="__main__":
    main()
