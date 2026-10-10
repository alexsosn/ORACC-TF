---
title: Query guide
status: active
---

# Query guide

These recipes use the public Text-Fabric API for the **released**
`assyrian-royal-inscriptions` RIAO/RINAP corpus. First follow the
[quick start](quick-start.md), which leaves `api = A.api` available. All
queries run against the extracted `app/` and `tf/`; none imports the
ORACC-TF converter or accesses its development source tree.

## Find a passage by qualified document identity

A bare `Q001801` is not a reliable joined-corpus key. Match its subproject
as well, then traverse the actual `line` and `word` nodes:

```python
key = "riao/ria1:Q001801"
document = next(
    n for n in api.F.otype.s("document")
    if api.F.document_key.v(n) == key
)
line = next(
    n for n in api.L.d(document, otype="line")
    if api.F.line.v(n) == "Q001801.1"
)
word_nodes = api.L.d(line, otype="word")
passage = [
    (api.F.source_id.v(word), api.F.form.v(word))
    for word in word_nodes
]
print(passage)
```

Use `api.L.d(line, otype="sign")` for its Text-Fabric **slot** extent.
A technical sign with `synthetic=1` is a positional anchor, not a
transcribed sign. See [Signs](signs.md).

## Find a lexeme and count occurrences

The `cf` feature on a word is not a substitute for the canonical lexical
relation when a compound word has multiple analyses. Identify the `lex`
node using its full lexical key, then traverse **incoming** `word_lex`
edges to distinct word occurrence nodes:

```python
lex = next(
    n for n in api.F.otype.s("lex")
    if (
        api.F.lang.v(n), api.F.cf.v(n),
        api.F.gw.v(n), api.F.pos.v(n),
    ) == ("akk", "mātu", "land", "N")
)
occurrences = set(api.E.word_lex.t(lex))
print(len(occurrences))
```

The count reflects linked word occurrences. It does not count repeated
`inst` string components, nor does it assume a word has exactly one lexeme.
Consult [Words and lexemes](words-and-lexemes.md) before using this as a
frequency denominator.

## Slice by catalogue metadata

The document-level `ruler` and `period` features come from the joined
ORACC catalogue and may be missing. This produces actual observed category
frequencies without assuming an invented ruler name or fabricating metadata:

```python
from collections import Counter

reigns = Counter()
for doc in api.F.otype.s("document"):
    ruler = api.F.ruler.v(doc)
    period = api.F.period.v(doc)
    if ruler is not None and period is not None:
        reigns[(period, ruler)] += 1

print(reigns.most_common(10))
```

Keep `document_key` when exporting matching documents to a table or
joining external catalogues: the corpus contains cross-subproject Q-number
collisions. See [Document identity](identity.md).

## Retrieve translations overlapping a line

Official TEI translation units may cover several lines. The
`translation_line` edge is from the `translation_unit` node **to the
covered `line` node**, so ask for incoming units. Preserve the inclusive
source `translation_sref` / `translation_eref` boundaries:

```python
line = next(
    n for n in api.F.line.s("Q001801.1")
    if api.F.document_key.v(n) == "riao/ria1:Q001801"
)
translation_units = api.E.translation_line.t(line)
ranges_and_text = [
    (
        api.F.translation_sref.v(unit),
        api.F.translation_eref.v(unit),
        api.F.translation_text.v(unit),
    )
    for unit in translation_units
]
print(ranges_and_text)
```

An empty result is meaningful, not permission to align a nearby translation
heuristically. The pinned official archive has **no `rinap5p1` TEI running
translations**; other source ranges are explicitly unresolved. Read the
[translation model and coverage gaps](translations.md).

## Source-aware damage/unreadable inspection

There is **no normalized `F.break` damage boolean** in the current TF
feature inventory. Do not use lack of `utf8` as a damage test, and do not
mistake `synthetic=1` empty positional slots for broken signs. A reliable
philological damage predicate requires classifying the **source GDL state**
with documented editorial conventions; ORACC-TF does not currently expose
that predicate as a ready-made TF feature.

For manual source inspection, request the heavy `sign_json` feature **on
demand** rather than preloading it for every ordinary query:

```python
import json

A.load("sign_json")  # intentionally excluded from default interactive preload
api = A.api  # refresh after explicitly loading an additional feature
sign = next(
    n for n in api.F.otype.s("sign")
    if api.F.synthetic.v(n) != 1
    and api.F.sign_json.v(n) is not None
)
source_gdl = json.loads(api.F.sign_json.v(sign))
print(source_gdl)  # inspect source conventions; not a damage classification
```

Loading `sign_json` can substantially increase memory use. See
[Lightweight installation](installation.md) for the measured tradeoff, and
the [generated feature reference](features.md) for exact field domains.

## Mistakes worth avoiding

| Mistake | Correct representation |
|---|---|
| Grouping all documents by bare Q-number | Use qualified `document_key` |
| Treating all TF sign slots as attested cuneiform | Exclude `synthetic=1` for source-sign counts |
| Counting a lemma solely by occurrence `cf` or repeated `inst` fields | Follow `word_lex` from canonical lexeme to distinct words |
| Assuming every source line has a translated string | Follow `translation_line` ranges; gaps are explicit |
| Treating an absent Unicode form as a broken/technical slot | Inspect source semantics and the separate `synthetic` flag |
