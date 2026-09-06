# Agent checklist for zero-span TF nodes

Before opening an implementation PR that changes Text-Fabric node anchoring:

1. Classify each zero-span entity as textual or genuinely non-textual.
2. For textual entities, default to explicit empty/synthetic slots per ADR-0001.
3. Ensure empty anchors are distinguishable from semantic/source slots by features and reporting.
4. Reuse descendant empty anchors for ancestors; do not create redundant empty slots per container.
5. Never attach zero-span entities to neighbouring real slots merely to satisfy `oslots`.
6. Never fabricate visible grapheme/sign/token content.
7. Add RED-first tests for empty word, empty line/container, wholly empty document, mixed real+empty text, deterministic ordering, and semantic-vs-total slot counts.
8. Treat a sidecar for textual zero-span nodes as an architectural deviation requiring a new ADR and independent review.
