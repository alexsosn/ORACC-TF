---
id: ISSUE-32-SOURCE-GATES
title: ETCSRI first-pass source research and acceptance boundaries
type: research
status: active
priority: P1
depends_on: [R-001]
updated: 2026-10-11
---

# ETCSRI — first pass (issue #32)

## Grounded starting point

- The source ranking in [R-001](R-001-corpus-selection.md) (2026-08-29) identifies
  ETCSRI as a morphology-rich Sumerian royal-inscription corpus. These counts
  are *historical observations*, not validated coverage for today's pinned input.
- The previously closed [PR #55](https://github.com/alexsosn/ORACC-TF/pull/55)
  established **derived CSV** research and RED tests for raw-source measurement,
  but had no `--raw-cache` implementation.
- [Zenodo 20625379](https://doi.org/10.5281/zenodo.20625379) records both
  `etcsri.zip` derived CSVs and `oracc_jsonzip_all.zip` containing project
  JSON bundles. This external cache is **measurement input**, not an
  automatically accepted canonical edition or data-redistribution licence.
- The existing standalone `assyrian-royal-inscriptions` dataset is not changed
  by this research work. ETCSRI must not be registered in `datasets.toml`
  before a source-grounded model and build actually exist.

## Research gate — source evidence before conversion design

The research script supports two **mutually exclusive** modes:

1. `--derived-zip` observes derived CSV column presence/population and records
   its archive SHA-256. Such reports have `raw_source_claims_supported=false`.
2. `--raw-cache` locates exactly `jsonzip/etcsri.zip` in the pinned outer
   cache, reads `etcsri/corpusjson/*.json` directly, and records SHA-256 of
   both outer cache and nested ETCSRI bundle, observed `node=c/d/l` shapes,
   GDL object key sets, lexical/morphological feature presence, and anomalies.
   This does not infer sign-slot equivalence, missing translations, or
   morphological analysis where the source does not provide them.

The scanner does not extract ZIP files, requires unambiguous member paths,
rejects duplicate members and malformed CDL node shapes, and bounds
individual/project/cumulative decompression size. Empty, invalid-JSON or
non-object corpus members are counted separately rather than silently
promoted to readable source editions. Passing synthetic fixtures is not a
substitute for running the scanner on the actual pinned source bytes.

## Plan for implementation (not yet authorized)

1. Run the two source censuses and retain reports and immutable byte digests.
   Resolve any upstream cache/source-version mismatch and source licence
   attribution with actual publisher declarations.
2. Write a source-to-TF mapping from the **raw census**:
   `base`, `morph`, `morph2`, `para` semantics; GDL composite/sign
   handling; source document/line/chunk identity; technical empty slots;
   catalogue/QPN relationships and provenance.
3. Choose explicit ETCSRI dataset identity and independent distribution.
   Preserve a lossless source morph/morph2 representation first; add a parsed
   morpheme layer only with separately tested source grammar and segment
   boundaries.
4. Commit RED tests for morphology/queryability, structure and sign/source
   round-trip against **real ETCSRI witnesses**. Build only after the review of
   the mapping and copyright/licence boundary.
5. Produce source-to-TF invariants, final source exception manifest, output
   packaging, app/manual usability checks, and independent adversarial review
   on the exact implementation head.

## Stop conditions

No claim of morphological coverage, zero-span handling, Unicode sign
correctness, or publication readiness may be derived solely from the derived
CSV archive, from R-001's old totals, or from generated synthetic fixtures.
Unknown source shapes or incompatible source permissions block mapping
decisions rather than triggering inferred repairs.
