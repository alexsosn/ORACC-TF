# ORACC-TF

A working copy of the [ORACC](http://oracc.org) open-data corpora, unpacked
into a single tree, plus the tooling to reproduce and maintain it — groundwork
for converting selected ORACC projects into
[Text-Fabric](https://annotation.github.io/text-fabric/) datasets.

## Contents

`data/` holds 33 top-level ORACC projects, 100 of which are subprojects,
extracted from ORACC's published ZIP distributions:

| Project | Subprojects |
|---|---|
| `tcma` | 29 — ali1, amarna, assur, barri, … ugarit |
| `atae` | 22 — assurmisc, burmarina, ctn1–3, ctn6, … wvdog152 |
| `saao` | 22 — saa01–saa21, saas2 |
| `ribo` | 11 — babylon2–8, babylon10, bab7scores, scores, sources |
| `rinap` | 8 — rinap1–5, rinap5p1, scores, sources |
| `riao`, `cmawro`, `cams` | 5 each |
| `adsd` | 5 — adart1–3, adart5–6 |
| `aemw` | 3 — alalakh, amarna, ugarit |
| `asbp` | 2 — ninmed, rlasb |
| `caspo`, `contrib`, `obabat` | 1 each |

The remaining 19 are flat single-project corpora: `akklove`, `babcity`,
`balt`, `blms`, `borsippa`, `btto`, `ccpo`, `cdli`, `ckst`, `csik`, `etcsri`,
`glass`, `hbtin`, `nere`, `obta`, `rimanum`, `suhu`, `urap`.

Each project directory follows ORACC's standard layout: `catalogue.json`,
`metadata.json`, `corpus.json`, per-text transliterations under `corpusjson/`,
glossaries (`gloss-*.json`) and indexes (`index-*.json`).

## Reproducing `data/` from scratch

The ZIPs themselves are not committed — they are opaque binaries git cannot
delta, and the extracted JSON is both the useful form and the git-friendly one.

```bash
# 1. Download the project ZIPs from http://oracc.org/doc/opendata/ into data/
# 2. Unpack them into their project/subproject tree
scripts/extract_archives.sh

# 3. Confirm every file landed at its recorded size
scripts/verify_extraction.py
```

The archives already encode their own paths (`atae-ctn1.zip` → `atae/ctn1/…`),
so the grouping falls out of extraction — see [docs/scripts.md](docs/scripts.md).

## Repository size

The tree is ~9.8 GB uncompressed but ORACC JSON is highly repetitive, so git
packs it at roughly 16x (measured: `saao` 1,522 MB → 97 MB). The packed
repository is well under GitHub's advisory limits.

One file exceeded GitHub's hard 100 MB per-file limit — `cdli/index-cat.json`
at 545 MB. It is stored sharded under `data/cdli/index-cat/` and can be
rejoined losslessly:

```bash
scripts/shard_index.py join data/cdli/index-cat -o data/cdli/index-cat.json
```

Before any push, `scripts/check_repo_limits.py` reports anything GitHub would
reject.

## Documentation

- [docs/scripts.md](docs/scripts.md) — the utility scripts in detail
- [docs/research.md](docs/research.md) — which ORACC projects are best suited
  to Text-Fabric conversion, and why

## Licence

ORACC corpus data is released by its projects under CC BY-SA 3.0 or CC0;
each project states its own terms in `metadata.json` and its index files.
The scripts in `scripts/` are provided under the MIT licence.
