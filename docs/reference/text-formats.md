---
title: Text and display formats
status: active
---

# Cuneiform, transliteration, and lexeme formats

The Text-Fabric data declares three public text formats in its
`otext` metadata. Their definitions come from the converter's emitted
TF features; they are available on the standalone corpus, not special
renderers that require the ORACC-TF builder.

| Text-Fabric format | Source fields and behavior |
|---|---|
| `text-orig-full` | `sign#{utf8}{cuneiform_trailer}` — cuneiform Unicode at semantic sign slots, with a presentation-only space after the final semantic sign of a word |
| `text-trans-full` | `word#{form} ` — the source word's transliteration followed by a separating space |
| `lex-default` | `lex#{cf} [{gw}]` — lexical citation form and guide word |

## First passage in both scripts

After following the [quick start](quick-start.md), `api = A.api` is
available. Resolve a real line with a **qualified** document key
before rendering. The public `T.text` method accepts the format name:

```python
key = "riao/ria1:Q001801"
line = next(
    node for node in api.F.line.s("Q001801.1")
    if api.F.document_key.v(node) == key
)
cuneiform = api.T.text(line, fmt="text-orig-full")
transliteration = api.T.text(line, fmt="text-trans-full")
print(cuneiform)
print(transliteration)
```

The browser defaults to `text-trans-full`; users can select other
available display modes where the Text-Fabric interface supports it.

## What an empty or incomplete rendering means

TF uses `sign` as its slot type, but some slots are
`synthetic=1`: technical **zero-width positional anchors** for
source nodes without semantic sign content. They have no fabricated
`utf8` and are not counted as cuneiform. The visible word form still
comes from the source's `form` field, not from guessing a Unicode
sequence.

Not all **real semantic signs** have Unicode glyphs. Absence of
`utf8` is not itself evidence of a damaged or unreadable inscription.
The source GDL contains more detail than a simple Unicode output;
source-aware interpretation may require loading heavy audit features
on demand. The `cuneiform_trailer` is only a display separator, not
an epigraphic sign.

`lex-default` displays `cf` and `gw` for a lexeme, but a word
may have no recognized lemma, no normalization, or links to several
lexical analyses. Count occurrences with `E.word_lex` rather than
equating `cf` string frequency with all lemmatized word occurrences.

The background model and examples are in [Signs](signs.md),
[Words and lexemes](words-and-lexemes.md),
[Query guide](query-guide.md), and the
[generated feature descriptions](features.md).
