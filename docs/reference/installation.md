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

## Measured 1.0 candidate

Clean standalone run **37078039146** measured the translation-bearing candidate
after the ORACC-TF builder package had been uninstalled. The runner was GitHub
Actions Ubuntu, so local timings vary with CPU, storage, and available memory.

| quantity | measurement |
|---|---:|
| release ZIP | about **41.3 MB** (41,264,487 bytes in the measured archive) |
| extracted tree before first load | about **340.8 MB** logical bytes |
| Text-Fabric cache created by first load | about **68.3 MB** |
| optimized cold Python startup | about **43 s** |
| optimized Python peak RSS | **1,839,064 KiB**, about **1.75 GiB** |
| optimized cold browser startup | about **43 s** |
| optimized browser peak RSS | **1,833,256 KiB**, about **1.75 GiB** |

The measured query after load completed in roughly 70 ms, and the browser
routes `/`, `/passage`, `/query`, and `/export` all returned HTTP 200.
These figures are performance evidence for the candidate, not guarantees for
other machines.

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

The first benchmark that excluded only the three largest raw JSON features used
about 2,088,904 KiB peak RSS for Python startup. The conservative default
profile used 1,839,064 KiB while preserving the representative query,
navigation, browser routes, text/lexical features, and translations.

## Release identity

`manifest.json` records the dataset, TF schema version, release id, builder
commit, source state, and content digests used by the standalone distribution.
For a published release, verify the archive checksum supplied with that release
before extraction.
