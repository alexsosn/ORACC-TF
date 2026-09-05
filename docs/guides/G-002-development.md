---
id: G-002
title: Development setup and conventions
type: guide
status: active
priority: P1
depends_on: []
updated: 2026-09-05
---

# Development setup and conventions

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Python 3.12 — Text-Fabric needs ≥3.9 and 3.12 is the current stable target.
`uv` is used because the locally installed 3.12 cannot build a venv with
`python -m venv` (it is a relocated uv-managed interpreter).

## Layout

```
programs/oracc_tf/      the converter package (importable as oracc_tf)
tests/                  pytest suite, one module per milestone
scripts/                standalone maintenance tools, stdlib only
data/                   the ORACC snapshot (see README)
docs/                   research, plans, guides; see docs/README.md
```

`scripts/` stays dependency-free so it runs against a bare Python; anything
needing the package lives in `programs/`.

### Publishable Text-Fabric dataset roots

A publishable dataset root has exactly this grammar:

```text
<output-base>/<dataset>/tf/<tf_version>/
```

`dataset` is the stable dataset identity from `datasets.toml`. `tf_version` is
the Text-Fabric schema version (`oracc_tf.TF_VERSION`) and is a SemVer value.
Upstream ORACC dates, archive hashes, and release source-state digests do **not**
appear in this path; they belong to release/provenance metadata and tags. This
keeps dataset identity stable when source bytes change without a schema change
and lets multiple schema versions coexist without collision.

The version directory is the independently loadable Text-Fabric root. It must
contain the TF warp (`otype.tf`, `oslots.tf`, `otext.tf`) and coordinated
sidecars such as `zero-span.json`. Consumers and packaging code must resolve
this root through the shared layout helper rather than duplicating string path
logic. Dataset and version identifiers are validated before any path is
constructed; absolute paths, separators, traversal components, and ambiguous
identifiers are rejected.

This `/tf/` boundary is an ORACC-TF repository contract. It is also compatible
with Agora Context-Fabric discovery, but downstream compatibility is evidence,
not the reason for the invariant.

Architecture/TDD evidence for issue #14: the initial test-only RED run
`33982968272` failed 21 new layout assertions because the canonical-root and
registered-builder APIs did not exist, while 80 pre-existing fast tests passed
and 1 skipped. Review then found a schema-identity hole: a caller could request
a different `tf_version` and relabel the current converter bytes. After fixing
an unrelated test-fixture error, clean RED run `33983503132` failed exactly
that one regression while 101 other fast tests passed and 1 skipped. The guard
landed at `cd9db297a4b5ed7e2d272258af3a22043072c3c9`; exact-head GREEN runs were
`33983685262` (standard fast + whole-corpus), `33983685320` (real-corpus
generated-reference/drift), and `33983685383` (retained M8 cross-validation).
No immutable publishable TF release using a conflicting repository layout
existed when this contract was adopted, so no migration shim is required.

## Tests

```bash
pytest -q                    # everything
pytest -q -m "not corpus"    # fast: unit + fixture only (~2 s)
pytest -q -m corpus          # whole-corpus invariants (~25 s)
```

Tests touching all 2,081 editions carry `@pytest.mark.corpus` so the inner
loop stays fast. CI runs both.

Each test module names the milestone it satisfies and quotes the acceptance
criteria from the plan in its docstring, so a failure points at the spec.

## Conventions

**Test first.** Every milestone in [P-001](../plans/P-001-riao-rinap-tf.md)
names its red tests. Write them, watch them fail, then implement.

**Assert content, not just counts.** P-001 §2.3 records a rule that produced
the right sign total while 6,588 slots held the wrong content. A count-based
test would have passed. Where a milestone concerns semantics, assert the
values.

**Measure, don't infer.** If a task needs a fact about the data, compute it.
R-001's figures have been corrected twice and both corrections came from
measuring rather than reasoning from an earlier document.

**Numbers live in code, not prose.** No hand-written count in any Markdown
file; see [R-003](../research/R-003-documentation.md) §4.

## Reporting

```bash
python -m oracc_tf.loader --list-unreadable   # the four edition cardinalities
python scripts/check_docs_registry.py         # registry vs documents
python scripts/scan_annotation.py --csv       # annotation depth per corpus
python scripts/audit_translations.py --tei DIR
```

## Task loop

Work is selected from [`docs/registry.json`](../registry.json) using the
protocol in [docs/README.md](../README.md). Mark a task `done` only when its
acceptance criteria pass, and record `evidence` — the command and its result.
