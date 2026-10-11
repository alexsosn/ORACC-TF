---
id: P-008
title: Source-faithful NINMED Text-Fabric vertical slice
type: plan
status: active
priority: P1
depends_on: [ISSUE-33]
updated: 2026-10-12
---

# NINMED source-to-TF vertical slice — research → design → RED → implementation → independent review

## Research inputs already measured, not guessed

Issue #33's pinned A/B report (merged PR #98, run 38166044432) compares ORACC
`asbp/ninmed` at repository commit `5fa3062632d0971345f5435c6db12adfc379eb67`
with `Nino-cunei/ninmed` at `9e413c41670117a96272ab2b2727ff9a1f9d3baf`.
It found 159 readable ORACC bodies (and one unreadable `P395407.json`),
65,089 ORACC word occurrences, 7,356 line-start events, 37 Nino source
documents versus 34 Nino TF documents, and only 34 shared ORACC/Nino source
IDs. Of the 34 paired source identities, **33** have different word-form
sequences. Nino `uniqueLemma` sometimes contains multiple analyses; it must
not be overwritten or called an equivalent of ORACC's `cf/gw/pos/sense`.

Independently examined the current checked-in primary witnesses:

- `P285136.json` (Git blob `a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b`):
  204 `node=l` words, 25 `node=d` events; first word
  `P285136.l003f2` has form `DU₃.DU₃.BI`, `cf=DÙ.DÙ.BI`,
  `gw=ritual (instructions)`, `pos=N`. Source GDL includes grouped
  logograms, unreadable signs and numeric signs, not a flat sign list.
- `P425685.json` (Git blob `4df915aa78b3f701c77c7ee96b6b72708ce4eb29`):
  172 words and 18 document markers; source first `P425685.l0fdd6`
  form `EN₂`. This is the *single* full-form-equal Nino paired witness
  in the pinned research report; do not infer other texts match.

Original source says `project=asbp/ninmed`, `license=CC0` and an official
source URL/timestamp. Edition and translation reuse terms require separate
upstream confirmation; the reference Nino source came by personal
communication and is **validation-only**, never copied into the new dataset.

## Implementation choice for the first executable experiment

First **test the existing source-generic TF graph conversion** against the
two real ORACC bodies without creating a competing massive converter.
If its sign classification, line/word identity, lexical edges or source
annotations are not faithful, stop and design isolated NINMED mappings rather
than force false equivalence with the 1.0 Assyrian corpus.

The first slice must be independently TF-loadable, carry distinct
`document_key=asbp/ninmed:P...` identities, retain source-native
`cf/gw/pos` and `word_lex` relations, and preserve every word's source
JSON (including `props`) **without modifying the published RIAO/RINAP
default feature inventory**. Permit a narrowly opt-in generic source-copy
feature only after RED establishes the actual loss. Do not import Nino
`uniqueLemma`, infer morpheme/gloss relationships, map words by index or
register a public dataset.

## Gates and stop conditions

1. **RED-first**: real pinned text IDs and content, exact source forms,
   lexical fields, Unicode/GDL source-sign semantics, lossless `word_json`,
   labelled non-royal dataset, missing field/unknown structure rejection.
2. Implement only repairs to observable failures. Test both files,
   compare node/slot source counts against a direct source census, and verify
   Text-Fabric load/query semantics.
3. Test royal 1.0 default build unchanged; no implicit NINMED feature
   additions or unrelated publication flags.
4. Independent adversarial review compares raw ORACC data, output TF and
   the pinned Nino A/B report. Challenge content drift, GDL counting and
   falsely equated Nino lemma semantics. Fix and rerun exact-head CI.
5. Only after this slice succeeds consider all 159 parseable bodies plus
   the explicit unreadable hazard; full dataset/release remains #33,
   not this milestone.
