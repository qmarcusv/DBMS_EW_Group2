"""Load UC6 normalized seed tables through parameterized ODBC batches.

Requires pyodbc and Microsoft ODBC Driver 18. Run: py -3.13 analysis/uc6_load_sql.py
"""
import hashlib
import json
from pathlib import Path
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "local_data/derived/uc6/parents_10k.jsonl"
MANIFEST = json.loads((PATH.parent / "manifest.json").read_text(encoding="utf-8"))


def main():
    if hashlib.sha256(PATH.read_bytes()).hexdigest() != MANIFEST["jsonl_sha256"]:
        raise ValueError("UC6 corpus hash mismatch")
    driver = next((x for x in reversed(pyodbc.drivers()) if x.startswith("ODBC Driver ") and "SQL Server" in x), None)
    if not driver:
        raise RuntimeError("SQL Server ODBC driver missing")
    conn = pyodbc.connect(f"DRIVER={{{driver}}};SERVER=localhost;DATABASE=DBMS_EW_Group02;"
                          "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes", autocommit=False)
    cur = conn.cursor()
    if any(cur.execute("SELECT OBJECT_ID(?,N'U')", "dbo." + name).fetchval() is not None
           for name in ("UC6_Seed_Parent", "UC6_Seed_Tag")):
        raise RuntimeError("UC6 seed exists; save results and clean explicitly before rerun")
    cur.execute("""CREATE TABLE dbo.UC6_Seed_Parent (
      PARENT_ID bigint NOT NULL CONSTRAINT PK_UC6_Seed_Parent PRIMARY KEY CLUSTERED,
      SOURCE_ROW int NOT NULL, OWNER nvarchar(128) NOT NULL,
      OBJECT_TYPE nvarchar(64) NOT NULL)""")
    cur.execute("""CREATE TABLE dbo.UC6_Seed_Tag (
      PARENT_ID bigint NOT NULL, TAG nvarchar(128) NOT NULL,
      CONSTRAINT PK_UC6_Seed_Tag PRIMARY KEY CLUSTERED(PARENT_ID,TAG),
      CONSTRAINT FK_UC6_Seed_Tag_Parent FOREIGN KEY(PARENT_ID)
       REFERENCES dbo.UC6_Seed_Parent(PARENT_ID))""")
    conn.commit()
    parents, tags = [], []
    for line in PATH.open(encoding="utf-8"):
        item = json.loads(line)
        parents.append((item["PARENT_ID"], item["SOURCE_ROW"], item["OWNER"], item["OBJECT_TYPE"]))
        tags.extend((item["PARENT_ID"], tag) for tag in item["tags"])
    if len(parents) != 10000 or len(tags) != MANIFEST["tag_rows"]:
        raise ValueError("Wrong corpus shape")
    try:
        for start in range(0, len(parents), 500):
            cur.executemany("INSERT dbo.UC6_Seed_Parent(PARENT_ID,SOURCE_ROW,OWNER,OBJECT_TYPE) VALUES(?,?,?,?)",
                            parents[start:start+500])
            conn.commit()
        for start in range(0, len(tags), 500):
            cur.executemany("INSERT dbo.UC6_Seed_Tag(PARENT_ID,TAG) VALUES(?,?)", tags[start:start+500])
            conn.commit()
        actual = (cur.execute("SELECT COUNT_BIG(*) FROM dbo.UC6_Seed_Parent").fetchval(),
                  cur.execute("SELECT COUNT_BIG(*) FROM dbo.UC6_Seed_Tag").fetchval())
        if actual != (10000, MANIFEST["tag_rows"]):
            raise RuntimeError(f"SQL UC6 seed count mismatch: {actual}")
        print(json.dumps({"section":"SQL_UC6_SEED_READY", "parents":actual[0], "tags":actual[1],
                          "corpus_sha256": MANIFEST["jsonl_sha256"], "driver":driver}))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
