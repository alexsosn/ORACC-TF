---
id: P-002
title: Automate ORACC upstream updates through ORACC-TF publication
type: plan
status: draft
priority: P0
depends_on: [R-002, P-001]
blocks: [P-003]
updated: 2026-08-29
---

# Plan: automate ORACC upstream updates through ORACC-TF publication

## Goal

A scheduled job notices that an ORACC archive changed, rebuilds only the
affected Text-Fabric datasets, proves the rebuild is sound, and publishes an
immutable release — or stops with a report naming exactly what a human must
decide.

Grounded in [R-002](../research/R-002-upstream-automation.md). Read its §1
first: ORACC supplies no version identity, so this plan manufactures one.

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
failure, missing TEI export, unparseable archive — blocks. It does not pass.

**5. Approvals attach to bytes.** An exception carries forward only while
*(archive sha256, text id, condition)* is unchanged.

**6. Rebuild the smallest thing that changed.** The unit is one dataset
(R-002 §9), not the corpus.

---

# Phase 0 — version and publication model

## 0.1 Three identities

```
oracc_state    max UTC-timestamp across contributing archives   e.g. 2026-08-07
tf_version     ORACC-TF converter/schema version                e.g. 1.2.0
dataset        the TF dataset name                              assyrian-royal-inscriptions
```

Release tag: `assyrian-royal-inscriptions/v1.2.0+oracc.2026-08-07`.

`oracc_state` is build metadata, not a precedence field — two archives can
carry the same date with different content. Precedence is `tf_version`.

**Acceptance:** tags sort correctly under SemVer; two different archive sets
never produce the same tag without differing `tf_version`.

## 0.2 Datasets and their inputs

`datasets.toml`:

```toml
[assyrian-royal-inscriptions]
archives = ["riao-ria1","riao-ria2","riao-ria3","riao-ria4","riao-ria5",
            "rinap-rinap1","rinap-rinap2","rinap-rinap3","rinap-rinap4",
            "rinap-rinap5","rinap-rinap5p1"]
tei = ["riao-teiCorpus"]

[etcsri]
archives = ["etcsri"]
```

**Acceptance:** every tracked archive belongs to ≥1 dataset; the daily sweep
polls only tracked archives (11, not 208).

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
- lemma-coverage delta per project
- new GDL object shapes not in P-001 §2.3's census
- new `c` chunk types
- licence string change
- `UTC-timestamp` before → after

**Acceptance:** the `etcsri` 2026-04 → 2026-08 change (Phase 1.3) produces a
diff whose text-level numbers reconcile with the corpus totals.

---

# Phase 5 — gates

Implement R-002 §7 as named, individually-suppressible gates:

| gate | blocks publication |
|---|---|
| `gdl-shape-unknown` | yes |
| `chunk-type-unknown` | yes |
| `lemma-coverage-drop` (> 2 pts) | yes |
| `word-count-unexplained` | yes |
| `q-collision-new-class` | yes |
| `project-disappeared` | yes |
| `licence-changed` | yes |
| `translation-coverage-drop` | yes |
| `texts-added` / `texts-modified` | no — normal |

Each gate emits a machine-readable finding: gate id, dataset, archive sha256,
affected text ids, and a one-line human explanation.

**Acceptance:** a synthetic archive with one unknown GDL shape blocks; a
synthetic archive adding 50 ordinary texts does not.

---

# Phase 6 — rebuild and validate

Rebuild only datasets whose archives changed (R-002 §9). Re-run the P-001 M6
invariants, then compare against the previous release:

- slot / word / document counts, with deltas explained by the Phase 4 diff
- every P-001 M1 disposition still 100 %
- TF loads, section addressing works, round-trip (M7) still passes
- translation coverage delta (M9)

**Acceptance:** rebuilding an unchanged archive set reproduces the previous
release's counts exactly.

---

# Phase 7 — package and publish

Deterministic archive (sorted entries, fixed mtimes), plus `upstream.lock.json`
for exactly the contributing archives, the validation reports, and
`SHA256SUMS`. Smoke-test by loading the packaged data in a clean directory.

Publish an immutable GitHub Release per Phase 0.1. Blocked updates publish
**reports only** — never a release.

**Acceptance:** reruns are idempotent; an existing tag fails rather than
overwrites; publication aborts if `main` moved during the build.

---

# Phase 8 — workflows

- `discover.yml` — daily, `HEAD`-only sweep of tracked archives; opens or
  updates a tracking issue when something changed.
- `inventory.yml` — weekly, full `/json/` + `projects.json` sweep; reports
  projects appearing or disappearing (R-002 §5).
- `update.yml` — triggered by discovery or manually; full download → diff →
  gates → build → validate → publish.

Concurrency group per dataset so two updates cannot race.

---

# Phase 9 — tests

**Unit:** ETag/SHA decision table; ZIP traversal and bomb fixtures; the 4-byte
`404` body; three-level archive-name mapping; gate evaluation.

**Integration:** replay `etcsri` 2026-04-28 → 2026-08-07 end to end and assert
the diff, gates, rebuild and release notes are all correct. This is a real
upstream change, not a synthetic one (R-002 §4).

**Negative:** an archive that disappears; a licence string change; a lemma
coverage drop — each must block with the right gate id.

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
- [ ] every gate in Phase 5 exists, is named, and is individually suppressible
- [ ] unknown GDL shapes and unknown chunk types block publication
- [ ] a disappeared project blocks and is never auto-deleted
- [ ] licence changes block
- [ ] translation-coverage falls block; rises do not
- [ ] approvals carry forward only for unchanged *(sha256, text id, condition)*
- [ ] green updates create immutable releases; blocked updates create reports only
- [ ] reruns are idempotent and existing tags fail
- [ ] the real `etcsri` 2026-04 → 2026-08 update replays green end to end
