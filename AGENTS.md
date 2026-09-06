# Agent instructions

## Text-Fabric zero-span architecture

Before designing or changing Text-Fabric serialization, read `docs/reference/architecture/ADR-0001-empty-slots-not-sidecars.md`.

Normative rule: an **independently positioned source entity in the textual sequence** that has no ordinary semantic slot remains inside Text-Fabric through an explicit empty/synthetic slot. Do not invent a zero-span sidecar merely to work around the TF `oslots` invariant.

- Ancestors/containers reuse descendant real or empty anchors; do not create one synthetic slot per ancestor.
- Non-textual graph abstractions anchor through occurrences/loci or a documented technical anchor when required; that anchor is not textual content.
- Converters and reports distinguish semantic/source slots, synthetic empty slots, and total TF slots.
- Never borrow a neighbouring real slot for an independently positioned textual entity.
- Never fabricate visible source content for an empty anchor.
- Sidecars are for data genuinely outside the TF graph/API contract. A sidecar for textual zero-span nodes requires an explicit corpus-specific ADR proving empty-slot anchoring is semantically invalid and must pass independent review.
