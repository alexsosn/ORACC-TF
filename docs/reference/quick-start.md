---
title: Quick start
status: active
---

# Quick start: Assyrian royal inscriptions

`assyrian-royal-inscriptions` is the joined **RIAO and RINAP** Text-Fabric
dataset of Assyrian royal inscriptions. It represents the editorial ORACC
corpusjson/GDL text structure as signs, word occurrences, lines, faces,
documents, and lexemes, with a separate line-range relation for those official
translations that could be aligned to the texts.

It is **not** every ORACC project or a photographic edition of the physical
inscriptions. Witness-only `scores` and `sources` subprojects are outside
this semantic dataset. Some published source members are unreadable or stubs;
some words have no lemma; and official running translations do not cover every
document. See the [source-to-TF audit](data-audit.md) and
[translations](translations.md) for those limits.

## 1. Obtain and extract the standalone corpus

Use the **versioned `assyrian-royal-inscriptions` release ZIP** and
its matching checksum from the
[ORACC-TF GitHub Releases page](https://github.com/alexsosn/ORACC-TF/releases).
Verify the checksum before extracting, and record the `release_id`,
`builder_commit`, and `source_state` from `manifest.json`. A green CI
build or staged candidate archive is not itself evidence of a public release;
follow the actual release asset URL and its matching checksum.

For a published **v1.0.0** release, the following Bash commands download the
two *matching* public assets, verify the checksum **before** extraction, and
enter the standalone corpus root (Linux; see other platforms below):

```bash
ARCHIVE=assyrian-royal-inscriptions-1.0.0.zip
BASE=https://github.com/alexsosn/ORACC-TF/releases/download/v1.0.0
curl -fL "$BASE/$ARCHIVE" -o "$ARCHIVE"
curl -fL "$BASE/$ARCHIVE.sha256" -o "$ARCHIVE.sha256"
if sha256sum --check "$ARCHIVE.sha256"; then
  mkdir -p assyrian-royal-inscriptions
  python -m zipfile -e "$ARCHIVE" assyrian-royal-inscriptions
  cd assyrian-royal-inscriptions
else
  echo "Checksum verification failed: refusing extraction" >&2
fi
```

The exact checksum asset is
`assyrian-royal-inscriptions-1.0.0.zip.sha256`; do not use a sidecar
belonging to a different archive or a CI measurement ZIP.

**Only use these commands after that release actually appears on GitHub.** If
v1.0.0 is not yet published, `curl -fL` reports the failed download;
a short-lived workflow artifact is not an interchangeable substitute.
On macOS use `shasum -a 256 -c "$ARCHIVE.sha256"` instead of `sha256sum`.
On Windows, download both named assets from the Releases page and use
`Get-FileHash -Algorithm SHA256` in PowerShell to compare the ZIP's digest
with the digest in its `.sha256` sidecar before extracting.

The ZIP contains `manifest.json`, `app/`, `tf/`, and `docs/` directly at
its root—there is no redundant dataset directory *inside* the archive.
You do not need to clone the ORACC-TF builder repository, download its
multi-GB source tree, or install the `oracc-tf` converter to *use* the corpus.

Install the pinned consumer runtime:

```bash
python -m pip install text-fabric==13.1.0
```

For expected archive size, installed footprint, RAM, and startup measurements,
see [Lightweight installation](installation.md).

## 2. Load the Text-Fabric app in Python

Run Python **from the extracted corpus root**:

```python
from pathlib import Path
from tf.app import use

root = Path.cwd()  # extracted release root, containing app/ and tf/
A = use(f"app:{root / 'app'}")
api = A.api
assert api is not None
```

The generated app locates the sibling `tf/<version>` tree. No maintainer-local
`locations=` setting or developer cache is required.

## 3. Retrieve your first passage

Here, the identity contains both the ORACC subproject and its Q-number.
Do not use the bare Q-number as a cross-project key.

```python
key = "riao/ria1:Q001801"
doc = next(
    n for n in api.F.otype.s("document")
    if api.F.document_key.v(n) == key
)
line = next(
    n for n in api.L.d(doc, otype="line")
    if api.F.line.v(n) == "Q001801.1"
)
words = api.L.d(line, otype="word")
print([api.F.form.v(word) for word in words])
```

This prints the source transliterations for the first numbered line. To
retrieve the official translated range covering the same line, follow the
*incoming* `translation_line` edge:

```python
units = api.E.translation_line.t(line)
print([api.F.translation_text.v(unit) for unit in units])
```

The returned list can be empty: a document without an aligned official
translation is not a failed load. See [Translations](translations.md).

## 4. Open the browser

From that same extracted root:

```bash
tf "app:$PWD/app"
```

This is the Text-Fabric 13.1 browser route tested against a clean staged
distribution. Use an absolute path to `app/` on shells without `$PWD`.

## Next steps

Start with the [query guide](query-guide.md) for lexical, metadata, and
translation-range examples; then read the [data model](model.md),
[signs and synthetic anchors](signs.md),
[words and lexemes](words-and-lexemes.md),
[qualified document identity](identity.md), and
[generated feature reference](features.md). See
[reproducibility](reproducibility.md) to identify a source snapshot and release
build without confusing a user installation with a maintainer rebuild.
