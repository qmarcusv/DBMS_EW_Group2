"""Load only dbo.UC4_Seed_10K via parameterized ODBC batches.

Requires pyodbc and ODBC Driver 18. Run: py -3.13 analysis/uc4_load_sql.py
"""
import hashlib
import json
from pathlib import Path
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "local_data/derived/uc4/corpus_10k.jsonl"
MANIFEST = json.loads((PATH.parent / "manifest.json").read_text(encoding="utf-8"))


def main():
    if hashlib.sha256(PATH.read_bytes()).hexdigest() != MANIFEST["jsonl_sha256"]:
        raise ValueError("UC4 corpus hash mismatch")
    drivers = pyodbc.drivers()
    driver = next((x for x in reversed(drivers) if x.startswith("ODBC Driver ") and "SQL Server" in x), None)
    if not driver:
        raise RuntimeError("Microsoft ODBC Driver for SQL Server required")
    conn = pyodbc.connect(f"DRIVER={{{driver}}};SERVER=localhost;DATABASE=DBMS_EW_Group02;"
                          "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes", autocommit=False)
    cur = conn.cursor()
    if cur.execute("SELECT OBJECT_ID(N'dbo.UC4_Seed_10K',N'U')").fetchval() is not None:
        raise RuntimeError("UC4 seed exists; preserve evidence or run UC4 cleanup explicitly")
    cur.execute("""CREATE TABLE dbo.UC4_Seed_10K (
      DOC_ID bigint NOT NULL PRIMARY KEY, TITLE nvarchar(512) NOT NULL,
      BODY nvarchar(max) NOT NULL, SUBJECT nvarchar(64) NOT NULL,
      RAW_DATE nvarchar(160) NOT NULL, SOURCE_FILE nvarchar(16) NOT NULL,
      SOURCE_ROW int NOT NULL)""")
    conn.commit()
    sql = "INSERT dbo.UC4_Seed_10K (DOC_ID,TITLE,BODY,SUBJECT,RAW_DATE,SOURCE_FILE,SOURCE_ROW) VALUES (?,?,?,?,?,?,?)"
    batch = []
    total = 0
    try:
        for line in PATH.open(encoding="utf-8"):
            x = json.loads(line)
            batch.append((x["DOC_ID"], x["TITLE"], x["BODY"], x["SUBJECT"],
                          x["RAW_DATE"], x["SOURCE_FILE"], x["SOURCE_ROW"]))
            if len(batch) == 100:
                cur.executemany(sql, batch)
                conn.commit()
                total += len(batch)
                batch.clear()
        if batch:
            cur.executemany(sql, batch)
            conn.commit()
            total += len(batch)
        actual = cur.execute("SELECT COUNT_BIG(*) FROM dbo.UC4_Seed_10K").fetchval()
        if actual != 10000 or total != 10000:
            raise RuntimeError(f"Loaded {total}, stored {actual}; expected 10000")
        print(json.dumps({"section": "SQL_SEED_READY", "rows": actual,
                          "source_jsonl_sha256": MANIFEST["jsonl_sha256"], "driver": driver}))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
