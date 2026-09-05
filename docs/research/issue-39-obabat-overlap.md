---
title: OBABAT overlap with Nino-cunei/oldbabylonian
type: research
status: done
issue: 39
updated: 2026-09-05
---

# OBABAT overlap with `Nino-cunei/oldbabylonian`

## Result

At the document-identifier level, **86 of 121 OBABAT documents overlap with `Nino-cunei/oldbabylonian`**. That is **71.1% of OBABAT** and **6.7% of the 1,285-document Nino corpus**.

The overlap is large enough that OBABAT should **not** be treated as an independent evaluation corpus when a model, rule set, or benchmark process has been developed on the Nino corpus. The 86 matched documents should be excluded from any such evaluation. The 35 unmatched OBABAT documents are only candidates for an independent slice: because both resources draw on the AbB publication tradition, they still need a secondary transcription/publication fingerprint check before being declared leakage-free.

A machine-readable manifest is committed beside this report as [`issue-39-obabat-overlap.json`](issue-39-obabat-overlap.json).

## Sources frozen for this comparison

### ORACC-TF / OBABAT

- repository: `alexsosn/ORACC-TF`
- revision inspected: `2406a204c40bb9beec999174ddab2efaa10ff565`
- membership file: `data/obabat/atletters/corpus.json`
- membership blob: `f3dae9f3e713683ebc4c49075ff8475a44e3b1f8`
- members: **121**
- project metadata identifies the corpus as Old Babylonian letters and records AbB publication/designation data plus CDLI URIs.

### Nino Old Babylonian

- repository: `Nino-cunei/oldbabylonian`
- revision inspected: `cd8ffe826a598af4715fd724387d9834ec1300d8`
- TF version: `1.0.6`
- document-ID feature: `tf/1.0.6/pnumber.tf`
- feature blob: `9d9d07d0f5f80f03aadae43e87bedddcc2d05ad1`
- documents: **1,285**
- feature description: `P number of a document`
- bundled source tree includes CDLI AbB transcriptions (`sources/cdli/transcriptions/.../AbB-primary.txt` and `AbB-secondary.txt`).

Using immutable revision and blob identifiers matters here because the Nino corpus is an external dependency and future snapshots can change membership.

## Matching strategy

Use an **exact CDLI P-number join**.

1. Read the keys of `data/obabat/atletters/corpus.json["members"]`.
2. Read document values from Nino's `pnumber.tf`.
3. Normalize only whitespace; accept identifiers matching `^P[0-9]{6}$`.
4. Compute exact set intersection.
5. Preserve publication/designation metadata only for audit and secondary checking; do not use it as the primary join key.

Minimal reproduction logic:

```python
import json

with open("data/obabat/atletters/corpus.json", encoding="utf-8") as fh:
    obabat = set(json.load(fh)["members"])

# Text-Fabric sparse node feature: ignore @metadata, then take the value
# after an optional node-number tab prefix or the full line otherwise.
def tf_values(path):
    out = set()
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("@"):
                continue
            value = line.split("\t", 1)[-1]
            if value.startswith("P") and len(value) == 7 and value[1:].isdigit():
                out.add(value)
    return out

nino = tf_values("pnumber.tf")
overlap = sorted(obabat & nino)
```

## Counts

| set | documents |
|---|---:|
| OBABAT | 121 |
| Nino Old Babylonian | 1,285 |
| exact P-number intersection | **86** |
| OBABAT not matched by P-number | **35** |
| OBABAT overlap rate | **71.1%** |
| Nino overlap rate | **6.7%** |

The overlap manifest records all 86 matched IDs and all 35 currently unmatched OBABAT IDs.

## Interpretation

An exact P-number match is strong evidence that both corpora represent the same CDLI document. It does **not** mean the two resources contain byte-identical transliteration or annotation. ORACC-TF adds project editorial annotation, while Nino is an ATF-derived Text-Fabric corpus. For leakage control, document identity is the relevant fact: training or tuning on one representation can leak lexical, graphemic, line, name, and document-specific information into evaluation on the other.

The unmatched 35 documents should not be assumed independent solely because their P-numbers are absent from the pinned Nino feature. Plausible causes include edition/snapshot differences, changed document coverage, or related AbB witnesses represented under different identifiers.

## False-positive risks

The exact-P-number strategy has low false-positive risk for document identity. Residual risks are mostly semantic:

- the same P-number may point to substantially revised transliterations in different snapshots;
- one corpus may encode a joined object or edition differently while retaining the same document identifier;
- “overlap” therefore means same document, not same annotation payload.

These do not weaken the exclusion decision; they make byte-level deduplication an insufficient substitute for identifier-level leakage control.

## False-negative risks

Exact P-number matching can miss related material when:

- fragments or joins have distinct CDLI identifiers;
- one edition represents a composite text while another represents witnesses separately;
- a later corpus snapshot adds or changes identifiers;
- publication aliases identify the same witness without the same P-number;
- duplicated or closely related witnesses occur in the same AbB publication environment.

For the 35 unmatched documents, a second gate should compare at least normalized transliteration fingerprints and publication/designation metadata.

## Benchmark recommendation

**Recommendation: exclude the 86 exact overlaps from evaluation.**

For a benchmark intended to be independent of `Nino-cunei/oldbabylonian`:

- do not randomly split all 121 OBABAT documents and call the result independent;
- treat the 35 unmatched IDs as `candidate_clean`, not `clean`;
- require normalized-text and publication/designation checks before admitting any of those 35 to evaluation;
- if a clean independent slice remains too small after that gate, use OBABAT for converter/tooling regression, annotation alignment, or cross-corpus feature validation rather than headline model evaluation.

## Proposed regression contract

Future overlap checks should consume the JSON manifest and fail closed when either source revision changes without recomputation. A future automated check should verify:

1. source revision/blob identifiers still match the manifest;
2. every current OBABAT member is classified as `overlap` or `oracc_only`;
3. no identifier appears in both classifications;
4. counts equal the lengths of the corresponding arrays;
5. a changed Nino or OBABAT snapshot requires regeneration and review of the benchmark recommendation.
