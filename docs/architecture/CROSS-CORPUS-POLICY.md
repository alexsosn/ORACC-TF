# Cross-corpus Text-Fabric policy

This repository adopts ADR-0001 as a project-family rule for Text-Fabric corpora: textual zero-span entities are represented with explicit empty/synthetic slots inside the TF warp, not moved to a sidecar merely to satisfy `oslots`.

When propagating this policy to sibling TF corpora, keep the same semantic contract even if feature names differ. Agents should treat a sidecar proposal for textual zero-span nodes as an architectural deviation requiring an explicit ADR.
