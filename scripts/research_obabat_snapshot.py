#!/usr/bin/env python3
"""Reproduce the issue #58 OBABAT implementation-snapshot research census.

This is a research utility, not converter code. It measures the frozen
``obabat/atletters`` source as a whole and separately for the exact-P-number
overlap / unmatched partitions accepted in issue #39.
"""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "obabat" / "atletters"
DEFAULT_OVERLAP = ROOT / "docs" / "research" / "issue-39-obabat-overlap.json"
WORD_FIELDS = ("cf", "gw", "sense", "norm", "pos", "epos", "base", "morph", "morph2")
CHILD_KEYS = ("group", "seq", "qualified", "mods")
SOURCE_FIELDS = ("project", "source", "license", "license-url", "more-info")


class ResearchError(ValueError):
    pass


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _sign_leaves(entries):
    for g in entries:
        kids = [k for k in CHILD_KEYS if k in g]
        if kids and g.get("utf8"):
            yield g
        elif kids:
            for key in kids:
                yield from _sign_leaves(g[key])
        elif "v" in g or "s" in g or "x" in g:
            yield g


def _scan_document(path: Path) -> dict[str, object]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    counts = Counter(documents=1)
    langs = Counter()
    dtypes = Counter()
    ctypes = Counter()
    stack = [doc]
    while stack:
        node = stack.pop()
        kind = node.get("node")
        if kind == "l":
            counts["words"] += 1
            f = node.get("f") or {}
            for field in WORD_FIELDS:
                if f.get(field):
                    counts[field] += 1
            if node.get("sig"):
                counts["sig"] += 1
            if f.get("lang"):
                langs[f["lang"]] += 1
            if not f.get("cf"):
                counts["words_without_cf"] += 1
            for prop in node.get("props") or []:
                if prop.get("name") == "discourse" and prop.get("value"):
                    counts["discourse"] += 1
            for sign in _sign_leaves(f.get("gdl") or []):
                counts["signs"] += 1
                if sign.get("utf8"):
                    counts["utf8"] += 1
                if sign.get("role") == "logo":
                    counts["logo"] += 1
                if sign.get("break"):
                    counts[f"break:{sign['break']}"] += 1
        elif kind == "d":
            dtypes[node.get("type", "?")] += 1
        elif kind == "c":
            ctypes[node.get("type", "?")] += 1
        stack.extend(node.get("cdl") or [])
    return {
        "counts": counts,
        "languages": langs,
        "dtypes": dtypes,
        "ctypes": ctypes,
        "source": {key: doc.get(key) for key in SOURCE_FIELDS},
        "textid": doc.get("textid"),
    }


def _merge(scans, ids):
    counts = Counter()
    langs = Counter()
    dtypes = Counter()
    ctypes = Counter()
    for pid in sorted(ids):
        item = scans[pid]
        counts.update(item["counts"])
        langs.update(item["languages"])
        dtypes.update(item["dtypes"])
        ctypes.update(item["ctypes"])
    words = counts["words"]
    return {
        "counts": dict(sorted(counts.items())),
        "coverage_pct": {
            field: round(100 * counts[field] / words, 4) if words else 0.0
            for field in ("cf", "gw", "sense", "norm", "pos", "epos", "sig")
        },
        "languages": dict(sorted(langs.items())),
        "dtypes": dict(sorted(dtypes.items())),
        "ctypes": dict(sorted(ctypes.items())),
    }


def build_report(corpus_dir=DEFAULT_CORPUS, overlap_path=DEFAULT_OVERLAP):
    corpus_dir = Path(corpus_dir)
    overlap_path = Path(overlap_path)
    corpus_path = corpus_dir / "corpus.json"
    catalogue_path = corpus_dir / "catalogue.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    overlap = json.loads(overlap_path.read_text(encoding="utf-8"))

    members = corpus.get("members")
    cat_members = catalogue.get("members")
    if not isinstance(members, dict) or not isinstance(cat_members, dict):
        raise ResearchError("corpus/catalogue members must be maps")
    member_ids = set(members)
    overlap_ids = set(overlap.get("overlap_ids") or [])
    unmatched_ids = set(overlap.get("not_in_pinned_nino_ids") or [])
    if overlap_ids & unmatched_ids or overlap_ids | unmatched_ids != member_ids:
        raise ResearchError("accepted overlap manifest does not partition corpus members")

    expected_blob = overlap["sources"]["oracc_tf"]["blob_sha"]
    actual_blob = _git_blob_sha(corpus_path)
    if actual_blob != expected_blob:
        raise ResearchError(
            f"corpus.json pin changed: expected {expected_blob}, got {actual_blob}"
        )

    corpusjson_dir = corpus_dir / "corpusjson"
    actual_files = {path.stem for path in corpusjson_dir.glob("P*.json")}
    expected_files = {
        Path(relative).stem for relative in members.values()
    }
    if actual_files != expected_files or expected_files != member_ids:
        raise ResearchError("corpus membership and corpusjson files differ")

    scans = {}
    source_mismatches = []
    textid_mismatches = []
    expected_source = {key: corpus.get(key) for key in SOURCE_FIELDS}
    for pid, relative in sorted(members.items()):
        scan = _scan_document(corpus_dir / relative)
        scans[pid] = scan
        if scan["textid"] != pid:
            textid_mismatches.append([pid, scan["textid"]])
        if scan["source"] != expected_source:
            source_mismatches.append(pid)

    catalogue_ids = set(cat_members)
    id_text_mismatches = sorted(
        pid for pid, row in cat_members.items() if row.get("id_text") != pid
    )
    project_mismatches = sorted(
        pid for pid, row in cat_members.items() if row.get("project") != corpus.get("project")
    )
    designations = Counter(
        row.get("designation") for row in cat_members.values() if row.get("designation")
    )
    designation_collisions = {
        value: count for value, count in sorted(designations.items()) if count > 1
    }

    return {
        "schema_version": 1,
        "dataset": "obabat/atletters",
        "source": {
            "corpus_blob_sha": actual_blob,
            "accepted_overlap_blob_sha": expected_blob,
            "project": corpus.get("project"),
            "license": corpus.get("license"),
            "license_url": corpus.get("license-url"),
            "timestamp": corpus.get("UTC-timestamp"),
            "document_source_metadata_mismatches": source_mismatches,
            "textid_mismatches": textid_mismatches,
        },
        "membership": {
            "corpus_members": len(member_ids),
            "corpusjson_files": len(actual_files),
            "overlap_ids": len(overlap_ids),
            "not_in_pinned_nino_ids": len(unmatched_ids),
        },
        "catalogue": {
            "members": len(catalogue_ids),
            "missing_from_catalogue": sorted(member_ids - catalogue_ids),
            "catalogue_only": sorted(catalogue_ids - member_ids),
            "id_text_mismatches": id_text_mismatches,
            "project_mismatches": project_mismatches,
            "designation_collision_count": len(designation_collisions),
            "designation_collisions": designation_collisions,
        },
        "all": _merge(scans, member_ids),
        "overlap": _merge(scans, overlap_ids),
        "not_in_pinned_nino": _merge(scans, unmatched_ids),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--overlap", type=Path, default=DEFAULT_OVERLAP)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.corpus_dir, args.overlap)
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
