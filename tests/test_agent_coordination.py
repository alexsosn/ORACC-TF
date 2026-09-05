"""P-004.PH0 RED tests for parallel-safe task coordination.

Issue #43 acceptance requires GitHub-native leases/claims, one active PR per task,
merge-safe evidence, dependency re-checks, and exact-head independent review.
These tests intentionally precede ``scripts.task_coordination``.
"""

from datetime import datetime, timezone

import pytest

from scripts.task_coordination import (
    analyze,
    claim_result,
    ready_tasks,
    validate_completion,
    validate_registry,
)

NOW = datetime(2026, 9, 5, 13, 0, tzinfo=timezone.utc)
BASE = "a" * 40
HEAD = "b" * 40
NEW_HEAD = "c" * 40


def marker(kind, **payload):
    import json

    return f"<!-- oracc-tf:{kind} {json.dumps(payload, sort_keys=True)} -->"


def task(task_id, issue, *, status="todo", priority="P0", blocked_by=(), evidence_file=None):
    out = {
        "id": task_id,
        "title": task_id,
        "priority": priority,
        "blocked_by": list(blocked_by),
        "status": status,
        "issue": issue,
    }
    if evidence_file is not None:
        out["evidence_file"] = evidence_file
    return out


def registry(*tasks):
    return {"schema_version": 2, "tasks": list(tasks)}


def issue(number, *, state="open", comments=()):
    return {"number": number, "state": state, "comments": list(comments)}


def comment(cid, body):
    return {"id": cid, "body": body}


def pr(number, task_id, issue_number, session, *, head=HEAD, state="open", extra="", reviews=()):
    body = marker(
        "implementation",
        task=task_id,
        issue=issue_number,
        session=session,
    )
    if extra:
        body += "\n" + extra
    return {
        "number": number,
        "state": state,
        "head_sha": head,
        "body": body,
        "reviews": list(reviews),
    }


def snapshot(*issues, prs=()):
    return {
        "main_sha": BASE,
        "issues": list(issues),
        "pull_requests": list(prs),
    }


def live_claim(cid, task_id, session, *, expires="2026-09-05T14:00:00Z"):
    return comment(
        cid,
        marker(
            "claim",
            task=task_id,
            session=session,
            base_sha=BASE,
            expires_at=expires,
        ),
    )


def review(rid, task_id, reviewer, implementer, *, head=HEAD, verdict="pass"):
    return {
        "id": rid,
        "body": marker(
            "review",
            task=task_id,
            review_session=reviewer,
            implementation_session=implementer,
            head_sha=head,
            verdict=verdict,
        ),
    }


def test_two_workers_claim_different_ready_tasks_without_global_lock():
    reg = registry(task("A", 101), task("B", 102))
    snap = snapshot(
        issue(101, comments=[live_claim(10, "A", "session-a")]),
        issue(102, comments=[live_claim(20, "B", "session-b")]),
    )

    states = analyze(reg, snap, NOW)

    assert states["A"].phase == "claimed"
    assert states["A"].owner_session == "session-a"
    assert states["B"].phase == "claimed"
    assert states["B"].owner_session == "session-b"


def test_same_task_race_has_one_deterministic_winner_and_explicit_loser_conflict():
    reg = registry(task("A", 101))
    snap = snapshot(
        issue(
            101,
            comments=[
                live_claim(12, "A", "session-later"),
                live_claim(11, "A", "session-first"),
            ],
        )
    )

    states = analyze(reg, snap, NOW)

    assert states["A"].phase == "conflict"
    assert states["A"].owner_session == "session-first"
    assert claim_result(states["A"], "session-first") == "owned"
    assert claim_result(states["A"], "session-later") == "conflict"


def test_duplicate_claim_by_same_session_is_idempotent():
    reg = registry(task("A", 101))
    snap = snapshot(
        issue(
            101,
            comments=[
                live_claim(11, "A", "session-a"),
                live_claim(12, "A", "session-a"),
            ],
        )
    )

    state = analyze(reg, snap, NOW)["A"]

    assert state.phase == "claimed"
    assert state.owner_session == "session-a"
    assert state.winning_claim_id == 11


def test_expired_claim_is_stale_until_explicit_recovery_then_can_be_reclaimed():
    reg = registry(task("A", 101))
    expired = live_claim(11, "A", "old", expires="2026-09-05T12:00:00Z")

    stale = analyze(reg, snapshot(issue(101, comments=[expired])), NOW)["A"]
    assert stale.phase == "stale"
    assert "A" not in ready_tasks(reg, snapshot(issue(101, comments=[expired])), NOW)

    recovered_comments = [
        expired,
        comment(12, marker("recover", task="A", session="new", claim_id=11)),
        live_claim(13, "A", "new"),
    ]
    recovered = analyze(reg, snapshot(issue(101, comments=recovered_comments)), NOW)["A"]
    assert recovered.phase == "claimed"
    assert recovered.owner_session == "new"


def test_dependency_is_rechecked_before_completion():
    start = registry(task("A", 101, status="done"), task("B", 102, blocked_by=("A",)))
    snap = snapshot(
        issue(101, state="closed"),
        issue(102, comments=[live_claim(20, "B", "impl")]),
        prs=[pr(201, "B", 102, "impl", reviews=[review(1, "B", "reviewer", "impl")])],
    )
    assert validate_completion("B", start, snap, NOW) == []

    changed = registry(task("A", 101, status="blocked"), task("B", 102, blocked_by=("A",)))
    problems = validate_completion("B", changed, snap, NOW)
    assert any("dependency A is blocked" in p for p in problems)


def test_duplicate_active_prs_conflict_unless_new_pr_explicitly_supersedes_old_one():
    reg = registry(task("A", 101))
    claim = live_claim(10, "A", "impl")
    duplicate = snapshot(
        issue(101, comments=[claim]),
        prs=[pr(201, "A", 101, "impl"), pr(202, "A", 101, "impl")],
    )
    assert analyze(reg, duplicate, NOW)["A"].phase == "conflict"

    superseding = pr(
        202,
        "A",
        101,
        "impl",
        extra=marker("supersede", task="A", session="impl", old_pr=201),
    )
    resolved = snapshot(issue(101, comments=[claim]), prs=[pr(201, "A", 101, "impl"), superseding])
    state = analyze(reg, resolved, NOW)["A"]
    assert state.phase == "review"
    assert state.active_pr == 202


def test_active_pr_must_match_winning_claim_session():
    reg = registry(task("A", 101))
    snap = snapshot(
        issue(101, comments=[live_claim(10, "A", "winner")]),
        prs=[pr(201, "A", 101, "different-session")],
    )
    state = analyze(reg, snap, NOW)["A"]
    assert state.phase == "conflict"
    assert any("implementation session" in p for p in state.problems)


def test_independent_review_must_be_other_session_and_exact_final_head():
    reg = registry(task("A", 101))
    claim = live_claim(10, "A", "impl")

    self_review = snapshot(
        issue(101, comments=[claim]),
        prs=[pr(201, "A", 101, "impl", reviews=[review(1, "A", "impl", "impl")])],
    )
    problems = validate_completion("A", reg, self_review, NOW)
    assert any("self-review" in p for p in problems)

    stale_review = snapshot(
        issue(101, comments=[claim]),
        prs=[pr(201, "A", 101, "impl", head=NEW_HEAD, reviews=[review(1, "A", "reviewer", "impl")])],
    )
    problems = validate_completion("A", reg, stale_review, NOW)
    assert any("exact head" in p for p in problems)

    good = snapshot(
        issue(101, comments=[claim]),
        prs=[pr(201, "A", 101, "impl", reviews=[review(1, "A", "reviewer", "impl")])],
    )
    assert validate_completion("A", reg, good, NOW) == []


def test_blocked_task_does_not_hide_unrelated_ready_work():
    reg = registry(
        task("A", 101, status="blocked"),
        task("B", 102, blocked_by=("A",)),
        task("C", 103, priority="P1"),
    )
    snap = snapshot(issue(101), issue(102), issue(103))

    assert ready_tasks(reg, snap, NOW) == ["C"]


def test_registry_requires_unique_issue_mapping_for_unfinished_tasks():
    missing = registry(task("A", None))
    assert any("issue" in p for p in validate_registry(missing))

    duplicate = registry(task("A", 101), task("B", 101))
    assert any("issue 101" in p for p in validate_registry(duplicate))


def test_new_task_evidence_files_are_unique_but_legacy_inline_evidence_is_allowed():
    reg = registry(
        task("legacy", None, status="done"),
        task("A", 101, evidence_file="docs/task-state/A.json"),
        task("B", 102, evidence_file="docs/task-state/A.json"),
    )
    reg["tasks"][0]["evidence"] = {"tests": "legacy evidence"}

    problems = validate_registry(reg)

    assert not any("legacy" in p and "issue" in p for p in problems)
    assert any("evidence_file" in p and "A.json" in p for p in problems)


def test_github_and_registry_completion_disagreement_is_detected():
    reg = registry(task("A", 101, status="todo"))
    snap = snapshot(issue(101, state="closed"))
    state = analyze(reg, snap, NOW)["A"]
    assert state.phase == "conflict"
    assert any("closed" in p and "todo" in p for p in state.problems)


def test_done_task_with_open_issue_is_detected():
    reg = registry(task("A", 101, status="done"))
    snap = snapshot(issue(101, state="open"))
    state = analyze(reg, snap, NOW)["A"]
    assert state.phase == "conflict"
    assert any("done" in p and "open" in p for p in state.problems)


def test_malformed_marker_fails_closed_instead_of_becoming_a_claim():
    reg = registry(task("A", 101))
    bad = comment(10, '<!-- oracc-tf:claim {"task":"A",oops} -->')
    state = analyze(reg, snapshot(issue(101, comments=[bad])), NOW)["A"]
    assert state.phase == "conflict"
    assert any("malformed" in p for p in state.problems)
