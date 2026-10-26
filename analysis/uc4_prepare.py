"""Create the pinned, deterministic 10K UC4 corpus shared by SQL and Mongo.

Run from the repository root: python analysis/uc4_prepare.py
"""
import csv
import hashlib
import heapq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "local_data/source/fake_real_news"
OUT = ROOT / "local_data/derived/uc4"
FILES = ("Fake.csv", "True.csv")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    provenance = json.loads((SOURCE / "PROVENANCE.json").read_text(encoding="utf-8"))
    for item in provenance["files"]:
        if digest(SOURCE / item["name"]) != item["sha256"]:
            raise ValueError("Source hash mismatch: " + item["name"])
    selected = {}
    for name in FILES:
        heap = []
        with (SOURCE / name).open(encoding="utf-8-sig", newline="") as stream:
            for row_no, row in enumerate(csv.DictReader(stream), 1):
                if not row["text"].strip():
                    continue
                key = int.from_bytes(hashlib.sha256(f"{name}:{row_no}".encode("ascii")).digest(), "big")
                if len(heap) < 5000:
                    heapq.heappush(heap, (-key, row_no))
                elif key < -heap[0][0]:
                    heapq.heapreplace(heap, (-key, row_no))
        selected[name] = {row_no for _, row_no in heap}
        if len(selected[name]) != 5000:
            raise ValueError("Insufficient eligible records in " + name)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "corpus_10k.jsonl"
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for name in FILES:
            offset = 0 if name == "Fake.csv" else 23481
            with (SOURCE / name).open(encoding="utf-8-sig", newline="") as stream:
                for row_no, row in enumerate(csv.DictReader(stream), 1):
                    if row_no not in selected[name]:
                        continue
                    record = {"_id": offset + row_no, "DOC_ID": offset + row_no,
                              "TITLE": row["title"], "BODY": row["text"],
                              "SUBJECT": row["subject"], "RAW_DATE": row["date"],
                              "SOURCE_FILE": name, "SOURCE_ROW": row_no}
                    out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    count += 1
    if count != 10000:
        raise ValueError("Wrong subset count")
    manifest = {"dataset_id": provenance["dataset_id"], "source_revision": provenance["revision"],
                "selection": "5000 nonblank BODY rows per source CSV, smallest SHA256(name:1-based-row)",
                "rows": count, "rows_per_source": {name: len(selected[name]) for name in FILES},
                "jsonl_sha256": digest(path), "source_sha256": {x["name"]: x["sha256"] for x in provenance["files"]}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
