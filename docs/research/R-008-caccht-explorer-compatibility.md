---
id: R-008
title: CACCHT Explorer compatibility with ORACC-TF
type: research
status: active
priority: P0
depends_on: [R-006]
updated: 2026-11-17
fact_policy: snapshot-evidence
evidence_date: 2026-11-17
evidence_basis: GitHub Actions source-pinned ETCSRI/NINMED and SHA256-verified published RIAO/RINAP v1.0.0 Explorer 0.1.2 probes
---

# R-008 — CACCHT Explorer compatibility with ORACC-TF (2026-11-17)

Status: **research verified, conditional reuse; not a usable ORACC reader without changes**.

Related: [#189 user-first UX](https://github.com/alexsosn/ORACC-TF/issues/189), [#190 research](https://github.com/alexsosn/ORACC-TF/issues/190), [#188 citations](https://github.com/alexsosn/ORACC-TF/issues/188), [PR #191](https://github.com/alexsosn/ORACC-TF/pull/191).

## Decision

The **Text-Fabric data model and existing ORACC-TF converters are compatible with the core of CACCHT Explorer**. In actual clean-runtime tests, Explorer 0.1.2 with Context-Fabric 0.5.8 loaded both original-source native vertical slices and the **public** RIAO/RINAP release, navigated real sections, rendered passages/interlinear representations, and queried the word nodes. There is no evidence that a new data store or a schema rewrite is needed.

The **shipped React reader is not yet compatible with the ORACC reference model**, and the semantic display defaults are biblical-corpus-specific. In particular, it misparses colon-bearing qualified ORACC references, suppresses transliteration from the format selector, offers empty word summaries, and does not expose the available same-corpus official TEI translations. A 4.18 GiB peak RSS was observed for the published release, compared with 2.59 GiB from a separate raw Text-Fabric `loadAll` baseline. These are blockers for calling the browser a lightweight first-use solution.

**Recommendation:** attempt small, generic changes *upstream in Explorer* (or a temporary minimal patch branch) rather than building another frontend or changing ORACC-TF's source data. Keep the current TF browser available for advanced TFQL workflows. A full public-app replacement decision requires real **Chromium first-use E2E** and a resource budget on the released RIAO/RINAP corpus.

## Sources and reproducible test design

Upstream: [Context-Fabric/context-fabric](https://github.com/Context-Fabric/context-fabric/tree/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer) at commit `8e955786ab04554fdfab68e4bce8a37236c85e88`, public `cfabric-browser==0.1.2` (MIT, Python >=3.13). ORACC-TF wheel supports Python >=3.10 and `text-fabric>=13.1,<14`; Explorer is therefore a separate **optional runtime**, not a converter dependency.

1. [Source-grounded installed-wheel probe](../../tests/e2e/issue190_caccht_explorer_probe.py) converts actual pinned ORACC JSON: ETCSRI `Q000935.json`, Git blob `a2eef2a0337d276191fbda85a4269948fb00f9c3` (7 words); NINMED `P285136.json`, Git blob `a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b` (204 words). It preserves a temporary layout `<kind>/tf/0.1.0` plus `<kind>/app/config.yaml`, compares stock config against a **reversible** `typeDisplay.word.base=true`, requests real FastAPI routes, and saves a full JSON report. No synthetic TF sample.
2. [Published-release probe](../../tests/e2e/issue190_caccht_release_probe.py) downloads the actual [ORACC-TF v1.0.0 release ZIP](https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0) and verifies its release SHA256 file. It loads `tf/0.4.0` and the actual bundled `app/config.yaml`, checks `Q001801` text/translation graph and the Explorer API, and measures process peak RSS.
3. [Raw Text-Fabric control](../../tests/e2e/issue190_tf_baseline_probe.py) loads **the same public TF files** in a separate clean venv with `text-fabric==13.1.2`, calls `loadAll` and records process peak RSS, time and node counts.
4. CI: [real-source run 43971008670](https://github.com/alexsosn/ORACC-TF/actions/runs/43971008670), artifacts `14277129981`; [published-release with baseline run 43972793845](https://github.com/alexsosn/ORACC-TF/actions/runs/43972793845) includes raw JSON artifacts `issue190-explorer-compatibility` and `issue190-riao-rinap-release-compatibility`.

These are API probes and static frontend code review, **not** evidence that a first-time human can actually navigate Explorer in a rendered browser.

## Measured compatibility

| Path | ETCSRI `Q000935` | NINMED `P285136` | Published RIAO/RINAP v1.0.0 |
| --- | --- | --- | --- |
| Loads from actual TF files | YES | YES | YES |
| Actual sections API | 200 (`document,line`) | 200 (`document,face,line`) | 200 (`document,face,line`, 2,078 documents) |
| Real `/passage` and `/interlinear` | Both 200 | Both 200 | Both 200 at `Q001801.1` |
| Word node type with `sign` slots | YES, 7 words | YES, 204 words | YES, 320,975 words |
| Native TFQL `word` query | 7 results | 204 results | Not run in this probe |
| Source feature values | Present | Present | Present |
| Word-card `summary` semantic roles | **Empty** | **Empty** | **Empty** for first RIAO word |
| Default user-selectable formats | Only `text-orig-full` | Only `text-orig-full` | Only `text-orig-full` |
| Translation via source-aligned TEI edges | Not in sample | Not in sample | **Not shown** for linked `Q001801` unit |
| Real React user journey | Not tested | Not tested | Not tested; code-level ref parsing defect |

A stock `/passage?mode=plain` call used `text-trans-full`, but Interlinear used `text-orig-full` and the frontend selector offered only `text-orig-full`. This is not a converter bug. The switch `word.base=true` changed `base_types` from `['sign']` to `['word']`, but did **not** populate the word summaries or fix the format selector.

Evidence from the *original* source vs Explorer:
- ETCSRI `Q000935.1.1`: `form=ur-{d}namma`, `cf=Urnammak`, `morph=N1=Urnammak`, `morph2=N1=NAME`, `lang=sux`; inspector returned these features but `summary=[]`.
- NINMED `P285136.1.1`: `form=DU₃.DU₃.BI`, `cf=DÙ.DÙ.BI`, `gw=ritual (instructions)`, `lang=akk-x-stdbab`; inspector includes `word_lex` and correct feature values; semantic summary empty. **Upstream marks this word `bad=yes`**, so this tests faithful display of an annotation, not its philological validity.
- Published RIAO `Q001801`: 6,792 translation-unit nodes in corpus overall; source-attested `translation_unit` `riao/ria1:Q001801:Q001801_project-en.0` contains substantive English text and links through `translation_line` to `Q001801.1`–`.15`. The excerpt was absent from Explorer `/passage` and `/interlinear` responses for the first linked line.

## Root causes and exact adaptation points

### 1. React Reader assumes Bible-style numeric chapter:verse references — **P0**

[frontend/src/common.ts:51–54](https://github.com/Context-Fabric/context-fabric/blob/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer/frontend/src/common.ts#L50-L55) implements `splitRef(ref)` by `const [chapter, verse] = ref.split(':')` and `Number(verse)`. [frontend/src/reader/ReaderApp.tsx](https://github.com/Context-Fabric/context-fabric/blob/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer/frontend/src/reader/ReaderApp.tsx) uses it for selected lines, scrolling, navigation and URLs.

For the actual release ref `riao/ria1:Q001801 Q001801.face.1:Q001801.1`, this parser gives **chapter=`riao/ria1`, verse=null** rather than preserving the document/face path. It similarly fails on namespaced NINMED refs and cannot identify an ETCSRI `document,line` boundary without a colon. Thus **FastAPI sections/passage 200 is insufficient** to assert working React Reader navigation.

Required upstream change: treat section references as opaque IDs, use the API's existing explicit `node`, `path`, `prev`/`next` and structured parent values for passage selection, rather than delimiter splitting or numeric-verse assumptions. RED tests must use actual strings above, including nonnumeric labels, 2-level and 3-level sections, and namespaced document keys. Preserve qualified source identity and deep links; avoid mutating `otext.sectionFeatures` just to satisfy the UI.

### 2. Hard-coded original-script formats — **P0**

[cfabric_browser/formats.py](https://github.com/Context-Fabric/context-fabric/blob/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer/cfabric_browser/formats.py) limits user-visible formats to `text-orig-full` and `text-orig-plain`. ORACC's `text-orig-full` renders **Unicode cuneiform signs**, while `text-trans-full` renders **word-level transliteration**. A default-config key alone cannot bypass the whitelist.

Required upstream change: generic, corpus-configurable format choices, label them “Cuneiform” and “Transliteration”, and respect a valid per-corpus default in Reader, Interlinear, Concordance and hover-card text. Use the user's system font (e.g. Noto Sans Cuneiform); never synthesize missing signs.

### 3. Hebrew-centric roles and lexeme display — **P0**

[cfabric_browser/summary.py](https://github.com/Context-Fabric/context-fabric/blob/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer/cfabric_browser/summary.py) searches for `lex`, `gloss`, `sp`, `language`, `vs`, `vt`, etc.; it sanitizes lexemes with Hebrew-specific `_clean_hebrew`. Our relevant fields are `cf`, `gw`, `pos`, `lang`, `base`, `morph`, `morph2`; `word_lex` is a real edge relation.

Required upstream change: declarative display-role mappings (e.g. citation form, guide word/gloss with original field label, POS, language, morphology), optional edge-backed lexeme resolution, Unicode/script-aware rendering, and clear treatment of missing annotations. Do not force `cf` into Hebrew `lex` or call an uncertain `gw` a verified translation. [interlinear.py](https://github.com/Context-Fabric/context-fabric/blob/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer/cfabric_browser/interlinear.py) uses these summaries, so its user-facing lines are empty until the semantic mapping is fixed.

### 4. Same-corpus TEI translation units — **P0**

Explorer's existing translation subsystem handles separately imported translation corpora aligned by book/chapter/verse. ORACC-TF's official TEI translations already exist in the **same** TF corpus as `translation_unit` nodes, with `translation_line`, `translation_note_unit`, `translation_text`, source metadata and possible multi-line spans.

Required upstream or thin ORACC-specific adapter: fetch aligned units by explicit edge, display them alongside relevant lines with exact source attribution and notes, avoid duplicating a multi-line unit for each line in a misleading way, and distinguish unavailable or unaligned texts from silence. Retain licensing/provenance statements. No numeric-range guessing or fabricated translations.

### 5. Ordinary non-TFQL search and corpus selection — **P0**

Explorer has a functioning search engine, template editor, word-click “Add as search term”, and KWIC Concordance. But [its user guide](https://github.com/Context-Fabric/context-fabric/blob/8e955786ab04554fdfab68e4bce8a37236c85e88/libs/explorer/guide/searching.md) explicitly says ordinary search primarily uses **Text-Fabric search templates**. This does not yet meet #189's criterion that first-time readers can enter a form or lemma and receive results with context without knowing TFQL.

Required browser workflow: source-aware plain form search over `form` and optional lexeme `cf` (with clearly defined Unicode case/normalization semantics), labelled filters, KWIC result, click-through to a correct section reference, and empty/error states. Reuse TFQL internally as needed, do not duplicate indexes or introduce a new query language.

### 6. Performance, installation and data layout — **P0 before public rollout**

| Measurement | Observed |
| --- | ---: |
| Published release ZIP | 41,285,702 bytes |
| Unpacked `.tf` bytes | 339,696,385 |
| Raw TF 13.1.2 `loadAll` process peak | **2,717,908 kB / 2.59 GiB** |
| Raw TF `loadAll` time | 56.28 s |
| Explorer/Context-Fabric 0.1.2 published-release probe process peak | **4,383,156 kB / 4.18 GiB** |
| Relative increase in measured process peak | **61.3%** |
| Small ETCSRI + NINMED Explorer combined probe | **102,804 kB** |

The two large-corpus processes were independent and loaded the same SHA256-verified corpus, but **not identical workloads**: Explorer additionally traversed translation edges and served API calls; raw TF called `loadAll`. Values are process high-water marks, **exclude Explorer worker subprocess RSS**, and do not establish steady-state machine memory or cold-start parity. Nevertheless ~4 GiB for a local research reader is problematic. Profile actual first-use corpus loading, feature selection, startup and worker multiplicity, then choose a release memory budget before adoption. Do not add Explorer to the mandatory wheel dependency set.

A correctly packaged `tf/<version>` plus sibling `app/config.yaml` is already recognized by Explorer. Flat native previews whose app lives in an arbitrary separate directory need a **reversible launcher/staging adapter**, not a converter or data schema change.

## Proposed minimal implementation order (research → plan → RED → code → review)

1. **Generic Reader navigation**. Test 2/3-level native section refs, qualified identifiers and nonnumeric lines; user can open `Q001801` and select its first/next line without broken URL state.
2. **Text format selection**. Expose both original cuneiform and transliteration consistently, using existing `otext` formats and `config.yaml` defaults.
3. **Role/word card**. Configurable `cf/gw/pos/lang/morph/morph2`, morphology missing cases, correct sign→word locality and word→lex edge; test source witnesses.
4. **In-corpus TEI overlay**. Test `Q001801` substantive TEI text and attribution on explicitly linked lines; negative tests for absent and unaligned units.
5. **First-use ordinary search**. Text field `form` vs citation form `cf`, KWIC, click-through to exact section; preserve complex TFQL under “Advanced”.
6. **Whole-corpus resource gate and real Chromium smoke**. Verify installation from the *published* release with no builder checkout; measure RSS, workers, startup, disk and correct UI on a constrained machine. Actual headless browser must click from catalogue to a text and inspect a word/translation, not merely call API.

Use source-grounded TDD and logically independent adversarial review at each implementation PR. Keep ORACC converters, source IDs and data licensing untouched. If upstream will not support generic sections, roles, formats and in-corpus translations without a large refactor, reconsider a small reader on the existing TF API **after** this feasibility gate, not before.

## Independent-review questions for the decision

- Do any browser links silently strip `riao/ria1:`, `asbp/ninmed:` or `Q001801.face.1`? Does mobile navigation use the same broken `splitRef`?
- Do hover cards confuse `gw`, `cf`, `morph`, text form and translation? Are `bad=yes` and missing `utf8` preserved, never “fixed” by rendering guesses?
- Are one TEI unit's 15 lines displayed as one attributable translation, not 15 unrelated copies? Can “no translation” be distinguished from “translation not visible”?
- Can a new researcher complete **catalogue → text → line → word → translation → ordinary search → copy citation** without TFQL?
- Is memory acceptable for real local hardware, including Explorer workers? Is a sign-slot corpus with `word.base=true` actually visually rendered as words, rather than only declared as a base type?
- Is the public released `v1.0.0` artifact the tested input rather than a small, more convenient mock?

**Current review disposition:** the research demonstrates meaningful code reuse and four concrete frontend/backend compatibility blockers; it does **not** certify a usable UI, translation fidelity in Explorer, or performance.
