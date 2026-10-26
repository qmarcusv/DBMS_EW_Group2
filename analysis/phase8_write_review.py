"""Review accepted UC1-UC6 write samples for report/dashboard use.

Reads only accepted transcripts and emits normalized rows; no DBMS mutation.
"""
import csv
import json
from pathlib import Path
import statistics

from phase8_review import FILES, OUT, ROOT, pct


def make(uc,engine,scale,config,kind,samples,affected,median,p95,rate,path):
    if not samples or any(x<0 for x in samples):
        raise ValueError(f"Missing/invalid write samples: {uc} {engine} {kind}")
    if abs(statistics.median(samples)-median)>0.0011 or abs(pct(samples,.95)-p95)>0.0011:
        raise ValueError(f"Write median/p95 mismatch: {uc} {engine} {kind}")
    if rate is not None and kind.startswith("INSERT") and sum(samples)>0:
        calculated=affected*1000/sum(samples)
        if abs(calculated-rate)>max(0.1,rate*.005):
            raise ValueError(f"Write throughput mismatch: {uc} {engine} {kind}")
    return {"uc":uc,"engine":engine,"scale":scale,"config":config,"kind":kind,
        "affected":affected,"batches":len(samples),"median_ms":median,"p95_ms":p95,
        "rows_per_second":rate,"source":path.relative_to(ROOT).as_posix()}


def sql_writes(uc,path):
    lines=path.read_text(encoding="utf-8-sig").splitlines()
    raw={};summaries={}
    for line in lines:
        if not line.startswith(("WRITE_RAW|","WRITE_SUMMARY|")):
            continue
        kind_label,*p=line.split("|")
        if uc=="uc1":
            if kind_label=="WRITE_RAW":
                kind,table,i,elapsed,affected=p[1],p[2],int(p[3]),float(p[4]),int(p[5])
            else:
                table,kind=p[0],p[1]
            config=table.split("_")[2];scale="100K";key=(scale,config,kind)
            if kind_label=="WRITE_RAW":
                raw.setdefault(key,[]).append((i,elapsed,affected))
            else:
                summaries[key]=(int(p[3]),float(p[5]),float(p[6]),None if p[7]=="NULL" else float(p[7]))
            continue
        if uc=="uc2":
            scale,config,kind=p[:3]; start=3
        elif uc=="uc3":
            scale,config,kind=p[:3]; start=3
        elif uc=="uc5":
            config,kind=p[:2];scale="1000K";start=2
        elif uc in ("uc4","uc6"):
            # These use whitespace-delimited native transcripts, handled below.
            continue
        key=(scale,config,kind)
        if kind_label=="WRITE_RAW":
            raw.setdefault(key,[]).append((int(p[start]),float(p[start+1]),int(p[start+2])))
        elif uc=="uc2":
            summaries[key]=(int(p[4]),float(p[5]),float(p[6]),None if p[7]=="NULL" else float(p[7]))
        else:
            summaries[key]=(None,float(p[start]),float(p[start+1]),None if p[start+2]=="NULL" else float(p[start+2]))
    if uc in ("uc4","uc6"):
        for line in lines:
            p=line.split()
            if not p or p[0] not in ("WRITE_RAW","WRITE_SUMMARY"):
                continue
            if p[0]=="WRITE_RAW":
                config,kind,i,elapsed,affected=p[1],p[2],int(p[3]),float(p[4]),int(p[5])
                raw.setdefault(("10K",config,kind),[]).append((i,elapsed,affected))
            else:
                config,kind,affected,median,p95,rate=p[1:7]
                summaries[("10K",config,kind)]=(int(affected),float(median),float(p95),None if rate=="NULL" else float(rate))
    if not summaries or set(raw)!=set(summaries):
        raise ValueError(f"SQL write raw/summary mismatch: {uc}")
    rows=[]
    for (scale,config,kind), (expected,median,p95,rate) in summaries.items():
        samples=raw[(scale,config,kind)]
        if [x[0] for x in samples]!=list(range(1,len(samples)+1)):
            raise ValueError(f"SQL write iteration mismatch: {uc}")
        if expected is not None and sum(x[2] for x in samples)!=expected:
            raise ValueError(f"SQL write affected mismatch: {uc}")
        rows.append(make(uc,"SQL_SERVER",scale,config,kind,[x[1] for x in samples],
                         sum(x[2] for x in samples),median,p95,rate,path))
    return rows


def mongo_writes(uc,path):
    items=[json.loads(line) for line in path.open(encoding="utf-8-sig") if line.strip()]
    raw={};summaries={}
    for x in items:
        if x.get("section") not in ("WRITE_RAW","WRITE_SUMMARY"):
            continue
        if uc=="uc1":
            config=x["configuration"]
            for kind,field in (("INSERT","inserts"),("UPDATE","updates")):
                key=("100K",config,kind)
                if x["section"]=="WRITE_RAW":
                    raw[key]=[(item["batch"],item["elapsed_ms"],item.get("rows",item.get("modified"))) for item in x[field]]
                else:
                    median=statistics.median(i[1] for i in raw[key]) if kind=="INSERT" else x["update_median_ms"]
                    p95=pct([i[1] for i in raw[key]],.95) if kind=="INSERT" else x["update_p95_ms"]
                    summaries[key]=(x["insert_rows"] if kind=="INSERT" else x["updated_rows"],
                                    median,p95,x["insert_rows_per_second"] if kind=="INSERT" else None)
            continue
        key=(x.get("scale","10K"),x["config"],x["kind"])
        if x["section"]=="WRITE_RAW":
            raw[key]=[(s["iteration"],s["elapsed_ms"],s["affected"]) for s in x["samples"]]
        else:
            summaries[key]=(x["rows"],x["query_median_ms"],x["query_p95_ms"],x.get("rows_per_second"))
    if not summaries or set(raw)!=set(summaries):
        raise ValueError(f"Mongo write raw/summary mismatch: {uc}")
    rows=[]
    for (scale,config,kind),(affected,median,p95,rate) in summaries.items():
        samples=raw[(scale,config,kind)]
        if [x[0] for x in samples]!=list(range(1,len(samples)+1)) or sum(x[2] for x in samples)!=affected:
            raise ValueError(f"Mongo write sample mismatch: {uc}")
        rows.append(make(uc,"MONGODB",scale,config,kind,[x[1] for x in samples],
                         affected,median,p95,rate,path))
    return rows


def main():
    rows=[]
    for uc,engines in FILES.items():
        rows.extend(sql_writes(uc,ROOT/engines["SQL_SERVER"]))
        if "MONGODB" in engines:
            rows.extend(mongo_writes(uc,ROOT/engines["MONGODB"]))
    rows.sort(key=lambda x:(x["uc"],x["engine"],x["scale"],x["config"],x["kind"]))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"write_cases.json").write_text(json.dumps({"status":"PASS","cases":rows},indent=2)+"\n",encoding="utf-8")
    with (OUT/"write_cases.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    print(json.dumps({"status":"PASS","write_cases":len(rows)}))


if __name__=="__main__":
    main()
