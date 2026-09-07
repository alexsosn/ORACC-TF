---
id: P-006
title: Issue-backed executable backlog bridge
type: plan
status: active
priority: P0
depends_on: [P-004]
updated: 2026-09-07
---

# Issue-backed executable backlog bridge

## Goal

Keep executable GitHub work selectable by the P-004 coordination loop even when a ticket was created after the original P-001–P-005 registry bootstrap and does not yet belong to a dedicated R/P document.

This file is intentionally an index, not a second specification. The mapped GitHub issue remains authoritative for research, design, TDD, acceptance criteria, production-integration dependencies, and independent-review gates. Registry `blocked_by` entries below represent dependencies that must be satisfied before the issue may be claimed at all. Where an issue explicitly permits research/design before a later production dependency, the ticket remains claimable and the issue's own stop conditions prevent premature integration/finalization.

Issue #48 remains the dispatcher/meta issue and is deliberately not a selectable task.

## ISSUE-32

ETCSRI morphology-rich TF dataset research/design/TDD — GitHub #32.

## ISSUE-33

ASBP/NINMED re-conversion and pinned cross-validation — GitHub #33.

## ISSUE-34

Translation-source policy for future corpus expansion — GitHub #34.

## ISSUE-35

Tier-2 ORACC-TF corpus-wave research and sequencing — GitHub #35.

## ISSUE-36

RINAP witnesses, exemplar linkage, and alignment-limit research — GitHub #36.

## ISSUE-38

TEI translation token cross-check against `index-tra` — GitHub #38.

## ISSUE-40

QPN glossary/proper-name entity-layer research — GitHub #40.

## ISSUE-41

Tier-3 small coherent corpus-wave evaluation — GitHub #41.

## ISSUE-42

Independent TEI translation-upstream discovery/versioning — GitHub #42.

## ISSUE-44

Legacy extraction workflow reconciliation with P-002 acquisition — GitHub #44.

## ISSUE-46

Pinned TEI ZIP/source-state support in translation auditing — GitHub #46.

## ISSUE-47

Generated-statistics documentation policy reconciliation — GitHub #47.

## ISSUE-58

Source-faithful OBABAT TF conversion — GitHub #58.

## ISSUE-69

BHSA/Text-Fabric application/browser gap research — GitHub #69.

## ISSUE-70

Per-dataset Text-Fabric application/browser implementation plan — GitHub #70.

## ISSUE-71

Per-dataset app packaging and Text-Fabric discovery — GitHub #71.

## ISSUE-72

Source-faithful cuneiform/transliteration/lexeme display formats — GitHub #72.

## ISSUE-73

Browser presentation policy, feature visibility, and docs integration — GitHub #73.

## ISSUE-74

Generated app provenance and collision-safe ORACC source links — GitHub #74.

## ISSUE-75

End-to-end Text-Fabric browser acceptance tests — GitHub #75.

## Maintenance rule

When one of these workstreams gains a dedicated normative plan, move its task to that plan without changing the task id or GitHub issue mapping unless there is an explicit migration. When an issue closes, registry status/evidence must be reconciled in the same merge window so closed work cannot remain falsely selectable or produce a GitHub/registry conflict.
