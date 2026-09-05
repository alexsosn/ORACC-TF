---
title: OBABAT overlap with Nino-cunei/oldbabylonian
type: research
status: done
issue: 39
updated: 2026-09-05
---

# OBABAT overlap with `Nino-cunei/oldbabylonian`

## Decision

**Convert OBABAT as an overlapping-but-richer ORACC dataset, not as an independent benchmark against `Nino-cunei/oldbabylonian`.**

At the document-identifier level, **86 of 121 OBABAT documents overlap with the pinned Nino corpus**. That is **71.1% of OBABAT** and **6.7% of the 1,285-document Nino corpus**. The pinned Nino corpus contains another **1,199** documents absent from OBABAT. OBABAT contains **35** documents whose P-numbers are absent from the pinned Nino revision.

The conversion remains useful because the two corpora expose materially different annotation layers. Nino is an ATF-derived graphemic corpus without lemma/POS/sense features; checked-in OBABAT is 93.9% lemmatised and 99.1% POS-annotated. An overlapping ORACC record such as `P510527` directly contains `cf`, `gw`, `sense`, `norm`, `pos`, and `epos` on word nodes, including proper-name and divine-name analyses. That is linguistic enrichment of the same document identity, not a redundant copy of the Nino feature model.

The 86 exact matches must be excluded from any evaluation claimed to be independent of Nino. The 35 unmatched OBABAT documents are only `candidate_clean`: both resources draw on the AbB/CDLI publication environment, and exact P-number non-membership alone does not prove independence.

A machine-readable manifest is committed beside this report as [`issue-39-obabat-overlap.json`](issue-39-obabat-overlap.json). The comparison is implemented by [`scripts/compare_obabat_overlap.py`](../../scripts/compare_obabat_overlap.py), with fail-closed research tests in [`tests/test_issue39_obabat_overlap.py`](../../tests/test_issue39_obabat_overlap.py).

## Frozen sources

### ORACC-TF / OBABAT

- repository: `alexsosn/ORACC-TF`
- revision inspected: `2406a204c40bb9beec999174ddab2efaa10ff565`
- membership file: `data/obabat/atletters/corpus.json`
- membership blob: `f3dae9f3e713683ebc4c49075ff8475a44e3b1f8`
- catalogue file: `data/obabat/atletters/catalogue.json`
- corpus members: **121**
- source timestamp in the checked-in ORACC payload: **2023-01-18**
- project metadata identifies Old Babylonian letters and records AbB designations/publications plus CDLI P-number URIs.

### Nino Old Babylonian

- repository: `Nino-cunei/oldbabylonian`
- revision inspected: `cd8ffe826a598af4715fd724387d9834ec1300d8`
- TF version: `1.0.6`
- document-ID feature: `tf/1.0.6/pnumber.tf`
- feature blob: `9d9d07d0f5f80f03aadae43e87bedddcc2d05ad1`
- documents: **1,285**
- feature description: `P number of a document`
- TF feature write date: **2020-06-26**
- bundled source tree includes CDLI AbB transcription material (`AbB-primary.txt` and `AbB-secondary.txt`).

The source states are pinned independently. Exact shared P-numbers establish shared CDLI **document identity**. They do not establish byte-identical transliteration or the same immutable CDLI source edition. The ORACC payload is from 2023, while the Nino TF feature set was written in 2020; no shared immutable CDLI source revision was found that would justify claiming edition/version identity. The safe classification is therefore “same document identifier, source-version equivalence unproven.”

## Matching strategy

The primary join is an **exact CDLI P-number match**.

1. Read the keys of `data/obabat/atletters/corpus.json["members"]`.
2. Read document values from Nino's `pnumber.tf`.
3. Normalize surrounding whitespace only.
4. Accept only identifiers matching `^P[0-9]{6}$`.
5. Fail on duplicate, missing, or malformed identifiers.
6. Compute exact intersection and both directional differences.
7. Keep publication/designation metadata and normalized text as secondary audit evidence only; neither may silently override distinct P-numbers.

The research comparator deliberately distinguishes a normalized-content match under distinct P-numbers from an exact identifier match. Such a pair is reported as `content_match_distinct_ids`, not promoted to the same document. Missing evidence remains `unresolved`.

Reproduction:

```bash
python scripts/compare_obabat_overlap.py \
  data/obabat/atletters/corpus.json \
  /path/to/pinned/Nino-cunei/oldbabylonian/tf/1.0.6/pnumber.tf \
  -o overlap.json
```

The external Nino file must be obtained from revision `cd8ffe826a598af4715fd724387d9834ec1300d8`; substituting a moving branch defeats the provenance gate.

## Counts

| set | documents |
|---|---:|
| OBABAT | 121 |
| Nino Old Babylonian | 1,285 |
| exact P-number intersection | **86** |
| OBABAT not in pinned Nino | **35** |
| pinned Nino not in OBABAT | **1,199** |
| OBABAT overlap rate | **71.1%** |
| Nino overlap rate | **6.7%** |

The committed manifest materializes all 86 exact overlaps and all 35 OBABAT identifiers absent from the pinned Nino revision. The complete 1,199-item reference-only set is deterministically emitted by the comparator; it is not duplicated in the committed manifest.

## Annotation difference

R-001 measured the two source families directly:

| feature/property | OBABAT | Nino Old Babylonian |
|---|---:|---:|
| documents | 121 | 1,285 |
| words | 9,517 | 76,505 |
| signs | source has GDL but 0% sign Unicode | 203,219 |
| lemma/citation form | **93.9%** | **absent** |
| POS | **99.1%** | **absent** |
| sense / guide word | present on lemmatised ORACC words | absent as TF lexical features |
| graphemic damage/editorial state | source GDL/ORACC structures | rich ATF-derived TF features |
| running English translation | not in checked-in ORACC JSON distribution | line-level translation present |

A direct overlap spot-check on `P510527` confirms the difference is present on a shared document, not merely on unrelated corpus members. Its ORACC word nodes include, for example:

- `ana`: `cf=ana`, `gw=to`, `sense=to`, `norm=ana`, `pos=PRP`;
- `Ilšu-ibni`: `cf=Ilšu-ibni`, `pos=PN`;
- `Šamaš`: `cf=Šamaš`, `pos=DN`.

Nino’s corpus-wide feature inventory has no equivalent lemma/POS/sense layer. Conversely, Nino exposes ATF-derived graphemic state and a running line-level English translation that the checked-in ORACC JSON distribution does not provide. A future OBABAT TF dataset is therefore complementary at the annotation level even where document identity overlaps.

This report does **not** claim that 93.9% lemma coverage holds specifically inside the 86-document overlap subset; that percentage is the measured OBABAT corpus-wide rate. The shared `P510527` record is evidence that the enrichment exists on at least one exact overlap, while any implementation should report coverage for the converted dataset and overlap subset separately.

## Collision and ambiguity policy

An exact valid P-number match is strong evidence that both corpora represent the same CDLI document. It is not evidence of identical bytes or identical editorial state.

Distinct P-numbers must not be collapsed by title, designation, lexical similarity, or normalized text alone. These are review signals only. This matters for fragments, joins, composite editions, witnesses, and later CDLI identifier changes.

False negatives remain possible when:

- fragments or joins carry distinct CDLI identifiers;
- one edition represents a composite text while another represents witnesses separately;
- a later snapshot changes document coverage or identifiers;
- publication aliases describe related material without the same P-number;
- duplicated or closely related witnesses occur in the same AbB publication environment.

For the 35 unmatched OBABAT records, a second gate should compare normalized transliteration fingerprints and publication/designation metadata. Any candidate that remains ambiguous must stay out of a leakage-clean benchmark slice.

## Dataset boundary if implemented

A future conversion should keep **all 121 OBABAT documents as one source-faithful ORACC dataset** rather than deleting the 86 overlaps from the published corpus. The overlap is useful for A/B comparison of ATF-derived and ORACC linguistic representations.

Required boundary/provenance rules:

- preserve the ORACC project identity `obabat/atletters` and CDLI P-number on every document;
- preserve the ORACC snapshot/source identity independently of Nino;
- do not merge ORACC and Nino nodes or pretend their source versions are identical;
- expose the overlap manifest as comparison metadata/tooling, not as graph identity edges with stronger semantics than the P-number supports;
- benchmark consumers must explicitly exclude the 86 exact overlaps when independence from Nino is required;
- the 35 `not_in_pinned_nino_ids` remain unverified for benchmark independence until the secondary fingerprint audit passes.

## Implementation recommendation

**Recommendation: convert, after a separate research/design/TDD issue.**

The intended value is ORACC linguistic enrichment and controlled cross-corpus comparison. “Independent Old Babylonian evaluation set” is not an acceptable motivation for the full corpus because 71.1% of OBABAT overlaps the pinned Nino dataset.

The follow-up implementation issue should start with RED fixtures for:

- preservation of qualified project/document identity;
- lemma/POS/sense round-trip on a known overlapping text such as `P510527`;
- zero sign-Unicode behavior without inventing cuneiform code points;
- overlap-manifest provenance and source-revision checks;
- explicit benchmark exclusion metadata or helper behavior, if such helper behavior is adopted.

## Regression contract

Future overlap checks should fail closed when either frozen input changes without recomputation. Automated validation should verify:

1. source revision/blob identifiers match the manifest;
2. every current OBABAT member is classified as `overlap_ids` or `not_in_pinned_nino_ids`;
3. no identifier appears in both classifications;
4. the reference-only count is reproduced from the pinned Nino source;
5. counts equal the lengths of materialized arrays where arrays are stored;
6. malformed, duplicate, and missing IDs fail rather than being normalized aggressively;
7. normalized-content equality under distinct P-numbers is never promoted to exact identity;
8. `not_in_pinned_nino_ids` is never treated as leakage-clean without the secondary fingerprint gate;
9. a changed Nino or OBABAT snapshot requires regeneration and review of the recommendation.
