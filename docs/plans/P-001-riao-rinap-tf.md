---
id: P-001
title: TDD implementation of a joined RIAO + RINAP TF module
type: plan
status: draft
priority: P0
depends_on: [R-001]
blocks: [P-002, P-003]
updated: 2026-08-29
---

# TDD implementation plan: a joined RIAO + RINAP Text-Fabric module

**Status:** plan, revision 3 (two rounds of independent review). Not yet implemented.
**Target dataset:** `assyrian-royal-inscriptions` — RIAO parts 1–5 and RINAP
1–5 (+5p1) as one continuous TF corpus.

> **Revision notes.**
> *Rev 2:* revision 1 defined a sign slot as "any GDL object with no
> `group`/`seq` child". A reviewer showed this is false (§2.3); the sign
> ontology, lexeme key, catalogue join and document cardinality were reworked.
> *Rev 3:* a second review showed translations are **not** out of scope. They
> are declared for 99.9 % of populated editions and 89.2 % are joinable today
> from one published TEI download, aligned by line range (§2.11). Translations
> become milestone M9, and a licence conflict is recorded.
> §9 records what changed and which review points did not hold.

---

## 1. Why joined

RIAO covers Assyria from its origins to **745 BC**; RINAP begins at **744 BC**
and runs to 612. Same genre (official royal inscriptions), same language
(Akkadian, with a Sumerian minority), same ORACC annotation conventions.
Joined, they are a genre-uniform diachronic corpus spanning ~1,500 years,
which no existing cuneiform TF dataset offers.

---

## 2. Ground truth

Every figure below was measured over all 2,081 edition files in
`data/riao/ria[1-5]` and `data/rinap/rinap[1-5]`, `rinap5p1` — not sampled.

### 2.1 Four cardinalities, not one

Revision 1 said "2,078 documents". That conflates *parseable* with
*populated*. Valid JSON files exist that contain no transliteration at all:
the `text → discourse → sentence` skeleton is present but the body is empty.

| stage | count |
|---|--:|
| source edition files | 2,081 |
| parseable JSON | 2,078 (3 are zero bytes) |
| **populated editions** (≥1 word) | **1,845** |
| **stub editions** (0 words) | **233** |

The stubs are 11 % of parseable files and cluster in runs (e.g.
`riao/ria4/Q000000.json`, `Q009474.json`, `Q005711`–`Q005713`). They must be
reported as their own class, not silently counted as documents. A stub has no
textual position, so it cannot yield a normal section path — which is exactly
why M6's "every node has a valid section path" invariant has to be stated
against *populated* documents.

**Decision:** emit stubs as metadata-only `document` nodes with `populated=0`
and no slots, and record all four cardinalities in the build report.

### 2.2 Three files are zero bytes

`rinap/rinap1/corpusjson/{Q003424,Q006331,Q006333}.json` are 0 bytes as
shipped by ORACC (extraction was verified clean against the ZIP manifests).
Skip and report; do not crash.

### 2.3 GDL is a tree of *semantically distinct* objects — this is the blocker

Revision 1 used this rule:

```python
if "group" in g:   recurse(g["group"])
elif "seq" in g:   recurse(g["seq"])
else:              yield g          # <- "a leaf is a sign"
```

**That rule is wrong.** It assumes any object with children is a structural
wrapper carrying no sign data. The numeral fixture chosen to test numerals
disproves it:

```json
{"n":"n", "sexified":"1(diš)", "form":"1", "utf8":"𒁹",
 "id":"Q005620.44.1.0", "seq":[{"r":"1"}]}
```

The **parent** is the sign — it holds the Unicode character, the rendered
form, the sexagesimal reading and the id. The rule recurses past it and emits
`{"r":"1"}`: no id, no `utf8`, no reading. Verified: this happens **6,584
times**. Two `q`/`qualified` structures and two compound `c` nodes
(`{"c":"|URU×GU|","utf8":"𒍀","seq":[{"s":"URU"},{"o":"containing"},{"s":"GU"}]}`)
fail the same way — and for the compound the rule would also emit the
**operator** `{"o":"containing"}` as if it were a sign.

Full inventory of GDL object kinds across the corpus:

| kind | children | count | disposition |
|---|---|--:|---|
| `v` syllabic sign | — | 589,030 | **slot** |
| `s` sign name (inside logogram) | — | 183,264 | **slot** |
| `logo` logogram wrapper | `group` | 125,769 | structural — recurse |
| `det` determinative wrapper | `seq` | 52,942 | structural — recurse |
| `x` unreadable stretch | — | 13,777 | **slot** (see below) |
| `n` numeral | `seq` | 6,584 | **slot from parent**, do not recurse |
| `r` rendering reference | — | 6,584 | not a sign — discard |
| `alternation` | `group` | 91 | structural — recurse |
| `ligature` | `group` | 36 | structural — recurse |
| bare `group` | `group` | 30 | structural — recurse |
| `q` qualified sign | `qualified` | 3 | **slot from parent** where it carries `utf8` |
| compound `c` (`\|URU×GU\|`) | `seq` | 2 | **slot from parent**, do not recurse |
| `o` operator (`containing`, `×`) | — | 2 | not a sign — discard |

Under a corrected rule — *an object bearing `utf8` **and** children is itself
the sign; an object with children and no `utf8` is a wrapper; `r` and `o`
leaves are rendering/operator references* — the corpus yields:

| | rev 1 rule | corrected |
|---|--:|--:|
| slots | 792,652 | **792,651** |
| of which composite (numeral/qualified/compound) | 0 | 6,588 |
| structural wrappers (no slot) | — | 178,869 |
| rendering/operator (no slot) | — | 6,586 |
| slots carrying `utf8` | 97.4 % | **98.3 %** |
| `utf8` excluding `x` placeholders | — | **100.0 %** |

**The count is a near-coincidence — off by one — because the rule swapped
6,584 numeral parents for their 6,584 children one for one.** The identity of
6,588 slots changes completely: from contentless rendering references to real
signs with Unicode, ids and sexagesimal readings. Passing a count-based
regression test would have proved nothing. This is the reviewer's central
point and it stands.

**Open decision to settle before M6 pins anything:** whether `x` (13,777
unreadable stretches) is a sign slot. It occupies textual position, so
dropping it breaks line reconstruction; but it is a breakage marker, not a
sign. Recommendation: emit it as a slot with `type=ellipsis` so positions stay
intact, and report Unicode coverage both ways (98.3 % / 100.0 %).

### 2.4 `d` nodes are flat markers, not containers

A text is a `c type=text` wrapper containing a **flat stream** where `d`
markers and `l` words are siblings:

```
c type=text
  d type=object            <- marker, no children
  d type=surface
  c type=discourse
    c type=sentence implicit=yes
      d type=line-start  ref=Q004473.1  label='1'
      l  'aš-šur'   cf='Aššur'  pos='DN'
      d type=line-start  ref=Q004473.2  label='2'
      c type=phrase                       <- a real container
        l 'KUR'      cf='mātu'   pos='N'
        l 'aš-šur'   cf='Aššur'  pos='GN'
```

A line "contains" every word until the next `line-start`. The converter must
be a **stateful streaming walk**, not a recursive descent mapping JSON nesting
onto TF nesting.

Marker counts (RIAO+RINAP only): `line-start` 56,226, `nonw` 5,850,
`nonx` 3,375, `surface` 2,298, `object` 2,050, `column` 758. There are **no**
`cell-*` and **no** `line-end` markers in these projects.

### 2.5 The `c` chunk layer: keep all of it, name none of it `sentence`

| `c` type | count | size |
|---|--:|---|
| `text` | 2,078 | whole file |
| `discourse` | 1,846 | whole body |
| `sentence` | 5,221 | median 20, p90 78, **max 6,303** — **all `implicit: yes`** |
| `phrase` | 4,499 | median 2, p99 5, max 82 |

Not one `sentence` node is editorially marked; every one carries
`implicit: yes`. These are discourse chunks ORACC inserts, not linguistic
sentences, and a 6,303-word "sentence" would break any query that assumes
otherwise.

Revision 1 modelled `sentence` and `phrase` but silently dropped `discourse`.
That is inconsistent — all three come from one ORACC mechanism.

**Decision:** emit a single generic `chunk` node type carrying
`chunk_type` (`text`/`discourse`/`sentence`/`phrase`), `chunk_subtype`,
`implicit`, and `source_id`. Additionally expose `phrase` as its own node type
for query ergonomics — justified because, unlike the others, it is genuinely
phrase-sized (median 2 words). Nothing is named `sentence`. Any `c` type not
in the table above fails the build rather than being dropped.

### 2.6 Unlemmatised words must survive

9.9 % of words have no `cf`/`gw`/`sense`/`norm`/`sig` but do have `form`,
`gdl`, and usually `pos`: `u` 26,176, `n` 3,862, absent 1,114, `X` 616.
Dropping them would delete 10 % of the corpus and corrupt every offset.

### 2.7 One word can carry **two to fourteen** lexemes

1,250 words are compound orthographic forms — one written form spelling
several lemmas, linked by `cof-head`/`cof-tails`, with analyses joined by `&`
in `inst`:

```
form  {LU₂}ša₂-SAG
inst  ša[of]DET&rēši[head]N
```

Two different arities matter here, and conflating them would produce a wrong
test either way:

| | arity 2 | 3 | 7 | 14 |
|---|--:|--:|--:|--:|
| `&`-separated slots in `inst` | 1,214 | 15 | 7 | 14 |
| **distinct lexemes** | 1,235 | 15 | — | — |

The high-arity cases collapse: `GAR.KUR` parses as
`šakin[governor]N&māti[land]N&māti[land]N…` — **two** lexemes, one repeated
thirteen times; `E₂-EDIN` is `bīt[house]N` plus `ṣēri[back]N` ×6. The
repetition is an ORACC encoding artifact, not thirteen distinct lemmas.

So: the `inst` **parser** must handle up to 14 slots, while the `word→lex`
**edge** has a maximum degree of **3**. Revision 1's test ("links to two lex
nodes") fails on the 15 genuine three-lexeme words; a test asserting degree 14
would be equally wrong.

### 2.8 Q-numbers are **not** unique — 140 collide

All 140 `rinap5p1` texts reuse Q-numbers present in `rinap5`. They are not
duplicates: comparing word counts for the same Q, **92 agree and 48 differ**,
sometimes drastically (`Q003840`: 79 words in `rinap5p1` vs 11 in `rinap5`).
They are two editions of the same inscription.

**Decision:** document identity is `subproject:Q` (`rinap5p1:Q003840`)
everywhere — including the catalogue join (§M5), where revision 1 wrongly
reverted to the bare Q-number.

### 2.9 Section labels are mostly empty

| marker | total | labelled | unlabelled |
|---|--:|--:|--:|
| `object` | 2,050 | 4 | 2,046 |
| `surface` | 2,298 | 249 (`o`, `r`, `l.e.`, `r?`) | 1,828 |

All 2,081 texts are Q-numbers — composite editions — so physical structure is
largely vestigial. Sections must be `document / face / line` with `face`
tolerating an empty label. `line-start` labels are plain numbers (`'1'`,
`'95'`), not the `'o 1'` form seen elsewhere in ORACC.

### 2.10 `sig` is an occurrence signature, not a lexeme id

```
@rinap/rinap3%akk:MU.SAR-e=mušarû[(royal) inscription//(royal) inscription]N'N$mušarê
 └project  └lang └form   └cf     └gw            //└sense           └pos'epos $└norm
```

There are **54,439 distinct `sig` strings** against 7,995 `(cf,gw,pos)`
triples — `sig` varies with project, written form and normalisation. It
identifies an analysis, not a lexeme.

Lexeme key options measured:

| key | nodes |
|---|--:|
| `(cf, gw, pos)` | 7,995 |
| `(lang, cf, gw, pos)` | **8,025** (+30) |

29 triples occur under more than one language (`Ningal` DN, `Asari` DN —
divine names shared between `akk` and `sux`). The corpus is 99.7 % `akk` but
also 901 `sux` and 65 `arc` words, and ORACC's own glossaries are
dialect-scoped. **Decision:** key on `(lang, cf, gw, pos)`, and preserve the
full `sig` on every word so source identity is never lost. A later
`lex_equiv` edge can link cross-language equivalents if wanted.

### 2.11 Translations exist, are aligned, and are obtainable

Revision 2 called translations out of scope on the grounds that they are not in
the JSON distribution. That was true of `corpusjson/` but wrong as a
conclusion. `metadata.json` declares a `formats` block listing which texts have
what, and `tr-en` is one of them:

```
formats: { atf: [...261], lem: [...238], tr-en: [...238], xtf: [...261] }
```

**Declared coverage is 99.9 %** — 1,843 of 1,845 populated editions:

| subproject | populated | `tr-en` declared | joinable from TEI | |
|---|--:|--:|--:|--:|
| `riao/ria1`–`ria5` | 717 | 717 | 716 | ~100 % |
| `rinap/rinap1` | 85 | 85 | 72 | 84.7 % |
| `rinap/rinap2` | 145 | 145 | 134 | 92.4 % |
| `rinap/rinap3` | 238 | 238 | 229 | 96.2 % |
| `rinap/rinap4` | 178 | 177 | 162 | 91.0 % |
| `rinap/rinap5` | 344 | 344 | 333 | 96.8 % |
| `rinap/rinap5p1` | 138 | 138 | **0** | **0 %** |
| **total** | **1,845** | **1,843** | **1,646** | **89.2 %** |

**Source.** The direct XTR URL pattern (`/rinap/rinap3/Q003475-en.xtr`) does
**not** resolve — it returns a soft-404 (body `404`, HTTP 200). The practical
source is the published TEI corpus export. Note the useful accident:

- `riao/downloads/riao-teiCorpus-20241202.zip` (7.8 MB → 60 MB XML) is
  misleadingly named. It contains **1,941 texts: all 904 RIAO *and* all 1,037
  RINAP1–5**, matching this snapshot exactly except `rinap5p1`.
- `rinap/downloads/rinap-teiCorpus-20190823.zip` is older and partial (676
  texts) and is superseded by the above.

So one download covers everything but `rinap5p1`, whose 138 translations are
declared in metadata but absent from both exports and need a separate route.

**Alignment is by line range, not by line.** Each translation unit is a
`<div3 type="tr">` carrying explicit references into the transliteration:

```xml
<div3 type="tr" xml:id="Q001801_project-en.0" n="(1)"
      xtr:sref="Q001801.1"  xtr:eref="Q001801.15"
      xtr:lab-start-lnum="1" xtr:lab-end-lnum="16"
      xtr:rows="15" xtr:label="(1)" xtr:se_label="Zarriqum 2001, 1">
```

`xtr:sref`/`xtr:eref` are exactly the `ref` values on our `d type=line-start`
markers, so the join is direct. Measured span sizes (RIAO): median **5** lines,
p90 11, max 72 — and **1 unit out of 5,992 spans exactly one line**. A
`line.translation` feature is therefore the wrong model; units must span line
ranges.

Unit subtypes: `tr` (6,849) is running translation; `dollar` (2,452) is
editorial/structural material. Inside a unit the text is marked up per word
(`<span type="w">`), with `type="i"` for italics and `type="r"` for editorial
parentheses.

**TEI word ids match ours.** `<w xml:id="Q001801.l00012">` is the same id as
the corpusjson `l` node, so the TEI can also be used to cross-check the word
layer independently.

**Licence conflict — resolve before redistributing.** `metadata.json` and the
TEI export both declare **CC0**. The live edition pages declare something
different:

> "The annotated edition is released under the Creative Commons Attribution
> Share-Alike license 3.0. Please cite this page as
> `http://oracc.org/riao/Q005808/`."

Two ORACC-published statements disagree about the same material. Treat the
translation layer as **CC BY-SA 3.0 with attribution** — the more restrictive
reading — and carry per-document `license`/`license_type` through the build so
the question stays auditable.

### 2.12 Catalogue metadata

Present on ≥90 % of 2,098 entries: `designation`, `genre`, `subgenre`,
`period`, `provenience`, `language`, `supergenre`, `ruler` (96.4 %),
`object_type`, `material`, `script`, `exemplars`, `primary_publication`,
`pleiades_id`/`pleiades_coord` (98.8 %), `cdli_id` (79.3 %). Source
`license` and `license_type` (including `restricted`) are retained on the
document node for provenance auditing.

---

## 3. Target TF model

Slot type is **sign**, matching `Nino-cunei/oldbabylonian` so queries port.

| node type | source | est. count |
|---|---|--:|
| `document` | one corpusjson file, keyed `subproject:Q` | 2,078 (1,845 populated) |
| `face` | `d type=surface` | 2,298 |
| `column` | `d type=column` | 758 |
| `line` | `d type=line-start` | 56,226 |
| `chunk` | every `c` node, typed by `chunk_type` | 13,644 |
| `phrase` | `c type=phrase` (also a chunk) | 4,499 |
| `word` | `l` node | 320,975 |
| `lex` | distinct `(lang, cf, gw, pos)` | 8,025 |
| `sign` **(slot)** | semantically classified GDL object | 792,651 *(provisional, §2.3)* |
| `translation_unit` | TEI `div3 type="tr"`, spanning `sref`→`eref` slots | ~9,500 |
| `translation_note` | TEI note attached to a unit | tbd |

Sections: `document` / `face` / `line`.

**Feature names reuse `oldbabylonian`'s** where they coincide, so existing
queries transfer: `reading`, `readingu`, `grapheme`, `lnno`, `period`,
`genre`, `material`, `collection`, `damage`, `missing`, `det`.

New features no cuneiform TF dataset currently has: `cf`, `gw`, `sense`,
`norm`, `pos`, `epos`, `lang`, `sig`, `discourse`, the `lex` node type and a
many-to-many `word→lex` edge.

**Source preservation.** Every sign slot carries `src_path` — document, word
id and the GDL path that produced it (e.g. `Q005620.l0012/gdl[0]`). Every word
retains a canonical serialisation of its original `gdl` subtree. This makes
the flattening auditable and lets the sign ontology be revised later without
re-deriving from ORACC.

---

## 4. TDD strategy

Fixtures are real files, each chosen for a specific hazard from §2:

| fixture | exercises |
|---|---|
| `riao/ria1/Q005620.json` | **numerals** — parent-borne `utf8`/`sexified`, `r` children |
| `riao/ria1/Q005278.json` | `q`/`qualified` sign — `ga-surₓ(SAG){KI}` |
| `riao/ria1/Q001801.json` | logogram `group`, determinative `seq` |
| `riao/ria1/Q005202.json` | `break: damaged`, half-brackets |
| `riao/ria1/Q005621.json` | `x: ellipsis`, `break: missing` |
| `riao/ria4/Q004473.json` | `c type=phrase`, 6,303-word implicit sentence |
| `riao/ria4/Q004456.json` | COF compound forms |
| `rinap/rinap4/Q003333.json` | 3-lexeme COF — `MU.SAG.NAM.LUGAL.LA` |
| `riao/ria5/Q009276.json` | 14 `inst` slots collapsing to 2 lexemes — `GAR.KUR` |
| `riao/ria4/Q000000.json` | **stub** — valid JSON, zero words |
| `rinap/rinap1/Q003424.json` | zero-byte file |
| `rinap/rinap5/Q003840.json` + `rinap5p1/Q003840.json` | **Q collision with differing content** |

Layers: unit (pure functions over inlined CDL) → fixture → whole-corpus
invariant → round-trip.

---

## 5. Milestones

### M0 — Harness and cardinalities
*Red:* assert the loader reports 2,081 files / 2,078 parseable / 1,845
populated / 233 stubs; zero-byte files raise a typed `EmptySourceError`.
**Exit:** all four cardinalities are computed and reported separately.

### M1 — Semantic GDL classification (the blocker; do it first)
*Red:*
- for `Q005620`, assert the numeral slot carries `utf8="𒁹"`, `sexified="1(diš)"`,
  `form="1"` and its id — and that no slot is a bare `{"r":"1"}`;
- for `Q005278`, assert the qualified sign emits **one** slot bearing `utf8`,
  with the qualification preserved as structure, not as extra slots;
- assert a compound `|URU×GU|` emits one slot and **no** operator slot;
- assert every GDL object receives an explicit disposition — `slot`,
  `structural`, `modifier`, or `rendering` — and that an **unknown shape fails
  the build** rather than being silently dropped;
- assert every slot carries a resolvable `src_path`.
**Exit:** disposition coverage is 100 % of encountered objects; the four-way
census matches §2.3.

### M2 — Word layer
*Red:* lemmatised words carry `cf/gw/sense/norm/pos/epos`; unlemmatised words
still exist with `form` and `lemmaknown=0`; word sign-spans are contiguous and
non-overlapping.
**Exit:** word count matches a direct `l`-node count exactly.

### M3 — Streaming section walk
*Red:* line 1 of `Q004473` holds exactly its source words; every word belongs
to exactly one line; `face` is created with an empty label; **no node type is
named `sentence`**; adversarial states — word before first line, line before
surface, column before surface — are handled explicitly, and object/surface
transitions reset column and line state. Any synthetic unit is marked
`synthetic=1` rather than silently fabricated.
**Exit:** line count matches the `line-start` count; the build report lists
every state anomaly encountered.

### M4 — Lexemes
*Red:* `(lang, cf, gw, pos)` keying yields 8,025 nodes and splits the 29
cross-language triples; the full `sig` survives on every word; `Q003333`
links to exactly **3** lex nodes; `Q009276` parses 14 `inst` slots but links to
exactly **2** lex nodes.
**Exit:** no lex node differing only by project; max `word→lex` degree is 3;
COF linking leaves the word count unchanged.

### M5 — Metadata join
*Red:* the join is keyed on **`(subproject, Q)`**; the regression fixture
`Q003840` retains *different* catalogue fields for `rinap5` and `rinap5p1`; a
text missing from the catalogue still converts with empty metadata; `license`
and `license_type` are preserved.
**Exit:** ≥96 % of populated documents have `ruler`; no metadata record is
attached to more than one document.

### M6 — Whole-corpus invariants
- **word count == 320,975** (hard target — derived directly from `l` nodes)
- documents == 2,078, populated == 1,845, stubs == 233, composite keys unique
- every sign belongs to exactly one word; every word to exactly one line
- every **populated** document has a valid section path
- sign count and Unicode coverage pinned **only after M1 lands**, then frozen
- `otype`/`oslots` load cleanly in Text-Fabric

### M7 — Round-trip and source preservation
*Red:* regenerate each word's `form` from its signs and assert equality;
separately assert every word's stored `gdl` serialisation is byte-identical to
the source. The second test is what makes round-trip achievable at all —
notation such as `|URU×GU|`, qualifiers and operator nesting cannot be
reconstructed from a flat sign sequence.
**Exit:** 100 % of words round-trip or every exception is enumerated and
justified.

### M9 — Translation layer (v1.1)
*Red:*
- `Q001801`'s first unit spans lines 1–15 and its `oslots` equal the union of
  those lines' signs — asserted against `xtr:sref`/`xtr:eref`, not recomputed
  from prose;
- a unit whose `xtr:rows` is 1 and one whose `rows` is 72 both round-trip;
- `subtype="dollar"` units are kept but distinguished from `subtype="tr"`;
- editorial markup survives: `type="i"` italics and `type="r"` parentheses are
  recoverable, with `text` (plain) and `text_raw` (marked up) both present;
- `rinap5p1` yields **zero** translation units and the build reports that gap
  explicitly rather than silently producing an under-translated corpus;
- every document's `license`/`license_type` is carried through.
*Green:* TEI reader keyed on `(subproject, Q)`; `translation_unit` nodes whose
`oslots` are the sign span of `sref`→`eref`; `translation_note` edges.
**Exit:** 1,646 documents carry ≥1 translation unit; no unit has empty
`oslots`; the TEI word ids (`Q001801.l00012`) reconcile 1:1 with our `word`
nodes for every joined text.

### M8 — Cross-validation
Load beside `akkadian_oldbabylonian`; assert shared feature names
(`readingu`, `lnno`, `period`, `genre`) have compatible value domains.

---

## 6. Risks

| risk | mitigation |
|---|---|
| Sign ontology still wrong for a rare shape | unknown GDL shapes fail the build; `src_path` makes every decision inspectable |
| Count-based tests pass while semantics are wrong | M1 asserts *content* of numeral/qualified/compound slots, never just totals |
| Catalogue attached to the wrong edition | `(subproject, Q)` join + the `Q003840` regression fixture |
| COF arity assumptions | parser tested to 14 `inst` slots; edge degree asserted ≤3 |
| Stub documents corrupt section invariants | invariants scoped to populated documents; stubs carry `populated=0` |
| Translation licence: JSON/TEI say CC0, edition pages say CC BY-SA 3.0 | treat as BY-SA with attribution; carry per-document licence fields (§2.11) |
| `rinap5p1` has no TEI translations | reported as an explicit gap, not silently absent; needs a separate source |
| Forcing word-level translation alignment | units span line ranges only (median 5 lines); no token alignment is attempted |

---

## 7. Scope

**In v1:** the edition layer (§3), built from `corpusjson` alone.

**In v1.1 — M9, translations.** Not out of scope: 89.2 % of populated editions
can be joined to published English translations from one TEI download, and
99.9 % are declared in `metadata.json` (§2.11).

`index-tra.json` is **not** a translation file and cannot substitute. It is an
inverted search index: English words are stemmed (`architrav`, `irrevers`) and
`instances` hold translation-word ids. Surface forms and sentence structure are
gone, so the running text is unrecoverable from it. It is, however, a good
**cross-check**: every translation token imported from TEI should be explicable
by the search index.

**Deferred:** `rinap/sources` and `rinap/scores` witnesses (0 % lemmatised),
Q→P exemplar linkage, and word-to-word alignment — ORACC promises unit↔line-range
alignment only, and forcing token alignment would invent precision the source
does not have.

---

## 8. Provisional figures

Do **not** freeze these until M1 lands: sign slot count (792,651), Unicode
coverage (98.3 % / 100.0 %), lex node count (8,025), chunk count (13,644).
Firm now: 2,081 files, 2,078 parseable, 1,845 populated, 233 stubs, 320,975
words, 56,226 lines, 140 Q collisions of which 48 differ in content.

---

## 9. Review responses

### Round 2 — translations

**Adopted.** Translations are real, aligned and obtainable, and "out of scope"
was the wrong call (§2.11). Verified: `metadata.json` declares `tr-en` for
1,843 of 1,845 populated editions, and `xtr:sref`/`xtr:eref` give exact
line-range references into the transliteration. The reviewer's model —
`translation_unit` spanning a slot range, with `translation_note` attached, and
no forced word alignment — is adopted as M9. The `index-tra.json` correction is
right and now stated explicitly: instances are translation-word ids, so running
text cannot be recovered from it. The licence warning is right and material:
the edition pages say CC BY-SA 3.0 while `metadata.json` and the TEI both say
CC0.

**Refined by measurement.**
- *XTR is the ideal source.* The documented per-text XTR URLs do not resolve —
  `/rinap/rinap3/Q003475-en.xtr` returns a soft-404. TEI is the practical
  source, not the fallback.
- *RINAP's TEI is dated 2018–2019.* True, but irrelevant: the
  **`riao-teiCorpus-20241202.zip` export is misnamed and contains all 1,037
  RINAP1–5 texts as well as all 904 RIAO ones**, current as of Dec 2024. One
  download covers everything in this snapshot except `rinap5p1`.
- *Coverage "very substantial".* Quantified: 89.2 % joinable, but with a hole —
  **`rinap5p1` yields 0 of 138**, absent from both exports despite being
  declared in metadata. M9 reports that gap rather than hiding it.
- *Alignment types vary.* Confirmed and quantified: median 5 lines per unit,
  p90 11, max 72, and only **1 of 5,992** units spans a single line. Interlinear
  alignment is effectively absent here, which strengthens the case against a
  `line.translation` feature.

### Round 1 — sign ontology

**Adopted.** The GDL leaf rule was wrong (§2.3) — verified: 6,584 numerals
plus 4 qualified/compound parents were discarded, and the compound case would
have emitted an operator as a sign. Stub editions are real and numerous
(§2.1, 233 of them). The lexeme key needed language-awareness and `sig`
preservation (§2.10). COFs exceed two components (§2.7) — though on inspection the `inst` slot
count (up to 14) and the distinct-lexeme count (max 3) diverge, and it is the
latter that governs the `word→lex` edge. The
`discourse` layer was dropped inconsistently (§2.5). M5 had reverted to
Q-number keying (§2.8). Source preservation and licence retention are now
explicit (§3, §2.11), and the translation claim is narrowed (§7).

**Did not hold for RIAO/RINAP.** Three supporting details came from a
corpus-wide scan across all 33 ORACC projects rather than these two:

- *"48 cell starts versus 47 cell ends, and just one line-end."* There are
  **no** `cell-*` or `line-end` markers in RIAO/RINAP at all (§2.4). The
  advice to be hostile about state transitions is kept regardless.
- *"the 6,311-word phrase in Q004473."* That is a `sentence`, not a phrase.
  Phrases are median 2 words, p99 5, max 82 (§2.5) — which is why `phrase`
  survives as a node type while `sentence` does not.
- *"1,686 discourse chunks."* The count is 1,846.

**Corrected but not as expected.** The reviewer predicted the sign total would
move once the ontology was fixed. It moves by **one** (792,652 → 792,651),
because the broken rule swapped numeral parents for their children one for
one. The conclusion is unchanged and arguably stronger: a count-based
regression test would have passed while 6,588 slots held the wrong content.
Unicode coverage does move, 97.4 % → 98.3 %.
