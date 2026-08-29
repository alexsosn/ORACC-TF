---
id: R-002
title: Upstream change detection, rebuild and publication for ORACC-TF
type: research
status: active
priority: P0
depends_on: [R-001]
informs: [P-002]
updated: 2026-08-29
---

# Research: automatic upstream discovery, rebuild, validation and publication for ORACC-TF

## Scope

ORACC-TF must detect that an ORACC project has been re-published upstream,
fetch the correct archives, verify them, rebuild the affected Text-Fabric
datasets, regenerate validation evidence, and publish an immutable ORACC-TF
release.

Every fact below was measured against `oracc.museum.upenn.edu` and the local
snapshot in `data/` on 2026-08-29, not inferred from documentation.

---

## 1. The central difference from a Zenodo-backed corpus

TLHdig-TF follows an upstream that hands it version identity for free:
immutable Zenodo records, DOIs, published MD5s, and a documented
latest-version relation. Its hard problem is *carrying approvals across* a
known version boundary.

**ORACC gives none of that.** It is a rolling publication with no version
numbers, no DOIs, and no published checksums. Its hard problem is the
mirror image: ORACC-TF must **manufacture** version identity from content,
per archive, and detect that a boundary happened at all.

| | TLHdig (Zenodo) | ORACC |
|---|---|---|
| version identity | immutable record id + DOI | **none** |
| published checksums | MD5 in record metadata | **none** (§2.4) |
| discovery API | Zenodo Records API | `projects.json` + `/json/` index (§2.1) |
| archive naming | changed between releases | stable `<project>[-<sub>].zip` (§2.2) |
| unit of release | one archive for the corpus | **208 independently updated archives** (§2.3) |
| change signal | new record id | `Last-Modified` / `ETag` / `UTC-timestamp` (§3) |
| retraction | records are permanent | projects appear, rename and vanish (§5) |

Consequence: the ORACC-TF updater is **per-archive**, not per-corpus, and its
"version" is a content hash it computes itself.

---

## 2. Discovery

### 2.1 Two machine-readable inventories exist

`http://oracc.museum.upenn.edu/projects.json` returns a clean list of public
projects and subprojects:

```json
{"type":"projects","public":["adsd","adsd/adart1",...,"aemw/alalakh/idrimi",...]}
```

144 entries as measured. Note it includes three-level paths
(`aemw/alalakh/idrimi`), which the current snapshot's two-level directory
layout does not represent.

`http://oracc.museum.upenn.edu/json/` returns an Apache directory index
listing **208 downloadable archives** — more than `projects.json` names,
because it also exposes archives such as `aemw-amarnax.zip` and
`aemw-myamarna.zip`.

**Use `/json/` as the download inventory and `projects.json` as the
publication-status inventory.** They answer different questions and disagree;
neither alone is sufficient.

### 2.2 Only one URL pattern is universal

Two patterns exist and they are not equivalent:

| pattern | result |
|---|---|
| `/json/<project>[-<sub>].zip` | works for all 208 archives |
| `/<project>/downloads/<project>-json.zip` | works for some projects; **`etcsri` and `blms` return a 4-byte body `404` with HTTP 200** |

The `/downloads/` pattern also returns **HTTP 200 for missing files**, so a
naive status-code check treats a 404 as success. Any fetcher must validate
that the response body is actually a ZIP, not trust the status line.

Archive names map to the snapshot's directory layout by replacing `-` with
`/`: `riao-ria1.zip` → `riao/ria1/`. This has been stable, but it is a
convention, not a guarantee, and three-level names such as
`aemw-alalakh-idrimi.zip` make the mapping ambiguous.

### 2.3 Updates are per-archive and highly asynchronous

Measured `Last-Modified` across archives:

| archive | Last-Modified | bytes |
|---|---|--:|
| `riao-ria1.zip` | 2023-04-29 | 1,320,374 |
| `atae-kalhu.zip` | 2023-07-28 | 10,130,337 |
| `riao-ria4.zip` | 2023-10-22 | 5,075,170 |
| `saao-saa01.zip` | 2024-06-07 | 5,008,085 |
| `blms.zip` | 2024-06-28 | 11,049,307 |
| `riao-json.zip` | 2025-04-16 | 16,605,952 |
| `rinap-rinap3.zip` | 2026-04-28 | 12,192,081 |
| `etcsri.zip` | **2026-08-07** | 13,205,491 |

Spans over three years. There is no corpus-wide release event to wait for,
so a single global "is ORACC newer?" check is meaningless. Discovery must
iterate archives.

### 2.4 No checksums are published

```
/json/SHA256SUMS  -> HTTP 500
/json/MD5SUMS     -> HTTP 500
```

Nothing to verify a download against. ORACC-TF must compute and record its
own SHA-256 per archive; that hash becomes the archive's identity, and the
only defence against a truncated or partial download is size + hash
stability across two fetches.

---

## 3. Change-detection signals, ranked

Three independent signals exist. None is sufficient alone.

**1. `ETag` (strongest cheap signal).** Present on `/json/*.zip`, in Apache's
`inode-size-mtime` form (e.g. `"d0092a-65080cba6b4c0"`). It changes when the
file changes and is free to obtain via `HEAD`. It is **not** a content hash:
it also changes on a byte-identical rebuild or a server-side file move, so it
can produce false positives. Treat it as *"something may have changed"*.

**2. `Last-Modified` + `Content-Length`.** Also free via `HEAD`. Useful as a
human-readable corroboration and for ordering, but mtime can move without
content changing.

**3. `UTC-timestamp` inside `metadata.json` (strongest semantic signal).**
Present in **140 of 140** local projects. This is ORACC's own build stamp for
that project:

```
balt            2025-11-21T08:06:45
tcma/assur      2025-05-30T06:51:22
rinap/rinap5    2025-05-02T06:43:19
aemw            2021-03-31T15:32:29
cdli            2019-01-12T02:59:09
```

It requires downloading the archive, so it cannot drive discovery — but it is
what should be recorded in the lock and shown in release notes, because it is
the only timestamp that means "ORACC rebuilt this data".

**Recommended cascade:** `HEAD` → compare `ETag`/`Last-Modified`/length against
the lock → on any difference, download → compute SHA-256 → if the SHA matches
the lock, record the new ETag and **stop** (a no-op rebuild); if it differs,
proceed to the diff stage. This makes false-positive ETags cheap.

---

## 4. The snapshot has already drifted

This is not hypothetical. Comparing the committed snapshot against upstream
today:

- **`etcsri` has changed upstream.** Local snapshot 12,928,763 bytes (fetched
  2026-04-28); upstream now 13,205,491 bytes, `Last-Modified` 2026-08-07.
  `etcsri` is R-001's top conversion candidate, so the first dataset built
  would already be stale.
- **45 public projects are absent from the snapshot**, including substantial
  ones: `dcclt` and its four subprojects, `armep`, `arrim`, `ecut`, `ctij`,
  `dsst`, `edlex`, `atae/kalhu`, `atae/nineveh`, `atae/durszarrukin`,
  `atae/kunalia`, `cams/akno`, `contrib/lambert`, `aemw/alalakh/idrimi`.
- **The source archives are no longer on disk.** They were deleted after
  extraction (they are gitignored). The snapshot's provenance therefore rests
  entirely on the extracted JSON, with no recorded checksum, size, or fetch
  date for any archive.

That last point is the strongest argument for the lock file in §6: the
current repository cannot answer "which bytes produced this data?" for any
project.

---

## 5. Projects are not stable identifiers

Comparing the snapshot's directories against `projects.json`:

- **In the snapshot, not public now:** `atae/ctn1`, `atae/ctn2`, `atae/ctn3`,
  `atae/ctn6`, `atae/stat1`–`stat3`, `atae/assurmisc`, `atae/edubba10`,
  `atae/rfdn17`, `atae/wvdog152`, `aemw/alalakh`, `aemw/ugarit`.
- **Public now, not in the snapshot:** `atae/assur`, `atae/kalhu`,
  `atae/nineveh`, `atae/kunalia`, `atae/durszarrukin`.

The ATAE pattern looks like a **reorganisation** from publication-based
subprojects (`ctn1`, `stat1`, `wvdog152` — book series) to site-based ones
(`assur`, `kalhu`, `nineveh`). Whether texts moved, merged or were withdrawn
cannot be determined from names.

**Therefore:** disappearance of a project must be a *review condition*, never
an automatic deletion of a published dataset. A Q-number-level diff is the
only way to distinguish "renamed" from "withdrawn", and that requires
retaining the previous extraction.

---

## 6. Introduce an upstream lock

The repository needs a generated `upstream.lock.json` recording, per archive:

```json
{
  "riao-ria4": {
    "url": "http://oracc.museum.upenn.edu/json/riao-ria4.zip",
    "sha256": "…",
    "bytes": 5075170,
    "etag": "\"4d6b62-6083…\"",
    "last_modified": "2023-10-22T09:57:38Z",
    "oracc_utc_timestamp": "2023-10-22T07:41:03",
    "fetched_at": "2026-08-29T…Z",
    "extract_paths": ["riao/ria4/"],
    "text_ids_sha256": "…"
  }
}
```

`text_ids_sha256` — a hash over the sorted list of text ids and their
individual content hashes — is what lets §5's rename question be answered
cheaply on the next update.

A companion `upstream.toml` holds policy: which archives are tracked, poll
cadence, and which changes may auto-publish.

---

## 7. What must block automatic publication

R-001 and P-001 already established the source hazards. Under automation each
becomes a gate:

| condition | why it blocks |
|---|---|
| a GDL object shape not in P-001 §2.3's census | the sign ontology is decided per shape; an unknown shape means unclassified slots |
| a new `c` chunk type | P-001 keeps all chunk types; a new one is unmodelled |
| lemma coverage drops > 2 points for a project | suggests upstream regression or a parse failure, not an edition change |
| word count changes by more than the text-level diff explains | indicates a walker bug, not source change |
| a new Q-number collision pattern beyond `rinap5`/`rinap5p1` | document identity is `subproject:Q`; a new collision class needs review |
| a tracked project disappears from `projects.json` | §5 — could be rename or withdrawal |
| licence string changes | §8 |
| translation coverage falls | the TEI join is external to the JSON and can rot independently |

Everything else — new texts, new lemmas, edition revisions, catalogue
changes — should flow through unattended.

Gates should carry forward per §5 of the TLHdig research: an approval attaches
to *(archive sha256, text id, condition)*, so it survives an unrelated
re-publication of the same archive but not a change to the text it approved.

---

## 8. Licence is a moving part, not a constant

P-001 §2.11 records that `metadata.json` and the TEI export declare CC0 while
the live edition pages declare CC BY-SA 3.0 with a citation request. Since the
JSON is refetched on every update, the licence string is upstream-controlled
and can change silently.

The lock must record the licence per archive, and a change must block
publication until reviewed. This is cheap insurance against redistributing
under superseded terms.

---

## 9. Rebuild granularity

Because archives update independently (§2.3), a full rebuild of everything on
every change is wasteful and makes provenance muddy. The unit of rebuild
should be **one TF dataset**, with the lock recording which archives feed it:

```
assyrian-royal-inscriptions  <- riao-ria1..5, rinap-rinap1..5, rinap-rinap5p1  (11 archives)
etcsri                       <- etcsri                                          (1 archive)
```

A change to `riao-ria4.zip` rebuilds only the joined RIAO+RINAP dataset. A
change to `etcsri.zip` rebuilds only that one. Datasets are versioned and
released independently.

---

## 10. Translations are a second, independent upstream

P-001 M9 sources translations from the TEI corpus export, which has its own
cadence and its own naming trap: `riao-teiCorpus-20241202.zip` contains the
RINAP texts too, and the date is *in the filename*, so discovery means
listing `/riao/downloads/` and `/rinap/downloads/` and picking the newest
`*teiCorpus-*.zip` — not requesting a fixed URL.

The TEI and JSON layers can drift apart: a JSON update can add texts the TEI
export does not yet cover. The update report must show translation coverage
as a delta (P-001 measured 89.2 %), and a **fall** in coverage is a gate
(§7), while a rise is normal.

---

## 11. Publication model

Follow TLHdig-TF's conclusion: Actions artifacts are diagnostics, releases are
products. Each green update produces an immutable GitHub Release whose tag
binds the dataset, its TF schema version, and the upstream state:

```
assyrian-royal-inscriptions/v1.2.0+oracc.2026-08-07
```

with assets: the packaged TF data, `upstream.lock.json` for exactly those
archives, the validation reports, and `SHA256SUMS`.

Because ORACC has no version string to inherit, the `+oracc.<date>` build
metadata should be the **maximum `UTC-timestamp`** across the contributing
archives (§3 signal 3) — the only upstream-meaningful date available.

---

## 12. Polling cadence

`HEAD` on 208 archives is cheap and can run daily. A full fetch is not.
Recommended: daily `HEAD` sweep over tracked archives only (11 for the first
dataset, not 208); download and rebuild only on ETag/length change; a weekly
full-inventory sweep to detect projects appearing or disappearing (§5).

Be a good citizen of a university-hosted server: serialise requests, set a
descriptive User-Agent, and back off on 5xx.

---

## 13. Sources

### Measured endpoints
- `http://oracc.museum.upenn.edu/projects.json` — 144 public entries
- `http://oracc.museum.upenn.edu/json/` — 208 archives, Apache index
- `http://oracc.museum.upenn.edu/json/<name>.zip` — universal download pattern
- `http://oracc.museum.upenn.edu/<p>/downloads/` — per-project, includes TEI exports
- `http://oracc.museum.upenn.edu/json/SHA256SUMS` — HTTP 500, no checksums published

### ORACC documentation
- Oracc JSON open data: <http://oracc.org/doc/opendata/>
- XTR (XML translations) namespace: <http://oracc.museum.upenn.edu/ns/xtr/1.0/>

### Local evidence
- `data/*/metadata.json` — `UTC-timestamp` present in 140/140 projects
- [R-001](R-001-corpus-selection.md) — corpus selection and annotation census
- [P-001](../plans/P-001-riao-rinap-tf.md) — CDL format ground truth and gates
