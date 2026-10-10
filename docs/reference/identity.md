---
title: Document identity
status: active
---

# Document identity

A bare ORACC Q-number is not a unique document identity in the joined
RIAO/RINAP corpus. ORACC-TF uses the qualified key

```text
<subproject>:<Q-number>
```

and stores it in `document_key` across the graph. The current source snapshot
contains **140** Q-numbers reused across subprojects; **48** of those collisions
refer to materially different source content.

## Q003840: the silent bare-Q failure

Both of these documents exist:

- `rinap/rinap5:Q003840`
- `rinap/rinap5p1:Q003840`

They do not describe the same catalogue object. The joined metadata regression
pins different designations, languages, object types, and proveniences for the
two qualified records. A dictionary keyed only by `Q003840` will silently
overwrite one of them.

Wrong:

```python
# Unsafe: a later subproject can overwrite an earlier document with the same Q.
by_q = {
    api.F.text_id.v(doc): doc
    for doc in api.F.otype.s("document")
}
doc = by_q["Q003840"]
```

Safe:

```python
by_document_key = {
    api.F.document_key.v(doc): doc
    for doc in api.F.otype.s("document")
}

rinap5 = by_document_key["rinap/rinap5:Q003840"]
rinap5p1 = by_document_key["rinap/rinap5p1:Q003840"]
assert rinap5 != rinap5p1
```

The same rule applies to joins with catalogue records, translations, external
tables, notebooks, and downstream databases: preserve the subproject qualifier
until an external identifier has been independently verified as globally unique.

## Which identifier to use

- Use `document_key` for ORACC-TF document identity and cross-node joins.
- `text_id` is the unqualified Q-number and is useful for display or
  source-local operations, not as a joined-corpus primary key.
- Word/source ids such as `Q003333.l04f6b` also need their document context
  when crossing subproject boundaries.
- External links must be derived from the qualified source identity; do not
  construct them from a bare Q-number when the target system's identity rules
  have not been verified.

The generated [`document_key` feature reference](features/mixed/document_key.md)
shows 2,078 distinct qualified document values in the current corpus.
