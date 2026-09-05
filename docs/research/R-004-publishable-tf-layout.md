---
id: R-004
title: Publishable Text-Fabric output layout
type: research
status: done
priority: P0
depends_on: []
updated: 2026-09-05
---

# Publishable Text-Fabric output layout

## Decision

The repository-standard publishable Text-Fabric root is:

```text
<output-base>/<dataset>/tf/<tf_version>/
```

`dataset` is the stable dataset identity from `datasets.toml`. `tf_version` is the converter schema version `oracc_tf.TF_VERSION`. Upstream ORACC dates, archive hashes, and source-state digests remain release/provenance identity and do not enter the stable filesystem path. The version directory is independently loadable by Text-Fabric and owns coordinated sidecars such as `zero-span.json`.

The high-level publication path is resolved by `oracc_tf.publishing.build_registered_tf()`. Low-level corpus builders retain arbitrary output directories for fixtures and internal validation. The registered builder fails closed for unknown datasets, unwired registered datasets, unsafe identifiers, non-SemVer versions, and any requested `tf_version` that differs from the converter's actual `TF_VERSION`.

No immutable publishable TF release using a conflicting repository layout existed when this contract was adopted, so no migration shim is required. Agora's `/tf/` discovery convention is compatible evidence, not the normative reason for the design.

## TDD evidence

Initial test-only RED run `33982968272` failed 21 new layout assertions because the canonical-root and registered-builder APIs did not yet exist; 80 pre-existing fast tests passed and 1 skipped. A later review found a schema-identity hole: caller-supplied `tf_version` could relabel current converter bytes. After correcting an unrelated test-fixture error, clean RED run `33983503132` failed exactly that one regression while 101 other fast tests passed and 1 skipped.

The fix is commit `cd9db297a4b5ed7e2d272258af3a22043072c3c9`. Exact-head GREEN runs are:

- `33983685262` — standard tests, including fast tests and whole-corpus invariants;
- `33983685320` — real-corpus generated-reference/drift validation;
- `33983685383` — retained M8 Old Babylonian cross-validation.

## Review checklist

Independent review must verify dataset/version/source-state separation, path traversal rejection, registered-dataset fail-closed behavior, standalone Text-Fabric loading, sidecar placement, schema-version anti-mislabeling, and reuse of the shared resolver by future packaging rather than duplicated path construction.
