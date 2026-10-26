"""Read-only, full-row parity verification after UC4 setup.

mongoexport --db dbms_ew_group02 --collection uc4_seed_10k --out results/uc4/accepted/uc4_mongo_seed_export.jsonl
py -3.13 analysis/uc4_verify.py
The script exports Mongo read copies to temporary files and removes them after comparison.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "local_data/derived/uc4/corpus_10k.jsonl"
EXPORT = ROOT / "results/uc4/accepted/uc4_mongo_seed_export.jsonl"
FIELDS = ("DOC_ID", "TITLE", "BODY", "SUBJECT", "RAW_DATE", "SOURCE_FILE", "SOURCE_ROW")


def load(path):
    rows = {}
    for line in path.open(encoding="utf-8"):
        item = json.loads(line)
        key = item["DOC_ID"]
        if key in rows:
            raise ValueError(f"Duplicate DOC_ID {key} in {path}")
        rows[key] = {field: item[field] for field in FIELDS}
    return rows


def main():
    expected = load(CORPUS)
    mongo = load(EXPORT)
    driver = next(x for x in reversed(pyodbc.drivers()) if x.startswith("ODBC Driver ") and "SQL Server" in x)
    db = pyodbc.connect(f"DRIVER={{{driver}}};SERVER=localhost;DATABASE=DBMS_EW_Group02;"
                        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes", autocommit=True)
    def sql_rows(table):
        rows = {}
        for row in db.cursor().execute(f"SELECT DOC_ID,TITLE,BODY,SUBJECT,RAW_DATE,SOURCE_FILE,SOURCE_ROW FROM dbo.{table}"):
            doc = dict(zip(FIELDS, row))
            rows[doc["DOC_ID"]] = doc
        return rows

    sql = sql_rows("UC4_Seed_10K")
    sql_copies = {c: sql_rows("UC4_Read_" + c) for c in "AC"}
    mongo_copies = {}
    with tempfile.TemporaryDirectory(prefix="uc4_verify_") as directory:
        for c in "AC":
            path = Path(directory) / f"read_{c}.jsonl"
            subprocess.run(["mongoexport", "--db", "dbms_ew_group02", "--collection", f"uc4_read_{c}",
                            "--out", str(path)], check=True, capture_output=True, text=True)
            mongo_copies[c] = load(path)
    result = {"section": "UC4_SEED_PARITY", "expected_rows": len(expected),
              "mongo_rows": len(mongo), "sql_rows": len(sql),
              "mongo_mismatches": sum(expected.get(k) != mongo.get(k) for k in set(expected) | set(mongo)),
              "sql_mismatches": sum(expected.get(k) != sql.get(k) for k in set(expected) | set(sql)),
              "read_copy_mismatches": {
                  "SQL_" + c: sum(expected.get(k) != rows.get(k) for k in set(expected) | set(rows))
                  for c, rows in sql_copies.items()
              } | {
                  "MONGO_" + c: sum(expected.get(k) != rows.get(k) for k in set(expected) | set(rows))
                  for c, rows in mongo_copies.items()
              },
              "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest()}
    result["status"] = "PASS" if result["expected_rows"] == 10000 and result["mongo_mismatches"] == result["sql_mismatches"] == 0 and all(x == 0 for x in result["read_copy_mismatches"].values()) else "FAIL"
    print(json.dumps(result))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
