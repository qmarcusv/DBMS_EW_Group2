"""Derive one 10K parent/tag corpus from the pinned BIG_TABLE_10K CSV.

Every tag is a deterministic label of a real source field. Optional tags express
presence or Y values; no news or free-text field is invented for this workload.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "local_data/derived/BIG_TABLE_10K.csv"
OUT = ROOT / "local_data/derived/uc6"
EXPECTED_HASH = "7f41f9d5a36b932a25101cc8929aad540a3f9f76ae68b5d434a221b7d6d4f116"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if digest(SOURCE) != EXPECTED_HASH:
        raise ValueError("BIG_TABLE_10K source hash changed")
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / "parents_10k.jsonl"
    length_dist = Counter()
    tag_freq = Counter()
    selected = {}
    count = 0
    with SOURCE.open(encoding="utf-8-sig", newline="") as src, output.open("w", encoding="utf-8", newline="\n") as dst:
        for row_no, row in enumerate(csv.DictReader(src), 1):
            parent_id = int(row["ID"])
            tags = ["owner:" + row["OWNER"], "type:" + row["OBJECT_TYPE"],
                    "temporary:" + row["TEMPORARY"]]
            if row["GENERATED"] == "Y":
                tags.append("generated:Y")
            if row["SUBOBJECT_NAME"] not in ("", "\\N"):
                tags.append("subobject:present")
            tags = sorted(set(tags))
            if len(tags) < 3 or len(tags) > 5:
                raise ValueError(f"Unexpected tag count at row {row_no}")
            doc = {"_id": parent_id, "PARENT_ID": parent_id, "SOURCE_ROW": row_no,
                   "OWNER": row["OWNER"], "OBJECT_TYPE": row["OBJECT_TYPE"], "tags": tags}
            dst.write(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
            length_dist[len(tags)] += 1
            tag_freq.update(tags)
            selected[parent_id] = set(tags)
    if count != 10000 or len(selected) != 10000:
        raise ValueError("UC6 needs 10000 unique parent IDs")
    queries = {"ONE_TABLE": ["type:TABLE"], "TWO_SYS_TABLE": ["owner:SYS", "type:TABLE"],
               "ONE_TEMP_Y": ["temporary:Y"], "TWO_TABLE_TEMP_Y": ["type:TABLE", "temporary:Y"]}
    expected = {key: sorted(pid for pid, tags in selected.items() if set(values) <= tags)
                for key, values in queries.items()}
    if any(not ids for ids in expected.values()):
        raise ValueError("Empty UC6 workload")
    manifest = {"dataset_id": "BIG_TABLE_10K_UC6_TAGS", "source_dataset_id": "BIG_TABLE_10K",
                "source_csv_sha256": EXPECTED_HASH, "jsonl_sha256": digest(output),
                "parents": count, "tag_rows": sum(k*v for k,v in length_dist.items()),
                "distinct_array_lengths": dict(sorted(length_dist.items())),
                "tag_rule": "owner, type, temporary always; generated:Y and subobject:present only if true; sorted distinct tags",
                "queries": {key: {"tags": values, "count": len(expected[key])} for key,values in queries.items()}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "expected_ids.json").write_text(json.dumps(expected, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
