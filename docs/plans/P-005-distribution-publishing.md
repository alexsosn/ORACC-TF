---
id: P-005
title: Publish semantic TF datasets to lightweight distribution repositories
type: plan
status: draft
priority: P0
depends_on: [R-005, P-001]
updated: 2026-09-09
---

# Publish semantic TF datasets to lightweight distribution repositories

## Goal

Turn the decision in R-005 into a deterministic, fail-closed publisher that projects one registered semantic ORACC-TF dataset into one lightweight generated distribution repository suitable for Agora repository acquisition.

Issue #60 owns PH0. Creating or mutating real external distribution repositories is **not** part of PH0; PH0 proves the contract locally/in fixtures first. Issue #79 extends that reviewed boundary with the canonical dedicated-repository root and typed support-path ownership needed by the later app/documentation publishers.

## Frozen contract

### Identity and path scopes

- Input dataset identity is exactly a registered `datasets.toml` key.
- Distribution identity is derived from the semantic dataset, never from contributing ORACC archive/subproject names.
- Central/local builder output remains dataset-keyed: `<output-base>/<dataset>/tf/<tf_version>/`. This is a development/staging path, not the path inside a dedicated generated repository.
- A published/generated repository represents exactly one semantic dataset. Its repository root is therefore the semantic distribution root and its canonical TF path is `tf/<tf_version>/`; the dataset id is **not** repeated as `<dataset>/tf/...` inside that repository.
- TF schema version is SemVer and is **not** release/source-state identity. A new upstream source state may legitimately produce different bytes at the same `<tf_version>` path in a newer immutable repository revision.
- Every staged publication therefore has an explicit immutable `release_id`, distinct from `tf_version`. PH0 treats it as an opaque caller-supplied publication identity; P-002.PH7 will supply the canonical release/tag identity once authenticated lock provenance is available.
- Upstream source-state identity remains provenance/release metadata and must not be encoded as a replacement for dataset or TF schema identity.

Path construction must preserve the distinction between the central builder and a dedicated generated repository. Shared helpers may validate the same dataset and SemVer inputs, but external repository consumers must never reproduce the dataset identity twice. A future collection repository may introduce a dataset-relative prefix through a separate reviewed abstraction; it must not leak into today's dedicated-repository contract.

### Generated dedicated repository

The publisher produces a staging tree containing only distribution material. The reviewed dedicated-repository shape is:

```text
README.md
manifest.json
tf/<tf_version>/
app/                 # optional typed support root when declared by the release
docs/                # optional typed support root when declared by the release
```

`README.md` is required as a regular root file. Every visible TF root must be independently loadable and contain the required TF warp. Coordinated sidecars are copied only when they genuinely exist in the source/build contract. Under ADR-0001, zero-span textual entities are represented by explicit synthetic TF slots, so current corpora do **not** require `zero-span.json`; the publisher must not fabricate a legacy sidecar merely to satisfy packaging.

The current generic support-path contract recognizes `app/` and `docs/` as typed release-level roots. Their content semantics remain owned by downstream tickets (#71 for the Text-Fabric app, #81/#78 for the standalone documentation bundle): #79 owns only path normalization, byte ownership, integrity, and transactional replacement. Arbitrary support kinds, symlinks, raw `data/`/`programs/`, and unowned content remain fail-closed.

`app/` and `docs/` are not TF-versioned. The current release owns the visible support bytes. A newer release may replace or omit them; omitted roots are removed transactionally so stale support files cannot survive a release transition. Non-empty support source roots must be pairwise disjoint and must not overlap the TF source or staging tree, so one mutable source subtree cannot masquerade as two independently owned typed artifacts.

### Manifest ownership

`manifest.json` is deterministic and records dataset id, current release id, TF version, ORACC-TF builder commit, source-state identity when available, tree/artifact integrity information, the exact relative TF root, and the current release's typed support-root records. It retains an immutable release ledger sufficient to reject reuse of an earlier `release_id` with different bytes after later releases have been staged. A provenance field that cannot yet be established must be explicitly unavailable/blocking; it must not be fabricated.

Manifest schema v4 records:

- `visible_roots`: a deterministic mapping from every currently visible canonical `tf/<tf_version>` root to the `release_id` whose digest/provenance describes those bytes;
- each release record's `support_roots`: typed `app`/`docs` records containing the canonical root-relative path and deterministic tree digest;
- top-level current release fields that exactly mirror `releases[release_id]`, including `support_roots`.

The manifest contract is fail-closed:

- every `visible_roots` target exists in the immutable release ledger and that release record names the same canonical `tf_root`;
- the filesystem TF-version roots and `visible_roots` keys agree exactly, so an untracked discoverable TF root cannot bypass integrity metadata;
- every visible TF root is structurally valid, independently loadable, and byte-digest-equal to its owning release record before any idempotent return or new staging transaction proceeds;
- every current support root exists at its canonical typed path and its complete tree digest matches the current release record before replay/publication proceeds;
- every path in the staged tree is either root furniture (`README.md`, `manifest.json`), an ancestor/descendant of a manifest-owned TF root, or an ancestor/descendant of a current manifest-owned support root; arbitrary injected files remain rejected;
- unsupported manifest schema versions or malformed/cross-root records are rejected rather than upgraded implicitly;
- publishing a newer release at an already-visible TF version updates only that TF root's owner in `visible_roots`; other version roots remain mapped to their own current bytes;
- support roots are current-release state rather than TF-versioned state, so multiple TF schema versions coexist under `tf/` while one current `app/`/`docs/` snapshot remains visible;
- replaying an older immutable release is a no-op when its ledger record matches, but it does not roll a visible TF root or current support surface back to historical bytes and it still validates all currently visible roots first.

### Immutability and publication transaction

Publication is stage -> validate -> compare identity -> publish. A version becomes visible only after the staged tree passes structural/load/integrity checks.

- same `release_id` + same TF/support bytes and provenance: idempotent no-op, even if a newer release is currently staged;
- same `release_id` + different bytes or provenance: hard conflict;
- different `release_id` may update bytes at the same TF schema-version path; immutable Git refs/tags preserve the older release tree externally;
- multiple TF schema-version roots may coexist without collision and each visible root has explicit current-release ownership/integrity metadata;
- support roots are replaced/removed in the same staging transaction as TF/manifest state and never survive merely because they existed in the previous tree;
- validation/copy/update failure preserves the last valid staged distribution; a failed candidate cannot become partially visible;
- source, stage, support roots, transaction backup paths, and typed support sources obey the reviewed non-overlap/ownership constraints;
- mutable branch heads may point at generated history, but Agora/release records pin an immutable commit/tag;
- corrections create a new release identity; published immutable identities are not rewritten.

### Repository boundary

A distribution repository contains no unrelated ORACC raw source tree, converter implementation, research plans, or other semantic datasets. The central ORACC-TF repository remains the builder/source of truth.

Repository naming is derived collision-safely from dataset identity. The implementation must not assume a raw ORACC name is a valid repository name or semantic dataset id. Root `app/` and `docs/` are accepted only when they are explicitly declared by the current release and digest-owned by manifest v4; their names are not blanket allow-list escapes from the PH0 unowned-content rule.

### Agora contract

PH0 targets Agora's existing repository acquisition model: repository + immutable ref + relative TF path. For a dedicated generated repository that relative TF path is `tf/<tf_version>`. It does not require a new release-asset protocol. A generated fixture must be consumable through the same path semantics used by `GitStore`.

App/docs acquisition behavior remains a downstream concern: #79 ensures their canonical root paths and integrity ownership, while #71/#81/#83 prove the relevant Text-Fabric, documentation, and researcher/tool consumption routes. The publisher must not duplicate app/data into unsafe locations merely to accommodate a consumer that currently loads only a TF subroot.

Collection repositories and release/OCI/HF artifacts remain supported architectural alternatives, not PH0 implementation targets. A later benchmark/review may reopen the choice if measured results contradict R-005.

## PH0 — local distribution contract and benchmark harness

### RED tests first

Before production publisher code, tests must fail for missing behavior covering:

1. every registered dataset maps deterministically to one distribution identity;
2. aggregate `assyrian-royal-inscriptions` remains one distribution despite eleven JSON archive inputs;
3. multiple TF versions are actually staged together without collision, every discoverable root has explicit visible-release ownership, and corruption of a non-current visible root fails closed;
4. same release identity/same bytes is idempotent;
5. same release identity/different bytes fails closed;
6. a new release identity may replace bytes at the same TF schema-version root without rewriting the earlier release ledger entry, while updating only that root's visible owner;
7. replaying an earlier release after a newer release is staged is a no-op when its bytes/provenance match and a conflict when they do not;
8. staged output contains no unrelated raw/build/research paths;
9. manifest binds distribution -> release id -> ORACC-TF builder commit -> source-state field explicitly;
10. incomplete TF warp publication is rejected before visibility, while a loadable ADR-0001/current TF root without a legacy `zero-span.json` sidecar is accepted;
11. unsafe/colliding repository-name derivations fail or disambiguate deterministically;
12. a representative generated repository can be acquired at an immutable revision and its TF root loaded;
13. benchmark accounting separates metadata bytes from the **pre-load materialized Git snapshot** bytes, records a deterministic pre-load tree digest, proves central/minimal TF payload byte-equivalence at pinned revisions, and records warm/no-change cost;
14. unsupported/tampered manifest schema or disagreement between the top-level current fields and `releases[release_id]` is rejected before an idempotent return or copied staging transaction.

### Implementation boundary

Add a package-level publisher/stager API; do not put cross-repository business logic into workflow YAML. External GitHub repository creation/push is deferred until the local transaction, manifest, immutability, and Agora-consumption contracts are independently reviewed.

### Verification

Run focused tests, repository fast tests, whole-corpus invariants, generated-reference drift, and retained M8 cross-validation. For the large dataset benchmark, build the current registered dataset from the checked-in source snapshot; do not require live ORACC download.

The benchmark must measure the materialized snapshot size/digest immediately after `GitStore.materialize()` and before `Text-Fabric.load()`, because TF loading may create cache files. Post-load size may be recorded separately, but it must not be mislabeled as Git materialization size. Central and generated-repository snapshots must have equal pre-load tree digests as well as equivalent TF load/cardinality results.

## Issue #79 — dedicated repository support-path extension

Issue #79 extends PH0 without creating a second packager. Its implementation gate is complete only when the existing publisher demonstrates all of the following through RED-first tests:

1. a dedicated repository uses `tf/<version>` directly and never `<dataset>/tf/<version>`;
2. declared `app/`/`docs/` trees are accepted and digest-owned, while identical undeclared paths remain rejected;
3. arbitrary support kinds, arbitrary unowned files, symlinks, raw build/source paths, and source/stage/support overlap remain fail-closed;
4. support source roots are pairwise disjoint;
5. current support digest corruption is rejected on replay;
6. a new release removes stale support roots omitted by its snapshot;
7. a failed update preserves the complete prior valid distribution;
8. multiple TF versions coexist without duplicating or version-scoping the current support roots;
9. the existing P-005 Agora benchmark still acquires and loads the dedicated repository's `tf/<version>` root at an immutable revision;
10. exact-head repository CI and a logically independent adversarial review pass after this normative plan is synchronized.

Content-level requirements such as mandatory `app/config.yaml`, documentation entry points, generated provenance content, and consumer route equivalence are intentionally not duplicated here; they remain owned by the app/docs/release tickets that consume this path/ownership foundation.

### Completion evidence gate

Durable ISSUE-79 evidence is recorded in `docs/task-state/ISSUE-79.json`. Before #79 may close, the exact final head containing that evidence and this normative synchronization must pass the standard repository tests, generated-reference check, retained M8 cross-validation, and the real P-005 Agora benchmark. A fresh logically-independent adversarial review must then pass on that same exact SHA; no code or documentation commit may follow the passing review before merge.

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
- benchmark evidence exists for central versus generated-repository acquisition and proves byte-equivalent pre-load TF snapshots;
- exact-head repository CI is green;
- logically-independent adversarial review passes on the exact final head.

## Stop conditions

Stop rather than publish externally if licence/redistribution semantics are unresolved, P-002 provenance is required but unavailable, immutable identity can be overwritten, a failed transaction can look valid, support bytes can escape manifest ownership, or the Agora benchmark cannot be measured reproducibly.
