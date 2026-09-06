---
id: P-005
title: Publish semantic TF datasets to lightweight distribution repositories
type: plan
status: draft
priority: P0
depends_on: [R-005, P-001]
updated: 2026-09-06
---

# Publish semantic TF datasets to lightweight distribution repositories

## Goal

Turn the decision in R-005 into a deterministic, fail-closed publisher that projects one registered semantic ORACC-TF dataset into one lightweight generated distribution repository suitable for Agora repository acquisition.

Issue #60 owns PH0. Creating or mutating real external distribution repositories is **not** part of PH0; PH0 proves the contract locally/in fixtures first.

## Frozen contract

### Identity

- Input dataset identity is exactly a registered `datasets.toml` key.
- Distribution identity is derived from the semantic dataset, never from contributing ORACC archive/subproject names.
- The canonical publishable TF root remains `<dataset>/tf/<tf_version>/` from G-002/#14.
- TF schema version is SemVer and is **not** release/source-state identity. A new upstream source state may legitimately produce different bytes at the same `<tf_version>` path in a newer immutable repository revision.
- Every staged publication therefore has an explicit immutable `release_id`, distinct from `tf_version`. PH0 treats it as an opaque caller-supplied publication identity; P-002.PH7 will supply the canonical release/tag identity once authenticated lock provenance is available.
- Upstream source-state identity remains provenance/release metadata and must not be encoded as a replacement for dataset or TF schema identity.

### Generated distribution

The publisher produces a staging tree containing only distribution material. At minimum:

```text
README.md
manifest.json
<dataset>/tf/<tf_version>/
```

The version root must be independently loadable and contain the required TF warp plus coordinated sidecars. The publisher rejects raw source/build/research paths in the staged output.

`manifest.json` is deterministic and records dataset id, current release id, TF version, ORACC-TF builder commit, source-state identity when available, tree/artifact integrity information, and the exact relative TF root. It also retains an immutable release ledger sufficient to reject reuse of an earlier `release_id` with different bytes after later releases have been staged. A provenance field that cannot yet be established must be explicitly unavailable/blocking; it must not be fabricated.

### Immutability and publication transaction

Publication is stage -> validate -> compare identity -> publish. A version becomes visible only after the staged tree passes structural/load/integrity checks.

- same `release_id` + same bytes: idempotent no-op, even if a newer release is currently staged;
- same `release_id` + different bytes or provenance: hard conflict;
- different `release_id` may update bytes at the same TF schema-version path; immutable Git refs/tags preserve the older release tree externally;
- multiple TF schema-version roots may coexist in the current repository tree without collision;
- partial/failed staging: never accepted as a valid version;
- mutable branch heads may point at generated history, but Agora/release records pin an immutable commit/tag;
- corrections create a new release identity; published immutable identities are not rewritten.

### Repository boundary

A distribution repository contains no unrelated ORACC raw source tree, converter implementation, research plans, or other semantic datasets. The central ORACC-TF repository remains the builder/source of truth.

Repository naming is derived collision-safely from dataset identity. The implementation must not assume a raw ORACC name is a valid repository name or semantic dataset id.

### Agora contract

PH0 targets Agora's existing repository acquisition model: repository + immutable ref + relative TF path. It does not require a new release-asset protocol. A generated fixture must be consumable through the same path semantics used by `GitStore`.

Collection repositories and release/OCI/HF artifacts remain supported architectural alternatives, not PH0 implementation targets. A later benchmark/review may reopen the choice if measured results contradict R-005.

## PH0 — local distribution contract and benchmark harness

### RED tests first

Before production publisher code, tests must fail for missing behavior covering:

1. every registered dataset maps deterministically to one distribution identity;
2. aggregate `assyrian-royal-inscriptions` remains one distribution despite eleven JSON archive inputs;
3. multiple TF versions coexist without collision;
4. same release identity/same bytes is idempotent;
5. same release identity/different bytes fails closed;
6. a new release identity may replace bytes at the same TF schema-version root without rewriting the earlier release ledger entry;
7. replaying an earlier release after a newer release is staged is a no-op when its bytes/provenance match and a conflict when they do not;
8. staged output contains no unrelated raw/build/research paths;
9. manifest binds distribution -> release id -> ORACC-TF builder commit -> source-state field explicitly;
10. incomplete TF warp/sidecar publication is rejected before visibility;
11. unsafe/colliding repository-name derivations fail or disambiguate deterministically;
12. a representative generated repository can be acquired at an immutable revision and its TF root loaded;
13. benchmark accounting separates metadata bytes from materialized TF bytes and records warm/no-change cost.

### Implementation boundary

Add a package-level publisher/stager API; do not put cross-repository business logic into workflow YAML. External GitHub repository creation/push is deferred until the local transaction, manifest, immutability, and Agora-consumption contracts are independently reviewed.

### Verification

Run focused tests, repository fast tests, whole-corpus invariants, generated-reference drift, and retained M8 cross-validation. For the large dataset benchmark, build the current registered dataset from the checked-in source snapshot; do not require live ORACC download.

## Later phases

- **PH1:** authenticated external-repository publisher and idempotent update transaction.
- **PH2:** Agora catalog integration and migration from any central-repo references.
- **PH3:** release automation/provenance integration with P-002.PH7 once lock provenance is available.

These phases require separate issues/review before external side effects.

## Acceptance for issue #60

Issue #60 may close only when:

- R-005 A/B/C/D comparison is reviewed;
- PH0 RED -> GREEN evidence exists;
- local generated distribution excludes unrelated source/build data;
- the representative Agora repository-acquisition/load contract is exercised;
- benchmark evidence exists for central versus generated-repository acquisition;
- exact-head repository CI is green;
- logically-independent adversarial review passes on the exact final head.

## Stop conditions

Stop rather than publish externally if licence/redistribution semantics are unresolved, P-002 provenance is required but unavailable, immutable identity can be overwritten, a failed transaction can look valid, or the Agora benchmark cannot be measured reproducibly.
