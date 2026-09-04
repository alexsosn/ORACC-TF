---
id: P-001
title: TDD implementation of a joined RIAO + RINAP TF module
type: plan
status: draft
priority: P0
depends_on: [R-001]
blocks: [P-002, P-003]
updated: 2026-09-04
---

# TDD implementation plan: a joined RIAO + RINAP Text-Fabric module

**Status:** implementation in progress, revision 5 (three rounds of independent review plus implementation measurements).
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
> *Rev 4:* M5 corpus-wide TDD measured the catalogue join and source licence
> fields. 2,075 of 2,078 parseable editions have a catalogue member; 1,844 of
> 1,845 populated editions have `ruler`; all 2,078 corpusjson documents carry
> `license` and `license-url`, while **none carries `license_type`**. The plan
> no longer asks the converter to fabricate that absent field (§2.12, M5).
> *Rev 5:* M6 discovered a Text-Fabric 13.1 warp constraint that the plan had
> missed: every non-slot TF node in `oslots` must span at least one sign. The
> source nevertheless contains 1,242 zero-span entities, including 295 words,
> 236 documents and 142 lines. They are now preserved in a deterministic
> `zero-span.json` sidecar with stable source-facing keys and cross-boundary
> relation edges, rather than by inventing or borrowing sign slots (§2.13,
> §3, M6). M6 also freezes Unicode coverage at 778,873 / 792,651 (98.2618 %).
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
why M6's section-path invariant has to be stated against *populated*
documents.

**Decision (revised by M6):** preserve all 2,078 source documents and record
all four cardinalities in the build report. A document that spans at least one
sign is emitted into the Text-Fabric warp. A metadata-only zero-span document
is preserved in the deterministic zero-span sidecar instead; it is **not**
assigned an invented sign merely to satisfy Text-Fabric's non-empty `oslots`
constraint. M6 measures 236 zero-span documents: all 233 stubs plus three
populated-but-zero-sign editions (§2.13).

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

**M1 implementation note:** the JSON key `o` is overloaded in `corpusjson`.
A real sign or `x` ellipsis may carry `o` as bracket/original-form markup,
while a standalone `{"o":"containing"}` object is a compound operator.
Classification therefore establishes sign identity (`utf8`, `v`, `s`, `x`)
before interpreting standalone `r`/`o` leaves as non-slots.

**Decision (M1):** `x` unreadable stretches are slots. They occupy textual
position, so dropping them breaks line reconstruction. Emit them with
`type=ellipsis`; Unicode coverage remains reportable both including and
excluding these placeholders.

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

### 2.6 Unlemmatised and signless words must survive

M2 pins the word layer at **320,975** source `l` nodes: **289,205** carry
lexical evidence and **31,770** do not. `lemmaknown` is based on `cf`, `gw`,
`sense`, or the occurrence `sig`; `norm` is preserved independently because
**230** source words have a normalization string but no lexical evidence.
Conversely, **878** genuinely lemmatised words have no `norm`, so the converter
must not invent one merely to make the feature matrix rectangular.

All 31,770 unlemmatised words retain `form`; dropping them would delete about
10 % of the corpus and corrupt every offset. M2 also finds **295** source words
whose GDL contributes zero semantic sign slots. Their source-level empty
half-open spans are retained. M6 further establishes that Text-Fabric 13.1
cannot represent those 295 words as warp nodes without assigning a false sign,
so their features and relation edges live in `zero-span.json` (§2.13). They
remain part of the corpus word cardinality and round-trip contract even though
the TF warp itself contains 320,680 word nodes.

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
reading. For the corpusjson edition layer, preserve the raw per-document
`license` and `license-url` fields. Do **not** derive `license_type` from their
text or URL: M5 measured that the field is absent from every current
corpusjson document. If a future upstream snapshot supplies an explicit
`license_type`/`license-type`, preserve its raw value.

### 2.12 Catalogue metadata

Present on ≥90 % of 2,098 entries: `designation`, `genre`, `subgenre`,
`period`, `provenience`, `language`, `supergenre`, `ruler` (96.4 %),
`object_type`, `material`, `script`, `exemplars`, `primary_publication`,
`pleiades_id`/`pleiades_coord` (98.8 %), `cdli_id` (79.3 %).

M5 measured the actual join against this snapshot: **2,075 of 2,078**
parseable editions have a catalogue member, **3** do not, and no catalogue
record is attached more than once. Among populated editions, **1,844 of
1,845 (99.95 %)** have `ruler`. All **2,078** parseable corpusjson documents
carry source `license` and `license-url`; **0** carry `license_type` or
`license-type`. The document layer preserves those raw source fields and never
manufactures a licence type.

### 2.13 Text-Fabric warp boundary and zero-span preservation

M6 is the first milestone that serialises the joined graph through Text-Fabric
13.1. The library rejects a non-slot node whose `oslots` set is empty. ORACC,
however, contains legitimate source entities with zero semantic sign extent.
Fabricating or borrowing a sign would make section and lexical relations look
valid while changing the source semantics.

**Decision:** the distributable v1 corpus is two coordinated layers:

1. the standard TF warp for every entity spanning at least one `sign` slot;
2. deterministic `zero-span.json` for source entities with no sign extent,
   including their complete emitted feature set and every relation edge that
   crosses the TF/sidecar boundary or connects two sidecar nodes.

Both layers use stable qualified source identities. For a non-document entity
the sidecar key is `<otype>:<subproject:Q>:<source_id>`; documents and lexemes
use their already-qualified canonical keys. An omitted node may therefore point
to an included TF node and still be resolved reproducibly from the included
node's `document_key` plus `source_id`/canonical lexeme key.

Whole-corpus M6 census:

| type | source total | TF warp | zero-span sidecar |
|---|--:|--:|--:|
| `document` | 2,078 | 1,842 | 236 |
| `face` | 2,312 emitted section faces | 2,036 | 276 |
| `column` | 758 | 723 | 35 |
| `line` | 56,226 | 56,084 | 142 |
| `chunk` | 13,644 | 13,388 | 256 |
| `phrase` | 4,499 | 4,499 | 0 |
| `word` | 320,975 | 320,680 | 295 |
| `lex` | 8,025 | 8,023 | 2 |
| `sign` slot | 792,651 | 792,651 | — |

The 236 zero-span documents are the 233 M0 stubs plus exactly three populated
editions whose words collectively yield no semantic sign slot:
`rinap/rinap1:Q003633`, `rinap/rinap2:Q006646`, and
`rinap/rinap4:Q003344`. Total zero-span sidecar nodes are **1,242**.

M6 freezes Unicode-bearing signs at **778,873 / 792,651 = 98.2618 %**.

**API limitation:** `build_tf()` still requires at least one sign overall,
because without any slot at all there is no valid Text-Fabric warp to save. A
zero-sign-only input can be represented by the sidecar schema but this M6 API
does not emit a standalone sidecar-only corpus. The joined RIAO+RINAP build is
not affected because it has 792,651 sign slots.

---

## 3. Target corpus model

Slot type is **sign**, matching `Nino-cunei/oldbabylonian` so queries port.
The source model and TF warp cardinalities are intentionally not identical:
zero-span source entities remain corpus entities in the sidecar (§2.13).

| node type | source | source total | TF warp | sidecar |
|---|---|--:|--:|--:|
| `document` | one corpusjson file, keyed `subproject:Q` | 2,078 | 1,842 | 236 |
| `face` | streaming `surface` state, including synthetic recovery faces | 2,312 | 2,036 | 276 |
| `column` | `d type=column` | 758 | 723 | 35 |
| `line` | `d type=line-start` | 56,226 | 56,084 | 142 |
| `chunk` | every `c` node, typed by `chunk_type` | 13,644 | 13,388 | 256 |
| `phrase` | `c type=phrase` (also a chunk) | 4,499 | 4,499 | 0 |
| `word` | `l` node | 320,975 | 320,680 | 295 |
| `lex` | distinct `(lang, cf, gw, pos)` | 8,025 | 8,023 | 2 |
| `sign` **(slot)** | semantically classified GDL object | 792,651 | 792,651 | — |
| `translation_unit` | TEI `div3 type="tr"`, spanning `sref`→`eref` slots | ~9,500 | tbd M9 | tbd M9 |
| `translation_note` | TEI note attached to a unit | tbd | tbd M9 | tbd M9 |

TF sections are `document / face / line` for slotted content. Sidecar entities
preserve the same source-facing identities and explicit relation edges; they
must not be mistaken for extra TF warp nodes.

**Feature names reuse `oldbabylonian`'s** where they coincide, so existing
queries transfer: `reading`, `readingu`, `grapheme`, `lnno`, `period`,
`genre`, `material`, `collection`, `damage`, `missing`, `det`.

New features no cuneiform TF dataset currently has: `cf`, `gw`, `sense`,
`norm`, `pos`, `epos`, `lang`, `sig`, `discourse`, the `lex` node type and a
many-to-many `word→lex` edge.

**Source preservation.** Every sign slot carries `src_path` — document, word
id and the GDL path that produced it (e.g. `Q005620.l0012/gdl[0]`). Every word
retains a canonical serialisation of its original `gdl` subtree, whether that
word is a TF warp node or a zero-span sidecar entity. Sidecar relation keys are
stable and resolve back to slotted TF entities through qualified source
identity. This makes the flattening auditable and lets the sign ontology be
revised later without re-deriving from ORACC.

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
invariant → round-trip. M6 adds a synthetic adversarial fixture because the
TF/sidecar relation boundary cannot be exercised by a single natural fixture
reliably: a signless word alone on a zero-span line followed by a slotted line
on the same face must preserve `word→line→face` across sidecar→sidecar→TF.

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
*Red:* a fully analysed word preserves `cf/gw/sense/norm/pos/epos`; a genuine
lemmatised source word may lack `norm` without fabrication; a norm-only
placeholder stays `lemmaknown=0`; unlemmatised words survive with `form`; a
signless source word survives with an empty span; word sign-spans are
contiguous and non-overlapping.
**Exit:** word count matches the direct `l`-node count exactly, with the measured
word classes in §2.6 pinned by the whole-corpus census.

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
text missing from the catalogue still converts with empty metadata; raw source
`license` and `license-url` are preserved; `license_type` is preserved only
when an explicit source field exists and is never inferred.
**Exit:** 2,075 of 2,078 parseable documents attach exactly one catalogue
record, 3 attach none; 1,844 of 1,845 populated documents have `ruler`; no
metadata record is attached to more than one document; source licence coverage
is `license=2,078`, `license-url=2,078`, `license_type=0` for this snapshot.

### M6 — Whole-corpus invariants
*Red/characterisation:* join M0–M5 into one real Text-Fabric graph and assert
source cardinalities independently from TF warp cardinalities. A source entity
with no semantic sign span must never receive an invented or borrowed slot.
Its features and relation edges must survive in deterministic `zero-span.json`;
an adversarial `word(empty) → line(empty) → face(slotted)` chain must remain
resolvable across both layers.

**Exit:**
- source words = **320,975**; documents = **2,078**; populated = **1,845**;
  stubs = **233**; qualified document keys are unique;
- signs = **792,651** and each belongs to exactly one source word; every source
  word belongs to exactly one source line; populated section paths have zero
  errors;
- Unicode-bearing signs = **778,873 (98.2618 %)**;
- TF warp counts are exactly those in §2.13 and `otype`/`oslots` load through
  Text-Fabric 13.1;
- sidecar counts are exactly those in §2.13, total **1,242**, with 295 words
  and 236 documents; the three populated zero-sign documents are pinned by
  qualified id;
- repeated builds produce byte-identical `zero-span.json` and stable sidecar
  relation keys resolve both omitted→omitted and omitted→TF edges;
- `build_tf()` rejects a corpus with zero total sign slots with typed
  `CorpusBuildError`; standalone sidecar-only emission is not claimed by M6.

### M7 — Round-trip and source preservation
*Red:* regenerate each word's `form` from its signs where sign-derived form is
well-defined and assert equality or enumerate every source-supported exception;
separately assert every source word's stored `gdl` serialisation is identical
to the source representation. **The word domain is TF + zero-span sidecar,
not TF warp nodes alone.** The second test is what makes round-trip achievable
at all — notation such as `|URU×GU|`, qualifiers and operator nesting cannot
be reconstructed from a flat sign sequence.
**Exit:** 100 % of the 320,975 source words are accounted for across TF +
sidecar; every non-round-tripping sign-derived `form` case is enumerated and
justified, and every stored source GDL representation is preserved exactly by
the chosen canonical/byte comparison contract.

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
- translation-source licence/provenance is explicit, while the corpusjson
  document's raw `license`/`license-url` fields remain unchanged.
*Green:* TEI reader keyed on `(subproject, Q)`; `translation_unit` nodes whose
`oslots` are the sign span of `sref`→`eref`; `translation_note` edges.
**Exit:** 1,646 documents carry ≥1 translation unit; no unit has empty
`oslots`; the TEI word ids (`Q001801.l00012`) reconcile 1:1 with our `word`
nodes for every joined text, treating zero-span corpusjson words explicitly
rather than assuming every source word is a TF warp node.

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
| Zero-span source entity disappears or gains a fake sign | preserve it in deterministic `zero-span.json`; hard-pin TF/sidecar cardinalities and cross-boundary relation tests (§2.13, M6) |
| Stub documents corrupt section invariants | invariants scoped to populated documents; all 233 stubs are explicit zero-span document entities rather than fabricated TF sections |
| Consumer counts only TF warp nodes and mistakes them for source totals | report source, TF and sidecar cardinalities separately; document that v1 is a coordinated TF + sidecar corpus |
| Translation licence: JSON/TEI say CC0, edition pages say CC BY-SA 3.0 | treat as BY-SA with attribution; preserve raw source licence fields and explicit translation-source provenance (§2.11) |
| `rinap5p1` has no TEI translations | reported as an explicit gap, not silently absent; needs a separate source |
| Forcing word-level translation alignment | units span line ranges only (median 5 lines); no token alignment is attempted |

---

## 7. Scope

**In v1:** the edition layer (§3), built from `corpusjson` alone and published
as a coordinated Text-Fabric warp plus deterministic zero-span sidecar. The
sidecar is part of the corpus contract, not an optional diagnostic artifact.

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

## 8. Pinned figures

M1 pins **792,651** sign slots; M2 pins **320,975** source words; M3 pins
**56,226** source lines; M4 pins **8,025** source lexemes; M5 pins the metadata
join; M6 now pins the physical TF/sidecar serialisation boundary.

Firm snapshot figures: 2,081 source files, 2,078 parseable, 1,845 populated,
233 stubs, 320,975 source words, 792,651 sign slots, 56,226 source lines,
8,025 lexemes, 140 Q collisions of which 48 differ in content, 2,098 catalogue
entries, 2,075 attached parseable editions, 3 missing catalogue members, and
1,844/1,845 populated editions with `ruler`.

M6 serialisation: Unicode **778,873 / 792,651 (98.2618 %)**; TF warp nodes
`document=1,842`, `face=2,036`, `column=723`, `line=56,084`, `chunk=13,388`,
`phrase=4,499`, `word=320,680`, `lex=8,023`, plus all 792,651 sign slots;
zero-span sidecar nodes `document=236`, `face=276`, `column=35`, `line=142`,
`chunk=256`, `word=295`, `lex=2`, total **1,242**. The three populated
zero-sign documents are `rinap/rinap1:Q003633`, `rinap/rinap2:Q006646`, and
`rinap/rinap4:Q003344`.

---

## 9. Review responses

### Round 3 — M6 Text-Fabric boundary

**Adopted.** The independent M6 review correctly rejected the then-green PR as
not yet final: implementation had discovered the TF 13.1 non-empty-`oslots`
constraint, but this normative plan still claimed every source document and
word became a TF node. Revision 5 makes the TF + sidecar split explicit,
freezes both cardinality domains, and propagates that contract into M7 and M9.

The review also required an adversarial mixed graph, not merely count checks:
a zero-span word on a zero-span line followed by a slotted line on the same
face. Its required relation path crosses sidecar→sidecar→TF. That regression is
now part of M6's test contract, along with byte-deterministic sidecar output and
stable source-facing keys.

**Measured rather than assumed.** Zero-span documents are **236**, not merely
the 233 obvious stubs. The additional three are populated source editions with
no semantic sign slots: `rinap/rinap1:Q003633`, `rinap/rinap2:Q006646`, and
`rinap/rinap4:Q003344`. Unicode coverage is exactly 778,873 of 792,651 signs.

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
preservation (§2.10). COFs exceed two components (§2.7) — though on inspection
the `inst` slot count (up to 14) and the distinct-lexeme count (max 3) diverge,
and it is the latter that governs the `word→lex` edge. The `discourse` layer
was dropped inconsistently (§2.5). M5 had reverted to Q-number keying (§2.8).
Source preservation and licence retention are now explicit (§3, §2.11), and
the translation claim is narrowed (§7).

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
