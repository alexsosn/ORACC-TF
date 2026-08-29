# Which ORACC projects are worth converting to Text-Fabric?

**Date:** 2026-08-29
**Scope:** all 33 ORACC projects / 141 corpora in `data/`, measured directly.

---

## Summary

The existing cuneiform Text-Fabric corpora — `Nino-cunei/oldbabylonian`,
`Nino-cunei/ninmed`, `Nino-cunei/uruk`, `DT-UCPH/cuc` — are all built from
**ATF transliteration**. Measured against the live datasets, none of them
carries a lemma, part-of-speech, or sense feature. They are sign-level
graphemic corpora with metadata.

ORACC's JSON distribution is a different kind of object. Its CDL (Cuneiform
Document Language) word nodes already carry **citation form, guide word,
sense, normalisation, part of speech, and per-sign Unicode**, produced by the
projects' own editors. Across `data/` that is **3.78 M word tokens, 44.8 % of
them lemmatised** — and in the best projects over 90 %.

So the useful conversion is not "more transliteration in TF". It is
**bringing a lemmatised, sense-annotated layer to cuneiform TF for the first
time**, which is what makes BHSA-style querying possible.

One corpus goes further still: **ETCSRI is fully morpheme-segmented and
morpheme-glossed** (`morph`/`morph2`), which no cuneiform TF corpus has and
which is structurally comparable to BHSA's morphology. It is the single
strongest candidate.

**Recommended first conversion: `etcsri`, then `riao`, then `rinap` editions.**

---

## Method

Every `corpusjson/*.json` in `data/` was parsed and its CDL tree walked —
47,233 text files across 141 corpora. For each corpus I counted lemma (`l`)
nodes and the presence of each annotation field on them, plus the structural
`d` nodes. Reference TF corpora were measured from the loaded datasets
themselves, not from their READMEs.

Scan scripts: `scan.py` / `scan2.py` (kept in the session scratchpad; the
logic is ~40 lines of stdlib `json` and is reproduced in the appendix below).

---

## What the reference corpora actually contain

| corpus | slot | node types | size | lemma? | translation? |
|---|---|---|---|---|---|
| `Nino-cunei/oldbabylonian` | sign | document, face, line, word, cluster, sign | 1,285 docs / 76,505 words / 203,219 signs | **no** | yes (`translation@en`, line level) |
| `DT-UCPH/cuc` (Ugaritic) | sign | tablet, column, line, word, sign | 279 tablets / 27,770 words / 146,017 signs | **no** | no |
| `Nino-cunei/ninmed` | — | Nineveh Medical Encyclopaedia, ATF-derived | 159 texts in ORACC terms | **no** | — |
| `Nino-cunei/uruk` | — | proto-cuneiform, CDLI-derived (archived Oct 2025) | ~5,000 tablets | **no** | no |
| `ETCBC/bhsa` | word | book, chapter, verse, half_verse, sentence, clause, phrase, subphrase, lex, … (13 types) | 426,568 words | yes + full syntax | yes |

`oldbabylonian`'s feature set is graphemic and rich in exactly the places ATF
is rich — `damage`, `missing`, `supplied`, `excised`, `uncertain`, `det`,
`langalt`, `flags`, `collated`, plus CDLI catalogue metadata (`period`,
`genre`, `material`, `museumcode`, `ARK`). There is no `lex`, `sp`, or
`gloss` equivalent anywhere in it.

BHSA is the model to aim at: a slot layer plus **linguistic** node types and a
separate `lex` node type. ORACC's data can reach part of the way there;
cuneiform ATF cannot reach it at all.

## What ORACC's CDL adds

A single word node from `saao/saa01`:

```json
{ "node": "l", "frag": "⸢a⸣-bat", "ref": "P224485.2.1",
  "f": { "lang": "akk-x-neoass", "form": "a-bat",
         "cf": "awātu", "gw": "word", "sense": "word",
         "norm": "abat", "pos": "N", "epos": "N",
         "gdl": [ {"v":"a","utf8":"𒀀","break":"damaged","delim":"-"},
                  {"v":"bat","utf8":"𒁁"} ] },
  "props": [ {"name":"discourse","value":"body"} ] }
```

That maps onto TF features almost one-to-one, and it supplies six things no
existing cuneiform TF corpus has: `cf` (lemma), `gw`, `sense`, `norm`, `pos`,
and a discourse label. `gdl` preserves the sign level, with `utf8` giving the
cuneiform character and `break` carrying the damage state — so **nothing from
the ATF-style model is lost**.

Structural `d` nodes supply the section hierarchy directly: 25,497 `object`,
51,567 `surface`, 32,629 `column`, **900,641 `line-start`**, plus 270 k
`cell-start`/`cell-end` (tabular texts) and 89,748 `field-start`/`field-end`.

Every project also ships `gloss-qpn.json` — a proper-noun glossary — alongside
its language glossary, i.e. a **ready-made named-entity layer** (e.g. `balt`
1,554 QPN entries, `babcity` 986).

---

## Inventory, ranked by lemmatisation

Score/source subprojects excluded (see below). Projects under 4,000 words omitted.

| project | subs | texts | words | lines | lemma % | pos % | morph % | unicode % | languages |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| `saao` | 22 | 5,055 | 547,670 | 101,263 | 57.2 | 100.0 | 0.0 | 79.4 | akk-x-neoass, akk-x-neobab |
| `rinap` | 6 | 1,174 | 241,656 | 42,502 | 89.7 | 99.5 | 0.4 | 80.7 | akk, sux |
| `adsd` | 5 | 692 | 263,714 | 23,629 | 66.2 | 100.0 | 0.0 | 0.0 | akk |
| `balt` | 1 | 2,990 | 185,175 | 44,723 | 79.6 | 99.7 | 0.0 | 59.1 | akk-x-neobab, arc |
| `tcma` | 29 | 2,179 | 169,061 | 45,414 | 70.2 | 99.2 | 0.0 | 62.2 | akk-x-midass, akk-x-neoass |
| `hbtin` | 1 | 485 | 123,644 | 20,816 | 87.1 | 94.9 | 0.0 | 0.0 | akk-x-ltebab |
| `aemw` | 4 | 2,207 | 131,007 | 40,823 | 62.4 | 72.6 | 0.0 | 78.7 | akk-x-mbperi, uga-040 |
| `riao` | 5 | 904 | 79,319 | 13,724 | 91.2 | 100.0 | 0.0 | 78.3 | akk |
| `cams` | 5 | 659 | 107,935 | 18,353 | 64.4 | 89.5 | 1.6 | 64.8 | akk-x-stdbab, akk-x-ltebab |
| `atae` | 22 | 2,167 | 129,677 | 36,032 | 48.0 | 80.7 | 0.0 | 0.0 | akk-x-neoass, arc |
| `ribo` | 8 | 411 | 60,592 | 15,257 | 89.2 | 99.8 | 2.2 | 86.5 | akk, sux |
| `cmawro` | 4 | 261 | 58,896 | 21,900 | 87.3 | 99.8 | 2.5 | 60.2 | akk-949, akk |
| `asbp` | 2 | 183 | 66,167 | 7,530 | 61.7 | 94.1 | 1.7 | 59.0 | akk-x-stdbab, sux |
| `blms` | 1 | 213 | 41,940 | 9,118 | 69.7 | 92.9 | 38.8 | 0.0 | sux, akk-x-stdbab |
| `etcsri` | 1 | 1,456 | 29,573 | 16,886 | 95.3 | 100.0 | 95.3 | 90.1 | sux, akk |
| `babcity` | 1 | 224 | 28,350 | 5,213 | 87.2 | 100.0 | 0.0 | 0.0 | akk-x-neobab |
| `ccpo` | 1 | 205 | 35,888 | 5,233 | 66.0 | 99.8 | 1.0 | 0.0 | akk-x-stdbab, sux |
| `borsippa` | 1 | 224 | 25,436 | 4,591 | 86.2 | 100.0 | 0.0 | 0.0 | akk-x-neobab, akk-x-neobab-949 |
| `btto` | 1 | 132 | 19,818 | 4,754 | 56.8 | 72.9 | 0.2 | 0.0 | akk, sux |
| `obabat` | 1 | 121 | 9,517 | 3,242 | 93.9 | 99.1 | 0.0 | 0.0 | akk-x-oldbab, akk |
| `rimanum` | 1 | 338 | 10,261 | 4,195 | 81.5 | 99.7 | 12.8 | 0.0 | akk-x-oldbab, sux |
| `ario` | 1 | 173 | 11,713 | 2,374 | 71.2 | 91.3 | 0.0 | 21.3 | peo, akk |
| `suhu` | 1 | 33 | 5,577 | 918 | 79.2 | 100.0 | 0.0 | 77.9 | akk |
| `glass` | 1 | 19 | 4,953 | 993 | 74.8 | 99.9 | 0.0 | 77.9 | akk-x-stdbab, akk-x-midass |
| `akklove` | 1 | 31 | 4,434 | 1,277 | 79.6 | 82.5 | 0.0 | 92.3 | akk-x-oldbab, akk-x-midass |
| `urap` | 1 | 147 | 8,291 | 2,288 | 39.5 | 89.1 | 0.7 | 0.0 | akk-x-oldbab, sux |
| `obta` | 1 | 35 | 5,972 | 810 | 47.7 | 99.9 | 4.0 | 61.9 | akk-x-oldbab, sux |
| `csik` | 1 | 711 | 8,130 | 3,379 | 17.2 | 18.8 | 0.0 | 0.0 | akk-x-stdbab, akk-x-stdbab-949 |
| `caspo` | 2 | 286 | 38,479 | 7,888 | 0.0 | 0.0 | 0.0 | 13.9 | akk-x-stdbab, akk-x-oldbab |
| `cdli` | 1 | 18,524 | 777,741 | 254,844 | 0.0 | 0.0 | 0.0 | 0.0 | sux, qpc |
| `contrib` | 1 | 345 | 52,743 | 11,298 | 0.0 | 0.0 | 0.0 | 86.4 | akk-x-mbperi, akk-x-stdbab |

---

## Recommendations

### Tier 1 — convert first

**1. `etcsri` — Electronic Text Corpus of Sumerian Royal Inscriptions**
1,456 texts · 29,573 words · 16,886 lines · **95.3 % lemmatised · 95.3 %
morpheme-segmented · 100 % POS · 90.1 % sign Unicode**

The only ORACC corpus with full morphological analysis. Word nodes carry
`base`, `morph` (`N1=kigal.N3=bi.N5=ak.N5=ø`) and `morph2`
(`N1=STEM.N3=3-SG-NH-POSS.N5=GEN.N5=ABS`), plus `para` sentence boundaries on
12.1 % of words. This is the only cuneiform material in `data/` that can
support BHSA-style morphological querying. It is also small enough to be a
clean pilot and prove the CDL→TF pipeline end to end.

**2. `riao` — Royal Inscriptions of Assyria** (5 subprojects)
904 texts · 79,319 words · **91.2 % lemmatised · 100 % POS · 78.3 % Unicode**

The highest-quality multi-subproject block. Genre-homogeneous, single language
(`akk`), consistently annotated across all five parts — so the five convert as
one dataset with a `subproject` feature rather than five datasets.

**3. `rinap` editions** (rinap1–5, rinap5p1 — *not* sources/scores)
1,174 texts · 241,656 words · **89.7 % lemmatised · 99.5 % POS · 80.7 % Unicode**

The largest high-quality block in ORACC. Neo-Assyrian royal inscriptions,
excellent Unicode coverage. Individual parts reach 94.6 % (`rinap5p1`) and
93.2 % (`rinap3`).

### Tier 2 — high value, larger or less uniform

- **`saao`** (22 subprojects, 5,055 texts, **547,670 words**) — the largest
  lemmatised corpus here and the canonical Neo-Assyrian letter archive.
  100 % POS but 57.2 % lemma coverage, uneven across volumes (`saa04` 68 %,
  `saa15` 41 %). Highest absolute payoff; budget for the unevenness.
- **`balt`** (2,990 texts, 185,175 words, 79.6 %) — Neo-Babylonian/Persian/
  Hellenistic administrative and legal texts; large QPN layer.
- **`hbtin`** (485 texts, 123,644 words, 87.1 %) — Hellenistic Uruk, with
  iconographic and onomastic data. Note **0 % Unicode**: sign-level `utf8` is
  absent, so a sign layer would have to come from `gdl` readings alone.
- **`adsd`** (5 subprojects, 692 texts, 263,714 words, 66.2 %) — Astronomical
  Diaries. Unique genre, dense tabular structure (the `cell-*` nodes matter
  here), 100 % POS, but no sign Unicode.
- **`tcma`** (29 subprojects, 2,179 texts, 169,061 words, 70.2 %) — Middle
  Assyrian; the widest subproject spread, useful if per-site partitioning is wanted.

### Tier 3 — small, coherent, low-effort

Good candidates for a themed dataset or for testing the pipeline:
`obabat` (93.9 %), `babcity` (87.2 %), `borsippa` (86.2 %), `rimanum` (81.5 %),
`suhu` (79.2 %), `akklove` (79.6 %), `glass` (74.8 %).

---

## What to skip, and why

**`cdli` — skip.** 18,524 texts and 777,741 words, but **0 % lemmatised**: it
is a bulk transliteration dump with no annotation layer. It is also the source
that `Nino-cunei/oldbabylonian` and `Nino-cunei/uruk` were already built from,
so converting it would duplicate existing TF datasets while adding nothing.
It is 1.36 GB of the repo and contributes no linguistic signal.

**Score and source subprojects — skip.** These are manuscript-witness
transliterations (score editions), not annotated editions. All are 0 % lemmatised:

| subproject | texts | words | lemma % |
|---|--:|--:|--:|
| `rinap/sources` | 2,206 | 262,717 | 0.0 |
| `rinap/scores` | 129 | 91,617 | 0.0 |
| `cmawro/sources` | 511 | 84,990 | 0.0 |
| `ribo/sources` | 400 | 41,145 | 0.0 |
| `ribo/bab7scores` | 40 | 14,876 | 0.0 |
| `ribo/scores` | 7 | 1,499 | 0.0 |

**Other 0 %-lemmatised corpora** (excluded from the ranking above):
`contrib/amarna` (345 texts, 52,743 words) and `caspo` (267 texts, 33,666
words) ship transliteration without annotation.

**`asbp/ninmed` — already exists, but a re-conversion is a genuine upgrade.**
`Nino-cunei/ninmed` is the same corpus (Nineveh Medical Encyclopaedia) built
from ATF. The ORACC version here is 62.7 % lemmatised with 95.7 % POS, so
converting from CDL would *add* the lemma/sense layer the existing dataset
lacks rather than duplicate it. Worth doing after Tier 1, and it gives a
direct A/B comparison against an existing Nino-cunei dataset — useful for
validating the pipeline.

---

## Limitations to plan around

**1. The JSON distribution ships no running translations.** This is the
biggest gap and it is easy to miss. `index-tra.json` looks like a translation
file but is a *stemmed word index* over translations:

```json
{"key": "architrav", "count": "9",
 "instances": ["rinap/rinap3:Q003520_project-en_project-en.58.52", ...]}
```

The references reach line level, so a bag-of-stems per line is recoverable,
but the readable translation is not in the open-data JSON at all. I confirmed
this by searching the full corpusjson key inventory — there is no `tr`,
`translation`, or `@en` node anywhere.

This matters because `Nino-cunei/oldbabylonian` *does* have `translation@en`.
An ORACC-derived TF corpus would beat it on lemmatisation and lose to it on
translation, unless translations are sourced separately — from the ORACC ATF
sources on GitHub, or from the project HTML.

**2. Lemma coverage is a ceiling, not a floor.** The 44.8 % overall figure is
dragged down by `cdli` and the score subprojects, but even good projects leave
5–40 % of tokens unlemmatised (broken or unidentifiable words). A TF build must
represent "word present, lemma unknown" explicitly rather than dropping tokens.

**3. Sign-level Unicode is inconsistent.** `utf8` in `gdl` ranges from 90.1 %
(`etcsri`) to 0 % (`hbtin`, `adsd`, `babcity`, `borsippa`, `atae`). A
sign-slot TF model like `oldbabylonian`'s is only fully realisable where
`utf8` is present; elsewhere the slot must fall back to the `v` reading.

**4. Possible overlap with `Nino-cunei/oldbabylonian`.** That dataset is
CDLI Old Babylonian letters (1,285 documents). `obabat/atletters` here is 121
Old Babylonian archival letters. The scale differs by an order of magnitude,
but the P-number sets should be checked for overlap before converting
`obabat` — compare its `catalogue.json` P-numbers against the `pnumber`
feature of the `akkadian_oldbabylonian` dataset.

---

## Proposed TF mapping

A model that stays compatible with `Nino-cunei/oldbabylonian` while adding the
ORACC layer:

| TF node type | CDL source | notes |
|---|---|---|
| `document` | `corpusjson/<P|Q>.json` | section level 1; `pnumber` from filename |
| `object` | `d` node `type=object` | tablet, prism, cylinder … |
| `surface` | `d` node `type=surface`/`obverse`/`reverse` | section level 2 (cf. `face`) |
| `column` | `d` node `type=column` | |
| `line` | `d` node `type=line-start` | section level 3; `label` → `lnno` |
| `cell` | `d` node `cell-start`/`cell-end` | needed for `adsd`, `obta` tabular texts |
| `word` | `l` node | |
| `lex` | distinct `cf`+`gw`+`pos` | BHSA-style lexeme node; back it with `gloss-*.json` |
| `sign` (**slot**) | `gdl` entry | fall back to `v` where `utf8` absent |

Word features: `cf`, `gw`, `sense`, `norm`, `pos`, `epos`, `lang`, `form`,
`frag`, `sig`, `discourse` (from `props`), and where present `base`, `morph`,
`morph2`. Sign features: `reading` (`v`), `readingu` (`utf8`), `damage`
(from `break`), `delim`. Document features from `catalogue.json`: period,
genre, provenience, museum number, measurements.

Naming the features after `oldbabylonian`'s where they coincide (`readingu`,
`lnno`, `pnumber`, `period`, `genre`) would let queries port between the
datasets.

---

## Suggested next steps

1. Build the CDL→TF walker against **`etcsri`** — smallest Tier 1 corpus,
   richest annotation, so it exercises every feature including morphology.
2. Validate by round-tripping transliteration back out of TF and diffing
   against `corpusjson` (the same discipline `oldbabylonian` applies to ATF).
3. Run the same pipeline over **`riao`** to prove multi-subproject handling.
4. Decide the translation question before scaling to `saao` — either source
   translations from ORACC ATF, or ship the datasets lemma-only and document it.
5. Re-convert **`asbp/ninmed`** and compare against `Nino-cunei/ninmed` as an
   end-to-end validation against a known-good dataset.

---

## Appendix: reproducing the scan

```python
# for each data/**/corpusjson/*.json, walk the CDL tree
stack = [json.load(open(fp))]
while stack:
    n = stack.pop()
    if n.get("node") == "l":                 # a word
        f = n.get("f") or {}
        # f: cf, gw, sense, norm, pos, epos, lang, form, gdl[], base, morph, morph2
        # n: props[] (discourse), para[] (sentence boundaries)
    elif n.get("node") == "d":               # structure
        n.get("type")                        # line-start, surface, column, object, cell-*
    stack.extend(n.get("cdl") or [])
```
