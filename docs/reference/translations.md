---
title: Translations
status: active
---

# Translations

ORACC-TF imports the official RIAO TEI corpus export
[`riao-teiCorpus-20241202.zip`](https://oracc.museum.upenn.edu/riao/downloads/riao-teiCorpus-20241202.zip).
The importer verifies its SHA-256 digest before parsing:

`b793d8920db58908e3a044b7f2d1a204c1ba0784e880007e0cd7941333e841bd`

The archive contains 1,639 qualified RIAO/RINAP document records and 9,301
translation-related TEI units. Running text is stored on `translation_unit`
nodes with the original TEI markup retained in `translation_text_raw`. The
source's inclusive `xtr:sref`/`xtr:eref` ranges resolve through the current M3
line graph; an explicit `xtr:ref` is represented as a one-line range. A range's
Text-Fabric `oslots` is the union of the current `SlotPlan.section_slots` for
those lines, including technical synthetic anchors where needed. This preserves
position without adding visible text or borrowing a neighbouring sign.

The importer retains TEI `tr` and `dollar` subtypes. A TEI unit without a source
range, an unresolved source line, or a document absent from the edition build
is recorded as an explicit alignment gap and is omitted from the aligned TF
graph. It is never assigned a guessed line. The pinned 2024 archive produced
6,792 aligned translation units and 2,509 explicit gaps; `rinap5p1` has no TEI
record in the archive (0 of its 138 populated editions). The real-source test
rechecks the complete graph and representative 1–15 and 1–72 line ranges.

Each corpus build writes a deterministic `translation-gaps.json` beside the
Text-Fabric feature files. Its `gaps` records preserve the qualified document
key, stable translation identity, source `xml:id` when present, subtype, range,
source archive digest, and a machine-readable reason (`missing-source-range`,
`unresolved-source-range`, or `document-not-in-corpus`). This lets consumers
inspect every omitted unit rather than relying only on aggregate coverage.

## Registered builds

Registered publication builds require the pinned archive, so a release artifact
cannot silently omit its translations. Download and verify the source with
`scripts/download_m9_tei.sh PATH`, then pass the archive to
`build_registered_tf(..., translations_archive=PATH)`, or set
`ORACC_TF_M9_TEI_ARCHIVE` to its path. In both cases the parser verifies the
pinned SHA-256 digest before the corpus build proceeds. The registered builder
raises an error when the archive is missing or has changed.

To retrieve the source translation units that explicitly cover a line, follow
the `translation_line` edge from the line node. There is no `line.translation`
feature because a unit may span several lines:

```python
line = next(
    node for node in api.F.line.s("Q001801.1")
    if api.F.document_key.v(node) == "riao/ria1:Q001801"
)
unit_nodes = api.E.translation_line.t(line)
units = [
    {
        "text": api.F.translation_text.v(node),
        "source_range": (
            api.F.translation_sref.v(node),
            api.F.translation_eref.v(node),
        ),
        "subtype": api.F.translation_subtype.v(node),
    }
    for node in unit_nodes
]
```

## Attribution and licence

The archive's TEI header does not state a per-unit licence. ORACC's published
guidance says its default is CC BY-SA 3.0 unless a project states otherwise.
The source licence recorded on translation features therefore says
“ORACC default CC BY-SA 3.0; project-specific terms may differ” and links to
[ORACC's licensing guidance](https://oracc.museum.upenn.edu/doc/about/).
This translation-source statement is separate from the `license` and
`license_url` features copied from `corpusjson` metadata; those metadata
currently say CC0 for the RIAO/RINAP editions. The converter does not treat that
edition metadata as a TEI-specific rights grant.
