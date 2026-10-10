---
title: Reproducibility
status: active
---

# Reproducibility and source identity

For normal reading and querying, you only need the released standalone
`assyrian-royal-inscriptions` archive described in the
[quick start](quick-start.md). You do **not** need the ORACC-TF development
checkout or raw upstream corpus exports.

The reproducibility record answers two different questions: **which exact
corpus did I query?** (release identity), and **how could a maintainer rebuild
it?** (source and converter identity). Do not confuse those operations.

## Record the release you actually used

The extracted release contains `manifest.json`. Record its dataset,
version, release id, source state, and builder commit with your research
output. For example, from the extracted distribution root:

```python
import json
from pathlib import Path

root = Path.cwd()
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
release_identity = {
    "dataset": manifest["dataset"],
    "release_id": manifest["release_id"],
    "tf_version": manifest["tf_version"],
    "builder_commit": manifest["builder_commit"],
    "source_state": manifest["source_state"],
    "tf_root": manifest["tf_root"],
}
print(release_identity)
```

`tf_version` identifies the **Text-Fabric corpus schema/layout version**,
not necessarily the version of the Python builder. The manifest's
`source_state` is a SHA-256 identity of the pinned source state, and
`builder_commit` is the Git commit used to convert it. Both are essential
if the same schema version is rebuilt with different inputs.

For downloading, use the published ZIP and its **matching release checksum**,
not the checksum of any upstream translation archive. Public asset
publication and user acquisition are governed by the separate release work;
the locally tested ZIP candidate is not by itself evidence of a public
download. Verify the final release asset digest before extraction.

## Inspect source-to-TF completeness

The source-to-TF audit record is maintained in
[`docs/task-state/ISSUE-124.json`](https://github.com/alexsosn/ORACC-TF/blob/main/docs/task-state/ISSUE-124.json)
in the **builder repository**. It enumerates the registered source
population, semantic sign/word/document counts, deviations in joined
catalogues, intentionally empty or unreadable upstream members, and
unexplained source-to-TF mismatches. Its `audit.source.source_state_sha256`
corresponds to the `source_state` recorded by publication.

Researchers can read the [source-to-TF audit](data-audit.md) and
[generated feature reference](features.md) directly from their standalone
documentation. Counts and coverage should be derived from the selected
release and its audit rather than copied from an unrelated source date.

In particular, a missing catalogue record, an unresolved TEI alignment, or
a source stub must not be silently filled with another document's data.
The current [translations page](translations.md) explains explicit TEI
alignment gaps and the absence of official running translation coverage for
`rinap5p1` in the pinned archive.

## Maintainer rebuild inputs

Rebuilding is a **separate maintainer activity**. It requires an ORACC-TF
builder checkout at the recorded `builder_commit`, its recorded RIAO/RINAP
source snapshot, the registered dataset definition, and the pinned official
translation archive `riao-teiCorpus-20241202.zip`.

The official translation archive is checked by SHA-256:

```text
b793d8920db58908e3a044b7f2d1a204c1ba0784e880007e0cd7941333e841bd
```

The builder script `scripts/download_m9_tei.sh` downloads that archive and
checks its digest. The Python publication entry point
`oracc_tf.publishing.build_registered_tf` requires its
`translations_archive` argument (or `ORACC_TF_M9_TEI_ARCHIVE` environment
variable) for a registered build. It rejects absent or changed archives;
building without a translation-bearing source must not be mistaken for the
release candidate. See the
[builder source and tests](https://github.com/alexsosn/ORACC-TF) for the
rebuild path.

The `ISSUE-124` audit, `manifest.json`, the pinned input archive, and
`tf/<version>` together give a practical 1.0 source/build identity without
requiring automated upstream polling, historical source locks, or release
certification machinery.

## Licence and attribution boundaries

Do not infer that all of the TF data has one blanket licence:

- RIAO/RINAP `corpusjson` edition metadata currently records **CC0**.
- The official TEI translation header does **not** independently assert
  an identical per-unit grant. ORACC's published default is **CC BY-SA 3.0**
  unless a project specifies other terms; the converter records that
  qualification rather than claiming the translations are CC0.
- Consult the [translation attribution/licence note](translations.md),
  and preserve source acknowledgements and the licence attached to the
  exact resource you redistribute.

Those two source categories should stay distinct in downstream exports.
A release checksum guarantees byte identity, **not** copyright clearance.
