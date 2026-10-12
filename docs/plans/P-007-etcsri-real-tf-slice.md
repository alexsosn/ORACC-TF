---
id: P-007
title: ETCSRI real-source Text-Fabric vertical slice
type: plan
status: active
priority: P1
issue: 32
updated: 2026-10-12
fact_policy: snapshot-evidence
evidence_date: 2026-10-11
evidence_basis: R-007 ETCSRI checked-in source census and pinned Q000935/Q000376 source Git blobs; RED-first PR #173 evidence
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

## Follow-up full-corpus milestone (issue #32, PR #176)

The original two-edition slice is merged in PR #173. Do not make an
additional generic converter path. Continue the isolated ETCSRI converter
with **real-source-shape** fixes, RED first.

The checked-in source [R-007 working-tree scan, run 38166385264] measured
1,456 corpusjson editions and the complete `node=d` marker inventory:
**16,886 `line-start`, 694 `nonx`, and 2 `nonw` records**.
The first whole-corpus RED run, 38181383535, failed at
`Q000377` because `nonx` had not been modeled. The actual Git blob
`62bbca48a50205353ac5ed8225a3ce3e163c5f31` contains nine `nonx`
markers. In sentence `Q000377.U490` one records
`ref=Q000377.387, scope=line, state=missing, extent=3, strict=1`.

For **`nonx`**, preserve the complete marker object and an independently
queryable nontext-span node, anchored by a technical `synthetic=1` sign
slot in the actual sentence. It must not belong to the preceding/following
physical line or count as a source sign/word; never invent three missing
line nodes from an `extent` annotation. Independently check real TF
`oslots` and source JSON on that pinned sentence.

For the **two `nonw`** source events, inspect their *actual* JSON shape
before choosing a representation. Do not classify as `nonx`, drop, or
fabricate words without evidence. Continue using the whole-corpus test
as a hard source-coverage gate: 29,573 words, full source-to-TF payload
roundtrip and exact original provenance, with every deviation reported.

The whole-corpus PR does not authorize publication, dataset registration,
or a source licence conclusion. Its independent adversarial review must
check exact-head CI and actual emitted TF content before merge.

## Real nonw witnesses (12 October follow-up)

The dedicated source-scan run `38231547891` revealed exactly two
`node=d,type=nonw` markers, subsequently independently inspected in their
actual checked-in JSON:

- `Q001794.json` (Git blob `286a599b1331f437ca1fa0bbb22e16053206056e`),
  sentence `Q001794.U4`: `{"node":"d","type":"nonw","ref":""}`,
  after source word `Q001794.l05654` on line 19 and before line 20.
- `Q001870.json` (Git blob `f8ad81e0619d52123b9be24848aeb9af3d7f709d`),
  sentence `Q001870.U2`: `{"node":"d","type":"nonw","ref":"Q001870.3.1.a","lang":"sux"}`,
  after word `Q001870.l06700` on line 3 and before line 4.

Neither has an `f` lexical object or GDL sign tree. Preserve them as
`nonword_marker` nodes with exact `marker_json`, queryable
`marker_type=nonw`, and a technical, non-visible anchor under their
source-chunk ancestry. A blank `ref` is **source data**, not an inferred
word/line identity. Reject malformed `ref`/`lang` shapes, do not assign a
lexeme or increase physical source word/sign/line counts, and test both
blob-pinned witnesses in real TF before proceeding to full-corpus checks.

## Full-source event and sign-shape correction (12 October)

The *actual* workflow 38235200315 surveyed all 694 source `nonx`
events and found ten combinations, not solely missing line counts:
649 line/missing/strict=1; 14 column/missing; 12 line/ruling;
8 line/blank; 3 line/traces; 3 line/illegible;
2 missing with no `scope` and strict=0;
1 line/erased; 1 column/blank; 1 case/blank.
Original `extent` is either a positive decimal string or one of
`n`, `rest`, `end`. No conversion may expand these uncertain spans
to invented lines or signs. Canonical source marker JSON and queryable
string values are retained; the scope feature is absent when omitted by
the source.

The first whole-corpus post-nonw failure (workflow 38235484148)
was a real GDL object at `Q000377.l02b7a`:
`{"b":"AŠ"}` followed by `{"m":"t"}` in the `mods` list
inside the compound `|E₂×AŠ@t|`. These are the source's base and
modifier *metadata* leaves, not independent sign slots. The shared
GDL classifier accepts these narrowly within `mods` and still rejects
unknown standalone or ill-typed shapes. Real-source negative tests
protect the sign-slot interpretation; the whole-corpus conversion
gate must still independently check all 1,456 texts and 68,403
source sign observations.

The `nonx` TF node type is intentionally `nontext_span`, not
`missing_span`: source `Q000834.json` (Git blob
`574f6ed3eace4a8d2d04d3da2c2fdc20e7af4f43`) attests
`Q000834.102` with `state=ruling`, `extent=n`, `scope=line`.
A ruling is not a claim that lexical text was once present. The
source-specific `gap_state` and full `marker_json` remain recoverable;
the technical slot is non-visible and does not count as an actual sign.
