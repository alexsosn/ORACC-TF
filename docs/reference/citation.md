---
title: Citation and rights
status: active
---

# Citation, credit, and source rights

ORACC-TF builds a Text-Fabric graph from existing scholarly editions; **the
ORACC editors and projects remain the creators of the underlying text editions,
translations, lemmatization, and research**. The Text-Fabric converter and
the source material must be cited separately.

## Cite the exact dataset you queried

When the standalone `assyrian-royal-inscriptions` corpus is published,
identify that **specific release**, not just the converter's source repository.
Its distribution root includes `manifest.json`. Record these fields with
your methods and query outputs:

- `dataset` — `assyrian-royal-inscriptions`;
- `release_id` — the particular published archive/ref, once assigned;
- `tf_version` — the Text-Fabric data schema version;
- `builder_commit` — the ORACC-TF converter commit;
- `source_state` — the pinned input-source state digest;
- the published archive URL and retrieval date.

A citation template (fill from the actual published release's identity) is:

> ORACC-TF contributors. *Assyrian Royal Inscriptions (RIAO/RINAP),
> Text-Fabric dataset*, [release_id], [tf_version]. Built with
> ORACC-TF [builder_commit] from [source_state]. [Archive URL], accessed
> [date]. Underlying editions and translations: Oracc RIAO and RINAP
> projects and the text-specific editors acknowledged by Oracc.

Fill each bracket from the released `manifest.json` and release location.
Do not substitute the builder's package version for the dataset version.
For stable document-specific work, preserve the qualified `document_key`,
for example `riao/ria1:Q001801`. A bare Q-number is not unique across
the joined subprojects.

Cite the relevant upstream text page or printed RIAO/RINAP edition too.
These scholarly sources are the primary editions, not publications authored
by the converter contributors. Consult the current
[Oracc RIAO](https://oracc.museum.upenn.edu/riao/) and
[Oracc RINAP](https://oracc.museum.upenn.edu/rinap/) portals and
the individual catalogue credits for editors and bibliographic references.
For example, the Q001801 catalogue names *A. Kirk Grayson* as a basis and
credits adaptation/lemmatization to *Jamie Novotny* and *Nathan Morello*;
that record should not be replaced by a generic ORACC-TF author.

## Cite the conversion software separately

The repository's [`CITATION.cff`](https://github.com/alexsosn/ORACC-TF/blob/main/CITATION.cff)
covers the **software**, not all material shipped within a derived TF corpus.
When citing code, specify the repository
`https://github.com/alexsosn/ORACC-TF` and the converter Git revision.
The project-level software licence is **MIT**; it does **not** relicense
upstream texts, translations or metadata.

## Why the source licence boundary needs attention

The actual pinned `riao/ria1:Q001801` input illustrates a tension between
machine-readable and edition-level declarations:

- Its `corpusjson/Q001801.json` root reports **CC0**.
- The same subproject's `catalogue.json` credits for Q001801 say the
  *annotated edition* is released under **CC BY-SA 3.0**.
- Oracc's individual RINAP text pages likewise include scholarly author/editor
  attributions and, for some editions, explicit CC BY-SA 3.0 notices.
- The imported official TEI running translations have their own source
  declaration/attribution context. The pinned archive does not supply an
  independently established CC0 grant for each translation. The converter
  records an Oracc default CC BY-SA 3.0 qualifier, not a claim that all
  translated material is unrestricted.

These differing statements are a **source-level rights conflict/ambiguity**,
not something ORACC-TF can legally resolve by choosing the more permissive
machine-readable field. Do not infer that **all corpus data are CC0**, or
that MIT applies to the corpus. Keep source records and credits intact,
check edition/project-specific reuse terms, and follow the applicable
attribution/share-alike obligations before redistribution. Where the terms
are unclear or inconsistent, obtain clarification from the rights holders.

See the [translation-specific licence details](translations.md), the
[repo software/data licence boundary](https://github.com/alexsosn/ORACC-TF/blob/main/LICENSE_SCOPE.md),
and [known issues](known-issues.md) for other limitations.

## Do not infer release status or a DOI

A staged candidate, even if its manifest has a version, is not automatically
a publicly published dataset. Use the actual versioned GitHub Release URL and
matching checksum for a released archive. No DOI or blanket data licence is
implied by the converter or its `CITATION.cff`; cite the upstream source
editions and contributors separately.
