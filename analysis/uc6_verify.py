"""Full parent/tag parity across canonical JSONL, SQL and Mongo seed/read copies."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "local_data/derived/uc6/parents_10k.jsonl"
FIELDS = ("PARENT_ID", "SOURCE_ROW", "OWNER", "OBJECT_TYPE", "tags")


def load(path):
    rows = {}
    for line in path.open(encoding="utf-8"):
        item = json.loads(line)
        pid = item["PARENT_ID"]
        if pid in rows:
            raise ValueError("Duplicate parent")
        rows[pid] = {field: item[field] for field in FIELDS}
    return rows


def main():
    manifest = json.loads((SOURCE.parent / "manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != manifest["jsonl_sha256"]:
        raise ValueError("Canonical UC6 file hash mismatch")
    expected = load(SOURCE)
    driver = next(x for x in reversed(pyodbc.drivers()) if x.startswith("ODBC Driver ") and "SQL Server" in x)
    db = pyodbc.connect(f"DRIVER={{{driver}}};SERVER=localhost;DATABASE=DBMS_EW_Group02;"
                        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes", autocommit=True)
    comparisons = {}
    for suffix in ("Seed", "Read_A", "Read_C"):
        rows = {}
        for row in db.cursor().execute(f"SELECT PARENT_ID,SOURCE_ROW,OWNER,OBJECT_TYPE FROM dbo.UC6_{suffix}_Parent"):
            pid, source_row, owner, obj_type = row
            rows[pid] = {"PARENT_ID": pid, "SOURCE_ROW": source_row, "OWNER": owner,
                         "OBJECT_TYPE": obj_type, "tags": []}
        tag_rows = 0
        for pid, tag in db.cursor().execute(f"SELECT PARENT_ID,TAG FROM dbo.UC6_{suffix}_Tag"):
            rows[pid]["tags"].append(tag)
            tag_rows += 1
        for row in rows.values():
            row["tags"].sort()
        comparisons["SQL_" + suffix] = {"parents": len(rows), "tag_rows": tag_rows,
            "mismatches": sum(expected.get(k) != rows.get(k) for k in set(expected) | set(rows))}
    with tempfile.TemporaryDirectory(prefix="uc6_verify_") as directory:
        for suffix, name in (("Seed","uc6_seed_10k"),("Read_A","uc6_read_A"),("Read_C","uc6_read_C")):
            path = Path(directory) / (name + ".jsonl")
            subprocess.run(["mongoexport", "--db", "dbms_ew_group02", "--collection", name,
                            "--out", str(path)], check=True, capture_output=True, text=True)
            rows = load(path)
            comparisons["MONGO_" + suffix] = {"parents": len(rows),
                "tag_rows": sum(len(x["tags"]) for x in rows.values()),
                "mismatches": sum(expected.get(k) != rows.get(k) for k in set(expected) | set(rows))}
    result = {"section": "UC6_CORPUS_PARITY", "dataset_id": manifest["dataset_id"],
              "corpus_sha256": manifest["jsonl_sha256"], "expected_parents": len(expected),
              "expected_tag_rows": manifest["tag_rows"], "copies": comparisons}
    result["status"] = "PASS" if len(expected) == 10000 and all(
        x["parents"] == 10000 and x["tag_rows"] == manifest["tag_rows"] and x["mismatches"] == 0
        for x in comparisons.values()) else "FAIL"
    print(json.dumps(result))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
