---
id: P-003
title: Build user documentation for ORACC-TF
type: plan
status: draft
priority: P1
depends_on: [R-003, P-001]
blocked_by: [P-001]
updated: 2026-08-29
---

# Plan: build user documentation for ORACC-TF

## Goal

A user who has never seen ORACC loads the dataset, prints a passage with its
translation, and writes a correct query — without reading the converter.

Grounded in [R-003](../research/R-003-documentation.md).

## Guiding rules

**1. Documentation follows a released dataset.** No reference page is written
before P-001 M6 produces countable output (R-003 §3). Until then, only the
skeleton and the generator exist.

**2. Never hand-write a number.** Every count, percentage and value domain is
generated from the build or the validation reports (R-003 §4). R-001's figures
have already been corrected twice; a copied number would rot silently.

**3. Feature meaning lives in TF metadata, not Markdown.** Each feature's
one-line description is set in the converter's `@description` and flows into
docs (R-003 §1.1). BHSA's 51 empty descriptions are the anti-pattern.

**4. Manual prose lives in preserved regions.** `<!-- manual:begin ... -->`
blocks survive regeneration.

**5. Every snippet runs.** Code in docs is executed in CI against the released
dataset.

**6. Lead with the traps.** The five hazards in R-003 §2 appear on the landing
page, not only in reference pages.

---

# Phase 0 — skeleton and generator (can start now)

## 0.1 Create the reference tree

Empty pages with front-matter and a one-line purpose, per R-003 §5. No
content claims yet.

**Acceptance:** `docs/reference/` exists; `docs/README.md` links every page;
no page contains an unverified number.

## 0.2 Feature descriptions in the converter

Every feature P-001 emits gets an `@description` at write time. Table of
required descriptions, including the six ambiguous ones from R-003 §1.2
(`cf`, `gw`, `sense`, `norm`, `epos`, `sig`).

**Acceptance:** the converter fails its own test suite if any emitted feature
has an empty description.

## 0.3 Generator

`scripts/gen_docs.py` reads the built dataset + reports and emits
`features.md`, `features/<nodetype>/<feature>.md`, and every statistic, while
preserving `manual:` regions.

**Acceptance:** running it twice is a no-op; deleting a manual region is
detected, not silently discarded.

## 0.4 Drift check

`scripts/check_docs.py` fails when a feature exists in data but not docs,
a documented feature is gone, a `@description` is empty, or a generated
number differs from the current build. Wire into CI.

**Acceptance:** removing a feature from the converter turns CI red.

---

# Phase 1 — the five hazard pages (highest value)

Each corresponds to a hazard in R-003 §2 and must exist before any tutorial.

## 1.1 `reference/signs.md`
The GDL ontology. Includes the P-001 §2.3 disposition census, states plainly
that a sign count reflects our classification, and shows the numeral case
(`𒁹`/`1(diš)`) that an earlier rule got wrong.

**Acceptance:** a reader can explain why `792,651` is not "the number of signs
on the tablets".

## 1.2 `reference/words-and-lexemes.md`
`cf`/`gw`/`sense`/`norm`/`pos`/`epos` disambiguated with examples. The four
absence cases (R-003 §2.2) as a table with counts. Compound forms and the
degree-3 `word→lex` edge, with a worked correct-vs-incorrect frequency count.

**Acceptance:** contains a runnable snippet that counts lemma frequency
correctly in the presence of COFs, and one showing the naive version's error.

## 1.3 `reference/translations.md`
The line-range model first, with the "translation of this line" question
answered explicitly as ill-posed. `xtr:sref`/`eref` provenance. Coverage per
subproject including the `rinap5p1` zero.

**Acceptance:** the first code block retrieves translation units overlapping a
line, never a per-line field.

## 1.4 `reference/identity.md`
`subproject:Q`, the 140 collisions, the 48 that differ in content, and how to
join to CDLI or a catalogue without merging editions.

**Acceptance:** shows the wrong join and its silent failure on `Q003840`.

## 1.5 `reference/model.md`
Node types, section hierarchy, an SVG diagram, and the statement that `d`
markers are flat in the source but nested in TF.

**Acceptance:** the node-count table is generated, not typed.

---

# Phase 2 — orientation and reproducibility

## 2.1 `reference/index.md`
What the corpus is (RIAO+RINAP, ~1,500 years, one genre), how to load it,
first query, and the five hazards as a linked list.

## 2.2 `reference/query-guide.md`
Recipes: passage retrieval, lemma search, damage-aware filtering, ruler/period
slicing, translation lookup. Plus a **common mistakes** table drawn from the
hazards.

## 2.3 `reference/reproducibility.md`
Which upstream archives produced this release (from `upstream.lock.json`,
P-002), how to rebuild, and the licence position — including the CC0 vs
CC BY-SA 3.0 conflict from P-001 §2.11.

**Acceptance:** licence text is generated from the lock, not typed.

---

# Phase 3 — generated feature reference

`features.md` index plus one page per feature with node type, value type,
description, value domain, frequency, and a manual interpretation region.

**Acceptance:** every feature in the dataset has a page; every page has a
non-empty description; regeneration is stable.

---

# Phase 4 — tutorial notebooks

`00_start`, `01_model`, `02_words_and_lexemes`, `03_translations`,
`04_search`, `05_export`. Executed in CI against the released dataset.

**Acceptance:** all notebooks run clean from a fresh environment.

---

# Phase 5 — release furniture

`CITATION.cff` (crediting the ORACC projects and their editors),
`CHANGELOG.md`, `KNOWN-ISSUES.md` seeded with: `rinap5p1` has no translations;
233 stub editions; the licence conflict; unlemmatised coverage.

---

# Definition of done

- [ ] no page contains a hand-typed count or percentage
- [ ] every emitted feature has a non-empty `@description`
- [ ] the generator is idempotent and preserves manual regions
- [ ] `check_docs.py` runs in CI and fails on drift
- [ ] all five hazard pages exist with runnable examples
- [ ] the COF frequency snippet demonstrates correct and incorrect counting
- [ ] the translation page never presents a per-line translation field
- [ ] the identity page demonstrates the `Q003840` join failure
- [ ] licence text is generated from `upstream.lock.json`
- [ ] every code block in docs executes in CI
- [ ] all tutorial notebooks run from a clean environment
- [ ] `CITATION.cff`, `CHANGELOG.md`, `KNOWN-ISSUES.md` exist
- [ ] the eight R-003 §7 user tasks are each achievable from the docs alone
