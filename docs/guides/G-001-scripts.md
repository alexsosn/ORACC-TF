---
id: G-001
title: Utility scripts
type: guide
status: active
priority: P2
depends_on: []
updated: 2026-09-06
---

# Utility scripts

Four small tools cover the pipeline from ORACC's published ZIPs to a
GitHub-hosted working copy. All are dependency-free (Python 3 stdlib + bash).

| Script | Purpose |
|---|---|
| [`extract_archives.sh`](../../scripts/extract_archives.sh) | Unpack ORACC ZIPs into their project/subproject tree |
| [`verify_extraction.py`](../../scripts/verify_extraction.py) | Check extracted files against the ZIP manifests |
| [`check_repo_limits.py`](../../scripts/check_repo_limits.py) | Find files GitHub will reject before pushing |
| [`shard_index.py`](../../scripts/shard_index.py) | Split/rejoin oversized ORACC index files |
| [`scan_annotation.py`](../../scripts/scan_annotation.py) | Measure annotation depth across every corpus |
| [`audit_translations.py`](../../scripts/audit_translations.py) | Audit English-translation coverage and joinability |
| [`check_docs_registry.py`](../../scripts/check_docs_registry.py) | Validate `docs/registry.json` against the documents |

---

## extract_archives.sh

```bash
scripts/extract_archives.sh [DATA_DIR]     # default: ./data
```

ORACC publishes each project and subproject as its own ZIP. **The hyphenated
filenames do not need to be parsed** — every archive already carries its
correct path internally:

```
blms.zip        ->  blms/...          top-level project
atae-ctn1.zip   ->  atae/ctn1/...     subproject of atae
saao-saa01.zip  ->  saao/saa01/...
```

Extracting in place therefore reproduces the project/subproject grouping.
Parent and subproject archives write disjoint paths and merge cleanly:
`caspo.zip` + `caspo-akkpm.zip` gives `caspo/` plus `caspo/akkpm/`.

## verify_extraction.py

```bash
scripts/verify_extraction.py [DATA_DIR]    # default: ./data
```

Confirms every file in every archive exists on disk at its recorded
uncompressed size. Catches truncated extractions and partial overwrites.
Exit code 0 on success.

## check_repo_limits.py

```bash
scripts/check_repo_limits.py [ROOT]        # default: .
```

Lists files over GitHub's **100 MB hard block** and **50 MB warning**
threshold. Respects `.gitignore` when run inside a git repo. Exit code 1 if
anything would be rejected.

These limits apply to the file as stored, so git's compression does not help:
a 545 MB JSON that packs to 30 MB is still rejected.

## scan_annotation.py

```bash
scripts/scan_annotation.py [--data DATA_DIR] [-o report.json] [--csv]
```

Walks the CDL tree of every `corpusjson` file and reports, per project or
subproject, how much of each annotation layer is actually present — lemma
(`cf`), guide word, sense, normalisation, part of speech, morphological
segmentation (`base`/`morph`/`morph2`), sentence boundaries (`para`),
discourse labels, and how many signs carry cuneiform Unicode.

This distinguishes genuinely lemmatised corpora from bulk transliteration
dumps, which is what decides whether a corpus is worth converting to
Text-Fabric. It is the evidence behind [research.md](../research/R-001-corpus-selection.md).

Takes roughly 10 minutes over the full 47k-file corpus. Writes a JSON report;
`--csv` also prints a flat summary.

## check_docs_registry.py

```bash
scripts/check_docs_registry.py [--docs docs]
```

`docs/registry.json` drives the automated development loop: an agent reads it
to choose the next task. If it drifts from the documents on disk, the agent
works from a false map.

This checks that every document has complete front-matter with a unique id
matching its filename, that all `depends_on`/`blocks` targets exist, that the
registry agrees with the documents field for field, that every task's plan and
spec section are findable, that the task graph is acyclic, and that nothing is
marked `done` while a dependency is not. It also prints which tasks are ready
to start.

Exit code 1 on any problem, so it belongs in CI.

## audit_translations.py

```bash
scripts/audit_translations.py [--data DATA_DIR] [--tei TEI_DIR] [--include-witnesses]
```

Reports two different things that both get called "translation coverage":

- **declared** — `metadata.json` carries a `formats` block whose `tr-en` list
  names the texts the project says have an English translation (99.9 % of
  populated RIAO/RINAP editions).
- **joinable** — translations you can actually obtain and align. ORACC's
  per-text XTR URLs do not resolve, so in practice this means the published
  TEI corpus export (89.2 %).

Pass `--tei` a directory holding an unzipped TEI export to get the joinable
figures and the alignment-span statistics. Fetch it from
<http://oracc.museum.upenn.edu/riao/downloads/> — and note the export is
misnamed: `riao-teiCorpus-*.zip` contains the RINAP texts too.

The span statistics are the point: translation units span a median of 4 lines
and only 1 of 8,310 spans a single line, so translation must be modelled as a
node over a **line range**, never as a line feature.

`*/sources` and `*/scores` are excluded by default — they are score editions
with no translations. `--include-witnesses` counts them.

## shard_index.py

```bash
scripts/shard_index.py split  <index.json> -o <dir> [--max-mb 90] [--dry-run] [--replace]
scripts/shard_index.py join   <dir> -o <index.json>
scripts/shard_index.py verify <dir> [--against <index.json>]
```

ORACC index files are one JSON object:

```json
{ "<metadata>": "...",
  "keys": [ {"key": "...", "count": "...", "instances": ["..."]} ],
  "map":  { "<raw form>": "<normalised form>" } }
```

`split` shards the `keys` array by the first character of each key, so a
consumer can resolve a key to exactly one shard without scanning — `p137994`
always lives in `keys-p.json`. Any bucket still over `--max-mb` is
subdivided by second character. `map` is written separately. Each shard is
standalone valid JSON carrying the original metadata header.

`--replace` deletes the source only after a complete staged shard directory has
verified against its manifest. Failed parsing, size checks, or verification do
not publish partial output. A pre-existing output directory is preserved when
staging fails.

### Ordering and integrity

ORACC emits `keys` in hash order, which carries no meaning. Sharding groups by
prefix, so `join` returns a semantically identical file whose keys are grouped
by shard rather than in the original order. Integrity is checked with the
existing **order-independent v1 digest** — SHA-1 over the sorted per-entry
SHA-1 values — recorded in `_index.json` alongside entry counts. The streaming
implementation deliberately preserves those digest bytes so existing shard
manifests remain verifiable without migration.

`verify --against <original>` streams both the shards and source and compares
their semantic digests. An explicitly present empty `map: {}` remains distinct
from an absent map. Duplicate map keys and duplicate top-level fields fail
closed instead of being silently collapsed by `json.load`.

### Memory and temporary disk

`split`, `join`, and `verify` no longer materialize a whole index or all shard
payloads in Python memory. JSON is read incrementally. A temporary stdlib
SQLite database provides disk-backed payload storage, duplicate detection, and
sorting for the legacy digest; its configured SQLite page cache is 8 MiB.
Python-side parser memory therefore scales with the configured read chunk and
the largest individual JSON value being decoded, rather than with total index
size. Temporary disk use does scale with the data being processed.

The pre-redesign synthetic baseline showed the old whole-document path scaling
approximately linearly with input size:

| synthetic input | legacy peak RSS |
|---:|---:|
| 4.6 MiB | ~55 MiB |
| 9.2 MiB | ~93 MiB |
| 18.4 MiB | ~178 MiB |
| 36.8 MiB | ~346 MiB |

A separate post-redesign synthetic scaling run from **3.6 MiB through 28.4 MiB**
stayed in the **~27–36 MiB peak-RSS range** instead of following total input
size. The CI regression does not assert an OS-level RSS number, because allocator
and runner versions make that brittle. It forces 4 KiB parser chunks over a
>4 MiB generated index and asserts that the parser buffer remains below 64 KiB;
this catches accidental accumulation of prior chunks while leaving room for
implementation overhead. Giant individual entries are tested separately and
remain an explicit lower bound on required memory.

### Failure model

Malformed or truncated JSON, invalid nesting, duplicate object fields that would
lose information, a single shard that cannot satisfy `--max-mb`, and manifest
digest mismatches all abort before new output is accepted. `join` writes to a
temporary destination and only replaces the requested output after the staged
content matches the manifest. The committed v1 shard format remains readable
and joinable.

---

## Applied case: `cdli/index-cat.json`

The only file in this repo that exceeded GitHub's hard limit.

| | |
|---|---|
| Original | 545.0 MB, 1 file |
| Sharded | 545.0 MB, 38 files (36 key shards + `map.json` + `_index.json`) |
| Size overhead | +0.00% |
| Largest shard | 69.7 MB (`keys-2.json`) |
| Contents | 1,391,923 key entries; 1,038,133 map pairs |

Reproduce or reverse:

```bash
scripts/shard_index.py verify data/cdli/index-cat
scripts/shard_index.py join   data/cdli/index-cat -o data/cdli/index-cat.json
```

The rejoined file is `.gitignore`d — the sharded directory is the committed form.
