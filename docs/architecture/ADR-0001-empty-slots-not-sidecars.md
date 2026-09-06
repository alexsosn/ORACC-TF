# ADR-0001: Represent zero-span textual entities with explicit empty slots

Status: Accepted

## Decision

Text-Fabric corpora maintained by this project family MUST represent source entities that have a textual position but no ordinary semantic slot by introducing an explicit empty/synthetic slot inside the Text-Fabric warp.

Do not move such entities into a sidecar merely because Text-Fabric requires every non-slot node to span at least one slot.

This applies to empty/signless words, empty lines, vacats, comments or other textual anchors, and otherwise-empty documents/sections that must remain addressable in Text-Fabric.

The empty slot is a technical positional anchor, not an assertion that a real grapheme/sign/token exists in the source.

## Required modelling contract

1. Keep the corpus's normal slot type. For cuneiform corpora whose slot type is `sign`, an empty anchor is still a `sign` slot because Text-Fabric has exactly one slot type per dataset.
2. Mark empty anchors explicitly, e.g. `type=empty` and/or `synthetic=1`, so they cannot be mistaken for source graphemes.
3. Preserve source cardinalities separately from TF slot cardinalities. Reports MUST distinguish semantic/source slots from synthetic empty slots and total TF slots.
4. Empty words receive an empty slot at their textual position.
5. Empty lines/containers receive an empty slot only when no descendant already supplies an anchor.
6. A wholly empty document receives an empty slot only when it would otherwise have no slot at all.
7. Ancestor nodes span the empty slot through normal `oslots`; do not create one empty slot per ancestor merely to satisfy TF.
8. Do not borrow a neighbouring real slot. That falsely assigns the entity another source object's textual extent.
9. Do not invent a visible Unicode sign or token value. Empty anchors should render as empty unless a corpus has an explicit source-level vacat/comment representation.
10. Sidecars remain appropriate only for data that is genuinely outside the Text-Fabric textual graph, not as a workaround for zero-length textual nodes.

## Precedent

This follows established Text-Fabric corpus practice rather than a project-local workaround.

- ETCBC/DSS creates empty slots for words with no glyphs and for vacat/other clusters with no signs, explicitly to anchor them in the text sequence.
- The Nino-cunei `tfFromAtf` converter used for Old Babylonian / Old Assyrian creates a slot when an empty line or document would otherwise be unlinked.

These precedents establish an important semantic distinction: an empty slot is a positional device in the TF warp, not fabricated philological content.

## Agent rule

Autonomous implementation/review agents working on a Text-Fabric corpus in this project family MUST treat this ADR as the default architectural rule.

Before proposing a zero-span sidecar, an agent must first test whether the entity belongs to the textual graph and can be represented by an explicit empty slot. A sidecar proposal for textual zero-span nodes is an architectural deviation and requires an explicit corpus-specific ADR explaining why empty-slot anchoring is semantically invalid.

## Testing requirements

Converters that can encounter zero-span source entities must include tests that prove:

- empty anchors are emitted deterministically;
- source/semantic slot counts exclude empty anchors;
- total TF slot counts include them;
- zero-span words/lines/documents remain queryable through normal TF relations;
- no neighbouring real slot is borrowed;
- no visible or lexical content is fabricated;
- repeated builds are byte- or graph-deterministic as appropriate;
- consumers can distinguish `empty`/`synthetic` anchors from real source slots.

## Consequence for ORACC-TF

The earlier `zero-span.json`/sidecar approach for ORACC textual nodes is superseded by this decision. Issue #37 and PR #63 must be redesigned around explicit empty-slot anchoring before merge. Any remaining sidecar use must be justified by data that is truly non-textual rather than merely zero-span.
