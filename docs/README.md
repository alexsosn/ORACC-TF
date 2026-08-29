---
id: INDEX
title: ORACC-TF documentation index
type: index
status: active
priority: P0
updated: 2026-08-29
---

# ORACC-TF documentation

Every document has an **id**, a **status**, a **priority** and explicit
**dependencies**, declared in YAML front-matter. [`registry.json`](registry.json)
is the machine-readable projection of all of it and is what an automated agent
reads to choose work.

## Layout

| folder | holds | audience |
|---|---|---|
| [`research/`](research/) | `R-NNN` — measured findings and why decisions were made | maintainers |
| [`plans/`](plans/) | `P-NNN` — what will be built, with phases and acceptance | maintainers, agents |
| [`guides/`](guides/) | `G-NNN` — how to operate the repository | maintainers |
| `reference/` | user-facing corpus documentation (created by P-003) | **users** |
| `reports/` | generated validation evidence | both |

Research and plans stay in the repository rather than a GitHub wiki: they must
be reviewable in pull requests next to the code they describe.

## Documents

| id | title | status | prio | depends on |
|---|---|---|---|---|
| [R-001](research/R-001-corpus-selection.md) | Which ORACC projects are worth converting | done | P0 | — |
| [R-002](research/R-002-upstream-automation.md) | Upstream change detection and publication | active | P0 | R-001 |
| [R-003](research/R-003-documentation.md) | Documentation architecture | active | P1 | R-001, P-001 |
| [P-001](plans/P-001-riao-rinap-tf.md) | Joined RIAO + RINAP TF module (TDD) | draft | P0 | R-001 |
| [P-002](plans/P-002-upstream-automation.md) | Automate ORACC upstream updates | draft | P0 | R-002, P-001 |
| [P-003](plans/P-003-documentation.md) | User documentation | draft | P1 | R-003, P-001 |
| [G-001](guides/G-001-scripts.md) | Utility scripts | active | P2 | — |
| [G-002](guides/G-002-development.md) | Development setup and conventions | active | P1 | — |

## Priorities

| | meaning |
|---|---|
| **P0** | on the critical path; nothing downstream can be trusted until it lands |
| **P1** | required for a usable public release, not for a correct one |
| **P2** | maintenance and convenience |

## Statuses

`draft` → not started · `active` → in progress · `done` → complete and verified
· `blocked` → waiting on a dependency · `superseded` → replaced, kept for history

---

## The agentic development loop

An agent works one **task** at a time. Tasks are the phases and milestones of
the plans, enumerated in [`registry.json`](registry.json) with stable ids
(`P-001.M1`, `P-002.PH3`, …).

**Protocol**

1. **Select.** Read `registry.json`. Take the lowest-numbered task that is
   `todo`, whose `blocked_by` are all `done`, at the highest available priority.
   Never start a task whose dependencies are unmet.
2. **Ground.** Open the `spec` section named by the task. It states the
   acceptance criteria. If the task requires a fact about the data, **measure
   it** — do not infer it from another document. R-001's figures have been
   corrected twice; both corrections came from measuring.
3. **Test first.** Every plan task names its red tests. Write them, watch them
   fail, then implement.
4. **Verify.** Run the task's acceptance criteria. A task is done only when
   they pass, not when the code exists.
5. **Record.** Set the task `status`, add `evidence` (the command run and its
   output location), and update the parent document's front-matter `updated`.
6. **Report contradictions.** If a measurement contradicts a document, fix the
   document in the same change and note it in the commit. Do not proceed on a
   known-false premise.

**Stop conditions.** An agent must stop and ask a human when: a gate in
P-002 §5 fires; a philological judgement is required (the sign ontology, chunk
semantics); a licence question arises; or a task's acceptance criteria cannot
be evaluated. Blocked work produces a report, never a silent pass.

**Invariant.** No task may hand-write a count or percentage into prose. Numbers
come from a script that can be re-run. See R-003 §4.
