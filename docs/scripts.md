# Utility scripts

Four small tools cover the pipeline from ORACC's published ZIPs to a
GitHub-hosted working copy. All are dependency-free (Python 3 stdlib + bash).

| Script | Purpose |
|---|---|
| [`extract_archives.sh`](../scripts/extract_archives.sh) | Unpack ORACC ZIPs into their project/subproject tree |
| [`verify_extraction.py`](../scripts/verify_extraction.py) | Check extracted files against the ZIP manifests |
| [`check_repo_limits.py`](../scripts/check_repo_limits.py) | Find files GitHub will reject before pushing |
| [`shard_index.py`](../scripts/shard_index.py) | Split/rejoin oversized ORACC index files |
| [`scan_annotation.py`](../scripts/scan_annotation.py) | Measure annotation depth across every corpus |

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
Text-Fabric. It is the evidence behind [research.md](research.md).

Takes roughly 10 minutes over the full 47k-file corpus. Writes a JSON report;
`--csv` also prints a flat summary.

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

`--replace` deletes the source file, but only after the shards verify.

### Ordering and integrity

ORACC emits `keys` in hash order, which carries no meaning. Sharding groups by
prefix, so `join` returns a semantically identical file whose keys are grouped
by shard rather than in the original order. Integrity is therefore checked with
an **order-independent digest** — a SHA-1 over the sorted per-entry hashes —
recorded in the shard directory's `_index.json` alongside entry counts.

`verify --against <original>` compares the shards to a source file directly.

### Memory

`split` and `join` load the whole document (roughly 6x the file size in RAM;
545 MB needs about 3.5 GB).

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
