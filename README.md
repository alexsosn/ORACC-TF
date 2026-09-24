# ORACC-TF

ORACC-TF builds [Text-Fabric](https://annotation.github.io/text-fabric/) datasets from
[ORACC](https://oracc.museum.upenn.edu/) open data. The central repository keeps
the source snapshot, conversion code, validation, documentation, and release
tooling needed to build those datasets reproducibly.

## Status

**ORACC-TF is pre-1.0.** The first release target is
`assyrian-royal-inscriptions`, a semantic corpus built from RIAO and RINAP
material. The current user-facing release gate is tracked in
[#89](https://github.com/alexsosn/ORACC-TF/issues/89).

This repository is the **builder/source repository**, not the intended
installation surface for researchers. It contains the large ORACC source tree
and development infrastructure. Current 1.0 work is producing a lightweight
standalone distribution with the Text-Fabric data, corpus app, and researcher
documentation, so using the corpus will not require cloning this repository.

If you are looking for a stable end-user package, 1.0 has not been published
yet.

## First dataset: `assyrian-royal-inscriptions`

The dataset is defined in [`datasets.toml`](datasets.toml). Its source selection
aggregates:

- RIAO 1–5;
- RINAP 1–5 plus RINAP 5 Part 1;
- the RIAO TEI corpus source used for the translation workstream.

The converter preserves ORACC textual structure and annotations in Text-Fabric,
including sign slots, words, lexemes, document/face/column/line structure,
catalogue metadata, qualified document identity, and source-grounded cuneiform
and transliteration features. Zero-span textual entities are represented by
explicit synthetic empty slots rather than fabricated visible text.

The generated feature inventory is documented in
[`docs/reference/features.md`](docs/reference/features.md). Translation import,
the standalone app, installation path, and the complete researcher manual are
still part of the 1.0 work.

## Researcher documentation

User-facing documentation lives under
[`docs/reference/`](docs/reference/):

- [Data model](docs/reference/model.md)
- [Signs](docs/reference/signs.md)
- [Words and lexemes](docs/reference/words-and-lexemes.md)
- [Translations](docs/reference/translations.md)
- [Document identity](docs/reference/identity.md)
- [Query guide](docs/reference/query-guide.md)
- [Reproducibility](docs/reference/reproducibility.md)
- [Feature reference](docs/reference/features.md)

The 1.0 manual is still being completed under
[#78](https://github.com/alexsosn/ORACC-TF/issues/78) and
[#82](https://github.com/alexsosn/ORACC-TF/issues/82). Pages marked as
`skeleton` describe the intended documentation surface but are not yet release
documentation.

Maintainer research, design plans, reports, and the agentic-development
registry are indexed separately in [`docs/README.md`](docs/README.md).

## Development quick start

ORACC-TF requires Python 3.10 or newer.

```bash
git clone https://github.com/alexsosn/ORACC-TF.git
cd ORACC-TF

python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

pytest -q -m 'not corpus'
```

The fast test suite does not require a full-corpus run. Whole-corpus and
integration work uses the source data under `data/` and is intentionally
separate from the normal researcher installation path.

## Repository layout

| Path | Purpose |
|---|---|
| [`datasets.toml`](datasets.toml) | semantic dataset definitions and source membership |
| [`programs/oracc_tf/`](programs/oracc_tf/) | conversion and build code |
| [`tests/`](tests/) | unit, contract, corpus, and integration tests |
| [`docs/reference/`](docs/reference/) | researcher-facing corpus documentation |
| [`docs/research/`](docs/research/) | measured research behind design decisions |
| [`docs/plans/`](docs/plans/) | implementation plans and acceptance criteria |
| [`data/`](data/) | large ORACC source working tree used by the builder |
| [`scripts/`](scripts/) | repository maintenance and analysis utilities |

Low-level source-tree maintenance commands are documented in
[`docs/guides/G-001-scripts.md`](docs/guides/G-001-scripts.md). Those utilities
are useful for maintaining local source material, but simple archive extraction
or size verification alone is not equivalent to release provenance.

## Data model

The Text-Fabric slot type is `sign`. Source words and higher structural nodes
are connected to those slots through the normal TF graph. Technical empty
positions use `synthetic=1` sign slots that preserve ordering but carry no
fabricated cuneiform, transliteration, or lexical content.

See the [data-model reference](docs/reference/model.md) and
[ADR-0001](docs/reference/architecture/ADR-0001-empty-slots-not-sidecars.md) for
the current rule.

## Licence

Software authored for this repository—including converter code, scripts, tests,
and supporting software documentation—is licensed under the
[MIT License](LICENSE).

The MIT licence does **not** apply to ORACC corpus texts, translations,
annotations, metadata, or other upstream/derived data. Those retain the terms
of their original sources. See [`LICENSE_SCOPE.md`](LICENSE_SCOPE.md) for the
code/data boundary and the corpus documentation for source-specific attribution
and licensing.
