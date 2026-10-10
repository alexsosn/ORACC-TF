---
title: Signs
status: active
---

# Signs

The Text-Fabric slot type is `sign`, but two kinds of slot must be kept
separate when interpreting the corpus:

- **792,651 semantic/source signs** come from ORACC GDL objects that the
  converter classifies as textual sign content.
- **689 synthetic technical slots** preserve source order for textual loci that
  have no semantic sign extent. They are marked `synthetic=1` and carry no
  fabricated cuneiform or lexical content.

The resulting TF graph has 793,340 slots. The source-to-TF audit checks the two
populations separately and currently reports no source-sign payload leaking onto
synthetic slots. See [Data model](model.md) and
[Source-to-TF audit](data-audit.md).

## What the semantic sign count means

The figure 792,651 is a **classification count over this ORACC source
snapshot**. It is not a claim about the number of physical sign impressions on
the surviving tablets. ORACC GDL contains textual objects, grouping operators,
rendering instructions, qualifiers, restorations, and normalized editorial
representations; the converter must decide which objects constitute the
semantic sign sequence used as TF slots.

The whole-corpus GDL census for the pinned snapshot is:

| disposition | GDL objects |
|---|---:|
| semantic slot | 792,651 |
| structural | 178,869 |
| rendering | 6,584 |
| modifier | 10 |
| unknown | 0 |

Those classes are defined by the converter and regression-tested against actual
GDL shapes. An unknown shape fails conversion rather than silently becoming a
slot.

## Numeral example: Q005620

A previous leaf-oriented rule could count the rendering child of a composite
numeral instead of the numeral object itself. In Q005620, the source object for
`1(diš)` carries the cuneiform value **𒁹** and is one semantic slot. Its
nested `{"r": "1"}` child is rendering metadata.

Conceptually:

```text
GDL parent:  n="n", form="1", sexified="1(diš)", utf8="𒁹"  -> semantic slot
child:       r="1"                                         -> rendering
```

The regression fixture identifies the source path
`Q005620.l00a19/gdl[0]` and requires that the parent payload, including
`utf8`, `form`, `sexified`, and source id, survives classification.

## Synthetic empty slots

A source word or independently positioned textual unit can legitimately have no
semantic GDL sign. Such an object stays in the normal TF graph. The slot planner
inserts the minimum positional anchor and sets `synthetic=1`.

When interpreting signs:

```python
semantic_slots = [
    n for n in api.F.otype.s("sign")
    if api.F.synthetic.v(n) != 1
]
empty_anchors = [
    n for n in api.F.otype.s("sign")
    if api.F.synthetic.v(n) == 1
]
```

Do not treat `len(api.F.otype.s("sign"))` as a source-sign count without
filtering synthetic anchors. Conversely, do not discard synthetic slots when
working with TF topology: they are the positional support that keeps signless
source words and sections queryable.

## Missing, damaged, and unreadable content

Absence of `utf8` on a semantic slot does not make that slot synthetic.
Editorial damage, unreadable signs, or source forms lacking a Unicode rendering
remain source content and retain their source identity. The `synthetic` flag,
not the presence of `utf8`, distinguishes a technical anchor from a semantic
source sign.

For field-level definitions, see the generated
[feature reference](features.md), especially
[`synthetic`](features/mixed/synthetic.md) and
[`oslots`](features/edge/oslots.md).
