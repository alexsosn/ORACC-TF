---
id: G-002
title: Development setup and conventions
type: guide
status: active
priority: P1
depends_on: []
updated: 2026-08-29
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
