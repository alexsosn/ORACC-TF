---
title: Data model
status: active
---

# Data model

ORACC-TF uses `sign` as the Text-Fabric slot type. The corpus distinguishes semantic source signs from technical empty slots required to preserve independently positioned zero-span textual entities.

## Empty textual positions

The normative rule is [ADR-0001](architecture/ADR-0001-empty-slots-not-sidecars.md): zero-span textual entities stay in the normal TF graph through explicit `synthetic=1` empty `sign` slots. Such slots preserve source order only; they carry no fabricated `utf8`, `readingu`, `sign_json`, grapheme, token, or lexical content. Ancestor sections reuse descendant anchors instead of receiving redundant synthetic slots.

Whole-corpus measurement for RIAO + RINAP after issue #37:

- semantic/source signs: **792,651**;
- synthetic empty slots: **689**;
- total TF slots: **793,340**;
- source words / TF word nodes: **320,975 / 320,975**;
- source documents / TF document nodes: **2,078 / 2,078**;
- zero-span sidecar nodes in new builds: **0**.

Unicode coverage remains **778,873 / 792,651 (98.2618%)** because synthetic slots are excluded from semantic-sign statistics.

`zero-span.json` is a legacy-reader format only. Current builds do not emit it for textual zero-span entities.
