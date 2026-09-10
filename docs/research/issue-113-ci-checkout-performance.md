# ISSUE-113 — GitHub Actions checkout-cost research

Status: research/design gate

Base revision: `6500bce7e554e447e081c135d119ef7941be984b`

## Question

Can ORACC-TF reduce GitHub Actions checkout/materialization cost for jobs that do not consume the checked-in `data/` tree, without weakening corpus, documentation, integration, or exact-head gates?

## Baseline evidence

Measurements below come from completed PR #105 merge-ref runs on 2026-09-10. They are wall-clock intervals read from GitHub Actions job logs.

| Workflow/job | Primary ORACC-TF checkout | Useful work after checkout | Observation |
|---|---:|---:|---|
| `tests.yml` / `pytest` | ~98 s on run `34485303518` | fast suite ~8 s before the intentional RED failure | one job combines fast and whole-corpus suites; full `data/` is required only for the latter |
| `p003-docs.yml` / `generated-reference` | ~143 s on run `34486751756` | build ~51 s; docs generation ~52 s; docs check ~14 s | genuinely requires the real checked-in corpus |
| `m8-oldbabylonian.yml` / `cross-validate` | ~128 s on run `34486751768` | external sparse checkout ~4 s; integration test ~11 s | the M8 test reads only the pinned external TF; ORACC-TF `data/` is not referenced |
| `issue102-unreadable-research.yml` / `census` | ~131 s for the current-branch harness checkout on run `34486751808` | second pinned `data/` checkout ~194 s; census ~42 s | first checkout needs only harness/workflow files; second checkout intentionally materializes exact pinned source data |

The dominant avoidable cost is repeated materialization of roughly 49.5k repository files in jobs whose commands do not consume `data/`.

## Dependency inventory

### `tests.yml`

Current `pytest` job performs one full checkout, installs `.[dev]`, runs `pytest -q -m "not corpus"`, then `pytest -q -m corpus`. `docs-registry` performs another full checkout and only runs `python scripts/check_docs_registry.py`.

Design boundary:
- fast tests need package source, tests, project metadata and test fixtures, not the corpus tree by contract;
- corpus tests must continue to receive real checked-in `data/`;
- docs-registry needs its script/docs/registry inputs, not corpus data.

### `p003-docs.yml`

The workflow calls `corpus.build_full_tf('/tmp/oracc-tf')`, then generates and checks reference docs from that build. Full `data/` remains required. This ticket must not manufacture a speedup by excluding production source data here.

### `m8-oldbabylonian.yml`

`tests/test_m8_oldbabylonian_integration.py` imports `tf.fabric.Fabric` and loads only `OLDBABYLONIAN_TF` from the pinned external `Nino-cunei/oldbabylonian` checkout. `pyproject.toml` declares the package under `programs/`; editable installation does not require `data/`.

A sparse primary checkout can therefore retain `pyproject.toml`, `programs/`, the targeted test, and any workflow-contract test inputs while excluding `data/`. The external pinned checkout/ref/path must remain unchanged.

### `issue102-unreadable-research.yml`

The first checkout supplies the current research harness. The second checkout deliberately pins revision `dd6a657d15999288948a266c9eb17666f9790497` and sparse-checks out `data`. The second checkout is the research evidence and must remain complete; only the first checkout is an optimization candidate.

## Frozen design

1. Split `tests.yml` into a sparse **fast/unit** job and a full-data **corpus** job. Both remain ordinary PR checks; coverage is separated by checkout scope rather than removed.
2. Make `docs-registry` sparse over the exact code/docs inputs it validates.
3. Make the primary ORACC-TF checkout in M8 sparse while preserving the pinned external TF checkout unchanged.
4. Make the first/harness checkout in ISSUE-102 research sparse while preserving the exact pinned-source `data` checkout unchanged.
5. Leave P003 full-data checkout unchanged.
6. Do not add path filters that can suppress the principal `tests` gates. Optimization is checkout scope, not a guess that a change probably needs less validation.

## Rejected/deferred options

- **Artifact/cache handoff for corpus data:** defer. It adds source-state/cache invalidation complexity that can hide drift; reconsider only with immutable source binding and measured benefit.
- **Sparse P003 checkout excluding corpus source:** reject; P003 intentionally builds the real corpus.
- **Dropping editable installation from M8:** unnecessary; package metadata/source are cheap enough to keep in the sparse set.
- **Path-filtering the main test workflow:** reject; a misclassified changed path must not silently remove a required gate.

## TDD contract

Before workflow edits, add static workflow-contract RED tests that require:
- separate fast and corpus jobs in `tests.yml`;
- fast checkout is sparse and still runs `pytest -q -m "not corpus"`;
- corpus job receives `data/` and still runs `pytest -q -m corpus`;
- docs-registry is sparse and still runs `scripts/check_docs_registry.py`;
- M8 primary checkout is sparse while its external pinned commit/path and integration command remain unchanged;
- ISSUE-102 first checkout is sparse while the second checkout retains the exact pinned source revision and `data` path;
- P003 remains a full checkout and still builds the real checked-in corpus;
- no new path filter can suppress the principal fast/corpus gates.

After GREEN, compare repeated Actions logs against these baselines. Performance acceptance comes from observed checkout reduction; correctness acceptance comes from unchanged command/data boundaries and full CI success.

## Stop conditions

Stop rather than optimize if a supposedly sparse job reads repository `data/` implicitly, if editable installation requires omitted files, or if the workflow split makes a previously required gate optional. Corpus/data-consuming jobs continue to use the real checked-in source tree.
