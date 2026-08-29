#!/usr/bin/env python3
"""Split oversized ORACC index JSON files into GitHub-safe shards, and rejoin them.

ORACC index files (index-cat.json, index-lem.json, index-txt.json, ...) are a
single JSON object shaped like:

    {
      <metadata: type, project, source, license, UTC-timestamp, name, ...>,
      "keys": [ {"key": ..., "count": ..., "instances": [...]}, ... ],
      "map":  { "<raw form>": "<normalised form>", ... }        # optional
    }

`cdli/index-cat.json` is 545 MB, which GitHub refuses to accept (hard limit is
100 MB per file). This tool shards the "keys" array by the first character of
each key, so a consumer can still resolve a key to exactly one shard without
scanning: key "p137994" always lives in keys-p.json.

Each shard is standalone valid JSON and carries the original metadata header,
so no shard is meaningless on its own.

    split   index-cat.json -o index-cat/     # 1 file  -> N shards
    join    index-cat/ -o index-cat.json     # N shards -> 1 file
    verify  index-cat/                       # check shards against manifest

Note on ordering: ORACC emits "keys" in hash order, which carries no meaning.
Sharding groups by prefix, so `join` produces a semantically identical file
whose keys are grouped by shard rather than in the original arbitrary order.
Integrity is therefore checked with an order-independent digest (see below).

Memory: loads the whole file (~6x the file size in RAM; 545 MB needs ~3.5 GB).
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict

MANIFEST = "_index.json"
KEYS_PREFIX = "keys-"
MAP_FILE = "map.json"
DEFAULT_MAX_MB = 90  # GitHub hard-blocks at 100 MB; leave headroom


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def digest_keys(entries):
    """Order-independent digest of the keys array."""
    h = sorted(hashlib.sha1(canon(e).encode()).hexdigest() for e in entries)
    return hashlib.sha1("".join(h).encode()).hexdigest()


def digest_map(mapping):
    return hashlib.sha1(canon(mapping).encode()).hexdigest()


def bucket_of(key, depth=1):
    """Shard label for a key: lowercased ASCII-alphanumeric prefix, else 'other'."""
    if not key:
        return "other"
    label = ""
    for ch in key[:depth].lower():
        if not (ch.isascii() and ch.isalnum()):
            return "other"
        label += ch
    return label or "other"


def dump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def split(src, outdir, max_mb=DEFAULT_MAX_MB, dry_run=False):
    with open(src, encoding="utf-8") as f:
        doc = json.load(f)

    if "keys" not in doc:
        sys.exit(f"{src}: no top-level 'keys' array - not an ORACC index file")

    entries = doc["keys"]
    mapping = doc.get("map")
    meta = {k: v for k, v in doc.items() if k not in ("keys", "map")}
    limit = max_mb * 1024 * 1024

    # Pass 1: one-character buckets, measured by serialised size.
    buckets = defaultdict(list)
    sizes = defaultdict(int)
    for e in entries:
        b = bucket_of(e.get("key", ""))
        buckets[b].append(e)
        sizes[b] += len(canon(e))

    # Pass 2: subdivide any bucket that would still exceed the limit.
    final = {}
    for b, ents in buckets.items():
        if sizes[b] <= limit or b == "other":
            final[b] = ents
            continue
        for e in ents:
            final.setdefault(bucket_of(e.get("key", ""), depth=2), []).append(e)

    shards = sorted(final)
    manifest = dict(meta)
    manifest["split"] = {
        "tool": "scripts/shard_index.py",
        "scheme": "keys[] sharded by lowercased alphanumeric key prefix; 'other' = non-alphanumeric or empty key",
        "source_file": os.path.basename(src),
        "shards": shards,
        "has_map": mapping is not None,
        "note": "join reorders keys by shard; ORACC's original order is hash order and carries no meaning",
        "verify": {
            "keys_count": len(entries),
            "keys_digest": digest_keys(entries),
            "map_count": len(mapping) if mapping is not None else 0,
            "map_digest": digest_map(mapping) if mapping is not None else None,
        },
    }

    if dry_run:
        print(f"{len(shards)} shards (dry run, nothing written)")
        for b in shards:
            print(f"  {KEYS_PREFIX}{b}.json  {sum(len(canon(e)) for e in final[b])/1048576:7.1f} MB  {len(final[b]):>9,} entries")
        return

    os.makedirs(outdir, exist_ok=True)
    dump(manifest, os.path.join(outdir, MANIFEST))
    if mapping is not None:
        dump({**meta, "section": "map", "map": mapping}, os.path.join(outdir, MAP_FILE))
    for b in shards:
        dump({**meta, "section": "keys", "shard": b, "keys": final[b]},
             os.path.join(outdir, f"{KEYS_PREFIX}{b}.json"))

    total = sum(os.path.getsize(os.path.join(outdir, p)) for p in os.listdir(outdir))
    biggest = max(os.listdir(outdir), key=lambda p: os.path.getsize(os.path.join(outdir, p)))
    print(f"split {src} -> {outdir}")
    print(f"  {len(shards)} key shards{' + map.json' if mapping is not None else ''} + {MANIFEST}")
    print(f"  {os.path.getsize(src)/1048576:.1f} MB -> {total/1048576:.1f} MB in {len(os.listdir(outdir))} files")
    print(f"  largest: {biggest} ({os.path.getsize(os.path.join(outdir, biggest))/1048576:.1f} MB)")


def load_shards(indir):
    with open(os.path.join(indir, MANIFEST), encoding="utf-8") as f:
        manifest = json.load(f)
    spec = manifest["split"]
    entries = []
    for b in spec["shards"]:
        with open(os.path.join(indir, f"{KEYS_PREFIX}{b}.json"), encoding="utf-8") as f:
            entries.extend(json.load(f)["keys"])
    mapping = None
    if spec.get("has_map"):
        with open(os.path.join(indir, MAP_FILE), encoding="utf-8") as f:
            mapping = json.load(f)["map"]
    return manifest, spec, entries, mapping


def verify(indir, against=None):
    manifest, spec, entries, mapping = load_shards(indir)
    want = spec["verify"]
    ok = True
    for label, got, exp in (
        ("keys count ", len(entries), want["keys_count"]),
        ("keys digest", digest_keys(entries), want["keys_digest"]),
        ("map count  ", len(mapping) if mapping else 0, want["map_count"]),
        ("map digest ", digest_map(mapping) if mapping else None, want["map_digest"]),
    ):
        mark = "ok  " if got == exp else "FAIL"
        if got != exp:
            ok = False
        shown = got if not isinstance(got, int) else f"{got:,}"
        print(f"  [{mark}] {label}  {shown}")

    if against:
        with open(against, encoding="utf-8") as f:
            orig = json.load(f)
        same_keys = digest_keys(orig["keys"]) == digest_keys(entries)
        same_map = digest_map(orig.get("map") or {}) == digest_map(mapping or {})
        print(f"  [{'ok  ' if same_keys else 'FAIL'}] keys match {against}")
        print(f"  [{'ok  ' if same_map else 'FAIL'}] map  match {against}")
        ok = ok and same_keys and same_map

    print("VERIFIED" if ok else "VERIFICATION FAILED")
    return 0 if ok else 1


def join(indir, out):
    manifest, spec, entries, mapping = load_shards(indir)
    meta = {k: v for k, v in manifest.items() if k != "split"}
    doc = dict(meta)
    doc["keys"] = entries
    if mapping is not None:
        doc["map"] = mapping
    dump(doc, out)
    want = spec["verify"]
    ok = len(entries) == want["keys_count"] and digest_keys(entries) == want["keys_digest"]
    print(f"join {indir} -> {out}  ({len(entries):,} keys, {os.path.getsize(out)/1048576:.1f} MB)")
    print("VERIFIED against manifest" if ok else "WARNING: digest mismatch")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("split", help="shard a large ORACC index file")
    s.add_argument("input")
    s.add_argument("-o", "--outdir", help="default: input path without .json")
    s.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--replace", action="store_true",
                   help="delete the source file once the shards verify")

    j = sub.add_parser("join", help="reassemble shards into one file")
    j.add_argument("indir")
    j.add_argument("-o", "--output", required=True)

    v = sub.add_parser("verify", help="check shards against their manifest")
    v.add_argument("indir")
    v.add_argument("--against", help="also compare against an original index file")

    a = ap.parse_args()
    if a.cmd == "split":
        default = a.input[:-5] if a.input.endswith(".json") else a.input + ".shards"
        outdir = a.outdir or default
        split(a.input, outdir, a.max_mb, a.dry_run)
        if a.replace and not a.dry_run:
            if verify(outdir) == 0:
                os.remove(a.input)
                print(f"removed {a.input}")
            else:
                sys.exit("shards did not verify; source file left in place")
        return 0
    if a.cmd == "join":
        return join(a.indir, a.output)
    return verify(a.indir, a.against)


if __name__ == "__main__":
    sys.exit(main())
