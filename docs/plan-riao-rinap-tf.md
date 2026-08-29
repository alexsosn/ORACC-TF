# TDD implementation plan: a joined RIAO + RINAP Text-Fabric module

**Status:** plan, not yet implemented
**Target dataset:** `assyrian-royal-inscriptions` — RIAO parts 1–5 and RINAP 1–5
(+5p1) as one continuous TF corpus.

---

## 1. Why joined

RIAO covers Assyria from its origins to **745 BC**; RINAP begins at **744 BC**
and runs to 612. They are the same genre (official royal inscriptions), the
same language (Akkadian), and the same ORACC annotation conventions. Joined,
they are a genre-uniform diachronic corpus spanning ~1,500 years — which no
existing cuneiform TF dataset offers.

Measured over `data/riao/ria[1-5]` + `data/rinap/rinap[1-5]`, `rinap5p1`:

| | |
|---|--:|
| edition text files | 2,081 (2,078 readable, 3 zero-byte) |
| distinct Q-numbers | 1,938 — **140 appear twice**, see §2.7 |
| words (`l` nodes) | 320,975 |
| lemmatised (`cf` present) | 90.1 % |
| sign leaves (recursive) | 792,652 |
| signs with cuneiform Unicode | 97.4 % |
| logogram signs | 183,071 |
| lines | 56,226 |
| distinct lexemes (`cf`+`gw`+`pos`) | 7,995 |

`rinap/sources` (2,206 texts) and `rinap/scores` (129) are **out of scope**:
they are manuscript witnesses, 0 % lemmatised, and would triple the token
count with unannotated text. They belong in a later, separate witness layer.

---

## 2. Ground truth: what the format actually is

Everything below was verified against the files, not assumed. These are the
facts the tests must encode.

### 2.1 `d` nodes are flat markers, not containers

This is the single most important structural fact. A text is a `c type=text`
wrapper containing a **flat stream** where `d` markers and `l` words are
siblings:

```
c type=text
  d type=object            <- marker, no children
  d type=surface           <- marker, no children
  c type=discourse
    c type=sentence implicit=yes
      d type=line-start  ref=Q004473.1  label='1'
      l  'aš-šur'    cf='Aššur'  pos='DN'
      l  '{d}IŠKUR'   cf='Adad'   pos='DN'
      d type=line-start  ref=Q004473.2  label='2'
      l  'u'          cf='u'      pos='CNJ'
      c type=phrase                       <- a real container
        l 'KUR'       cf='mātu'   pos='N'
        l 'aš-šur'    cf='Aššur'  pos='GN'
```

A line "contains" every word until the next `line-start`. **The converter must
be a stateful streaming walk**, opening and closing TF nodes as markers pass —
not a recursive descent that maps JSON nesting onto TF nesting.

### 2.2 There is no sentence segmentation — do not emit a `sentence` node

Across all 2,078 texts there are 5,221 `c type=sentence` nodes, and **every
single one carries `implicit: yes`**. Not one is an editorially marked
sentence. Their sizes confirm it: median 20 words, p90 78, **max 6,303**.

The distribution is also not one-per-text (232 texts have none, 1,583 have
one, 263 have between 2 and 243). What ORACC is emitting is a discourse-chunk
wrapper, inserted around whatever the editor bracketed — not linguistic
segmentation.

**Decision:** emit these as a `chunk` node type if useful for navigation, but
never name them `sentence`. A `sentence` node in a TF corpus carries a strong
promise — BHSA's `sentence` is a real syntactic unit — and a 6,303-word
"sentence" would break every query that assumes it.

`c type=phrase` **is** real: 4,499 genuine sub-word-group containers (e.g.
`KUR aš-šur` "land of Assyria"). Model it, but expect ~99 % of words to have
no phrase parent.

### 2.3 `gdl` is a recursive tree

The sign layer nests. A flat iteration over `f["gdl"]` misses ~11 % of signs
and badly undercounts Unicode coverage, because wrapper nodes carry no `utf8`
of their own. Recursion is through two different keys:

| shape | meaning | recurse into |
|---|---|---|
| `{v, utf8, id, delim}` | plain syllabic sign | — (leaf) |
| `{gg:"logo", gdl_type:"logo", group:[…]}` | logogram; children use `s` (sign name), `role:"logo"`, `logolang:"sux"` | `group` |
| `{det:"semantic", pos:"pre"\|"post", seq:[…]}` | determinative | `seq` |
| `{n:"n", sexified:"1(diš)", form:"1", utf8, seq:[{r:"1"}]}` | numeral | `seq` |
| `{x:"ellipsis", break:"missing", o:"["}` | unreadable stretch | — (leaf) |

Break state lives on leaves: `break: "missing"` (147,565) or `"damaged"`
(53,998), with `breakStart`/`breakEnd` and `ho`/`hc` half-bracket flags and
`o` carrying the literal bracket character.

### 2.4 Unlemmatised words must survive

9.9 % of words have no `cf`/`gw`/`sense`/`norm`/`sig`, but they still have
`form`, `gdl`, and usually `pos`:

| `pos` when `cf` absent | count |
|---|--:|
| `u` (unknown) | 26,176 |
| `n` (numeral) | 3,862 |
| *absent* | 1,114 |
| `X` | 616 |

Dropping them would silently delete 10 % of the corpus and corrupt every line
and sign offset. They must become words with an explicit "no lemma" marker.

### 2.5 One word can carry two lexemes

1,250 words are compound orthographic forms: a single written form spelling
two lemmas. They carry `cof-head`/`cof-tails` linking the parts, and `inst`
joins the analyses with `&`:

```
form  {LU₂}ša₂-SAG
inst  ša[of]DET&rēši[head]N
```

So the word→lex relation is **many-to-many**, not many-to-one. This is the
main reason `lex` must be an edge, not a word feature.

### 2.6 Section labels are mostly empty

| marker | total | labelled | unlabelled |
|---|--:|--:|--:|
| `object` | 2,050 | 4 | 2,046 |
| `surface` | 2,298 | 249 (`o`, `r`, `l.e.`, `r?`) | 1,828 (some texts have several) |
| `column` | 758 | — | — |

These are **composite editions** (all 2,081 texts are Q-numbers, not
P-numbers), so physical object/surface structure is largely vestigial. The
section hierarchy must therefore be `document / face / line`, with `face`
tolerating an empty label — it cannot be keyed on label text.

`line-start` labels are plain line numbers (`'1'`, `'95'`) in RIAO/RINAP,
**not** the `'o 1'` form seen elsewhere in ORACC. Do not parse a surface out
of the line label.

### 2.7 Q-numbers are **not** unique — 140 collide

`rinap5` and `rinap5p1` both edit Ashurbanipal, and all 140 `rinap5p1` texts
reuse Q-numbers already present in `rinap5`. They are **not** duplicates:
comparing word counts for the same Q-number, 92 agree and **48 differ**,
sometimes drastically (`Q003840`: 79 words in `rinap5p1` vs 11 in `rinap5`).
They are two editions of the same inscription.

**Decision:** the document key must be `subproject:Qnumber`
(`rinap5p1:Q003840`), never the bare Q-number. Keying on Q-number alone would
silently drop or merge 140 texts — 7 % of the corpus. A test asserts the
composite key is unique and that exactly 140 bare Q-numbers collide.

### 2.8 Three files are zero bytes

`rinap/rinap1/corpusjson/{Q003424,Q006331,Q006333}.json` are 0 bytes as
shipped by ORACC (extraction was verified clean against the ZIP manifests).
The loader must skip and report them, not crash.

### 2.9 `sig` is the canonical lexeme identity

```
@rinap/rinap3%akk:MU.SAR-e=mušarû[(royal) inscription//(royal) inscription]N'N$mušarê
 └ project  └lang └form  └cf      └gw            //└sense            └pos'epos $└norm
```

Use the `cf[gw]pos` triple as the `lex` key, not the raw string — `sig`
embeds the project name, which would wrongly split identical lexemes between
RIAO and RINAP.

### 2.10 Catalogue metadata is rich

Present on ≥90 % of the 2,098 catalogue entries: `designation`, `genre`,
`subgenre`, `period`, `provenience`, `language`, `supergenre`, `ruler`
(96.4 %), `object_type`, `material`, `script`, `exemplars`, `popular_name`,
`primary_publication`, `pleiades_id`/`pleiades_coord` (geo-coordinates,
98.8 %), `cdli_id` (79.3 %).

---

## 3. Target TF model

Slot type is **sign**, matching `Nino-cunei/oldbabylonian` so queries port.

| node type | source | est. count |
|---|---|--:|
| `document` | one corpusjson file, keyed `subproject:Q` | 2,078 |
| `face` | `d type=surface` | 2,298 |
| `column` | `d type=column` (sparse) | 758 |
| `line` | `d type=line-start` | 56,226 |
| `chunk` | `c type=sentence` (all implicit — **not** named `sentence`) | 5,221 |
| `phrase` | `c type=phrase` | 4,499 |
| `word` | `l` node | 320,975 |
| `lex` | distinct `cf`+`gw`+`pos` | 7,995 |
| `sign` **(slot)** | recursive `gdl` leaf | 792,652 |

Sections: `document` / `face` / `line`.

**Feature names deliberately reuse `oldbabylonian`'s** where they coincide, so
existing queries and notebooks transfer: `reading`, `readingu`, `grapheme`,
`lnno`, `period`, `genre`, `material`, `collection`, `damage`, `missing`, `det`.

New features that no cuneiform TF dataset currently has — the point of the
exercise: `cf`, `gw`, `sense`, `norm`, `pos`, `epos`, `lang`, `sig`,
`discourse`, plus the `lex` node type and a `word→lex` edge.

---

## 4. TDD strategy

**Test data is committed, small, and real.** No synthetic CDL. Each fixture is
a real file chosen because it exercises a specific hazard from §2:

| fixture | bytes | exercises |
|---|--:|---|
| `riao/ria1/Q001801.json` | 45 K | logogram `group`, determinative `seq` |
| `riao/ria1/Q005202.json` | 19 K | `break: damaged`, half-brackets |
| `riao/ria1/Q005620.json` | 181 K | numerals, `sexified` |
| `riao/ria1/Q005621.json` | 621 K | `x: ellipsis`, `break: missing` |
| `riao/ria4/Q004473.json` | 2.0 M | `c type=phrase`, long text, 6k-word wrapper |
| `riao/ria4/Q004456.json` | — | `cof-head`/`cof-tails` compound forms |
| `rinap/rinap1/Q003424.json` | 0 | zero-byte file |

The cycle is strict red-green-refactor: **every milestone below starts by
writing failing tests that encode a §2 fact**, then the minimum code to pass.

### Test layers

1. **Unit** — pure functions over hand-inlined CDL fragments (fast, no I/O).
2. **Fixture** — the seven files above, asserting exact counts and values.
3. **Property/invariant** — assertions that must hold over the *whole* corpus.
4. **Round-trip** — regenerate transliteration from TF, diff against source.

---

## 5. Milestones

### M0 — Harness
*Red:* a test that loads each fixture and asserts it parses (the zero-byte one
must raise a typed `EmptySourceError`).
*Green:* `loader.py` with `iter_texts(paths)` skipping and reporting empties.
**Exit:** 6 fixtures parse, 1 reports empty, suite runs in <2 s.

### M1 — Sign extraction (hardest; do it first)
*Red:* for `Q001801`, assert the recursive leaf count exceeds the flat `len(gdl)`
count; assert a known logogram yields its `s`/`role`/`logolang`; assert a
determinative yields `det`+`detpos`; assert `sexified` survives on a numeral;
assert an `x: ellipsis` leaf is emitted, not skipped.
*Green:* `sign_leaves()` recursing `group`/`seq`, plus `sign_features()`.
**Exit:** across all fixtures, recursive count > flat count and no leaf is lost.

### M2 — Word layer
*Red:* assert a lemmatised word carries `cf/gw/sense/norm/pos/epos`; assert an
unlemmatised word still exists with `form` and `lemmaknown=0`; assert word
sign-spans are contiguous and non-overlapping.
*Green:* `word_nodes()`.
**Exit:** fixture word counts match a direct `l`-node count exactly.

### M3 — Streaming section walk
*Red:* for `Q004473`, assert line 1 holds exactly the three words seen in §2.1;
assert every word belongs to exactly one line; assert `face` is created even
with an empty label; assert **no** node type named `sentence` is produced (chunks, if emitted, are `chunk`).
*Green:* the stateful marker walk.
**Exit:** line count matches `d type=line-start` count per fixture.

### M4 — Lexemes
*Red:* assert `mušarû[(royal) inscription]N` is one `lex` node shared by RIAO
and RINAP occurrences (i.e. the project prefix in `sig` is ignored); assert a
`cof` word links to **two** lex nodes.
*Green:* `lex` nodes + `word→lex` edge.
**Exit:** no lex node whose key differs only by project; lex count == 7,995.

### M5 — Metadata join
*Red:* assert `Q004473` gets `ruler`, `period`, `provenience`, `genre` from
`catalogue.json`; assert a text absent from the catalogue still converts with
empty metadata; assert `corpus` is `riao`/`rinap` and `subproject` is `ria4`.
*Green:* catalogue merge keyed on Q-number.
**Exit:** ≥96 % of documents have `ruler`, matching the measured catalogue rate.

### M6 — Whole-corpus invariants
Run over all 2,078 texts:
- every sign belongs to exactly one word; every word to exactly one line
- slot count == 792,652 (±0, pinned as a regression guard)
- document count == 2,078 and composite keys are unique
- word count == 320,975
- lemmatised fraction == 90.1 % (±0.1)
- Unicode fraction == 97.4 % (±0.1)
- no node has an empty section path
- `otype`/`oslots` load cleanly in Text-Fabric

### M7 — Round-trip
*Red:* for each fixture, regenerate the transliterated `form` of every word
from its signs and assert equality with `f.form`; regenerate line text and
diff against the source ordering.
**Exit:** 100 % of words round-trip, or every exception is enumerated and
justified in the test (this is the discipline `oldbabylonian` applies to ATF).

### M8 — Cross-validation
Load the built dataset next to `akkadian_oldbabylonian` and assert the shared
feature names (`readingu`, `lnno`, `period`, `genre`) have compatible value
domains, so a query written against one runs against the other.

---

## 6. Risks

| risk | mitigation |
|---|---|
| Streaming walk mis-nests on an unseen marker order | M6 invariant: every word in exactly one line, over all 2,078 texts |
| `gdl` has shapes not in the 20 observed | fail loudly on an unknown key combination rather than silently dropping |
| `cof` handling corrupts word counts | M4 asserts word count is unchanged by lex linking |
| Q-number collision (**realised**: 140 between `rinap5`/`rinap5p1`) | document key is `subproject:Q`; a test asserts exactly 140 bare-Q collisions and 2,078 unique composite keys |
| No translations available | out of scope by construction — see `research.md` §Limitations |

---

## 7. Out of scope for v1

Translations (not in the ORACC JSON distribution at all), `rinap/sources` and
`rinap/scores` witnesses, and the Q→P exemplar linkage. Each is a follow-on
once the edition layer is proven.
