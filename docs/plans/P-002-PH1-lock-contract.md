---
id: P-002-PH1
title: Upstream configuration and lock execution plan
type: plan
status: draft
priority: P0
depends_on: [R-002-PH1, P-002]
blocks: []
updated: 2026-09-05
---

# P-002 Phase 1 execution plan — upstream configuration and lock

Date: 2026-09-05
Depends on: P-002.PH0
Research: `docs/research/R-002-PH1-lock-contract.md`

## Gate 1 — policy and deterministic model

**RED first:** add tests for `upstream.toml` parsing, exact source/policy values, deterministic lock serialization under input reordering, required per-archive fields, canonical `text_ids_sha256`, and rejection of malformed/duplicate/out-of-scope records.

**Implementation:** add the hand-edited `upstream.toml` and a small stdlib-only lock/config module. No network client belongs in this gate.

**Test:** fast suite plus registry check. The new tests must fail before the production API/config exists and pass after implementation.

## Gate 2 — live provenance backfill

Add a serial backfill command that derives the eleven tracked archives from `datasets.toml`, downloads only canonical `/json/<archive>.zip` URLs with the configured User-Agent, validates ZIP structure, computes archive SHA-256/bytes, extracts lock metadata, computes extraction paths and text-id/content hashes, and compares extracted source files with the committed `data/` tree without modifying it.

The command writes deterministic `upstream.lock.json` and a deterministic backfill report. Any archive fetch/parse failure, missing licence evidence, or unexplained extraction mismatch is a hard failure.

## Gate 3 — clean-checkout reproducibility

In CI, regenerate from a clean checkout using the URLs recorded by the lock. Assert byte-for-byte equality of regenerated lock serialization and verify the extraction comparison result is either exact or fully enumerated in the committed report. Run fast + whole-corpus suites after provenance work.

## Finalization gate

Update `docs/registry.json` only after all Phase 1 acceptance criteria are evidenced. Run exact-head CI. Then perform an independent skeptical review of the complete PR diff; fix every blocker, rerun exact-head CI, and repeat independent review before ready/merge.
