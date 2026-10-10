---
title: Corpus scope and sources
status: active
---

# Corpus scope: Assyrian royal inscriptions

The `assyrian-royal-inscriptions` Text-Fabric dataset joins annotated
**RIAO** (*Royal Inscriptions of Assyria Online*) and **RINAP**
(*Royal Inscriptions of the Neo-Assyrian Period*) material from
[ORACC](https://oracc.museum.upenn.edu/).

The registered build uses eleven ORACC subprojects:
`riao/ria1`–`riao/ria5`, `rinap/rinap1`–`rinap/rinap5`, and
`rinap/rinap5p1`. The exact registered source selection is in
[`datasets.toml`](https://github.com/alexsosn/ORACC-TF/blob/main/datasets.toml).
The joined data preserves source editions, signs, word occurrences,
canonical lexemes, sections, line identity, and available catalogue
metadata. Read the [data model](model.md) for the graph and
[document identity](identity.md) for globally qualified
`document_key` values such as `riao/ria1:Q001801`.

The **source** is ORACC's editorial `corpusjson`/GDL data. ORACC-TF
converts it into TF features and edges; conversion does not constitute
a new decipherment, new physical-inscription reading, or a diplomatic
facsimile. Catalogues can describe objects and their provenance, but
the dataset does not itself ship high-resolution tablet images or 3D
models. Other ORACC projects, and witness-only `scores` and `sources`
subprojects, are outside this semantic resource.

The pinned official RIAO **TEI** archive supplies running translations
where source-supported line-range matching is possible. A translated
unit may cover multiple source lines; some TEI units cannot be aligned
and `rinap5p1` has no coverage in that pinned archive. This is a
limitation of *the imported source*, not a claim that the inscriptions
have never been translated. See [Translations](translations.md).

Source coverage is uneven. Some readable editions have no catalogue
record, some catalogues are not backed by a readable text, a few
source files are unreadable, and words vary in lexical annotation.
The [source-to-TF audit](data-audit.md) lists the exact mismatches and
its [limitations page](known-issues.md) gives the researcher-facing
interpretation. Do not infer missing forms, data or translations from
neighboring ORACC documents.

For acquiring the corpus without the central developer source
checkout, follow the [quick start](quick-start.md) and
[installation profile](installation.md). A verified staged ZIP is not
automatically a public 1.0 release; publication is a separate gate.
