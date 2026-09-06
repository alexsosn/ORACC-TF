# Agent instructions

## Text-Fabric zero-span architecture

Before designing or changing Text-Fabric serialization, read `docs/architecture/ADR-0001-empty-slots-not-sidecars.md`.

Normative rule: a source entity that belongs to the textual graph but has no ordinary semantic slot is represented inside Text-Fabric with an explicit empty/synthetic slot. Do not invent a zero-span sidecar as a workaround for the TF `oslots` invariant. Sidecars for textual zero-span nodes require an explicit corpus-specific ADR proving empty-slot anchoring is semantically invalid.

Converters and reports must distinguish semantic/source slots, synthetic empty slots, and total TF slots. Never borrow a neighbouring real slot or fabricate visible source content.
