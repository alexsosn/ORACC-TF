#!/usr/bin/env python3
"""Measure annotation depth across every ORACC corpus in data/.

Walks the CDL tree of every corpusjson file and reports, per project or
subproject, how much of each annotation layer is actually present. This is the
evidence behind docs/research.md: it distinguishes corpora that are genuinely
lemmatised from bulk transliteration dumps, which is what decides whether a
corpus is worth converting to Text-Fabric.

Counted per word (CDL "l") node:
    cf      citation form (the lemma)          norm    normalised form
    gw      guide word                         pos     part of speech
    sense   sense gloss                        base    morphological stem
    morph   morpheme segmentation              morph2  glossed morphemes
    para    sentence/paragraph boundary        discourse   discourse label
    gdl     signs (recursing through group/seq), how many carry utf8,
            how many are logograms, and their break states

Structural CDL "d" nodes (object, surface, column, line-start, cell-*) are
counted too, since they become the TF section hierarchy.

Usage:
    scripts/scan_annotation.py [-o report.json] [--data DATA_DIR] [--csv]

Takes roughly 10 minutes over the full 47k-file corpus.
"""

import argparse
import glob
import json
import os
import sys
from collections import Counter

WORD_FIELDS = ("cf", "gw", "sense", "norm", "pos", "epos", "base", "morph", "morph2")


def sign_leaves(entries):
    """Yield leaf sign entries from a gdl list.

    gdl is a tree, not a flat list: logograms nest their signs under "group"
    and determinatives/numerals under "seq". Iterating the top level only
    misses every sign inside those wrappers - about 11% of signs in RIAO and
    RINAP, and it undercounts Unicode coverage badly, since the wrapper node
    itself carries no utf8.
    """
    for g in entries:
        if "group" in g:
            yield from sign_leaves(g["group"])
        elif "seq" in g:
            yield from sign_leaves(g["seq"])
        else:
            yield g


def scan_corpus(cdir):
    st = Counter()
    langs, dtypes, poss = Counter(), Counter(), Counter()
    for fp in glob.glob(os.path.join(cdir, "*.json")):
        try:
            doc = json.load(open(fp, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            st["unreadable"] += 1
            continue
        st["texts"] += 1
        stack = [doc]
        while stack:
            n = stack.pop()
            kind = n.get("node")
            if kind == "l":
                st["words"] += 1
                f = n.get("f") or {}
                for key in WORD_FIELDS:
                    if f.get(key):
                        st[key] += 1
                if f.get("lang"):
                    langs[f["lang"]] += 1
                if f.get("pos"):
                    poss[f["pos"]] += 1
                if n.get("para"):
                    st["para"] += 1
                for p in n.get("props") or []:
                    if p.get("name") == "discourse" and p.get("value"):
                        st["discourse"] += 1
                for g in sign_leaves(f.get("gdl") or []):
                    st["signs"] += 1
                    if g.get("utf8"):
                        st["utf8"] += 1
                    if g.get("role") == "logo":
                        st["logo"] += 1
                    if g.get("break"):
                        st["break_" + g["break"]] += 1
            elif kind == "d":
                dtypes[n.get("type", "?")] += 1
            stack.extend(n.get("cdl") or [])
    out = dict(st)
    out["langs"] = dict(langs.most_common(8))
    out["dtypes"] = dict(dtypes.most_common(12))
    out["pos_values"] = dict(poss.most_common(15))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("-o", "--output", default="annotation-report.json")
    ap.add_argument("--csv", action="store_true", help="also print a CSV summary to stdout")
    a = ap.parse_args()

    dirs = sorted(glob.glob(os.path.join(a.data, "**", "corpusjson"), recursive=True))
    if not dirs:
        sys.exit(f"no corpusjson directories under {a.data}")

    report = {}
    for cdir in dirs:
        name = os.path.relpath(os.path.dirname(cdir), a.data)
        st = scan_corpus(cdir)
        if not st.get("words"):
            continue
        report[name] = st
        w = st["words"]
        print(f"{name:28} texts={st['texts']:>6} words={w:>9,} "
              f"lemma={100*st.get('cf',0)/w:5.1f}% pos={100*st.get('pos',0)/w:5.1f}% "
              f"morph={100*st.get('morph',0)/w:5.1f}%", flush=True)

    with open(a.output, "w") as f:
        json.dump(report, f, indent=1)
    print(f"\nwrote {a.output}  ({len(report)} corpora)")

    if a.csv:
        print("\ncorpus,texts,words,lemma_pct,pos_pct,sense_pct,morph_pct,utf8_pct")
        for name, st in sorted(report.items(), key=lambda kv: -kv[1]["words"]):
            w = st["words"]
            print(f"{name},{st['texts']},{w},"
                  f"{100*st.get('cf',0)/w:.1f},{100*st.get('pos',0)/w:.1f},"
                  f"{100*st.get('sense',0)/w:.1f},{100*st.get('morph',0)/w:.1f},"
                  f"{100*st.get('utf8',0)/max(st.get('signs',0),1):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
