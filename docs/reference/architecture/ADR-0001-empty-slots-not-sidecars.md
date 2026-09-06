# ADR-0001: Represent zero-span textual entities with explicit empty slots

Status: Accepted  
Scope: project-family Text-Fabric architecture

## Decision

A source entity that **belongs to the textual sequence** and has an independent source position/order but no ordinary semantic slot MUST remain inside the Text-Fabric warp through an explicit empty/synthetic slot.

Do not move textual zero-span entities into a sidecar merely because Text-Fabric requires every non-slot node to span at least one slot.

The empty slot is a technical positional anchor. It is not an assertion that a real grapheme, cuneiform sign, character, or word exists in the source.

Typical cases include signless/empty words, vacats, empty textual lines, textual comments/markers, and otherwise-empty textual documents or sections that must remain addressable in source order.

## Scope boundary: textual loci vs non-textual graph nodes

This ADR does **not** require an empty content slot for every non-slot object with no semantic span.

- A textual entity with its own source position/order gets an explicit empty/synthetic slot when it otherwise has no slot.
- An ancestor/container reuses descendant slots, including descendant empty slots; do not make one synthetic slot per ancestor.
- A genuinely non-textual node with no independent textual position — for example a lexeme abstraction, manuscript record, resource, metadata record, or apparatus/provenance object — should normally anchor through its textual occurrence/locus or through an explicitly documented O(1) technical anchor if the corpus model requires one. Such an anchor must not be presented as that node's textual content.
- A sidecar is appropriate only when data is genuinely outside the Text-Fabric graph/API contract. **Zero span by itself is not sufficient reason for a sidecar.**

This distinction is important: preserving a zero-length textual position is different from assigning fake textual extent to metadata.

## Required modelling contract

1. Keep the corpus's normal slot type. Text-Fabric has one slot type per dataset, so in a cuneiform corpus with slot type `sign`, an empty positional anchor is technically a `sign` slot even though it is not a semantic cuneiform sign.
2. Mark empty anchors explicitly, e.g. `type=empty`, `is_gap=1`, and/or `synthetic=1`, so consumers can distinguish them from source content.
3. Preserve source cardinalities separately from TF slot cardinalities. Reports MUST distinguish:
   - semantic/source slots;
   - synthetic/empty slots;
   - total TF slots.
4. Empty words/textual units receive an empty slot at their source position.
5. Empty lines or textual containers receive an empty slot only if no descendant already supplies an anchor.
6. A wholly empty textual document receives an empty slot only if it would otherwise have no slot.
7. Ancestors span descendant real/empty slots through normal `oslots`; do not create redundant empty slots merely to satisfy TF.
8. Do not borrow a neighbouring real slot for a **textual zero-span entity**. That falsely assigns it another source object's textual extent.
9. Do not invent visible Unicode, grapheme, sign, token, or lexical content for an empty anchor. Rendering should be empty unless the source itself supplies a visible vacat/comment representation.
10. Non-textual technical anchors must be explicitly documented and must not leak into APIs as fabricated content.

## Precedent

This follows established Text-Fabric corpus practice rather than a project-local workaround.

- ETCBC/DSS creates empty slots for words with no glyphs and for vacat/other clusters with no signs, explicitly to anchor them in the text sequence.
- The Nino-cunei `tfFromAtf` converter used for Old Babylonian / Old Assyrian creates `cv.slot()` anchors when a textual line or document would otherwise be unlinked.
- Existing project-family work such as Pseudepigrapha-TF already uses gap/technical slots for empty textual readings while distinguishing metadata/apparatus nodes from textual content.

The reusable semantic principle is: **empty slots preserve textual position; they do not fabricate philological content.**

## Agent rule

Autonomous implementation and review agents working on a Text-Fabric corpus in this project family MUST treat this ADR as the default architecture.

Before proposing any zero-span sidecar, an agent must classify the affected objects:

1. Does the entity belong to the textual sequence and have an independent source position/order? Use an explicit empty/synthetic slot if it otherwise has none.
2. Is it a non-textual graph object? Anchor it through its textual locus/occurrence or a documented technical anchor when required by the model.
3. Is it genuinely outside the TF graph/API contract? Only then consider a sidecar.

A sidecar proposal whose only justification is "Text-Fabric rejects empty `oslots`" is an architectural error. Deviating from this ADR requires an explicit corpus-specific ADR and independent review.

## Testing requirements

Converters that can encounter zero-span source entities must include tests that prove:

- empty anchors are emitted deterministically and in source order;
- source/semantic slot counts exclude synthetic empty anchors;
- total TF slot counts include them;
- empty textual words/lines/documents remain queryable through normal TF relations;
- ancestors reuse descendant anchors rather than multiplying empty slots;
- no neighbouring real slot is borrowed for an independently positioned textual entity;
- no visible or lexical content is fabricated;
- non-textual technical anchors do not render as textual content;
- repeated builds are byte- or graph-deterministic as appropriate;
- consumers can explicitly distinguish empty/synthetic anchors from real source slots.

## Consequence for ORACC-TF

The earlier `zero-span.json`/sidecar approach for ORACC textual nodes is superseded by this decision. Issue #37 and PR #63 must be redesigned around explicit empty-slot anchoring before merge. Any remaining sidecar use must be justified by data genuinely outside the TF graph/API contract rather than merely by zero span.
