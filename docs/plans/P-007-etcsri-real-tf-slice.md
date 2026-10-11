---
id: P-007
title: ETCSRI real-source Text-Fabric vertical slice
type: plan
status: active
priority: P1
issue: 32
updated: 2026-10-11
fact_policy: snapshot-evidence
---

# P-007 — ETCSRI source-grounded TF vertical slice

## Research evidence and boundaries

This first production increment builds a **separate** TF graph for the actual
`data/etcsri/corpusjson/Q000935.json` and
`data/etcsri/corpusjson/Q000376.json` sources. R-007 measured the source tree
(1,456 texts, 29,573 words; 28,180 paired `morph`/`morph2` and 3,584
`para` words); those values describe the checked-in snapshot only, **not**
this vertical slice. Q000935 is the small morphology and nested determinative
witness; Q000376 is the many-sentence, phrase, `para`, damaged sign and
word-`props` witness. Source hashes are pinned by their Git blobs:
`a2eef2a0337d276191fbda85a4269948fb00f9c3` and
`b2b99268db05b6cbbd1dc4571a5d28592d766a85` respectively.

Q000935 word `Q000935.l04855` has independent
`base="ur-{d}namma"`, `morph="N1=Urnammak"`,
`morph2="N1=NAME"`, with a separate GDL `det=semantic,pos=pre`
container holding sign `𒀭`. Q000376 has mixed
`text/discourse/sentence/phrase` chunks and `line-start` events;
word-`para` is **outside** the word's `f` mapping.
All morphological strings are source data, not proved segmentation/alignment.

## Data model and publication boundary

- `etcsri` is a separate dataset identity; its converter is
  `oracc_tf.etcsri`. Do not change RIAO/RINAP build behavior or register
  a release in `datasets.toml` in this slice.
- TF `sign` slots represent **classified semantic signs**, via the existing
  source-grounded `gdl.classify_tree` dispositions. Child signs under a
  `det` structural wrapper get their **own slots**; the wrapper is a
  `determinative` non-slot node with an explicit `det_sign` relation,
  `det_kind`, `det_pos`, `src_path` and raw `det_json`. Rendering-only
  descendants of slot-bearing composites never become duplicate sign slots.
- One `word` node per source `node=l`, with separate queryable
  `base`, `morph`, `morph2`, `form`, `cf/gw/pos` where supplied.
  `para_json` (word top-level), `props_json`, and `f_json` retain exact
  source-object information. No invented morpheme-node alignment or
  etymological interpretation.
- Preserve `document`, `text`, `discourse`, `sentence`,
  `phrase`, and `line` nodes. `source_id`, `document_key`,
  `line` and `chunk_parent`/word↔line relationships support independent
  structure queries. `line-start` is a source event, not a word.
- TF non-slot nodes require at least one slot: allocate explicitly labeled
  `synthetic=1` **technical** slots for empty words/sections/lines.
  Never mistake them for source signs; report their count separately.
- Freeze source SHA-256 and word/sign/structural cardinalities in the
  test report. Output is a local reproducible `tf/` tree, not a published
  corpus or source-licence adjudication. Original JSON root declares CC0,
  but annotated-edition/editorial rights remain to be reviewed separately.

## Gates

1. **Research/design:** this plan and R-007 inspected before code; no
   inferential morphological grammar, no generic schema migration.
2. **RED:** commit executable tests first, using **real** Q000935/Q000376
   source objects. Demand exact `base/morph/morph2`, independent `para`,
   typed sentence/discourse/phrase and four line-start events in Q000935,
   51 sentences/17 phrases/128 line-starts in Q000376; nested pre/post
   determinative signs, no sign inflation, canonical `src_path`, and
   source-object round-trip. Unknown CDL or GDL shapes must raise.
3. **GREEN:** isolated builder, TF writer with stable feature metadata,
   deterministically repeated outputs and real TF load/query.
4. **Adversarial review:** separately inspect source JSON paths, output node
   counts, GDL classification and empty-slot policy. A valid test fixture
   with absent/misleading morphology must fail; empty text must never be
   silently counted. Fix blockers and rerun **exact-head** CI.
5. **Deferred:** full 1,456-text conversion, catalogue/QPN joins,
   morphological segmentation, external Zenodo cache reconciliation,
   app/browser/package, and provenance/rights review are separate
   issue #32 follow-ups—not certified by two real witnesses.

## Stop conditions

Unknown source chunk/marker/GDL types, non-unique word/sign identities,
inconsistent source spans, non-roundtripping `para/props`, ambiguous
morpheme pairing, or licence conflicts must be surfaced explicitly; never
silently rewrite source to satisfy the TF graph.
