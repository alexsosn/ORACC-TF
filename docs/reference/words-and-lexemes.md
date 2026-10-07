---
title: Words and lexemes
status: active
---

# Words and lexemes

A `word` node is a source occurrence. A `lex` node is a canonical lexical
identity used to connect occurrences that share the same
`(lang, cf, gw, pos)` key. The two domains must not be counted as though every
word had exactly one lexeme.

The corpus contains 320,975 source/TF word nodes and 8,025 lexeme nodes.
The generated [`word_lex` reference](features/edge/word_lex.md) currently
records 289,205 linked word occurrences and 289,824 word→lex links. Five words
have three outgoing lexeme links and 609 have two.

## Word-level lexical fields

The source fields are preserved independently; missing one does not license the
converter to infer it from another.

| feature | interpretation |
|---|---|
| `cf` | citation form / canonical lexical form supplied by ORACC |
| `gw` | ORACC guide word (gloss-like lexical discriminator) |
| `sense` | source sense when supplied; it may be narrower than `gw` |
| `norm` | normalized occurrence form; normalization alone is not lemma evidence |
| `pos` | source part of speech used in the canonical lexeme key |
| `epos` | effective/contextual part-of-speech value on the occurrence |
| `sig` | ORACC occurrence signature; for compound forms it can encode several analyses |

Four source-coverage cases are easy to conflate:

| case | words |
|---|---:|
| unlemmatised words | 31,770 |
| lemmatised words with no `norm` | 878 |
| norm-only but unlemmatised placeholders | 230 |
| unlemmatised words with no `form` | 0 |

Separately, 295 source words contain zero semantic signs. They are still normal
TF word nodes; their position is supplied by a `synthetic=1` empty anchor.
See [Signs](signs.md).

## One word can link to several lexemes

Q003333.l04f6b is a compound occurrence whose three analyses resolve to three
distinct lexeme nodes:

- `šattu[year]N`
- `rēšu[head]N`
- `šarrūtu[kingship]N`

The TF graph represents those analyses as three outgoing `word_lex` edges.
For an occurrence node:

```python
word = next(
    n for n in api.F.source_id.s("Q003333.l04f6b")
    if api.F.otype.v(n) == "word"
)
lexemes = api.E.word_lex.f(word)
assert len(lexemes) == 3
```

The reverse direction gives the word occurrences linked to a lexeme:

```python
target = next(
    n for n in api.F.otype.s("lex")
    if (
        api.F.lang.v(n),
        api.F.cf.v(n),
        api.F.gw.v(n),
        api.F.pos.v(n),
    ) == ("akk", "mātu", "land", "N")
)

correct_words = set(api.E.word_lex.t(target))
```

This is the correct basis for lexical occurrence frequency.

## The naive frequency count

A naive count based only on the direct `cf` feature of word nodes misses
non-head analyses of compound forms:

```python
naive_words = {
    n for n in api.F.cf.s("mātu")
    if api.F.otype.v(n) == "word"
}

# This may be smaller than the edge-based set because compound analyses
# are represented by word_lex rather than duplicated into the word's cf field.
missing_from_naive = correct_words - naive_words
```

Q009276.l00a19 shows a second reason not to count raw analysis syntax. Its
`inst` string has **14** slots: one `šakin[governor]N` occurrence and
thirteen repetitions of `māti[land]N`. The canonical occurrence signature
resolves the word to only **two** distinct lexemes:
`šaknu[appointee]N` and `mātu[land]N`. Counting `inst` components would
inflate lexical frequency; counting `word_lex` edges preserves distinct
word→lex relations.

The raw `sig` and `inst` fields remain available for source audit and
philological inspection. They should not replace the canonical `word_lex`
relation for corpus frequency calculations.
