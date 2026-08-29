#!/usr/bin/env python3
"""Audit English-translation coverage for ORACC editions, and how much of it
can actually be joined to the local corpus.

Two different things get called "translation coverage" and they differ:

  declared   metadata.json lists a "formats" block; formats["tr-en"] holds the
             text ids the project says have an English translation.
  joinable   a translation you can actually obtain and align. ORACC's per-text
             XTR URLs do not resolve, so in practice this means the published
             TEI corpus export, which carries <div3 type="tr"> units with
             xtr:sref / xtr:eref references into the transliteration.

Those references are the same values as the "ref" on a corpusjson
d/line-start node, so alignment is by LINE RANGE, not by line: measured span
is a median of 5 lines. Do not model translation as a line feature.

Note the TEI exports are misnamed: riao-teiCorpus-*.zip contains the RINAP
texts too. Fetch it from
    http://oracc.museum.upenn.edu/riao/downloads/
and unzip the XML somewhere, then point --tei at that directory.

Usage:
    scripts/audit_translations.py [--data DATA_DIR] [--tei TEI_DIR]
                                  [--projects riao rinap]
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict


def populated_editions(subdir):
    """Q-ids under subdir/corpusjson that contain at least one word."""
    out = set()
    for fp in glob.glob(os.path.join(subdir, "corpusjson", "*.json")):
        try:
            doc = json.load(open(fp, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        stack, n = [doc], 0
        while stack and not n:
            x = stack.pop()
            if x.get("node") == "l":
                n = 1
            stack.extend(x.get("cdl") or [])
        if n:
            out.add(os.path.basename(fp)[:-5])
    return out


def declared(subdir):
    md = os.path.join(subdir, "metadata.json")
    if not os.path.isfile(md):
        return set()
    try:
        fmt = (json.load(open(md, encoding="utf-8")).get("formats") or {})
    except (json.JSONDecodeError, OSError):
        return set()
    return set(fmt.get("tr-en") or [])


def tei_units(tei_dir):
    """subproject -> {q: n_translation_units} from TEI corpus exports."""
    found = defaultdict(dict)
    spans = []
    for path in sorted(glob.glob(os.path.join(tei_dir, "*teiCorpus*.xml"))):
        raw = open(path, encoding="utf-8", errors="replace").read()
        for rec in raw.split("<?xml-stylesheet")[1:]:
            m = re.search(r'<name type="file">([^<]+)</name>', rec)
            if not m:
                continue
            parts = m.group(1).split("/")
            if len(parts) < 3:
                continue
            sub, q = f"{parts[0]}/{parts[1]}", parts[2].replace(".xtf", "")
            units = re.findall(r'<div3[^>]*type="tr"[^>]*subtype="tr"[^>]*>', rec)
            if units:
                found[sub][q] = max(found[sub].get(q, 0), len(units))
                spans += [int(r) for r in
                          (re.search(r'xtr:rows="(\d+)"', u) for u in units) if r
                          for r in [r.group(1)]]
    return found, spans


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--tei", help="directory holding unzipped *teiCorpus*.xml")
    ap.add_argument("--projects", nargs="*", default=["riao", "rinap"])
    ap.add_argument("--include-witnesses", action="store_true",
                    help="also count */sources and */scores, which are score "
                         "editions with no translations and are normally out of scope")
    a = ap.parse_args()

    tei, spans = tei_units(a.tei) if a.tei else ({}, [])

    subdirs = []
    for proj in a.projects:
        for d in sorted(glob.glob(os.path.join(a.data, proj, "*"))):
            if not os.path.isdir(os.path.join(d, "corpusjson")):
                continue
            if not a.include_witnesses and os.path.basename(d) in ("sources", "scores"):
                continue
            subdirs.append(d)
    if not subdirs:
        sys.exit(f"no subprojects with corpusjson under {a.data}")

    print(f"{'subproject':20}{'populated':>10}{'declared':>10}{'in TEI':>8}{'joinable':>10}{'cover%':>8}")
    tp = td = tj = 0
    for d in subdirs:
        key = "/".join(d.split(os.sep)[-2:])
        pop, dec = populated_editions(d), declared(d)
        have = set(tei.get(key, {}))
        join = pop & have
        tp, td, tj = tp + len(pop), td + len(pop & dec), tj + len(join)
        print(f"{key:20}{len(pop):>10}{len(pop & dec):>10}{len(have):>8}"
              f"{len(join):>10}{100*len(join)/max(len(pop),1):>7.1f}%")
    print(f"\npopulated {tp:,}   declared tr-en {td:,} ({100*td/max(tp,1):.1f}%)"
          f"   joinable from TEI {tj:,} ({100*tj/max(tp,1):.1f}%)")
    if spans:
        spans.sort()
        one = sum(1 for x in spans if x == 1)
        print(f"\ntranslation units: {len(spans):,}")
        print(f"  lines spanned  : median {spans[len(spans)//2]}  "
              f"p90 {spans[int(len(spans)*.9)]}  max {spans[-1]}")
        print(f"  spanning 1 line: {one:,} ({100*one/len(spans):.1f}%) "
              f"-> alignment is by line RANGE, not per line")
    elif not a.tei:
        print("\n(pass --tei DIR with the unzipped TEI corpus export for joinable figures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
