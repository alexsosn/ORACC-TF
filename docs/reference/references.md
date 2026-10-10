---
title: References and scholarly context
status: active
---

# References for the RIAO/RINAP corpus

The ORACC-TF dataset depends on the scholarly data and editorial work
published by the [Open Richly Annotated Cuneiform Corpus (ORACC)](https://oracc.museum.upenn.edu/).
The two principal source-project entry points are:

- [Royal Inscriptions of Assyria Online (RIAO)](https://oracc.museum.upenn.edu/riao/):
  editions from the royal inscription tradition assembled in `riao/ria1`
  through `riao/ria5`.
- [Royal Inscriptions of the Neo-Assyrian Period (RINAP)](https://oracc.museum.upenn.edu/rinap/):
  editions used by the `rinap/rinap1` through `rinap/rinap5` and
  `rinap/rinap5p1` source subprojects.
- [The Text-Fabric project](https://annotation.github.io/text-fabric/):
  graph/feature data format, Python API and browser interface in which
  ORACC-TF publishes the converted material.

The converter's actual dataset selection is defined in the
[`datasets.toml`](https://github.com/alexsosn/ORACC-TF/blob/main/datasets.toml).
The [source-to-TF audit](data-audit.md) describes its completeness
and reader-facing exceptions. The [reproducibility guide](reproducibility.md)
explains how to identify the exact pinned source and converted release.

## One source-grounded publication example

The ORACC RIAO catalogue credits for
`riao/ria1:Q001801` identify the printed source as:

A. Kirk Grayson, *Assyrian Rulers of the Third and Second Millennia BC
(to 1115 BC)* (Toronto, 1987), RIMA 1.

The catalogue separately credits Jamie Novotny for adaptation and Nathan
Morello for lemmatization/update of this online edition. This reference
identifies the scholarly basis of **Q001801**, not every text in RIAO
or RINAP. Use each other inscription's own ORACC catalogue credits
to select the appropriate volume, edition and contributors.

For citations of **individual inscriptions**, follow the scholarly
edition's own ORACC page, credits and bibliographic references.
Different subprojects and individual records can have different
editors, editions, or source-specific reuse rights. A list of project
URLs is not a substitute for citing the text's original editor,
edition, translation, and publication. For example, the
`riao/ria1:Q001801` catalogue explicitly credits the Grayson
edition and later digital adaptation/lemmatization (see
[Acknowledgements](acknowledgements.md)).

Consult [Citation and licensing](citation.md) before publishing
derived text/translation data. The ORACC-TF software's MIT licence
does not relicense the scholarly corpus or official TEI translations.
