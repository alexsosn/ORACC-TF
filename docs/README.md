---
id: INDEX
title: ORACC-TF documentation index
type: index
status: active
priority: P0
updated: 2026-09-05
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
| `task-state/` | task-specific completion or blocker evidence | agents, maintainers |

Research and plans stay in the repository rather than a GitHub wiki: they must
be reviewable in pull requests next to the code they describe.

## Documents

| id | title | status | prio | depends on |
|---|---|---|---|---|
| [R-001](research/R-001-corpus-selection.md) | Which ORACC projects are worth converting | done | P0 | — |
| [R-002](research/R-002-upstream-automation.md) | Upstream change detection and publication | active | P0 | R-001 |
| [R-003](research/R-003-documentation.md) | Documentation architecture | active | P1 | R-001, P-001 |
| [R-004](research/R-004-agent-coordination.md) | Parallel agent coordination and failure modes | done | P0 | — |
| [P-001](plans/P-001-riao-rinap-tf.md) | Joined RIAO + RINAP TF module (TDD) | draft | P0 | R-001 |
| [P-002](plans/P-002-upstream-automation.md) | Automate ORACC upstream updates | draft | P0 | R-002, P-001 |
| [P-003](plans/P-003-documentation.md) | User documentation | draft | P1 | R-003, P-001 |
| [P-004](plans/P-004-agent-coordination.md) | Parallel-safe research-design-TDD-review loop | active | P0 | R-004 |
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
(`P-001.M1`, `P-002.PH3`, …). The parallel coordination contract is
[P-004](plans/P-004-agent-coordination.md); `oracc_tf.coordination` is the
executable reconciler for normalized registry/GitHub snapshots.

**Protocol**

1. **Enumerate.** Read `registry.json` and collect **all dependency-ready**
   `todo` tasks. Priority and task id order the candidate set; they do not give
   a worker ownership. Never start a task whose dependencies are unmet.
2. **Reconcile.** For each candidate, read its mapped GitHub issue comments and
   open implementation PRs and reconcile them with `oracc_tf.coordination`.
   Only a task whose runtime phase is `ready` may be claimed. `conflict` and
   unrecovered `stale` states are fail-closed for that task; unrelated ready
   work remains available.
3. **Claim.** Post an expiring `oracc-tf:claim` marker, immediately re-read the
   issue and PR set, and run reconciliation again. Proceed only when
   `claim_result()` says this session owns the winning claim. A losing claimant
   selects another ready task. Recover an expired lease only with an explicit
   `oracc-tf:recover` marker referencing the stale claim.
4. **Ground and plan.** Open the task's `spec`, measure any required data fact,
   and record research/design decisions before changing production code. If a
   measurement contradicts a document, correct the document in the same work.
5. **Test first.** Commit the task's RED tests and observe the intended failure
   before implementing production behavior.
6. **Implement and verify.** Make the smallest implementation that satisfies
   the planned contract, then run the task acceptance gates and retained
   regression suites on the exact candidate head.
7. **Independent review.** Record a review session distinct from the
   implementation session and bind it to the exact head SHA. Any blocker enters
   a dev/review sub-loop: add a RED regression where applicable, fix, rerun the
   exact-head gates, and obtain a fresh independent review. Head movement makes
   the previous passing review stale.
8. **Record.** Re-check dependencies, write new durable completion or blocker
   evidence to the task's `evidence_file`, synchronize registry/issue state, and
   finalize only when reconciliation and acceptance gates agree. Legacy
   completed tasks may retain inline registry evidence.

**Stop conditions.** Do not continue a task while reconciliation reports a
non-race conflict or an unrecovered stale lease. Existing project stop
conditions also apply: a P-002 §5 gate fires; a philological judgement is
required (the sign ontology, chunk semantics); a licence question arises; or a
task's acceptance criteria cannot be evaluated. Blocked work produces durable
evidence and does not prevent unrelated ready tasks from advancing.

**Invariant.** No task may hand-write a count or percentage into prose. Numbers
come from a script that can be re-run. See R-003 §4.
