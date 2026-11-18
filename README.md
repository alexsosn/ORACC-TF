# ORACC-TF

ORACC-TF builds [Text-Fabric](https://annotation.github.io/text-fabric/) datasets from
[ORACC](https://oracc.museum.upenn.edu/) open data. The central repository keeps
the source snapshot, conversion code, validation, documentation, and release
tooling needed to build those datasets reproducibly.

## Status

The first standalone corpus, `assyrian-royal-inscriptions` (RIAO/RINAP), is
**published as [v1.0.0](https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0)**.
The remaining **independent public-download/clean-install acceptance**, not
release publication itself, is tracked under
[#23](https://github.com/alexsosn/ORACC-TF/issues/23),
[#83](https://github.com/alexsosn/ORACC-TF/issues/83), and the
[user-facing 1.0 gate #89](https://github.com/alexsosn/ORACC-TF/issues/89).

This repository is the **builder/source repository**, not the intended
installation surface for researchers. It contains the large ORACC source tree
and development infrastructure. Researchers can download the published
standalone ZIP containing Text-Fabric data, its app, and documentation
without cloning this repository.

For a stable end-user package, use the [published GitHub Releases](https://github.com/alexsosn/ORACC-TF/releases)
and verify the matching checksum. Workflow candidates are not public releases.

## Published ETCSRI and NINMED corpora: native Text-Fabric 0.1.0

Both corpora are **publicly available** in [native-v0.1.0](https://github.com/alexsosn/ORACC-TF/releases/tag/native-v0.1.0).
Each ZIP contains versioned Text-Fabric data, an auto-discoverable local
browser app, a corpus-specific manual and its manifest. You need **only**
Text-Fabric to read them, not this source repository, its ORACC JSON or the
converter. Both public assets were independently downloaded, checksummed,
extracted and queried in [GitHub Actions run 44377078649](https://github.com/alexsosn/ORACC-TF/actions/runs/44377078649).

| Corpus | Source bodies | Source words | Download | Verify |
| --- | ---: | ---: | --- | --- |
| ETCSRI (Sumerian royal inscriptions) | 1,456 | 29,573 | [etcsri-0.1.0.zip](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/etcsri-0.1.0.zip) | [SHA-256](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/etcsri-0.1.0.zip.sha256) |
| ASBP/NINMED (Nineveh medical texts) | 159 readable, plus one known zero-byte source member | 65,089 | [ninmed-0.1.0.zip](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip) | [SHA-256](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip.sha256) |

### Start reading without a source checkout

On Linux, using Python 3.10+ and `curl`/`unzip` (change `corpus` to `ninmed`
to download the medical texts):

```bash
corpus=etcsri
base="https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0"
curl --fail --location -o "$corpus-0.1.0.zip" "$base/$corpus-0.1.0.zip"
curl --fail --location -o "$corpus-0.1.0.zip.sha256" "$base/$corpus-0.1.0.zip.sha256"
sha256sum -c "$corpus-0.1.0.zip.sha256"
mkdir -p "$corpus-0.1.0"
unzip -q "$corpus-0.1.0.zip" -d "$corpus-0.1.0"
cd "$corpus-0.1.0"
python -m pip install "text-fabric==13.1.0"
python -m tf.browser.start "app:$PWD/app" "--modules=" -noweb
```

Open the localhost URL printed by Text-Fabric. On macOS, replace `sha256sum -c`
with `shasum -a 256 -c`; on Windows, verify the companion SHA-256 using
`Get-FileHash` and unpack the ZIP before launching the browser. In Python,
load the unpacked corpus with `from tf.app import use` and
`A = use("app:/absolute/path/to/unpacked/app", modules=[""], silent="deep")`.
The app automatically locates its sibling `tf/0.1.0/` directory.

The built-in browser is intended for advanced Text-Fabric/TFQL research;
ordinary catalogue browsing and form search without TFQL remain tracked in
[issue #189](https://github.com/alexsosn/ORACC-TF/issues/189). Neither
JSON-derived corpus contains an official running translation. ORACC JSON
exports declare CC0, while the converter uses MIT and ORACC websites,
third-party images and independently edited texts retain separate rights.
See the [ETCSRI](docs/native/etcsri/rights.md) and
[NINMED](docs/native/ninmed/rights.md) source/citation notices.

## First dataset: `assyrian-royal-inscriptions`

The dataset is defined in [`datasets.toml`](datasets.toml). Its source selection
aggregates:

- RIAO 1–5;
- RINAP 1–5 plus RINAP 5 Part 1;
- the RIAO TEI corpus source used for the translation workstream.

The converter preserves ORACC textual structure and annotations in Text-Fabric,
including sign slots, words, lexemes, document/face/column/line structure,
catalogue metadata, qualified document identity, and source-grounded cuneiform
and transliteration features. Zero-span textual entities are represented by
explicit synthetic empty slots rather than fabricated visible text.

The generated feature inventory is documented in
[`docs/reference/features.md`](docs/reference/features.md). The pinned RIAO/RINAP
source audit, official TEI translation import, real Text-Fabric browser acceptance,
and standalone researcher manual were validated on the production
release-format ZIP. **The v1.0.0 ZIP and checksum are now public**;
an additional logically independent, fresh-machine user acceptance of the
published bytes remains tracked by [#23](https://github.com/alexsosn/ORACC-TF/issues/23)
and [#83](https://github.com/alexsosn/ORACC-TF/issues/83).

## Researcher documentation

User-facing documentation lives under
[`docs/reference/`](docs/reference/):

- [Data model](docs/reference/model.md)
- [Signs](docs/reference/signs.md)
- [Words and lexemes](docs/reference/words-and-lexemes.md)
- [Translations](docs/reference/translations.md)
- [Document identity](docs/reference/identity.md)
- [Query guide](docs/reference/query-guide.md)
- [Reproducibility](docs/reference/reproducibility.md)
- [Feature reference](docs/reference/features.md)

The standalone researcher manual is assembled into the tested distribution.
Start with the [quick start](docs/reference/quick-start.md) and
[installation and resource measurements](docs/reference/installation.md).
The complete manual and source-faithful app passed staged release-format ZIP
checks, and the publishing workflow downloaded and verified both public assets.
Independent fresh-machine extraction, load and browser acceptance of those
exact public bytes is the remaining final gate.

The two separately developed native corpora have dedicated, source-specific
researcher manuals: [ETCSRI](docs/native/etcsri/index.md) (Sumerian royal
inscriptions and morphological annotations) and
[NINMED](docs/native/ninmed/index.md) (Nineveh medical texts and ORACC lexemes).
These describe the verified public native `0.1.0` distributions, optional
local reconversion workflows and separate source rights. The release-delivery
gate [#194](https://github.com/alexsosn/ORACC-TF/issues/194) passed public
download, checksum, Text-Fabric and browser smoke tests.

Maintainer research, design plans, reports, and the agentic-development
registry are indexed separately in [`docs/README.md`](docs/README.md).

## Development quick start

ORACC-TF requires Python 3.10 or newer.

```bash
git clone https://github.com/alexsosn/ORACC-TF.git
cd ORACC-TF

python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

pytest -q -m 'not corpus'
```

The fast test suite does not require a full-corpus run. Whole-corpus and
integration work uses the source data under `data/` and is intentionally
separate from the normal researcher installation path.

## Optional ETCSRI source reconversion (advanced users)

After installing a wheel built from this repository, researchers can create
a separate ETCSRI Text-Fabric corpus **without cloning the large builder
repository or receiving upstream ORACC source files in the wheel**:

```bash
python -m pip install /path/to/oracc_tf-0.1.0-py3-none-any.whl
python -m oracc_tf build-etcsri \
  --source-dir /path/to/etcsri/corpusjson \
  --output /path/to/my-etcsri-tf
```

`--source-dir` may also point to the parent of `corpusjson/`.
Optionally repeat `--text-id Q000935` to build a selected subset.
The command refuses missing source files and nonempty output directories;
it does not download, redistribute, or silently skip source material.

To query the resulting TF directly:

```python
from tf.fabric import Fabric
tf = Fabric(locations="/path/to/my-etcsri-tf", silent="deep")
assert tf.loadAll(silent="deep")
api = tf.api
matching_words = [
    n for n in api.F.otype.s("word")
    if api.F.morph.v(n)
]
print(len(matching_words))
```

This optional source-to-TF workflow creates a local development copy.
Researchers who only want to use the published corpus should download the
[verified ETCSRI ZIP](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/etcsri-0.1.0.zip) instead.
See the [source-specific reader manual](docs/native/etcsri/index.md) for
source-grounded morphology, installation and reuse rights. The corpus
conversion workstream remains separately indexed as
[issue #32](https://github.com/alexsosn/ORACC-TF/issues/32).
A clean-wheel end-to-end CI smoke test exercises this command against
the pinned real edition Q000935 and checks TF morphology queries.

## Optional NINMED source reconversion (advanced users)

The source-complete native `asbp/ninmed` converter supports a code-only
wheel with a user-supplied primary ORACC `corpusjson` directory:

```bash
python -m oracc_tf build-ninmed \
  --source-dir /path/to/asbp/ninmed/corpusjson \
  --output /path/to/my-ninmed-tf \
  --skip-known-empty
```

**Why `--skip-known-empty`?** The currently checked-in ORACC NINMED source
tree contains 160 `*.json` files: 159 readable texts and one genuinely
zero-byte `P395407.json`. A full-directory build rejects that file
without explicit opt-in; the flag excludes **only that known empty
member** and reports its ID. Unknown empty or malformed sources still
fail. Omit the flag when building a selected readable edition, for example:

```bash
python -m oracc_tf build-ninmed \
  --source-dir /path/to/asbp/ninmed/corpusjson \
  --output /path/to/one-text-tf \
  --text-id P285136
```

To query the resulting native word→lexeme graph:

```python
from tf.fabric import Fabric
tf = Fabric(locations="/path/to/my-ninmed-tf", silent="deep")
assert tf.loadAll(silent="deep")
api = tf.api
matches = [w for w in api.F.otype.s("word") if api.F.cf.v(w) == "DÙ.DÙ.BI"]
for w in matches[:5]:
    print(api.F.source_id.v(w), api.E.word_lex.f(w))
```

In the initial whole-source GitHub runner measurement, building the 159
readable editions took **12.47 s**, generating **91.4 MB** of TF
files, with **~997 MiB peak process RSS** including TF verification/load.
These are indicative build/test measurements, not a laptop memory guarantee.

This locally rebuilt converter output is a development copy, separate from
the [published NINMED ZIP](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip).
Neither the local app nor the public archive is a hosted browser service or a
replacement for `Nino-cunei/ninmed`. Read the
[NINMED manual](docs/native/ninmed/index.md) for native lexical features,
installation, source exceptions and reuse rights. Primary-source form differences remain documented
under [issue #33](https://github.com/alexsosn/ORACC-TF/issues/33).
A clean-wheel E2E smoke installs the code without cloning the large
source tree and queries real P285136/P425685 TF data.

## Native ETCSRI/NINMED local browser preview

The installed converter can build either corpus from user-supplied ORACC
`corpusjson` files. An **optional locally generated** Text-Fabric browser app can then
be prepared from that independently loadable `tf/` output:

```bash
# First use build-etcsri or build-ninmed (documented above).
python -m oracc_tf prepare-local-app \
  --kind etcsri \
  --tf-dir /path/to/etcsri-tf \
  --app-dir /path/to/etcsri-app

# Starts the standard Text-Fabric browser without opening a browser tab:
python -m tf.browser.start app:/path/to/etcsri-app \
  --locations=/path/to/etcsri-tf --modules= -noweb
```

For NINMED, change `--kind` to `ninmed` and point `--tf-dir`
to that corpus's generated TF directory. Use a **new or empty** `--app-dir`
for each preview: local generation refuses to overwrite a nonempty folder.
Open the localhost URL printed by Text-Fabric in a web browser.
In the search pad, enter `word`, click the search button, and expand a result
with its disclosure triangle. The native browser shows source-attested ETCSRI
morphology or NINMED lexical features in the expanded word card; it does not
infer absent annotations. The original document and line identifiers remain
available for cross-checking the source.

**Cuneiform font:** The browser renders source UTF-8 signs from
`text-orig-full`. If the sign boxes or the *Special characters in
text-orig-full* palette show empty squares, install a system font with
Unicode cuneiform coverage, such as
[Noto Sans Cuneiform](https://notofonts.github.io/cuneiform/).
For Ubuntu 22.04/24.04 and compatible systems:

```bash
sudo apt-get install fonts-noto-core
fc-cache -f
fc-match -f '%{family}:%{file}\n' 'sans-serif:charset=1202D'
```

The last command should resolve U+1202D (`𒀭`) to a cuneiform-capable font
such as `Noto Sans Cuneiform`, rather than a generic fallback without the glyph.
On Windows or macOS, install Noto Sans Cuneiform using the operating system's
font manager and restart the browser. Font rendering is a *local browser/OS
requirement*: the Python wheel and TF output intentionally do **not** bundle
fonts or fetch remote fonts at runtime. Missing squares do not imply that the
original ORACC signs have been removed or replaced by the converter.

The local app checks the **actual native document identities and node
types**, and deliberately does not register either corpus as a released
semantic dataset. Technical missing-span, nonword and determinative
objects are hidden from normal ETCSRI textual display rather than
rendered as imaginary cuneiform. Original primary ORACC annotations
remain in the TF graph and are queryable via its Python API.

The official Text-Fabric browser uses the supplied *flat* TF directory;
do not append `/0.1.0` to the `--locations` path. This is a local
preview feature and not a hosted service, bundled source corpus, or
assertion of published dataset/translation licence clearance.

## Repository layout

| Path | Purpose |
|---|---|
| [`datasets.toml`](datasets.toml) | semantic dataset definitions and source membership |
| [`programs/oracc_tf/`](programs/oracc_tf/) | conversion and build code |
| [`tests/`](tests/) | unit, contract, corpus, and integration tests |
| [`docs/reference/`](docs/reference/) | researcher-facing corpus documentation |
| [`docs/research/`](docs/research/) | measured research behind design decisions |
| [`docs/plans/`](docs/plans/) | implementation plans and acceptance criteria |
| [`data/`](data/) | large ORACC source working tree used by the builder |
| [`scripts/`](scripts/) | repository maintenance and analysis utilities |

Low-level source-tree maintenance commands are documented in
[`docs/guides/G-001-scripts.md`](docs/guides/G-001-scripts.md). Those utilities
are useful for maintaining local source material, but simple archive extraction
or size verification alone is not equivalent to release provenance.

## Data model

The Text-Fabric slot type is `sign`. Source words and higher structural nodes
are connected to those slots through the normal TF graph. Technical empty
positions use `synthetic=1` sign slots that preserve ordering but carry no
fabricated cuneiform, transliteration, or lexical content.

See the [data-model reference](docs/reference/model.md) and
[ADR-0001](docs/reference/architecture/ADR-0001-empty-slots-not-sidecars.md) for
the current rule.

## Packaging a standalone candidate (maintainers)

After a registered build, app generation and researcher-manual assembly have
already been validated and staged with `distribution.stage_distribution`,
package the **same complete staged tree** for manual publication:

```bash
python -m oracc_tf.release_archive \
  --stage /path/to/assyrian-royal-inscriptions \
  --output-dir /path/to/release-output

(cd /path/to/release-output && sha256sum -c assyrian-royal-inscriptions-*.zip.sha256)
```

The resulting ZIP includes TF data, the app and researcher documentation;
the sidecar is computed from its exact archive bytes. `<release_id>` comes
from the staged `manifest.json`; it is **not** inferred from the builder's
Python package version. The CLI deliberately refuses incomplete/unowned trees
and never uploads assets or creates tags. The full-corpus installation CI also
builds and checks a release-format ZIP and checksum from the same staged tree;
its short-lived Actions artifact is for independent QA, not a published release.
The clean-candidate check opens that exact archive with the builder uninstalled
and verifies Q001801 transliteration, cuneiform, lexeme edges and official
translation alignment through the pinned Text-Fabric runtime.

## Distribution identity versus public acquisition

The `manifest.repository` field currently contains the registered **logical**
dataset repository identity `ORACC-TF-assyrian-royal-inscriptions`. That is
**not** a working download URL or proof that a separate dataset repository
exists. The **published** v1.0.0 ZIP and checksum are available from the actual
[GitHub Release](https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0).
Use that published URL, the `release_id`, and the `source_state` /
`builder_commit` recorded inside the ZIP for reproducibility.

## Published v1.0.0 and acceptance

The [v1.0.0 GitHub Release](https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0)
**already exists**, with `assyrian-royal-inscriptions-1.0.0.zip` and its
matching `.zip.sha256` sidecar. The
[manually authorized publication run](https://github.com/alexsosn/ORACC-TF/actions/runs/38128162676)
built and validated the pinned RIAO/RINAP+TEI corpus, tested clean
Text-Fabric/browser consumption without the builder, then downloaded the newly
published ZIP and sidecar over public URLs and checked their SHA-256.

**Do not rerun the publication switch** to try to update the existing release:
the workflow deliberately refuses an already existing `v1.0.0` tag or
release. Published v1.0.0 asset bytes are **immutable**; subsequent changes to
`main` researcher documentation do not retroactively update the manual inside
that ZIP. A correction to the published dataset requires a separately planned
version/release, not an overwrite.

The existing [quick start](docs/reference/quick-start.md) and
[installation/measurement guide](docs/reference/installation.md) identify
the actual public assets and their checksum. A **logically independent**
fresh-machine reviewer still needs to download those exact public bytes,
verify the sidecar, load representative RIAO/RINAP and aligned TEI in Python,
and exercise the browser before [#23](https://github.com/alexsosn/ORACC-TF/issues/23)
and [#83](https://github.com/alexsosn/ORACC-TF/issues/83) can be closed.

Source rights, credits, and attribution must remain specific to the upstream
RIAO/RINAP editions and TEI material; publishing the archive did not convert
those rights into the repository's MIT software licence.

## Licence

Software authored for this repository—including converter code, scripts, tests,
and supporting software documentation—is licensed under the
[MIT License](LICENSE).

The MIT licence does **not** apply to ORACC corpus texts, translations,
annotations, metadata, or other upstream/derived data. Those retain the terms
of their original sources. See [`LICENSE_SCOPE.md`](LICENSE_SCOPE.md) for the
code/data boundary and the corpus documentation for source-specific attribution
and licensing.
