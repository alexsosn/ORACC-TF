---
title: Tier-2 translation-source eligibility policy
type: research
status: review
issue: 34
updated: 2026-09-05
---

# Tier-2 translation-source eligibility policy

## Decision

Translation support must be **opt-in per corpus/subproject and per frozen source artifact**. A Tier-2 corpus remains eligible for linguistic conversion when no acceptable running-translation source exists, but the resulting TF dataset must be explicitly translation-free.

A translation source is eligible only when all of the following are true:

1. it contains recoverable running translation text rather than a search/concordance index;
2. acquisition is reproducible from a stable public source and the exact bytes are pinned by version/record identity plus checksum;
3. the project-specific licence or permission covers the translation material actually being redistributed;
4. alignment is carried by the source itself (interlinear, line, labeled range, paragraph/section, or document); no alignment is guessed from lexical similarity;
5. parsing is deterministic and preserves the source text, language, labels/ranges, attribution, and provenance;
6. coverage can be measured against the corpus membership list, with missing translation represented explicitly;
7. any ambiguity in rights, version identity, or alignment fails closed to `translation_status=unavailable` until separately resolved.

`index-tra.json` is **never** an eligible running-translation source.

## Evidence from the checked-in snapshot

R-001 already established that `corpusjson` contains no `tr`, `translation`, or `@en` running-translation nodes. It also established the semantics of `index-tra.json`: ORACC exports a stemmed English search index whose entries point to occurrences/lines. The readable translation is not reconstructible from that index because original word forms, punctuation, sentence/range structure, and omitted stop/normalization information are lost.

The current snapshot confirms that translation indexes are widespread in Tier-2 candidates:

- `data/saao/saa01/index-tra.json` — present;
- `data/balt/index-tra.json` — present;
- `data/hbtin/index-tra.json` — present.

Their presence is useful for **coverage discovery only**: a document referenced by `index-tra` has some indexed translation material in the ORACC build. The index itself must not be transformed into TF translation text.

ADSD and TCMA are multi-subproject trees, so translation eligibility must be resolved at subproject granularity rather than inherited from the umbrella project name.

## ORACC translation semantics

ORACC's own ATF documentation provides four relevant source-level translation forms:

- `#tr.<lang>:` interlinear translation;
- `@translation parallel <lang> project`, structurally parallel to the transliteration;
- `@translation labeled <lang> project` with explicit single-line or line-range labels;
- inline translation facilities.

For labeled translation, ORACC explicitly requires start/end labels such as `@label o 17` or `@label r ii 3' - r ii 4'`. This is sufficient to build source-faithful line/range edges without semantic inference.

Reference: https://oracc.museum.upenn.edu/doc/help/editinginatf/translations/

ORACC also documents TEI export from ATF and individual corpus pages advertise a TEI view. TEI is therefore a potentially eligible structured carrier, but it is not automatically eligible merely because a page exposes a TEI link: the exact endpoint/export artifact, coverage, checksum/version strategy, and project rights still have to pass the same gate.

References:
- https://oracc.museum.upenn.edu/doc/about/aboutoracc/
- https://oracc.museum.upenn.edu/doc/about/standards/

## Source-family classification

| source family | running text | source alignment | reproducible/versionable | rights signal | policy |
|---|---|---|---|---|---|
| checked-in `index-tra.json` | **no**; stemmed search terms only | occurrence refs only | yes, via repository commit/blob | follows snapshot | **reject for translation text**; coverage hint only |
| checked-in `corpusjson/*.json` | no in current snapshot | n/a | yes | follows snapshot | **translation-free source** |
| ORACC live HTML text page | yes where displayed | visual line/range association | stable document URI, but page bytes can change | project/page specific | **audit only**, not production ingestion |
| ORACC TEI export/view | expected structured running text where translation exists | potentially source-preserved | endpoint is stable in principle but bytes are moving unless frozen | project specific | **candidate**, require frozen acquisition + fixture inspection |
| public ATF source/archive | yes when `#tr`/`@translation` is present | strongest; native labels/ranges | eligible if versioned/frozen | project/source specific | **preferred** |
| immutable repository release/DOI bundle containing ATF/TEI | yes if payload actually contains it | source-preserved | **yes**, with record/version + checksum | record/project specific | **preferred** after payload/licence verification |
| project HTML scraped into inferred paragraphs | yes | lossy/fragile | page may move/change | project specific | **reject** when used as a parser contract |
| OCR/re-keying from a printed translation | possible | derived | versionable locally | publication rights often separate | **reject by default**; requires a separate rights/research issue |

## Representative corpus findings

### BALT

BALT provides the strongest current path to a translation-enabled Tier-2 corpus.

Observed evidence:

- the project states that it contains **2,990** Babylonian administrative/legal texts;
- live document pages visibly contain running translations aligned to explicit line ranges, e.g. `P308396` and `P308399`;
- the project credits Yuval Levavi and Caroline Waerzeggers for transliterations/translations and states that permission was granted for their material;
- the project's reuse page states that website content, except where separately noted, is CC BY-SA 3.0 and gives a required BALT attribution;
- a versioned Zenodo record exists for BALT (`10.5281/zenodo.17667912`, version 1.1.0 in the University of Helsinki catalogue), with `BALT.zip` and an exposed MD5 checksum (`595a70f55011592cfad3acad3fced0ec`); the record declares Akkadian and English and describes the ZIP as containing annotated texts.

References:
- https://oracc.org/balt/
- https://oracc.org/balt/Creditsandreuse/
- https://oracc.org/balt/P308396
- https://zenodo.org/records/17667912

**Status: provisionally eligible, pending one file-level gate.** Before implementation, independently download the pinned Zenodo version and verify that `BALT.zip` actually contains the translation-bearing ATF/structured source needed for deterministic alignment. The metadata is strong evidence of a reproducible source, but metadata alone is insufficient to claim that the archive contains the exact running translations shown on ORACC.

If the archive lacks translation-bearing structured source, BALT remains translation-free in ORACC-TF until an eligible TEI/ATF export is frozen.

### SAAO

SAAO demonstrates that running translations exist and can be line/range aligned on the live site. Examples from SAA01 visibly pair transliteration lines with translations, and individual pages describe the edition as adapted from the relevant State Archives of Assyria volume.

However, ORACC's general reuse guidance calls out SAAO specifically as a project for which previously published material may have different terms and copyright may remain with authors/publishers. The Assyrian Empire Builders portal states more strongly that its SAA correspondence was reproduced with permission from the authors and Neo-Assyrian Text Corpus Project, that copyright remains with them, and that reproduction beyond educational fair use requires permission.

References:
- https://oracc.org/saao/saa01/P334610
- https://oracc.org/saao/saa01/P334644
- https://oracc.org/doc/help/visitingoracc/reusingoracc/
- https://oracc.org/saao/aebp/royalcorrespondence/

This conflicts with any blanket inference from a page footer saying that the “annotated edition” is CC BY-SA 3.0. The conservative interpretation is that lemmatisation/annotation and reused published translation text may have different rights layers.

**Status: not eligible for redistribution as TF translation until a project/source-specific licence determination explicitly covers the translation text.** SAAO can still be converted lemma/POS-only from the checked-in open-data snapshot. A later rights clarification or separately licensed source can enable translation without changing the linguistic corpus boundary.

### HBTIN

The checked-in HBTIN snapshot contains `index-tra.json`, but the same index semantics apply: it is not running text. No independently pinned, inspected structured translation artifact has been established in this research pass.

**Status: translation-free by default; candidate for a separate source-acquisition check.**

### ADSD and TCMA

Both are umbrella trees with multiple subprojects. Translation availability, source format, licence, and provenance can differ by subproject.

**Status: no umbrella-level translation inheritance.** Each subproject must present its own eligible source record. Absence of an eligible translation does not block linguistic conversion.

## Required provenance record

Every translation-enabled dataset/subproject should carry machine-readable provenance equivalent to:

```json
{
  "translation": {
    "status": "available",
    "language": "en",
    "source_kind": "atf",
    "source_url": "https://…",
    "source_record": "doi-or-release-id",
    "source_version": "1.1.0",
    "source_sha256": "…",
    "license": "CC-BY-SA-3.0",
    "attribution": "…",
    "alignment": "source-line-or-range",
    "coverage": {
      "documents_total": 0,
      "documents_with_translation": 0,
      "translation_units": 0
    }
  }
}
```

For a translation-free build, store the negative decision too:

```json
{
  "translation": {
    "status": "unavailable",
    "reason": "no_eligible_source"
  }
}
```

This prevents a future converter from silently substituting `index-tra`, scraping HTML, or importing an unreviewed translation source.

## Alignment contract

Allowed alignment levels are those explicitly supplied by the source:

- `line` for interlinear translations;
- `line_range` for labeled translation ranges;
- `section`/`paragraph` when source markup provides that boundary;
- `document` only when the source provides running translation without finer alignment.

Do not manufacture word-level alignment from line/range translations. Do not split a source range into per-line translations unless the source itself supplies line correspondence. Preserve source labels and the original translation unit as lossless features even if convenience edges are also exposed.

## Coverage contract

Before enabling translation for any corpus/subproject, the implementation research fixture must compute:

- number of corpus documents;
- number with at least one eligible running-translation unit;
- number with no translation;
- unit counts by alignment type and language;
- unresolved source labels/ranges;
- orphan translation units whose document is outside the corpus membership set.

`index-tra` may be compared against this result as a diagnostic signal, but disagreement must not be “fixed” by reconstructing text from the index.

## Acquisition and versioning policy

Order of preference:

1. **immutable DOI/release artifact** containing ATF/TEI/structured translations;
2. **public version-controlled source repository** pinned to commit/tree/blob;
3. **official ORACC structured export** fetched from a stable URI and immediately frozen with checksum plus acquisition timestamp/source metadata;
4. otherwise **no translation**.

Live HTML is useful for independent spot-checks but is not a production source contract. A moving ORACC JSON/TEI URL is not historically reproducible by URL alone; ORACC-TF must freeze the bytes or rely on an immutable upstream release.

## Licence policy

The generic ORACC default is not sufficient when a project reuses previously published translations. Use the narrowest applicable rights statement:

- record the project/source licence in machine-readable metadata;
- preserve required attribution at dataset and, where needed, document/source level;
- if the source says permission was granted only for display or another limited use, do not redistribute the translation in TF;
- if a project page and a source-specific rights statement appear inconsistent, treat the translation as unavailable until clarified;
- do not infer that a licence covering ORACC annotations necessarily covers a previously published translation.

## Recommendation

Adopt this policy before Tier-2 expansion.

- **BALT:** proceed to a dedicated acquisition/fixture issue that verifies the immutable Zenodo payload and measures translation coverage before parser work.
- **SAAO:** convert linguistic annotation independently of translation; keep translation disabled until rights are explicitly resolved for the reusable source.
- **HBTIN/ADSD/TCMA:** do not block linguistic conversion on translation; open source-acquisition checks only where translation materially improves the dataset and a structured public source is plausible.
- **All corpora:** reject `index-tra.json` as running text and fail closed on source/licence/alignment ambiguity.

No translation parser should be implemented from this research PR. The first translation-enabled implementation ticket must begin with RED fixtures for source acquisition, checksum/version mismatch, missing translations, line/range alignment, orphan labels, mixed licences/attribution, and deterministic round-trip of the source translation text.
