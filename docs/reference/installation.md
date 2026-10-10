---
title: Lightweight local installation
status: active
---

# Lightweight local installation

The 1.0 researcher path is a versioned standalone
`assyrian-royal-inscriptions` release archive. It contains the Text-Fabric
data, generated app, researcher documentation, and release manifest. Using the
corpus does not require cloning the central ORACC-TF builder/source repository.

## Runtime

Install the Text-Fabric version used by the measured candidate:

```bash
python -m pip install text-fabric==13.1.0
```

After extracting the release, run Python from its root:

```python
from pathlib import Path
from tf.app import use

root = Path.cwd()
A = use(f"app:{root / 'app'}")
```

For the browser, the tested Text-Fabric 13.1 route is:

```bash
tf "app:$PWD/app"
```

On shells without `$PWD`, replace that expression with the absolute path to
the extracted `app` directory. The generated app discovers the sibling
`tf/<version>` data tree; no ORACC-TF Python package or raw ORACC source tree
is needed by the consumer.

## Measured standalone candidate (10 October 2026)

A source-aware clean-consumer measurement is [GitHub Actions run
38070730938](https://github.com/alexsosn/ORACC-TF/actions/runs/38070730938),
job `standalone-candidate` at head
`4a9c017426fa5faa5b370d3d0959799fab182e16`. The ORACC-TF builder was
uninstalled before the user-path checks. Cold Python and browser measurements
were each repeated three times; timings and peak RSS below are medians on a
GitHub Actions Ubuntu runner, **not minimum hardware requirements or promises
for a different machine**.

| quantity | measured value |
|---|---:|
| measurement-only ZIP | **41,294,294 bytes** (41.3 MB decimal) |
| extracted tree before first load | **340,824,705 bytes** |
| extracted tree after first load (including generated cache) | **388,746,881 bytes** |
| cold Python startup, 3-run median | **27.279 s** |
| cold Python peak RSS, 3-run median | **1,837,544 KiB** (about 1.75 GiB) |
| cold browser startup, 3-run median | **28.829 s** |
| cold browser peak RSS, 3-run median | **1,830,660 KiB** (about 1.75 GiB) |
| representative query, median | **0.044 s** |
| largest TF node slot | **793,340** |

**Artifact distinction:** the measurement-only ZIP contains an extra
`assyrian-royal-inscriptions/` root directory to support the resource
benchmark. The **versioned release-format ZIP** from the same workflow has the
canonical `manifest.json`, `app/`, `tf/`, `docs/` layout at archive root.
They are **different archives**, with different bytes and checksums; a
measurement ZIP's hash must never be used to verify a published release.
The workflow also extracts and smoke-loads the exact versioned release-format
candidate independently. Use the sidecar belonging to the *published asset*
when one exists.

The query, translation/lexeme, original cuneiform/transliteration, and browser
routes `/`, `/passage`, `/query`, `/export` passed on the candidate.
The source-aware browser acceptance and public feature-help link are tracked
separately under [#75](https://github.com/alexsosn/ORACC-TF/issues/75).
A passing CI run does **not** mean that a v1.0.0 public asset already exists.

## Default feature loading

The release retains the complete TF feature set on disk. The generated app keeps
large raw/audit and duplicate provenance features out of the normal interactive
preload when they are not needed for navigation, text display, lexical
inspection, or aligned translation reading.

The measured default still preloads the researcher-facing fields needed for
normal work, including `document_key`, `source_id`, `form`, `utf8`,
`cf`, `gw`, `sense`, `pos`, `lang`, `translation_text`, section
features, and `synthetic`.

An excluded feature remains available from the same dataset. Load one explicitly
when an audit task needs it:

```python
A.load("src_path sig translation_text_raw")
```

The earlier three-JSON-feature preload benchmark used about
2,088,904 KiB peak RSS for Python. The current conservative default profile
already excludes additional nonessential provenance fields while retaining
navigation, word/lexeme inspection, and aligned translations. In the latest
run, **further** experimental lean exclusions used 1,840,624 KiB for Python
and 1,833,060 KiB for the browser: no persuasive additional memory reduction
over the current default was observed. Do not discard researcher-facing
features or expand the exclusion list based only on run-to-run noise.

## Release identity

`manifest.json` records the dataset, TF schema version, release id, builder
commit, source state, and content digests used by the standalone distribution.
For a published release, verify the archive checksum supplied with that release
before extraction.
