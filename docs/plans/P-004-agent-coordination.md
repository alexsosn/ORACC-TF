---
id: P-004
title: Parallel-safe research-design-TDD-review task loop
type: plan
status: active
priority: P0
depends_on:
  - R-004
updated: 2026-09-07
---

# Parallel-safe research-design-TDD-review task loop

## Goal

Allow multiple agents to advance unrelated ORACC-TF tasks concurrently without duplicate implementation, silent stale ownership, self-review, or loss of durable evidence.

## Sources of truth

Git contains normative task identifiers, dependencies, priority, durable status, GitHub issue mapping, and task-specific evidence pointers. GitHub issue/PR history contains leases, recoveries/releases, implementation ownership, supersession, and review provenance. Reconciliation must report disagreement; it must not silently mutate either source.

## Machine markers

New markers use JSON inside HTML comments so they remain visible in raw GitHub history without cluttering rendered prose.

Claim:

```text
<!-- oracc-tf:claim {"task":"P-004.PH0","session":"SESSION","base_sha":"SHA","expires_at":"RFC3339"} -->
```

Recovery and release:

```text
<!-- oracc-tf:recover {"task":"P-004.PH0","session":"SESSION","claim_id":COMMENT_ID} -->
<!-- oracc-tf:release {"task":"P-004.PH0","session":"SESSION","claim_id":COMMENT_ID} -->
```

Implementation PR:

```text
<!-- oracc-tf:implementation {"task":"P-004.PH0","issue":43,"session":"SESSION"} -->
```

Explicit replacement:

```text
<!-- oracc-tf:supersede {"task":"P-004.PH0","session":"SESSION","old_pr":PR_NUMBER} -->
```

Independent review:

```text
<!-- oracc-tf:review {"task":"P-004.PH0","review_session":"REVIEW_SESSION","implementation_session":"IMPLEMENTATION_SESSION","head_sha":"SHA","verdict":"pass"} -->
```

## Dependency semantics

Registry dependencies have two distinct meanings:

- `blocked_by`: **claim/start dependencies**. Every referenced task must be `done` before the task becomes `ready` and can be claimed.
- `completion_blocked_by`: **completion-only dependencies**. These do not prevent claiming when the issue explicitly permits research, design, fixture preparation, or other bounded work to start early. They must all be `done` before `validate_completion()` can pass and the task can be finalized.

Use `completion_blocked_by` only when the mapped issue explicitly defines what may proceed early and where production integration or merge must stop. A dependency that prevents any useful source-grounded work belongs in `blocked_by` instead. Both dependency sets participate in static existence, cycle, and completed-task validation.

## Runtime states

The durable registry uses `todo`, `blocked`, and `done`. Reconciliation computes runtime states:

- `ready`: claim/start dependencies are complete, issue is open, and no ownership event blocks selection;
- `claimed`: one session owns the live winning lease and no implementation PR is active;
- `review`: the winning session has the active implementation PR;
- `blocked`: the durable task is blocked or a claim/start dependency is incomplete;
- `stale`: an expired claim still requires explicit recovery;
- `conflict`: registry/GitHub disagreement, malformed coordination data, competing live sessions, duplicate unsuperseded PRs, or invalid ownership.

Completed tasks reconcile as `done` when their mapped issue is closed. Legacy completed tasks created before this protocol may remain unmapped.

## Selection and claim protocol

A worker must:

1. read current main, registry metadata, mapped issue comments, and open PRs;
2. enumerate all `ready` tasks rather than relying on a repository-global lock;
3. select the highest-priority available task and post a claim marker;
4. immediately re-read the issue and PR set;
5. resolve claims by ascending GitHub comment id; repeated claims from the same session are idempotent;
6. proceed only when `claim_result()` reports that session as owner; a losing session reselects another ready task;
7. create the implementation PR with the matching task, issue, and implementation session.

Different tasks can be claimed concurrently. Multiple live sessions for one task produce an explicit conflict state even though the earliest comment remains the deterministic winner.

## Lease recovery

Expiry never makes a task silently available. An expired claim produces `stale`. A new worker posts a recovery marker referencing the stale claim id, then posts a new claim and re-runs reconciliation. A live claim cannot be recovered. A normal owner can relinquish work with a release marker.

## PR ownership and supersession

A task has at most one active implementation PR. When an old PR must remain open while a replacement is prepared, the replacement must carry a supersession marker referencing every older active implementation PR for that task. The active PR implementation session must equal the winning claim session.

## Completion gate

Before a task is finalized, the worker re-reads current state and verifies:

- every claim/start dependency and every completion-only dependency is still `done`;
- the task has one valid winning claim and one active implementation PR;
- PR task/issue/session metadata agrees with the registry and claim;
- tests and required external gates pass on the exact candidate head;
- an independent review marker records a different review session, the implementation session, the exact final head SHA, and a passing verdict;
- any review blocker is fixed, tests rerun, and the changed head is independently reviewed again.

Moving the PR head invalidates an earlier passing review marker.

## Evidence and merge behavior

New completion or blocker evidence is stored under `docs/task-state/` in a task-specific JSON file referenced by the task. Existing inline evidence remains valid for completed pre-protocol work. Stable task metadata can remain in the registry while independent PRs write different evidence files, reducing shared-file contention.

Registry metadata still needs normal git conflict handling. Issue mappings and evidence-file paths must be unique; the static checker rejects duplicates.

## PH0 — coordination protocol and reconciliation

Issue: #43.

### RED tests

`tests/test_agent_coordination.py` must cover:

- independent claims on unrelated ready tasks;
- deterministic same-task race arbitration and idempotent duplicate claims;
- stale lease recovery;
- dependency changes before completion;
- duplicate PR conflict and explicit supersession;
- implementation-session mismatch;
- self-review and stale-head review rejection;
- blocked work not hiding unrelated ready tasks;
- unique issue/evidence mapping;
- registry/GitHub completion disagreement;
- fail-closed malformed markers.

### Exit criteria

- the RED suite is recorded before production implementation;
- `oracc_tf.coordination` passes the behavioral suite;
- static registry checking understands the coordination metadata and task-specific evidence convention;
- developer documentation describes claim/recovery/review commands and stop behavior;
- current unfinished registry tasks have durable issue mappings;
- current duplicate/in-flight work is reconciled or explicitly documented for migration;
- exact-head CI passes;
- an independent review of the exact final head passes, with any blockers resolved through the dev/review sub-loop.

## Issue-backed executable backlog bridge

Open executable tickets created outside the original P-001–P-005 task lists are also registered here so P-004 can select them. Their GitHub issue bodies remain the authoritative research/design/TDD/review specification; this section supplies stable task/spec anchors only. Issue #48 is the dispatcher/meta issue and is deliberately not selectable.

For tickets whose issue explicitly permits research/design before a later production dependency, put only the true claim/start gate in `blocked_by` and put later integration/finalization dependencies in `completion_blocked_by`. The worker must still obey all issue-local integration, merge, and stop conditions.

### ISSUE-32
ETCSRI morphology-rich TF dataset research/design/TDD — GitHub #32.

### ISSUE-33
ASBP/NINMED re-conversion and pinned cross-validation — GitHub #33.

### ISSUE-34
Translation-source policy for future corpus expansion — GitHub #34.

### ISSUE-35
Tier-2 ORACC-TF corpus-wave research and sequencing — GitHub #35.

### ISSUE-36
RINAP witnesses, exemplar linkage, and alignment-limit research — GitHub #36.

### ISSUE-38
TEI translation token cross-check against `index-tra` — GitHub #38.

### ISSUE-40
QPN glossary/proper-name entity-layer research — GitHub #40.

### ISSUE-41
Tier-3 small coherent corpus-wave evaluation — GitHub #41.

### ISSUE-42
Independent TEI translation-upstream discovery/versioning — GitHub #42.

### ISSUE-44
Legacy extraction workflow reconciliation with P-002 acquisition — GitHub #44.

### ISSUE-46
Pinned TEI ZIP/source-state support in translation auditing — GitHub #46.

### ISSUE-47
Generated-statistics documentation policy reconciliation — GitHub #47.

### ISSUE-58
Source-faithful OBABAT TF conversion — GitHub #58.

### ISSUE-69
BHSA/Text-Fabric application/browser gap research — GitHub #69.

### ISSUE-70
Per-dataset Text-Fabric application/browser implementation plan — GitHub #70.

### ISSUE-71
Per-dataset app packaging and Text-Fabric discovery — GitHub #71.

### ISSUE-72
Source-faithful cuneiform/transliteration/lexeme display formats — GitHub #72.

### ISSUE-73
Browser presentation policy, feature visibility, and docs integration — GitHub #73.

### ISSUE-74
Generated app provenance and collision-safe ORACC source links — GitHub #74.

### ISSUE-75
End-to-end Text-Fabric browser acceptance tests — GitHub #75.

When one of these workstreams gains a dedicated normative R/P document, move its registry task to that document without changing the task id or GitHub issue mapping unless an explicit migration says otherwise. When an issue closes, reconcile registry status/evidence in the same merge window so closed work cannot remain falsely selectable.