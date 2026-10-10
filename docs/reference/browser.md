---
title: Text-Fabric browser guide
status: active
---

# Open and use the Text-Fabric browser

From a properly extracted standalone `assyrian-royal-inscriptions`
corpus directory (containing `manifest.json`, `tf/`, `app/`, and
`docs/`), install the exact measured runtime as described in
[Installation](installation.md), then start the browser:

```bash
python -m pip install text-fabric==13.1.0
tf "app:$PWD/app"
```

Replace `$PWD/app` with an absolute `app/` path when your shell does
not define `$PWD`. This **app:** route has been tested with the
Text-Fabric 13.1 parser. Do not substitute a `data:` browser argument
without validating it against the actual pinned runtime.

## Navigation and features

The generated app provides normal document/section browsing and
researcher-oriented feature inspection. Start from a document with its
qualified identity: the joined corpus has Q-numbers that occur in
more than one ORACC subproject. Use the passage interface to inspect
its lines, signs, words, and lexical features. The browser's default
text format is `text-trans-full` (transliteration); the corpus also
declares `text-orig-full` for cuneiform and `lex-default` for
lexeme rendering. See [Text formats](text-formats.md).

The real-browser smoke gate exercises the routes `/`,
`/passage`, `/query`, and `/export` for the current app. Queries
should respect `document_key` and the `word_lex` and
`translation_line` relations instead of assuming that a bare Q
value, lemma string, or a one-line translation field is unique.
For Python examples consult the [query guide](query-guide.md).

## Feature-help and offline limitations

Feature-help links open **the existing ORACC-TF source repository** on
GitHub, at `ORACC-TF/blob/<builder_commit>/docs/reference/features.md#<feature>`.
The registered release build pins `<builder_commit>` to the exact Git SHA
recorded in the distribution manifest. Ad hoc app generation defaults to the
current `main` reference; that moving ref is not a suitable published
release identity. The feature index provides anchors for individual fields
such as `word_lex` and `translation_line`.

These links still require internet access. The pinned Text-Fabric browser
does **not** itself serve the local Markdown help from `docs/`. For offline
reading, open the bundled `docs/index.md` directly and follow the
[generated feature inventory](features.md). Publication acceptance must
follow the **actual generated help links** against the pinned source commit,
not merely assume they work because the browser itself starts.

A candidate ZIP can have complete local docs without being a publicly
downloadable release; that separate publication check remains necessary.

## Memory and missing values

The browser preload excludes some heavy raw/audit fields to keep
ordinary startup feasible; those fields remain shipped in the TF
data and can be loaded explicitly when research requires them.
The [installation measurements](installation.md) report disk and
memory costs. `synthetic=1` sign anchors carry no invented visible
text, and not every line has an aligned translation. See
[Signs](signs.md) and [Translations](translations.md).

This describes the tested candidate and its supported interfaces;
the versioned public **release publication** is a separate step.
