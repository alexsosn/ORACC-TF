---
title: Known source and model limitations
status: active
---

# Known issues and limitations

This page describes the **current pinned RIAO/RINAP candidate**, not defects
that the converter silently repairs. For exact affected documents and source
membership use the [source-to-TF audit](data-audit.md), its machine-readable
builder record `docs/task-state/ISSUE-124.json`, and the published release
manifest. Values will need rechecking for each updated snapshot.

## Missing or incomplete upstream material

- The checked source tree contains **2,081 corpusjson members**. The source
  audit can read **2,078**, of which **1,845** have populated text and
  **233 are readable stubs**. Three unreadable/zero-byte RINAP1 members are
  explicitly listed in the audit's `source.hazards`; they do not become
  invented TF documents.
- Some readable editions have **no joined catalogue record**; conversely
  some catalogue records have no readable in-scope edition. Missing
  `ruler`, `period`, `provenience`, etc. must remain missing.
  Use the audit's `catalogue.missing_document_keys` and
  `catalogue.unmatched_catalogue_keys` for exact identities.
- A subset of ORACC words lacks complete lemma/normalization annotation:
  the candidate has **31,770 unlemmatised words**, with further missing
  `norm` values and compounds with multiple lexical analyses. Counting
  word occurrences solely by `cf` or by the repeated `inst` source
  string can misstate frequency. See [Words and lexemes](words-and-lexemes.md).

## Graph and cuneiform semantics

- The TF slot type is `sign`, but **689** of its slots are technical,
  empty `synthetic=1` position anchors in this source snapshot. They
  are not Unicode cuneiform, attested signs, or silently restored
  content. Do not add them to source-sign statistics.
- Some actual semantic signs lack `utf8` Unicode rendering; missing
  Unicode is not a normalized damage label. ORACC editorial unreadability
  and damage require philological interpretation of source GDL, not an
  invented `F.break` feature.
- Some words contain zero semantic signs yet remain source occurrence
  nodes anchored at technical positions. See [Signs](signs.md) and the
  [data model](model.md).
- Document Q-numbers are **not globally unique** across projects.
  The current audit identifies cross-subproject Q collisions; join with
  qualified `document_key`, not bare `text_id`.
  See [Document identity](identity.md).
- This is an editorial text corpus, **not** an image/3D facsimile of
  original inscriptions. Conversion cannot independently verify physical
  readings, restorations, or archaeological provenance.

## Translation scope and alignment

Official TEI translations have uneven coverage. For the pinned
`riao-teiCorpus-20241202.zip`, **6,792 units** have source-supported
line-range alignment, while **2,509 units** are recorded as explicit
alignment gaps. A missing range, unresolved source line, or absent
document is not mapped to a guessed position.

The `rinap5p1` subproject has **no corresponding official running
translation records in this pinned archive** (0 of its 138 populated
editions). This does not establish that no translation exists elsewhere;
it only describes the imported source and release candidate.

A normal consumer can query aligned units through
`E.translation_line.t(line)`. The build records unresolved TEI units in
`translation-gaps.json` next to the TF feature files. This gap
inventory does not mean that every source line is translated.
Read [Translations](translations.md) for the inclusive range model,
TEI markup handling, and the exact gap categories.

## Upstream licences and attribution

A `corpusjson` root may declare **CC0** even when the same annotated
edition's catalogue credits or Oracc site assert **CC BY-SA 3.0**. The
pinned Q001801 example is source-verifiable. This is a **rights ambiguity**,
not permission to erase original contributors or to sublicense all texts as
MIT. The official translation source has separate licence qualifications.
See [Citation and source rights](citation.md) for conservative use and
proper upstream editorial credit.

## Performance and release state

The default interactive app excludes certain heavy source/audit features
from preload, but they remain on disk and can be loaded explicitly; some
queries may require substantially more memory. Consult the
[measured installation profile](installation.md).

The **standalone publication and checksum are not yet published** as part
of the pre-1.0 state described here. A successful builder/CI staging test
is not evidence that a versioned corpus ZIP is publicly downloadable.
