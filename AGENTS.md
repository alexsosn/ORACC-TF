# ORACC-TF Agent Instructions

## Mandatory coordination

All autonomous work must follow the parallel-safe coordination protocol in `docs/plans/P-004-agent-coordination.md` and the machine-readable task registry in `docs/registry.json`.

Before implementing a task:

1. Reconcile the task against current GitHub issue/PR markers and registry state.
2. Hold a live claim lease for that task.
3. Bind exactly one open implementation PR to the winning claim session.
4. Follow research → design → RED-first TDD → implementation → exact-head tests → logically independent review.
5. Never complete a task from a stale claim, stale review, or superseded implementation.

## Text-Fabric zero-span architecture

For any Text-Fabric modelling work, read `docs/reference/architecture/ADR-0001-empty-slots-not-sidecars.md` before designing zero-span handling.

Independently positioned textual entities with zero semantic slot extent stay inside TF through explicit synthetic empty slots. Ancestors reuse descendant anchors. Do not borrow neighbouring real slots and do not invent visible/lexical content. A sidecar is not an acceptable workaround merely because TF rejects empty `oslots`; any exception requires a corpus-specific ADR and independent review.
