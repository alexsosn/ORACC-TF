---
id: R-003
title: Documentation architecture for ORACC-TF
type: research
status: active
priority: P1
depends_on: [R-001, P-001]
informs: [P-003]
updated: 2026-08-29
---

# Research: documentation architecture for ORACC-TF

## Purpose

Decide what ORACC-TF must document, where each fact lives, and which parts can
be generated, so that a user who has never seen ORACC can load the dataset and
ask a correct question — and so an agent can extend the docs without inventing
semantics.

---

## 1. What the reference corpora actually do

Measured against the loaded datasets, not their READMEs.

### 1.1 The two reference corpora take opposite approaches

`Nino-cunei/oldbabylonian` documents **every feature inside the TF data**:

```
readingu    "reading of a sign using cuneiform unicode characters"
langalt     "1 if a sign is in the alternate language (i.e. Sumerian) - between underscores _ _"
det         "whether a sign is a determinative gloss - between braces { }"
```

`ETCBC/bhsa` ships **51 word features with an empty description string** —
`sp`, `vt`, `vs`, `ps`, `nu`, `gn`, `st`, `ls`, `pdp`, `nme`, `pfm`, `prs`,
`uvf`, `vbe`, `vbs`. Every one of those is an opaque two- or three-letter
abbreviation whose meaning exists only in ETCBC's external documentation site.

BHSA gets away with it because it has a large institution, two decades of
publications, and a dedicated feature-documentation website. **ORACC-TF has
none of those**, so it must follow `oldbabylonian`: the description travels
with the data.

This is not a style preference. It decides where the source of truth lives.

### 1.2 ORACC-TF's own features are just as opaque

The features P-001 introduces are abbreviations inherited from ORACC:

| feature | what a new user would guess | what it is |
|---|---|---|
| `cf` | ? | citation form — the lemma |
| `gw` | ? | guide word — the disambiguating gloss |
| `epos` | "extended POS"? | the *effective* POS in context, vs `pos` from the lexicon |
| `sense` | same as `gw`? | the contextual sense, often equal to `gw` but not always |
| `norm` | normalised spelling? | normalised Akkadian, absent on 9.9 % of words |
| `sig` | signature | an *occurrence* analysis, 54,439 distinct — not a lexeme id |

Left undocumented these are a trap: `cf` vs `norm`, `pos` vs `epos`, and
`gw` vs `sense` are all pairs a user will conflate. `sig` in particular
*looks* like a stable identifier and is not (P-001 §2.10).

---

## 2. What is hard to document here, and why

ORACC-TF has five concepts that a conventional feature table cannot carry.

### 2.1 The sign layer is a decision, not a fact

P-001 §2.3 shows the sign slot is the product of a **semantic classification**
of GDL objects: composite signs emit from the parent, wrappers recurse,
rendering references and operators emit nothing. An earlier rule produced the
same slot count while 6,588 slots held the wrong content.

A user counting signs is therefore counting *our ontology*, not an
objective property of the tablet. This must be stated plainly, with the census
table, or people will publish sign statistics they cannot defend.

### 2.2 Absence has several meanings

`cf` may be missing because the word is broken, because it is a numeral, or
because ORACC has not lemmatised it. P-001 §2.6 measures the split: `pos=u`
26,176, `pos=n` 3,862, no `pos` 1,114, `pos=X` 616. A single "no lemma"
feature flattens four different situations. The docs must distinguish them and
say which is safe to filter out.

### 2.3 One word can carry several lexemes

P-001 §2.7: the `word→lex` edge has degree up to 3, and the underlying `inst`
carries up to 14 `&`-slots. Any user aggregating "lemma frequency" by counting
words will be wrong on 1,250 words unless the docs say so up front.

### 2.4 Translation aligns to line ranges, not lines

P-001 §2.11: median 4 lines per unit, and only 1 of 8,310 units spans a single
line. The obvious query — "give me the translation of this line" — has no
well-defined answer. Documentation must lead with the range model or every
user will write the wrong query first.

### 2.5 Document identity is not the Q-number

P-001 §2.8: 140 Q-numbers collide between `rinap5` and `rinap5p1`, and 48 of
those differ in content. Anyone joining on the bare Q-number against an
external catalogue will silently merge two editions. This belongs in the
landing page, not buried in a reference table.

---

## 3. Current state audit

Everything in the repository today is **builder-facing**: R-001 selects a
corpus, P-001 specifies a converter, P-002 specifies automation, G-001
documents maintenance scripts. That is appropriate for the current phase.

**There is no user-facing documentation at all** — no data model page, no
feature reference, no query guide, no tutorial, no citation file, no
changelog. There is also no dataset yet, which is the right reason for the gap.

The rule that follows from this: **documentation is written against a released
dataset, never against a plan.** Until P-001 M6 produces countable output, a
feature reference would be a specification pretending to be documentation.

---

## 4. Where each kind of fact should live

| fact | source of truth | how it reaches docs |
|---|---|---|
| feature exists, type, node type | the TF data | generated |
| one-line feature meaning | TF `@description` metadata | generated |
| value domain / frequency | the built dataset | generated |
| counts, coverage percentages | validation reports | generated |
| why a feature exists; caveats | hand-written page | manual |
| the GDL ontology decision | P-001 §2.3 → prose page | manual, cites the plan |
| upstream state, licence | `upstream.lock.json` (P-002) | generated |

**Never** hand-maintain a count or a percentage in Markdown. Every number in
R-001 has already been corrected twice; a hand-copied number in a docs page
would silently rot on the next rebuild.

---

## 5. Recommended information architecture

```text
README.md                          short: what it is, how to load, where to go

docs/
  README.md                        the index (this wiki's home)
  research/   R-00N-*.md           why decisions were made
  plans/      P-00N-*.md           what will be built, with acceptance
  guides/     G-00N-*.md           how to operate the repo
  reference/                       USER-FACING, mostly generated
    index.md                       load it, first query, orientation
    model.md                       node types, sections, the diagram
    signs.md                       the GDL ontology and what a slot means
    words-and-lexemes.md           cf/gw/sense/norm/pos/epos; COFs; absence
    translations.md                the line-range model
    identity.md                    subproject:Q, collisions, joining outward
    query-guide.md                 recipes + common mistakes
    reproducibility.md             upstream lock, rebuild, licence
    features.md                    generated index
    features/<nodetype>/<feat>.md  generated per feature
  reports/                         generated validation evidence
tutorial/                          notebooks
CITATION.cff  CHANGELOG.md  KNOWN-ISSUES.md
```

Plain Markdown on GitHub, as `oldbabylonian` and TLHdig-TF do. No docs
framework in the first pass; MkDocs can be layered on later without changing
the content model.

**Research and plans stay in the tree** rather than moving to a GitHub wiki:
they must be reviewable in pull requests alongside the code they describe, and
a wiki is a separate repository with no PR review.

---

## 6. Generation and drift

The generator reads the built TF dataset plus the validation reports and emits
`features.md`, `features/**`, and every statistic. Hand-written prose lives in
fenced regions the generator preserves:

```markdown
<!-- manual:begin interpretation -->
`epos` differs from `pos` when ORACC's editors judged the contextual part of
speech to differ from the lexicon entry.
<!-- manual:end -->
```

A `docs-drift` check fails CI when a feature exists in the data but not the
docs, when a documented feature no longer exists, when a `@description` is
empty, or when a generated number differs from the current build. This is the
same discipline P-002 applies to upstream state, pointed inward.

---

## 7. Acceptance standard

Documentation is "mature" when a competent user who has never seen ORACC can,
without reading the source:

1. load the dataset and print a passage with translation;
2. explain what one sign slot represents and why the count is an ontology;
3. filter unlemmatised words, knowing which of the four absence cases they dropped;
4. count lemma frequencies correctly in the presence of compound forms;
5. retrieve the translation covering a line, understanding the range model;
6. join a document to an external catalogue without the Q-collision bug;
7. state the licence and cite the dataset;
8. reproduce the build from the lock file.

Each maps to a page in §5 and to a runnable snippet.

---

## 8. Sources

- `ETCBC/bhsa` — 51 word features, all `description` empty (measured)
- `Nino-cunei/oldbabylonian` — every feature carries a description (measured)
- Text-Fabric data model: <https://annotation.github.io/text-fabric/tf/about/datamodel.html>
- [P-001](../plans/P-001-riao-rinap-tf.md) — the format facts these pages must explain
- [R-002](R-002-upstream-automation.md) — upstream state that `reproducibility.md` documents
