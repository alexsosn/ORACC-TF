---
id: R-005
title: Distribution architecture for installable ORACC-TF datasets
type: research
status: active
priority: P0
depends_on: [P-001]
updated: 2026-09-06
---

# Distribution architecture for installable ORACC-TF datasets

## Question

What should be the distribution unit for generated ORACC-TF corpora when the central repository remains the reproducible builder but Agora/Context-Fabric should install one corpus without treating the whole builder/source repository as its practical distribution surface?

This research is the source-grounded gate for issue #60. It does not create distribution repositories or publish corpus bytes.

## Measured baseline

Measurements are bound to ORACC-TF main `6c608ae749ac7e4884676f2f371a42779c182340` and Agora main `302178da1f85c6097950d1bb4c0986bd10c3c141`, observed 2026-09-06.

- GitHub reports `alexsosn/ORACC-TF` repository size `627839` KiB (about 613 MiB). This is repository metadata from GitHub, not a claim about cold-install transfer.
- `datasets.toml` currently defines exactly one semantic publishable dataset, `assyrian-royal-inscriptions`, from eleven JSON archive inputs plus the independently tracked `riao-teiCorpus` translation source. The dataset therefore deliberately aggregates upstream archive/subproject boundaries.
- Issue #14 established the publishable root grammar `<output-base>/<dataset>/tf/<tf_version>/`. Dataset identity, TF schema version, and upstream source state are distinct identities.
- No generated publishable TF root is committed to the central repository today; distribution work must therefore not pretend there is a legacy published tree that requires byte-for-byte path compatibility.

### What Agora actually transfers

Agora's `GitStore.ensure_metadata()` does **not** perform a normal full checkout. At the pinned Agora revision it runs a shallow `git clone --filter=blob:none --no-checkout --depth 1`, then resolves the selected revision. Corpus materialization creates a second temporary repository, fetches the exact revision with `--filter=blob:none --depth 1`, and uses `git archive` for only the requested repository-relative path. Persistent repository cache is metadata-only; selected corpus bytes live in revision-addressed snapshots.

Consequences:

1. The 613 MiB GitHub repository size is not the expected Agora cold-transfer size.
2. A central-repository source can already avoid materializing unrelated blobs.
3. Repository topology still matters: tree metadata, revision resolution, availability, history policy, cache identity, and the repository itself remain part of acquisition. A lightweight distribution surface can therefore still reduce coupling even though the naive "Agora clones 613 MiB" argument is false.

Agora discovers TF roots from `otype.tf`, fingerprints the warp from Git blob identities, and validates snapshots before accepting them. This is compatible with a repository exposing one stable dataset and versioned `/tf/<version>/` roots.

### Current Agora acquisition model

The current resource schema requires `upstream.repository`; repository-relative `tf_path` and `ref` are supported. `kind: collection` adds lazy member discovery/indexing but still has a repository upstream. The current schema has no first-class release-asset, OCI, or Hugging Face acquisition descriptor. Option D would therefore require an Agora protocol/schema extension rather than merely changing ORACC-TF publication.

## Options A-D

| Option | Fit | Benefits | Costs / failure modes | Current verdict |
|---|---|---|---|---|
| A. One repository per semantic TF dataset | Direct match to `datasets.toml` identity and #14 root contract | Small independent acquisition surface; one cache/revision identity per scholarly dataset; aggregate datasets remain aggregate; simple Agora repository source | Repository count grows with datasets; publisher needs cross-repo credentials/idempotency; issues must route back to builder | **Preferred hypothesis** |
| B. One repository per raw ORACC project/subproject | Mirrors upstream hierarchy | Small repositories | Breaks semantic dataset boundary; RIAO/RINAP would be split despite one intended corpus; multiplies catalog/release objects; upstream packaging dictates user ontology | **Reject as default** |
| C. Collection repositories with lazy members | Agora already supports collection/lazy-member model | Fewer repositories; independent member materialization | Reintroduces shared repository/tree/release coupling; requires collection index lifecycle; grouping policy becomes another identity decision | **Useful only when many small datasets share a real scholarly/release boundary** |
| D. Immutable release/OCI/HF artifacts plus lightweight catalog | Artifact-native immutability and potentially cheap direct transfer | Decouples data bytes from Git history | Agora does not currently model this acquisition; needs downloader, integrity/cache/update semantics and schema changes before ORACC-TF can rely on it | **Future comparison, not current implementation target** |

## Decision

Adopt **one generated lightweight distribution repository per semantic publishable dataset** as the design target unless the benchmark gate disproves it. Raw ORACC archive/project boundaries are provenance inputs, not distribution identities.

For the current registry this means one distribution identity for `assyrian-royal-inscriptions`, even though it aggregates RIAO and RINAP archives. Future datasets get their own repository only when they become registered publishable datasets.

The central `ORACC-TF` repository remains authoritative for converter source, source snapshots/locks, research, tests, and publication orchestration. Distribution repositories are generated outputs; they must not become a second hand-maintained source of converter logic or raw ORACC trees.

## Required provenance boundary

Every published distribution version must bind at least:

- semantic dataset id;
- TF schema version;
- exact ORACC-TF builder commit;
- exact contributing upstream source-state identity / archive hashes when P-002 lock provenance is available;
- generated artifact/tree digest;
- licence/provenance payloads appropriate to the contributing sources;
- verification result proving required TF warp/sidecars are complete before the version becomes addressable.

A mutable branch name is not an immutable release identity. Agora should pin an immutable distribution commit or immutable tag resolved to a commit. Re-running publication for the same identity and bytes is idempotent; the same immutable version identity with different bytes is a hard failure.

## Generated repository boundary

A distribution repository contains only corpus-distribution material: generated TF roots, coordinated sidecars/manifests, provenance/integrity metadata, and minimal generated README/licence/attribution furniture. It must not copy unrelated `data/`, converter source, research plans, or other datasets.

Recommended tree shape:

```text
README.md
manifest.json
<dataset>/
  tf/
    <tf_version>/
      otype.tf
      oslots.tf
      otext.tf
      ...features...
      zero-span.json
```

The repository name is an operational locator, not the semantic id. A collision-safe generated name should be derived from the dataset id (provisionally `ORACC-TF-<dataset>`); the manifest remains authoritative for semantic identity.

## Benchmark still required

The architecture is not complete until a test publisher can create a local/generated distribution fixture and the benchmark records, for a representative small fixture and `assyrian-royal-inscriptions`:

- cold acquisition bytes transferred;
- metadata-resolution time;
- time to usable TF load;
- local cache size;
- no-change/update-check cost;

for central-monorepo repository acquisition versus the generated per-dataset repository shape using Agora's actual `GitStore` path. The benchmark must distinguish Git metadata transfer from selected TF blob transfer.

## Stop conditions

- Do not create real distribution repositories manually before publisher/provenance tests are green.
- Do not claim release-grade upstream provenance until P-002.PH1 can establish authenticated lock state.
- Do not weaken source licences or assume redistribution rights merely because generated TF is technically publishable.
- If the measured Agora benchmark shows per-dataset repositories provide no meaningful isolation/cost/reliability benefit, revisit A versus C/D before external publication.
