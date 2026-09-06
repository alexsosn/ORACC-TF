---
id: R-004
title: Parallel agent coordination and failure modes
type: research
status: done
priority: P0
depends_on: []
updated: 2026-09-05
---

# Parallel agent coordination and failure modes

## Scope

This note records the repository state examined for issue #43 and the constraints used to design a parallel-safe task loop. It covers coordination only; corpus semantics and ORACC acquisition behavior are out of scope.

## Existing model

`docs/registry.json` records task identifiers, dependencies, priority, durable status, and completion evidence. `scripts/check_docs_registry.py` checks document/registry drift, dependency references, cycles, and impossible completed dependencies. `docs/README.md` tells a worker to choose the first ready task by priority and identifier.

The model has no durable mapping from an unfinished task to its GitHub issue, no claim/lease identity, no implementation-session identity, no active-PR binding, and no review-session provenance. The checker therefore cannot reconcile git state with live GitHub state.

The current repository supplied a concrete race witness during the audit: open PRs #12 and #13 both targeted `P-001.M9`, while the registry still represented `P-001.M9` as unowned work. Existing active work on `P-002.PH1` and `P-003.PH0` was likewise visible through GitHub activity rather than machine-readable registry coordination state.

## Failure modes

### Simultaneous selection

Two workers following the old selector can choose the same ready task before either observes the other's branch or PR. A branch name is not an atomic claim and does not provide deterministic arbitration.

### Abandoned ownership

A permanent `in_progress` flag can deadlock work after a worker disappears. Treating age alone as permission to take over work can instead produce two active implementations. Recovery therefore needs an expiring lease plus an explicit recovery record.

### Duplicate implementation PRs

Issue or branch naming conventions do not establish which PR owns a task. The task loop needs one active implementation PR, with explicit supersession when an older PR is intentionally replaced.

### Dependency changes

A dependency can change after implementation starts. Checking dependencies only during initial selection permits a task to be finalized against an invalidated prerequisite. Dependencies must be checked again at completion.

### Review identity

Parallel agents can publish through the same GitHub account. GitHub login is therefore insufficient evidence that implementation and review were performed by separate runs. Machine-readable session identifiers are required, together with the exact reviewed head SHA.

### Shared evidence writes

Large evidence payloads embedded in one registry file force unrelated implementation PRs to edit the same shared structure. New completion/blocker evidence should live in task-specific files; legacy inline evidence remains readable during migration.

## Design constraints derived from the audit

- Git stores normative task/dependency metadata and durable completion or blocker evidence.
- GitHub issue and PR history stores ephemeral ownership, recovery, supersession, and review events.
- Claims are leases rather than permanent locks.
- Claim arbitration is deterministic from GitHub comment identifiers.
- A losing claimant must reselect; unrelated tasks remain claimable.
- Stale ownership is visible until an explicit recovery event references it.
- Completion requires rechecking dependencies, unique implementation ownership, and an independent passing review of the exact final head.
- Registry/GitHub disagreement is surfaced as a conflict instead of being silently repaired.
- Recognized malformed coordination markers fail closed.

The executable contract is defined in [P-004](../plans/P-004-agent-coordination.md) and `oracc_tf.coordination`.