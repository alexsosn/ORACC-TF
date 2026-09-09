---
id: P-002
title: Automate ORACC upstream updates through ORACC-TF publication
type: plan
status: draft
priority: P0
depends_on: [R-002, P-001]
blocks: [P-003]
updated: 2026-09-09
---

# Plan: automate ORACC upstream updates through ORACC-TF publication

## Goal

A scheduled job notices that an ORACC archive changed, rebuilds only the
affected Text-Fabric datasets, proves the rebuild is sound, and publishes an
immutable release — or stops with a report naming exactly what a human must
decide.

Grounded in [R-002](../research/R-002-upstream-automation.md). Read its §1
first: ORACC supplies no version identity, so this plan manufactures one.
The reviewed executable PH5 safety contract is
[`issue-95-ph5-gate-contracts.json`](../research/issue-95-ph5-gate-contracts.json).

## Guiding rules

**1. The lock is the source of truth for upstream state.** No script may
re-derive "what version do we have" by inspecting `data/`. It reads
`upstream.lock.json`.

**2. Identity is a hash we compute, never a string upstream gave us.** ORACC
publishes no version and no checksum (R-002 §2.4). An archive is identified by
its SHA-256.

**3. A signal that something changed is not evidence that content changed.**
`ETag` moves on byte-identical rebuilds. Always confirm with SHA-256 before
rebuilding (R-002 §3).

**4. Silence is never success.** A gate that cannot evaluate — network
failure, missing TEI export, unparseable archive — emits `evaluation-error`
and blocks. It does not pass and cannot be approved.

**5. Approvals bind typed findings to exact evidence.** Every `GateFinding`
uses a real `subject.scope`/subject id, canonical `condition_sha256`, and an
`evidence_fingerprint` over the exact accepted/candidate evidence refs. An
approval never disables gate execution, and any relevant evidence or baseline
change makes it stale.

**6. Rebuild the smallest thing that changed.** The unit is one dataset
(R-002 §9), not the corpus.

**7. Compare only with the last accepted state.** A blocked candidate may be
reported and retried but never becomes the accepted baseline for the next
candidate.

---

# Phase 0 — version and publication model

## 0.1 Four identities

```
oracc_state    max UTC-timestamp across contributing archives   e.g. 2026-08-07
source_state   SHA-256 of canonical archive-name→SHA-256 set     content identity
tf_version     ORACC-TF converter/schema version                 e.g. 1.2.0
dataset        the TF dataset name                               assyrian-royal-inscriptions
```

Release tag:
`assyrian-royal-inscriptions/v1.2.0+oracc.2026-08-07.<source_state>`.

`oracc_state` is human-readable build metadata, not content identity: two
archives can carry the same date with different bytes. `source_state` is the
SHA-256 of the complete contributing archive-name/SHA-256 mapping in canonical
archive-name order and is included in full in the tag. SemVer precedence is
therefore determined by `tf_version`; the ORACC date and source digest remain
build metadata.

**Acceptance:** the version component of every tag obeys SemVer precedence;
two different archive sets cannot produce the same tag merely because their
maximum `UTC-timestamp` is equal; archive ordering does not change
`source_state`.

## 0.2 Datasets and their inputs

`datasets.toml`:

```toml
[assyrian-royal-inscriptions]
archives = ["riao-ria1","riao-ria2","riao-ria3","riao-ria4","riao-ria5",
            "rinap-rinap1","rinap-rinap2","rinap-rinap3","rinap-rinap4",
            "rinap-rinap5","rinap-rinap5p1"]
tei = ["riao-teiCorpus"]
```

Only datasets that ORACC-TF can currently build and publish belong in this
active mapping. `etcsri` remains the real upstream-change integration fixture
for Phase 9, but is not part of the daily tracked set until an `etcsri` TF
dataset is registered.

**Acceptance:** every tracked archive belongs to ≥1 active dataset; the daily
sweep polls only the 11 RIAO/RINAP archives, not all 208 upstream archives.

---

# Phase 1 — upstream configuration and lock

## 1.1 `upstream.toml` (hand-edited policy)

```toml
[source]
index      = "http://oracc.museum.upenn.edu/json/"
projects   = "http://oracc.museum.upenn.edu/projects.json"
user_agent = "ORACC-TF/1.0 (+https://github.com/alexsosn/ORACC-TF)"

[policy]
poll_cron          = "daily"
inventory_cron     = "weekly"
auto_publish       = true
max_parallel_fetch = 1
```

## 1.2 `upstream.lock.json` (generated)

Per-archive record exactly as R-002 §6, including `sha256`, `bytes`, `etag`,
`last_modified`, `oracc_utc_timestamp`, `licence`, `extract_paths`, and
`text_ids_sha256`.

**Acceptance:** the lock is regenerable from a clean checkout by downloading
the recorded archives; regeneration is byte-stable.

## 1.3 Backfill the current snapshot

R-002 §4: the source archives were deleted after extraction, so the repository
cannot say which bytes produced `data/`. Re-fetch the 11 archives for dataset 1,
record them, and **diff the extraction against the committed tree**.

**Acceptance:** either the extraction matches `data/` exactly — in which case
the snapshot is now provenanced — or the differences are enumerated in a report.
Do not silently overwrite `data/`.

> Expect `etcsri` to differ: upstream is 13,205,491 bytes at 2026-08-07 against
> a snapshot of 12,928,763 (R-002 §4). That is the first real update to process
> and doubles as the integration fixture in Phase 9.

---

# Phase 2 — discovery client

## 2.1 Inventory

Parse `/json/` (208 archives) and `projects.json` (144 entries). Keep both;
they answer different questions (R-002 §2.1).

Persist a deterministic project-inventory candidate alongside the archive
candidate state. The accepted project-inventory baseline advances only with a
fully accepted update; a blocked candidate never overwrites it.

## 2.2 `HEAD` sweep

For each tracked archive, record status, `ETag`, `Last-Modified`,
`Content-Length`.

**Must not** trust the status line alone: the `/downloads/` pattern returns
**HTTP 200 with a 4-byte body `404`** (R-002 §2.2). Use `/json/` exclusively,
and validate that any downloaded body begins with the ZIP magic `PK\x03\x04`.

**Acceptance:** a fabricated 4-byte `404` body is rejected as not-an-archive;
a 5xx backs off and does not mark the archive unchanged.

## 2.3 Change decision

```
etag == lock.etag and length == lock.bytes   -> unchanged, no download
otherwise                                     -> download, compute sha256
sha256 == lock.sha256                         -> refresh etag in lock, NO rebuild
sha256 != lock.sha256                         -> changed, go to Phase 4
```

**Acceptance:** a byte-identical republication updates the lock's `etag` and
triggers no build.

---

# Phase 3 — safe download and extraction

Stream to a temp file, cap total bytes, compute SHA-256 in the same pass.
Never `extractall()` a remote archive: reject absolute paths, `..` traversal,
symlinks, and entries escaping the destination. Enforce an uncompressed-size
ceiling and a compression-ratio ceiling.

Derive extract paths **structurally** from the archive's own entries (they
carry `project/subproject/` prefixes — P-001 §2.1), not from the filename.
Three-level names such as `aemw-alalakh-idrimi.zip` make filename-derived
mapping ambiguous (R-002 §2.2).

**Acceptance:** fixtures for traversal, symlink, zip-bomb, and a
three-level-name archive all fail closed.

---

# Phase 4 — source diff

Per changed archive, produce:

- text ids added / removed / modified (by per-text content hash)
- word-count delta per text
- lemma-coverage delta per subproject
- new GDL object shapes not in P-001 §2.3's census
- new `c` chunk types
- licence string change
- `UTC-timestamp` before → after

PH4 is policy-free. PH5 assembles accepted and candidate dataset-wide contexts
from all contributors, including unchanged archives, before deciding whether a
shape, collision class, coverage change, or disappearance is new.

**Acceptance:** the `etcsri` 2026-04 → 2026-08 change (Phase 1.3) produces a
diff whose text-level numbers reconcile with the corpus totals.

---

# Phase 5 — gates

Implement R-002 §7 and the reviewed
`issue-95-ph5-gate-contracts.json` as named gates. Every gate returns a typed
`GateFinding` with `subject.scope`, subject id, canonical condition,
`condition_sha256`, exact evidence refs and `evidence_fingerprint`. Required
evidence includes both **accepted and candidate** dataset source/manifests for
dataset-wide findings. A contributor-set mismatch emits non-approvable
`dataset-input-set-changed` before normal gate evaluation.

| gate | stage | blocks publication |
|---|---|---|
| `gdl-shape-unknown` | PH5 prebuild | yes |
| `chunk-type-unknown` | PH5 prebuild | yes |
| `lemma-coverage-drop` (> 2 pts, exact rational arithmetic) | PH5 prebuild | yes |
| `q-collision-new-class` | PH5 prebuild | yes |
| `project-disappeared` | PH5 prebuild | yes |
| `licence-changed` | PH5 prebuild | yes |
| `translation-coverage-drop` | PH5 prebuild | yes |
| `word-count-unexplained` | PH5 postbuild | yes |
| `texts-added` / `texts-modified` | observation | no — normal |

Every applicable gate runs even after another blocker is found. Findings are
serialized deterministically. Approval is applied only after a finding exists;
it never suppresses execution. Every `evaluation-error` remains visible and is
categorically non-approvable. The baseline for every comparison is the **last
accepted** state, never the last observed or blocked candidate.

Project disappearance binds accepted/candidate project-inventory evidence and
derives tracked relevance from the accepted dataset→archive mapping plus each
accepted `ArchiveLock.extract_paths`. Translation coverage independently binds
authenticated TEI evidence. Missing inventory, TEI, source, manifest, or other
required evidence is an evaluation-error rather than an implicit pass.

**PH5 prebuild** runs after the complete candidate source/inventory/translation
contexts are assembled and before conversion. If it has unresolved blockers,
no publishable rebuild proceeds.

**PH5 postbuild** runs after Phase 6 creates an independent build report. For
`word-count-unexplained`, require both:

```
candidate_build_source_words == candidate_PH4_source_words
candidate_build_source_words - accepted_build_source_words == ph4_text_word_delta_sum
```

The build totals include the TF warp plus zero-span sidecar domain. Both
accepted/candidate build-report digests and both accepted/candidate dataset
contexts participate in the evidence fingerprint. Missing build evidence is a
non-approvable evaluation-error.

**Acceptance:** a synthetic archive with one unknown GDL shape blocks; a
synthetic archive adding 50 ordinary texts does not. Multiple simultaneous
findings are all emitted. A stale approval cannot match after condition,
evidence, contributor, candidate, or accepted baseline identity changes.

---

# Phase 6 — rebuild and validate

Rebuild only datasets whose archives changed (R-002 §9). Re-run the P-001 M6
invariants, then compare against the previous release:

- slot / word / document counts, with deltas explained by the Phase 4 diff
- every P-001 M1 disposition still 100 %
- TF loads, section addressing works, round-trip (M7) still passes
- translation coverage delta (M9)
- emit the independent accepted/candidate-compatible build report required by
  PH5 postbuild word reconciliation

After validation succeeds, run PH5 postbuild. A rebuild is not publication-ready
until both PH5 stages have no unresolved blocker and no evaluation-error.

**Acceptance:** rebuilding an unchanged archive set reproduces the previous
release's counts exactly.

---

# Phase 7 — package and publish

Deterministic archive (sorted entries, fixed mtimes), plus `upstream.lock.json`
for exactly the contributing archives, the validation reports, and
`SHA256SUMS`. Smoke-test by loading the packaged data in a clean directory.

Publish an immutable GitHub Release per Phase 0.1. Blocked updates publish
**reports only** — never a release.

Immediately before promotion/publication, perform the PH5 **TOCTOU** check:
re-read the last accepted baseline identities and recompute/verify candidate
source, contributor/dataset-manifest, project-inventory, TEI/build and finding
approval evidence. Any drift invalidates readiness. Only after this check may
lock/inventory/translation/build baselines advance atomically with publication.

**Acceptance:** reruns are idempotent; an existing tag fails rather than
overwrites; publication aborts if `main` or any accepted/candidate evidence
identity used by PH5 moved during the build.

---

# Phase 8 — workflows

- `discover.yml` — daily, `HEAD`-only sweep of tracked archives; opens or
  updates a tracking issue when something changed.
- `inventory.yml` — weekly, full `/json/` + `projects.json` sweep; reports
  projects appearing or disappearing (R-002 §5).
- `update.yml` — triggered by discovery or manually; full download → diff →
  PH5 prebuild → build → validate → PH5 postbuild → TOCTOU → publish.

Concurrency group per dataset so two updates cannot race.

---

# Phase 9 — tests

**Unit:** ETag/SHA decision table; ZIP traversal and bomb fixtures; the 4-byte
`404` body; three-level archive-name mapping; gate evaluation, exact approval
matching, deterministic multi-finding order, missing-evidence errors, and
accepted/candidate baseline lifecycle.

**Integration:** replay `etcsri` 2026-04-28 → 2026-08-07 end to end and assert
the diff, gates, rebuild and release notes are all correct. This is a real
upstream change, not a synthetic one (R-002 §4).

**Negative:** an archive that disappears; a licence string change; a lemma
coverage drop; stale approval evidence; contributor-set drift; missing TEI or
build evidence — each must block with the right finding/evaluation-error.

---

# Definition of done

- [ ] daily sweep does no work when ETags are unchanged
- [ ] byte-identical republication refreshes the lock and triggers no build
- [ ] archives are identified by our own SHA-256, never an upstream string
- [ ] the 4-byte `404` body and other non-ZIP responses are rejected
- [ ] extraction is path-safe, size-bounded and structurally derived
- [ ] `upstream.lock.json` records sha256, bytes, etag, mtime, `UTC-timestamp`, licence
- [ ] the existing snapshot is backfilled and provenanced (Phase 1.3)
- [ ] rebuilds are scoped to affected datasets only
- [ ] every gate in Phase 5 exists, is named, runs deterministically, and emits a typed subject
- [ ] approvals match exact condition and evidence fingerprint only; stale approvals do not carry forward
- [ ] every missing/malformed required input becomes a non-approvable evaluation-error
- [ ] dataset-wide gates bind accepted/candidate source state and contributor/dataset-manifest evidence
- [ ] blocked candidate evidence never advances the last accepted baseline
- [ ] PH5 prebuild runs before conversion and PH5 postbuild independently reconciles build/source word totals
- [ ] unknown GDL shapes and unknown chunk types block publication
- [ ] a disappeared project blocks and is never auto-deleted
- [ ] licence changes block
- [ ] translation-coverage falls block; rises do not; missing authenticated TEI evidence does not pass
- [ ] project-inventory and build-report evidence are versioned with accepted/candidate baselines
- [ ] the final TOCTOU check revalidates accepted and candidate evidence before atomic promotion
- [ ] green updates create immutable releases; blocked updates create reports only
- [ ] reruns are idempotent and existing tags fail
- [ ] the real `etcsri` 2026-04 → 2026-08 update replays green end to end
