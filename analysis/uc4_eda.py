"""Read-only EDA for the pinned Fake/True CSV corpus; writes aggregate JSON only.

Run from DBMS_Group2 root: python analysis/uc4_eda.py
No SQL/Mongo objects are created and no source CSV is modified.
"""

from collections import Counter
from datetime import datetime
from hashlib import sha256
import csv
import heapq
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "local_data" / "source" / "fake_real_news"
OUTPUT = ROOT / "results" / "uc4" / "eda" / "summary.json"
FILES = ("Fake.csv", "True.csv")
TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)
DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d-%b-%y")
TERMS = (
    "trump", "president", "election", "government", "health", "climate",
    "database", "fraud", "vaccine", "bitcoin", "congress", "economy",
    "policy", "technology", "security", "russia", "reuters", "news",
    "earthquake", "senate", "market", "court", "military",
)
PHRASES = (
    "white house", "united states", "climate change", "donald trump",
    "stock market", "social media", "health care", "national security",
    "fake news", "prime minister", "federal government", "supreme court",
)
PHRASE_RE = {phrase: re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.I)
             for phrase in PHRASES}


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    lower = int(rank)
    fraction = rank - lower
    return round(ordered[lower] + fraction * (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]), 2)


def distribution(values):
    return {"min": min(values) if values else None,
            "p25": percentile(values, .25), "p50": percentile(values, .5),
            "p75": percentile(values, .75), "p90": percentile(values, .9),
            "p95": percentile(values, .95), "p99": percentile(values, .99),
            "max": max(values) if values else None}


def load_rows(name):
    with (SOURCE / name).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["title", "text", "subject", "date"]:
            raise ValueError(f"Unexpected header in {name}: {reader.fieldnames}")
        for row_no, row in enumerate(reader, 1):
            yield row_no, row


def date_parses(value):
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass
    return False


def sample_key(name, row_no):
    return int.from_bytes(sha256(f"{name}:{row_no}".encode("ascii")).digest(), "big")


def count_candidates(text, terms, phrases):
    words = TOKEN.findall(text)
    terms.update(set(word.lower() for word in words).intersection(TERMS))
    for phrase, pattern in PHRASE_RE.items():
        if pattern.search(text):
            phrases[phrase] += 1
    return len(words)


def main():
    provenance = json.loads((SOURCE / "PROVENANCE.json").read_text(encoding="utf-8"))
    files = {}
    all_text_hashes = Counter()
    all_title_hashes = Counter()
    text_hashes_by_file = {name: set() for name in FILES}
    full_terms, full_phrases = Counter(), Counter()
    heaps = {name: [] for name in FILES}
    total = 0

    for name in FILES:
        stat = {"rows": 0, "eligible_nonblank_text_rows": 0, "blank_text_rows": 0,
                "blank_title_rows": 0, "blank_subject_rows": 0,
                "blank_date_rows": 0, "date_parseable_rows": 0,
                "date_nonstandard_rows": 0, "date_longer_than_32_rows": 0,
                "titles_over_256_chars": 0, "max_date_chars": 0,
                "max_subject_chars": 0, "text_under_100_chars": 0,
                "text_under_50_words": 0, "subjects": Counter(),
                "text_char_lengths": [], "text_word_lengths": [], "title_char_lengths": []}
        for row_no, row in load_rows(name):
            stat["rows"] += 1
            total += 1
            title, text = row["title"] or "", row["text"] or ""
            subject, date = (row["subject"] or "").strip(), (row["date"] or "").strip()
            stat["subjects"][subject or "<blank>"] += 1
            stat["max_date_chars"] = max(stat["max_date_chars"], len(row["date"] or ""))
            stat["max_subject_chars"] = max(stat["max_subject_chars"], len(row["subject"] or ""))
            stat["blank_title_rows"] += not title.strip()
            stat["blank_subject_rows"] += not subject
            stat["blank_date_rows"] += not date
            stat["date_longer_than_32_rows"] += len(date) > 32
            if date:
                parsed = date_parses(date)
                stat["date_parseable_rows"] += parsed
                stat["date_nonstandard_rows"] += not parsed
            stat["titles_over_256_chars"] += len(title) > 256
            stat["title_char_lengths"].append(len(title))
            all_title_hashes[sha256(title.strip().casefold().encode("utf-8")).hexdigest()] += 1
            if not text.strip():
                stat["blank_text_rows"] += 1
                continue
            stat["eligible_nonblank_text_rows"] += 1
            stat["text_char_lengths"].append(len(text))
            words = count_candidates(text, full_terms, full_phrases)
            stat["text_word_lengths"].append(words)
            stat["text_under_100_chars"] += len(text) < 100
            stat["text_under_50_words"] += words < 50
            text_hash = sha256(text.encode("utf-8")).hexdigest()
            all_text_hashes[text_hash] += 1
            text_hashes_by_file[name].add(text_hash)
            key = sample_key(name, row_no)
            heap = heaps[name]
            if len(heap) < 5000:
                heapq.heappush(heap, (-key, row_no))
            elif key < -heap[0][0]:
                heapq.heapreplace(heap, (-key, row_no))
        for metric in ("text_char_lengths", "text_word_lengths", "title_char_lengths"):
            stat[metric] = distribution(stat[metric])
        stat["subjects"] = dict(sorted(stat["subjects"].items()))
        files[name] = stat

    if total != provenance["total_rows"] or any(files[f["name"]]["rows"] != f["rows"]
                                                   for f in provenance["files"]):
        raise ValueError("CSV rows do not match pinned provenance")

    chosen = {name: {row_no for _, row_no in heaps[name]} for name in FILES}
    subset_terms, subset_phrases = Counter(), Counter()
    subset_subjects = Counter()
    subset_lengths, subset_words = [], []
    subset_text_hashes = Counter()
    for name in FILES:
        for row_no, row in load_rows(name):
            if row_no not in chosen[name]:
                continue
            text = row["text"]
            subset_subjects[(row["subject"] or "").strip() or "<blank>"] += 1
            subset_lengths.append(len(text))
            subset_words.append(count_candidates(text, subset_terms, subset_phrases))
            subset_text_hashes[sha256(text.encode("utf-8")).hexdigest()] += 1

    out = {
        "source_revision": provenance["revision"],
        "token_counting_method": "ASCII-letter regex; candidate document frequency only, not SQL/Mongo FTS tokenization",
        "date_parse_formats": list(DATE_FORMATS),
        "total_rows": total,
        "eligible_nonblank_text_rows": sum(x["eligible_nonblank_text_rows"] for x in files.values()),
        "files": files,
        "exact_duplicate_nonblank_text_excess_rows": sum(n - 1 for n in all_text_hashes.values() if n > 1),
        "distinct_texts_present_in_both_files": len(text_hashes_by_file[FILES[0]].intersection(text_hashes_by_file[FILES[1]])),
        "normalized_duplicate_title_excess_rows": sum(n - 1 for n in all_title_hashes.values() if n > 1),
        "full_candidate_term_document_frequency": dict(sorted(full_terms.items())),
        "full_candidate_phrase_document_frequency": dict(sorted(full_phrases.items())),
        "proposed_10k_subset": {
            "selection": "Per file, 5000 nonblank-text rows with smallest SHA256('Fake.csv:<1-based CSV row>' or 'True.csv:<1-based CSV row>') value; no deduplication; sort by source file then row number for DOC_ID assignment",
            "rows": 10000,
            "rows_by_file": {name: len(chosen[name]) for name in FILES},
            "subjects": dict(sorted(subset_subjects.items())),
            "text_char_lengths": distribution(subset_lengths),
            "text_word_lengths": distribution(subset_words),
            "exact_duplicate_text_excess_rows": sum(n - 1 for n in subset_text_hashes.values() if n > 1),
            "candidate_term_document_frequency": dict(sorted(subset_terms.items())),
            "candidate_phrase_document_frequency": dict(sorted(subset_phrases.items())),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: {total} source rows, 10000 proposed subset rows")


if __name__ == "__main__":
    main()
