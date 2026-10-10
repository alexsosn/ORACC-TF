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

The app currently generates **feature-help links to GitHub**, at
`ORACC-TF-assyrian-royal-inscriptions/blob/main/docs/reference/features.md`,
rather than serving local Markdown help directly from the
`docs/` directory. Their availability requires the corresponding
**published dataset repository** and its reference tree to exist.
A candidate ZIP can have complete offline `docs/` while those online
help links remain unavailable. Do not consider a staging/browser HTTP
200 result proof that every external help destination works.

For offline reading, open the bundled `docs/index.md` directly
and follow the [generated feature inventory](features.md). Future
publication must check the **actual link destination** and version
match, not assume it is live because `docs/` was packaged.

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
